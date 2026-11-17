"""Audio Asset Discovery, License/SHA-256 Verification, and Read-Only QA Adapter Catalog.

Guarantees:
- Never imports visual engines or mutates/imports external QA scripts (`tools/mix.py`, `build_audio.py`).
- Validates every file-backed asset for path traversal/symlink escapes, ffprobe + PCM decodability,
  finite samples, sample rate bounds, SHA-256 integrity, commercial usage rights, and CC BY attribution.
- Procedural native assets are truthfully labeled as `procedural` (never mislabeled 'copyright-free').
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf


VALID_SAMPLE_RATE_RANGE = (8000, 192000)


@dataclass
class LicensePolicy:
    allow_commercial_only: bool = True
    require_explicit_license_for_external: bool = True
    allow_user_file_without_sidecar: bool = False
    allowed_licenses: Tuple[str, ...] = (
        "procedural",
        "cc0",
        "cc-by",
        "cc-by-4.0",
        "cc-by-3.0",
        "mit",
        "user_licensed",
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AudioAsset:
    asset_id: str
    source: str  # "native_procedural" | "qa_music" | "qa_sfx" | "qa_real_sfx" | "user_file"
    asset_type: str  # "music" | "sfx" | "ambience"
    file_path: Optional[str] = None
    generator_name: Optional[str] = None
    duration_sec: float = 0.0
    sample_rate: int = 48000
    channels: int = 2
    tags: List[str] = field(default_factory=list)
    mood: str = "neutral"
    intensity: float = 0.5
    provenance: Dict[str, Any] = field(default_factory=dict)
    license_type: str = "procedural"
    author: str = ""
    title: str = ""
    source_url: str = ""
    license_url: str = ""
    commercial_use_allowed: bool = True
    attribution_required: bool = False
    attribution_text: str = ""
    content_sha256: str = ""
    expected_sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    ok: bool
    asset_id: str
    status: str  # "VERIFIED" | "REJECTED"
    reason: str
    needs_resample: bool = False
    computed_sha256: str = ""
    attribution_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResolutionResult:
    ok: bool
    asset: Optional[AudioAsset]
    validation: Optional[ValidationResult]
    score: float = 0.0
    fallback_used: bool = False
    reason: str = ""
    rejected_candidates: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "asset_id": self.asset.asset_id if self.asset else None,
            "score": round(self.score, 4),
            "fallback_used": self.fallback_used,
            "reason": self.reason,
            "rejected_candidates": self.rejected_candidates,
        }


def compute_file_sha256(path: Path, chunk_bytes: int = 262144) -> str:
    """Compute SHA-256 digest using bounded chunked streaming."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_bytes)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _is_path_within_roots(path: Path, allowed_roots: Optional[List[Path]]) -> Tuple[bool, str]:
    raw_str = str(path)
    if ".." in Path(raw_str).parts:
        return False, f"Path contains forbidden '..' segment: {raw_str}"
    if allowed_roots:
        try:
            resolved = path.resolve(strict=False)
        except Exception as exc:
            return False, f"Cannot resolve path '{raw_str}': {exc}"
        for root in allowed_roots:
            try:
                if resolved.is_relative_to(root.resolve()):
                    return True, ""
            except Exception:
                continue
        return False, f"Path '{resolved}' escapes trusted allowed roots {[str(r) for r in allowed_roots]}"
    return True, ""


def _probe_audio_stream_ffprobe(path: Path) -> Tuple[bool, Dict[str, Any], str]:
    try:
        res = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_type,sample_rate,channels,duration",
                "-show_entries", "format=duration,size",
                "-of", "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        data = json.loads(res.stdout or "{}")
    except Exception as exc:
        return False, {}, f"ffprobe failed to decode audio file '{path.name}': {exc}"

    streams = data.get("streams") or []
    if not streams:
        return False, data, f"No audio stream found inside '{path.name}'"
    st = streams[0]
    sr = int(st.get("sample_rate") or 0)
    ch = int(st.get("channels") or 0)
    dur_raw = st.get("duration") or data.get("format", {}).get("duration") or 0.0
    try:
        dur = float(dur_raw)
    except (TypeError, ValueError):
        dur = 0.0

    if not (VALID_SAMPLE_RATE_RANGE[0] <= sr <= VALID_SAMPLE_RATE_RANGE[1]):
        return False, {"sample_rate": sr, "channels": ch, "duration_sec": dur}, (
            f"Unsupported sample rate {sr} Hz (supported {VALID_SAMPLE_RATE_RANGE[0]}..{VALID_SAMPLE_RATE_RANGE[1]} Hz)"
        )
    if ch not in (1, 2):
        return False, {"sample_rate": sr, "channels": ch, "duration_sec": dur}, (
            f"Unsupported channel count {ch} (only mono=1 or stereo=2 supported)"
        )
    if dur <= 0.015:
        return False, {"sample_rate": sr, "channels": ch, "duration_sec": dur}, (
            f"Corrupt or near-empty duration ({dur:.4f}s)"
        )
    return True, {"sample_rate": sr, "channels": ch, "duration_sec": dur}, ""


