"""STEP 8: Unit & Negative Regression Tests for Strict Fail-Closed Style Lock & Fact Gate."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from director.provenance_guard import ProvenanceGuard, StyleLockViolationError
from director.quality_gate import audit_style_lock
from director.route_styles import parse_skill_request, route_and_lock_style
from director.parse_script import analyze_facts_and_entities
from director.preflight import KOKORO_VERIFIED_LANGS


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestStyleLockAndNegativeRegressions(unittest.TestCase):
    def tearDown(self) -> None:
        ProvenanceGuard.deactivate()

    def test_explicit_parsing_variants(self) -> None:
        m1, s1, txt1 = parse_skill_request("/short-director --skill stick-figure Why do cats purr?")
        self.assertEqual((m1, s1, txt1), ("explicit", "stick-figure", "Why do cats purr?"))

        m2, s2, txt2 = parse_skill_request("Skill: map-route\nHome to the park, 2.5 km in 8 minutes")
        self.assertEqual((m2, s2), ("explicit", "map-route"))
        self.assertIn("2.5 km", txt2)

        m3, s3, _ = parse_skill_request("Make a short using breakdown style: inside a watch")
        self.assertEqual((m3, s3), ("explicit", "breakdown"))

    def test_unknown_explicit_skill_fails_closed(self) -> None:
        with self.assertRaises(StyleLockViolationError):
            parse_skill_request("/short-director --skill cyber-anime-3d Some script")
        with self.assertRaises(StyleLockViolationError):
            parse_skill_request("Skill: fake-engine\nSome script")

    def test_explicit_mode_blocks_reading_other_five_skill_mds_and_adapters(self) -> None:
        decisions, _, guard = route_and_lock_style(
            project_root=PROJECT_ROOT,
            raw_input="/short-director --skill stick-figure How do geysers erupt?",
            upstream_sha="testsha",
        )
        self.assertEqual(decisions["selection_mode"], "explicit")
        self.assertEqual(decisions["selected_skill"], "stick-figure")

        # Attempting to open another skill's SKILL.md or template MUST fail closed!
        foreign_md = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "skills" / "graph" / "SKILL.md"
        with self.assertRaises(StyleLockViolationError):
            foreign_md.read_text(encoding="utf-8")

        # Attempting to import another skill's adapter MUST fail closed!
        with self.assertRaises(StyleLockViolationError):
            __import__("director.assets.zach_d_films_adapter")

        # Attempting to switch locked skill MUST fail closed!
        with self.assertRaises(StyleLockViolationError):
            guard.lock_to_skill("graph")

    def test_auto_mode_blocks_engine_files_during_capability_scan_and_locks_one(self) -> None:
        guard = ProvenanceGuard.activate(PROJECT_ROOT, selection_mode="auto")
        # Reading SKILL.md during auto_capability_scan is permitted
        _ = (PROJECT_ROOT / "vendor" / "claude-animation-skills" / "skills" / "graph" / "SKILL.md").read_text(encoding="utf-8")
        # Reading template.html or build.py during auto_capability_scan MUST fail closed!
        with self.assertRaises(StyleLockViolationError):
            _ = (PROJECT_ROOT / "vendor" / "claude-animation-skills" / "skills" / "graph" / "template.html").read_text(encoding="utf-8")

    def test_audit_rejects_foreign_shot_asset_import_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work_dir = Path(td) / "engine_work"
            work_dir.mkdir(parents=True)
            js_file = work_dir / "shots.js"
            js_file.write_text("const x = 1; drawStick(ctx, {});\n", encoding="utf-8")

            base_decisions = {
                "selection_mode": "explicit",
                "selected_skill": "stick-figure",
                "style_lock": {
                    "enabled": True,
                    "engine": "stick-figure",
                    "mixing_policy": "forbidden",
                    "fallback_policy": "fail-closed",
                },
                "origin_skills": ["stick-figure"],
            }
            base_sb = {
                "selected_skill": "stick-figure",
                "origin_skills": ["stick-figure"],
                "shots": [{"shot_id": "shot_00", "engine": "stick-figure"}],
                "visual_assets": [{"asset_id": "a0", "origin_skill": "stick-figure", "generator_module": "director/assets/stick_figure_adapter.py"}],
            }
            base_ep = {
                "work_dir": str(work_dir),
                "visual_sources": [str(js_file)],
            }
            clean_guard = {
                "violations": [],
                "opened_skill_files": [],
                "imported_adapter_modules": ["director.assets.stick_figure_adapter"],
                "events": [],
            }

            # Baseline valid passes
            ok_rep = audit_style_lock(base_decisions, base_sb, base_ep, clean_guard)
            self.assertEqual(ok_rep["status"], "PASS")

            # Negative 1: Foreign guest shot engine
            bad_sb_shot = copy.deepcopy(base_sb)
            bad_sb_shot["shots"].append({"shot_id": "shot_01", "engine": "zach-d-films"})
            r1 = audit_style_lock(base_decisions, bad_sb_shot, base_ep, clean_guard)
            self.assertEqual(r1["status"], "FAIL")

            # Negative 2: Foreign visual asset origin_skill
            bad_sb_asset = copy.deepcopy(base_sb)
            bad_sb_asset["visual_assets"][0]["origin_skill"] = "map-route"
            r2 = audit_style_lock(base_decisions, bad_sb_asset, base_ep, clean_guard)
            self.assertEqual(r2["status"], "FAIL")

            # Negative 3: Secondary / fallback engine configured
            bad_dec_fb = copy.deepcopy(base_decisions)
            bad_dec_fb["fallback_skill"] = "minimalistic-graphics"
            r3 = audit_style_lock(bad_dec_fb, base_sb, base_ep, clean_guard)
            self.assertEqual(r3["status"], "FAIL")

            # Negative 4: Foreign code signature / template injected into JS file
            js_file.write_text("import { makeHuman } from 'skills/zach-d-films/engine/src/human.js';\n", encoding="utf-8")
            r4 = audit_style_lock(base_decisions, base_sb, base_ep, clean_guard)
            self.assertEqual(r4["status"], "FAIL")

            # Negative 5: Incomplete audit (missing guard snapshot) -> NOT_VERIFIED, never PASS!
            js_file.write_text("const x = 1;\n", encoding="utf-8")
            r5 = audit_style_lock(base_decisions, base_sb, base_ep, None)
            self.assertEqual(r5["status"], "NOT_VERIFIED")

    def test_graph_rejects_invented_numbers_and_kokoro_rejects_vietnamese_claim(self) -> None:
        # Graph with zero user numbers MUST fail closed (Principle 8)
        with self.assertRaises(ValueError):
            analyze_facts_and_entities(
                raw_script="Our startup grew super fast this year!",
                sentences=["Our startup grew super fast this year."],
                selected_skill="graph",
            )
        # Verify Kokoro v1.0 table never claims Vietnamese support (Principle 7)
        self.assertNotIn("vi", KOKORO_VERIFIED_LANGS)
        self.assertNotIn("vi-vn", KOKORO_VERIFIED_LANGS)

    def test_auto_mode_capability_routing_across_genres(self) -> None:
        prompts = [
            ("Monthly active users grew from 500 in Jan to 2400 in Apr and 19000 in Aug", "graph"),
            ("Home to the gym, 2.8 km in 9 minutes across town", "map-route"),
            ("Exploded view teardown inside a smartwatch: every part labelled", "breakdown"),
            ("Every small step feels quiet until habits compound", "minimalistic-graphics"),
            ("Could steel plate armor stop a high velocity bullet impact?", "zach-d-films"),
            ("Why does your brain feel groggy when you wake up from a long afternoon sleep?", "stick-figure"),
        ]
        for prompt, expected_skill in prompts:
            ProvenanceGuard.deactivate()
            dec, _, guard = route_and_lock_style(PROJECT_ROOT, f"/short-director {prompt}", upstream_sha="test")
            self.assertEqual(dec["selection_mode"], "auto")
            self.assertEqual(dec["selected_skill"], expected_skill, f"Auto route mismatch for: {prompt}")
            self.assertEqual(dec["origin_skills"], [expected_skill])
            self.assertEqual(guard.phase, "locked")
            # Once locked in auto mode, opening any other skill's template MUST fail closed!
            other = "graph" if expected_skill != "graph" else "map-route"
            with self.assertRaises(StyleLockViolationError):
                _ = (PROJECT_ROOT / "vendor" / "claude-animation-skills" / "skills" / other / "template.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
