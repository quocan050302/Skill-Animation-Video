"""Unit & Regression Tests for Narrative Audio Planning, Grounded SFX, Manual Preservation & Visual Isolation."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from director.audio_narrative import (
    build_audio_narrative_plan,
    extract_sound_events,
    preserve_manual_audio_events,
    validate_audio_plan,
)
from director.mix_audio import load_voice_track_safe, mix_production_audio
from director.provenance_guard import ProvenanceGuard
from director.quality_gate import audit_style_lock, run_audio_quality_gate


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _sample_parsed_and_sb(skill: str, text_a: str, text_b: str, motifs: list[str], grounded_props=None, fps: int = 30) -> tuple[dict, dict]:
    parsed = {
        "entities_and_facts": {"detected_motifs": motifs},
        "beats": [
            {"beat_index": 0, "role": "hook", "text": text_a, "start": 0.0, "end": 4.0, "words": []},
            {"beat_index": 1, "role": "payoff", "text": text_b, "start": 4.0, "end": 9.0, "words": []},
        ],
        "voice": {"vo_wav_path": None, "words": []},
    }
    st_0 = {"action": "intro", "visual_metaphor": motifs[0], "secondary_prop": motifs[-1]}
    st_1 = {"action": "end", "visual_metaphor": motifs[-1], "secondary_prop": motifs[0]}
    if grounded_props is not None:
        st_0["grounded_props"] = grounded_props
        st_1["grounded_props"] = grounded_props
    sb = {
        "selected_skill": skill,
        "origin_skills": [skill],
        "fps": fps,
        "total_duration_sec": 9.0,
        "entities_and_facts": {"detected_motifs": motifs},
        "visual_assets": [{"asset_id": "a0", "origin_skill": skill, "generator_module": f"director/assets/{skill.replace('-', '_')}_adapter.py"}],
        "shots": [
            {
                "shot_id": "shot_00", "index": 0, "engine": skill, "beat_role": "hook",
                "narration_text": text_a, "start": 0.0, "end": 4.0, "duration": 4.0,
                "setup_type": "hook_dynamic_cu" if skill == "stick-figure" else "hook_metric_counter_intro",
                "novel_non_template": False, "camera": {"framing": "CU", "movement": "push_in"},
                "staging": st_0, "transition_out": "whip" if skill == "stick-figure" else "cut",
            },
            {
                "shot_id": "shot_01", "index": 1, "engine": skill, "beat_role": "payoff",
                "narration_text": text_b, "start": 4.0, "end": 9.0, "duration": 5.0,
                "setup_type": "novel_slowmo_ripple_cutaway" if skill == "zach-d-films" else "payoff_sunny_pullback",
                "novel_non_template": skill == "zach-d-films", "camera": {"framing": "WS", "movement": "pull_back"},
                "staging": st_1, "transition_out": "cut",
            },
        ],
    }
    return parsed, sb


class TestAudioNarrativePlanning(unittest.TestCase):
    def tearDown(self) -> None:
        ProvenanceGuard.deactivate()

    def test_a5_manual_cues_survive_rerun_and_win_collisions_without_duplication(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            parsed, sb = _sample_parsed_and_sb("stick-figure", "Quick focus.", "Sharp memory.", ["clock"])
            plan1 = build_audio_narrative_plan(parsed, sb, Path(td))

            # Pin a manual SFX cue right where an auto transition/event occurs and lock manual music segment
            manual_plan = copy.deepcopy(plan1)
            manual_t = plan1["sfx"][0]["time_sec"] if plan1["sfx"] else 1.0
            pinned = {
                "time_sec": manual_t,
                "shot_relative_sec": manual_t,
                "shot_id": "shot_00",
                "event": "custom_manual_bell",
                "intent": "brain_spark_chime",
                "kind": "emphasis",
                "gain_db": -6.0,
                "pan": -0.2,
                "manual": True,
                "evidence": "user_manual_pin",
            }
            manual_plan["sfx"].append(pinned)
            manual_plan["music"]["segments"][0]["manual"] = True
            manual_plan["music"]["segments"][0]["mood"] = "emotional"

            # Re-plan twice preserving manual edits
            plan2 = preserve_manual_audio_events(manual_plan, plan1)
            plan3 = preserve_manual_audio_events(plan2, plan1)

            manual_matches = [s for s in plan3["sfx"] if s.get("event") == "custom_manual_bell"]
            self.assertEqual(len(manual_matches), 1, "Manual SFX cue must survive rerun without duplication")
            self.assertEqual(manual_matches[0]["gain_db"], -6.0)
            self.assertEqual(plan3["music"]["segments"][0]["mood"], "emotional")
            self.assertTrue(plan3["manual_edits_preserved"])

    def test_a6_a18_timestamps_shot_relative_and_fps_alignment(self) -> None:
        parsed30, sb30 = _sample_parsed_and_sb("zach-d-films", "Gladiator clash.", "Final blow doesn't come.", ["roman_gladiator", "projectile"], fps=30)
        parsed60, sb60 = _sample_parsed_and_sb("zach-d-films", "Gladiator clash.", "Final blow doesn't come.", ["roman_gladiator", "projectile"], fps=60)
        with tempfile.TemporaryDirectory() as td:
            p30 = build_audio_narrative_plan(parsed30, sb30, Path(td) / "r30")
            p60 = build_audio_narrative_plan(parsed60, sb60, Path(td) / "r60")

            for ev in p30["sfx"]:
                sh = next(s for s in sb30["shots"] if s["shot_id"] == ev["shot_id"])
                self.assertAlmostEqual(ev["time_sec"] - sh["start"], ev["shot_relative_sec"], places=3)
            self.assertEqual([(e["time_sec"], e["event"]) for e in p30["sfx"]], [(e["time_sec"], e["event"]) for e in p60["sfx"]])

            # Non-finite or out-of-range manual cue must fail validation
            bad = copy.deepcopy(p30)
            bad["sfx"].append({"time_sec": 99.0, "event": "oob", "intent": "soft_impact", "manual": True})
            with self.assertRaises(ValueError):
                validate_audio_plan(bad, fps=30, duration=9.0)

    def test_a7_no_hallucinated_sfx_for_ungrounded_words(self) -> None:
        # Narration mentions sword & shield, yet visual engine is `graph` with `grounded_props=["chart"]`!
        parsed, sb = _sample_parsed_and_sb(
            "graph",
            "Sword clashes climbed from 100 to 500.",
            "Shield sales reached 900.",
            ["chart"],
            grounded_props=["chart"],
        )
        evs = extract_sound_events(sb["shots"][0], None, sb["shots"][1], [], selected_skill="graph", global_motifs=["chart"])
        intents = [e["intent"] for e in evs]
        self.assertNotIn("sword_blade_ring", intents)
        self.assertNotIn("metal_shield_clang", intents)
        self.assertNotIn("sword_draw_scrape", intents)

    def test_a8_a9_intentional_silence_and_missing_mandatory_voice_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "sil_run"
            parsed, sb = _sample_parsed_and_sb("minimalistic-graphics", "Quiet pulse.", "Still calm.", ["scale"])

            # Mandatory voice missing -> MUST fail closed
            with self.assertRaises(RuntimeError):
                load_voice_track_safe(parsed, n_total=48000, voice_expected=True)

            # Intentional silence (--voice-mode off --music-mode off --sfx-mode off) -> clean PASS!
            plan = build_audio_narrative_plan(parsed, sb, run_dir, music_mode="off", sfx_mode="off", voice_expected=False)
            mix_rep = mix_production_audio(
                sb, parsed, run_dir, seed=42, audio_plan=plan,
                music_mode="off", sfx_mode="off", voice_expected=False,
            )
            fake_mp4 = run_dir / "dummy.mp4"
            # Mux silent AAC audio onto valid synthetic 9s silent black clip to verify post-encode intentional silence QC
            import subprocess
            subprocess.run([
                "ffmpeg", "-v", "error", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=270x480:r=30:d=9.0",
                "-i", mix_rep["mix_wav_path"],
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest",
                str(fake_mp4),
            ], check=True)
            aqc = run_audio_quality_gate(fake_mp4, fake_mp4, run_dir / "audio", plan, mix_rep, logs_dir=run_dir / "logs")
            self.assertEqual(aqc["overall_status"], "PASS")
            self.assertTrue(aqc["intentionally_silent"])

    def test_a15_audio_integration_preserves_provenance_guard_visual_lock(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "guard_run"
            guard = ProvenanceGuard.activate(PROJECT_ROOT, selection_mode="explicit", selected_skill="stick-figure")
            parsed, sb = _sample_parsed_and_sb("stick-figure", "How do naps help?", "Twenty minutes works best.", ["clock", "brain"])
            plan = build_audio_narrative_plan(parsed, sb, run_dir, voice_expected=False)
            _ = mix_production_audio(sb, parsed, run_dir, seed=42, audio_plan=plan, voice_expected=False)
            snap = guard.snapshot_report()
            self.assertEqual(snap["violations"], [])

            dec = {
                "selection_mode": "explicit", "selected_skill": "stick-figure", "origin_skills": ["stick-figure"],
                "style_lock": {"enabled": True, "engine": "stick-figure", "mixing_policy": "forbidden", "fallback_policy": "fail-closed"},
            }
            audit = audit_style_lock(dec, sb, {"work_dir": str(run_dir), "visual_sources": ["director/assets/stick_figure_adapter.py"]}, snap)
            self.assertEqual(audit["status"], "PASS")

    def test_b7_script_variations_produce_distinct_arcs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p_calm, sb_calm = _sample_parsed_and_sb("minimalistic-graphics", "Small steps.", "Progress compounds.", ["scale"])
            p_rome, sb_rome = _sample_parsed_and_sb("zach-d-films", "Gladiator knocked in Rome.", "Fifty times rental catch.", ["roman_gladiator", "roman_ledger_50x"])
            plan_calm = build_audio_narrative_plan(p_calm, sb_calm, Path(td) / "c", voice_expected=False)
            plan_rome = build_audio_narrative_plan(p_rome, sb_rome, Path(td) / "r", voice_expected=False)
            self.assertNotEqual(plan_calm["music"]["musical_key"], plan_rome["music"]["musical_key"])
            self.assertNotEqual(plan_calm["music"]["theme"], plan_rome["music"]["theme"])
            self.assertNotEqual(len(plan_calm["sfx"]), len(plan_rome["sfx"]))


if __name__ == "__main__":
    unittest.main()
