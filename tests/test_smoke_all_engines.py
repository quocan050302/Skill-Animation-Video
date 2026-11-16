"""STEP 8 (Acceptance Tests A & H): Smoke Tests Across All 6 Engines + Upstream Isolation Check."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from director.run import execute_short_director_run


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestAllEnginesSmokeAndUpstreamIsolation(unittest.TestCase):
    def test_upstream_repo_unmodified_and_standalone_prepare_works(self) -> None:
        upstream_dir = PROJECT_ROOT / "vendor" / "claude-animation-skills"
        st = subprocess.run(["git", "status", "--porcelain"], cwd=str(upstream_dir), capture_output=True, text=True, check=True)
        self.assertEqual(st.stdout.strip(), "", "Upstream tracked files must remain KEPT AS IS (0 modifications)")

        # Verify upstream kit/anim.py load_spec + prepare still work standalone in isolation
        with tempfile.TemporaryDirectory() as td:
            spec_p = Path(td) / "demo.graph.json"
            spec_p.write_text(json.dumps({"label": "Users", "values": [10, 25, 80]}), encoding="utf-8")
            code = (
                "import sys; from pathlib import Path; "
                f"sys.path.insert(0, {str(upstream_dir / 'kit')!r}); "
                "import anim; "
                f"s = anim.load_spec({str(spec_p)!r}, {{'label':'','values':None,'labels':[],'final':None,'prefix':'','suffix':'','decimals':0,'dark':False}}); "
                f"anim.prepare(Path({str(upstream_dir / 'skills/graph/template.html')!r}), s, 4.0, Path({str(Path(td) / 'work')!r}), False); "
                f"assert (Path({str(Path(td) / 'work/index.html')!r})).exists()"
            )
            subprocess.run([sys.executable, "-c", code], check=True)

    def test_remaining_five_engines_smoke_renders(self) -> None:
        cases = [
            ("graph", "Monthly revenue climbed from 4000 in Jan to 9500 in Apr, 22000 in Jul, and 61000 in Oct."),
            ("minimalistic-graphics", "Tiny daily habits feel invisible until one quiet morning they compound."),
            ("map-route", "Walk from Old Square to Cedar Pier, 2.4 km in 8 minutes across the river."),
            ("breakdown", "Espresso portafilter: dispersion screen, tamped puck, precision basket, brass manifold, thermal collar, walnut grip."),
            ("zach-d-films", "Could layered copper and steel plates absorb a high speed kinetic strike? Let us test the force ripple."),
        ]
        with tempfile.TemporaryDirectory() as td:
            for skill_name, prompt in cases:
                out_dir = Path(td) / f"smoke_{skill_name}"
                manifest = execute_short_director_run(
                    raw_prompt=prompt,
                    out_dir=out_dir,
                    cli_skill=skill_name,
                    fps=30,
                    seed=99,
                    render_4k_mode="upscale",  # Fast smoke mode, verifies honest upscale declaration too!
                )
                self.assertTrue(manifest["delivered"], f"Smoke test failed delivery for {skill_name}")
                self.assertEqual(manifest["selected_skill"], skill_name)
                self.assertEqual(manifest["origin_skills"], [skill_name])
                self.assertFalse(manifest["video_contract"]["native_4k"])
                self.assertIn("upscaled", manifest["video_contract"]["delivery_4k_declaration"])

                audit = json.loads((out_dir / "style_lock_audit.json").read_text(encoding="utf-8"))
                self.assertEqual(audit["status"], "PASS")
                self.assertEqual(audit["violations"], [])

                qc = json.loads((out_dir / "qc_report.json").read_text(encoding="utf-8"))
                self.assertIn(qc["overall_status"], ("PASS", "WARN"))


if __name__ == "__main__":
    unittest.main()
