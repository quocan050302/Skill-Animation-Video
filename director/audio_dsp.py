"""Shared Time-Deterministic NumPy/SciPy Audio DSP Primitives (48 kHz Stereo Pipeline).

Pure math / SciPy synthesis helpers reused cleanly across `music_director.py`,
`sfx_director.py`, and `mix_audio.py` without duplicating filter/envelope logic
or touching any visual engine modules.
"""

from __future__ import annotations

from typing import List

import numpy as np
from scipy import signal


SR = 48000


def _t(n: int, sr: int = SR) -> np.ndarray:
    return np.arange(n, dtype=np.float64) / float(sr)


def _lp(x: np.ndarray, cutoff: float, order: int = 2, sr: int = SR) -> np.ndarray:
    b, a = signal.butter(order, min(0.98, max(0.002, cutoff / (sr * 0.5))), btype="low")
    return signal.lfilter(b, a, x)


def _hp(x: np.ndarray, cutoff: float, order: int = 2, sr: int = SR) -> np.ndarray:
    b, a = signal.butter(order, max(0.001, min(0.98, cutoff / (sr * 0.5))), btype="high")
    return signal.lfilter(b, a, x)


def _bp(x: np.ndarray, lo: float, hi: float, order: int = 2, sr: int = SR) -> np.ndarray:
    lo_n = max(0.001, min(0.96, lo / (sr * 0.5)))
    hi_n = max(lo_n + 0.002, min(0.98, hi / (sr * 0.5)))
    b, a = signal.butter(order, [lo_n, hi_n], btype="band")
    return signal.lfilter(b, a, x)


def _place(buf: np.ndarray, clip: np.ndarray, at_sec: float, gain: float = 1.0, pan: float = 0.0, sr: int = SR) -> None:
    """Place mono or stereo clip into stereo buffer `buf` (`[N, 2]`) with constant-power pan."""
    if clip.size == 0:
        return
    i0 = int(round(at_sec * sr))
    clip_len = clip.shape[0]
    if i0 >= buf.shape[0] or i0 + clip_len <= 0:
        return
    src_start = max(0, -i0)
    dst_start = max(0, i0)
    count = min(clip_len - src_start, buf.shape[0] - dst_start)
    if count <= 0:
        return
    pan_c = max(-1.0, min(1.0, float(pan)))
    angle = (pan_c + 1.0) * (np.pi / 4.0)
    g_l = gain * np.cos(angle)
    g_r = gain * np.sin(angle)
    seg = clip[src_start : src_start + count]
    if seg.ndim == 2:
        buf[dst_start : dst_start + count, 0] += seg[:, 0] * g_l * 1.4142
        buf[dst_start : dst_start + count, 1] += seg[:, 1] * g_r * 1.4142
    else:
        buf[dst_start : dst_start + count, 0] += seg * g_l
        buf[dst_start : dst_start + count, 1] += seg * g_r


def _whoosh(rng: np.random.Generator, dur: float = 0.30, up: bool = True) -> np.ndarray:
    n = max(16, int(dur * SR))
    t = _t(n)
    noise = rng.standard_normal(n)
    lo = _bp(noise, 240.0, 1100.0)
    hi = _bp(noise, 1400.0, 5600.0)
    sweep = np.linspace(0.0, 1.0, n) if up else np.linspace(1.0, 0.0, n)
    env = np.sin(np.pi * np.clip(t / dur, 0.0, 1.0)) ** 1.6
    return (lo * (1.0 - sweep) + hi * sweep) * env * 1.25


def _pop(freq: float = 560.0) -> np.ndarray:
    n = int(0.11 * SR)
    t = _t(n)
    f_curve = freq * (1.0 + 14.0 * t)
    atk = np.minimum(1.0, t / 0.002)
    return np.sin(2.0 * np.pi * np.cumsum(f_curve) / SR) * np.exp(-t * 42.0) * atk * 0.72


