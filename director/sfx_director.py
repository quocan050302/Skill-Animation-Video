"""SFX Director: Visual-Grounded Foley Selection, Asset Resolution & 48 kHz Spatial Renderer.

Supports `--sfx-mode auto|procedural|qa-library|off`, `--sfx-density sparse|balanced|detailed`,
and `--sfx-gain-db`. Only uses verified licensed WAV assets or native procedural DSP.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf
from scipy import signal

from .audio_catalog import AudioAsset, LicensePolicy, ValidationResult, resolve_audio_asset
from .audio_dsp import (
    SR,
    _airflow_hiss,
    _arrow_swish,
    _blade_ring,
    _chime,
    _coin_cascade,
    _cosmic_swell,
    _door_slide_open,
    _electric_crackle,
    _elevator_arrival_chime,
    _elevator_button_click,
    _glass_tap,
    _low_sting,
    _lp,
    _marker_ring_draw,
    _mechanical_click,
    _motor_drive_hum,
    _pin_drop,
    _place,
    _pop,
    _relay_cabinet_click,
    _reveal_soft,
    _riser,
    _sand_thud,
    _sheave_cable_whir,
    _shield_clang,
    _step_gravel,
    _subsea_bubble,
    _sword_draw,
    _thud,
    _tick,
    _ui_pop_soft,
    _whoosh,
)


def _mix_mono(*clips: np.ndarray) -> np.ndarray:
    n = max((len(c) for c in clips), default=0)
    out = np.zeros(n, dtype=np.float64)
    for c in clips:
        out[: len(c)] += c
    return out


def select_procedural_sfx(
    generator_name: str,
    event: Dict[str, Any],
    rng: np.random.Generator,
    sr: int = SR,
) -> np.ndarray:
    """Synthesize a bespoke DSP sound effect cleanly without reusing stale static cues."""
    gen = (generator_name or "soft_impact").lower()
    if gen == "whoosh_pan":
        return _whoosh(rng, dur=0.28, up=float(event.get("pan", 0.0)) >= 0.0)
    if gen == "transition_sweep":
        return _whoosh(rng, dur=0.24, up=True) * 0.85
    if gen == "soft_impact":
        return _mix_mono(_pop(480.0) * 0.45, _thud(rng, 85.0, 0.22) * 0.55)
    if gen == "heavy_thud":
        return _thud(rng, 64.0, 0.36)
    if gen == "sand_thud":
        return _sand_thud(rng, 0.40)
    if gen == "sword_blade_ring":
        return _blade_ring(1040.0, 0.72)
    if gen == "sword_draw_scrape":
        return _sword_draw(rng, 0.34)
    if gen == "metal_shield_clang":
        return _shield_clang(rng, 0.45)
    if gen == "coin_clink_cascade":
        return _coin_cascade(rng, 0.56)
    if gen == "clock_tick":
        return _tick(rng)
    if gen == "mechanical_click":
        return _mechanical_click(rng)
    if gen == "brain_spark_chime":
        return _chime(1480.0, 0.65)
    if gen == "ui_pop_subtle":
        return _pop(540.0) * 0.65
    if gen == "ui_pin_drop":
        return _pin_drop()
    if gen == "riser_tension":
        return _riser(rng, dur=0.68)
    if gen == "step_gravel":
        return _step_gravel(rng)
    if gen == "glass_tap_ui":
        return _glass_tap(rng)
    if gen == "electric_spark_pulse":
        return _electric_crackle(rng, 0.28)
    if gen == "subsea_bubble_hum":
        return _subsea_bubble(rng, 0.38)
    if gen == "cosmic_swell":
        return _cosmic_swell(rng, 0.78)
    if gen == "elevator_button_click":
        return _elevator_button_click(rng)
    if gen == "relay_cabinet_click":
        return _relay_cabinet_click(rng)
    if gen == "motor_drive_hum":
        return _motor_drive_hum(rng, 0.52)
    if gen == "sheave_cable_whir":
        return _sheave_cable_whir(rng, 0.44)
    if gen == "door_slide_open":
        return _door_slide_open(rng, 0.42)
    if gen == "elevator_arrival_chime":
        return _elevator_arrival_chime(880.0, 0.62)
    if gen == "ui_pop_soft":
        return _ui_pop_soft(rng, 520.0)
    if gen == "marker_ring_draw":
        return _marker_ring_draw(rng, 0.16)
    if gen == "arrow_swish":
        return _arrow_swish(rng, 0.15)
    if gen == "reveal_soft":
        return _reveal_soft(rng, 0.34)
    if gen == "low_sting":
        return _low_sting(rng, 0.32)
    if gen == "airflow_hiss":
        return _airflow_hiss(rng, 0.48)
    return _pop(520.0) * 0.6


def _load_sfx_wav(file_path: Path, sr: int = SR, max_dur_sec: float = 4.0) -> np.ndarray:
    with sf.SoundFile(str(file_path)) as sfh:
        in_sr = int(sfh.samplerate)
        max_frames = min(len(sfh), int(math.ceil(max_dur_sec * in_sr)))
        raw = sfh.read(frames=max(1, max_frames), dtype="float64", always_2d=True)

    if raw.shape[1] == 1:
        mono_or_stereo = raw[:, 0]
    else:
        mono_or_stereo = raw[:, :2]

    if in_sr != sr:
        g = math.gcd(in_sr, sr)
        if mono_or_stereo.ndim == 2:
            mono_or_stereo = np.stack([
                signal.resample_poly(mono_or_stereo[:, c], sr // g, in_sr // g)
                for c in range(2)
            ], axis=1)
        else:
            mono_or_stereo = signal.resample_poly(mono_or_stereo, sr // g, in_sr // g)

    # Normalize peak conservatively to 0.75 before explicit cue gain_db scaling
    pk = float(np.max(np.abs(mono_or_stereo)) + 1e-9)
    if pk > 0.0:
        mono_or_stereo = mono_or_stereo * (0.75 / pk)

    # Clean head/tail fade (3ms / 15ms) preserving transient punch
    n = mono_or_stereo.shape[0]
    head = min(int(0.002 * sr), n // 6)
    tail = min(int(0.015 * sr), n // 4)
    if head > 0:
        w_h = np.linspace(0.0, 1.0, head)
        mono_or_stereo[:head] *= w_h[:, None] if mono_or_stereo.ndim == 2 else w_h
    if tail > 0:
        w_t = np.linspace(1.0, 0.0, tail)
        mono_or_stereo[-tail:] *= w_t[:, None] if mono_or_stereo.ndim == 2 else w_t
    return mono_or_stereo


def design_sfx_cues(
    audio_plan: Dict[str, Any],
    catalog: List[AudioAsset],
    policy: LicensePolicy,
    sfx_mode: str = "auto",
    sfx_density: str = "balanced",
    sfx_gain_db: float = 0.0,
    seed: int = 42,
    allowed_roots: Optional[List[Path]] = None,
    validations_cache: Optional[Dict[str, ValidationResult]] = None,
) -> Tuple[List[Dict[str, Any]], List[str], List[AudioAsset]]:
    """Resolve verified SFX assets (or DSP generators) for every event in `audio_plan['sfx']`."""
    if sfx_mode == "off":
        return [], ["SFX disabled via --sfx-mode off."], []

    planned_events = list(audio_plan.get("sfx", []))
    notes: List[str] = []
    used_assets: List[AudioAsset] = []
    designed: List[Dict[str, Any]] = []
    used_counts: Dict[str, int] = {}
    validations = validations_cache if validations_cache is not None else {}

    qa_sfx = [a for a in catalog if a.asset_type == "sfx" and a.source in ("qa_real_sfx", "qa_sfx")]
    native_sfx = [a for a in catalog if a.asset_type == "sfx" and a.source == "native_procedural"]

    if sfx_mode == "qa-library" and not qa_sfx:
        raise RuntimeError(
            "Requested --sfx-mode qa-library, but no QA SFX files were found. "
            "Provide --qa-audio-root <path> or use --sfx-mode auto."
        )

    prefer_qa = (sfx_mode == "auto")
    if prefer_qa and not qa_sfx:
        notes.append("QA_LIBRARY_UNAVAILABLE: Using native procedural DSP SFX library.")

    for idx, ev in enumerate(planned_events):
        intent = str(ev.get("intent") or ev.get("event") or "soft_impact")
        kind = str(ev.get("kind") or "foley")
        pinned_id = ev.get("asset_id") if ev.get("manual") else None

        pool = qa_sfx if sfx_mode == "qa-library" else ((qa_sfx + native_sfx) if prefer_qa else native_sfx)
        if pinned_id and pinned_id != "resolved_at_runtime":
            exact = [a for a in catalog if a.asset_id == pinned_id]
            if exact:
                pool = exact

        res = resolve_audio_asset(
            intent=intent,
            mood=kind,
            catalog=pool,
            policy=policy,
            seed=seed + idx * 13,
            used_counts=used_counts,
            prefer_qa=prefer_qa or (sfx_mode == "qa-library"),
            asset_type="sfx",
            allowed_roots=allowed_roots,
            validations_cache=validations,
        )
        if not res.ok or res.asset is None:
            if sfx_mode == "qa-library":
                raise RuntimeError(f"--sfx-mode qa-library failed to resolve verified SFX for intent='{intent}': {res.reason}")
            raise RuntimeError(f"Failed to resolve SFX for intent='{intent}': {res.reason}")

        asset = res.asset
        used_counts[asset.asset_id] = used_counts.get(asset.asset_id, 0) + 1
        used_assets.append(asset)
        if res.fallback_used:
            notes.append(f"WARN: {res.reason}")

        designed.append({
            **ev,
            "cue_index": idx,
            "asset_id": asset.asset_id,
            "source": "procedural" if asset.source == "native_procedural" else asset.source,
            "generator_name": asset.generator_name,
            "file_path": asset.file_path,
            "asset": asset,
            "effective_gain_db": round(float(ev.get("gain_db", -10.0)) + float(sfx_gain_db), 2),
        })

    return designed, notes, used_assets


def render_sfx_stem(
    audio_plan: Dict[str, Any],
    designed_cues: List[Dict[str, Any]],
    out_path: Path,
    seed: int = 42,
    sr: int = SR,
    cue_sheet_path: Optional[Path] = None,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Render frame-aligned spatial SFX cues into 48 kHz stereo `audio/sfx.wav` + `sfx_cue_sheet.json`."""
    total_dur = float(audio_plan.get("total_duration_sec", 15.0))
    n_total = max(1, int(round(total_dur * sr)))
    sfx_buf = np.zeros((n_total, 2), dtype=np.float64)
    rng = np.random.default_rng(seed + 701)

    sheet_entries: List[Dict[str, Any]] = []
    for cue in designed_cues:
        t_sec = float(cue["time_sec"])
        if t_sec < 0.0 or t_sec >= total_dur:
            continue

        asset: Optional[AudioAsset] = cue.get("asset")
        if asset and asset.file_path and asset.source != "native_procedural":
            clip = _load_sfx_wav(Path(asset.file_path), sr=sr)
        else:
            gen_name = str(cue.get("generator_name") or (asset.generator_name if asset else "") or cue.get("intent") or "soft_impact")
            clip = select_procedural_sfx(gen_name, cue, rng, sr=sr)

        # Depth attenuation & subtle distance filter only when visually indicated
        depth = str(cue.get("depth") or "mid")
        gain_db = float(cue.get("effective_gain_db", cue.get("gain_db", -10.0)))
        if depth == "far":
            if clip.ndim == 2:
                clip = np.stack([_lp(clip[:, 0], 3400.0, sr=sr), _lp(clip[:, 1], 3400.0, sr=sr)], axis=1)
            else:
                clip = _lp(clip, 3400.0, sr=sr)
            gain_db -= 3.5

        gain_lin = 10.0 ** (gain_db / 20.0)
        pan = float(cue.get("pan", 0.0))

        # Preserve sharp onset while preventing edge clicks
        _place(sfx_buf, clip, t_sec, gain=gain_lin, pan=pan, sr=sr)

        # Optional subtle room early reflection on physical impacts in `mid`/`far` space
        if depth == "far" and cue.get("kind") in ("foley", "impact"):
            _place(sfx_buf, clip * 0.22, t_sec + 0.022, gain=gain_lin * 0.35, pan=-pan * 0.5, sr=sr)

        sheet_entries.append({
            "cue_index": cue["cue_index"],
            "time_sec": round(t_sec, 3),
            "shot_relative_sec": cue.get("shot_relative_sec"),
            "shot_id": cue.get("shot_id"),
            "event": cue.get("event"),
            "intent": cue.get("intent"),
            "kind": cue.get("kind"),
            "priority": cue.get("priority", 2),
            "asset_id": cue.get("asset_id"),
            "source": cue.get("source"),
            "gain_db": round(gain_db, 2),
            "pan": round(pan, 2),
            "depth": depth,
            "manual": bool(cue.get("manual", False)),
            "evidence": cue.get("evidence"),
            "clip_duration_sec": round(clip.shape[0] / float(sr), 3),
        })

    sfx_buf = np.nan_to_num(sfx_buf, nan=0.0, posinf=0.0, neginf=0.0)
    pk = float(np.max(np.abs(sfx_buf)))
    if pk > 0.92:
        sfx_buf = sfx_buf * (0.92 / pk)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), sfx_buf.astype(np.float32), sr)

    cue_sheet = {
        "schema_version": "sd-sfx-cues-1",
        "enabled": audio_plan.get("sfx_mode", "auto") != "off",
        "mode": audio_plan.get("sfx_mode", "auto"),
        "density": audio_plan.get("sfx_density", "balanced"),
        "cues_count": len(sheet_entries),
        "cues": sheet_entries,
    }
    if cue_sheet_path is not None:
        cue_sheet_path.write_text(json.dumps(cue_sheet, ensure_ascii=False, indent=2), encoding="utf-8")

    return sfx_buf, cue_sheet