def discover_native_audio_assets(root: Path) -> List[AudioAsset]:
    """Enumerate built-in procedural music beds, SFX generators, and ambiences."""
    prov_base = {
        "repository": "Short Director",
        "origin": "native_procedural_dsp",
        "statement": "Procedurally synthesized at runtime via NumPy/SciPy DSP (not third-party audio).",
        "project_root": str(root.resolve()),
    }

    music_defs = [
        ("nat_bed_curious", "curious_marimba_pluck", "curious", 0.42, ["curious", "explainer", "science", "setup", "default"]),
        ("nat_bed_wonder", "wonder_shimmer_pad", "wonder", 0.46, ["wonder", "discovery", "route", "map", "space"]),
        ("nat_bed_tension", "tension_pulse_strings", "tension", 0.72, ["tension", "danger", "drama", "conflict", "turn", "escalation"]),
        ("nat_bed_mystery", "mystery_sparse_bell", "mystery", 0.38, ["mystery", "question", "hook", "minimal"]),
        ("nat_bed_triumph", "triumph_brass_plucks", "triumph", 0.78, ["triumph", "payoff", "resolve", "victory", "growth"]),
        ("nat_bed_emotional", "emotional_warm_chord", "emotional", 0.50, ["emotional", "mercy", "human", "warm", "story"]),
        ("nat_bed_calm", "calm_minimal_sine", "calm", 0.24, ["calm", "minimal", "minimalistic-graphics", "meditation", "habit"]),
    ]

    assets: List[AudioAsset] = []
    for aid, gen, mood, inten, tags in music_defs:
        assets.append(
            AudioAsset(
                asset_id=aid,
                source="native_procedural",
                asset_type="music",
                file_path=None,
                generator_name=gen,
                duration_sec=0.0,  # synthesized dynamically to exact segment length
                sample_rate=48000,
                channels=2,
                tags=tags,
                mood=mood,
                intensity=inten,
                provenance=dict(prov_base),
                license_type="procedural",
                author="Short Director DSP",
                title=gen.replace("_", " ").title(),
                commercial_use_allowed=True,
                attribution_required=False,
            )
        )

    sfx_defs = [
        ("nat_sfx_whoosh_pan", "whoosh_pan", 0.28, "transition", ["whip", "transition", "whoosh", "swipe", "motion"]),
        ("nat_sfx_sweep", "transition_sweep", 0.24, "transition", ["iris_mask", "match_zoom", "sweep", "zoom"]),
        ("nat_sfx_soft_impact", "soft_impact", 0.26, "impact", ["hook_reveal", "soft_impact", "appear", "pop"]),
        ("nat_sfx_heavy_thud", "heavy_thud", 0.36, "impact", ["heavy_thud", "dip_to_black", "slam", "object_thud", "drop"]),
        ("nat_sfx_sand_thud", "sand_thud", 0.40, "foley", ["body_sand_thud", "sand", "fall", "knockdown", "shield_drop"]),
        ("nat_sfx_blade_ring", "sword_blade_ring", 0.72, "foley", ["sword", "blade_halt_ring", "steel", "gladius"]),
        ("nat_sfx_sword_draw", "sword_draw_scrape", 0.34, "foley", ["sword_draw_glint", "metal_scrape", "blade"]),
        ("nat_sfx_shield_clang", "metal_shield_clang", 0.45, "foley", ["shield", "armor", "clang", "wood_hit", "sword_wood_hit"]),
        ("nat_sfx_coin_cascade", "coin_clink_cascade", 0.58, "foley", ["coin", "coins", "coin_slam_cascade", "denarii", "bill", "50x"]),
        ("nat_sfx_clock_tick", "clock_tick", 0.06, "foley", ["clock", "tick", "timer", "cutaway", "scan_tick", "mechanical_click"]),
        ("nat_sfx_spark_chime", "brain_spark_chime", 0.65, "emphasis", ["chime", "insight", "payoff", "sparkle", "mercy", "pin_drop", "ui_pin_drop"]),
        ("nat_sfx_ui_pop", "ui_pop_subtle", 0.12, "ui", ["ui", "pop", "card", "callout", "hop_boing"]),
        ("nat_sfx_riser", "riser_tension", 0.75, "tension", ["riser", "buildup", "anticipation"]),
        ("nat_sfx_step_gravel", "step_gravel", 0.22, "foley", ["step", "walk", "footstep", "pendulum"]),
        ("nat_sfx_glass_tap", "glass_tap_ui", 0.09, "ui", ["tap", "screen", "phone", "send", "button"]),
        ("nat_sfx_electric_crackle", "electric_spark_pulse", 0.28, "foley", ["chip", "circuit", "tower", "turbine", "rf", "electric"]),
        ("nat_sfx_subsea_bubble", "subsea_bubble_hum", 0.38, "foley", ["ocean", "subsea", "water", "fiber", "photon"]),
        ("nat_sfx_cosmic_swell", "cosmic_swell", 0.78, "reveal", ["cosmic", "star", "universe", "nebula", "scale"]),
        ("nat_sfx_elevator_btn", "elevator_button_click", 0.11, "ui", ["elevator", "button", "press", "call"]),
        ("nat_sfx_relay_click", "relay_cabinet_click", 0.14, "foley", ["relay", "cabinet", "contactor", "controller"]),
        ("nat_sfx_motor_hum", "motor_drive_hum", 0.52, "foley", ["motor", "traction", "sheave", "drive"]),
        ("nat_sfx_cable_whir", "sheave_cable_whir", 0.44, "foley", ["cable", "counterweight", "shaft", "pulley"]),
        ("nat_sfx_door_slide", "door_slide_open", 0.42, "foley", ["door", "doors", "slide", "landing"]),
        ("nat_sfx_arrival_chime", "elevator_arrival_chime", 0.62, "emphasis", ["arrival", "ding", "chime", "elevator"]),
        ("nat_sfx_ui_pop_soft", "ui_pop_soft", 0.08, "ui", ["ui_pop_soft", "verified_counter", "callout_pop"]),
        ("nat_sfx_marker_ring", "marker_ring_draw", 0.16, "ui", ["marker_ring_draw", "focus_ring", "spotlight", "callout_ring"]),
        ("nat_sfx_arrow_swish", "arrow_swish", 0.15, "ui", ["arrow_swish", "tracked_arrow", "leader_label", "callout_arrow"]),
        ("nat_sfx_reveal_soft", "reveal_soft", 0.34, "reveal", ["reveal_soft", "exploded_panes", "layer_reveal", "callout_reveal"]),
        ("nat_sfx_low_sting", "low_sting", 0.32, "impact", ["low_sting", "twist_alert", "outer_failure", "contrast_sting"]),
        ("nat_sfx_airflow_hiss", "airflow_hiss", 0.48, "foley", ["airflow_hiss", "bleed_hole", "pressure_vent", "moisture_vent"]),
        ("nat_sfx_tank_groan", "tank_structural_groan", 0.58, "foley", ["tank_structural_groan", "tank_groan", "seam_leak", "steel_strain"]),
        ("nat_sfx_rivet_ping", "rivet_tension_ping", 0.16, "foley", ["rivet_tension_ping", "rivet", "shear_snap"]),
        ("nat_sfx_tank_rupture", "tank_rupture_impact", 0.46, "impact", ["tank_rupture_impact", "tank_rupture", "wall_burst"]),
        ("nat_sfx_molasses_rush", "molasses_wave_rush", 0.72, "foley", ["molasses_wave_rush", "molasses", "viscous_wave"]),
        ("nat_sfx_street_impact", "street_obstacle_impact", 0.34, "impact", ["street_obstacle_impact", "building_smash", "wagon_crash"]),
        ("nat_sfx_footsteps_retreat", "footsteps_retreat", 0.52, "foley", ["footsteps_retreat", "cobblestone_run", "retreat"]),
        ("nat_sfx_rail_creak", "rail_creak", 0.44, "foley", ["rail_creak", "elevated_rail", "trestle_bend"]),
        ("nat_sfx_reveal_pop", "reveal_pop", 0.08, "ui", ["reveal_pop", "callout_reveal"]),
        ("nat_sfx_focus_ring_draw", "tracked_focus_ring_draw", 0.16, "ui", ["tracked_focus_ring_draw"]),
        ("nat_sfx_counter_soft", "counter_emphasis_soft", 0.32, "ui", ["counter_emphasis_soft"]),
    ]

    for aid, gen, dur, mood, tags in sfx_defs:
        assets.append(
            AudioAsset(
                asset_id=aid,
                source="native_procedural",
                asset_type="sfx",
                file_path=None,
                generator_name=gen,
                duration_sec=dur,
                sample_rate=48000,
                channels=2,
                tags=tags,
                mood=mood,
                intensity=0.6,
                provenance=dict(prov_base),
                license_type="procedural",
                author="Short Director DSP",
                title=gen.replace("_", " ").title(),
                commercial_use_allowed=True,
                attribution_required=False,
            )
        )

    amb_defs = [
        ("nat_amb_studio", "studio_room_ambience", "neutral", ["studio", "room", "indoors"]),
        ("nat_amb_arena", "arena_wind_ambience", "dramatic", ["arena", "outdoor", "wind", "rome", "city"]),
        ("nat_amb_boston_street", "period_street_ambience", "neutral", ["boston", "1919", "north end", "cobblestone", "historical"]),
        ("nat_amb_boston_rescue", "rescue_ambience", "calm", ["rescue", "aftermath", "evening", "quiet"]),
    ]
    for aid, gen, mood, tags in amb_defs:
        assets.append(
            AudioAsset(
                asset_id=aid,
                source="native_procedural",
                asset_type="ambience",
                file_path=None,
                generator_name=gen,
                duration_sec=0.0,
                sample_rate=48000,
                channels=2,
                tags=tags,
                mood=mood,
                intensity=0.25,
                provenance=dict(prov_base),
                license_type="procedural",
                author="Short Director DSP",
                title=gen.replace("_", " ").title(),
                commercial_use_allowed=True,
                attribution_required=False,
            )
        )
    return assets


