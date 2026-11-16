"""Music Director: Adaptive Score Bed Selection, Harmonic Synthesis & Crossfade Renderer.

Supports `--music-mode auto|procedural|qa-library|file|off`, `--music-file`,
`--music-gain-db`, and `--music-intensity calm|medium|high`.
Never loads unverified or disallowed external audio; builds seamless 48 kHz stereo stems.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf
from scipy import signal

from .audio_catalog import (
    AudioAsset,
    LicensePolicy,
    ValidationResult,
    discover_user_music_asset,
    resolve_audio_asset,
    validate_audio_asset,
)
from .audio_dsp import (
    SR,
    _chime,
    _place,
    _pluck_note,
    _soft_pad_chord,
)


# Cohesive key/scale progressions (never identical fixed progressions for all scripts!)
HARMONIC_PALETTES: Dict[str, Dict[str, List[Tuple[int, List[int]]]]] = {
    "D_minor": {
        "base": [(50, [62, 65, 69]), (46, [58, 62, 65]), (53, [60, 65, 69]), (48, [60, 64, 67])],
        "tension": [(50, [62, 65, 70]), (45, [57, 61, 64]), (46, [58, 62, 65]), (45, [57, 61, 67])],
        "triumph": [(50, [62, 66, 69]), (55, [62, 67, 71]), (57, [61, 64, 69]), (50, [62, 66, 74])],
    },
    "D_dorian": {
        "base": [(50, [62, 65, 69]), (55, [62, 67, 71]), (53, [60, 65, 69]), (52, [59, 64, 67])],
        "tension": [(50, [62, 65, 69]), (48, [60, 64, 67]), (46, [58, 62, 65]), (45, [57, 61, 64])],
        "triumph": [(50, [62, 66, 69]), (55, [62, 67, 71]), (48, [60, 64, 67]), (50, [62, 66, 74])],
    },
    "E_minor": {
        "base": [(52, [64, 67, 71]), (48, [60, 64, 67]), (55, [62, 67, 71]), (50, [62, 66, 69])],
        "tension": [(52, [64, 67, 71]), (47, [59, 63, 66]), (48, [60, 64, 67]), (47, [59, 63, 69])],
        "triumph": [(52, [64, 68, 71]), (57, [64, 69, 73]), (59, [63, 66, 71]), (52, [64, 68, 76])],
    },
    "A_minor": {
        "base": [(45, [57, 60, 64]), (53, [60, 65, 69]), (48, [60, 64, 67]), (55, [59, 62, 67])],
        "tension": [(45, [57, 60, 64]), (50, [62, 65, 69]), (46, [58, 62, 65]), (52, [59, 64, 68])],
        "triumph": [(45, [57, 61, 64]), (50, [62, 66, 69]), (52, [59, 64, 68]), (45, [57, 61, 69])],
    },
    "F_lydian": {
        "base": [(53, [65, 69, 72]), (55, [67, 71, 74]), (45, [60, 64, 69]), (48, [60, 64, 67])],
        "tension": [(53, [65, 69, 72]), (50, [62, 65, 69]), (46, [58, 62, 65]), (48, [60, 64, 67])],
        "triumph": [(53, [65, 69, 72]), (58, [65, 70, 74]), (48, [60, 64, 67]), (53, [65, 69, 77])],
    },
    "G_mixolydian": {
        "base": [(55, [67, 71, 74]), (53, [65, 69, 72]), (48, [60, 64, 67]), (50, [62, 66, 69])],
        "tension": [(55, [67, 70, 74]), (53, [65, 69, 72]), (50, [62, 65, 69]), (50, [62, 66, 69])],
        "triumph": [(55, [67, 71, 74]), (48, [60, 64, 67]), (50, [62, 66, 69]), (55, [67, 71, 79])],
    },
    "C_pentatonic": {
        "base": [(48, [60, 64, 67]), (57, [64, 69, 72]), (53, [60, 65, 69]), (55, [62, 67, 71])],
        "tension": [(48, [60, 64, 67]), (57, [64, 69, 72]), (50, [62, 65, 69]), (55, [62, 67, 71])],
        "triumph": [(48, [60, 64, 67]), (53, [60, 65, 69]), (55, [62, 67, 71]), (48, [60, 64, 72])],
    },
}


def align_musical_changes(
    segments: List[Dict[str, Any]],
    bpm: int,
    duration: float,
) -> List[Dict[str, Any]]:
    """Snap non-manual transition edges gently onto musical grid without disturbing exact cuts."""
    if not segments or bpm <= 0:
        return segments
    beat_s = 60.0 / float(bpm)
    out: List[Dict[str, Any]] = []
    for idx, seg in enumerate(segments):
        sc = dict(seg)
        if idx > 0 and not sc.get("manual", False):
            # Stay tight to narrative beat boundary: allow subtle +/- 0.08s alignment at most
            raw_t = float(sc["start_sec"])
            nearest = round(raw_t / beat_s) * beat_s
            if abs(nearest - raw_t) <= 0.08 and nearest > float(out[-1]["start_sec"]) + 0.3:
                sc["start_sec"] = round(nearest, 3)
                out[-1]["end_sec"] = round(nearest, 3)
        out.append(sc)
    out[0]["start_sec"] = 0.0
    out[-1]["end_sec"] = round(duration, 3)
    return out


def select_music_beds(
    plan: Dict[str, Any],
    catalog: List[AudioAsset],
    policy: LicensePolicy,
    music_mode: str = "auto",
    music_file: Optional[Path] = None,
    music_rights_confirmed: bool = False,
    seed: int = 42,
    allowed_roots: Optional[List[Path]] = None,
    validations_cache: Optional[Dict[str, ValidationResult]] = None,
) -> Tuple[List[Dict[str, Any]], List[str], List[AudioAsset]]:
    """Resolve verified music beds for every planned segment under `--music-mode` rules."""
    music_cfg = plan.get("music") or {}
    if music_mode == "off" or not music_cfg.get("enabled", True):
        return [], ["Music disabled via --music-mode off."], []

    segments = align_musical_changes(
        list(music_cfg.get("segments", [])),
        int(music_cfg.get("bpm", 104)),
        float(plan.get("total_duration_sec", 15.0)),
    )
    notes: List[str] = []
    used_assets: List[AudioAsset] = []
    selections: List[Dict[str, Any]] = []
    validations = validations_cache if validations_cache is not None else {}

    if music_mode == "file":
        if music_file is None:
            raise ValueError("--music-mode file requires --music-file <path>.")
        user_asset = discover_user_music_asset(music_file, rights_confirmed=music_rights_confirmed)
        roots = allowed_roots or [music_file.resolve().parent]
        val = validate_audio_asset(user_asset, policy, allowed_roots=roots)
        validations[user_asset.asset_id] = val
        if not val.ok:
            raise RuntimeError(f"Music file rejected ({music_file}): {val.reason}")
        used_assets.append(user_asset)
        for seg in segments:
            selections.append({**seg, "bed_id": user_asset.asset_id, "source": "user_file", "asset": user_asset})
        return selections, [f"Verified user music file: {music_file.name}"], used_assets

    qa_beds = [a for a in catalog if a.asset_type == "music" and a.source in ("qa_music",)]
    native_beds = [a for a in catalog if a.asset_type == "music" and a.source == "native_procedural"]

    if music_mode == "qa-library":
        if not qa_beds:
            raise RuntimeError(
                "Requested --music-mode qa-library, but no QA music library beds were found. "
                "Provide --qa-audio-root <path>, set SHORT_DIRECTOR_QA_ROOT, or use --music-mode auto."
            )
        for seg in segments:
            res = resolve_audio_asset(
                intent=str(seg.get("mood", "curious")),
                mood=str(seg.get("mood", "curious")),
                catalog=qa_beds,
                policy=policy,
                seed=seed,
                prefer_qa=True,
                asset_type="music",
                allowed_roots=allowed_roots,
                validations_cache=validations,
            )
            if not res.ok or res.asset is None:
                raise RuntimeError(f"--music-mode qa-library failed to resolve verified QA bed for '{seg.get('mood')}': {res.reason}")
            used_assets.append(res.asset)
            selections.append({**seg, "bed_id": res.asset.asset_id, "source": res.asset.source, "asset": res.asset})
        return selections, notes, used_assets

    # `auto` or `procedural` mode
    prefer_qa = (music_mode == "auto")
    if prefer_qa and not qa_beds:
        notes.append("QA_LIBRARY_UNAVAILABLE: Using native procedural adaptive score beds.")

    for seg in segments:
        pool = (qa_beds + native_beds) if prefer_qa else native_beds
        # When segment mood explicitly says generated/procedural or manual bed matches native
        res = resolve_audio_asset(
            intent=str(seg.get("mood", "curious")),
            mood=str(seg.get("mood", "curious")),
            catalog=pool,
            policy=policy,
            seed=seed,
            prefer_qa=prefer_qa,
            asset_type="music",
            allowed_roots=allowed_roots,
            validations_cache=validations,
        )
        if not res.ok or res.asset is None:
            raise RuntimeError(f"Failed to resolve any verified music asset for segment {seg}: {res.reason}")
        if res.fallback_used:
            notes.append(f"WARN: {res.reason}")
        used_assets.append(res.asset)
        selections.append({
            **seg,
            "bed_id": res.asset.asset_id,
            "source": "procedural" if res.asset.source == "native_procedural" else res.asset.source,
            "asset": res.asset,
        })

    return selections, notes, used_assets


def _load_wav_segment_looped(
    file_path: Path,
    dur_sec: float,
    sr: int = SR,
    crossfade_loop_sec: float = 0.25,
) -> np.ndarray:
    """Read bounded audio frames safely, resample cleanly to 48k stereo, and loop without seam clicks."""
    n_target = max(1, int(round(dur_sec * sr)))
    with sf.SoundFile(str(file_path)) as sfh:
        in_sr = int(sfh.samplerate)
        need_in = min(len(sfh), int(math.ceil((dur_sec + crossfade_loop_sec + 1.0) * in_sr)))
        raw = sfh.read(frames=max(1, need_in), dtype="float64", always_2d=True)

    if raw.shape[1] == 1:
        raw = np.repeat(raw, 2, axis=1)
    elif raw.shape[1] > 2:
        raw = raw[:, :2]

    if in_sr != sr:
        g = math.gcd(in_sr, sr)
        raw = np.stack([
            signal.resample_poly(raw[:, ch], sr // g, in_sr // g)
            for ch in range(2)
        ], axis=1)

    if raw.shape[0] >= n_target:
        out = raw[:n_target].copy()
    else:
        # Seamless equal-power crossfade loop tiling (no hard step discontinuity at loop seam!)
        src = raw
        xf = min(int(crossfade_loop_sec * sr), src.shape[0] // 4)
        out = np.zeros((n_target, 2), dtype=np.float64)
        pos = 0
        first = True
        while pos < n_target:
            take = min(src.shape[0], n_target - pos)
            if first or xf <= 8:
                out[pos : pos + take] = src[:take]
                pos += take - (xf if pos + take < n_target and xf > 8 else 0)
                first = False
            else:
                blend = min(xf, n_target - pos, take)
                theta = np.linspace(0.0, np.pi * 0.5, blend)[:, None]
                fade_out = np.cos(theta)
                fade_in = np.sin(theta)
                out[pos : pos + blend] = out[pos : pos + blend] * fade_out + src[:blend] * fade_in
                rem = take - blend
                if rem > 0:
                    out[pos + blend : pos + blend + rem] = src[blend : blend + rem]
                step_adv = max(1, take - (xf if pos + take < n_target else 0))
                pos += step_adv

    # Gentle edge micro-fade so segment head/tail start cleanly at zero
    edge = min(int(0.015 * sr), n_target // 4)
    if edge > 0:
        out[:edge] *= np.linspace(0.0, 1.0, edge)[:, None]
        out[-edge:] *= np.linspace(1.0, 0.0, edge)[:, None]
    return out


def compose_score_segments(
    seg: Dict[str, Any],
    total_seg_dur: float,
    seed: int,
    sr: int = SR,
) -> np.ndarray:
    """Compose a distinct procedural musical bed segment in matching harmonic palette."""
    n = max(16, int(round(total_seg_dur * sr)))
    out = np.zeros((n, 2), dtype=np.float64)

    key_name = str(seg.get("musical_key") or "D_minor")
    mood = str(seg.get("mood") or "curious").lower()
    bpm = int(seg.get("bpm") or 104)
    intensity = float(seg.get("intensity") or 0.5)
    palette = HARMONIC_PALETTES.get(key_name, HARMONIC_PALETTES["D_minor"])

    if mood in ("triumph", "payoff", "resolve"):
        prog = palette["triumph"]
    elif mood in ("tension", "escalation"):
        prog = palette["tension"]
    else:
        prog = palette["base"]

    rng = np.random.default_rng(seed + int(round(float(seg.get("start_sec", 0.0)) * 100)))
    beat_s = 60.0 / float(bpm)
    note_cache: Dict[int, np.ndarray] = {}

    def get_pluck(m: int) -> np.ndarray:
        if m not in note_cache:
            note_cache[m] = _pluck_note(rng, m, 0.46)
        return note_cache[m]

    bar_t = 0.0
    bar_idx = 0
    pad_gain = 0.34 + intensity * 0.20

    while bar_t < total_seg_dur - 0.12:
        root, triad = prog[bar_idx % len(prog)]
        bar_len = min(4.0 * beat_s, total_seg_dur - bar_t)
        _place(out, _soft_pad_chord(triad, bar_len), bar_t, gain=pad_gain, pan=0.0, sr=sr)

        if mood in ("calm", "mystery"):
            bell_f = 440.0 * (2.0 ** ((triad[0] - 69) / 12.0))
            _place(out, _chime(bell_f, min(1.3, bar_len)), bar_t, gain=0.28 + 0.15 * intensity, pan=-0.12 if bar_idx % 2 == 0 else 0.12, sr=sr)
            if mood == "mystery" and bar_t + 2.0 * beat_s < total_seg_dur - 0.1:
                bell_f2 = 440.0 * (2.0 ** ((triad[-1] - 69) / 12.0))
                _place(out, _chime(bell_f2, 0.9), bar_t + 2.0 * beat_s, gain=0.22, pan=0.18, sr=sr)
        else:
            # Grounded bass root + active arpeggio scaling with narrative intensity
            _place(out, get_pluck(root), bar_t, gain=0.52 + 0.22 * intensity, pan=-0.10, sr=sr)
            if intensity >= 0.48 and bar_t + beat_s < total_seg_dur - 0.08:
                _place(out, get_pluck(root + (7 if bar_idx % 2 == 0 else 0)), bar_t + beat_s, gain=0.35 + 0.15 * intensity, pan=0.08, sr=sr)
            if bar_t + 2.0 * beat_s < total_seg_dur - 0.08:
                _place(out, get_pluck(root + 7), bar_t + 2.0 * beat_s, gain=0.45 + 0.18 * intensity, pan=0.12, sr=sr)
            for step_i, m_n in enumerate(triad):
                nt = bar_t + (step_i + 1) * beat_s
                if nt < total_seg_dur - 0.08:
                    _place(out, get_pluck(m_n), nt, gain=0.24 + 0.18 * intensity, pan=(-0.22 + 0.22 * step_i), sr=sr)

        bar_t += 4.0 * beat_s
        bar_idx += 1

    edge = min(int(0.020 * sr), n // 4)
    if edge > 0:
        out[:edge] *= np.linspace(0.0, 1.0, edge)[:, None]
        out[-edge:] *= np.linspace(1.0, 0.0, edge)[:, None]
    return out


def render_music_stem(
    plan: Dict[str, Any],
    selections: List[Dict[str, Any]],
    out_path: Path,
    music_gain_db: float = 0.0,
    seed: int = 42,
    sr: int = SR,
    cue_sheet_path: Optional[Path] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Render all selected music segments with equal-power crossfades into 48 kHz stereo `music.wav`."""
    total_dur = float(plan.get("total_duration_sec", 15.0))
    n_total = max(1, int(round(total_dur * sr)))
    master = np.zeros((n_total, 2), dtype=np.float64)

    rendered_segments: List[Dict[str, Any]] = []
    gain_mult = 10.0 ** (float(music_gain_db) / 20.0)

    for idx, sel in enumerate(selections):
        s_t = float(sel["start_sec"])
        e_t = float(sel["end_sec"])
        xf = float(sel.get("crossfade_sec", 0.0)) if idx > 0 else 0.0
        overlap_start = max(0.0, s_t - xf)
        seg_len_sec = max(0.1, e_t - overlap_start)

        asset: Optional[AudioAsset] = sel.get("asset")
        if asset and asset.file_path and asset.source != "native_procedural":
            seg_pcm = _load_wav_segment_looped(Path(asset.file_path), seg_len_sec, sr=sr)
            # Normalize external music RMS gently around -22 dBFS baseline before segment intensity scalar
            seg_rms = float(np.sqrt(np.mean(seg_pcm ** 2)) + 1e-9)
            target_rms = 0.075 * (0.7 + 0.6 * float(sel.get("intensity", 0.5)))
            seg_pcm = seg_pcm * min(4.0, target_rms / seg_rms)
        else:
            seg_pcm = compose_score_segments(sel, seg_len_sec, seed=seed + idx * 31, sr=sr)

        seg_pcm = seg_pcm * gain_mult

        i0 = int(round(overlap_start * sr))
        i_end = min(n_total, i0 + seg_pcm.shape[0])
        take = max(0, i_end - i0)
        if take <= 0:
            continue

        xf_n = min(int(round(xf * sr)), take, i0 + take) if idx > 0 and xf > 0.0 else 0
        if xf_n > 8:
            # Equal-power cosine/sin crossfade across [i0 : i0 + xf_n] (zero pop, constant loudness)
            theta = np.linspace(0.0, np.pi * 0.5, xf_n)[:, None]
            master[i0 : i0 + xf_n] = master[i0 : i0 + xf_n] * np.cos(theta) + seg_pcm[:xf_n] * np.sin(theta)
            if take > xf_n:
                master[i0 + xf_n : i_end] = seg_pcm[xf_n:take]
        else:
            master[i0:i_end] += seg_pcm[:take]

        rendered_segments.append({
            "segment_id": sel.get("segment_id", f"seg_{idx:02d}"),
            "start_sec": round(s_t, 3),
            "end_sec": round(e_t, 3),
            "crossfade_sec": round(xf, 3),
            "mood": sel.get("mood"),
            "intensity": sel.get("intensity"),
            "bed_id": sel.get("bed_id"),
            "source": sel.get("source"),
            "rms_dbfs": round(float(20.0 * np.log10(np.sqrt(np.mean(seg_pcm[:take] ** 2)) + 1e-9)), 2),
        })

    # Smooth overall tail fade cleanly
    tail_n = min(n_total // 6, int(0.32 * sr))
    if tail_n > 0 and selections:
        master[-tail_n:] *= np.linspace(1.0, 0.0, tail_n)[:, None]

    # Guard finiteness & extreme peaks cleanly
    master = np.nan_to_num(master, nan=0.0, posinf=0.0, neginf=0.0)
    pk = float(np.max(np.abs(master)))
    if pk > 0.95:
        master = master * (0.95 / pk)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), master.astype(np.float32), sr)

    cue_sheet = {
        "schema_version": "sd-music-cues-1",
        "enabled": bool(selections),
        "mode": (plan.get("music") or {}).get("mode", "auto"),
        "musical_key": (plan.get("music") or {}).get("musical_key"),
        "bpm": (plan.get("music") or {}).get("bpm"),
        "music_gain_db": round(float(music_gain_db), 2),
        "segments_count": len(rendered_segments),
        "segments": rendered_segments,
    }
    if cue_sheet_path is not None:
        cue_sheet_path.write_text(json.dumps(cue_sheet, ensure_ascii=False, indent=2), encoding="utf-8")

    return master, cue_sheet
