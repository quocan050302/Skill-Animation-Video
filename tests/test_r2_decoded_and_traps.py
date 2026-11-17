from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = REPO_ROOT / "vendor" / "claude-animation-skills" / "kit"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from director.assets import build_locked_engine_workspace
from director.build_storyboard import build_storyboard_and_bible
from director.character_performance import validate_character_grounding
from director.cinematic_composition import design_frame_for_action, score_visual_progression
from director.cinematic_composition_qa import audit_cinematic_composition
from director.curiosity_director import find_curiosity_beats, plan_attention_pointer
from director.decoded_visual_quality import (
    assess_decoded_frame_triple,
    audit_phone_composition,
    estimate_scene_readability,
    estimate_subject_screen_occupancy,
    probe_video_metadata,
    render_subject_id_matte_at_t,
    run_decoded_visual_quality_audit,
    sample_event_aligned_frames,
    write_visual_proof_contact_sheet,
)
from director.preflight import DiskBudgetGuard, find_browser_executable
from director.parse_script import parse_script_and_build_voice
from director.quality_gate import audit_style_lock, run_final_quality_gate
from director.retention_qa import audit_editorial_fatigue, compare_ab_versions
from director.route_styles import route_and_lock_style
from director.visual_storytelling_director import plan_story_action_graph, validate_narrative_causality
from director.visual_storytelling_qa import (
    audit_caption_layout,
    audit_historical_claims,
    audit_period_integrity,
    audit_physical_and_character_telemetry,
    audit_pointer_tracking,
    audit_reveal_order_decoded,
    audit_spatiotemporal_variety,
    audit_world_state_causality,
)
from tools.run_validation_async import ValidationTask, build_task_graph, verify_test_suite_coverage