def _thud(rng: np.random.Generator, f0: float = 68.0, dur: float = 0.34) -> np.ndarray:
    n = max(16, int(dur * SR))
    t = _t(n)
    f_curve = f0 * (1.0 + 1.6 * np.exp(-t * 28.0))
    atk = np.minimum(1.0, t / 0.002)
    tone = np.sin(2.0 * np.pi * np.cumsum(f_curve) / SR) * np.exp(-t * 11.0)
    trans = _lp(rng.standard_normal(n), 850.0) * np.exp(-t * 38.0) * 0.45
    return (tone + trans) * atk


def _chime(freq: float = 1567.98, dur: float = 0.75) -> np.ndarray:
    n = max(16, int(dur * SR))
    t = _t(n)
    atk = np.minimum(1.0, t / 0.004)
    harm = (
        np.sin(2.0 * np.pi * freq * t)
        + 0.42 * np.sin(2.0 * np.pi * freq * 2.005 * t) * np.exp(-t * 5.0)
        + 0.20 * np.sin(2.0 * np.pi * freq * 3.01 * t) * np.exp(-t * 9.0)
    )
    fade_tail = np.minimum(1.0, np.maximum(0.0, dur - t) / 0.04)
    return harm * np.exp(-t * 4.5) * atk * fade_tail * 0.45


def _sparkle_arpeggio() -> np.ndarray:
    out = np.zeros((int(0.85 * SR), 2), dtype=np.float64)
    for idx, f in enumerate([1318.5, 1568.0, 1975.5, 2637.0]):
        _place(out, _chime(f, 0.55), idx * 0.055, gain=0.45, pan=-0.3 + idx * 0.2)
    return out.mean(axis=1)


def _blade_ring(freq: float = 1020.0, dur: float = 0.68) -> np.ndarray:
    n = max(16, int(dur * SR))
    t = _t(n)
    atk = np.minimum(1.0, t / 0.002)
    partials = (
        np.sin(2.0 * np.pi * freq * t)
        + 0.55 * np.sin(2.0 * np.pi * freq * 1.49 * t) * np.exp(-t * 4.5)
        + 0.35 * np.sin(2.0 * np.pi * freq * 2.34 * t) * np.exp(-t * 8.0)
        + 0.20 * np.sin(2.0 * np.pi * freq * 3.81 * t) * np.exp(-t * 14.0)
    )
    fade_tail = np.minimum(1.0, np.maximum(0.0, dur - t) / 0.04)
    return partials * np.exp(-t * 5.2) * atk * fade_tail * 0.42


def _sword_draw(rng: np.random.Generator, dur: float = 0.34) -> np.ndarray:
    n = max(16, int(dur * SR))
    t = _t(n)
    scrape = _bp(rng.standard_normal(n), 2200.0, 6800.0) * np.sin(np.pi * np.clip(t / dur, 0.0, 1.0))
    tone = _blade_ring(2140.0, dur) * 0.38
    return scrape * 0.38 + tone


def _shield_clang(rng: np.random.Generator, dur: float = 0.45) -> np.ndarray:
    th = _thud(rng, 115.0, dur) * 0.65
    ring = _blade_ring(640.0, dur) * 0.75
    snap = _bp(rng.standard_normal(len(th)), 1200.0, 4200.0) * np.exp(-_t(len(th)) * 45.0) * 0.45
    return th + ring + snap


def _sand_thud(rng: np.random.Generator, dur: float = 0.40) -> np.ndarray:
    n = max(16, int(dur * SR))
    t = _t(n)
    low = _thud(rng, 58.0, dur) * 0.72
    grit = _bp(rng.standard_normal(n), 700.0, 3200.0) * np.exp(-t * 14.0) * 0.38
    return low + grit


