"""Verification Tests for Grounded Character Performance & Foot-Lock (G15-G16, N17-N20)."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from director.assets import build_locked_engine_workspace
from director.build_storyboard import build_storyboard_and_bible
from director.character_performance import (
    plan_character_action,
    validate_character_grounding,
)
from director.parse_script import parse_script_and_build_voice
from director.preflight import find_browser_executable
from director.provenance_guard import ProvenanceGuard
from director.route_styles import route_and_lock_style


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"


class TestCharacterPerformance(unittest.TestCase):
    def tearDown(self) -> None:
        ProvenanceGuard.deactivate()

    def test_g15_character_planner_and_negative_traps_n17_n18_n19(self) -> None:
        p_ret = plan_character_action({"physical_action": "wave_speed_chase_escalation", "duration_sec": 3.5}, {"role": "pedestrian"})
        self.assertEqual(p_ret["primary_intent"], "retreat")
        self.assertIn("retreat", p_ret["phases"])

        p_brk = plan_character_action({"physical_action": "shore_onlooker_react", "duration_sec": 3.0}, {"role": "onlooker"})
        self.assertEqual(p_brk["primary_intent"], "brace")

        # N17: Stance foot slide > 0.08m fails closed
        bad_slide = [{"time_sec": 0.5, "stance_slide_m": 0.14, "left_foot_ground_err_m": 0.0, "right_foot_ground_err_m": 0.0}]
        self.assertEqual(validate_character_grounding(bad_slide, require_motion=False)["status"], "FAIL")

        # N18: Floor penetration > 0.03m fails closed
        bad_pen = [{"time_sec": 0.5, "stance_slide_m": 0.0, "left_foot_ground_err_m": -0.065, "right_foot_ground_err_m": 0.0}]
        self.assertEqual(validate_character_grounding(bad_pen, require_motion=False)["status"], "FAIL")

        # N18: Teleport root jump (> 6.5 m/s) fails closed
        bad_tele = [
            {"time_sec": 0.5, "world_pelvis": [0.0, 0.95, 0.0], "left_foot_ground_err_m": 0.0, "right_foot_ground_err_m": 0.0},
            {"time_sec": 0.6, "world_pelvis": [0.0, 0.95, 2.5], "left_foot_ground_err_m": 0.0, "right_foot_ground_err_m": 0.0},
        ]
        self.assertEqual(validate_character_grounding(bad_tele, require_motion=False)["status"], "FAIL")

        # N19: Retreat moving toward threat (dot > 0.35) fails closed
        bad_dir = [{"time_sec": 1.0, "action_intent": "retreat", "move_toward_threat_dot": 0.85, "left_foot_ground_err_m": 0.0, "right_foot_ground_err_m": 0.0}]
        self.assertEqual(validate_character_grounding(bad_dir, require_motion=False)["status"], "FAIL")

    def test_g16_webgl_foot_contact_non_slide_retreat_and_seek_repeatability(self) -> None:
        browser_exe = find_browser_executable()
        self.assertIsNotNone(browser_exe)
        script = (
            "In January 1919, people in Boston's North End heard a deep rumble, but nobody expected a flood. "
            "The wave wasn't water, it was molasses. "
            "A massive steel tank on Commercial Street had been leaking for years before those tank walls finally gave way. "
            "More than 2.3 million gallons poured out at roughly 35 miles per hour, striking the elevated railway. "
            "Twenty-one people died and about 150 were injured, forcing engineers to tighten rules on steel construction."
        )
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td)
            prompt = f"/short-director --skill zach-d-films {script}"
            dec, cleaned, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill="zach-d-films", upstream_sha="test")
            ps = parse_script_and_build_voice(cleaned, "zach-d-films", rd, KIT_DIR, voice_mode="off")
            sb = build_storyboard_and_bible(ps, dec, rd, fps=30, seed=42, caption_mode="kinetic", callout_mode="smart")
            ep = build_locked_engine_workspace("zach-d-films", PROJECT_ROOT, rd, sb, ps)

            wave_shot = next((s for s in sb["shots"] if s.get("procedural_generator") == "zach3d:boston_wave_street_stage"), None)
            self.assertIsNotNone(wave_shot)
            t0 = round(wave_shot["start"] + 0.08, 3)
            t1 = round(wave_shot["start"] + 0.45, 3)
            t2 = round(wave_shot["start"] + 0.90, 3)
            t3 = round(wave_shot["start"] + 1.45, 3)
            times = [t0, t1, t2, t3]

            render_mjs = PROJECT_ROOT / "director" / "render_node.mjs"
            env = os.environ.copy()
            env["PLAYWRIGHT_CHROME_PATH"] = browser_exe
            tr = subprocess.run(
                ["node", str(render_mjs), "trace", ep["entry_html"], ",".join(f"{t:.3f}" for t in times), "1", "d3d11"],
                capture_output=True, text=True, check=True, env=env,
            )
            traces = json.loads([ln for ln in tr.stdout.splitlines() if ln.startswith("{")][-1])["traces"]
            char_samples = [
                {"time_sec": r["time"], **r["telemetry"]["character_performance"]}
                for r in traces
                if isinstance((r.get("telemetry") or {}).get("character_performance"), dict)
            ]
            self.assertEqual(len(char_samples), len(times))
            audit = validate_character_grounding(char_samples, require_motion=True)
            self.assertEqual(audit["status"], "PASS", f"Grounded locomotion check failed: {audit}")
            self.assertLessEqual(audit["worst_penetration_m"], 0.03)
            self.assertLessEqual(audit["worst_stance_slide_m"], 0.08)
            self.assertLess(char_samples[-1]["move_toward_threat_dot"], -0.4)


if __name__ == "__main__":
    unittest.main()
