"""SD-RETENTION-04.R2 Negative Tests N46-N50: 3D Label Removal, DOM Clamping & Mobile Readability."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from director.assets.zach_d_films_adapter import generate_engine_project
from director.build_storyboard import build_storyboard_and_bible
from director.decoded_visual_quality import audit_phone_composition
from director.editorial_design_system import OverlayStyleSpec, ROLE_STYLE_VARIANTS, measure_text_layout
from director.parse_script import parse_script_and_build_voice
from director.preflight import run_preflight
from director.render_scene import _run_render_node
from director.retention_qa import audit_overlay_render
from director.route_styles import route_and_lock_style
from director.semantic_visual_evidence_qa import audit_smoke_geometry_and_continuity

ROOT = Path(__file__).resolve().parents[1]
KIT_DIR = ROOT / "vendor" / "claude-animation-skills" / "kit"


class TestSceneTextSafeZones(unittest.TestCase):
    def test_n46_no_clipped_3d_card_in_london_scene(self) -> None:
        lon_py = (ROOT / "director" / "assets" / "zdf_london_smog_scenes.py").read_text(encoding="utf-8")
        self.assertNotIn("ILLUSTRATIVE AIRFLOW", lon_py)
        self.assertNotIn("makeLabelCardTexture", lon_py)

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src_js = tmp / "engine_work" / "src" / "london_smog_scenes.js"
            src_js.parent.mkdir(parents=True, exist_ok=True)
            src_js.write_text("export function fake(){ return 'ILLUSTRATIVE AIRFLOW'; }", encoding="utf-8")
            sb = {"shots": [{"shot_id": "s0", "procedural_generator": "zach3d:london_atmospheric_inversion_stage"}]}
            res = audit_smoke_geometry_and_continuity([], sb, run_dir=tmp)
            self.assertEqual(res["status"], "FAIL")
            self.assertTrue(any("ILLUSTRATIVE AIRFLOW" in i for i in res["issues"]))

    def test_n47_n48_n49_dom_clipping_tiny_font_and_caption_overlap_traps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            fake_mp4 = tmp / "fake.mp4"
            fake_mp4.write_bytes(b"\x00" * 32)
            # N47 + N48 + N49 via phone composition & overlay audit
            tl = {
                "total_duration_sec": 8.0,
                "caption_mode": "kinetic",
                "callout_mode": "smart",
                "overlays": [{
                    "overlay_id": "ov_00", "start": 0.5, "end": 2.5,
                    "placement_box": [120, 220, 950, 340],
                    "font_size_1080": 26,  # N48: sub-minimum 320px/360px font
                    "role": "explanation",
                }],
            }
            bad_traces = [{
                "time": 1.5,
                "telemetry": {
                    "overlay": {
                        "caption": {
                            "caption_layout": {"word_overlap_count": 1, "min_word_gap_px": 0.2, "clipped_by_viewport": True, "in_safe_area": False}
                        },
                        "overlays": [{
                            "overlay_id": "ov_00", "visible": True, "dom_rendered": True, "alpha": 1.0,
                            "clipped_by_viewport": True, "char_overflow": True, "in_safe_area": False, "caption_overlap": True,
                            "overlay_visibility_proof": {
                                "dom_rendered": True,
                                "rendered_glyph_bbox": [900.0, 300.0, 1140.0, 380.0],
                                "clipped_by_viewport": True,
                                "char_overflow": True,
                                "fits_viewport_1080": False,
                                "fits_mobile_360": False,
                                "mobile_360_font_px": 6.5,
                            },
                        }],
                    }
                },
            }]
            comp = audit_phone_composition(views=(320, 360, 390, 1080), editorial_timeline=tl, raw_traces=bad_traces)
            self.assertEqual(comp["status"], "FAIL")
            self.assertTrue(any("DOM glyph overflow/clip" in i or "Caption word overlap" in i for i in comp["issues"]))
            self.assertTrue(any("mobile-360 readability fail" in i for i in comp["issues"]))

            hero_spec = ROLE_STYLE_VARIANTS["curiosity_headline"][0]
            small_hero = OverlayStyleSpec(**{**hero_spec.to_dict(), "font_size_1080": 48.0})
            lay_360 = measure_text_layout("TINY / HERO TEST", small_hero, viewport=360)
            self.assertFalse(lay_360["meets_mobile_360_min"])

    def test_n50_live_chromium_dom_clamping_across_mobile_safe_zones(self) -> None:
        pf = run_preflight(ROOT, selected_skill="zach-d-films", lang="en")
        london_txt = (
            "At noon on December 5, 1952, London streets darkened under toxic smog. "
            "Warm air trapped coal smoke over the city until 1956."
        )
        style, cleaned, _ = route_and_lock_style(ROOT, f"/short-director --skill zach-d-films {london_txt}", cli_skill="zach-d-films", upstream_sha=pf.upstream_sha)
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            parsed = parse_script_and_build_voice(cleaned, selected_skill="zach-d-films", run_dir=tmp, kit_dir=KIT_DIR, lang="en", voice_mode="off")
            sb = build_storyboard_and_bible(parsed_script=parsed, style_decisions=style, run_dir=tmp, fps=30, seed=42, caption_mode="kinetic", callout_mode="smart", editorial_theme="role-aware")
            eng = generate_engine_project(ROOT, tmp, sb, parsed)
            mid_ts = [round(0.5 * (float(s["start"]) + float(s["end"])), 3) for s in sb["shots"]]
            tr_res = _run_render_node(
                node_bin=pf.node_path,
                render_mjs=(ROOT / "director" / "render_node.mjs").resolve(),
                args=["trace", eng["entry_html"], ",".join(f"{t:.3f}" for t in mid_ts), "1", pf.webgl_backend],
                browser_exe=pf.browser_executable,
                log_path=tmp / "dom_trace.log",
            )
            traces = tr_res["traces"]
            ed_tl = json.loads((tmp / "editorial_timeline.json").read_text(encoding="utf-8"))
            mob = audit_phone_composition(views=(320, 360, 390, 1080), storyboard=sb, editorial_timeline=ed_tl, raw_traces=traces)
            self.assertEqual(mob["status"], "PASS", f"Mobile 320/360/390/1080 check failed: {mob['issues']}")
            vis_proofs = [
                ov["overlay_visibility_proof"]
                for r in traces
                for ov in ((r.get("telemetry") or {}).get("overlay") or {}).get("overlays", [])
                if ov.get("visible") and isinstance(ov.get("overlay_visibility_proof"), dict)
            ]
            self.assertTrue(vis_proofs, "Expected real Chromium DOM overlay_visibility_proof records")
            for vp in vis_proofs:
                self.assertTrue(vp["dom_rendered"])
                self.assertFalse(vp["clipped_by_viewport"])
                self.assertTrue(vp["fits_mobile_360"])


if __name__ == "__main__":
    unittest.main()