def _coin_cascade(rng: np.random.Generator, dur: float = 0.56) -> np.ndarray:
    n = max(16, int(dur * SR))
    out = np.zeros(n, dtype=np.float64)
    for k in range(6):
        offset = int(k * 0.045 * SR)
        if offset >= n:
            break
        freq = 3200.0 + float(rng.uniform(-350.0, 650.0)) + k * 210.0
        seg = _chime(freq, min(0.28, (n - offset) / SR)) * (0.85 ** k)
        cnt = min(len(seg), n - offset)
        out[offset : offset + cnt] += seg[:cnt]
    return out * 0.68


def _tick(rng: np.random.Generator) -> np.ndarray:
    n = int(0.035 * SR)
    t = _t(n)
    atk = np.minimum(1.0, t / 0.0015)
    return (_hp(rng.standard_normal(n), 2800.0) * np.exp(-t * 190.0) * 0.55 + np.sin(2.0 * np.pi * 2200.0 * t) * np.exp(-t * 150.0) * 0.3) * atk


def _mechanical_click(rng: np.random.Generator) -> np.ndarray:
    n = int(0.065 * SR)
    t = _t(n)
    atk = np.minimum(1.0, t / 0.0015)
    c1 = np.sin(2.0 * np.pi * 1680.0 * t) * np.exp(-t * 120.0) * 0.45
    c2 = _bp(rng.standard_normal(n), 1800.0, 5200.0) * np.exp(-t * 140.0) * 0.40
    return (c1 + c2) * atk


def _pin_drop() -> np.ndarray:
    n = int(0.32 * SR)
    t = _t(n)
    atk = np.minimum(1.0, t / 0.002)
    f = 920.0 * (1.0 - 0.35 * np.exp(-t * 18.0))
    return (np.sin(2.0 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11.0) * 0.55 + _chime(1840.0, 0.32) * 0.4) * atk


def _riser(rng: np.random.Generator, dur: float = 0.68) -> np.ndarray:
    n = max(32, int(dur * SR))
    t = _t(n)
    env = (t / dur) ** 2.1
    f_curve = 180.0 + 880.0 * (t / dur) ** 1.7
    tone = np.sin(2.0 * np.pi * np.cumsum(f_curve) / SR) * 0.32
    air = _bp(rng.standard_normal(n), 400.0, 3200.0) * 0.42
    fade_end = np.minimum(1.0, np.maximum(0.0, dur - t) / 0.025)
    return (tone + air) * env * fade_end


def _step_gravel(rng: np.random.Generator) -> np.ndarray:
    n = int(0.18 * SR)
    t = _t(n)
    crunch = _bp(rng.standard_normal(n), 900.0, 4400.0) * np.exp(-t * 26.0) * 0.42
    body = _thud(rng, 88.0, 0.18) * 0.45
    return crunch + body


def _pluck_note(rng: np.random.Generator, midi_note: int, dur: float = 0.48) -> np.ndarray:
    freq = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
    n = max(32, int(dur * SR))
    period = max(4, int(round(SR / freq)))
    ring = rng.uniform(-1.0, 1.0, period)
    out = np.zeros(n, dtype=np.float64)
    for i in range(n):
        idx = i % period
        out[i] = ring[idx]
        ring[idx] = 0.497 * (ring[idx] + ring[(idx + 1) % period])
    t = _t(n)
    out = _bp(out, 140.0, 3600.0) * np.exp(-t * 5.2)
    atk = np.minimum(1.0, t / 0.002)
    out = out * atk
    pk = np.max(np.abs(out)) + 1e-9
    return out / pk


def _soft_pad_chord(midi_notes: List[int], dur: float) -> np.ndarray:
    n = max(16, int(dur * SR))
    t = _t(n)
    acc = np.zeros(n, dtype=np.float64)
    for m in midi_notes:
        f = 440.0 * (2.0 ** ((m - 69) / 12.0))
        acc += np.sin(2.0 * np.pi * f * t) + 0.35 * np.sin(2.0 * np.pi * f * 2.0 * t + 0.4)
    acc = _lp(acc / max(1, len(midi_notes)), 1200.0)
    fade_in = np.minimum(1.0, t / min(0.28, dur * 0.45))
    fade_out = np.minimum(1.0, np.maximum(0.0, dur - t) / min(0.32, dur * 0.45))
    return acc * fade_in * fade_out * 0.35


