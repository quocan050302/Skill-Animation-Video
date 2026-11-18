"""SD-RETENTION-04.R1 Negative Traps (N01-N20), Causal Graph & Domain Generalization Tests."""

from __future__ import annotations

import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from director.build_storyboard import build_storyboard_and_bible
from director.parse_script import parse_script_and_build_voice
from director.preflight import run_preflight
from director.semantic_visual_evidence_qa import (
    audit_causal_transition_visibility,
    audit_claim_pointer_semantics,
    audit_relative_motion_evidence,
    audit_story_silent_comprehension_proxies,
    audit_visual_claim_coverage,
    run_semantic_visual_evidence_qa,
)
from director.visual_causality_director import (
    EVIDENCE_SUPPORTED,
    EVIDENCE_UNSUPPORTED,
    PHYSICS_VISUAL_APPROX,
    VALID_PROOF_TYPES,
    build_causal_event_graph,
    validate_world_state_conservation,
)
from director.visual_event_graph import extract_semantic_visual_events
from director.visual_storytelling_director import plan_story_action_graph, validate_narrative_causality
from director.visual_storytelling_qa import audit_historical_claims


ROOT = Path(__file__).resolve().parents[1]
KIT_DIR = ROOT / "vendor" / "claude-animation-skills" / "kit"


