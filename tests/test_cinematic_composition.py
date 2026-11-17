"""Verification Tests for Cinematic Frame Composition & Collision QA (G17-G18, N07)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from director.cinematic_composition import (
    design_frame_for_action,
    plan_reveal_camera,
    score_visual_progression,
)
from director.cinematic_composition_qa import audit_cinematic_composition


class TestCinematicComposition(unittest.TestCase):
    def test_g17_g18_negative_space_and_progression_scoring(self) -> None:
        shots = [
            {"shot_id": "s0", "framing": "ECU_Telephoto", "angle": "long_lens_foreshortened", "move": "telephoto_micro_track", "physical_action": "bridge_deck_gentle_wave", "staging": {"sky_theme": "tacoma_overcast"}},
            {"shot_id": "s1", "framing": "VWS", "angle": "elevated_panorama", "move": "slow_reveal_drift", "physical_action": "wide_establish_1940", "staging": {"sky_theme": "tacoma_overcast"}},
            {"shot_id": "s2", "framing": "CU", "angle": "under_deck_low", "move": "push_under_girder", "physical_action": "under_deck_vortex_cutaway", "staging": {"sky_theme": "tacoma_overcast"}},
            {"shot_id": "s3", "framing": "MS", "angle": "tilted_deck_axis", "move": "roll_coupled_follow", "physical_action": "torsion_deck_twist", "staging": {"sky_theme": "tacoma_storm"}},
            {"shot_id": "s4", "framing": "WS_Pullback", "angle": "high_shore_aftermath", "move": "pull_back_settle", "physical_action": "aftermath_broken_stub_towers", "staging": {"sky_theme": "tacoma_aftermath"}},
        ]
        ovs = [
            {"overlay_id": "ov_0", "shot_id": "s0", "role": "curiosity_headline", "placement_box": [104, 210, 976, 448]},
            {"overlay_id": "ov_1", "shot_id": "s1", "role": "location_time", "placement_box": [104, 185, 640, 275]},
        ]
        arc = plan_reveal_camera([{"narrative_event_id": f"n{i}", "physical_action": s["physical_action"]} for i, s in enumerate(shots)])
        self.assertEqual(arc[0]["scale_tier"], "macro_or_telephoto_hook")
        self.assertEqual(arc[2]["scale_tier"], "close_mechanical_detail")

        with tempfile.TemporaryDirectory() as td:
            rep = audit_cinematic_composition(Path(td), {"shots": shots}, {"overlays": ovs}, raw_traces=None)
            self.assertEqual(rep["status"], "PASS")
            self.assertEqual(rep["unique_framings_count"], 5)
            self.assertTrue((Path(td) / "composition_report.json").exists())

    def test_negative_traps_collision_face_caption_and_repetitive_triplets(self) -> None:
        # Face protect zone overlap on onlooker shot fails composition
        bad_face = design_frame_for_action(
            {"shot_id": "s_on", "physical_action": "shore_onlooker_react", "framing": "MS"},
            editorial_layout=[{"overlay_id": "ov_x", "role": "curiosity_headline", "placement_box": [280, 490, 760, 740]}],
        )
        self.assertFalse(bad_face["composition_ok"])

        # Caption intrusion (y1 > 1345) fails composition
        bad_cap = design_frame_for_action(
            {"shot_id": "s_cap", "physical_action": "torsion", "framing": "MS"},
            editorial_layout=[{"overlay_id": "ov_c", "role": "explanation", "placement_box": [120, 1290, 560, 1410]}],
        )
        self.assertFalse(bad_cap["composition_ok"])

        # Runtime caption_overlap in raw_traces fails N07
        with tempfile.TemporaryDirectory() as td:
            rep = audit_cinematic_composition(
                Path(td),
                {"shots": [{"shot_id": "s0", "framing": "CU", "angle": "eye", "move": "push"}]},
                {"overlays": []},
                raw_traces=[{"time": 1.2, "telemetry": {"overlay": {"overlays": [{"overlay_id": "ov_0", "visible": True, "caption_overlap": True, "in_safe_area": True}]}}}],
            )
            self.assertEqual(rep["status"], "FAIL")

        # Duplicate consecutive camera triplet fails progression
        dup_shots = [
            {"shot_id": f"s{i}", "framing": "MS", "angle": "eye", "move": "orbit", "setup_type": f"st{i}", "physical_action": f"act{i}"}
            for i in range(5)
        ]
        prog = score_visual_progression(dup_shots, [])
        self.assertEqual(prog["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