def _glass_tap(rng: np.random.Generator) -> np.ndarray:
    n = int(0.09 * SR)
    t = _t(n)
    atk = np.minimum(1.0, t / 0.0012)
    tone = np.sin(2.0 * np.pi * 1580.0 * t) * np.exp(-t * 68.0) * 0.50
    ping = np.sin(2.0 * np.pi * 2940.0 * t) * np.exp(-t * 95.0) * 0.32
    click = _bp(rng.standard_normal(n), 2200.0, 6200.0) * np.exp(-t * 150.0) * 0.25
    return (tone + ping + click) * atk


def _electric_crackle(rng: np.random.Generator, dur: float = 0.28) -> np.ndarray:
    n = max(32, int(dur * SR))
    t = _t(n)
    bursts = np.zeros(n, dtype=np.float64)
    for k in range(5):
        pos = int((0.02 + k * 0.045) * SR)
        if pos >= n - 40:
            break
        ln = min(int(0.018 * SR), n - pos)
        sub_t = np.arange(ln) / SR
        bursts[pos : pos + ln] += (
            _bp(rng.standard_normal(ln), 3200.0, 8200.0) * np.exp(-sub_t * 140.0) * (0.75 + 0.25 * (k % 2))
        )
    buzz = np.sin(2.0 * np.pi * 120.0 * t) * np.exp(-t * 7.5) * 0.14
    env = np.minimum(1.0, t / 0.003) * np.minimum(1.0, np.maximum(0.0, dur - t) / 0.03)
    return (bursts + buzz) * env


def _subsea_bubble(rng: np.random.Generator, dur: float = 0.38) -> np.ndarray:
    n = max(32, int(dur * SR))
    out = np.zeros(n, dtype=np.float64)
    for k, off in enumerate((0.0, 0.09, 0.19)):
        pos = int(off * SR)
        ln = min(int(0.11 * SR), n - pos)
        if ln <= 16:
            break
        st = np.arange(ln) / SR
        f0 = 320.0 + k * 140.0
        freq = f0 * (1.0 + 1.45 * (st / max(0.05, ln / SR)))
        sig = np.sin(2.0 * np.pi * np.cumsum(freq) / SR) * np.exp(-st * 26.0) * np.minimum(1.0, st / 0.003)
        out[pos : pos + ln] += sig * 0.42
    rumble = _bp(rng.standard_normal(n), 75.0, 260.0) * np.exp(-_t(n) * 4.5) * 0.22
    return out + rumble


def _cosmic_swell(rng: np.random.Generator, dur: float = 0.78) -> np.ndarray:
    n = max(32, int(dur * SR))
    t = _t(n)
    f = 62.0 + 48.0 * (t / dur)
    sub = np.sin(2.0 * np.pi * np.cumsum(f) / SR) * 0.38 + np.sin(2.0 * np.pi * np.cumsum(f * 1.5) / SR) * 0.18
    shimmer = _bp(rng.standard_normal(n), 800.0, 2400.0) * 0.16
    env = np.sin(np.pi * np.minimum(1.0, t / dur)) ** 1.3
    return (sub + shimmer) * env


def _elevator_button_click(rng: np.random.Generator) -> np.ndarray:
    """Crisp tactile microswitch press + subtle illuminated confirmation ping."""
    n = int(0.11 * SR)
    t = _t(n)
    atk = np.minimum(1.0, t / 0.0008)
    snap = _bp(rng.standard_normal(n), 1800.0, 5600.0) * np.exp(-t * 165.0) * 0.55
    body = np.sin(2.0 * np.pi * 640.0 * t) * np.exp(-t * 72.0) * 0.42
    ring = np.sin(2.0 * np.pi * 1920.0 * t) * np.exp(-t * 48.0) * 0.28
    return (snap + body + ring) * atk


