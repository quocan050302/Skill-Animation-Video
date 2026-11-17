"""End-to-End Integration, Style-Lock Isolation, Mobile DOM, Role SFX & Negative Trap Tests (SD-RETENTION-03)."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from director.assets import build_locked_engine_workspace
from director.audio_narrative import build_audio_narrative_plan
from director.build_storyboard import build_storyboard_and_bible
from director.parse_script import parse_script_and_build_voice
from director.preflight import find_browser_executable
from director.provenance_guard import ProvenanceGuard
from director.quality_gate import run_final_quality_gate
from director.retention_qa import audit_sfx_editorial_sync
from director.route_styles import route_and_lock_style
from director.visual_storytelling_qa import (
    audit_physical_and_character_telemetry,
    audit_pointer_tracking,
    run_visual_storytelling_qa,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"

TACOMA_SCRIPT = (
    "In 1940, drivers crossing a massive suspension bridge felt the highway heave upward like ocean waves. "
    "The Tacoma Narrows Bridge opened on July 1, 1940, across Puget Sound in Washington State. "
    "Engineers quickly nicknamed it Galloping Gertie because crosswinds made the 2,800-foot main span bounce vertically. "
    "Instead of open trusses, the 39-foot wide deck used eight-foot solid steel plate girders that caught swirling wind gusts. "
    "On November 7, 1940, around 10 a.m., the roadbed stopped bouncing up and down and started twisting in violent torsional waves. "
    "Onlookers on shore watched cables whip while an abandoned car tilted nearly forty-five degrees. "
    "Soon after 11 a.m., a 600-foot section of the center span broke free from its suspenders and plunged into Puget Sound. "
    "No human died on the bridge, though engineers redesigned suspension aerodynamics worldwide after that collapse."
)


class TestRetention03Integration(unittest.TestCase):
    def tearDown(self) -> None:
        ProvenanceGuard.deactivate()

    def test_tacoma_role_aware_pipeline_audio_sync_and_webgl_trace_mobile(self) -> None:
        browser_exe = find_browser_executable()
        self.assertIsNotNone(browser_exe)

        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "tacoma_role_aware"
            prompt = f"/short-director --skill zach-d-films {TACOMA_SCRIPT}"
            dec, cleaned, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill="zach-d-films", upstream_sha="test")
            ps = parse_script_and_build_voice(cleaned, "zach-d-films", rd, KIT_DIR, voice_mode="off")
            sb = build_storyboard_and_bible(
                ps, dec, rd, fps=30, seed=42,
                edit_energy="dynamic", scene_novelty="high",
                caption_mode="kinetic", callout_mode="smart",
                editorial_theme="role-aware", curiosity_layer="auto",
            )
            ProvenanceGuard.deactivate()

            self.assertEqual(sb["editorial_theme"], "role-aware")
            self.assertEqual(sb["curiosity_layer"], "auto")
            self.assertGreaterEqual(len(sb["shots"]), 7)
            self.assertTrue((rd / "editorial_design_tokens.json").exists())
            self.assertTrue((rd / "editorial_roles_plan.json").exists())
            self.assertTrue((rd / "composition_report.json").exists())

            ed_tl = json.loads((rd / "editorial_timeline.json").read_text(encoding="utf-8"))
            roles_seen = {o.get("role") for o in ed_tl["overlays"]}
            self.assertIn("curiosity_headline", roles_seen)
            self.assertGreaterEqual(len(roles_seen), 3, f"Expected >=3 distinct semantic roles, got {roles_seen}")
            curios = [o for o in ed_tl["overlays"] if o.get("role") == "curiosity_headline"]
            self.assertLessEqual(len(curios), 2)
            self.assertEqual(curios[0]["label"], "THE ROAD / WAS MOVING!")

            # Audio narrative plan: Tacoma foley + role-mapped SFX + pre-collapse anticipation duck!
            ap = build_audio_narrative_plan(ps, sb, run_dir=rd, voice_expected=False)
            cue_intents = {c["intent"] for c in ap["sfx"]}
            self.assertIn("span_collapse_splash", cue_intents)
            self.assertIn("wind_bridge_gust", cue_intents)
            ducks = (ap.get("music") or {}).get("twist_duck_windows") or []
            self.assertTrue(any(d.get("reason") == "pre_collapse_silence_anticipation" for d in ducks))
            sync_res = audit_sfx_editorial_sync(rd, ed_tl, {"cues": ap["sfx"]})
            self.assertEqual(sync_res["status"], "PASS", f"SFX editorial sync failed: {sync_res}")

            # Generate ZDF workspace & sample 4 hero WebGL timestamps
            ep = build_locked_engine_workspace("zach-d-films", PROJECT_ROOT, rd, sb, ps)
            ProvenanceGuard.deactivate()

            sample_times = []
            for o in ed_tl["overlays"][:5]:
                sample_times.append(round(o["start"] + 0.35 * (o["end"] - o["start"]), 3))
            col_sh = next((s for s in sb["shots"] if "collapse" in str(s.get("procedural_generator") or "")), sb["shots"][-1])
            sample_times.append(round(col_sh["start"] + 0.65 * col_sh["duration"], 3))
            times_csv = ",".join(f"{t:.3f}" for t in sorted(set(sample_times)))

            render_mjs = PROJECT_ROOT / "director" / "render_node.mjs"
            env = os.environ.copy()
            env["PLAYWRIGHT_CHROME_PATH"] = browser_exe
            tr_res = subprocess.run(
                ["node", str(render_mjs), "trace", ep["entry_html"], times_csv, "1", "d3d11"],
                capture_output=True, text=True, check=True, env=env,
            )
            traces = json.loads([ln for ln in tr_res.stdout.splitlines() if ln.startswith("{")][-1])["traces"]

            # Audit pointer tracking (`tip_target_error_px <= 36`), physical motion & QA report persistence
            ptr_qa = audit_pointer_tracking(traces, ed_tl, max_tip_error_px=36.0, run_dir=rd)
            self.assertEqual(ptr_qa["status"], "PASS", f"Pointer tracking error exceeded limit: {ptr_qa}")
            self.assertGreater(ptr_qa["checked_settled_tips"], 0)

            sag = json.loads((rd / "story_action_graph.json").read_text(encoding="utf-8"))
            vs_qa = run_visual_storytelling_qa(rd, sb, sag, ed_tl, raw_traces=traces, audio_plan=ap)
            self.assertEqual(vs_qa["overall_status"], "PASS", f"Tacoma QA failed: {vs_qa}")
            self.assertEqual(vs_qa["subjective_visual_review"], "NOT_VERIFIED")
            self.assertTrue((rd / "world_state_telemetry.json").exists())
            self.assertTrue((rd / "pointer_tracking.json").exists())

            # Honest NOT_VERIFIED quality_gate check
            qc_stub = run_final_quality_gate(
                rd,
                dec,
                sb,
                ep,
                {"selected_skill": "zach-d-films", "allowed_visual_adapter": "zach_d_films_adapter"},
                {"native_4k": False, "render_4k_mode": "native"},
                rd / "missing_prev.mp4",
                rd / "missing_4k.mp4",
            )
            self.assertEqual(qc_stub["subjective_visual_review"], "NOT_VERIFIED")
            self.assertEqual(qc_stub["viewer_retention_status"], "NOT_VERIFIED")

    def test_single_skill_isolation_stick_figure_and_third_topic_generalization(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            # 1. Single-skill isolation: stick-figure forces legacy + callout_mode='off'
            rd_sf = Path(td) / "sf"
            prompt_sf = "/short-director --skill stick-figure Why does cold water sink beneath warm water in lakes?"
            dec_sf, cleaned_sf, _ = route_and_lock_style(PROJECT_ROOT, prompt_sf, cli_skill="stick-figure", upstream_sha="test")
            ps_sf = parse_script_and_build_voice(cleaned_sf, "stick-figure", rd_sf, KIT_DIR, voice_mode="off")
            sb_sf = build_storyboard_and_bible(
                ps_sf, dec_sf, rd_sf, fps=30, seed=42,
                callout_mode="smart", editorial_theme="role-aware", curiosity_layer="auto",
            )
            ProvenanceGuard.deactivate()
            self.assertEqual(sb_sf["callout_mode"], "off")
            self.assertEqual(sb_sf["editorial_theme"], "legacy")
            tl_sf = json.loads((rd_sf / "editorial_timeline.json").read_text(encoding="utf-8"))
            self.assertEqual(len(tl_sf["overlays"]), 0)

            # 2. N32 / Generalization: brand-new science topic inside ZDF (no Tacoma or Boston keywords)
            rd_vol = Path(td) / "volcano"
            prompt_vol = (
                "/short-director --skill zach-d-films "
                "Why do volcanic eruptions create jagged lightning bolts inside thick ash clouds? "
                "Hot silica tephra grains smash together at extreme speeds, stripping electrons across updraft zones."
            )
            dec_v, cleaned_v, _ = route_and_lock_style(PROJECT_ROOT, prompt_vol, cli_skill="zach-d-films", upstream_sha="test")
            ps_v = parse_script_and_build_voice(cleaned_v, "zach-d-films", rd_vol, KIT_DIR, voice_mode="off")
            sb_v = build_storyboard_and_bible(ps_v, dec_v, rd_vol, fps=30, seed=42, editorial_theme="role-aware", curiosity_layer="auto")
            ProvenanceGuard.deactivate()
            tl_v = json.loads((rd_vol / "editorial_timeline.json").read_text(encoding="utf-8"))
            self.assertEqual(sb_v["editorial_theme"], "role-aware")
            self.assertTrue(len(sb_v["shots"]) >= 1)
            self.assertIsNotNone(tl_v)

    def test_negative_traps_n29_misaligned_pointer_fails(self) -> None:
        bad_ptr_traces = [{
            "time_sec": 1.2,
            "telemetry": {
                "overlay": {
                    "overlays": [{
                        "overlay_id": "ov_00",
                        "role": "curiosity_headline",
                        "visible": True,
                        "alpha": 1.0,
                        "anchor_projected_xy": [420.0, 620.0],
                        "tip_xy": [510.0, 740.0],
                        "tip_target_error_px": 150.0,
                    }]
                }
            },
        }]
        rep = audit_pointer_tracking(bad_ptr_traces, {"callout_mode": "smart"}, max_tip_error_px=36.0)
        self.assertEqual(rep["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
