"""Verification Tests for R1: Expressive Voice Prosody, Capability Truth & Negative Traps (N1-N3, N15)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from director.parse_script import parse_script_and_build_voice
from director.preflight import verify_language_voice_support
from director.retention_qa import audit_prosody_delivery, audit_word_alignment
from director.voice_candidate_eval import evaluate_voice_candidates
from director.voice_prosody import (
    _infer_clause_intent,
    build_prosody_plan,
    get_backend_capabilities,
    measure_voice_delivery,
    render_voice_ab_probe,
    validate_prosody_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"


class TestVoiceProsody(unittest.TestCase):
    def test_honest_capability_disclosure_and_lexicon_token_conservation(self) -> None:
        ok, backend, voice_id, _ = verify_language_voice_support("en", KIT_DIR)
        self.assertTrue(ok)
        caps = get_backend_capabilities(backend, voice_id)
        self.assertIn("backend", caps)
        self.assertFalse(caps["neural_prosody"] if backend == "windows_sapi" else False)

        # Lexicon acronyms (`FAA`, `CFR`) map onto SSML alias while keeping exact visible tokens
        sents = [
            "FAA rule requires safe multi-pane windows.",
            "Wait, what if pressure rises?",
        ]
        plan = build_prosody_plan(sents, voice_style="cinematic", backend=backend, voice_id=voice_id)
        self.assertGreaterEqual(plan["phrase_count"], 2)
        if backend == "windows_sapi":
            self.assertIn("sub alias=", plan["phrases"][0]["ssml_markup"])
        validate_prosody_plan(plan, sents)

    def test_cinematic_vs_legacy_real_waveform_and_ab_probe(self) -> None:
        script = (
            "Why is there a tiny hole in an airplane window? "
            "An airplane window actually has three layers: an outer pane, a middle pane, and a scratch cover. "
            "Wait, what if that outer pane fails? "
            "Then the middle fail-safe pane holds cabin pressure while venting moisture!"
        )
        with tempfile.TemporaryDirectory() as td:
            ra = parse_script_and_build_voice(script, "zach-d-films", Path(td) / "a", KIT_DIR, voice_style="legacy")
            rb = parse_script_and_build_voice(script, "zach-d-films", Path(td) / "b", KIT_DIR, voice_style="cinematic")

            rep_a = ra["voice"]["voice_delivery_report"]
            rep_b = rb["voice"]["voice_delivery_report"]
            self.assertEqual(rep_b["algorithmic_prosody_execution_status"], "PASS")
            self.assertEqual(rep_b["subjective_voice_quality_status"], "NOT_VERIFIED")
            self.assertEqual(rb["voice"]["word_anchor_confidence"], "ESTIMATED")

            probe = render_voice_ab_probe(
                legacy_wav=Path(ra["voice"]["vo_wav_path"]),
                enhanced_wav=Path(rb["voice"]["vo_wav_path"]),
                out_wav=Path(td) / "voice_ab_probe.wav",
                report_a=rep_a,
                report_b=rep_b,
            )
            self.assertTrue(Path(probe["voice_ab_probe_wav"]).exists())
            self.assertGreater(probe["delta_rms_dynamic_span_db"], 0.0)

    def test_negative_traps_n1_n2_n3_n15_fail_closed(self) -> None:
        sents = [
            "Phrase one explains the bleed hole mechanism.",
            "Wait, what happens if the outer pane cracks?",
            "Then the middle pane vents pressure slowly.",
        ]
        # N2: Dropped word / broken SSML token conservation MUST fail closed
        plan = build_prosody_plan(sents, voice_style="cinematic", backend="windows_sapi", voice_id="Microsoft David Desktop")
        bad_plan = json.loads(json.dumps(plan))
        bad_plan["phrases"][0]["ssml_markup"] = bad_plan["phrases"][0]["ssml_markup"].replace("explains", "")
        with self.assertRaises(ValueError):
            validate_prosody_plan(bad_plan, sents)

        # N3: Extreme rate / pitch clamp violations MUST fail closed
        extreme_plan = json.loads(json.dumps(plan))
        extreme_plan["phrases"][0]["rate_multiplier"] = 1.95
        with self.assertRaises(ValueError):
            validate_prosody_plan(extreme_plan, sents)

        pitch_plan = json.loads(json.dumps(plan))
        pitch_plan["phrases"][0]["pitch_semitones"] = 9.5
        with self.assertRaises(ValueError):
            validate_prosody_plan(pitch_plan, sents)

        with tempfile.TemporaryDirectory() as td:
            rd = Path(td)
            (rd / "audio").mkdir()
            sr = 24000
            t = np.arange(int(6.0 * sr)) / float(sr)
            # N1: Monotone constant-rate identical-amplitude flat tone wave masquerading as cinematic
            flat = (0.12 * np.sin(2.0 * np.pi * 120.0 * t)).astype(np.float32)
            vo_p = rd / "audio" / "vo.wav"
            sf.write(str(vo_p), flat, sr)
            spans = [
                {"phrase_id": "ph_00", "start": 0.0, "end": 1.9, "word_count": 6, "pause_after_ms": 100, "text": "one two three four five six"},
                {"phrase_id": "ph_01", "start": 2.0, "end": 3.9, "word_count": 6, "pause_after_ms": 100, "text": "one two three four five six"},
                {"phrase_id": "ph_02", "start": 4.0, "end": 5.9, "word_count": 6, "pause_after_ms": 0, "text": "one two three four five six"},
            ]
            rep_mono = measure_voice_delivery(vo_p, spans, plan, [{"w": "x", "s": 0.0, "e": 0.3}] * 18)
            self.assertEqual(rep_mono["algorithmic_prosody_execution_status"], "FAIL")

            # N3: Clipped waveform fails closed
            clipped = np.clip(flat * 15.0, -1.0, 1.0).astype(np.float32)
            sf.write(str(vo_p), clipped, sr)
            rep_clip = measure_voice_delivery(vo_p, spans, plan, [{"w": "x", "s": 0.0, "e": 0.3}] * 18)
            self.assertEqual(rep_clip["algorithmic_prosody_execution_status"], "FAIL")

            # N15: Dishonest EXACT_FORCED claim over CDF heuristic alignment fails audit_word_alignment
            (rd / "audio" / "words.json").write_text(json.dumps([{"w": "hello", "s": 0.0, "e": 0.3, "line": 0}]), encoding="utf-8")
            (rd / "editorial_timeline.json").write_text(
                json.dumps({"word_anchor_confidence": "EXACT_FORCED", "word_alignment_method": "windows_sapi_vocal_energy_cdf"}),
                encoding="utf-8",
            )
            wa = audit_word_alignment(rd)
            self.assertEqual(wa["status"], "FAIL")
            # Missing delivery report with active voice also fails audit_prosody_delivery
            self.assertEqual(audit_prosody_delivery(rd)["status"], "FAIL")

    def test_storytelling_intents_explicit_voice_id_and_candidate_eval(self) -> None:
        self.assertEqual(_infer_clause_intent("In January 1919, nobody expected a flood.", 0, 5, 0), "hook_whispered_curiosity")
        self.assertEqual(_infer_clause_intent("It wasn't water, it was molasses.", 1, 5, 0), "sudden_reveal")
        self.assertEqual(_infer_clause_intent("Those tank walls finally gave way.", 2, 5, 0), "rupture_burst")
        self.assertEqual(_infer_clause_intent("Twenty-one people died and 150 were injured.", 3, 5, 0), "human_cost")
        self.assertEqual(_infer_clause_intent("It forced engineers to tighten structural rules.", 4, 5, 0), "reflective_payoff")

        # Invalid explicit --voice-id MUST fail cleanly (never silently fall back)
        ok_bad, _, _, _ = verify_language_voice_support("en", KIT_DIR, requested_voice_id="Nonexistent Fantasy Neural Voice")
        self.assertFalse(ok_bad)

        script = (
            "In January 1919, nobody expected a flood. "
            "The wave roaring down the street wasn't water, it was molasses. "
            "On January 15th, those tank walls finally gave way. "
            "Twenty-one people died and about 150 were injured."
        )
        with tempfile.TemporaryDirectory() as td:
            ev = evaluate_voice_candidates(script, Path(td), KIT_DIR, lang="en")
            self.assertTrue((Path(td) / "voice_only_A.wav").exists())
            self.assertTrue((Path(td) / "voice_only_B.wav").exists())
            self.assertTrue(Path(ev["voice_ab_probe_wav"]).exists())
            self.assertTrue(Path(ev["checklist_md"]).exists())
            self.assertEqual(ev["payload"]["subjective_voice_quality_status"], "NOT_VERIFIED")
            for cand in ev["payload"]["candidates"]:
                self.assertLess(cand["max_sample_step"], 0.90, f"Sudden phrase boundary jump in {cand['candidate_id']}")


if __name__ == "__main__":
    unittest.main()