def _relay_cabinet_click(rng: np.random.Generator) -> np.ndarray:
    """Metallic electromagnetic contactor snap inside control cabinet."""
    n = int(0.14 * SR)
    t = _t(n)
    atk = np.minimum(1.0, t / 0.001)
    latch = _bp(rng.standard_normal(n), 1100.0, 4200.0) * np.exp(-t * 95.0) * 0.55
    coil = np.sin(2.0 * np.pi * 420.0 * t) * np.exp(-t * 58.0) * 0.38
    hum = np.sin(2.0 * np.pi * 120.0 * t) * np.exp(-t * 18.0) * 0.22
    return (latch + coil + hum) * atk


def _motor_drive_hum(rng: np.random.Generator, dur: float = 0.52) -> np.ndarray:
    """Traction motor rotor engage + electromagnetic stator hum."""
    n = max(32, int(dur * SR))
    t = _t(n)
    atk = np.minimum(1.0, t / 0.002)
    engage = _bp(rng.standard_normal(n), 500.0, 2200.0) * np.exp(-t * 55.0) * 0.36
    freq = 92.0 + 36.0 * np.sin(np.pi * np.minimum(1.0, t / dur))
    motor = np.sin(2.0 * np.pi * np.cumsum(freq) / SR) * 0.42 + np.sin(2.0 * np.pi * np.cumsum(freq * 3.0) / SR) * 0.16
    env = np.minimum(1.0, np.maximum(0.0, dur - t) / 0.08)
    return (engage + motor * 0.72) * atk * env


def _sheave_cable_whir(rng: np.random.Generator, dur: float = 0.44) -> np.ndarray:
    """Steel traction cables rolling smoothly across grooved drive sheave."""
    n = max(32, int(dur * SR))
    t = _t(n)
    atk = np.minimum(1.0, t / 0.002)
    pulley_tick = _bp(rng.standard_normal(n), 1600.0, 4800.0) * np.exp(-t * 70.0) * 0.35
    whir = _bp(rng.standard_normal(n), 280.0, 1450.0) * 0.32 * (0.65 + 0.35 * np.sin(2.0 * np.pi * 6.0 * t))
    tone = np.sin(2.0 * np.pi * 240.0 * t) * 0.18
    env = np.minimum(1.0, np.maximum(0.0, dur - t) / 0.06)
    return (pulley_tick + whir + tone) * atk * env


def _door_slide_open(rng: np.random.Generator, dur: float = 0.42) -> np.ndarray:
    """Pneumatic door latch release and brushed steel track glide."""
    n = max(32, int(dur * SR))
    t = _t(n)
    atk = np.minimum(1.0, t / 0.0015)
    unlatch = _bp(rng.standard_normal(n), 950.0, 3400.0) * np.exp(-t * 64.0) * 0.48
    slide = _bp(rng.standard_normal(n), 180.0, 920.0) * np.exp(-t * 5.2) * 0.35
    env = np.minimum(1.0, np.maximum(0.0, dur - t) / 0.05)
    return (unlatch + slide) * atk * env


def _elevator_arrival_chime(freq: float = 880.0, dur: float = 0.62) -> np.ndarray:
    """Warm two-tone harmonic elevator arrival chime (E5 -> A5)."""
    n = max(32, int(dur * SR))
    t = _t(n)
    atk1 = np.minimum(1.0, t / 0.0015)
    note1 = np.sin(2.0 * np.pi * (freq * 0.75) * t) * np.exp(-t * 6.5) * 0.45 * atk1
    shift = np.maximum(0.0, t - 0.14)
    active2 = (t >= 0.14).astype(np.float64) * np.minimum(1.0, shift / 0.0015)
    note2 = np.sin(2.0 * np.pi * freq * shift) * np.exp(-shift * 4.8) * 0.52 * active2
    return note1 + note2


