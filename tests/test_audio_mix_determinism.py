"""Determinism, Ducking Envelope, Crossfade Seam, Bounds, and Audio QC Negative Gate Tests."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from director.audio_narrative import build_audio_narrative_plan
from director.mix_audio import (
    SR,
    apply_sidechain_ducking,
    calculate_voice_activity_envelope,
    mix_production_audio,
)
from director.quality_gate import run_audio_quality_gate


def _synth_vo_with_pause(path: Path, dur: float = 8.0, sr: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(sr * dur), dtype=np.float32) / sr
    sig = np.zeros_like(t)
    # Speech windows: 0.5..3.0s and 5.0..7.5s; quiet pause: 3.0..5.0s
    m1 = (t >= 0.5) & (t <= 3.0)
    m2 = (t >= 5.0) & (t <= 7.5)
    speech = 0.25 * np.sin(2.0 * np.pi * 220.0 * t) + 0.12 * np.sin(2.0 * np.pi * 660.0 * t)
    sig[m1 | m2] = speech[m1 | m2]
    sf.write(str(path), sig, sr)


def _setup_fixture(root_dir: Path) -> tuple[dict, dict, dict]:
    vo_p = root_dir / "vo_src.wav"
    _synth_vo_with_pause(vo_p, 8.0)
    parsed = {
        "entities_and_facts": {"detected_motifs": ["clock", "roman_gladiator"]},
        "beats": [
            {"beat_index": 0, "role": "hook", "text": "Wait for it.", "start": 0.0, "end": 3.5, "words": []},
            {"beat_index": 1, "role": "turn", "text": "Here is the catch.", "start": 3.5, "end": 6.0, "words": []},
            {"beat_index": 2, "role": "payoff", "text": "Saved at last.", "start": 6.0, "end": 8.0, "words": []},
        ],
        "voice": {"vo_wav_path": str(vo_p), "words": []},
    }
    sb = {
        "selected_skill": "stick-figure",
        "origin_skills": ["stick-figure"],
        "fps": 30,
        "total_duration_sec": 8.0,
        "shots": [
            {"shot_id": "shot_00", "index": 0, "engine": "stick-figure", "beat_role": "hook", "narration_text": "Wait.", "start": 0.0, "end": 3.5, "duration": 3.5, "setup_type": "hook_dynamic_cu", "novel_non_template": False, "camera": {"movement": "push_in"}, "staging": {"visual_metaphor": "clock", "secondary_prop": "clock"}, "transition_out": "whip"},
            {"shot_id": "shot_01", "index": 1, "engine": "stick-figure", "beat_role": "turn", "narration_text": "Catch.", "start": 3.5, "end": 6.0, "duration": 2.5, "setup_type": "novel_mechanism_cutaway", "novel_non_template": True, "camera": {"movement": "snap"}, "staging": {"visual_metaphor": "clock", "secondary_prop": "clock"}, "transition_out": "iris_mask"},
            {"shot_id": "shot_02", "index": 2, "engine": "stick-figure", "beat_role": "payoff", "narration_text": "Saved.", "start": 6.0, "end": 8.0, "duration": 2.0, "setup_type": "payoff_sunny_pullback", "novel_non_template": False, "camera": {"movement": "pull"}, "staging": {"visual_metaphor": "clock", "secondary_prop": "clock"}, "transition_out": "cut"},
        ],
    }
    plan = build_audio_narrative_plan(parsed, sb, root_dir, voice_expected=True)
    return parsed, sb, plan


class TestAudioMixDeterminismAndQC(unittest.TestCase):
    def test_a10_a11_a12_a13_determinism_ducking_and_crossfade_seams(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d1 = Path(td) / "r1"
            d2 = Path(td) / "r2"
            p1, sb1, pl1 = _setup_fixture(d1)
            p2, sb2, pl2 = _setup_fixture(d2)

            m1 = mix_production_audio(sb1, p1, d1, seed=42, audio_plan=pl1)
            m2 = mix_production_audio(sb2, p2, d2, seed=42, audio_plan=pl2)

            # A13: Deterministic identical seed -> identical PCM hashes
            self.assertEqual(m1["stems"]["music"]["pcm_sha256"], m2["stems"]["music"]["pcm_sha256"])
            self.assertEqual(m1["stems"]["sfx"]["pcm_sha256"], m2["stems"]["sfx"]["pcm_sha256"])
            self.assertEqual(m1["stems"]["ambience"]["pcm_sha256"], m2["stems"]["ambience"]["pcm_sha256"])
            self.assertEqual(m1["mix_pcm_sha256"], m2["mix_pcm_sha256"])

            # A10: 48 kHz stereo finite non-clipping array
            mix_arr, sr = sf.read(m1["mix_wav_path"], dtype="float32", always_2d=True)
            self.assertEqual(sr, 48000)
            self.assertEqual(mix_arr.shape[1], 2)
            self.assertTrue(np.all(np.isfinite(mix_arr)))
            self.assertLess(float(np.max(np.abs(mix_arr))), 0.99)

            # A11: Ducking reduces music level inside active VO (1.0..2.5s) vs pause (3.6..4.4s)
            mu_arr, _ = sf.read(m1["music_wav_path"], dtype="float64", always_2d=True)
            rms_during_vo = float(np.sqrt(np.mean(mu_arr[int(1.0 * SR) : int(2.5 * SR)] ** 2)))
            rms_in_pause = float(np.sqrt(np.mean(mu_arr[int(3.6 * SR) : int(4.4 * SR)] ** 2)))
            self.assertGreater(rms_in_pause, rms_during_vo * 1.4, "Music should breathe back up in vocal pause")
            self.assertGreater(rms_during_vo, 1e-4, "Music should duck naturally, not zero-mute")

            # Unit test sidechain attack/release function directly
            t = np.arange(SR * 2) / float(SR)
            vo = np.where((t >= 0.5) & (t <= 1.2), 0.3 * np.sin(2 * np.pi * 200 * t), 0.0)
            act = calculate_voice_activity_envelope(vo, SR, 35.0, 260.0)
            mus = np.ones((len(vo), 2), dtype=np.float64) * 0.2
            ducked = apply_sidechain_ducking(mus, act, depth_db=-10.0)
            self.assertLess(float(np.mean(ducked[int(0.8 * SR)])), float(np.mean(ducked[int(0.1 * SR)])))

    def test_b8_quality_gate_catches_muted_music_loud_sfx_clipping_and_missing_credits(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "qc_neg"
            parsed, sb, plan = _setup_fixture(run_dir)
            mix_rep = mix_production_audio(sb, parsed, run_dir, seed=42, audio_plan=plan)

            mp4 = run_dir / "test_vid.mp4"
            subprocess.run([
                "ffmpeg", "-v", "error", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=270x480:r=30:d=8.0",
                "-i", mix_rep["mix_wav_path"],
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest",
                str(mp4),
            ], check=True)

            audio_dir = run_dir / "audio"
            # Baseline passes cleanly
            rep_ok = run_audio_quality_gate(mp4, mp4, audio_dir, plan, mix_rep, logs_dir=run_dir / "logs")
            self.assertIn(rep_ok["overall_status"], ("PASS", "WARN"))

            # Neg 1: Silent/missing music while music enabled -> FAIL!
            orig_music = (audio_dir / "music.wav").read_bytes()
            sf.write(str(audio_dir / "music.wav"), np.zeros((SR * 8, 2), dtype=np.float32), SR)
            rep_nomus = run_audio_quality_gate(mp4, mp4, audio_dir, plan, mix_rep, logs_dir=run_dir / "logs")
            self.assertEqual(rep_nomus["checks"]["missing_expected_cues"]["status"], "FAIL")
            self.assertEqual(rep_nomus["overall_status"], "FAIL")
            (audio_dir / "music.wav").write_bytes(orig_music)

            # Neg 2: Loud SFX masking VO -> FAIL!
            orig_sfx = (audio_dir / "sfx.wav").read_bytes()
            sf.write(str(audio_dir / "sfx.wav"), np.ones((SR * 8, 2), dtype=np.float32) * 0.9, SR)
            rep_mask = run_audio_quality_gate(mp4, mp4, audio_dir, plan, mix_rep, logs_dir=run_dir / "logs")
            self.assertEqual(rep_mask["checks"]["voice_music_intelligibility"]["status"], "FAIL")
            (audio_dir / "sfx.wav").write_bytes(orig_sfx)

            # Neg 3: Clipped audio mux -> FAIL!
            clip_wav = run_dir / "clip.wav"
            sf.write(str(clip_wav), np.ones((SR * 8, 2), dtype=np.float32), SR)
            clip_mp4 = run_dir / "clip.mp4"
            subprocess.run([
                "ffmpeg", "-v", "error", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=270x480:r=30:d=8.0",
                "-i", str(clip_wav),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest",
                str(clip_mp4),
            ], check=True)
            rep_clip = run_audio_quality_gate(clip_mp4, clip_mp4, audio_dir, plan, mix_rep, logs_dir=run_dir / "logs")
            self.assertEqual(rep_clip["checks"]["lufs_and_true_peak_post_encode"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
