"""End-to-End Integration Smoke Tests for SD-AUDIO-01 (B1, B2, B4, B5, B6)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from director.audio_catalog import compute_file_sha256
from director.audio_narrative import analyze_audio_beats
from director.edit_timeline import compute_video_stream_digest
from director.run import execute_short_director_run


def _write_wav(path: Path, sr: int = 48000, dur: float = 2.0, freq: float = 260.0, channels: int = 2) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(sr * dur), dtype=np.float32) / sr
    sig = 0.28 * np.sin(2.0 * np.pi * freq * t) * (0.7 + 0.3 * np.sin(2.0 * np.pi * 2.0 * t))
    data = np.stack([sig, sig * 0.92], axis=1) if channels == 2 else sig
    sf.write(str(path), data, sr)
    return compute_file_sha256(path)


def _snapshot_tree(root: Path) -> dict[str, tuple[str, int]]:
    snap: dict[str, tuple[str, int]] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            snap[str(p.relative_to(root))] = (compute_file_sha256(p), p.stat().st_mtime_ns)
    return snap


class TestAudioIntegrationSmoke(unittest.TestCase):
    def test_b1_stick_figure_e2e_4k_and_b5_b6_audio_only_remix(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "sf_demo"
            prompt = (
                "A stick warrior draws a bright sword on cold stone. "
                "Suddenly a clock ticks faster before a shield clang sparks triumph."
            )
            manifest = execute_short_director_run(
                raw_prompt=prompt,
                out_dir=out_dir,
                cli_skill="stick-figure",
                fps=30,
                seed=42,
                lang="en",
                render_4k_mode="native",
            )

            self.assertEqual(manifest["selected_skill"], "stick-figure")
            self.assertTrue(manifest["delivered"])
            prev_path = Path(manifest["artifacts"]["preview_1080_mp4"])
            fin_path = Path(manifest["artifacts"]["final_4k_mp4"])
            self.assertTrue(prev_path.exists())
            self.assertTrue(fin_path.exists())

            style_audit = json.loads((out_dir / "style_lock_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(style_audit["status"], "PASS", style_audit)

            qc = json.loads((out_dir / "qc_report.json").read_text(encoding="utf-8"))
            self.assertIn(qc["overall_status"], ("PASS", "WARN"), qc)
            self.assertEqual(qc["ffprobe_final_4k"]["width"], 2160)
            self.assertEqual(qc["ffprobe_final_4k"]["height"], 3840)

            aqc = json.loads((out_dir / "audio" / "audio_qc_report.json").read_text(encoding="utf-8"))
            self.assertIn(aqc["overall_status"], ("PASS", "WARN"), aqc)
            self.assertEqual(aqc["subjective_editorial_listening"], "NOT_VERIFIED")
            self.assertTrue((out_dir / "audio" / "audio_plan.json").exists())
            self.assertTrue((out_dir / "audio" / "music_cue_sheet.json").exists())
            self.assertTrue((out_dir / "audio" / "sfx_cue_sheet.json").exists())
            self.assertTrue((out_dir / "audio" / "audio_asset_manifest.json").exists())
            self.assertTrue((out_dir / "audio" / "credits_audio.txt").exists())
            for stem in ("voice.wav", "music.wav", "sfx.wav", "ambience.wav", "mix.wav"):
                self.assertTrue((out_dir / "audio" / stem).exists(), f"Missing stem {stem}")

            mix_rep = json.loads((out_dir / "audio" / "audio_mix_report.json").read_text(encoding="utf-8"))
            self.assertTrue(mix_rep["already_mastered"])

            # B5 / B6: Lossless video copy `--audio-only` remix preserving video stream packet digest
            dig_prev_before = compute_video_stream_digest(prev_path)
            dig_fin_before = compute_video_stream_digest(fin_path)

            remix_manifest = execute_short_director_run(
                raw_prompt="",
                out_dir=out_dir,
                audio_only=True,
                sfx_density="detailed",
                music_intensity="high",
                preserve_original_on_remix=True,
            )
            self.assertTrue(remix_manifest["audio_only_remix"])
            self.assertTrue(remix_manifest["video_packets_unchanged"])
            remixed_prev = Path(remix_manifest["artifacts"]["preview_1080_mp4"])
            remixed_fin = Path(remix_manifest["artifacts"]["final_4k_mp4"])
            self.assertEqual(remixed_prev.name, "preview_1080_remixed.mp4")
            self.assertEqual(remixed_fin.name, "final_4k_remixed.mp4")
            self.assertTrue(remixed_prev.exists())
            self.assertTrue(remixed_fin.exists())
            self.assertEqual(compute_video_stream_digest(remixed_prev), dig_prev_before)
            self.assertEqual(compute_video_stream_digest(remixed_fin), dig_fin_before)
            self.assertEqual(compute_video_stream_digest(prev_path), dig_prev_before)
            self.assertEqual(compute_video_stream_digest(fin_path), dig_fin_before)

            remix_aqc = json.loads((out_dir / "audio" / "audio_qc_report.json").read_text(encoding="utf-8"))
            self.assertIn(remix_aqc["overall_status"], ("PASS", "WARN"), remix_aqc)

    def test_b4_qa_readonly_ccby_attribution_and_unlicensed_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            qa_root = Path(td) / "QA_ReadOnly_Fixture"
            fog = qa_root / "audio" / "music" / "external_dark_fog.wav"
            step = qa_root / "audio" / "real_sfx" / "external_sword_blade.wav"
            unlic = qa_root / "audio" / "real_sfx" / "rogue_unlicensed.wav"

            sha_fog = _write_wav(fog, sr=44100, dur=3.5, freq=185.0, channels=2)
            sha_step = _write_wav(step, sr=44100, dur=0.45, freq=980.0, channels=1)
            _ = _write_wav(unlic, sr=48000, dur=0.4, freq=500.0, channels=1)

            lic_dir = qa_root / "audio" / "licenses"
            lic_dir.mkdir(parents=True)
            k_credit = (
                '"Dark Fog" Kevin MacLeod (incompetech.com) Licensed under Creative Commons: '
                "By Attribution 4.0 License http://creativecommons.org/licenses/by/4.0/"
            )
            (lic_dir / "licenses.json").write_text(json.dumps({
                "assets": [
                    {
                        "filename": "external_dark_fog.wav",
                        "license_type": "cc-by-4.0",
                        "author": "Kevin MacLeod",
                        "title": "Dark Fog",
                        "source_url": "https://incompetech.com",
                        "license_url": "http://creativecommons.org/licenses/by/4.0/",
                        "commercial_use_allowed": True,
                        "attribution_required": True,
                        "attribution_text": k_credit,
                        "sha256": sha_fog,
                    },
                    {
                        "filename": "external_sword_blade.wav",
                        "license_type": "cc0",
                        "author": "Freesound CC0 Author",
                        "title": "Sword Blade Clang",
                        "source_url": "https://freesound.org",
                        "commercial_use_allowed": True,
                        "attribution_required": False,
                        "sha256": sha_step,
                    },
                ]
            }), encoding="utf-8")

            snap_before = _snapshot_tree(qa_root)
            out_dir = Path(td) / "qa_run"
            prompt = (
                "Inside the shadowy stone arena, tension builds as blades meet in silent danger. "
                "The duel decides who walks out alive."
            )
            manifest = execute_short_director_run(
                raw_prompt=prompt,
                out_dir=out_dir,
                cli_skill="stick-figure",
                fps=30,
                seed=77,
                render_4k_mode="preview",
                qa_audio_root=qa_root,
                music_mode="qa-library",
                sfx_mode="auto",
            )

            self.assertEqual(manifest["qa_audio_root_status"], "QA_LIBRARY_MOUNTED_READONLY")
            aqc = json.loads((out_dir / "audio" / "audio_qc_report.json").read_text(encoding="utf-8"))
            self.assertIn(aqc["overall_status"], ("PASS", "WARN"), aqc)

            asset_manifest = json.loads((out_dir / "audio" / "audio_asset_manifest.json").read_text(encoding="utf-8"))
            used_records = [a for a in asset_manifest.get("assets", []) if a.get("selected_uses")]
            used_shas = {a.get("sha256") for a in used_records}
            self.assertIn(sha_fog, used_shas, asset_manifest)
            used_ids = {a.get("asset_id") for a in used_records}
            self.assertFalse(any("rogue_unlicensed" in str(i) for i in used_ids))

            credits_text = (out_dir / "audio" / "credits_audio.txt").read_text(encoding="utf-8")
            self.assertIn("Kevin MacLeod", credits_text)
            self.assertIn("creativecommons.org/licenses/by/4.0/", credits_text)

            # Strictly read-only guarantee: QA tree hashes and timestamps unchanged
            self.assertEqual(_snapshot_tree(qa_root), snap_before)

    def test_b2_minimalistic_graphics_e2e_and_analyze_audio_beats(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "mg_demo"
            prompt = (
                "Clean geometric triangles align in calm balance. "
                "Suddenly a bright center point highlights the insight."
            )
            manifest = execute_short_director_run(
                raw_prompt=prompt,
                out_dir=out_dir,
                cli_skill="minimalistic-graphics",
                fps=30,
                seed=19,
                render_4k_mode="preview",
            )
            self.assertEqual(manifest["selected_skill"], "minimalistic-graphics")
            aqc = json.loads((out_dir / "audio" / "audio_qc_report.json").read_text(encoding="utf-8"))
            self.assertIn(aqc["overall_status"], ("PASS", "WARN"), aqc)

            # Verify analyze_audio_beats works cleanly without requiring run_dir
            sd = json.loads((out_dir / "style_decisions.json").read_text(encoding="utf-8"))
            sentences = json.loads((out_dir / "script.json").read_text(encoding="utf-8"))
            sb = json.loads((out_dir / "storyboard.json").read_text(encoding="utf-8"))
            parsed_stub = {
                "beats": sentences,
                "entities_and_facts": sb.get("entities_and_facts", {}),
                "voice": {"words": []},
            }
            plan = analyze_audio_beats(parsed_stub, sb)
            self.assertEqual(plan["selected_skill"], "minimalistic-graphics")
            self.assertEqual(plan["ambience"]["generator_name"], "minimal_quiet")
            self.assertGreaterEqual(len(plan["music"]["segments"]), 1)
            self.assertEqual(sd["selected_skill"], "minimalistic-graphics")


if __name__ == "__main__":
    unittest.main()