def _ui_pop_soft(rng: np.random.Generator, base_hz: float = 520.0) -> np.ndarray:
    """Warm non-fatiguing editorial pop with subtle seeded harmonic variation."""
    n = int(0.08 * SR)
    t = _t(n)
    detune = 1.0 + rng.uniform(-0.045, 0.045)
    f0 = base_hz * detune
    atk = np.minimum(1.0, t / 0.002)
    env = np.exp(-t * 48.0) * atk
    sweep = np.sin(2.0 * np.pi * (f0 * (1.0 + 0.18 * np.exp(-t * 60.0))) * t)
    warm = 0.35 * np.sin(2.0 * np.pi * (f0 * 0.5) * t)
    return _lp((sweep * 0.72 + warm) * env, 2600.0)


def _marker_ring_draw(rng: np.random.Generator, dur: float = 0.16) -> np.ndarray:
    """Delicate vector marker arc draw + restrained harmonic ping for focus rings."""
    n = max(64, int(dur * SR))
    t = _t(n)
    atk = np.minimum(1.0, t / 0.004)
    fade = np.minimum(1.0, np.maximum(0.0, dur - t) / 0.04)
    glide = _bp(rng.standard_normal(n), 950.0, 2900.0) * np.exp(-t * 14.0) * 0.28
    tone_hz = 1120.0 * (1.0 + rng.uniform(-0.03, 0.03))
    shimmer = np.sin(2.0 * np.pi * tone_hz * t) * np.exp(-t * 22.0) * 0.34
    return (glide + shimmer) * atk * fade


def _arrow_swish(rng: np.random.Generator, dur: float = 0.15) -> np.ndarray:
    """Silky low-hiss vector leader-arrow swish synced to tracked label entrances."""
    n = max(64, int(dur * SR))
    t = _t(n)
    u = t / dur
    env = np.sin(np.pi * np.minimum(1.0, u)) ** 1.6
    noise = _bp(rng.standard_normal(n), 380.0, 2100.0)
    body = 0.16 * np.sin(2.0 * np.pi * (260.0 + 180.0 * u) * t)
    return (noise * 0.45 + body) * env


def _reveal_soft(rng: np.random.Generator, dur: float = 0.34) -> np.ndarray:
    """Warm clean chordal bloom for multi-layer cutaway reveals and verified counters."""
    n = max(64, int(dur * SR))
    t = _t(n)
    atk = np.minimum(1.0, t / 0.008)
    env = np.exp(-t * 6.5) * atk
    f0 = 587.33 * (1.0 + rng.uniform(-0.02, 0.02))
    c = (
        0.48 * np.sin(2.0 * np.pi * f0 * t)
        + 0.32 * np.sin(2.0 * np.pi * (f0 * 1.25) * t)
        + 0.24 * np.sin(2.0 * np.pi * (f0 * 1.50) * t)
    )
    return _lp(c * env, 4200.0)


def _low_sting(rng: np.random.Generator, dur: float = 0.32) -> np.ndarray:
    """Controlled chest-warmth contrast sting for failure / structural alert beats."""
    n = max(64, int(dur * SR))
    t = _t(n)
    atk = np.minimum(1.0, t / 0.004)
    freq = 62.0 - 16.0 * np.minimum(1.0, t / dur)
    sub = np.sin(2.0 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 7.2) * 0.65
    click = _bp(rng.standard_normal(n), 420.0, 1400.0) * np.exp(-t * 44.0) * 0.26
    return (sub + click) * atk


def _airflow_hiss(rng: np.random.Generator, dur: float = 0.48) -> np.ndarray:
    """Smooth aerodynamic bleed/Equalization vent hush without fatiguing high-end hiss."""
    n = max(64, int(dur * SR))
    t = _t(n)
    u = t / dur
    env = np.sin(np.pi * np.minimum(1.0, u)) ** 1.3
    air = _bp(rng.standard_normal(n), 420.0, 2350.0) * 0.42
    whistle = 0.10 * np.sin(2.0 * np.pi * (740.0 + 120.0 * np.sin(np.pi * u)) * t)
    return (air + whistle) * env
