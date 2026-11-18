"""SD-RETENTION-04.R1 Negative Traps (N21-N40), Action Camera Info-Gain & Live London WebGL Proof."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np
from PIL import Image

from director.action_camera_director import (
    plan_action_driven_camera,
    score_camera_information_gain,
    select_camera_intent,
    validate_camera_proof_visibility,
)
from director.assets.zach_d_films_adapter import generate_engine_project
from director.audio_narrative import extract_sound_events
from director.build_storyboard import build_storyboard_and_bible
from director.camera_execution import evaluate_camera_trace_accuracy
from director.decoded_visual_quality import _masks_from_matte_rgb
from director.parse_script import parse_script_and_build_voice
from director.preflight import run_preflight
from director.provenance_guard import ProvenanceGuard
from director.quality_gate import audit_style_lock
from director.render_scene import _run_render_node
from director.route_styles import route_and_lock_style
from director.semantic_visual_evidence_qa import (
    _load_detailed_matte_channels,
    audit_ab_vo_and_metric_consistency,
    audit_claim_pointer_semantics,
    audit_relative_motion_evidence,
    write_qa_failure_examples,
)
from director.sfx_director import select_procedural_sfx


ROOT = Path(__file__).resolve().parents[1]
KIT_DIR = ROOT / "vendor" / "claude-animation-skills" / "kit"

LONDON_SCRIPT = (
    "Zach D. Films style: "
    "At noon on December 5, 1952, London streets suddenly turned dark as midnight under toxic smog. "
    "Millions of coal fireplaces and power station chimneys pumped thick soot and sulfur smoke into icy winter air. "
    "Then a warm temperature inversion slid overhead like a lid, trapping cold dirty air against the ground for five days. "
    "Visibility dropped to zero until red double-decker buses crawled blindly behind conductors carrying hand lanterns. "
    "Pedestrians coughed and shielded their faces against acidic droplets, leading to an estimated 4,000 excess deaths that month. "
    "Four years later, the Clean Air Act of 1956 drove a historic shift toward smokeless heating and cleaner city skies."
)


def _write_wav(path: Path, freq_hz: float, dur_sec: float = 0.5, sr: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(dur_sec * sr)
    t = np.arange(n, dtype=np.float64) / sr
    pcm = (np.sin(2.0 * np.pi * freq_hz * t) * 12000.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


class TestSdRetention04CameraAndVisualProof(unittest.TestCase):
    def tearDown(self) -> None:
        ProvenanceGuard.deactivate()

    def test_n21_n22_n23_n24_camera_q1_q5_and_info_gain(self) -> None:
        sb = {"shots": [{"shot_id": "shot_00", "framing": "MS", "physical_action": "sway", "camera": {"framing": "MS", "movement": "gentle_drift"}}]}
        # N21: Missing Q1-Q5 fields
        bad_q = [{"shot_id": "shot_00", "why_this_shot": "", "what_viewer_learns": "", "target_causal_feature_id": "beam_a", "camera_justification_rule": "rule", "counterfactual_loss_if_omitted": "", "info_gain_metrics": {"camera_motion_justification": 0.9, "total_info_gain_score": 0.85}}]
        self.assertEqual(validate_camera_proof_visibility(bad_q, sb)["status"], "FAIL")

        # N22: Generic stage_center anchor forbidden
        bad_cen = [{"shot_id": "shot_00", "why_this_shot": "ok", "what_viewer_learns": "ok", "target_causal_feature_id": "stage_center", "camera_justification_rule": "rule", "counterfactual_loss_if_omitted": "lost", "info_gain_metrics": {"camera_motion_justification": 0.9, "total_info_gain_score": 0.85}}]
        self.assertEqual(validate_camera_proof_visibility(bad_cen, sb)["status"], "FAIL")

        # N23: Gimmick whip spin on split comparison fails motion justification
        gimmick_cand = {"shot_id": "shot_00", "proof_type": "comparative_split_reference", "camera": {"framing": "WS_Split", "movement": "whip_spin_shake"}, "staging": {"salient_action_anchor": "twin_towers"}}
        ig_g = score_camera_information_gain(gimmick_cand)
        self.assertLess(ig_g["camera_motion_justification"], 0.45)
        bad_mot = [{"shot_id": "shot_00", "why_this_shot": "ok", "what_viewer_learns": "ok", "target_causal_feature_id": "twin_towers", "camera_justification_rule": "rule", "counterfactual_loss_if_omitted": "lost", "info_gain_metrics": ig_g}]
        self.assertEqual(validate_camera_proof_visibility(bad_mot, sb)["status"], "FAIL")

        # N24: Offset reference candidate beats dead-centered candidate
        centered_c = {"shot_id": "shot_00", "proof_type": "displacement_relative_to_fixed_reference", "camera": {"framing": "MS", "movement": "gentle_drift", "pos": [0.0, 1.4, 3.0]}, "staging": {"salient_action_anchor": "plumb_tip", "salient_action_world_pos": [0.0, 2.0, 0.0]}}
        offset_c = {"shot_id": "shot_00", "proof_type": "displacement_relative_to_fixed_reference", "camera": {"framing": "WS_Ref", "movement": "track_pan", "pos": [-1.2, 1.8, 4.2]}, "staging": {"salient_action_anchor": "plumb_tip", "salient_action_world_pos": [0.5, 2.0, 0.0]}}
        self.assertGreater(score_camera_information_gain(centered_c)["subject_centering_penalty"], 0.0)
        chosen, _ = select_camera_intent([centered_c, offset_c])
        self.assertEqual(chosen["camera"]["framing"], "WS_Ref")

    def test_n25_n26_ab_vo_parity_and_metric_inconsistency(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            ra, rb = tmp / "A", tmp / "B"
            _write_wav(ra / "audio" / "vo.wav", 330.0)
            _write_wav(rb / "audio" / "vo.wav", 440.0)  # N25: different PCM!
            res = audit_ab_vo_and_metric_consistency(ra, rb)
            self.assertEqual(res["status"], "FAIL")
            self.assertFalse(res["pcm_identical"])

            # N26: Identical PCM WAVs yet stale vo_pcm_sha256 in voice_delivery_report.json
            shutil.copy2(ra / "audio" / "vo.wav", rb / "audio" / "vo.wav")
            (rb / "audio" / "voice_delivery_report.json").write_text(
                json.dumps({"status": "PASS", "vo_pcm_sha256": "deadbeef" * 8}),
                encoding="utf-8",
            )
            res2 = audit_ab_vo_and_metric_consistency(ra, rb)
            self.assertEqual(res2["status"], "FAIL")
            self.assertTrue(any("METRIC_INCONSISTENCY" in i for i in res2["issues"]))

    def test_n27_n29_n30_n35_n36_n37_mattes_warnings_and_examples(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            # N29: Detailed matte channel decoding stays backward-compatible with R2 masks
            mp = tmp / "matte.png"
            arr = np.full((120, 90, 3), 40, dtype=np.uint8)
            arr[10:25, 10:25] = [0, 224, 96]     # cause_source (0x00e060)
            arr[30:45, 10:25] = [32, 255, 32]    # effect_result (0x20ff20)
            arr[50:65, 10:25] = [224, 0, 80]     # reference_fixed (0xe00050)
            arr[70:85, 10:25] = [0, 0, 255]      # character (0x0000ff)
            arr[90:105, 10:25] = [255, 0, 0]     # subject (0xff0000)
            Image.fromarray(arr).save(mp)

            det = _load_detailed_matte_channels(mp)
            self.assertEqual(det["status"], "PASS")
            self.assertGreater(det["role_ratios"]["cause_source"], 0.01)
            self.assertGreater(det["role_ratios"]["effect_result"], 0.01)
            self.assertGreater(det["role_ratios"]["reference_fixed"], 0.01)
            self.assertGreater(det["role_ratios"]["character"], 0.01)

            r2_masks = _masks_from_matte_rgb(np.asarray(Image.open(mp)))
            self.assertTrue(r2_masks["causal_feature_mask"].any())
            self.assertTrue(r2_masks["character_mask"].any())
            self.assertTrue(r2_masks["subject_mask"].any())

            # N36: Missing reference_fixed triggers advisory warning on displacement claim
            ceg = {"causal_events": [{"causal_event_id": "cev_000", "proof_type": "displacement_relative_to_fixed_reference"}]}
            arr_noref = np.full((120, 90, 3), 40, dtype=np.uint8)
            arr_noref[20:60, 20:60] = [0, 255, 0]
            mp2 = tmp / "matte_noref.png"
            Image.fromarray(arr_noref).save(mp2)
            rel_w = audit_relative_motion_evidence(
                ceg,
                {"shots": [{"shot_id": "shot_00", "start": 0.0, "end": 2.0, "causal_event_id": "cev_000"}]},
                matte_manifest={"frames": [{"t_sec": 0.12, "matte_path": str(mp2)}, {"t_sec": 1.88, "matte_path": str(mp2)}]},
                qa_dir=tmp,
            )
            self.assertEqual(rel_w["status"], "WARN")
            self.assertTrue(rel_w["warnings"])

            # N37: Pointer tip in black sky outside foreground patch triggers advisory warning
            ptr_w = audit_claim_pointer_semantics(
                {"overlays": [{"overlay_id": "ov_00", "narrative_claim_id": "c0", "target_entity_id": "e0", "target_feature_id": "f0", "proof_target_id": "f0", "semantic_region_of_change": "r0", "why_this_overlay": "because", "pointer_shape": "impact_arrow"}]},
                raw_traces=[{"time": 1.0, "telemetry": {"overlay": {"overlays": [{"overlay_id": "ov_00", "visible": True, "alpha": 1.0, "tip_target_error_px": 4.0, "tip_xy": [1040, 1880]}]}}}],
                matte_manifest={"frames": [{"t_sec": 1.0, "matte_path": str(mp2)}]},
                qa_dir=tmp,
            )
            self.assertEqual(ptr_w["status"], "WARN")

            # N30: qa_failures_visual_examples writes index even gracefully
            ex_dir = tmp / "qa_examples"
            write_qa_failure_examples(ex_dir, None, [], ["Sample issue N30"])
            self.assertTrue((ex_dir / "examples_index.json").exists())

    def test_n31_to_n40_london_1952_e2e_plan_webgl_seek_mattes_and_sfx(self) -> None:
        pf = run_preflight(ROOT, selected_skill="zach-d-films", lang="en")
        self.assertTrue(pf.ok)
        prompt = f"/short-director --skill zach-d-films {LONDON_SCRIPT}"
        style, cleaned, _ = route_and_lock_style(ROOT, prompt, cli_skill="zach-d-films", upstream_sha=pf.upstream_sha)
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            parsed = parse_script_and_build_voice(
                cleaned,
                selected_skill="zach-d-films",
                run_dir=tmp,
                kit_dir=KIT_DIR,
                lang="en",
                voice_mode="off",
            )
            sb = build_storyboard_and_bible(
                parsed_script=parsed,
                style_decisions=style,
                run_dir=tmp,
                fps=30,
                seed=42,
                edit_energy="dynamic",
                scene_novelty="high",
                transition_policy="motivated",
                caption_mode="kinetic",
                callout_mode="smart",
                editorial_theme="role-aware",
                curiosity_layer="auto",
            )
            # N31: Causal files, Q1-Q5 contracts, >= 5 distinct London generators, clean style lock
            for req in ("causal_event_graph.json", "causal_evidence_contracts.json", "causal_traceability.csv", "camera_intent_report.json"):
                self.assertTrue((tmp / req).exists(), f"Missing {req}")
            gens = {s["procedural_generator"] for s in sb["shots"]}
            self.assertGreaterEqual(len(gens), 5, f"Expected >=5 distinct London generators, got {gens}")
            self.assertTrue(all(g.startswith("zach3d:london_") for g in gens), f"Unexpected generators: {gens}")

            # Generate engine project + pre-render audit (N38)
            guard = ProvenanceGuard.activate(ROOT, selection_mode="explicit", selected_skill="zach-d-films")
            eng = generate_engine_project(ROOT, tmp, sb, parsed)
            aud = audit_style_lock(style, sb, eng, guard_snapshot=guard.snapshot_report(), stage="pre_render")
            self.assertEqual(aud["status"], "PASS")

            # N39: London SFX cue extraction & DSP wave synthesis
            rng = np.random.default_rng(77)
            for si, sh in enumerate(sb["shots"]):
                prev_s = sb["shots"][si - 1] if si > 0 else None
                next_s = sb["shots"][si + 1] if si + 1 < len(sb["shots"]) else None
                evs = extract_sound_events(sh, prev_s, next_s, parsed["voice"]["words"], selected_skill="zach-d-films")
                for ev in evs:
                    wav = select_procedural_sfx(ev["intent"], ev, rng)
                    self.assertTrue(np.all(np.isfinite(wav)))

            # N32, N33, N34: Live Headless Chromium trace non-sequential seek + exact revisit + semantic matte pass!
            dur = float(sb["total_duration_sec"])
            seek_times = [round(min(dur - 0.1, x), 3) for x in (6.3, 0.4, 20.1, 3.7, 6.3)]
            tr_res = _run_render_node(
                node_bin=pf.node_path,
                render_mjs=(ROOT / "director" / "render_node.mjs").resolve(),
                args=["trace", eng["entry_html"], ",".join(str(t) for t in seek_times), "1", pf.webgl_backend],
                browser_exe=pf.browser_executable,
                log_path=tmp / "logs" / "seek_trace.log",
            )
            traces = tr_res["traces"]
            self.assertEqual(len(traces), 5)
            # N32: Exact determinism across non-sequential seek (first t=6.3 vs revisited t=6.3)
            c0 = traces[0]["telemetry"]["camera"]
            c4 = traces[4]["telemetry"]["camera"]
            for k in range(3):
                self.assertAlmostEqual(c0["realized_pos"][k], c4["realized_pos"][k], places=4)
            cam_eval = evaluate_camera_trace_accuracy(sb, json.loads((tmp / "camera_paths.json").read_text(encoding="utf-8")), traces)
            self.assertEqual(cam_eval["status"], "PASS", f"Camera trace failures: {cam_eval['failures']}")

            # N34: Live WebGL semantic matte pass at shot midpoints
            mid_times = [round(0.5 * (float(s["start"]) + float(s["end"])), 3) for s in sb["shots"]]
            mattes_dir = tmp / "qa" / "mattes"
            _run_render_node(
                node_bin=pf.node_path,
                render_mjs=(ROOT / "director" / "render_node.mjs").resolve(),
                args=["mattes", eng["entry_html"], str(mattes_dir), ",".join(f"{t:.3f}" for t in mid_times), "1", pf.webgl_backend],
                browser_exe=pf.browser_executable,
                log_path=tmp / "logs" / "mattes_smoke.log",
            )
            manifest = json.loads((mattes_dir / "matte_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["frames"]), len(mid_times))
            for fr in manifest["frames"]:
                d = _load_detailed_matte_channels(Path(fr["matte_path"]), overlay_boxes_1080=fr.get("overlay_boxes_1080"))
                self.assertEqual(d["status"], "PASS")
                # Scene fog MUST NOT corrupt matte colors into brown; foreground (subject|character) pixels must read cleanly
                fg_ratio = float(d["role_ratios"]["subject"]) + float(d["role_ratios"]["character"])
                self.assertGreater(fg_ratio, 0.04, f"Missing foreground subject/character matte in {fr['shot_id']}")


if __name__ == "__main__":
    unittest.main()
