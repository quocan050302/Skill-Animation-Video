"""Verification Tests for R2.6: False-Pass-Proof QA, Overlay Diff Proofs, A/B Event Alignment & Traps (N11-N24)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from director.retention_qa import audit_overlay_render, compare_ab_versions
from director.visual_storytelling_qa import (
    audit_caption_layout,
    audit_historical_claims,
    audit_period_integrity,
    audit_reveal_order_decoded,
    audit_spatiotemporal_variety,
    build_ab_alignment,
    run_visual_storytelling_qa,
)


def _make_solid_mp4(out_mp4: Path, color_hex: str = "0x101820", dur: float = 2.5) -> None:
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"color=c={color_hex}:s=270x480:r=10:d={dur}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_mp4),
        ],
        check=True, capture_output=True,
    )


class TestStorytellingQA(unittest.TestCase):
    def test_n11_n12_n20_overlay_render_false_pass_proofs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td)
            vid_on = rd / "flat_on.mp4"
            vid_off = rd / "flat_off.mp4"
            _make_solid_mp4(vid_on, "0x182230", 2.0)
            _make_solid_mp4(vid_off, "0x182230", 2.0)

            ed_tl = {
                "caption_mode": "kinetic",
                "callout_mode": "smart",
                "overlays": [
                    {
                        "overlay_id": "ov_00",
                        "type": "focus_ring",
                        "anchor_id": "tank_rivet_seam",
                        "label": "1915 RIVETED SEAM",
                        "start": 0.2,
                        "end": 1.8,
                        "placement_box": [120, 320, 520, 428],
                    }
                ],
            }
            fake_traces = [{
                "time": 1.0,
                "telemetry": {
                    "overlay": {
                        "overlays": [{
                            "overlay_id": "ov_00",
                            "visible": True,
                            "dom_rendered": True,
                            "alpha": 1.0,
                            "label_bbox": [120, 320, 520, 428],
                        }]
                    }
                },
            }]
            # N11/N12: Flat solid pixels claiming visible=True overlay MUST FAIL even without baseline!
            res_flat = audit_overlay_render(vid_on, ed_tl, raw_traces=fake_traces)
            self.assertEqual(res_flat["status"], "FAIL")

            # N20: Matched ON/OFF video with zero pixel delta MUST FAIL!
            res_zero = audit_overlay_render(vid_on, ed_tl, compare_baseline_mp4=vid_off, raw_traces=fake_traces)
            self.assertEqual(res_zero["status"], "FAIL")

            # Fake telemetry dom_rendered=False while visible=True MUST FAIL!
            bad_dom_traces = json.loads(json.dumps(fake_traces))
            bad_dom_traces[0]["telemetry"]["overlay"]["overlays"][0]["dom_rendered"] = False
            self.assertEqual(audit_overlay_render(vid_on, ed_tl, raw_traces=bad_dom_traces)["status"], "FAIL")

    def test_n13_n22_ab_alignment_and_script_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td)
            run_a = rd / "A"
            run_b = rd / "B"
            (run_a / "audio").mkdir(parents=True)
            (run_b / "audio").mkdir(parents=True)

            # Different total durations (`4.0s` vs `5.2s`) aligned by narrative_event_id!
            (run_a / "script.json").write_text(json.dumps(["Line one Boston.", "Line two molasses."]), encoding="utf-8")
            (run_b / "script.json").write_text(json.dumps(["Line one Boston.", "Line two molasses."]), encoding="utf-8")
            (run_a / "storyboard.json").write_text(json.dumps({
                "total_duration_sec": 4.0,
                "shots": [
                    {"shot_id": "shot_00", "narrative_event_id": "nev_000", "beat_id": "beat_00", "start": 0.0, "end": 1.8},
                    {"shot_id": "shot_01", "narrative_event_id": "nev_001", "beat_id": "beat_01", "start": 1.8, "end": 4.0},
                ],
            }), encoding="utf-8")
            (run_b / "storyboard.json").write_text(json.dumps({
                "total_duration_sec": 5.2,
                "shots": [
                    {"shot_id": "shot_00", "narrative_event_id": "nev_000", "beat_id": "beat_00", "start": 0.0, "end": 2.4},
                    {"shot_id": "shot_01", "narrative_event_id": "nev_001", "beat_id": "beat_01", "start": 2.4, "end": 5.2},
                ],
            }), encoding="utf-8")
            _make_solid_mp4(run_a / "preview_1080.mp4", "0x203040", 4.1)
            _make_solid_mp4(run_b / "preview_1080.mp4", "0x403020", 5.3)

            align = build_ab_alignment(run_a, run_b, rd / "ab_out")
            self.assertEqual(align["alignment_status"], "PASS")
            self.assertEqual(align["pairs"][1]["t_a"], 2.9)
            self.assertEqual(align["pairs"][1]["t_b"], 3.8)
            ab_res = compare_ab_versions(run_a, run_b, rd / "ab_out")
            self.assertTrue((rd / "ab_out" / "ab_alignment.json").exists())
            self.assertEqual(len(ab_res["visual_frame_diffs"]), 2)

            # N13: Completely different script MUST FAIL closed!
            (run_b / "script.json").write_text(json.dumps(["How Roman gladiators fought lions inside arenas long ago."]), encoding="utf-8")
            with self.assertRaises(ValueError):
                compare_ab_versions(run_a, run_b, rd / "ab_bad")

    def test_n14_n17_n18_n19_n21_n23_n24_qa_traps(self) -> None:
        sag = {
            "schema_version": "sd-story-action-graph-1",
            "period_year": 1919,
            "narrative_events": [
                {
                    "narrative_event_id": "nev_000",
                    "source_event_id": "ve_00",
                    "location_id": "boston_street",
                    "physical_action": "street_rumble_foreshadow",
                    "world_state_after": ["turn_look"],
                    "primary_asset": "street",
                    "reveal_after_sec": 3.5,
                    "spoiler_tokens": ["molasses", "35"],
                }
            ],
        }
        # N14/N21: Renamed setups with near-identical decoded frames MUST FAIL spatiotemporal variety
        sb_fake_var = {
            "shots": [
                {"shot_id": "shot_00", "index": 0, "duration": 2.0, "setup_type": "setup_a", "event_ids": ["ve_00"], "procedural_generator": "zach3d:boston_street_hook_stage", "staging": {"grounded_props": []}},
                {"shot_id": "shot_01", "index": 1, "duration": 2.0, "setup_type": "setup_b", "event_ids": ["ve_00"], "procedural_generator": "zach3d:boston_street_hook_stage", "staging": {"grounded_props": []}},
            ]
        }
        sdiv_dup = {
            "adjacent_perceptual_pairs": [{"ssim_masked": 0.985, "roi_mad": 0.3}],
            "perceptual_samples": [
                {"shot_id": "shot_00", "intra_mad_roi": 0.05},  # N17 frozen shot
                {"shot_id": "shot_01", "intra_mad_roi": 1.2},
            ],
        }
        self.assertEqual(audit_spatiotemporal_variety(sb_fake_var, sdiv_dup, sag)["status"], "FAIL")

        # N18/N23: Estimated speed without qualifier MUST FAIL historical claims audit
        claims = {
            "claims": [
                {"claim_id": "spd", "display_token": "~35 MPH EST.", "canonical_value": "35", "uncertainty": "estimated"}
            ]
        }
        bad_tl_est = {"overlays": [{"overlay_id": "ov_x", "label": "35 MPH EXACT SPEED", "sublabel": ""}]}
        self.assertEqual(audit_historical_claims(claims, bad_tl_est)["status"], "FAIL")

        # N19: Overlapping caption DOM words MUST FAIL audit_caption_layout
        bad_cap_trace = [{
            "time": 1.0,
            "telemetry": {"overlay": {"caption": {"chunk_id": "cap_000", "caption_layout": {"word_overlap_count": 2, "min_word_gap_px": -1.0, "in_safe_area": True}}}},
        }]
        self.assertEqual(audit_caption_layout(raw_traces=bad_cap_trace)["status"], "FAIL")

        # N24: Reveal leak inside runtime telemetry traces MUST FAIL decoded reveal audit
        bad_rev_trace = [{
            "time": 0.5,
            "telemetry": {"overlay": {"overlays": [{"overlay_id": "ov_00", "visible": True, "label": "MOLASSES WAVE"}]}},
        }]
        self.assertEqual(audit_reveal_order_decoded(sag, {"overlays": []}, raw_traces=bad_rev_trace)["status"], "FAIL")

        # N24/run_visual_storytelling_qa preserves NOT_VERIFIED subjective fields
        with tempfile.TemporaryDirectory() as td:
            rep = run_visual_storytelling_qa(
                run_dir=Path(td),
                storyboard=sb_fake_var,
                action_graph=sag,
                editorial_timeline=bad_tl_est,
                scene_diversity_report=sdiv_dup,
                raw_traces=bad_cap_trace,
                historical_claims=claims,
            )
            self.assertEqual(rep["overall_status"], "FAIL")
            self.assertEqual(rep["subjective_visual_review"], "NOT_VERIFIED")
            self.assertEqual(rep["viewer_retention_status"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
