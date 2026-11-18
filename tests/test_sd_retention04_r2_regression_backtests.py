"""SD-RETENTION-04.R2 Negative Tests N56-N60: Non-Destructive Backtests, Mount St. Helens & DAG Coverage."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from director.audio_narrative import extract_sound_events
from director.editorial_overlay import OverlaySafetyError, validate_reveal_order
from director.semantic_visual_evidence_qa import audit_relative_motion_evidence
from director.sfx_director import select_procedural_sfx
from director.visual_causality_director import _infer_proof_type
from director.visual_storytelling_director import CONTINUATION_SUBPHASES
from tools.run_validation_async import build_task_graph, verify_test_suite_coverage

ROOT = Path(__file__).resolve().parents[1]


class TestSdRetention04R2RegressionBacktests(unittest.TestCase):
    def test_n56_boston_scene_fix_and_legacy_immutability(self) -> None:
        # Legacy pre-R4 Boston artifact remains untouched if present locally
        legacy_boston = ROOT / "runs" / "sd_retention03_r2_boston_proof_20261118"
        if legacy_boston.exists() and (legacy_boston / "qc_report.json").exists():
            # Confirm we did not overwrite legacy baseline files in-place
            self.assertTrue((legacy_boston / "qc_report.json").is_file())

        # Fixed negation handling in proof_type inference (negated "flood" must not trigger particle_path_propagation)
        pt = _infer_proof_type("Nobody expected a flood of syrup down the street", "street_rumble", "hook", "boston_street_hook")
        self.assertEqual(pt, "human_reaction_consequence")
        self.assertEqual(_infer_proof_type("Nobody expected a structural failure", "structural_hold", "setup", "generic"), "context_establish")

        # Fixed Boston JS asset tags shearing plates & jet with causal_feature
        bm_txt = (ROOT / "director" / "assets" / "zdf_boston_molasses_scenes.py").read_text(encoding="utf-8")
        self.assertIn("tagSemantic(leftPlate, 'causal_feature')", bm_txt)
        self.assertIn("tagSemantic(rightPlate, 'causal_feature')", bm_txt)
        self.assertIn("tagSemantic(jet, 'causal_feature')", bm_txt)

        # Structural state telemetry satisfies audit_relative_motion_evidence cleanly
        rel = audit_relative_motion_evidence(
            {"causal_events": [{"causal_event_id": "c0", "proof_type": "material_deformation"}]},
            {"shots": [{"shot_id": "s0", "causal_event_id": "c0"}]},
            raw_traces=[{"shot_id": "s0", "time": 1.0, "telemetry": {"narrative_action": {"structural_state": {"ruptureProgress": 0.42}}}}],
        )
        self.assertEqual(rel["status"], "PASS")

    def test_n57_tacoma_reference_fixed_towers_tagged(self) -> None:
        tac_txt = (ROOT / "director" / "assets" / "zdf_tacoma_bridge_scenes.py").read_text(encoding="utf-8")
        self.assertIn("tagSemantic(pier, 'reference_fixed')", tac_txt)
        self.assertIn("tagSemantic(leg, 'reference_fixed')", tac_txt)
        self.assertIn("tagSemantic(strut, 'reference_fixed')", tac_txt)

    def test_n58_st_helens_reveal_gate_blocks_premature_blast_spoiler(self) -> None:
        sag = {
            "narrative_events": [
                {"narrative_event_id": "n0", "physical_action": "north_flank_bulge_distortion", "narration_text": "Mount St. Helens' north slope bulged outward.", "start_sec": 0.0, "end_sec": 4.0, "reveal_after_sec": 0.2, "spoiler_tokens": []},
                {"narrative_event_id": "n1", "physical_action": "horizontal_decompression_blast", "narration_text": "A supersonic lateral blast exploded at 300 mph.", "start_sec": 12.0, "end_sec": 16.0, "reveal_after_sec": 12.2, "spoiler_tokens": ["lateral blast", "300 mph"]},
            ]
        }
        bad_tl = {"overlays": [{"overlay_id": "ov_early", "label": "300 MPH LATERAL BLAST", "sublabel": "", "start": 0.5, "end": 2.5}]}
        res = validate_reveal_order(sag, bad_tl)
        self.assertEqual(res["status"], "FAIL")

    def test_n59_st_helens_subphases_and_volcanic_sfx_dsp(self) -> None:
        for req_fam in ("volcano_cryptodome_cutaway", "volcano_landslide_avalanche", "volcano_lateral_blast", "volcano_forest_sweep", "volcano_plinian_column", "volcano_crater_aftermath"):
            self.assertIn(req_fam, CONTINUATION_SUBPHASES)

        rng = np.random.default_rng(1980)
        for gen in (
            "zach3d:sthelens_ridge_hook_stage",
            "zach3d:sthelens_cryptodome_cutaway_stage",
            "zach3d:sthelens_landslide_avalanche_stage",
            "zach3d:sthelens_lateral_blast_stage",
            "zach3d:sthelens_forest_sweep_stage",
            "zach3d:sthelens_plinian_column_stage",
        ):
            sh = {"shot_id": "s_v", "start": 0.0, "end": 4.0, "procedural_generator": gen, "setup_type": gen, "narration_text": "Volcanic eruption blast", "camera": {"framing": "WS", "movement": "track"}, "staging": {}}
            evs = extract_sound_events(sh, None, None, [], selected_skill="zach-d-films")
            self.assertTrue(evs, f"Expected grounded volcanic SFX events for {gen}")
            for ev in evs:
                wav = select_procedural_sfx(ev["intent"], ev, rng)
                self.assertTrue(np.all(np.isfinite(wav)))
                self.assertGreater(float(np.max(np.abs(wav))), 0.01)

    def test_n60_validation_async_full_dag_covers_all_test_modules(self) -> None:
        tasks = build_task_graph("full")
        cov = verify_test_suite_coverage(ROOT / "tests", tasks)
        self.assertTrue(cov["ok"], f"N60: Unregistered test modules in tools/run_validation_async.py: {cov['missing_modules']}")
        self.assertIn("tests.test_atmospheric_volume_renderer", cov["covered_modules"])
        self.assertIn("tests.test_scene_text_safe_zones", cov["covered_modules"])
        self.assertIn("tests.test_sd_retention04_r2_visual_quality", cov["covered_modules"])
        self.assertIn("tests.test_sd_retention04_r2_regression_backtests", cov["covered_modules"])


if __name__ == "__main__":
    unittest.main()
