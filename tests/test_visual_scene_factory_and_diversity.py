"""STEP 8 Rendered 3D Cutaway, Transition Verification, Determinism & Scene Diversity QA Tests (C, F, G, L)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from director.assets.zach_d_films_adapter import generate_engine_project
from director.build_storyboard import build_storyboard_and_bible
from director.preflight import run_preflight
from director.provenance_guard import ProvenanceGuard
from director.render_scene import _run_render_node
from director.run import execute_short_director_run


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestVisualSceneFactoryAndDiversity(unittest.TestCase):
    def test_f_c_zach_3d_device_cutaway_pixels_and_determinism(self) -> None:
        """Render non-Roman 3D device cutaway + ocean fiber + cosmos stills via Metal/WebGL; verify genuine separation & seed hash parity."""
        from tests.test_visual_event_and_coverage import _make_mock_parsed_script

        sentences = [
            "Your finger taps send on a glowing phone screen.",
            "Inside the glass shell, copper circuit traces carry voltage pulses.",
            "Then subsea fiber cables guide laser light before atoms trace back to cosmic stars.",
        ]
        parsed = _make_mock_parsed_script(sentences)
        sd = {
            "selection_mode": "explicit",
            "selected_skill": "zach-d-films",
            "style_lock": {"enabled": True, "engine": "zach-d-films", "mixing_policy": "forbidden", "fallback_policy": "fail-closed"},
            "origin_skills": ["zach-d-films"],
        }

        pf = run_preflight(PROJECT_ROOT, selected_skill="zach-d-films")
        self.assertTrue(pf.ok, pf.errors)

        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            sb = build_storyboard_and_bible(
                parsed, sd, run_dir, fps=30, seed=108,
                edit_energy="dynamic", scene_novelty="high", transition_policy="motivated",
            )
            # Ensure cutaway shot exists cleanly & NO Roman code was emitted in shots.js
            guard = ProvenanceGuard.activate(PROJECT_ROOT, selection_mode="explicit", selected_skill="zach-d-films")
            try:
                eng = generate_engine_project(PROJECT_ROOT, run_dir, sb, parsed)
                shots_js = (run_dir / "engine_work" / "src" / "shots.js").read_text(encoding="utf-8")
                self.assertNotIn("romanHelmet", shots_js)
                self.assertNotIn("arenaStage", shots_js)
                self.assertIn("makeSmartphoneRig", shots_js)
                self.assertIn("makeSubseaCableRig", shots_js)

                cut_shot = next((s for s in sb["shots"] if "cutaway" in s["setup_type"] or "cutaway" in s.get("procedural_generator", "")), sb["shots"][1])
                t_a = round(float(cut_shot["start"]) + 0.05, 3)
                t_b = round(0.5 * (float(cut_shot["start"]) + float(cut_shot["end"])), 3)
                render_mjs = PROJECT_ROOT / "director" / "render_node.mjs"
                _run_render_node(
                    "node", render_mjs,
                    ["stills", eng["entry_html"], str(run_dir / "stills"), f"{t_a:.3f},{t_b:.3f}", "1", pf.webgl_backend],
                    pf.browser_executable, run_dir / "stills.log",
                )
                pa = np.asarray(Image.open(run_dir / "stills" / f"still_{t_a:.3f}.png").convert("RGB"), dtype=np.float32)
                pb = np.asarray(Image.open(run_dir / "stills" / f"still_{t_b:.3f}.png").convert("RGB"), dtype=np.float32)
                mad_cutaway = float(np.abs(pb - pa).mean())
                self.assertGreater(mad_cutaway, 1.5, f"Cutaway glass shell peel showed negligible pixel diff ({mad_cutaway:.3f})")

                # Determinism hash check: exact SHA-256 parity across two seeded invocations on first 4 frames
                h1 = _run_render_node("node", render_mjs, ["hashes", eng["entry_html"], "30", "0", "4", "1", pf.webgl_backend], pf.browser_executable, run_dir / "h1.log")
                h2 = _run_render_node("node", render_mjs, ["hashes", eng["entry_html"], "30", "0", "4", "1", pf.webgl_backend], pf.browser_executable, run_dir / "h2.log")
                self.assertEqual([x["sha256"] for x in h1["hashes"]], [x["sha256"] for x in h2["hashes"]])
            finally:
                ProvenanceGuard.deactivate()

    def test_g_l_full_e2e_non_roman_zach_with_diversity_qa_and_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "zdf_visual_e2e"
            prompt = (
                "Your thumb taps send on a glowing phone screen. "
                "Inside the chassis, a circuit chip sends currents racing to a tall radio tower. "
                "Deep beneath the ocean, subsea fiber cables flash light into a data center powered by stars."
            )
            manifest = execute_short_director_run(
                raw_prompt=prompt,
                out_dir=out_dir,
                cli_skill="zach-d-films",
                fps=30,
                seed=314,
                render_4k_mode="upscale",  # fast bounded smoke in unit suite; full native 4K tested in Step 9 demo
                edit_energy="dynamic",
                scene_novelty="high",
                transition_policy="motivated",
                voice_mode="auto",
            )
            self.assertTrue(manifest["delivered"])
            self.assertEqual(manifest["selected_skill"], "zach-d-films")

            # Verify all SD-VISUAL-01 artifacts exist & passed QC
            for fname in (
                "visual_events.json",
                "shot_coverage.json",
                "camera_paths.json",
                "transition_edl.json",
                "scene_diversity_report.json",
                "style_lock_audit.json",
                "qc_report.json",
            ):
                self.assertTrue((out_dir / fname).exists(), f"Missing artifact {fname}")

            edl = json.loads((out_dir / "transition_edl.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(edl["transitions_count"], 4)
            for tr in edl["transitions"]:
                self.assertTrue(tr["executed_in_renderer"])
                self.assertEqual(tr["verification_status"], "VERIFIED_DECODED", tr)

            div = json.loads((out_dir / "scene_diversity_report.json").read_text(encoding="utf-8"))
            self.assertIn(div["overall_status"], ("PASS", "WARN"), div)
            self.assertEqual(div["subjective_visual_review"], "NOT_VERIFIED")
            self.assertEqual(div["checks"]["adjacent_repetition_guard"]["hard_clone_count"], 0, div)
            self.assertEqual(div["checks"]["visual_skill_lock"]["status"], "PASS")
            self.assertGreaterEqual(div["checks"]["scene_novelty_metrics"]["unique_setups"], 4)


if __name__ == "__main__":
    unittest.main()