def _write_solid_test_mp4(out_mp4: Path, frames_rgb: list[tuple[int, int, int]], fps: int = 10) -> None:
    """Create tiny deterministic H264 MP4 from RGB color triples via ffmpeg."""
    pf = run_preflight(ROOT, selected_skill="zach-d-films", lang="en")
    tmp_dir = out_mp4.parent / "_tmp_frames"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for idx, rgb in enumerate(frames_rgb):
        im = Image.new("RGB", (270, 480), rgb)
        im.save(tmp_dir / f"f_{idx:04d}.png")
    cmd = [
        pf.ffmpeg_path, "-y", "-framerate", str(fps), "-i", str(tmp_dir / "f_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), str(out_mp4),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg test video failed: {res.stderr[-400:]}")


class TestSdRetention04CausalityAndTraps(unittest.TestCase):
    def _sample_causal_fixture(self, tmp: Path):
        raw_text = (
            "On December 5, 1952, London's midday streets disappeared into toxic fog. "
            "Millions of coal fireplaces and factories pumped sulfur smoke into cold air. "
            "A warm air temperature inversion acted like a lid and trapped the smog over the city. "
            "Visibility dropped to near zero as conductors walked ahead of buses with lanterns. "
            "Residents coughed and shielded their faces, leading to an estimated 4,000 excess deaths that month. "
            "The crisis led to the Clean Air Act of 1956, pushing a gradual shift toward smokeless fuel."
        )
        parsed = parse_script_and_build_voice(
            raw_text, selected_skill="zach-d-films", run_dir=tmp, kit_dir=KIT_DIR, voice_mode="off"
        )
        ev_graph = extract_semantic_visual_events(parsed, selected_skill="zach-d-films")
        story_graph = plan_story_action_graph(parsed, ev_graph, seed=42)
        bundle = build_causal_event_graph(ev_graph, story_graph, selected_skill="zach-d-films", run_dir=tmp)
        return parsed["sentences"], ev_graph, story_graph, bundle["causal_graph"], bundle["evidence_contracts"]

    def test_n01_n02_n05_frozen_pixels_and_missing_matte_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _, _, _, ceg, cec = self._sample_causal_fixture(tmp)
            dur_max = max(float(e["settle_sec"]) for e in ceg["causal_events"])
            n_frames = int(round((dur_max + 1.0) * 10))
            mp4 = tmp / "frozen.mp4"
            _write_solid_test_mp4(mp4, [(90, 90, 90)] * n_frames, fps=10)
            sb = {
                "total_duration_sec": dur_max,
                "shots": [
                    {
                        "shot_id": f"shot_{i:02d}",
                        "causal_event_id": ev["causal_event_id"],
                        "narrative_event_id": ev["narrative_event_id"],
                        "start": ev["onset_sec"],
                        "end": ev["settle_sec"],
                    }
                    for i, ev in enumerate(ceg["causal_events"])
                ],
            }
            cov = audit_visual_claim_coverage(ceg, cec, sb, video_mp4=mp4, require_decoded_frames=True)
            self.assertEqual(cov["status"], "FAIL")
            self.assertTrue(any("N01" in msg for msg in cov["issues"]))

            # N02: Varying RGB video paired with empty background matte (missing causal_feature pixels)
            mp4_dyn = tmp / "varying.mp4"
            frames = [((i * 17) % 240, (i * 29) % 240, (i * 7) % 240) for i in range(n_frames)]
            _write_solid_test_mp4(mp4_dyn, frames, fps=10)
            mattes_dir = tmp / "qa" / "mattes"
            mattes_dir.mkdir(parents=True, exist_ok=True)
            matte_frames = []
            for i, ev in enumerate(ceg["causal_events"]):
                t_m = ev["peak_sec"]
                mp = mattes_dir / f"m_{i}.png"
                Image.new("RGB", (270, 480), (40, 40, 40)).save(mp)  # pure environment only
                matte_frames.append({"t_sec": t_m, "matte_path": str(mp)})
            cov_m = audit_visual_claim_coverage(
                ceg, cec, sb, video_mp4=mp4_dyn, matte_manifest={"frames": matte_frames}, qa_dir=tmp / "qa"
            )
            self.assertEqual(cov_m["status"], "FAIL")
            self.assertTrue(any("N02" in msg for msg in cov_m["issues"]))

    def test_n03_world_state_conservation_and_n12_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            _, _, _, ceg, _ = self._sample_causal_fixture(Path(td))
            events = [dict(e) for e in ceg["causal_events"]]
            # N03: Force unmotivated drop in particulate_load without mitigation
            events[2]["state_transition_kind"] = "causal_progression"
            events[2]["is_flashback_transition"] = False
            events[2]["world_state_after"] = {**events[2]["world_state_after"], "particulate_load": 0.65}
            events[3]["state_transition_kind"] = "causal_progression"
            events[3]["is_flashback_transition"] = False
            events[3]["world_state_after"] = {**events[3]["world_state_after"], "particulate_load": 0.0}
            res = validate_world_state_conservation(events)
            self.assertEqual(res["status"], "FAIL")
            self.assertTrue(any("particulate_load" in v for v in res["violations"]))

            # N12: Self-loop causal edge & inverted parent timing
            bad_cycle = [dict(events[0]), dict(events[1])]
            bad_cycle[0]["cause_event_ids"] = [bad_cycle[0]["causal_event_id"]]
            bad_cycle[0]["onset_sec"] = 9.0
            bad_cycle[1]["onset_sec"] = 2.0
            res_cyc = validate_world_state_conservation(bad_cycle)
            self.assertEqual(res_cyc["status"], "FAIL")
            self.assertTrue(any("Self-loop" in v for v in res_cyc["violations"]))

    def test_n04_n06_fake_camera_motion_fails_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            _, _, _, ceg, _ = self._sample_causal_fixture(Path(td))
            ceg["causal_events"][1]["proof_type"] = "particle_path_propagation"
            ceg["causal_events"][3]["proof_type"] = "displacement_relative_to_fixed_reference"
            events = ceg["causal_events"]
            shots = [{"shot_id": f"shot_{i:02d}", "causal_event_id": e["causal_event_id"]} for i, e in enumerate(events)]
            traces = [
                {"shot_id": "shot_01", "telemetry": {"physical_motion": {"vertex_disp_max_m": 0.0}}},
                {"shot_id": "shot_03", "telemetry": {"physical_motion": {"vertex_disp_max_m": 0.0}}},
            ]
            rel = audit_relative_motion_evidence(ceg, {"shots": shots}, raw_traces=traces)
            self.assertEqual(rel["status"], "FAIL")
            self.assertTrue(any("N04/N06" in msg for msg in rel["issues"]))

    def test_n07_unsupported_claim_never_faked(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            ps = parse_script_and_build_voice(
                "An abstract jurisprudence debate shifted bond yield curve expectations. Another debate persisted.",
                selected_skill="zach-d-films",
                run_dir=tmp,
                kit_dir=KIT_DIR,
                voice_mode="off",
            )
            ev_g = extract_semantic_visual_events(ps, selected_skill="zach-d-films")
            out = build_causal_event_graph(ev_g, selected_skill="zach-d-films", require_supported=False)
            ev0 = out["causal_graph"]["causal_events"][0]
            self.assertEqual(ev0["evidence_status"], EVIDENCE_UNSUPPORTED)
            with self.assertRaises(ValueError):
                build_causal_event_graph(ev_g, selected_skill="zach-d-films", require_supported=True)

    def test_n08_n09_pointer_semantic_rejection_and_tip_error(self) -> None:
        ed_tl = {
            "overlays": [
                {
                    "overlay_id": "ov_00",
                    "shot_id": "shot_00",
                    "causal_event_id": "cev_000",
                    "narrative_claim_id": "claim_0",
                    "target_entity_id": "stage_center",
                    "target_feature_id": "stage_center",
                    "proof_target_id": "stage_center",
                    "semantic_region_of_change": "",
                    "why_this_overlay": "",
                    "pointer_shape": "impact_arrow",
                }
            ]
        }
        traces = [{"time": 1.0, "telemetry": {"overlay": {"overlays": [{"overlay_id": "ov_00", "visible": True, "alpha": 1.0, "tip_target_error_px": 54.0}]}}}]
        ptr_res = audit_claim_pointer_semantics(ed_tl, raw_traces=traces)
        self.assertEqual(ptr_res["status"], "FAIL")
        self.assertTrue(any("N08" in x for x in ptr_res["issues"]))
        self.assertTrue(any("N09" in x for x in ptr_res["issues"]))

    def test_n10_transition_black_frame_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            mp4 = tmp / "black_mid.mp4"
            frames = [(180, 140, 100)] * 10 + [(0, 0, 0)] * 3 + [(100, 160, 210)] * 10
            _write_solid_test_mp4(mp4, frames, fps=10)
            tr_edl = {"transitions": [{"transition_id": "tr_00", "actual_method": "zoom_through", "boundary_sec": 1.1}]}
            _, _, _, ceg, _ = self._sample_causal_fixture(tmp)
            res = audit_causal_transition_visibility({"shots": []}, ceg, transition_edl=tr_edl, video_mp4=mp4)
            self.assertEqual(res["status"], "FAIL")
            self.assertTrue(any("N10" in i for i in res["issues"]))

    def test_n11_n13_n14_n15_n16_n17_causality_period_claims(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _, _, sag, ceg, cec = self._sample_causal_fixture(tmp)
            # N14: Contracts & CSV traceability integrity
            self.assertTrue((tmp / "causal_traceability.csv").exists())
            with (tmp / "causal_traceability.csv").open("r", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            self.assertEqual(len(rows), len(ceg["causal_events"]) + 1)
            for c in cec["contracts"]:
                self.assertTrue(c["expected_visible_consequence"]["observable_signal"])
                self.assertTrue(c["counterfactual_failure"]["failure_mode"])

            # N15: Physics disclosure honest approximation
            self.assertIn(PHYSICS_VISUAL_APPROX, ceg["physics_disclosure"])
            self.assertNotIn("accurate_simulation", ceg["physics_disclosure"])

            # N11: Causal inversion Clean Air Act before inversion trap
            inv_sag = json.loads(json.dumps(sag))
            inv_sag["narrative_events"] = list(reversed(inv_sag["narrative_events"]))
            c_inv = validate_narrative_causality(inv_sag, {"shots": []})
            self.assertEqual(c_inv["status"], "FAIL")

            # N13: 1952 smartphone anachronism blocked
            anach_sag = {**sag, "period_year": 1952}
            c_an = validate_narrative_causality(
                anach_sag,
                {"shots": [{"shot_id": "s0", "procedural_generator": "zach3d:human_device_stage", "staging": {"grounded_props": ["phone_screen"]}}]},
            )
            self.assertEqual(c_an["status"], "FAIL")

            # N17: Post-Clean-Air regression back to dense coal capture
            c_reg = validate_narrative_causality(
                sag,
                {
                    "shots": [
                        {"shot_id": "s_clean", "scene_family": "air_quality_aftermath", "physical_action": "clean_air_act_recovery"},
                        {"shot_id": "s_bad", "scene_family": "atmospheric_inversion_cap", "physical_action": "thermal_inversion_lid_trapping"},
                    ]
                },
            )
            self.assertEqual(c_reg["status"], "FAIL")

            # N16: Historical estimated claim missing ~ / EST. fails
            hc = {"claims": [{"claim_id": "c_est", "canonical_value": "4,000", "numeric_value": 4000, "uncertainty": "estimated"}]}
            ed_tl = {"overlays": [{"overlay_id": "ov_x", "label": "4000 DEATHS", "sublabel": "Monthly toll"}]}
            hc_res = audit_historical_claims(hc, ed_tl)
            self.assertEqual(hc_res["status"], "FAIL")

    def test_n18_n19_n20_proxies_and_honesty_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _, _, _, ceg, cec = self._sample_causal_fixture(tmp)
            # N18: All events collapsed onto single proof type
            flat_ceg = json.loads(json.dumps(ceg))
            for e in flat_ceg["causal_events"]:
                e["proof_type"] = "state_change_before_after"
            p_res = audit_story_silent_comprehension_proxies({"shots": []}, flat_ceg, {"claim_coverage_ratio": 1.0})
            self.assertEqual(p_res["status"], "FAIL")

            # N19: Coverage below 0.85 fails
            p_low = audit_story_silent_comprehension_proxies({"shots": []}, ceg, {"claim_coverage_ratio": 0.50})
            self.assertEqual(p_low["status"], "FAIL")

            # N20: Full Semantic QA fails cleanly on missing MP4 and preserves NOT_VERIFIED subjective statuses
            sem = run_semantic_visual_evidence_qa(
                tmp, {"shots": []}, ceg, cec, video_mp4=tmp / "missing.mp4", require_decoded_frames=True
            )
            self.assertEqual(sem["overall_status"], "FAIL")
            self.assertEqual(sem["subjective_visual_review"], "NOT_VERIFIED")
            self.assertEqual(sem["viewer_retention_status"], "NOT_VERIFIED")

    def test_domain_generalization_four_unrelated_topics(self) -> None:
        """Prove build_causal_event_graph generalizes cleanly across non-London domains."""
        scripts = [
            "You tap an elevator button in a busy lobby. Inside the control cabinet relays route the signal. A heavy traction motor pulls the cab up the shaft.",
            "A message on your smartphone races beneath the ocean. Inside a subsea fiber cable lasers pulse light through dark water. Servers inside a datacenter rack decode the packets cleanly.",
            "When sleep begins, brain neurons clear adenosine buildup. Deep waves sweep across the cortex while muscles rest. Morning sunlight wakes the rested mind cleanly.",
            "On December 5, 1952, cold fog and coal soot engulfed London. A warm air inversion trapped pollution over the city. The Clean Air Act of 1956 gradually cleared residential skies.",
        ]
        with tempfile.TemporaryDirectory() as td:
            for idx, txt in enumerate(scripts):
                rd = Path(td) / f"dom_{idx}"
                ps = parse_script_and_build_voice(txt, selected_skill="zach-d-films", run_dir=rd, kit_dir=KIT_DIR, voice_mode="off")
                ev_g = extract_semantic_visual_events(ps, selected_skill="zach-d-films")
                b = build_causal_event_graph(ev_g, selected_skill="zach-d-films")
                cevs = b["causal_graph"]["causal_events"]
                self.assertGreaterEqual(len(cevs), 3)
                for e in cevs:
                    self.assertIn(e["proof_type"], VALID_PROOF_TYPES)
                    self.assertEqual(e["evidence_status"], EVIDENCE_SUPPORTED)
                self.assertEqual(b["causal_graph"]["world_state_conservation"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
