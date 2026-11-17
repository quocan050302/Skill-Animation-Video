"""Verification Tests for R2.2: Modular 1919 Boston 3D WebGL Scenes, Rupture Impact, Wave Flow & Seek Determinism."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from director.assets import build_locked_engine_workspace
from director.build_storyboard import build_storyboard_and_bible
from director.parse_script import parse_script_and_build_voice
from director.preflight import find_browser_executable
from director.provenance_guard import ProvenanceGuard
from director.route_styles import route_and_lock_style
from director.visual_storytelling_qa import audit_motion_dynamics, audit_story_action_coverage


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"

BOSTON_SHORT_SCRIPT = (
    "In January 1919, people in Boston's North End heard a deep rumble, but nobody expected a flood. "
    "The wave wasn't water, it was molasses. "
    "A massive steel tank on Commercial Street had been leaking for years before those tank walls finally gave way. "
    "More than 2.3 million gallons poured out at roughly 35 miles per hour, striking the elevated railway. "
    "Twenty-one people died and about 150 were injured, forcing engineers to tighten rules on steel construction."
)


class TestBostonMolassesScenes(unittest.TestCase):
    def tearDown(self) -> None:
        ProvenanceGuard.deactivate()

    def test_modular_scenes_render_actions_and_cutaway_in_webgl(self) -> None:
        browser_exe = find_browser_executable()
        self.assertIsNotNone(browser_exe, "Chromium/Edge WebGL executable required")

        with tempfile.TemporaryDirectory() as td:
            rd = Path(td)
            prompt = f"/short-director --skill zach-d-films {BOSTON_SHORT_SCRIPT}"
            dec, cleaned, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill="zach-d-films", upstream_sha="test")
            ps = parse_script_and_build_voice(cleaned, "zach-d-films", rd, KIT_DIR, voice_mode="off")
            sb = build_storyboard_and_bible(ps, dec, rd, fps=30, seed=42, caption_mode="kinetic", callout_mode="smart")
            ep = build_locked_engine_workspace("zach-d-films", PROJECT_ROOT, rd, sb, ps)

            work_dir = Path(ep["work_dir"])
            bm_js = work_dir / "src" / "boston_molasses_scenes.js"
            self.assertTrue(bm_js.exists())
            bm_txt = bm_js.read_text(encoding="utf-8")
            for sym in (
                "makeNorthEndStreet1919",
                "makeMolassesStorageTank1919",
                "makeSeamLeakAndRivetFailureRig",
                "makeMolassesGravityCurrentRig",
                "makeElevatedRailAndStreetImpactRig",
                "makePeriodCrowdActionRig",
                "makeRescueAndAftermathRig",
                "makeBostonLocationOverview",
                "getNarrativeActionTelemetry",
                "computeAnchorsTelemetry",
            ):
                self.assertIn(sym, bm_txt, f"Missing composable helper {sym} in boston_molasses_scenes.js")

            # Sample start & end of key shots to inspect true 3D action telemetry & camera travel
            shots = sb["shots"]
            sample_ts = []
            for s in shots:
                t_a = round(float(s["start"]) + 0.15, 3)
                t_b = round(max(t_a + 0.1, float(s["end"]) - 0.18), 3)
                sample_ts.extend([t_a, t_b])
            times_csv = ",".join(f"{t:.3f}" for t in sample_ts)

            render_mjs = PROJECT_ROOT / "director" / "render_node.mjs"
            env = os.environ.copy()
            env["PLAYWRIGHT_CHROME_PATH"] = browser_exe

            tr_res = subprocess.run(
                ["node", str(render_mjs), "trace", ep["entry_html"], times_csv, "1", "d3d11"],
                capture_output=True, text=True, check=True, env=env,
            )
            traces = json.loads([l for l in tr_res.stdout.splitlines() if l.startswith("{")][-1])["traces"]
            sag = json.loads((rd / "story_action_graph.json").read_text(encoding="utf-8"))

            # Verify story action coverage & camera/scene dynamics directly on real WebGL telemetry
            cov = audit_story_action_coverage(sag, sb, raw_traces=traces)
            self.assertEqual(cov["status"], "PASS", f"Action coverage check failed: {cov}")
            dyn = audit_motion_dynamics(sb, raw_traces=traces)
            self.assertEqual(dyn["status"], "PASS", f"Motion dynamics check failed: {dyn}")

            # Verify rupture progression occurs across rupture shot (`0 -> >0.25`)
            rup_vals = [
                float(((((r.get("telemetry") or {}).get("narrative_action") or {}).get("structural_state") or {}).get("ruptureProgress")) or 0.0)
                for r in traces
                if ((r.get("telemetry") or {}).get("narrative_action") or {}).get("physical_action") == "tank_panel_rupture"
            ]
            self.assertTrue(rup_vals, "Expected tank_panel_rupture shot telemetry")
            self.assertGreater(max(rup_vals) - min(rup_vals), 0.25, f"Tank did not rupture visibly: {rup_vals}")

            # Verify continuous viscous surface & grounded crowd telemetry
            wave_phys = [
                (r.get("telemetry") or {}).get("physical_motion")
                for r in traces
                if isinstance((r.get("telemetry") or {}).get("physical_motion"), dict)
            ]
            self.assertTrue(wave_phys, "Expected Boston continuous viscous wave physical_motion telemetry")
            self.assertTrue(all(w.get("surface_mode") == "continuous_viscous_heightfield" for w in wave_phys))
            self.assertGreater(max(float(w.get("vertex_disp_max_m") or 0.0) for w in wave_phys), 0.05)

            char_rows = [
                {
                    "shot_id": r.get("shot_id") or (r.get("telemetry") or {}).get("shot_id"),
                    "time_sec": r["time"],
                    **(r["telemetry"]["character_performance"]),
                }
                for r in traces
                if isinstance((r.get("telemetry") or {}).get("character_performance"), dict)
            ]
            self.assertTrue(char_rows, "Expected Boston grounded character_performance telemetry")
            from director.character_performance import validate_character_grounding
            self.assertEqual(validate_character_grounding(char_rows, require_motion=True)["status"], "PASS")

            # Render two distinct stills & confirm non-flat distinct geometry (seek determinism + visual variety)
            st_dir = rd / "stills_check"
            t_pick_a = f"{sample_ts[0]:.3f}"
            t_pick_b = f"{sample_ts[min(len(sample_ts) - 1, 5)]:.3f}"
            subprocess.run(
                ["node", str(render_mjs), "stills", ep["entry_html"], str(st_dir), f"{t_pick_a},{t_pick_b}", "1", "d3d11"],
                check=True, capture_output=True, env=env,
            )
            img_a = np.asarray(Image.open(st_dir / f"still_{t_pick_a}.png").convert("RGB"), dtype=np.float32)
            img_b = np.asarray(Image.open(st_dir / f"still_{t_pick_b}.png").convert("RGB"), dtype=np.float32)
            self.assertGreater(float(img_a.std()), 10.0)
            self.assertGreater(float(np.abs(img_a - img_b).mean()), 4.5)


if __name__ == "__main__":
    unittest.main()