def _write_silence_wav(path: Path, dur_sec: float = 1.5, sr: int = 48000, freq_val: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = int(dur_sec * sr)
    buf = (np.sin(np.arange(n_frames) * (2.0 * np.pi * max(1, freq_val) / sr)) * (4000 if freq_val else 0)).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(buf.tobytes())


def _make_solid_mp4(path: Path, dur_sec: float = 1.6, w: int = 270, h: int = 480, color: str = "black") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s={w}x{h}:r=30:d={dur_sec}",
            "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={dur_sec}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _make_textured_mp4(path: Path, dur_sec: float = 1.8, w: int = 360, h: int = 640) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc2=s={w}x{h}:r=30:d={dur_sec}",
            "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={dur_sec}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _write_matte_png(path: Path, subj_box: tuple[int, int, int, int], causal_box: tuple[int, int, int, int] | None = None, w: int = 270, h: int = 480) -> None:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    x0, y0, x1, y1 = subj_box
    arr[y0:y1, x0:x1] = (0, 255, 0)
    if causal_box is not None:
        cx0, cy0, cx1, cy1 = causal_box
        arr[cy0:cy1, cx0:cx1] = (255, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(path)


class TestR2DecodedAndTraps(unittest.TestCase):
    def test_negative_traps_t01_to_t16(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            sb_one = {
                "total_duration_sec": 1.6,
                "shots": [{
                    "shot_id": "shot_00", "index": 0, "start": 0.0, "end": 1.6, "duration": 1.6,
                    "procedural_generator": "zach3d:tacoma_hook_telephoto_stage",
                    "physical_action": "bridge_hook_initial_sway",
                }],
            }

            # T01: Blank / flat MP4 MUST fail decoded sampler
            blank_mp4 = tmp / "blank.mp4"
            _make_solid_mp4(blank_mp4, dur_sec=1.6, color="black")
            res_t01 = sample_event_aligned_frames(blank_mp4, sb_one)
            self.assertEqual(res_t01["status"], "FAIL", f"T01 must fail blank MP4: {res_t01}")
            self.assertTrue(any("T01" in x or "Blank" in x for x in res_t01["issues"]))

            # T02: Stale SHA256 or truncated MP4 duration MUST fail decoded sampler
            tex_mp4 = tmp / "tex.mp4"
            _make_textured_mp4(tex_mp4, dur_sec=1.6)
            res_t02_sha = sample_event_aligned_frames(tex_mp4, sb_one, {"expected_sha256": "0" * 64})
            self.assertEqual(res_t02_sha["status"], "FAIL")
            res_t02_trunc = sample_event_aligned_frames(tex_mp4, {"shots": [{**sb_one["shots"][0], "end": 5.0}]})
            self.assertEqual(res_t02_trunc["status"], "FAIL")

            # T03: Frozen rigid object under camera pan + claimed deformation MUST FAIL
            f0 = np.full((480, 270, 3), 30, dtype=np.uint8)
            f0[10:470, 10:260] = 35
            f0[180:260, 90:180] = (200, 90, 40)
            # Pan background + rigid block identically by +12 px without internal deformation
            f1 = np.roll(f0, 12, axis=1)
            f2 = np.roll(f0, 24, axis=1)
            m0 = {"status": "PASS", "subject_mask": (f0[:, :, 0] > 150)}
            m1 = {"status": "PASS", "subject_mask": (f1[:, :, 0] > 150)}
            m2 = {"status": "PASS", "subject_mask": (f2[:, :, 0] > 150)}
            cams = [
                {"realized_pos": [0.0, 2.0, 8.0], "realized_forward": [0.0, 0.0, -1.0]},
                {"realized_pos": [0.8, 2.0, 8.0], "realized_forward": [0.08, 0.0, -0.996]},
                {"realized_pos": [1.6, 2.0, 8.0], "realized_forward": [0.16, 0.0, -0.987]},
            ]
            res_t03 = assess_decoded_frame_triple([f0, f1, f2], [m0, m1, m2], cams, expected_action_type="deforming", claimed_vertex_disp_m=0.45)
            self.assertEqual(res_t03["status"], "FAIL", f"T03 rigid pan must fail: {res_t03}")

            # T04: Missing semantic subject matte when require_matte=True MUST FAIL
            res_t04 = run_decoded_visual_quality_audit(tmp / "t04", tex_mp4, sb_one, {"overlays": []}, require_matte=True)
            self.assertEqual(res_t04["status"], "FAIL", f"T04 missing matte must fail: {res_t04}")

            # T05 & T06: Tiny distant subject / tiny causal detail on 360px phone MUST FAIL
            matte_tiny_dir = tmp / "t05_run" / "qa" / "mattes"
            matte_frames = []
            for idx, ts in enumerate((0.1, 0.83, 1.46)):
                mp = matte_tiny_dir / f"m_{idx}.png"
                _write_matte_png(mp, subj_box=(130, 235, 140, 245), causal_box=(132, 238, 136, 242))
                matte_frames.append({"t_sec": ts, "matte_path": mp.name})
            res_t05 = run_decoded_visual_quality_audit(
                tmp / "t05_run", tex_mp4, sb_one, {"overlays": []},
                matte_manifest={"frames": matte_frames}, require_matte=True,
            )
            self.assertEqual(res_t05["status"], "FAIL")
            joined_t05 = " | ".join(res_t05.get("issues") or [])
            self.assertTrue("T05" in joined_t05 and "T06" in joined_t05, f"Expected T05 & T06 failures: {joined_t05}")

            # T07: Overlay intruding UI safe zone OR blocking causal feature MUST FAIL mobile phone audit
            bad_tl_ui = {
                "total_duration_sec": 4.0,
                "overlays": [{"overlay_id": "ov_bad", "start": 0.2, "end": 1.2, "placement_box": [10, 80, 1060, 1460], "font_size_1080": 24}],
            }
            res_t07 = audit_phone_composition((320, 360, 390, 1080), sb_one, bad_tl_ui, [{"shot_id": "shot_00", "protected_detail_min_px_360": 18.0, "overlay_causal_overlap_ratio": 0.60}])
            self.assertEqual(res_t07["status"], "FAIL")

            # T08 & T09: Generic target / large tip error / 0 validated settled tips MUST NOT PASS
            tl_ptr = {"callout_mode": "smart", "overlays": [{"overlay_id": "ov_1", "pointer_shape": "impact_arrow", "target_semantic_id": "bridge_midspan_twist"}]}
            res_t08_zero = audit_pointer_tracking(raw_traces=[], editorial_timeline=tl_ptr)
            self.assertEqual(res_t08_zero["status"], "FAIL", "T09: 0 settled tips cannot PASS")
            bad_ptr_traces = [{
                "time_sec": 1.0,
                "telemetry": {"overlay": {"overlays": [{
                    "overlay_id": "ov_1", "visible": True, "alpha": 0.98,
                    "tip_target_error_px": 54.0, "target_semantic_id": "stage_center",
                    "pointer_hits_causal_feature": False,
                }]}},
            }]
            res_t08_miss = audit_pointer_tracking(bad_ptr_traces, tl_ptr)
            self.assertEqual(res_t08_miss["status"], "FAIL")
            self.assertGreaterEqual(len(res_t08_miss["issues"]), 3)

            # T10: Overlay runtime caption overlap MUST FAIL audit_cinematic_composition
            cap_overlap_trace = [{
                "time": 1.0,
                "telemetry": {"overlay": {"overlays": [{"overlay_id": "ov_1", "visible": True, "caption_overlap": True, "in_safe_area": False}]}},
            }]
            res_t10 = audit_cinematic_composition(None, sb_one, {"overlays": []}, raw_traces=cap_overlap_trace)
            self.assertEqual(res_t10["status"], "FAIL")

            # T11: Cramped/overlapping caption DOM layout MUST FAIL
            bad_cap_tr = [{"time": 0.8, "telemetry": {"overlay": {"caption": {"caption_layout": {"word_overlap_count": 1, "min_word_gap_px": 0.2}}}}}]
            self.assertEqual(audit_caption_layout(bad_cap_tr)["status"], "FAIL")

            # T12: Missing 3D pointer anchors / all offscreen skips MUST FAIL / NOT_VERIFIED (never PASS!)
            skipped_traces = [{"time_sec": 1.0, "telemetry": {"overlay": {"overlays": [{"overlay_id": "ov_1", "visible": False, "hidden_reason": "offscreen"}]}}}]
            res_t12 = audit_pointer_tracking(skipped_traces, tl_ptr)
            self.assertNotEqual(res_t12["status"], "PASS")

            # T13: Disconnected cables OR flat torsion MUST FAIL physical telemetry audit
            sb_phys = {"shots": [{"shot_id": "shot_tw", "start": 0.0, "end": 2.0, "duration": 2.0, "procedural_generator": "zach3d:tacoma_torsion_twist_stage", "physical_action": "torsional_flutter_escalation"}]}
            tr_bad_cable = [{"time_sec": 1.0, "shot_id": "shot_tw", "telemetry": {"physical_motion": {"vertex_disp_max_m": 0.002, "deck_roll_span_rad": 0.0, "cables_attached": False}}}]
            res_t13 = audit_physical_and_character_telemetry(sb_phys, raw_traces=tr_bad_cable)
            self.assertEqual(res_t13["status"], "FAIL")

            # T14: Frozen debris (collapse shot static in decoded triple)
            f_stat = np.zeros((240, 135, 3), dtype=np.uint8)
            f_stat[80:160, 30:105] = 180
            m_stat = {"status": "PASS", "subject_mask": (f_stat[:, :, 0] > 100)}
            res_t14 = assess_decoded_frame_triple([f_stat, f_stat.copy(), f_stat.copy()], [m_stat, m_stat, m_stat], expected_action_type="collapse", claimed_vertex_disp_m=2.0)
            self.assertEqual(res_t14["status"], "FAIL")

            # T15: Collapse before torsion OR unexpected collapse inside non-collapse shot
            sb_t15 = {"shots": [
                {"shot_id": "s0", "start": 0.0, "end": 2.0, "duration": 2.0, "procedural_generator": "zach3d:tacoma_wide_establish_stage"},
                {"shot_id": "s1", "start": 2.0, "end": 4.0, "duration": 2.0, "procedural_generator": "zach3d:tacoma_torsion_twist_stage"},
            ]}
            tr_t15 = [
                {"time_sec": 0.5, "shot_id": "s0", "telemetry": {"physical_motion": {"collapse_active": True, "vertex_disp_max_m": 1.2, "cables_attached": True}}},
                {"time_sec": 3.0, "shot_id": "s1", "telemetry": {"physical_motion": {"deck_roll_span_rad": 0.3, "vertex_disp_max_m": 0.4, "cables_attached": True}}},
            ]
            self.assertEqual(audit_physical_and_character_telemetry(sb_t15, tr_t15)["status"], "FAIL")

            # T16: Grounded human floor penetration / sliding MUST FAIL
            tr_t16 = [
                {"time_sec": 0.0, "shot_id": "s0", "telemetry": {"character_performance": {"left_foot_ground_err_m": -0.09, "stance_slide_m": 0.25, "world_pelvis": [0.0, 0.9, 0.0], "action_intent": "retreat", "move_toward_threat_dot": 0.8}}},
            ]
            self.assertEqual(validate_character_grounding(tr_t16)["status"], "FAIL")

    def test_negative_traps_t17_to_t32(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            # T17: Post-collapse world-state reset back to intact bridge MUST FAIL causality
            bad_ag = {
                "period_year": 1940,
                "events": [
                    {"narrative_event_id": "ev_00", "start": 0.0, "end": 2.0, "physical_action": "bridge_span_collapse", "post_collapse": False},
                    {"narrative_event_id": "ev_01", "start": 2.0, "end": 4.0, "physical_action": "bridge_vertical_bounce", "world_state": {"center_span_collapsed": False}, "post_collapse": True},
                ],
            }
            sb_t17 = {
                "shots": [
                    {"shot_id": "shot_00", "narrative_event_id": "ev_00", "start": 0.0, "end": 2.0, "duration": 2.0, "physical_action": "bridge_span_collapse", "procedural_generator": "zach3d:tacoma_collapse_plunge_stage"},
                    {"shot_id": "shot_01", "narrative_event_id": "ev_01", "start": 2.0, "end": 4.0, "duration": 2.0, "physical_action": "bridge_vertical_bounce", "procedural_generator": "zach3d:tacoma_roadway_wave_stage"},
                ]
            }
            self.assertEqual(audit_world_state_causality(bad_ag, sb_t17)["status"], "FAIL")

            # T18: Pseudo-variety / duplicate adjacent composition without progression MUST FAIL
            sdiv_dup = {"adjacent_perceptual_pairs": [{"ssim_masked": 0.99, "roi_mad": 0.25}]}
            sb_t18 = {"shots": [
                {"shot_id": "s0", "setup_type": "st_a", "procedural_generator": "g0", "physical_action": "bounce", "framing": "wide", "camera_angle": "eye", "camera_move": "pan", "start": 0.0, "end": 2.0, "duration": 2.0},
                {"shot_id": "s1", "setup_type": "st_b", "procedural_generator": "g0", "physical_action": "bounce", "framing": "wide", "camera_angle": "eye", "camera_move": "pan", "start": 2.0, "end": 4.0, "duration": 2.0},
            ]}
            self.assertEqual(audit_spatiotemporal_variety(sb_t18, sdiv_dup, {"events": []})["status"], "FAIL")

            # T19: Spoiler/label leak before reveal time MUST FAIL
            ag_t19 = {"narrative_events": [{"narrative_event_id": "ev0", "reveal_after_sec": 3.0, "spoiler_tokens": ["collapse"]}]}
            tr_t19 = [{"time": 0.5, "telemetry": {"overlay": {"overlays": [{"overlay_id": "ov0", "narrative_event_id": "ev0", "visible": True, "label": "SPAN COLLAPSE"}]}}}]
            self.assertEqual(audit_reveal_order_decoded(ag_t19, {"overlays": []}, raw_traces=tr_t19)["status"], "FAIL")

            # T20: Exact unverified numeric claim without qualifier MUST FAIL
            claims = {"claims": [{"claim_id": "wind_mph", "display_token": "~42 MPH EST.", "canonical_value": "42", "uncertainty": "estimated"}]}
            self.assertEqual(audit_historical_claims(claims, {"overlays": [{"overlay_id": "o1", "label": "42 MPH EXACT WIND", "sublabel": ""}]})["status"], "FAIL")

            # T21: Period anachronism (modern smartphone/datacenter prop inside 1940 run) MUST FAIL
            sb_t21 = {"shots": [{"shot_id": "s0", "procedural_generator": "zach3d:human_device_stage", "staging": {"grounded_props": ["phone_screen"]}}]}
            self.assertEqual(audit_period_integrity(sb_t21, {"period_year": 1940})["status"], "FAIL")

            # T22: Visual skill leakage across isolated engines MUST FAIL style-lock audit
            sd_bad = {
                "selected_skill": "zach-d-films", "selection_mode": "explicit", "origin_skills": ["zach-d-films"],
                "style_lock": {"enabled": True, "engine": "zach-d-films", "mixing_policy": "forbidden", "fallback_policy": "fail-closed"},
                "secondary_skill": "stick-figure",
            }
            sb_bad = {
                "selected_skill": "zach-d-films", "origin_skills": ["zach-d-films"],
                "shots": [{"shot_id": "s0", "engine": "stick-figure"}],
                "visual_assets": [{"origin_skill": "zach-d-films", "generator_module": "director/assets/stick_figure_adapter.py"}],
            }
            self.assertEqual(audit_style_lock(sd_bad, sb_bad, None, None)["status"], "FAIL")

            # T23 & T24: Fake native_4k on upscaled/non-4K stream MUST FAIL + subjective fields remain NOT_VERIFIED
            vid_1080 = tmp / "not_4k_1080.mp4"
            _make_textured_mp4(vid_1080, dur_sec=1.2, w=360, h=640)
            res_t23_dims = sample_event_aligned_frames(
                vid_1080,
                {"shots": [{"shot_id": "s0", "start": 0.0, "end": 1.0}]},
                {"expected_width": 2160, "expected_height": 3840},
            )
            self.assertEqual(res_t23_dims["status"], "FAIL", "T23: Claiming 2160x3840 on smaller stream must FAIL")
            up_mp4 = tmp / "flat_up_4k.mp4"
            _make_solid_mp4(up_mp4, dur_sec=1.0, w=2160, h=3840, color="0x1e293b")
            from director.quality_gate import _verify_4k_sharpness
            sharp_r, has_hf = _verify_4k_sharpness(up_mp4, 0.5)
            self.assertFalse(has_hf, f"T23: Flat non-detailed 4K stream cannot claim subpixel native 4K detail (ratio={sharp_r})")

            # T24: Subjective visual review in decoded QA must always remain NOT_VERIFIED
            rep_dec = run_decoded_visual_quality_audit(tmp / "t24_dec", up_mp4, {"shots": [{"shot_id": "s0", "start": 0.0, "end": 1.0}]}, {"overlays": []})
            self.assertEqual(rep_dec["subjective_visual_quality"], "NOT_VERIFIED")
            self.assertEqual(rep_dec["viewer_retention_status"], "NOT_VERIFIED")

            # T25: Metadata cinematic_composition PASS blocked when decoded_qa_report FAILS
            sb_good_plan = {"shots": [
                {"shot_id": "s0", "start": 0.0, "end": 2.0, "duration": 2.0, "framing": "wide", "camera_angle": "eye", "camera_move": "pan", "procedural_generator": "a"},
                {"shot_id": "s1", "start": 2.0, "end": 4.0, "duration": 2.0, "framing": "closeup", "camera_angle": "low", "camera_move": "orbit", "procedural_generator": "b"},
            ]}
            res_t25 = audit_cinematic_composition(None, sb_good_plan, {"overlays": []}, decoded_qa_report={"status": "FAIL", "issues": ["T05: Tiny subject"]})
            self.assertEqual(res_t25["status"], "FAIL")

            # T26: A/B voice PCM parity guard fails on mismatched vo.wav
            dir_a, dir_b = tmp / "ab_a", tmp / "ab_b"
            _write_silence_wav(dir_a / "audio" / "vo.wav", freq_val=440)
            _write_silence_wav(dir_b / "audio" / "vo.wav", freq_val=880)
            (dir_a / "editorial_timeline.json").write_text(json.dumps({"editorial_theme": "legacy", "callout_mode": "off", "curiosity_layer": "off", "overlays": []}), encoding="utf-8")
            (dir_b / "editorial_timeline.json").write_text(json.dumps({"editorial_theme": "role-aware", "callout_mode": "smart", "curiosity_layer": "auto", "overlays": [{"overlay_id": "o1"}]}), encoding="utf-8")
            (dir_a / "final_4k.mp4").write_bytes(b"a")
            (dir_b / "final_4k.mp4").write_bytes(b"b")
            with self.assertRaises(ValueError) as ctx_t26:
                compare_ab_versions(dir_a, dir_b, tmp / "ab_out", require_voice_parity=True)
            self.assertIn("T26", str(ctx_t26.exception))

            # T28: Missing tests/test_*.py in DAG MUST FAIL verify_test_suite_coverage
            cov_bad = verify_test_suite_coverage(REPO_ROOT / "tests", [ValidationTask(task_id="only_one", cmd=["python3", "-m", "unittest", "tests.test_unit_and_negative"])])
            self.assertFalse(cov_bad["ok"])
            self.assertGreater(len(cov_bad["missing_modules"]), 5)
            # And real full DAG MUST cover 100% of test_*.py files
            cov_full = verify_test_suite_coverage(REPO_ROOT / "tests", build_task_graph("full"))
            self.assertTrue(cov_full["ok"], f"Full DAG missing test modules: {cov_full['missing_modules']}")

            # T30: DiskBudgetGuard blocks when free space < required + headroom
            guard = DiskBudgetGuard(tmp / "disk_guard")
            res_t30 = guard.check(required_bytes=2 * (1024 ** 3), free_bytes_override=8 * (1024 ** 3))
            self.assertFalse(res_t30["ok"])
            self.assertEqual(res_t30["status"], "DISK_BUDGET_BLOCKED")

            # T31: Over-annotated shot with free_screen_ratio < 0.20 MUST FAIL
            over_tl = {"total_duration_sec": 4.0, "overlays": [{"overlay_id": "ov_fill", "start": 0.0, "end": 4.0, "placement_box": [100, 220, 920, 420], "font_size_1080": 32}]}
            res_t31 = audit_phone_composition((360,), {"total_duration_sec": 4.0}, over_tl)
            self.assertEqual(res_t31["status"], "FAIL")
            self.assertLess(res_t31["free_screen_ratio"], 0.20)

            # T32: Headline/caption vertical overlap on 320px/360px mobile MUST FAIL
            res_t32 = audit_phone_composition((320, 360), {"total_duration_sec": 5.0}, {"total_duration_sec": 5.0, "overlays": [{"overlay_id": "ov_low", "start": 0.5, "end": 1.5, "placement_box": [80, 1300, 960, 1540], "font_size_1080": 26}]})
            self.assertEqual(res_t32["status"], "FAIL")

    def test_t27_t29_generalization_and_skyscraper_seek_invariance(self) -> None:
        """Positive Matrix + T27 out-of-order WebGL seek invariance + T29 packet parity + neutral third-domain check."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)

            # Neutral third-domain generalization test ("Submarine ballast tank compressed air") without Tacoma/Boston hardcoding
            sub_prompt = (
                "/short-director --skill zach-d-films "
                "When a steel submarine dives, flooded ballast tanks pull the hull beneath the ocean surface. "
                "High-pressure compressed air blasts water downward through hull vents so buoyant air restores lift."
            )
            sub_dec, sub_clean, _ = route_and_lock_style(REPO_ROOT, sub_prompt, cli_skill="zach-d-films", upstream_sha="r2_test")
            sub_ps = parse_script_and_build_voice(sub_clean, "zach-d-films", tmp / "sub", KIT_DIR, voice_mode="off")
            sub_sb = build_storyboard_and_bible(sub_ps, sub_dec, tmp / "sub", fps=30, seed=7)
            sub_gens = [s["procedural_generator"] for s in sub_sb["shots"]]
            self.assertFalse(any("tacoma_" in g or "boston_" in g or "roman_" in g for g in sub_gens), f"Third domain leaked hardcoded domain stages: {sub_gens}")
            # FrameDesignIntent written + grounded fields present
            self.assertTrue((tmp / "sub" / "frame_design_intent.json").exists())
            fdi = json.loads((tmp / "sub" / "frame_design_intent.json").read_text(encoding="utf-8"))
            self.assertTrue(all("salient_action_anchor" in x and "minimum_visible_feature_px" in x for x in fdi["shots"]))

            # T29: --audio-only packet preservation check rejects re-encoded video stream vs accepts -c:v copy
            v_src = tmp / "v_src.mp4"
            v_copy = tmp / "v_copy.mp4"
            v_reenc = tmp / "v_reenc.mp4"
            a_new = tmp / "a_new.wav"
            _make_textured_mp4(v_src, dur_sec=1.2)
            _write_silence_wav(a_new, dur_sec=1.2, freq_val=520)
            subprocess.run(["ffmpeg", "-y", "-i", str(v_src), "-i", str(a_new), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", str(v_copy)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["ffmpeg", "-y", "-i", str(v_src), "-i", str(a_new), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "28", "-c:a", "aac", "-shortest", str(v_reenc)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            def _vmd5(mp: Path) -> str:
                return subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp), "-map", "0:v", "-c", "copy", "-f", "md5", "-"], capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(_vmd5(v_src), _vmd5(v_copy), "Lossless -c:v copy remux must preserve identical video packets")
            self.assertNotEqual(_vmd5(v_src), _vmd5(v_reenc), "T29: Re-encoded video stream must be caught as modified packet MD5")

            # Skyscraper E2E scene workspace + out-of-order WebGL seek determinism (T27) + matte & cutaway validation
            sky_prompt = (
                "/short-director --skill zach-d-films "
                "Look up at a skyscraper in a strong storm and the rooftop is moving. "
                "Crosswinds create alternating vortices across the facade while a pendulum tuned mass damper swings opposite inside."
            )
            sky_dir = tmp / "sky_seek"
            sky_dec, sky_clean, _ = route_and_lock_style(REPO_ROOT, sky_prompt, cli_skill="zach-d-films", upstream_sha="r2_test")
            sky_ps = parse_script_and_build_voice(sky_clean, "zach-d-films", sky_dir, KIT_DIR, voice_mode="off")
            sky_sb = build_storyboard_and_bible(sky_ps, sky_dec, sky_dir, fps=30, seed=42, callout_mode="smart", editorial_theme="role-aware")
            sky_ep = build_locked_engine_workspace("zach-d-films", REPO_ROOT, sky_dir, sky_sb, sky_ps)
            self.assertIn("zach3d:skyscraper_tmd_cutaway_stage", [s["procedural_generator"] for s in sky_sb["shots"]])

            browser = find_browser_executable()
            self.assertIsNotNone(browser, "Playwright browser binary must exist for WebGL seek check")
            # Sample >=3 non-monotonic timestamps twice ([t2, t0, t1] vs [t0, t1, t2]) and verify identical SHA-256 / telemetry
            t0 = round(float(sky_sb["shots"][0]["start"]) + 0.5, 3)
            t1 = round(float(sky_sb["shots"][1]["start"]) + 0.5, 3)
            t2 = round(float(sky_sb["shots"][-1]["start"]) + 0.5, 3)

            env = dict(os.environ)
            env["PLAYWRIGHT_CHROME_PATH"] = str(browser)
            html = Path(sky_ep["entry_html"]).resolve()
            angle = "metal" if sys.platform == "darwin" else "d3d11"

            for order_name, t_list in (("forward", [t0, t1, t2]), ("out_of_order", [t2, t0, t1])):
                out_sub = tmp / f"seek_{order_name}"
                out_sub.mkdir(parents=True, exist_ok=True)
                csv = ",".join(f"{x:.3f}" for x in t_list)
                subprocess.run(
                    [
                        "node", str(REPO_ROOT / "director" / "render_node.mjs"),
                        "stills", str(html), str(out_sub), csv, "0", angle,
                    ],
                    env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )

            for ts in (t0, t1, t2):
                pa = tmp / "seek_forward" / f"still_{ts:.3f}.png"
                pb = tmp / "seek_out_of_order" / f"still_{ts:.3f}.png"
                arr_a = np.asarray(Image.open(pa).convert("RGB"), dtype=np.int16)
                arr_b = np.asarray(Image.open(pb).convert("RGB"), dtype=np.int16)
                mad = float(np.abs(arr_a - arr_b).mean())
                self.assertLess(mad, 0.25, f"T27 out-of-order seek mismatch at t={ts}s (MAD={mad})")


if __name__ == "__main__":
    unittest.main()
