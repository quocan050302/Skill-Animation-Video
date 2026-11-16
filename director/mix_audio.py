"""STEP 6: Procedural Sound Design, Beat-Synced Underscore, SFX & Ducking Mixer.

100% licensed/original code-synthesized DSP audio (NumPy + SciPy):
- Continuous subtle room/studio ambience (prevents dead-air digital zero dropouts)
- Style-matched musical underscore synced to tempo & narrative turn
- Frame-accurate transition & action SFX (`whoosh`, `pop`, `sparkle`, `thud`, `tick`, `riser`)
- Voiceover high-pass cleanup, gentle leveling compression, and envelope sidechain ducking
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import soundfile as sf
from scipy import signal


SR = 48000


def _t(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float64) / SR


def _lp(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    b, a = signal.butter(order, min(0.98, cutoff / (SR * 0.5)), btype="low")
    return signal.lfilter(b, a, x)


def _hp(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    b, a = signal.butter(order, max(0.001, cutoff / (SR * 0.5)), btype="high")
    return signal.lfilter(b, a, x)


def _bp(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    b, a = signal.butter(order, [max(0.001, lo / (SR * 0.5)), min(0.98, hi / (SR * 0.5))], btype="band")
    return signal.lfilter(b, a, x)


def _place(buf: np.ndarray, clip: np.ndarray, at_sec: float, gain: float = 1.0, pan: float = 0.0) -> None:
    """Place mono clip into stereo buffer `buf` (shape [N, 2]) with constant-power pan (-1..+1)."""
    i0 = int(round(at_sec * SR))
    if i0 >= buf.shape[0] or i0 + len(clip) <= 0:
        return
    src_start = max(0, -i0)
    dst_start = max(0, i0)
    count = min(len(clip) - src_start, buf.shape[0] - dst_start)
    if count <= 0:
        return
    angle = (pan + 1.0) * (np.pi / 4.0)
    g_l = gain * np.cos(angle)
    g_r = gain * np.sin(angle)
    seg = clip[src_start : src_start + count]
    buf[dst_start : dst_start + count, 0] += seg * g_l
    buf[dst_start : dst_start + count, 1] += seg * g_r


def _whoosh(rng: np.random.Generator, dur: float = 0.30, up: bool = True) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    noise = rng.standard_normal(n)
    lo = _bp(noise, 240, 1100)
    hi = _bp(noise, 1400, 5600)
    sweep = np.linspace(0.0, 1.0, n) if up else np.linspace(1.0, 0.0, n)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.6
    return (lo * (1.0 - sweep) + hi * sweep) * env * 1.35


def _pop(freq: float = 560.0) -> np.ndarray:
    n = int(0.11 * SR)
    t = _t(n)
    f_curve = freq * (1.0 + 14.0 * t)
    return np.sin(2.0 * np.pi * np.cumsum(f_curve) / SR) * np.exp(-t * 42.0) * 0.8


def _thud(rng: np.random.Generator, f0: float = 68.0, dur: float = 0.34) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    f_curve = f0 * (1.0 + 1.6 * np.exp(-t * 28.0))
    tone = np.sin(2.0 * np.pi * np.cumsum(f_curve) / SR) * np.exp(-t * 11.0)
    trans = _lp(rng.standard_normal(n), 850.0) * np.exp(-t * 38.0) * 0.45
    return tone + trans


def _chime(freq: float = 1567.98, dur: float = 0.75) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    atk = np.minimum(1.0, t / 0.004)
    harm = (
        np.sin(2.0 * np.pi * freq * t)
        + 0.42 * np.sin(2.0 * np.pi * freq * 2.005 * t) * np.exp(-t * 5.0)
        + 0.20 * np.sin(2.0 * np.pi * freq * 3.01 * t) * np.exp(-t * 9.0)
    )
    return harm * np.exp(-t * 4.5) * atk * 0.45


def _sparkle_arpeggio() -> np.ndarray:
    out = np.zeros((int(0.85 * SR), 2), dtype=np.float64)
    for idx, f in enumerate([1318.5, 1568.0, 1975.5, 2637.0]):
        _place(out, _chime(f, 0.55), idx * 0.055, gain=0.45, pan=-0.3 + idx * 0.2)
    return out.mean(axis=1)


def _blade_ring(freq: float = 980.0, dur: float = 0.65) -> np.ndarray:
    n = int(dur * SR)
    t = _t(n)
    atk = np.minimum(1.0, t / 0.003)
    partials = (
        np.sin(2.0 * np.pi * freq * t)
        + 0.55 * np.sin(2.0 * np.pi * freq * 1.49 * t) * np.exp(-t * 4.5)
        + 0.35 * np.sin(2.0 * np.pi * freq * 2.34 * t) * np.exp(-t * 8.0)
        + 0.20 * np.sin(2.0 * np.pi * freq * 3.81 * t) * np.exp(-t * 14.0)
    )
    return partials * np.exp(-t * 5.2) * atk * 0.42


def _tick(rng: np.random.Generator) -> np.ndarray:
    n = int(0.035 * SR)
    t = _t(n)
    return _hp(rng.standard_normal(n), 2800.0) * np.exp(-t * 190.0) * 0.55 + np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 150.0) * 0.3


def _pluck_note(rng: np.random.Generator, midi_note: int, dur: float = 0.48) -> np.ndarray:
    freq = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
    n = int(dur * SR)
    period = max(4, int(round(SR / freq)))
    ring = rng.uniform(-1.0, 1.0, period)
    out = np.zeros(n, dtype=np.float64)
    for i in range(n):
        idx = i % period
        out[i] = ring[idx]
        ring[idx] = 0.497 * (ring[idx] + ring[(idx + 1) % period])
    t = _t(n)
    out = _bp(out, 140.0, 3600.0) * np.exp(-t * 5.2)
    pk = np.max(np.abs(out)) + 1e-9
    return out / pk


def _soft_pad_chord(midi_notes: List[int], dur: float) -> np.ndarray:
    n = max(1, int(dur * SR))
    t = _t(n)
    acc = np.zeros(n, dtype=np.float64)
    for m in midi_notes:
        f = 440.0 * (2.0 ** ((m - 69) / 12.0))
        acc += np.sin(2.0 * np.pi * f * t) + 0.35 * np.sin(2.0 * np.pi * f * 2.0 * t + 0.4)
    acc = _lp(acc / max(1, len(midi_notes)), 1200.0)
    fade_in = np.minimum(1.0, t / 0.28)
    fade_out = np.minimum(1.0, np.maximum(0.0, dur - t) / 0.32)
    return acc * fade_in * fade_out * 0.35


def mix_production_audio(
    storyboard: Dict[str, Any],
    parsed_script: Dict[str, Any],
    run_dir: Path,
    seed: int = 42,
) -> Dict[str, Any]:
    """Synthesize SFX + underscore + ambience and mix with ducked voiceover into `audio/mix.wav`."""
    audio_dir = run_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    total_dur = float(storyboard["total_duration_sec"])
    n_total = int(round(total_dur * SR))
    selected_skill = storyboard["selected_skill"]
    shots = storyboard["shots"]

    # 1. Load & condition Voiceover
    vo_raw, vo_sr = sf.read(parsed_script["voice"]["vo_wav_path"], dtype="float64")
    if vo_raw.ndim > 1:
        vo_raw = vo_raw.mean(axis=1)
    if vo_sr != SR:
        vo_raw = signal.resample_poly(vo_raw, SR, vo_sr)

    vo_clean = _hp(vo_raw, 85.0)
    # Smooth envelope soft-knee compression on VO
    vo_env = _lp(np.abs(vo_clean), 18.0)
    comp_gain = np.where(vo_env > 0.14, (0.14 / np.maximum(vo_env, 1e-6)) ** 0.38, 1.0)
    vo_clean = vo_clean * comp_gain
    vo_pk = np.max(np.abs(vo_clean)) + 1e-9
    vo_clean = (vo_clean / vo_pk) * 0.86

    vo_track = np.zeros(n_total, dtype=np.float64)
    copy_n = min(n_total, len(vo_clean))
    vo_track[:copy_n] = vo_clean[:copy_n]

    # 2. Subtle warm studio/outdoor ambience bed (prevents dead digital silence)
    amb_noise = _bp(rng.standard_normal(n_total), 120.0, 900.0)
    t_all = _t(n_total)
    amb_mod = 0.65 + 0.35 * np.sin(2.0 * np.pi * 0.22 * t_all)
    amb_mono = amb_noise * amb_mod * 0.012
    ambience = np.stack([amb_mono, np.roll(amb_mono, 240)], axis=1)

    # 3. Beat-synced procedural underscore matched to locked skill mood
    music = np.zeros((n_total, 2), dtype=np.float64)
    bpm = 108.0 if selected_skill in ("stick-figure", "map-route") else (92.0 if selected_skill == "minimalistic-graphics" else 100.0)
    beat_s = 60.0 / bpm

    # Chord progression: Dm7 -> Bbmaj7 -> Fmaj7 -> C6, resolving bright on final shot
    prog_minor = [(50, [62, 65, 69]), (46, [58, 62, 65]), (53, [60, 65, 69]), (48, [60, 64, 67])]
    prog_bright = [(50, [62, 66, 69]), (55, [62, 67, 71]), (57, [61, 64, 69]), (50, [62, 66, 74])]

    payoff_start = shots[-1]["start"] if shots else total_dur * 0.78
    bar_t = 0.0
    bar_idx = 0
    note_cache: Dict[int, np.ndarray] = {}

    def get_pluck(m: int) -> np.ndarray:
        if m not in note_cache:
            note_cache[m] = _pluck_note(rng, m, 0.46)
        return note_cache[m]

    while bar_t < total_dur - 0.15:
        prog = prog_bright if bar_t >= payoff_start - 0.1 else prog_minor
        root, triad = prog[bar_idx % 4]
        bar_len = min(4.0 * beat_s, total_dur - bar_t)
        # Warm soft pad layer
        _place(music, _soft_pad_chord(triad, bar_len), bar_t, gain=0.45, pan=0.0)

        if selected_skill != "minimalistic-graphics":
            # Plucked bass & off-beat arpeggio
            _place(music, get_pluck(root), bar_t, gain=0.65, pan=-0.12)
            if bar_t + 2 * beat_s < total_dur:
                _place(music, get_pluck(root + 7), bar_t + 2 * beat_s, gain=0.50, pan=0.12)
            for step_i, m_n in enumerate(triad):
                nt = bar_t + (step_i + 1) * beat_s
                if nt < total_dur - 0.1:
                    _place(music, get_pluck(m_n), nt, gain=0.32, pan=(-0.25 + 0.25 * step_i))
        else:
            # Minimalistic calm bell pulse on beat 1
            _place(music, _chime(440.0 * (2.0 ** ((triad[0] - 69) / 12.0)), 1.2), bar_t, gain=0.35, pan=0.0)

        bar_t += 4.0 * beat_s
        bar_idx += 1

    # Resolving final chord swell on ending payoff
    if shots:
        end_hit = max(0.0, total_dur - 0.72)
        _place(music, _sparkle_arpeggio(), end_hit, gain=0.52, pan=0.0)

    # 4. Frame-accurate Editorial SFX Cues
    sfx = np.zeros((n_total, 2), dtype=np.float64)
    cues_log: List[Dict[str, Any]] = []

    # Opening hook subtle pop
    _place(sfx, _pop(520.0), 0.04, gain=0.32, pan=-0.1)
    cues_log.append({"time": 0.04, "type": "hook_pop"})

    for i, s in enumerate(shots):
        # Transition out SFX
        tr = s["transition_out"]
        t_end = float(s["end"])
        if i < len(shots) - 1:
            if tr == "whip":
                _place(sfx, _whoosh(rng, 0.28, up=(i % 2 == 0)), max(0.0, t_end - 0.15), gain=0.36, pan=(-0.35 if i % 2 == 0 else 0.35))
                cues_log.append({"time": round(t_end - 0.15, 3), "type": "whip_whoosh"})
            elif tr in ("iris_mask", "match_zoom"):
                _place(sfx, _whoosh(rng, 0.22, up=True), max(0.0, t_end - 0.12), gain=0.26, pan=0.0)
                cues_log.append({"time": round(t_end - 0.12, 3), "type": "transition_sweep"})
            elif tr == "dip_to_black":
                _place(sfx, _thud(rng, 58.0, 0.4), max(0.0, t_end - 0.06), gain=0.38, pan=0.0)
                cues_log.append({"time": round(t_end - 0.06, 3), "type": "turn_low_thud"})

        # Mid-shot bespoke action cues
        mid_t = 0.5 * (float(s["start"]) + float(s["end"]))
        if s.get("novel_non_template"):
            if selected_skill == "zach-d-films":
                _place(sfx, _whoosh(rng, 0.25, up=False), float(s["start"]) + 0.12, gain=0.35, pan=-0.15)
                _place(sfx, _blade_ring(1040.0, 0.72), mid_t - 0.1, gain=0.34, pan=0.1)
                _place(sfx, _thud(rng, 62.0, 0.36), mid_t - 0.08, gain=0.34, pan=0.0)
            else:
                for k in range(5):
                    tk = float(s["start"]) + 0.35 + k * 0.16
                    if tk < float(s["end"]):
                        _place(sfx, _tick(rng), tk, gain=0.28, pan=-0.2 + k * 0.1)
                _place(sfx, _chime(1318.5, 0.65), mid_t, gain=0.28, pan=0.15)
            cues_log.append({"time": round(mid_t, 3), "type": "mechanism_ticks_and_chime"})
        elif "mechanism" in s["beat_role"] and selected_skill == "zach-d-films":
            _place(sfx, _thud(rng, 64.0, 0.34), float(s["start"]) + 0.48, gain=0.40, pan=0.1)
            _place(sfx, _blade_ring(1480.0, 0.55), float(s["start"]) + 0.50, gain=0.25, pan=0.15)
            cues_log.append({"time": round(float(s["start"]) + 0.48, 3), "type": "scale_coin_slam"})
        elif "turn" in s["beat_role"]:
            _place(sfx, _thud(rng, 72.0, 0.32), float(s["start"]) + 0.18, gain=0.40, pan=0.0)
            cues_log.append({"time": round(float(s["start"]) + 0.18, 3), "type": "turn_impact"})

    # Payoff sparkle
    _place(sfx, _sparkle_arpeggio(), max(0.0, payoff_start + 0.25), gain=0.34, pan=0.0)
    cues_log.append({"time": round(payoff_start + 0.25, 3), "type": "payoff_sparkle"})

    # 5. Sidechain envelope ducking of Music under Voiceover
    vo_activity = _lp(np.abs(vo_track), 5.0)
    duck_curve = 1.0 - 0.62 * np.clip(vo_activity / 0.045, 0.0, 1.0)
    ducked_music = music * (0.23 * duck_curve[:, None])

    vo_stereo = np.stack([vo_track, vo_track], axis=1)
    master = vo_stereo * 1.0 + ducked_music + sfx * 0.42 + ambience

    # Smooth 0.38s ending fade-out
    fade_len = min(n_total // 4, int(0.38 * SR))
    if fade_len > 0:
        fade_env = np.ones(n_total, dtype=np.float64)
        fade_env[-fade_len:] = np.linspace(1.0, 0.0, fade_len)
        master *= fade_env[:, None]

    # Soft limiter & target peak -1.2 dBFS before FFmpeg EBU R128 final loudnorm
    peak = float(np.max(np.abs(master)) + 1e-9)
    master = np.tanh(master / max(1.0, peak * 1.05)) * 0.87

    mix_wav = audio_dir / "mix.wav"
    sfx_wav = audio_dir / "sfx.wav"
    music_wav = audio_dir / "music.wav"
    sf.write(str(mix_wav), master.astype(np.float32), SR)
    sf.write(str(sfx_wav), (sfx * 0.42).astype(np.float32), SR)
    sf.write(str(music_wav), ducked_music.astype(np.float32), SR)

    rms_db = round(float(20.0 * np.log10(np.sqrt(np.mean(master ** 2)) + 1e-9)), 2)
    peak_db = round(float(20.0 * np.log10(np.max(np.abs(master)) + 1e-9)), 2)
    vo_rms_db = round(float(20.0 * np.log10(np.sqrt(np.mean(vo_track[:copy_n] ** 2)) + 1e-9)), 2)
    music_rms_db = round(float(20.0 * np.log10(np.sqrt(np.mean(ducked_music ** 2)) + 1e-9)), 2)

    report = {
        "sample_rate": SR,
        "channels": 2,
        "duration_sec": round(n_total / SR, 3),
        "mix_wav_path": str(mix_wav),
        "rms_dbfs": rms_db,
        "peak_dbfs": peak_db,
        "vo_rms_dbfs": vo_rms_db,
        "ducked_music_rms_dbfs": music_rms_db,
        "vo_to_music_margin_db": round(vo_rms_db - music_rms_db, 2),
        "sfx_cue_count": len(cues_log),
        "sfx_cues": cues_log,
    }
    (audio_dir / "audio_mix_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
