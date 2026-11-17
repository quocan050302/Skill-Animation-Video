"""Verification Tests for Step 6 & E2E: 3-Pane Airplane Window WebGL Assembly, Determinism & Remux Guard (N13)."""

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
from director.retention_qa import audit_prosody_delivery, run_retention_editorial_qa
from director.route_styles import route_and_lock_style


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"


class TestRetentionE2E(unittest.TestCase):
    def tearDown(self) -> None:
        ProvenanceGuard.deactivate()

    def test_airplane_window_3pane_webgl_cutaway_and_seed_determinism(self) -> None:
        browser_exe = find_browser_executable()
        self.assertIsNotNone(browser_exe)
        prompt = (
            "/short-director --skill zach-d-films "
            "Why is there a tiny hole in an airplane window? "
            "An airplane window has three layers: outer pane, middle pane, and inner scratch pane. "
            "Wait, what if that outer pane fails? Then the middle fail-safe pane vents moisture!"
        )
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td)
            dec, cleaned, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill="zach-d-films", upstream_sha="test")
            ps = parse_script_and_build_voice(cleaned, "zach-d-films", rd, KIT_DIR, voice_mode="off")
            sb = build_storyboard_and_bible(ps, dec, rd, fps=30, seed=101, edit_energy="dynamic", scene_novelty="high")
            ep = build_locked_engine_workspace("zach-d-films", PROJECT_ROOT, rd, sb, ps)

            gens = {s["procedural_generator"] for s in sb["shots"]}
            self.assertIn("zach3d:airplane_window_hole_stage", gens)

            render_mjs = PROJECT_ROOT / "director" / "render_node.mjs"
            env = os.environ.copy()
            env["PLAYWRIGHT_CHROME_PATH"] = browser_exe

            # Sample trace across all shots: check real LayeredCutaway layers_count & anchor projection
            mid_times = [round(0.5 * (float(s["start"]) + float(s["end"])), 4) for s in sb["shots"]]
            t_arg = ",".join(str(x) for x in mid_times)
            tr1 = subprocess.run(
                ["node", str(render_mjs), "trace", ep["entry_html"], t_arg, "1", "d3d11"],
                capture_output=True, text=True, check=True, env=env,
            )
            traces = json.loads([l for l in tr1.stdout.splitlines() if l.startswith("{")][-1])["traces"]
            self.assertGreaterEqual(len(traces), len(sb["shots"]))
            for rec in traces:
                cw = rec["telemetry"]["cutaway"]
                self.assertIsNotNone(cw)
                self.assertGreaterEqual(cw["layers_count"], 4)
                self.assertEqual(cw["components_count"], 3)
                self.assertIn("middle_bleed_hole", rec["telemetry"]["anchors"])

            # Verify identical seeded PNG hashes across back-to-back renders (N13 determinism)
            h1_res = subprocess.run(
                ["node", str(render_mjs), "hashes", ep["entry_html"], "30", "0", "8", "1", "d3d11"],
                capture_output=True, text=True, check=True, env=env,
            )
            h2_res = subprocess.run(
                ["node", str(render_mjs), "hashes", ep["entry_html"], "30", "0", "8", "1", "d3d11"],
                capture_output=True, text=True, check=True, env=env,
            )
            h1 = json.loads([l for l in h1_res.stdout.splitlines() if l.startswith("{")][-1])["hashes"]
            h2 = json.loads([l for l in h2_res.stdout.splitlines() if l.startswith("{")][-1])["hashes"]
            self.assertEqual([x["sha256"] for x in h1], [x["sha256"] for x in h2])

            # Negative trap N13 / G20: Ensure retention QA never fabricates verified subjective status
            dummy_vid = rd / "fake_vid.mp4"
            dummy_vid.write_bytes(b"")
            qa = run_retention_editorial_qa(rd, dummy_vid, sb, parsed_script=ps, raw_traces=traces)
            self.assertEqual(qa["overall_status"], "FAIL")  # zero-byte video fails closed
            self.assertEqual(qa["subjective_voice_quality_status"], "NOT_VERIFIED")
            self.assertEqual(qa["viewer_retention_status"], "NOT_VERIFIED")
            self.assertEqual(audit_prosody_delivery(rd, parsed_script=ps)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
