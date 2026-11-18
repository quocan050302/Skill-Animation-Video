"""SD-RETENTION-04.R2 Negative Tests N51-N55: Visual Quality, Pacing, Info-Gain Separation & Honesty."""

from __future__ import annotations

import json
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from director.action_camera_director import score_camera_information_gain
from director.build_storyboard import build_storyboard_and_bible
from director.parse_script import parse_script_and_build_voice
from director.preflight import run_preflight
from director.retention_qa import compare_ab_versions
from director.route_styles import route_and_lock_style
from director.semantic_visual_evidence_qa import (
    audit_editorial_pacing,
    build_observed_evidence_report,
    run_semantic_visual_evidence_qa,
)

ROOT = Path(__file__).resolve().parents[1]
KIT_DIR = ROOT / "vendor" / "claude-animation-skills" / "kit"


def _write_tone_wav(p: Path, hz: float = 220.0) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    sr = 24000
    n = int(sr * 1.0)
    t = np.arange(n, dtype=np.float64) / sr
    pcm = (np.sin(2.0 * np.pi * hz * t) * 10000.0).astype(np.int16)
    with wave.open(str(p), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


class TestSdRetention04R2VisualQuality(unittest.TestCase):
    def test_n51_london_r2_has_zero_repeated_setups_or_generators(self) -> None:
        pf = run_preflight(ROOT, selected_skill="zach-d-films", lang="en")
        london_txt = (
            "At noon on December 5, 1952, London's busy streets turned dark as midnight under toxic smog. "
            "Freezing weather drove coal fireplaces and power plants to burn cheap soft coal nonstop. "
            "Dense sulfur emissions poured upward from brick chimneys into chilly winter air. "
            "Then a warm temperature inversion slid overhead like a lid trapping smoke below. "
            "Vertical mixing stalled completely so trapped clouds spread sideways across rooftops. "
            "Visibility dropped near zero while red double-decker buses crawled behind conductors holding lanterns. "
            "Citizens coughed through five days of acidic fog, leaving an estimated 4,000 excess deaths that month. "
            "Four years later Parliament passed the 1956 Clean Air Act pushing a shift toward smokeless heating."
        )
        style, cleaned, _ = route_and_lock_style(ROOT, f"/short-director --skill zach-d-films {london_txt}", cli_skill="zach-d-films", upstream_sha=pf.upstream_sha)
        r1_vo = ROOT / "runs" / "sd_retention04_london_smog_20261118_0233Z" / "enhanced_B" / "audio" / "vo.wav"
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            parsed = parse_script_and_build_voice(
                cleaned,
                selected_skill="zach-d-films",
                run_dir=tmp,
                kit_dir=KIT_DIR,
                lang="en",
                user_voice_file=r1_vo if r1_vo.exists() else None,
                voice_mode="auto" if r1_vo.exists() else "off",
            )
            sb = build_storyboard_and_bible(
                parsed_script=parsed,
                style_decisions=style,
                run_dir=tmp,
                fps=30,
                seed=42,
                edit_energy="dynamic",
                scene_novelty="high",
                max_static_hold_sec=6.0 if not r1_vo.exists() else 4.5,
                caption_mode="kinetic",
                callout_mode="smart",
                editorial_theme="role-aware",
            )
            setups = [s.get("setup_type") for s in sb["shots"]]
            gens = [s.get("procedural_generator") for s in sb["shots"]]
            self.assertGreaterEqual(len(set(gens)), 7, f"Expected >=7 distinct London R2 generators, got {gens}")
            for idx in range(len(setups) - 1):
                self.assertNotEqual(setups[idx], setups[idx + 1], f"N51: Consecutive repeated setup at idx {idx}: {setups}")

    def test_n52_pacing_warns_above_4s_and_fails_above_5s_idle(self) -> None:
        sb_warn = {
            "shots": [
                {"shot_id": "s0", "start": 0.0, "end": 2.2, "setup_type": "a", "procedural_generator": "g1", "physical_action": "x"},
                {"shot_id": "s1", "start": 2.2, "end": 4.4, "setup_type": "a", "procedural_generator": "g1", "physical_action": "x"},
            ]
        }
        p_warn = audit_editorial_pacing(sb_warn)
        self.assertEqual(p_warn["status"], "WARN")
        self.assertGreater(p_warn["max_idle_run_sec"], 4.0)

        sb_fail = {
            "shots": [
                {"shot_id": "s0", "start": 0.0, "end": 5.4, "setup_type": "a", "procedural_generator": "g1", "physical_action": "same"},
            ]
        }
        traces_flat = [{"shot_id": "s0", "time": 1.0, "telemetry": {"physical_motion": {"vertex_disp_max_m": 0.0}}}]
        p_fail = audit_editorial_pacing(sb_fail, raw_traces=traces_flat)
        self.assertEqual(p_fail["status"], "FAIL")
        self.assertTrue(any("N43" in i for i in p_fail["issues"]))

    def test_n53_separates_planning_heuristic_from_observed_proof_gain(self) -> None:
        cand = {"framing": "CU", "movement": "orbit", "scene_family": "volcano", "physical_action": "cutaway", "staging": {"salient_action_anchor": "cryptodome"}}
        ig = score_camera_information_gain(cand)
        self.assertIn("planned_camera_info_gain", ig)
        self.assertTrue(ig["is_planning_heuristic"])
        self.assertEqual(ig["metric_authority"], "PLANNING_HEURISTIC_NOT_DECODED_PROOF")

        # High planned score (0.95) with zero decoded pixel delta yields near-zero observed_proof_gain
        rep = build_observed_evidence_report(
            claim_cov={"claims": [{"causal_event_id": "cev_0", "shot_id": "shot_00", "frame_mad_before_action_or_after": 0.0, "matte_role_ratio": 0.0, "status": "FAIL"}]},
            storyboard={"shots": []},
            camera_intent_report={"planned_camera_info_gain": 0.95},
        )
        self.assertTrue(rep["metric_separation_enforced"])
        self.assertTrue(rep["planned_camera_info_gain"]["is_planning_heuristic"])
        self.assertEqual(rep["planned_camera_info_gain"]["mean"], 0.95)
        self.assertLess(rep["observed_proof_gain"]["mean"], 0.30)

    def test_n54_n55_ab_reuse_transparency_and_acceptance_classification(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            ra, rb, out = tmp / "A", tmp / "B", tmp / "ab"
            _write_tone_wav(ra / "audio" / "vo.wav", 330.0)
            _write_tone_wav(rb / "audio" / "vo.wav", 330.0)
            for rdir in (ra, rb):
                (rdir / "story_action_graph.json").write_text(json.dumps({"narrative_events": [{"narrative_event_id": "n0", "beat_id": "b0", "start_sec": 0.0, "end_sec": 1.0}]}), encoding="utf-8")
                (rdir / "audio" / "voice_delivery_report.json").write_text(json.dumps({"active_tts_backend": "windows_sapi", "summary_metrics": {}}), encoding="utf-8")
            ab = compare_ab_versions(ra, rb, out, reused_baseline_a=True, neural_voice_available=False, active_tts_backend="windows_sapi")
            self.assertEqual(ab["baseline_origin"], "REUSED_BASELINE")
            self.assertTrue(ab["reused_baseline_a"])
            self.assertFalse(ab["voice_backend_status"]["neural_voice_available"])
            self.assertEqual(ab["subjective_preference_status"], "NOT_VERIFIED")

            qa_run = tmp / "qa_run"
            qa_run.mkdir()
            gdoc = run_semantic_visual_evidence_qa(
                run_dir=qa_run,
                storyboard={"total_duration_sec": 2.0, "shots": [{"shot_id": "shot_00", "start": 0.0, "end": 2.0, "causal_event_id": "cev_00", "procedural_generator": "zach3d:london_fog_street_hook_stage"}]},
                causal_graph={"causal_events": [{"causal_event_id": "cev_00", "proof_type": "state_change_before_after"}]},
                evidence_contracts={"by_event_id": {"cev_00": {"expected_visible_consequence": {}}}},
                require_decoded_frames=False,
            )
            self.assertIn("ENGINE_TECHNICAL_PASS", gdoc)
            self.assertTrue(gdoc["DEMO_EDITORIAL_REVIEW_REQUIRED"])
            self.assertTrue(gdoc["HUMAN_VISUAL_REVIEW_REQUIRED"])
            self.assertEqual(gdoc["HUMAN_VISUAL_REVIEW_STATUS"], "NOT_VERIFIED")
            self.assertEqual(gdoc["HUMAN_AUDIO_REVIEW_STATUS"], "NOT_VERIFIED")
            self.assertFalse(gdoc["PRODUCTION_RELEASE_READY"])
            self.assertTrue((qa_run / "observed_evidence_report.json").exists())
            self.assertTrue((qa_run / "pacing_report.json").exists())


if __name__ == "__main__":
    unittest.main()
