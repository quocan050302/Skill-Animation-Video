"""SD-RETENTION-04.R2 Negative Tests N41-N45: Volumetric-Like Atmosphere Renderer & Continuity."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from director.assets.zach_d_films_adapter import generate_engine_project
from director.build_storyboard import build_storyboard_and_bible
from director.parse_script import parse_script_and_build_voice
from director.preflight import run_preflight
from director.render_scene import _run_render_node
from director.route_styles import route_and_lock_style
from director.semantic_visual_evidence_qa import audit_smoke_geometry_and_continuity

ROOT = Path(__file__).resolve().parents[1]
KIT_DIR = ROOT / "vendor" / "claude-animation-skills" / "kit"


class TestAtmosphericVolumeRenderer(unittest.TestCase):
    def test_n41_n42_n43_n45_smoke_geometry_continuity_matte_and_honesty_traps(self) -> None:
        sb = {"shots": [{"shot_id": "shot_00", "procedural_generator": "zach3d:london_coal_combustion_cutaway_stage"}]}

        # N41: Exposed low-poly dodecahedron / sphere smoke primitives must FAIL closed
        bad_n41 = [{"time": 2.0, "telemetry": {"physical_motion": {"physical_model": "stylized_atmospheric_visualization", "exposed_dodecahedron_smoke_count": 3, "source_plume_continuity": 0.92}}}]
        res_41 = audit_smoke_geometry_and_continuity(bad_n41, sb)
        self.assertEqual(res_41["status"], "FAIL")
        self.assertTrue(any("N41" in i for i in res_41["issues"]))

        # N42: Detached floating smoke puff far from emission source must FAIL closed
        bad_n42 = [{"time": 3.0, "telemetry": {"physical_motion": {"physical_model": "stylized_atmospheric_visualization", "exposed_dodecahedron_smoke_count": 0, "source_plume_continuity": 0.42}}}]
        res_42 = audit_smoke_geometry_and_continuity(bad_n42, sb)
        self.assertEqual(res_42["status"], "FAIL")
        self.assertTrue(any("N42" in i for i in res_42["issues"]))

        # N45: Dishonest CFD / Navier-Stokes claim must FAIL closed
        bad_n45 = [{"time": 3.0, "telemetry": {"physical_motion": {"physical_model": "full_3d_navier_stokes_cfd", "exposed_dodecahedron_smoke_count": 0, "source_plume_continuity": 0.90}}}]
        res_45 = audit_smoke_geometry_and_continuity(bad_n45, sb)
        self.assertEqual(res_45["status"], "FAIL")
        self.assertTrue(any("cfd" in i.lower() or "dishonest" in i.lower() for i in res_45["issues"]))

        # N43: Atmospheric primitive engine generates FBM soft alphaMap + matteAlphaClip + depth-sorted ash NormalBlending
        atm_txt = (ROOT / "director" / "assets" / "atmospheric_volume_primitives.py").read_text(encoding="utf-8")
        lon_txt = (ROOT / "director" / "assets" / "zdf_london_smog_scenes.py").read_text(encoding="utf-8")
        adp_txt = (ROOT / "director" / "assets" / "zach_d_films_adapter.py").read_text(encoding="utf-8")
        self.assertIn("matteAlphaClip", atm_txt)
        self.assertIn("matteAlphaMap", atm_txt)
        self.assertIn("alphaMap: aMap", adp_txt)
        self.assertNotIn("DodecahedronGeometry", lon_txt)

    def test_n44_volumetric_ash_webgl_seek_determinism_and_continuity(self) -> None:
        pf = run_preflight(ROOT, selected_skill="zach-d-films", lang="en")
        prompt_text = (
            "On May 18 1980 Mount St. Helens' swollen north flank bulged outward. "
            "Deep inside the peak molten rock inflated an expanding magma cryptodome. "
            "A magnitude 5.1 earthquake tore the north slope loose in a giant landslide. "
            "Unroofing that hillside unleashed a supersonic lateral blast faster than 300 mph. "
            "The surge flattened 230 square miles of forest and sent a Plinian ash column 15 miles high. "
            "Fifty-seven people died leaving an open horseshoe crater."
        )
        style, cleaned, _ = route_and_lock_style(ROOT, f"/short-director --skill zach-d-films {prompt_text}", cli_skill="zach-d-films", upstream_sha=pf.upstream_sha)
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            parsed = parse_script_and_build_voice(cleaned, selected_skill="zach-d-films", run_dir=tmp, kit_dir=KIT_DIR, lang="en", voice_mode="off")
            sb = build_storyboard_and_bible(parsed_script=parsed, style_decisions=style, run_dir=tmp, fps=30, seed=1980, edit_energy="dynamic", scene_novelty="high", caption_mode="kinetic", callout_mode="smart", editorial_theme="role-aware")
            eng = generate_engine_project(ROOT, tmp, sb, parsed)
            dur = float(sb["total_duration_sec"])
            seek_ts = [round(min(dur - 0.1, x), 3) for x in (7.2, 0.4, 17.6, 3.2, 7.2)]
            res = _run_render_node(
                node_bin=pf.node_path,
                render_mjs=(ROOT / "director" / "render_node.mjs").resolve(),
                args=["trace", eng["entry_html"], ",".join(str(t) for t in seek_ts), "1", pf.webgl_backend],
                browser_exe=pf.browser_executable,
                log_path=tmp / "seek.log",
            )
            tr = res["traces"]
            self.assertEqual(len(tr), 5)
            for k in range(3):
                self.assertAlmostEqual(tr[0]["telemetry"]["camera"]["realized_pos"][k], tr[4]["telemetry"]["camera"]["realized_pos"][k], places=4)
            audit_ok = audit_smoke_geometry_and_continuity(tr, sb, run_dir=tmp)
            self.assertEqual(audit_ok["status"], "PASS", f"Expected clean ash trace: {audit_ok}")
            self.assertEqual(audit_ok["exposed_dodecahedron_smoke_max"], 0)
            self.assertIn("stylized_atmospheric_visualization", audit_ok["physical_models_disclosed"])


if __name__ == "__main__":
    unittest.main()
