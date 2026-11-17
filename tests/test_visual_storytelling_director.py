"""Verification Tests for R2.1: Story-Driven Visual Action Graph, World-State Causality, Reveal Order & Period Integrity."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from director.build_storyboard import build_storyboard_and_bible
from director.editorial_overlay import OverlaySafetyError, build_editorial_timeline
from director.parse_script import parse_script_and_build_voice
from director.preflight import verify_language_voice_support
from director.provenance_guard import ProvenanceGuard
from director.route_styles import route_and_lock_style
from director.visual_event_graph import extract_semantic_visual_events
from director.visual_storytelling_director import (
    NarrativeCausalityError,
    plan_story_action_graph,
    score_story_diversity,
    validate_narrative_causality,
    validate_reveal_order,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"


BOSTON_SCRIPT = (
    "In January 1919, people in Boston's North End heard a deep rumble, but nobody expected a flood. "
    "The wave roaring down the street wasn't water, it was molasses. "
    "High above Commercial Street stood a massive steel tank that had been leaking for years. "
    "On the afternoon of January 15th, those tank walls finally gave way. "
    "More than 2.3 million gallons of thick dark syrup poured across the neighborhood. "
    "Moving faster than a racehorse at roughly 35 miles per hour, the surge outran crowded streets. "
    "It smashed buildings, buckled an elevated railway support, and trapped fleeing workers in heavy syrup. "
    "Twenty-one people died and about 150 were injured. "
    "Investigators later blamed severe problems in the tank's steel and construction. "
    "The Great Molasses Flood became a grim milestone that forced engineers to tighten structural rules."
)


class TestVisualStorytellingDirector(unittest.TestCase):
    def tearDown(self) -> None:
        ProvenanceGuard.deactivate()

    def test_boston_1919_story_action_graph_and_storyboard_routing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td)
            prompt = f"/short-director --skill zach-d-films {BOSTON_SCRIPT}"
            dec, cleaned, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill="zach-d-films", upstream_sha="test")
            ps = parse_script_and_build_voice(cleaned, "zach-d-films", rd, KIT_DIR, voice_mode="off")
            sb = build_storyboard_and_bible(
                ps, dec, rd, fps=30, seed=42, caption_mode="kinetic", callout_mode="smart"
            )
            self.assertTrue((rd / "story_action_graph.json").exists())
            sag = json.loads((rd / "story_action_graph.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(sag["unique_actions_count"], 6)
            self.assertGreaterEqual(sag["unique_locations_count"], 5)
            self.assertEqual(sag["period_year"], 1919)

            # Distinct location/generator variety (never one tank filmed 10 ways)
            gens = [s["procedural_generator"] for s in sb["shots"]]
            self.assertIn("zach3d:boston_street_hook_stage", gens)
            self.assertIn("zach3d:boston_tank_rupture_stage", gens)
            self.assertIn("zach3d:boston_wave_street_stage", gens)
            self.assertIn("zach3d:boston_elevated_rail_impact_stage", gens)
            self.assertIn("zach3d:boston_engineering_cutaway_stage", gens)
            self.assertIn("zach3d:boston_rescue_aftermath_stage", gens)

            # N01: Desktop voice capability truth check
            ok, backend, vid, _ = verify_language_voice_support("en", KIT_DIR)
            self.assertTrue(ok)
            if backend == "windows_sapi":
                self.assertIn("Microsoft", vid)

            # Reveal order lock passes cleanly (never reveals "MOLASSES" in shot 0 hook!)
            ed_tl = json.loads((rd / "editorial_timeline.json").read_text(encoding="utf-8"))
            rev = validate_reveal_order(sag, ed_tl, words=ps["voice"]["words"])
            self.assertEqual(rev["status"], "PASS", f"Early reveal violation: {rev}")
            if ed_tl["overlays"]:
                self.assertNotIn("molasses", ed_tl["overlays"][0]["label"].lower())

    def test_negative_traps_n04_n05_n06_n07(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td)
            prompt = f"/short-director --skill zach-d-films {BOSTON_SCRIPT}"
            dec, cleaned, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill="zach-d-films", upstream_sha="test")
            ps = parse_script_and_build_voice(cleaned, "zach-d-films", rd, KIT_DIR, voice_mode="off")
            vg = extract_semantic_visual_events(ps, selected_skill="zach-d-films")
            sag = plan_story_action_graph(ps, vg)

            # N04: Repeated unchanged world-state over >= 4 consecutive shots MUST FAIL
            cloned_events = [dict(sag["narrative_events"][0], source_event_id=f"ev_{k}") for k in range(5)]
            fake_shots = [
                {"shot_id": f"shot_{k:02d}", "index": k, "event_ids": [f"ev_{k}"], "setup_type": f"cam_{k}", "duration": 2.5}
                for k in range(5)
            ]
            div = score_story_diversity(fake_shots, {"narrative_events": cloned_events})
            self.assertEqual(div["status"], "FAIL")

            # N05: Overlay revealing "MOLASSES" at t=0.1s before spoken word MUST FAIL
            spoiled_tl = {
                "overlays": [{"overlay_id": "ov_spoiler", "label": "RAW MOLASSES SURGE", "start": 0.1, "end": 1.6}]
            }
            self.assertEqual(validate_reveal_order(sag, spoiled_tl, words=ps["voice"]["words"])["status"], "FAIL")

            # N06: Causal inversion (wave surge before tank rupture) MUST FAIL
            inv_events = list(sag["narrative_events"])
            idx_rup = next(i for i, e in enumerate(inv_events) if e["physical_action"] == "tank_panel_rupture")
            idx_wave = next(i for i, e in enumerate(inv_events) if e["physical_action"] == "molasses_wave_surge")
            inv_events[idx_rup], inv_events[idx_wave] = inv_events[idx_wave], inv_events[idx_rup]
            c_res = validate_narrative_causality({**sag, "narrative_events": inv_events}, {"shots": []})
            self.assertEqual(c_res["status"], "FAIL")

            # N07: Period anachronism (smartphone or Roman arena inside 1919 shot) MUST FAIL
            bad_sb = {
                "shots": [{
                    "shot_id": "shot_02",
                    "procedural_generator": "zach3d:human_device_stage",
                    "staging": {"grounded_props": ["phone_screen"]},
                }]
            }
            p_res = validate_narrative_causality(sag, bad_sb)
            self.assertEqual(p_res["status"], "FAIL")

    def test_generalization_across_mixed_non_boston_topics(self) -> None:
        topics = [
            "Why do airplane windows have a tiny bleed hole? Three layers hold pressure safely!",
            "You press an elevator button. Inside the controller cabinet, relays command the traction motor before doors open.",
        ]
        for idx, txt in enumerate(topics):
            with tempfile.TemporaryDirectory() as td:
                rd = Path(td)
                prompt = f"/short-director --skill zach-d-films {txt}"
                dec, cleaned, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill="zach-d-films", upstream_sha="test")
                ps = parse_script_and_build_voice(cleaned, "zach-d-films", rd, KIT_DIR, voice_mode="off")
                sb = build_storyboard_and_bible(ps, dec, rd, fps=30, seed=10 + idx)
                self.assertEqual(sb["causality_check"]["status"], "PASS")
                self.assertIsNone(sb["story_action_graph"]["period_year"])


if __name__ == "__main__":
    unittest.main()
