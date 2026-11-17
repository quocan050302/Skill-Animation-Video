"""Verification Tests for R4: Motivated Layered SFX, Audio/Timeline Sync, Engine Isolation & Traps (N10-N12, N14)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from director import VALID_SKILLS
from director.assets import build_locked_engine_workspace
from director.audio_narrative import build_audio_narrative_plan
from director.build_storyboard import build_storyboard_and_bible
from director.mix_audio import mix_production_audio
from director.parse_script import parse_script_and_build_voice
from director.provenance_guard import ProvenanceGuard
from director.quality_gate import verify_voice_music_intelligibility
from director.retention_qa import audit_sfx_editorial_sync
from director.route_styles import route_and_lock_style


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestRetentionAudioSync(unittest.TestCase):
    def tearDown(self) -> None:
        ProvenanceGuard.deactivate()

    def test_overlay_sfx_sync_and_negative_traps_n10_n11_n12(self) -> None:
        kit = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"
        prompt = (
            "/short-director --skill zach-d-films "
            "Why is there a tiny hole in an airplane window? "
            "An airplane window has three layers and equalizes cabin pressure safely!"
        )
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td)
            dec, cleaned, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill="zach-d-films", upstream_sha="test")
            ps = parse_script_and_build_voice(cleaned, "zach-d-films", rd, kit, voice_mode="off")
            sb = build_storyboard_and_bible(ps, dec, rd, fps=30, seed=42, caption_mode="kinetic", callout_mode="smart")
            plan = build_audio_narrative_plan(ps, sb, run_dir=rd, sfx_density="detailed")
            mix_production_audio(sb, ps, rd, seed=42, audio_plan=plan, voice_expected=False)

            tl = json.loads((rd / "editorial_timeline.json").read_text(encoding="utf-8"))
            sfx_cs = json.loads((rd / "audio" / "sfx_cue_sheet.json").read_text(encoding="utf-8"))
            self.assertEqual(audit_sfx_editorial_sync(rd, tl, sfx_cs)["status"], "PASS")

            # N10 trap: Two callout SFX spaced < 0.14s MUST fail anti-double-pop audit
            bad_double = {
                "cues": [
                    {"time_sec": 1.00, "event": "callout_focus_ring", "kind": "ui"},
                    {"time_sec": 1.07, "event": "callout_verified_counter", "kind": "ui"},
                ]
            }
            self.assertEqual(audit_sfx_editorial_sync(rd, tl, bad_double)["status"], "FAIL")

            # N11 trap: Desynchronized overlay SFX drifted > 45ms from editorial_timeline MUST fail
            if tl["overlays"]:
                t_bad = round(float(tl["overlays"][0]["start"]) + 0.35, 3)
                bad_drift = {"cues": [{"time_sec": t_bad, "event": "callout_focus_ring", "kind": "ui"}]}
                self.assertEqual(audit_sfx_editorial_sync(rd, tl, bad_drift)["status"], "FAIL")

            # N12 trap: Loud SFX over active voice fails verify_voice_music_intelligibility
            sr = 48000
            vo = (0.10 * np.sin(2.0 * np.pi * 220.0 * np.arange(sr) / sr)).astype(np.float32)
            sfx_loud = (0.45 * np.sin(2.0 * np.pi * 650.0 * np.arange(sr) / sr)).astype(np.float32)
            aud = rd / "n12_aud"
            aud.mkdir()
            sf.write(str(aud / "voice.wav"), vo, sr)
            sf.write(str(aud / "sfx.wav"), sfx_loud, sr)
            sf.write(str(aud / "music.wav"), np.zeros(sr, dtype=np.float32), sr)
            res_n12 = verify_voice_music_intelligibility(aud, {"voice": {"expected": True}})
            self.assertEqual(res_n12["status"], "FAIL")

    def test_n14_non_zdf_engines_strictly_isolated_without_overlay_controller(self) -> None:
        kit = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"
        for sk in [s for s in VALID_SKILLS if s != "zach-d-films"]:
            with tempfile.TemporaryDirectory() as td:
                rd = Path(td)
                p_text = (
                    "Growth went from 10 to 80 in four steps."
                    if sk == "graph"
                    else "First step clears focus. Second step holds steady."
                )
                prompt = f"/short-director --skill {sk} {p_text}"
                dec, cleaned, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill=sk, upstream_sha="test")
                ps = parse_script_and_build_voice(cleaned, sk, rd, kit, voice_mode="off")
                sb = build_storyboard_and_bible(ps, dec, rd, fps=30, seed=7, caption_mode="kinetic", callout_mode="smart")
                self.assertEqual(sb["callout_mode"], "off", f"Non-ZDF skill {sk} leaked smart overlays")
                ep = build_locked_engine_workspace(sk, PROJECT_ROOT, rd, sb, ps)
                work = Path(ep["work_dir"])
                self.assertFalse((work / "src" / "editorial_overlay_renderer.js").exists(), f"Overlay JS leaked into {sk}")
                ProvenanceGuard.deactivate()

    def test_boston_1919_bespoke_sfx_sync_and_solemn_aftermath(self) -> None:
        kit = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"
        prompt = (
            "/short-director --skill zach-d-films "
            "In January 1919, a leaking Boston molasses tank groaned quietly. "
            "On January 15th, those tank walls finally gave way. "
            "The wave smashed buildings and an elevated railway support. "
            "Twenty-one people died and about 150 were injured."
        )
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td)
            dec, cleaned, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill="zach-d-films", upstream_sha="test")
            ps = parse_script_and_build_voice(cleaned, "zach-d-films", rd, kit, voice_mode="off")
            sb = build_storyboard_and_bible(ps, dec, rd, fps=30, seed=42, caption_mode="kinetic", callout_mode="smart")
            plan = build_audio_narrative_plan(ps, sb, run_dir=rd, sfx_density="detailed")
            mix_production_audio(sb, ps, rd, seed=42, audio_plan=plan, voice_expected=False)

            self.assertEqual(plan["ambience"]["generator_name"], "period_street_ambience")
            intents = [c["intent"] for c in plan["sfx"]]
            self.assertIn("tank_rupture_impact", intents)
            self.assertIn("street_obstacle_impact", intents)

            # Impact SFX synced strictly within <= 1 frame (34ms) of visual contact_action.hit_time_sec
            rup_shot = next(s for s in sb["shots"] if s["procedural_generator"] == "zach3d:boston_tank_rupture_stage")
            ca = (rup_shot.get("staging") or {}).get("contact_action")
            self.assertIsNotNone(ca)
            rup_sfx = next(c for c in plan["sfx"] if c["intent"] == "tank_rupture_impact")
            self.assertLessEqual(abs(float(rup_sfx["time_sec"]) - float(ca["hit_time_sec"])), 0.034)

            # Respectful aftermath shot emits zero UI overlay pops
            aft_shot = next((s for s in sb["shots"] if s["procedural_generator"] == "zach3d:boston_rescue_aftermath_stage"), None)
            if aft_shot:
                aft_ui = [c for c in plan["sfx"] if c["shot_id"] == aft_shot["shot_id"] and c["kind"] == "ui"]
                self.assertEqual(aft_ui, [], f"Disrespectful UI SFX scheduled on aftermath shot: {aft_ui}")


if __name__ == "__main__":
    unittest.main()
