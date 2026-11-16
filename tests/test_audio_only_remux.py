"""Regression Tests for Lossless `--audio-only` Remix, Picture Packet Invariance & Failure Rollback."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from director.edit_timeline import compute_video_stream_digest, remix_existing_video_audio
from director.run import execute_short_director_run


class TestAudioOnlyRemux(unittest.TestCase):
    def _build_synthetic_completed_run(self, run_dir: Path) -> None:
        (run_dir / "audio").mkdir(parents=True, exist_ok=True)
        (run_dir / "logs").mkdir(parents=True, exist_ok=True)
        sr = 44100
        t = np.arange(int(sr * 5.0), dtype=np.float32) / sr
        vo = 0.25 * np.sin(2 * np.pi * 240.0 * t)
        vo_p = run_dir / "audio" / "vo.wav"
        sf.write(str(vo_p), vo, sr)

        for name, res in (("preview_1080.mp4", "270x480"), ("final_4k.mp4", "540x960")):
            subprocess.run([
                "ffmpeg", "-v", "error", "-y",
                "-f", "lavfi", "-i", f"testsrc=size={res}:rate=30:duration=5.0",
                "-i", str(vo_p),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest",
                str(run_dir / name),
            ], check=True)

        (run_dir / "audio" / "lines.json").write_text(json.dumps([
            {"index": 0, "text": "Step one.", "start": 0.0, "end": 2.4, "duration": 2.4},
            {"index": 1, "text": "Step two.", "start": 2.5, "end": 5.0, "duration": 2.5},
        ]), encoding="utf-8")
        (run_dir / "audio" / "words.json").write_text(json.dumps([
            {"w": "Step", "s": 0.1, "e": 0.5, "line": 0},
            {"w": "one.", "s": 0.5, "e": 1.2, "line": 0},
            {"w": "Step", "s": 2.6, "e": 3.0, "line": 1},
            {"w": "two.", "s": 3.0, "e": 3.8, "line": 1},
        ]), encoding="utf-8")
        (run_dir / "style_decisions.json").write_text(json.dumps({
            "selection_mode": "explicit", "selected_skill": "stick-figure", "origin_skills": ["stick-figure"],
            "style_lock": {"enabled": True, "engine": "stick-figure", "mixing_policy": "forbidden", "fallback_policy": "fail-closed"},
        }), encoding="utf-8")
        (run_dir / "style_lock_audit.json").write_text(json.dumps({"status": "PASS", "violations": []}), encoding="utf-8")
        (run_dir / "storyboard.json").write_text(json.dumps({
            "selected_skill": "stick-figure", "origin_skills": ["stick-figure"], "fps": 30, "total_duration_sec": 5.0,
            "entities_and_facts": {"detected_motifs": ["clock"]},
            "shots": [
                {"shot_id": "shot_00", "index": 0, "engine": "stick-figure", "beat_role": "hook", "narration_text": "Step one.", "start": 0.0, "end": 2.5, "duration": 2.5, "setup_type": "hook_dynamic_cu", "novel_non_template": False, "camera": {"movement": "push_in"}, "staging": {"visual_metaphor": "clock", "secondary_prop": "clock"}, "transition_out": "whip"},
                {"shot_id": "shot_01", "index": 1, "engine": "stick-figure", "beat_role": "payoff", "narration_text": "Step two.", "start": 2.5, "end": 5.0, "duration": 2.5, "setup_type": "payoff_sunny_pullback", "novel_non_template": False, "camera": {"movement": "pull_back"}, "staging": {"visual_metaphor": "clock", "secondary_prop": "clock"}, "transition_out": "cut"},
            ],
        }), encoding="utf-8")

    def test_a16_a17_audio_only_preserves_video_packets_and_rolls_back_on_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "remix_case"
            self._build_synthetic_completed_run(run_dir)

            md5_4k_before = compute_video_stream_digest(run_dir / "final_4k.mp4")
            md5_prev_before = compute_video_stream_digest(run_dir / "preview_1080.mp4")

            # A16 + B5: Run full `--audio-only` remix changing music gain
            manifest = execute_short_director_run(
                raw_prompt="",
                out_dir=run_dir,
                cli_skill="stick-figure",
                audio_only=True,
                music_gain_db=-6.0,
                sfx_density="detailed",
            )
            self.assertTrue(manifest["audio_only_remix"])
            self.assertTrue(manifest["video_packets_unchanged"])
            self.assertEqual(manifest["video_packet_md5_4k"], md5_4k_before)
            self.assertEqual(manifest["video_packet_md5_preview"], md5_prev_before)
            self.assertIn(manifest["audio"]["audio_qc_status"], ("PASS", "WARN"))

            # A17: Failed candidate QC inside remix_existing_video_audio MUST NOT overwrite original MP4!
            orig_bytes = (run_dir / "final_4k.mp4").read_bytes()
            sb = json.loads((run_dir / "storyboard.json").read_text(encoding="utf-8"))
            with self.assertRaises(RuntimeError):
                remix_existing_video_audio(
                    run_dir=run_dir,
                    storyboard=sb,
                    audio_info={"mix_wav_path": str(run_dir / "audio" / "mix.wav"), "already_mastered": True},
                    verify_candidate_fn=lambda _p, _k: (False, "simulated_qc_failure"),
                )
            self.assertEqual((run_dir / "final_4k.mp4").read_bytes(), orig_bytes)
            self.assertFalse((run_dir / "tmp").exists())


if __name__ == "__main__":
    unittest.main()