def _load_qa_license_index(licenses_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Index QA `audio/licenses/*.json` safely by stem, filename, rel_path, and asset_id."""
    index: Dict[str, Dict[str, Any]] = {}
    if not licenses_dir.exists() or not licenses_dir.is_dir():
        return index

    def _register(entry: Dict[str, Any], default_key: str) -> None:
        if not isinstance(entry, dict):
            return
        keys = set()
        for kfield in ("asset_id", "id", "filename", "file", "file_name", "path", "rel_path", "stem", "name"):
            val = entry.get(kfield)
            if isinstance(val, str) and val.strip():
                v = val.strip()
                keys.add(v)
                keys.add(Path(v).name)
                keys.add(Path(v).stem)
        if not keys:
            keys.add(default_key)
        for k in keys:
            index[k] = entry

    for jp in sorted(licenses_dir.glob("*.json")):
        try:
            payload = json.loads(jp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, list):
            for idx, item in enumerate(payload):
                _register(item, f"{jp.stem}_{idx}")
        elif isinstance(payload, dict):
            if "assets" in payload and isinstance(payload["assets"], list):
                for idx, item in enumerate(payload["assets"]):
                    _register(item, f"{jp.stem}_{idx}")
            elif any(k in payload for k in ("license", "license_type", "sha256", "content_sha256", "filename", "author")):
                _register(payload, jp.stem)
            else:
                for sub_k, sub_v in payload.items():
                    if isinstance(sub_v, dict):
                        _register({**sub_v, "stem": sub_k}, str(sub_k))
    return index


def _parse_external_audio_md(md_path: Path) -> Dict[str, Dict[str, str]]:
    """Extract attribution metadata blocks from QA `audio/EXTERNAL-AUDIO.md` read-only."""
    info: Dict[str, Dict[str, str]] = {}
    if not md_path.exists():
        return info
    try:
        txt = md_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return info
    if "dark fog" in txt.lower() or "external_dark_fog" in txt.lower():
        m_credit = re.search(r'("Dark Fog".*?4\.0[^\n]*)', txt, flags=re.IGNORECASE)
        info["external_dark_fog"] = {
            "license_type": "cc-by-4.0",
            "author": "Kevin MacLeod",
            "title": "Dark Fog",
            "source_url": "https://incompetech.com",
            "license_url": "http://creativecommons.org/licenses/by/4.0/",
            "attribution_text": (
                m_credit.group(1).strip()
                if m_credit
                else '"Dark Fog" Kevin MacLeod (incompetech.com) Licensed under Creative Commons: By Attribution 4.0 License http://creativecommons.org/licenses/by/4.0/'
            ),
        }
    return info


def discover_qa_audio_assets(qa_root: Path) -> List[AudioAsset]:
    """Read-only discovery of QA-Unified-Video-Studio audio beds, SFX, and license JSONs."""
    qa_root = qa_root.resolve()
    audio_dir = qa_root / "audio"
    if not audio_dir.exists() or not audio_dir.is_dir():
        return []

    lic_index = _load_qa_license_index(audio_dir / "licenses")
    ext_md_notes = _parse_external_audio_md(audio_dir / "EXTERNAL-AUDIO.md")

    discovered: List[AudioAsset] = []
    scan_specs = [
        ("qa_music", "music", audio_dir / "music"),
        ("qa_sfx", "sfx", audio_dir / "sfx"),
        ("qa_real_sfx", "sfx", audio_dir / "real_sfx"),
    ]

    for source_kind, asset_type, folder in scan_specs:
        if not folder.exists() or not folder.is_dir():
            continue
        for entry_name in sorted(os.listdir(folder)):
            if not entry_name.lower().endswith(".wav"):
                continue
            wav_path = folder / entry_name
            stem = wav_path.stem

            meta = (
                lic_index.get(f"{folder.name}/{entry_name}")
                or lic_index.get(entry_name)
                or lic_index.get(stem)
                or {}
            )

            # Determine honest license baseline: external_* or real_sfx MUST have explicit metadata
            is_external = source_kind == "qa_real_sfx" or stem.startswith("external_")
            default_lic = "unknown" if is_external else str(meta.get("license_type") or meta.get("license") or "procedural").lower()
            lic_type = str(meta.get("license_type") or meta.get("license") or default_lic).strip().lower()

            author = str(meta.get("author") or meta.get("creator") or "")
            title = str(meta.get("title") or stem.replace("_", " ").title())
            src_url = str(meta.get("source_url") or meta.get("url") or "")
            lic_url = str(meta.get("license_url") or "")
            attr_text = str(meta.get("attribution_text") or meta.get("credit") or "")
            attr_req = bool(meta.get("attribution_required", ("cc-by" in lic_type or lic_type.startswith("cc_by"))))
            comm_ok = meta.get("commercial_use_allowed")
            if comm_ok is None:
                comm_ok = lic_type not in ("unknown", "", "personal_only", "nc", "non-commercial")

            # Check known EXTERNAL-AUDIO.md attribution notice ONLY if license file also agrees on cc-by or filename matches documented CC-BY
            if stem in ext_md_notes and lic_type in ("cc-by", "cc-by-4.0", "cc-by-3.0"):
                md_entry = ext_md_notes[stem]
                author = author or md_entry["author"]
                title = title or md_entry["title"]
                src_url = src_url or md_entry["source_url"]
                lic_url = lic_url or md_entry["license_url"]
                attr_text = attr_text or md_entry["attribution_text"]
                attr_req = True

            if attr_req and not attr_text and author:
                attr_text = f'"{title}" by {author} ({src_url or "QA Library"}) — {lic_type.upper()} {lic_url}'.strip()

            expected_sha = str(meta.get("sha256") or meta.get("content_sha256") or "").strip().lower()
            tags_raw = meta.get("tags") or re.findall(r"[a-z0-9]+", stem.lower())
            tags = [str(t).lower() for t in tags_raw] if isinstance(tags_raw, list) else re.findall(r"[a-z0-9]+", str(tags_raw).lower())
            mood = str(meta.get("mood") or (tags[0] if tags else "neutral")).lower()
            intensity = float(meta.get("intensity", 0.55))

            try:
                file_sz = wav_path.stat().st_size if wav_path.exists() else 0
            except Exception:
                file_sz = 0

            discovered.append(
                AudioAsset(
                    asset_id=f"{source_kind}_{stem}",
                    source=source_kind,
                    asset_type=asset_type,
                    file_path=str(wav_path),
                    generator_name=None,
                    duration_sec=float(meta.get("duration_sec") or 0.0),
                    sample_rate=int(meta.get("sample_rate") or 0),
                    channels=int(meta.get("channels") or 0),
                    tags=sorted(set(tags)),
                    mood=mood,
                    intensity=intensity,
                    provenance={
                        "qa_root": str(qa_root),
                        "rel_path": f"audio/{folder.name}/{entry_name}",
                        "file_bytes": file_sz,
                        "license_record_found": bool(meta),
                    },
                    license_type=lic_type,
                    author=author,
                    title=title,
                    source_url=src_url,
                    license_url=lic_url,
                    commercial_use_allowed=bool(comm_ok),
                    attribution_required=attr_req,
                    attribution_text=attr_text,
                    content_sha256="",
                    expected_sha256=expected_sha,
                )
            )
    return discovered


def discover_user_music_asset(
    music_file: Path,
    rights_confirmed: bool = False,
) -> AudioAsset:
    """Create candidate AudioAsset entry for `--music-mode file --music-file PATH`."""
    p = music_file
    sidecar_meta: Dict[str, Any] = {}
    for cand in (p.with_suffix(".license.json"), p.parent / f"{p.stem}.license.json"):
        if cand.exists():
            try:
                sidecar_meta = json.loads(cand.read_text(encoding="utf-8"))
                break
            except Exception:
                sidecar_meta = {}

    lic = str(sidecar_meta.get("license_type") or sidecar_meta.get("license") or ("user_licensed" if rights_confirmed else "unknown")).lower()
    comm = sidecar_meta.get("commercial_use_allowed")
    if comm is None:
        comm = bool(rights_confirmed or (lic in ("cc0", "cc-by", "cc-by-4.0", "mit", "user_licensed")))
    author = str(sidecar_meta.get("author") or ("User Provided" if rights_confirmed else ""))
    attr_req = bool(sidecar_meta.get("attribution_required", "cc-by" in lic))
    attr_text = str(sidecar_meta.get("attribution_text") or "")

    return AudioAsset(
        asset_id=f"user_music_{p.stem}",
        source="user_file",
        asset_type="music",
        file_path=str(p),
        duration_sec=0.0,
        sample_rate=0,
        channels=0,
        tags=["user", "custom"],
        mood=str(sidecar_meta.get("mood") or "neutral"),
        intensity=0.55,
        provenance={"user_supplied": True, "rights_confirmed_flag": rights_confirmed, "has_sidecar_license": bool(sidecar_meta)},
        license_type=lic,
        author=author,
        title=str(sidecar_meta.get("title") or p.stem),
        source_url=str(sidecar_meta.get("source_url") or ""),
        license_url=str(sidecar_meta.get("license_url") or ""),
        commercial_use_allowed=bool(comm),
        attribution_required=attr_req,
        attribution_text=attr_text,
        expected_sha256=str(sidecar_meta.get("sha256") or "").lower(),
    )


def validate_audio_asset(
    asset: AudioAsset,
    policy: LicensePolicy,
    allowed_roots: Optional[List[Path]] = None,
) -> ValidationResult:
    """Strictly verify safety, provenance, SHA-256, license rights, and audio decodability."""
    # Native procedural assets require no disk file
    if asset.source == "native_procedural":
        if not asset.generator_name:
            return ValidationResult(False, asset.asset_id, "REJECTED", "Native procedural asset lacks generator_name")
        return ValidationResult(True, asset.asset_id, "VERIFIED", "Verified native DSP procedural generator")

    if not asset.file_path:
        return ValidationResult(False, asset.asset_id, "REJECTED", "File-backed audio asset missing file_path")

    raw_path = Path(asset.file_path)
    roots_ok, root_reason = _is_path_within_roots(raw_path, allowed_roots)
    if not roots_ok:
        return ValidationResult(False, asset.asset_id, "REJECTED", root_reason)

    resolved_path = raw_path.resolve(strict=False)
    if not resolved_path.exists() or not resolved_path.is_file():
        return ValidationResult(False, asset.asset_id, "REJECTED", f"Audio file does not exist: {raw_path}")

    if resolved_path.stat().st_size < 44:
        return ValidationResult(False, asset.asset_id, "REJECTED", f"Truncated or zero-length audio file: {resolved_path.name}")

    # License policy checks BEFORE trusting content
    lic_norm = (asset.license_type or "unknown").strip().lower()
    if policy.require_explicit_license_for_external and lic_norm in ("", "unknown", "none"):
        return ValidationResult(False, asset.asset_id, "REJECTED", f"Missing verified license metadata for external audio '{resolved_path.name}'")

    if policy.allowed_licenses and lic_norm not in policy.allowed_licenses:
        return ValidationResult(False, asset.asset_id, "REJECTED", f"Disallowed license type '{lic_norm}' for '{resolved_path.name}'")

    if policy.allow_commercial_only and not asset.commercial_use_allowed:
        return ValidationResult(False, asset.asset_id, "REJECTED", f"Commercial use prohibited by asset license: {resolved_path.name}")

    if asset.attribution_required and not (asset.attribution_text.strip() or asset.author.strip()):
        return ValidationResult(False, asset.asset_id, "REJECTED", f"Attribution-required asset '{resolved_path.name}' missing author/credit text")

    # Full SHA-256 verification
    computed_sha = compute_file_sha256(resolved_path)
    asset.content_sha256 = computed_sha
    if asset.expected_sha256 and computed_sha.lower() != asset.expected_sha256.lower():
        return ValidationResult(
            False,
            asset.asset_id,
            "REJECTED",
            f"SHA-256 mismatch for '{resolved_path.name}': expected {asset.expected_sha256[:12]}..., got {computed_sha[:12]}...",
            computed_sha256=computed_sha,
        )

    # FFprobe decodeability + sample rate / channel check
    ok_probe, probe_meta, probe_err = _probe_audio_stream_ffprobe(resolved_path)
    if not ok_probe:
        return ValidationResult(False, asset.asset_id, "REJECTED", probe_err, computed_sha256=computed_sha)

    # Sample-level readability & finiteness verification via soundfile (bounded read check)
    try:
        with sf.SoundFile(str(resolved_path)) as sfh:
            total_frames = len(sfh)
            if total_frames <= 0:
                return ValidationResult(False, asset.asset_id, "REJECTED", f"Zero PCM frames in '{resolved_path.name}'", computed_sha256=computed_sha)
            sample_blk = sfh.read(frames=min(total_frames, 48000 * 4), dtype="float32", always_2d=True)
            if not np.all(np.isfinite(sample_blk)):
                return ValidationResult(False, asset.asset_id, "REJECTED", f"Non-finite (NaN/Inf) PCM samples in '{resolved_path.name}'", computed_sha256=computed_sha)
    except Exception as exc:
        return ValidationResult(False, asset.asset_id, "REJECTED", f"SoundFile decode error for '{resolved_path.name}': {exc}", computed_sha256=computed_sha)

    asset.sample_rate = int(probe_meta["sample_rate"])
    asset.channels = int(probe_meta["channels"])
    asset.duration_sec = round(float(probe_meta["duration_sec"]), 3)
    needs_resample = (asset.sample_rate != 48000) or (asset.channels != 2)

    return ValidationResult(
        ok=True,
        asset_id=asset.asset_id,
        status="VERIFIED",
        reason="Verified file integrity, SHA-256, license rights, and audio decodability",
        needs_resample=needs_resample,
        computed_sha256=computed_sha,
        attribution_text=asset.attribution_text,
    )


def resolve_audio_asset(
    intent: str,
    mood: str,
    catalog: List[AudioAsset],
    policy: LicensePolicy,
    seed: int = 42,
    used_counts: Optional[Dict[str, int]] = None,
    prefer_qa: bool = True,
    asset_type: Optional[str] = None,
    min_duration: float = 0.0,
    allowed_roots: Optional[List[Path]] = None,
    validations_cache: Optional[Dict[str, ValidationResult]] = None,
) -> ResolutionResult:
    """Rank candidates deterministically and return ONLY a verified playable AudioAsset."""
    intent_low = (intent or "").lower()
    mood_low = (mood or "").lower()
    intent_tokens = set(re.findall(r"[a-z0-9]+", intent_low))
    counts = used_counts if used_counts is not None else {}

    scored: List[Tuple[float, AudioAsset]] = []
    for item in catalog:
        if asset_type and item.asset_type != asset_type:
            continue
        score = 0.0
        tags = {t.lower() for t in item.tags}
        if intent_low in tags or (item.generator_name and intent_low == item.generator_name):
            score += 6.0
        overlap = len(intent_tokens & tags)
        score += overlap * 2.5
        if mood_low and item.mood.lower() == mood_low:
            score += 3.5
        elif mood_low and mood_low in tags:
            score += 2.0
        if prefer_qa and item.source in ("qa_music", "qa_real_sfx", "qa_sfx"):
            score += 1.5
        if min_duration > 0.0 and item.file_path and item.duration_sec > 0.0 and item.duration_sec < min_duration:
            score -= 0.8
        # Repetition penalty so consecutive events avoid monotonous identical SFX when alternatives exist
        rep = counts.get(item.asset_id, 0)
        score -= rep * 1.15
        # Deterministic seed tie-break
        tie = (int(hashlib.sha256(f"{seed}:{intent}:{item.asset_id}".encode()).hexdigest()[:8], 16) % 1000) * 1e-6
        scored.append((score + tie, item))

    scored.sort(key=lambda pair: (-pair[0], pair[1].asset_id))

    rejected: List[Dict[str, str]] = []
    saw_qa_rejection = False
    for sc, candidate in scored:
        v = validations_cache.get(candidate.asset_id) if validations_cache else None
        if v is None:
            v = validate_audio_asset(candidate, policy, allowed_roots=allowed_roots)
            if validations_cache is not None:
                validations_cache[candidate.asset_id] = v
        if v.ok:
            used_back = bool(saw_qa_rejection and candidate.source == "native_procedural")
            reason = (
                f"Fell back to native procedural '{candidate.asset_id}' after QA asset validation rejection(s)"
                if used_back
                else f"Resolved '{candidate.asset_id}' ({candidate.source}) for intent='{intent}', mood='{mood}'"
            )
            return ResolutionResult(
                ok=True,
                asset=candidate,
                validation=v,
                score=sc,
                fallback_used=used_back,
                reason=reason,
                rejected_candidates=rejected,
            )
        if candidate.source != "native_procedural":
            saw_qa_rejection = True
        rejected.append({"asset_id": candidate.asset_id, "reason": v.reason})

    return ResolutionResult(
        ok=False,
        asset=None,
        validation=None,
        score=0.0,
        fallback_used=False,
        reason=f"No verified audio asset available for intent='{intent}', mood='{mood}', type='{asset_type}'",
        rejected_candidates=rejected,
    )


def write_audio_asset_manifest(
    out_path: Path,
    catalog: List[AudioAsset],
    validations: Dict[str, ValidationResult],
    used_asset_roles: Dict[str, List[str]],
    qa_status: str,
    qa_root: Optional[Path] = None,
    fallback_notes: Optional[List[str]] = None,
) -> Path:
    """Write `audio/audio_asset_manifest.json` with hashes, license status, provenance, and rejections."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []
    rejected_count = 0
    verified_count = 0
    for asset in catalog:
        v = validations.get(asset.asset_id)
        uses = used_asset_roles.get(asset.asset_id, [])
        if not uses and asset.source == "native_procedural":
            # Keep catalog concise: always log external assets + any used native assets
            continue
        status = v.status if v else "UNCHECKED"
        if status == "REJECTED":
            rejected_count += 1
        elif status == "VERIFIED":
            verified_count += 1
        records.append({
            "asset_id": asset.asset_id,
            "origin": asset.source,
            "procedural": asset.source == "native_procedural",
            "asset_type": asset.asset_type,
            "local_source_path": asset.file_path or asset.generator_name,
            "sha256": (v.computed_sha256 if v and v.computed_sha256 else asset.content_sha256) or None,
            "sample_rate": asset.sample_rate,
            "channels": asset.channels,
            "duration_sec": asset.duration_sec,
            "license_type": asset.license_type,
            "commercial_use_allowed": asset.commercial_use_allowed,
            "attribution_required": asset.attribution_required,
            "author": asset.author,
            "title": asset.title,
            "source_url": asset.source_url,
            "mandatory_credit": asset.attribution_text if asset.attribution_required else "",
            "validation_status": status,
            "validation_reason": v.reason if v else "Not evaluated",
            "selected_uses": uses,
        })

    manifest = {
        "schema_version": "sd-audio-assets-1",
        "qa_audio_root_status": qa_status,
        "qa_audio_root": str(qa_root.resolve()) if qa_root else None,
        "verified_evaluated_count": verified_count,
        "rejected_assets_count": rejected_count,
        "fallback_notes": fallback_notes or [],
        "assets": records,
    }
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def write_credits_file(
    out_path: Path,
    used_assets: List[AudioAsset],
    validations: Dict[str, ValidationResult],
) -> Path:
    """Write `audio/credits_audio.txt` emitting required CC BY attributions & provenance summaries."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    cc_by_lines: List[str] = []
    cc0_lines: List[str] = []
    proc_lines: List[str] = []
    other_lines: List[str] = []

    for a in used_assets:
        if a.asset_id in seen:
            continue
        seen.add(a.asset_id)
        v = validations.get(a.asset_id)
        if v and not v.ok:
            continue
        lic = a.license_type.lower()
        if a.source == "native_procedural":
            proc_lines.append(f"- {a.title} [{a.asset_id}]: Procedurally synthesized via Short Director DSP (NumPy/SciPy).")
        elif "cc-by" in lic or a.attribution_required:
            credit = a.attribution_text.strip() or f'"{a.title}" by {a.author} ({a.source_url}) — {a.license_type.upper()} {a.license_url}'
            cc_by_lines.append(f"- {credit}")
        elif lic == "cc0":
            cc0_lines.append(f"- {a.title} [{a.asset_id}] ({a.file_path}): CC0 Public Domain Dedication ({a.source_url or a.author}).")
        else:
            other_lines.append(f"- {a.title} [{a.asset_id}]: License={a.license_type} ({a.file_path})")

    lines = ["# Audio Provenance & Attribution Credits", ""]
    if cc_by_lines:
        lines.extend(["## Mandatory Third-Party Attribution (CC BY)", *cc_by_lines, ""])
    if cc0_lines:
        lines.extend(["## CC0 Assets Used", *cc0_lines, ""])
    if other_lines:
        lines.extend(["## Licensed / User-Supplied Audio", *other_lines, ""])
    if proc_lines:
        lines.extend(["## Procedural Audio Generators (Synthesized at Runtime)", *proc_lines, ""])
    if not (cc_by_lines or cc0_lines or other_lines or proc_lines):
        lines.append("No active external or procedural audio stems rendered (audio intentionally silent/disabled).")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path
