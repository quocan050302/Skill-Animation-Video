"""Verification Tests for Curiosity Headlines, Smart Pointer Binding & Reveal Locks (G05-G08, N09-N10)."""

from __future__ import annotations

import unittest

from director.curiosity_director import (
    CuriosityPolicyError,
    bind_pointer_and_headline_timing,
    find_curiosity_beats,
    plan_attention_pointer,
    score_editorial_value,
    validate_reveal_lock,
)


class TestCuriosityDirector(unittest.TestCase):
    def test_g05_g06_g07_g08_curiosity_cap_pointer_binding_and_value_score(self) -> None:
        actions = [
            {
                "narrative_event_id": "nev_000",
                "start_sec": 0.0,
                "end_sec": 4.2,
                "physical_action": "bridge_deck_gentle_wave",
                "editorial_intent": "curiosity_hook",
                "required_anchors": ["bridge_midspan_twist"],
                "narration_text": "Drivers crossing this massive suspension bridge saw solid steel bending like a ribbon.",
            },
            {
                "narrative_event_id": "nev_001",
                "start_sec": 4.2,
                "end_sec": 9.0,
                "physical_action": "wide_establish_1940",
                "editorial_intent": "context_establish",
                "required_anchors": ["bridge_midspan_twist"],
                "narration_text": "Tacoma Narrows opened in July 1940 in Washington State.",
            },
            {
                "narrative_event_id": "nev_002",
                "start_sec": 9.0,
                "end_sec": 14.5,
                "physical_action": "plate_girder_vortex",
                "editorial_intent": "mechanism",
                "required_anchors": ["plate_girder_windward"],
                "narration_text": "Solid eight-foot plate girders trapped wind gusts underneath the roadway.",
            },
            {
                "narrative_event_id": "nev_003",
                "start_sec": 14.5,
                "end_sec": 20.0,
                "physical_action": "torsion_deck_twist",
                "editorial_intent": "twist_escalation",
                "required_anchors": ["deck_twist_edge_l"],
                "narration_text": "Then violent twisting torsion rippled from tower to tower.",
            },
        ]

        beats = find_curiosity_beats("Tacoma Narrows suspension bridge started twisting", actions, max_headlines=2)
        self.assertEqual(len(beats), 2)
        self.assertEqual(beats[0]["label"], "THE ROAD / WAS MOVING!")
        self.assertEqual(beats[1]["label"], "THEN IT / STARTED TWISTING")

        # Smart pointer planning & contact binding
        ptrs = [plan_attention_pointer({**b, "required_anchors": [b["target_anchor_id"]]}) for b in beats]
        self.assertEqual(ptrs[0]["pointer_shape"], "impact_arrow")
        self.assertEqual(ptrs[0]["anchor_id"], "bridge_midspan_twist")
        self.assertEqual(ptrs[1]["anchor_id"], "deck_twist_edge_l")

        timed = bind_pointer_and_headline_timing(
            [
                {**beats[0], **ptrs[0], "overlay_id": "ov_00", "start": 0.2, "end": 2.3},
                {**beats[1], **ptrs[1], "overlay_id": "ov_01", "start": 14.7, "end": 16.9},
            ],
            words=[
                {"w": "twisting", "s": 14.6, "e": 15.0},
            ],
            story_actions=actions,
            contact_schedule=[{"narrative_event_id": "nev_003", "hit_time_sec": 15.1}],
        )
        self.assertEqual(len(timed), 2)
        self.assertGreaterEqual(timed[1]["start"], 14.95)

        val_ok = score_editorial_value(timed[0], actions[0], actions, prior_candidates=[])
        self.assertTrue(val_ok["keep"])
        self.assertEqual(val_ok["rules"]["spoiler_penalty"], 0.0)

        # N04 pointer lacking physical feature fails closed
        with self.assertRaises(CuriosityPolicyError):
            plan_attention_pointer({"narrative_event_id": "nev_x", "role": "warning_danger", "target_anchor_id": "stage_center"})

    def test_negative_traps_n09_n10_early_spoiler_and_duplicate_headline(self) -> None:
        actions = [
            {"narrative_event_id": "nev_000", "start_sec": 0.0, "end_sec": 4.0, "physical_action": "hook", "narration_text": "Watch this bridge move"},
            {"narrative_event_id": "nev_003", "start_sec": 15.0, "end_sec": 20.0, "physical_action": "torsion_twist", "narration_text": "Then it started twisting"},
            {"narrative_event_id": "nev_006", "start_sec": 28.0, "end_sec": 34.0, "physical_action": "span_collapse_plunge", "narration_text": "Finally the center span collapsed"},
        ]

        # N09: Early twist/collapse reveal before beat time MUST FAIL
        bad_early = validate_reveal_lock(
            [{"overlay_id": "ov_00", "role": "curiosity_headline", "label": "THEN IT / STARTED TWISTING", "start": 2.0}],
            actions,
        )
        self.assertEqual(bad_early["status"], "FAIL")

        bad_collapse = validate_reveal_lock(
            [{"overlay_id": "ov_00", "role": "warning_danger", "label": "SPAN COLLAPSED", "start": 10.0}],
            actions,
        )
        self.assertEqual(bad_collapse["status"], "FAIL")

        # N10: Duplicate headline repeated within 5s MUST FAIL
        bad_dup = validate_reveal_lock(
            [
                {"overlay_id": "ov_00", "role": "curiosity_headline", "label": "THE ROAD / WAS MOVING!", "start": 0.3},
                {"overlay_id": "ov_01", "role": "curiosity_headline", "label": "THE ROAD / WAS MOVING!", "start": 3.1},
            ],
            actions,
        )
        self.assertEqual(bad_dup["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
