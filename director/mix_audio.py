"""STEP 6: Production Sound Mixing, Sidechain Ducking & Single-Pass EBU R128 Mastering.

Implements strict mix hierarchy:
  Voice Intelligibility > Grounded Action SFX > Musical Underscore / Ambience

Generates deterministic 48 kHz stereo stems:
  - `audio/voice.wav` (when voice expected, else silent track noted intentional)
  - `audio/music.wav` (ducked & raw cue telemetry)
  - `audio/sfx.wav`
  - `audio/ambience.wav`
  - `audio/master_pre.wav`
  - `audio/mix.wav` (single mastering pass to -14 LUFS / -1.5 dBTP)
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf
from scipy import signal

from .audio_catalog import (
    AudioAsset,
    LicensePolicy,
    ValidationResult,
    discover_native_audio_assets,
    discover_qa_audio_assets,
    write_audio_asset_manifest,
    write_credits_file,
)
from .audio_dsp import (
    SR,
    _bp,
    _chime,
    _hp,
    _lp,
    _place,
    _pluck_note,
    _pop,
    _soft_pad_chord,
    _sparkle_arpeggio,
    _t,
    _thud,
    _tick,
    _whoosh,
)
from .audio_narrative import build_audio_narrative_plan
from .music_director import render_music_stem, select_music_beds
from .sfx_director import design_sfx_cues, render_sfx_stem


def _pcm_sha256(arr: np.ndarray) -> str:
    arr32 = np.ascontiguousarray(arr.astype(np.float32))
    return hashlib.sha256(arr32.tobytes()).hexdigest()


def _stem_stats(arr: np.ndarray, sr: int = SR, active_thresh_db: float = -55.0) -> Dict[str, Any]:
    mono = arr.mean(axis=1) if arr.ndim == 2 else arr
    rms = float(np.sqrt(np.mean(mono ** 2)) + 1e-12)
    pk = float(np.max(np.abs(arr)) + 1e-12)
    rms_db = round(float(20.0 * np.log10(rms)), 2)
    peak_db = round(float(20.0 * np.log10(pk)), 2)
    hop = max(1, int(0.02 * sr))
    n_hops = len(mono) // hop
    if n_hops > 0:
        frames = mono[: n_hops * hop].reshape(n_hops, hop)
        frame_rms_db = 20.0 * np.log10(np.sqrt(np.mean(frames ** 2, axis=1)) + 1e-12)
        active_sec = round(float(np.sum(frame_rms_db > active_thresh_db) * (hop / sr)), 3)
    else:
        active_sec = 0.0
    return {
        "rms_dbfs": max(-120.0, rms_db),
        "peak_dbfs": max(-120.0, peak_db),
        "active_sec": active_sec,
        "pcm_sha256": _pcm_sha256(arr),
    }


def load_voice_track_safe(
    parsed_script: Dict[str, Any],
    n_total: int,
    target_sr: int = SR,
    voice_expected: bool = True,
) -> Tuple[np.ndarray, bool]:
    """Load expected VO audio safely in bounded chunks or fail closed when mandatory VO is missing."""
    if not voice_expected:
        return np.zeros(n_total, dtype=np.float64), False

    vo_info = parsed_script.get("voice") or {}
    vo_path_str = vo_info.get("vo_wav_path")
    if not vo_path_str or not Path(vo_path_str).exists():
        raise RuntimeError(f"Mandatory voiceover expected, but voice WAV is missing: {vo_path_str!r}")

    vo_path = Path(vo_path_str)
    with sf.SoundFile(str(vo_path)) as sfh:
        in_sr = int(sfh.samplerate)
        max_in = min(len(sfh), int(math.ceil((n_total / float(target_sr) + 1.0) * in_sr)))
        vo_raw = sfh.read(frames=max(1, max_in), dtype="float64", always_2d=True)

    if vo_raw.size == 0 or not np.all(np.isfinite(vo_raw)):
        raise RuntimeError(f"Corrupt or non-finite voiceover audio in {vo_path}")

    mono = vo_raw.mean(axis=1)
    if float(np.max(np.abs(mono))) < 1e-5:
        raise RuntimeError(f"Mandatory voiceover track is effectively silent: {vo_path}")

    if in_sr != target_sr:
        g = math.gcd(in_sr, target_sr)
        mono = signal.resample_poly(mono, target_sr // g, in_sr // g)

    return mono, True


def normalize_and_condition_voice(vo_mono: np.ndarray, sr: int = SR) -> np.ndarray:
    """High-pass cleanup + smooth dynamics conditioning + clean peak margin for VO."""
    if float(np.max(np.abs(vo_mono))) < 1e-7:
        return np.zeros_like(vo_mono, dtype=np.float64)
    vo_clean = _hp(vo_mono, 85.0, sr=sr)
    vo_env = _lp(np.abs(vo_clean), 18.0, sr=sr)
    comp_gain = np.where(vo_env > 0.14, (0.14 / np.maximum(vo_env, 1e-6)) ** 0.38, 1.0)
    vo_clean = vo_clean * comp_gain
    pk = float(np.max(np.abs(vo_clean)) + 1e-9)
    vo_clean = (vo_clean / pk) * 0.85
    return np.nan_to_num(vo_clean, nan=0.0, posinf=0.0, neginf=0.0)


def calculate_voice_activity_envelope(
    voice: np.ndarray,
    sample_rate: int = SR,
    attack_ms: float = 35.0,
    release_ms: float = 260.0,
) -> np.ndarray:
    """Directional exponential envelope follower preventing choppy syllabic ducking/pumping."""
    mono = np.abs(voice.mean(axis=1) if voice.ndim == 2 else voice)
    if float(np.max(mono)) < 1e-7:
        return np.zeros(len(mono), dtype=np.float64)

    # Compute 5 ms RMS frames for fast vector smoothing before sample interpolation
    hop = max(1, int(round(0.005 * sample_rate)))
    n_frames = max(1, int(math.ceil(len(mono) / hop)))
    padded = np.pad(mono, (0, n_frames * hop - len(mono)))
    rms_f = np.sqrt(np.mean(padded.reshape(n_frames, hop) ** 2, axis=1) + 1e-12)

    dt = hop / float(sample_rate)
    a_atk = math.exp(-dt / max(1e-3, attack_ms * 0.001))
    a_rel = math.exp(-dt / max(1e-3, release_ms * 0.001))

    env_f = np.zeros(n_frames, dtype=np.float64)
    cur = 0.0
    for i in range(n_frames):
        x = rms_f[i]
        coeff = a_atk if x > cur else a_rel
        cur = coeff * cur + (1.0 - coeff) * x
        env_f[i] = cur

    # Normalize relative to speech threshold (0.045 RMS -> 1.0 activity) and upsample smoothly
    act_f = np.clip((env_f - 0.012) / 0.045, 0.0, 1.0)
    t_f = (np.arange(n_frames, dtype=np.float64) + 0.5) * hop
    t_s = np.arange(len(mono), dtype=np.float64)
    return np.interp(t_s, t_f, act_f)


def apply_sidechain_ducking(
    music: np.ndarray,
    voice_activity: np.ndarray,
    attack_ms: float = 35.0,
    release_ms: float = 260.0,
    depth_db: float = -10.5,
    sample_rate: int = SR,
) -> np.ndarray:
    """Attenuate music gently under speech while keeping underscore clearly audible in gaps."""
    if music.size == 0:
        return music
    n = min(music.shape[0], len(voice_activity))
    act = voice_activity[:n]
    min_gain = 10.0 ** (min(-0.5, float(depth_db)) / 20.0)
    duck_gain = 1.0 - (1.0 - min_gain) * np.clip(act, 0.0, 1.0)
    out = music.copy()
    if out.ndim == 2:
        out[:n] *= duck_gain[:, None]
    else:
        out[:n] *= duck_gain
    return out


def _synthesize_ambience_bed(
    amb_cfg: Dict[str, Any],
    n_total: int,
    rng: np.random.Generator,
    sr: int = SR,
) -> np.ndarray:
    if not amb_cfg.get("enabled", True):
        return np.zeros((n_total, 2), dtype=np.float64)
    gen = str(amb_cfg.get("generator_name") or "studio_room_ambience")
    gain_db = float(amb_cfg.get("gain_db", -32.0))
    gain_lin = 10.0 ** (gain_db / 20.0)
    t_all = _t(n_total, sr=sr)

    if gen == "arena_wind_ambience":
        # Subtle textured open-air arena rumble (filtered warm noise with gentle slow breeze modulation)
        base = _bp(rng.standard_normal(n_total), 90.0, 620.0, sr=sr)
        mod = 0.58 + 0.42 * np.sin(2.0 * np.pi * 0.16 * t_all + 0.3)
    elif gen == "period_street_ambience":
        # Historical 1919 Boston harbor air & quiet distant street tone (zero modern engines/sirens)
        base = _bp(rng.standard_normal(n_total), 80.0, 520.0, sr=sr)
        mod = 0.62 + 0.38 * np.sin(2.0 * np.pi * 0.14 * t_all + 0.4)
    elif gen == "coastal_wind_ambience":
        # 1940 Puget Sound narrows coastal air & subtle bridge wind swell
        base = _bp(rng.standard_normal(n_total), 95.0, 680.0, sr=sr)
        mod = 0.58 + 0.42 * np.sin(2.0 * np.pi * 0.18 * t_all + 0.6)
    elif gen in ("minimal_quiet", "rescue_ambience"):
        base = _bp(rng.standard_normal(n_total), 140.0, 480.0, sr=sr)
        mod = 0.70 + 0.30 * np.sin(2.0 * np.pi * 0.11 * t_all)
    else:
        base = _bp(rng.standard_normal(n_total), 110.0, 780.0, sr=sr)
        mod = 0.65 + 0.35 * np.sin(2.0 * np.pi * 0.22 * t_all)

    amb_mono = base * mod
    pk_rms = float(np.sqrt(np.mean(amb_mono ** 2)) + 1e-9)
    amb_mono = (amb_mono / pk_rms) * gain_lin
    return np.stack([amb_mono, np.roll(amb_mono, int(0.005 * sr))], axis=1)


def mix_stems(
    voice: np.ndarray,
    music: np.ndarray,
    sfx: np.ndarray,
    ambience: np.ndarray,
    mixing_config: Optional[Dict[str, Any]] = None,
    sr: int = SR,
) -> Dict[str, Any]:
    """Combine voice, ducked music, SFX, and ambience under explicit intelligibility hierarchy."""
    cfg = mixing_config or {}
    n_total = max(len(voice), music.shape[0], sfx.shape[0], ambience.shape[0])

    def _fit_stereo(x: np.ndarray) -> np.ndarray:
        if x.ndim == 1:
            st = np.stack([x, x], axis=1)
        else:
            st = x[:, :2]
        if st.shape[0] < n_total:
            return np.pad(st, ((0, n_total - st.shape[0]), (0, 0)))
        return st[:n_total].copy()

    vo_mono = np.pad(voice, (0, max(0, n_total - len(voice))))[:n_total] if voice.ndim == 1 else voice[:n_total].mean(axis=1)
    vo_stereo = np.stack([vo_mono, vo_mono], axis=1)
    mus_st = _fit_stereo(music)
    sfx_st = _fit_stereo(sfx)
    amb_st = _fit_stereo(ambience)

    has_vo = float(np.max(np.abs(vo_mono))) > 1e-5
    vo_act = calculate_voice_activity_envelope(
        vo_mono,
        sample_rate=sr,
        attack_ms=float(cfg.get("attack_ms", 35.0)),
        release_ms=float(cfg.get("release_ms", 260.0)),
    ) if has_vo else np.zeros(n_total, dtype=np.float64)

    # Calibrate music level cleanly (-20 dBFS base, ducked further by -10.5 dB during speech)
    mus_rms = float(np.sqrt(np.mean(mus_st ** 2)) + 1e-9)
    mus_active = mus_rms > 1e-6
    if mus_active:
        base_music_scale = float(cfg.get("music_bus_gain", 0.34))
        mus_scaled = mus_st * base_music_scale
        ducked_music = apply_sidechain_ducking(
            mus_scaled,
            vo_act,
            attack_ms=float(cfg.get("attack_ms", 35.0)),
            release_ms=float(cfg.get("release_ms", 260.0)),
            depth_db=float(cfg.get("duck_depth_db", -10.5)),
            sample_rate=sr,
        )
    else:
        ducked_music = mus_st

    # Optional twist-beat silence/ducking window for contrast transitions (smooth 25ms cosine ramp)
    for twin in cfg.get("twist_duck_windows", []):
        if float(np.max(np.abs(ducked_music))) <= 1e-6:
            break
        w0 = max(0, int(round(float(twin.get("start_sec", 0.0)) * sr)))
        w1 = min(n_total, int(round(float(twin.get("end_sec", 0.0)) * sr)))
        if w1 > w0 + 16:
            depth = 10.0 ** (float(twin.get("duck_db", -11.0)) / 20.0)
            ramp = min((w1 - w0) // 3, int(0.025 * sr))
            env = np.full(w1 - w0, depth, dtype=np.float64)
            if ramp > 0:
                env[:ramp] = 1.0 - (1.0 - depth) * 0.5 * (1.0 - np.cos(np.pi * np.arange(ramp) / ramp))
                env[-ramp:] = depth + (1.0 - depth) * 0.5 * (1.0 - np.cos(np.pi * np.arange(ramp) / ramp))
            ducked_music[w0:w1] *= env[:, None]

    # Voice-protecting pocket on SFX bus (gently dips colliding dense SFX under speech without muting impacts)
    if has_vo and float(np.max(np.abs(sfx_st))) > 1e-6:
        sfx_pocket = 1.0 - 0.28 * vo_act[:, None]
        sfx_bus = sfx_st * sfx_pocket * float(cfg.get("sfx_bus_gain", 0.72))
    else:
        sfx_bus = sfx_st * float(cfg.get("sfx_bus_gain", 0.72))

    # Optional intentional silences mask
    sil_mask = np.ones((n_total, 1), dtype=np.float64)
    for isil in cfg.get("intentional_silences", []):
        i0 = max(0, int(round(float(isil.get("start_sec", 0.0)) * sr)))
        i1 = min(n_total, int(round(float(isil.get("end_sec", 0.0)) * sr)))
        if i1 > i0:
            sil_mask[i0:i1] = 0.0

    # Master Pre (before single EBU R128 mastering stage)
    master_pre = (vo_stereo + ducked_music + sfx_bus + amb_st) * sil_mask

    # Gentle tail fade cleanly when active audio present (avoid overwriting intentionally short ends)
    fade_len = min(n_total // 6, int(0.32 * sr))
    if fade_len > 0 and float(np.max(np.abs(master_pre))) > 1e-6:
        env = np.ones(n_total, dtype=np.float64)
        env[-fade_len:] = np.linspace(1.0, 0.0, fade_len)
        master_pre *= env[:, None]

    # Pre-master safety soft clip (< 0.96) & NaN guard
    master_pre = np.nan_to_num(master_pre, nan=0.0, posinf=0.0, neginf=0.0)
    pk_pre = float(np.max(np.abs(master_pre)))
    if pk_pre > 0.95:
        master_pre = np.tanh(master_pre / max(1.0, pk_pre * 1.05)) * 0.89

    return {
        "voice_stereo": vo_stereo,
        "music_raw_stereo": mus_st,
        "music_ducked_stereo": ducked_music,
        "sfx_stereo": sfx_bus,
        "ambience_stereo": amb_st,
        "master_pre": master_pre,
        "voice_activity": vo_act,
    }


def _master_pre_to_final_wav(
    master_pre_wav: Path,
    final_mix_wav: Path,
    target_lufs: float = -14.0,
    target_tp_dbtp: float = -1.5,
) -> Tuple[np.ndarray, str]:
    """Apply ONE authoritative EBU R128 loudness normalization + limiter pass cleanly."""
    pre_arr, pre_sr = sf.read(str(master_pre_wav), dtype="float64", always_2d=True)
    if float(np.max(np.abs(pre_arr))) < 1e-6:
        # Intentionally completely silent run -> preserve pure silence without inflating quantization noise!
        sf.write(str(final_mix_wav), pre_arr.astype(np.float32), pre_sr)
        return pre_arr, "intentional_silence_bypass"

    ff_bin = shutil.which("ffmpeg")
    if ff_bin:
        effective_tp = min(-2.4, float(target_tp_dbtp) - 0.85)
        af = (
            f"alimiter=limit=0.82:attack=4:release=60:level=false,"
            f"loudnorm=I={target_lufs:.1f}:TP={effective_tp:.1f}:LRA=9,"
            f"lowpass=f=18000,"
            f"alimiter=limit=0.74:attack=4:release=60:level=false"
        )
        subprocess.run(
            [
                ff_bin, "-v", "error", "-y",
                "-i", str(master_pre_wav),
                "-af", af,
                "-ar", str(pre_sr), "-ac", "2",
                "-c:a", "pcm_f32le",
                str(final_mix_wav),
            ],
            check=True,
        )
        out_arr, _ = sf.read(str(final_mix_wav), dtype="float64", always_2d=True)
        out_arr = np.nan_to_num(out_arr, nan=0.0, posinf=0.0, neginf=0.0)
        return out_arr, "ffmpeg_alimiter_loudnorm_single_pass"

    # Deterministic pure-NumPy fallback if ffmpeg unavailable
    cur_rms = float(np.sqrt(np.mean(pre_arr ** 2)) + 1e-9)
    tgt_rms = 10.0 ** ((target_lufs - 1.5) / 20.0)
    scaled = np.tanh((pre_arr * min(4.0, tgt_rms / cur_rms)) / 0.92) * 0.84
    sf.write(str(final_mix_wav), scaled.astype(np.float32), pre_sr)
    return scaled, "numpy_soft_limiter_fallback"


def write_audio_mix_report(
    out_path: Path,
    stems: Dict[str, np.ndarray],
    final_mix: np.ndarray,
    mastering_method: str,
    cue_counts: Dict[str, int],
    audio_plan: Dict[str, Any],
    notes: List[str],
    sr: int = SR,
) -> Dict[str, Any]:
    vo_s = _stem_stats(stems["voice_stereo"], sr=sr)
    mus_s = _stem_stats(stems["music_ducked_stereo"], sr=sr)
    sfx_s = _stem_stats(stems["sfx_stereo"], sr=sr)
    amb_s = _stem_stats(stems["ambience_stereo"], sr=sr)
    mix_s = _stem_stats(final_mix, sr=sr)

    dur = round(final_mix.shape[0] / float(sr), 3)
    margin = round(vo_s["rms_dbfs"] - mus_s["rms_dbfs"], 2) if (vo_s["rms_dbfs"] > -90 and mus_s["rms_dbfs"] > -90) else None

    report: Dict[str, Any] = {
        "schema_version": "sd-audio-mix-1",
        "sample_rate": sr,
        "channels": 2,
        "duration_sec": dur,
        "mastering_method": mastering_method,
        "already_mastered": True,
        "voice_expected": bool((audio_plan.get("voice") or {}).get("expected", True)),
        "rms_dbfs": mix_s["rms_dbfs"],
        "peak_dbfs": mix_s["peak_dbfs"],
        "vo_rms_dbfs": vo_s["rms_dbfs"],
        "ducked_music_rms_dbfs": mus_s["rms_dbfs"],
        "vo_to_music_margin_db": margin,
        "mix_pcm_sha256": mix_s["pcm_sha256"],
        "stems": {
            "voice": vo_s,
            "music": mus_s,
            "sfx": sfx_s,
            "ambience": amb_s,
            "mix": mix_s,
        },
        "sfx_cue_count": cue_counts.get("sfx_rendered", 0),
        "music_segments_count": cue_counts.get("music_rendered", 0),
        "notes": notes,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def mix_production_audio(
    storyboard: Dict[str, Any],
    parsed_script: Dict[str, Any],
    run_dir: Path,
    seed: int = 42,
    audio_plan: Optional[Dict[str, Any]] = None,
    catalog: Optional[List[AudioAsset]] = None,
    policy: Optional[LicensePolicy] = None,
    qa_audio_root: Optional[Path] = None,
    music_mode: str = "auto",
    sfx_mode: str = "auto",
    sfx_density: str = "balanced",
    music_file: Optional[Path] = None,
    music_rights_confirmed: bool = False,
    music_gain_db: float = 0.0,
    sfx_gain_db: float = 0.0,
    music_intensity: Optional[str] = None,
    voice_expected: bool = True,
    existing_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Synthesize/resolve all stems, enforce hierarchy & sidechain ducking, master once, and export manifests."""
    audio_dir = run_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    total_dur = float(storyboard["total_duration_sec"])
    n_total = max(1, int(round(total_dur * SR)))

    # 1. Build/reuse validated narrative AudioPlan
    if audio_plan is None:
        audio_plan = build_audio_narrative_plan(
            parsed_script=parsed_script,
            storyboard=storyboard,
            run_dir=run_dir,
            music_mode=music_mode,
            sfx_mode=sfx_mode,
            sfx_density=sfx_density,
            music_intensity=music_intensity,
            voice_expected=voice_expected,
            existing_plan=existing_plan,
            music_gain_db=music_gain_db,
            sfx_gain_db=sfx_gain_db,
        )

    # 2. Discover read-only AudioCatalog (native + optional QA root)
    policy_eff = policy or LicensePolicy(allow_user_file_without_sidecar=music_rights_confirmed)
    validations: Dict[str, ValidationResult] = {}
    allowed_roots: List[Path] = []
    if qa_audio_root and qa_audio_root.exists():
        allowed_roots.append(qa_audio_root.resolve())
    if music_file and music_file.exists():
        allowed_roots.append(music_file.resolve().parent)

    if catalog is None:
        native_assets = discover_native_audio_assets(run_dir)
        qa_assets = discover_qa_audio_assets(qa_audio_root) if (qa_audio_root and qa_audio_root.exists()) else []
        catalog = native_assets + qa_assets

    qa_status = "QA_LIBRARY_MOUNTED_READONLY" if (qa_audio_root and (qa_audio_root / "audio").exists()) else "QA_LIBRARY_UNAVAILABLE"

    # 3. Load & condition Voiceover
    vo_raw, vo_present = load_voice_track_safe(parsed_script, n_total, target_sr=SR, voice_expected=voice_expected)
    vo_clean = normalize_and_condition_voice(vo_raw, sr=SR) if vo_present else np.zeros(n_total, dtype=np.float64)

    # 4. Select & render Music Stem
    music_sels, music_notes, music_assets = select_music_beds(
        plan=audio_plan,
        catalog=catalog,
        policy=policy_eff,
        music_mode=music_mode,
        music_file=music_file,
        music_rights_confirmed=music_rights_confirmed,
        seed=seed,
        allowed_roots=allowed_roots or None,
        validations_cache=validations,
    )
    music_wav = audio_dir / "music.wav"
    music_raw_stereo, music_cue_sheet = render_music_stem(
        plan=audio_plan,
        selections=music_sels,
        out_path=music_wav,
        music_gain_db=music_gain_db,
        seed=seed,
        sr=SR,
        cue_sheet_path=audio_dir / "music_cue_sheet.json",
    )

    # 5. Design & render SFX Stem
    sfx_cues, sfx_notes, sfx_assets = design_sfx_cues(
        audio_plan=audio_plan,
        catalog=catalog,
        policy=policy_eff,
        sfx_mode=sfx_mode,
        sfx_density=sfx_density,
        sfx_gain_db=sfx_gain_db,
        seed=seed,
        allowed_roots=allowed_roots or None,
        validations_cache=validations,
    )
    sfx_wav = audio_dir / "sfx.wav"
    sfx_raw_stereo, sfx_cue_sheet = render_sfx_stem(
        audio_plan=audio_plan,
        designed_cues=sfx_cues,
        out_path=sfx_wav,
        seed=seed,
        sr=SR,
        cue_sheet_path=audio_dir / "sfx_cue_sheet.json",
    )

    # 6. Synthesize scene ambience stem
    amb_stereo = _synthesize_ambience_bed(audio_plan.get("ambience") or {}, n_total, rng, sr=SR)
    if music_mode == "off" and sfx_mode == "off" and not voice_expected:
        amb_stereo = np.zeros_like(amb_stereo)

    # 7. Combine under strict hierarchy + write individual stems + master_pre
    mix_cfg = {
        **(audio_plan.get("voice") or {}),
        "intentional_silences": audio_plan.get("intentional_silences", []),
        "twist_duck_windows": (audio_plan.get("music") or {}).get("twist_duck_windows", []),
    }
    stems = mix_stems(
        voice=vo_clean,
        music=music_raw_stereo,
        sfx=sfx_raw_stereo,
        ambience=amb_stereo,
        mixing_config=mix_cfg,
        sr=SR,
    )

    voice_wav = audio_dir / "voice.wav"
    amb_wav = audio_dir / "ambience.wav"
    master_pre_wav = audio_dir / "master_pre.wav"
    mix_wav = audio_dir / "mix.wav"

    sf.write(str(voice_wav), stems["voice_stereo"].astype(np.float32), SR)
    sf.write(str(music_wav), stems["music_ducked_stereo"].astype(np.float32), SR)
    sf.write(str(sfx_wav), stems["sfx_stereo"].astype(np.float32), SR)
    sf.write(str(amb_wav), stems["ambience_stereo"].astype(np.float32), SR)
    sf.write(str(master_pre_wav), stems["master_pre"].astype(np.float32), SR)

    # 8. Authoritative Single-Pass Master
    qpol = audio_plan.get("quality_policy") or {}
    final_mix_arr, master_method = _master_pre_to_final_wav(
        master_pre_wav=master_pre_wav,
        final_mix_wav=mix_wav,
        target_lufs=float(qpol.get("target_lufs", -14.0)),
        target_tp_dbtp=float(qpol.get("max_true_peak_dbtp", -1.5)),
    )

    # 9. Emit Provenance Asset Manifest & Mandatory Credits
    used_roles: Dict[str, List[str]] = {}
    for sel in music_sels:
        a = sel.get("asset")
        if a:
            used_roles.setdefault(a.asset_id, []).append(f"music:{sel.get('segment_id')}({sel.get('mood')})")
    for c in sfx_cues:
        a = c.get("asset")
        if a:
            used_roles.setdefault(a.asset_id, []).append(f"sfx:{c.get('event')}@{c.get('time_sec')}s")

    all_notes = list(dict.fromkeys(music_notes + sfx_notes))
    manifest_p = write_audio_asset_manifest(
        out_path=audio_dir / "audio_asset_manifest.json",
        catalog=catalog,
        validations=validations,
        used_asset_roles=used_roles,
        qa_status=qa_status,
        qa_root=qa_audio_root,
        fallback_notes=all_notes,
    )
    credits_p = write_credits_file(
        out_path=audio_dir / "credits_audio.txt",
        used_assets=music_assets + sfx_assets,
        validations=validations,
    )

    report = write_audio_mix_report(
        out_path=audio_dir / "audio_mix_report.json",
        stems=stems,
        final_mix=final_mix_arr,
        mastering_method=master_method,
        cue_counts={
            "music_rendered": len(music_sels),
            "sfx_expected": len(audio_plan.get("sfx", [])),
            "sfx_rendered": len(sfx_cue_sheet.get("cues", [])),
        },
        audio_plan=audio_plan,
        notes=all_notes,
        sr=SR,
    )

    # Attach exact paths & provenance summary for orchestrator / QC gate
    report.update({
        "mix_wav_path": str(mix_wav.resolve()),
        "voice_wav_path": str(voice_wav.resolve()),
        "music_wav_path": str(music_wav.resolve()),
        "sfx_wav_path": str(sfx_wav.resolve()),
        "ambience_wav_path": str(amb_wav.resolve()),
        "master_pre_wav_path": str(master_pre_wav.resolve()),
        "audio_plan_json_path": str((audio_dir / "audio_plan.json").resolve()),
        "music_cue_sheet_json_path": str((audio_dir / "music_cue_sheet.json").resolve()),
        "sfx_cue_sheet_json_path": str((audio_dir / "sfx_cue_sheet.json").resolve()),
        "audio_asset_manifest_json_path": str(manifest_p.resolve()),
        "credits_audio_txt_path": str(credits_p.resolve()),
        "qa_audio_root_status": qa_status,
        "music_mode": music_mode,
        "sfx_mode": sfx_mode,
        "sfx_cues": [{"time": c["time_sec"], "type": c["event"]} for c in sfx_cue_sheet.get("cues", [])],
    })
    (audio_dir / "audio_mix_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
