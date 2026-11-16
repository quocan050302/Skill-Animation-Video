"""STEP 8 Unit & Negative Tests (A, B, C, D, E, H, I, K) for SD-VISUAL-01."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from director import VALID_SKILLS
from director.audio_narrative import extract_sound_events
from director.build_storyboard import build_storyboard_and_bible
from director.camera_choreographer import build_camera_plan, plan_camera_path
from director.provenance_guard import ProvenanceGuard, StyleLockViolationError
from director.scene_asset_factory import (
    UnsupportedSceneError,
    compile_scene_entities,
    evaluate_scene_silhouette_and_camera_bounds,
    validate_entity_continuity,
)
from director.shot_director import plan_editorial_coverage, validate_coverage
from director.transition_director import emit_transition_edl
from director.visual_event_graph import (
    extract_semantic_visual_events,
    validate_visual_event_graph,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_mock_parsed_script(sentences: list[str], alignment_method: str = "per_sentence_vocal_formant_energy") -> dict:
    beats = []
    words = []
    cur = 0.0
    for li, sent in enumerate(sentences):
        toks = sent.split()
        b_start = cur
        b_words = []
        for tok in toks:
            dw = 0.28
            wobj = {"w": tok, "s": round(cur, 3), "e": round(cur + dw, 3), "line": li}
            words.append(wobj)
            b_words.append(wobj)
            cur += dw
        role = "hook" if li == 0 else ("payoff" if li == len(sentences) - 1 else ("turn" if sent.lower().startswith("but") else "mechanism"))
        beats.append({
            "beat_index": li,
            "role": role,
            "text": sent,
            "start": round(b_start, 3),
            "end": round(cur, 3),
            "duration": round(cur - b_start, 3),
            "word_count": len(toks),
            "words": b_words,
        })
        cur += 0.18

    joined_low = " ".join(sentences).lower()
    motifs = []
    for k, triggers in (
        ("phone_screen", ("phone", "screen", "tap", "send", "finger", "message")),
        ("microchip_pcb", ("chip", "pcb", "circuit", "silicon")),
        ("cell_tower_wave", ("tower", "radio", "antenna")),
        ("subsea_fiber_cable", ("ocean", "subsea", "fiber", "cable")),
        ("datacenter_rack", ("data center", "server", "rack")),
        ("power_turbine", ("turbine", "generator", "grid")),
        ("cosmic_origin", ("star", "stars", "cosmos", "universe")),
        ("brain", ("brain", "neuron", "sleep")),
    ):
        if any(t in joined_low for t in triggers):
            motifs.append(k)
    if not motifs:
        motifs = ["idea_spark"]

    return {
        "raw_input_script": " ".join(sentences),
        "script_origin": "user_verbatim_sentences",
        "sentences": sentences,
        "beats": beats,
        "entities_and_facts": {
            "user_numbers": [],
            "number_suffix": "",
            "detected_motifs": motifs,
            "fact_checks": [{"rule": "factual_tone_audit", "status": "PASS"}],
        },
        "voice": {
            "backend": "off" if alignment_method == "silent_syllabic_pacing" else "macos_say",
            "alignment_method": alignment_method,
            "vo_duration_sec": round(cur, 3),
            "words": words,
        },
    }


class TestVisualEventAndCoverage(unittest.TestCase):
    def test_a_b_semantic_events_anti_repetition_and_non_duplicated_splits(self) -> None:
        sentences = [
            "Your finger taps send on a glowing phone screen, while tiny copper circuits wake inside the processor.",
            "Next, electromagnetic waves leap off a neighborhood radio tower and plunge into a dark subsea fiber ocean cable.",
            "Then servers inside a massive data center decode the packet using turbines spinning at a distant power grid.",
            "Finally every silicon atom inside that message traces back to ancient stars forging elements in the cosmos.",
        ]
        parsed = _make_mock_parsed_script(sentences)
        graph = extract_semantic_visual_events(parsed, selected_skill="zach-d-films", fps=30, seed=77)
        # Multi-clause causal chain yields >= 8 distinct visual events
        self.assertGreaterEqual(len(graph["events"]), 8)
        for ev in graph["events"]:
            self.assertFalse(ev["word_anchor"]["uncertain"])
            self.assertEqual(ev["word_anchor"]["timing_confidence"], "waveform_aligned")

        coverage = plan_editorial_coverage(
            visual_events=graph,
            parsed_script=parsed,
            selected_skill="zach-d-films",
            fps=30,
            seed=77,
            edit_energy="dynamic",
            scene_novelty="high",
            transition_policy="motivated",
        )
        shots = coverage["shots"]
        self.assertGreaterEqual(len(shots), 8)
        div = coverage["diversity_summary"]
        self.assertEqual(div["adjacent_identical_setups"], 0, shots)
        self.assertEqual(div["adjacent_identical_cam_triples"], 0, shots)

        # Ensure split shots inside the same beat NEVER duplicate identical full narration text
        for i in range(1, len(shots)):
            if shots[i]["beat_id"] == shots[i - 1]["beat_id"]:
                self.assertNotEqual(shots[i]["narration_text"], shots[i - 1]["narration_text"])

        # Voice off marks timing explicitly uncertain (`estimated_uncertain`)
        parsed_silent = _make_mock_parsed_script(sentences, alignment_method="silent_syllabic_pacing")
        g_silent = extract_semantic_visual_events(parsed_silent, selected_skill="zach-d-films", fps=30, seed=77)
        for ev in g_silent["events"]:
            self.assertTrue(ev["word_anchor"]["uncertain"])
            self.assertEqual(ev["word_anchor"]["timing_confidence"], "estimated_uncertain")

    def test_c_canonical_planning_determinism(self) -> None:
        sentences = [
            "Your thumb taps send on a phone screen.",
            "Signals flash inside a silicon circuit chip, then cross ocean fiber cables toward stars.",
        ]
        parsed = _make_mock_parsed_script(sentences)
        sd = {"selection_mode": "explicit", "selected_skill": "zach-d-films", "style_lock": {"enabled": True, "engine": "zach-d-films", "mixing_policy": "forbidden", "fallback_policy": "fail-closed"}}
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            sb1 = build_storyboard_and_bible(parsed, sd, Path(d1), fps=30, seed=99, edit_energy="dynamic", scene_novelty="high")
            sb2 = build_storyboard_and_bible(parsed, sd, Path(d2), fps=30, seed=99, edit_energy="dynamic", scene_novelty="high")
            self.assertEqual(sb1["shots"], sb2["shots"])
            self.assertEqual(
                (Path(d1) / "visual_events.json").read_text(encoding="utf-8"),
                (Path(d2) / "visual_events.json").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                (Path(d1) / "transition_edl.json").read_text(encoding="utf-8"),
                (Path(d2) / "transition_edl.json").read_text(encoding="utf-8"),
            )

    def test_d_provenance_guard_locks_visual_planning_and_all_six_skills(self) -> None:
        sentences = ["Light travels through glass fiber across an ocean.", "Compute clusters route every packet accurately."]
        parsed = _make_mock_parsed_script(sentences)
        for skill in VALID_SKILLS:
            guard = ProvenanceGuard.activate(PROJECT_ROOT, selection_mode="explicit", selected_skill=skill)
            try:
                g = extract_semantic_visual_events(parsed, selected_skill=skill, fps=30, seed=42)
                cov = plan_editorial_coverage(g, parsed, selected_skill=skill, fps=30, seed=42)
                inv = compile_scene_entities(g, selected_skill=skill, seed=42)
                check = validate_entity_continuity(cov["shots"], inv, selected_skill=skill)
                self.assertTrue(check["ok"])
                # Foreign visual engine read MUST still raise StyleLockViolationError
                other = next(s for s in VALID_SKILLS if s != skill)
                foreign_md = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "skills" / other / "SKILL.md"
                with self.assertRaises(StyleLockViolationError):
                    foreign_md.read_text(encoding="utf-8")
            finally:
                ProvenanceGuard.deactivate()

    def test_e_non_roman_script_rejects_armor_and_validates_bounds(self) -> None:
        sentences = [
            "Your finger taps send on a phone screen.",
            "Inside the chassis, a circuit chip sparks current, then optical light enters a deep ocean fiber cable before a turbine powers a data center beneath distant stars.",
        ]
        parsed = _make_mock_parsed_script(sentences)
        g = extract_semantic_visual_events(parsed, selected_skill="zach-d-films", fps=30, seed=55)
        cov = plan_editorial_coverage(g, parsed, selected_skill="zach-d-films", fps=30, seed=55, edit_energy="dynamic")
        inv = compile_scene_entities(g, selected_skill="zach-d-films", seed=55)
        res = validate_entity_continuity(cov["shots"], inv, selected_skill="zach-d-films")
        self.assertGreaterEqual(res["unique_generators"], 4)
        for gen in res["generators_per_shot"]:
            self.assertNotIn("roman", gen)

        # Negative E1: Injecting Roman generator onto a non-Roman shot MUST raise UnsupportedSceneError
        bad_shot = dict(cov["shots"][0])
        bad_inv = json.loads(json.dumps(inv))
        eid = bad_shot["event_ids"][0]
        bad_inv["by_event"][eid]["asset"]["procedural_generator"] = "zach3d:roman_historical_stage"
        with self.assertRaises(UnsupportedSceneError):
            validate_entity_continuity([bad_shot], bad_inv, selected_skill="zach-d-films")

        # Negative E2: Camera clipping inside subject bounds (dist < 0.25m or y < 0.08) fails check
        bad_cam = {"space": "world_3d", "keyframes": [{"pos": [0.0, 0.02, 0.0], "look": [0.0, 0.02, 0.0], "fov": 35}]}
        bounds_bad = evaluate_scene_silhouette_and_camera_bounds(bad_shot, bad_cam, bad_inv["by_event"][eid])
        self.assertFalse(bounds_bad["ok"])

    def test_h_diverse_script_niches_yield_distinct_graphs(self) -> None:
        p_neuro = _make_mock_parsed_script(["Your brain pulses through deep sleep stages.", "Neurons clear tired chemical pressure."])
        p_ocean = _make_mock_parsed_script(["Pulses speed down subsea ocean fiber cables.", "Turquoise light beams reach a distant power turbine."])
        g1 = extract_semantic_visual_events(p_neuro, selected_skill="zach-d-films")
        g2 = extract_semantic_visual_events(p_ocean, selected_skill="zach-d-films")
        self.assertNotEqual(g1["unique_scene_families"], g2["unique_scene_families"])
        self.assertIn("anatomical_cutaway", g1["unique_scene_families"])
        self.assertIn("ocean_infrastructure", g2["unique_scene_families"])

    def test_i_audio_visual_sync_and_no_ungrounded_hallucination(self) -> None:
        shot_phone = {
            "shot_id": "shot_00",
            "index": 0,
            "engine": "zach-d-films",
            "beat_role": "hook",
            "start": 0.0,
            "end": 2.0,
            "setup_type": "human_device_macro",
            "procedural_generator": "zach3d:human_device_stage",
            "transition_out": "zoom_through",
            "camera": {"framing": "CU", "movement": "macro_push_in"},
            "staging": {"grounded_props": ["phone_screen"]},
            "narration_text": "Tap send on screen.",
        }
        evs = extract_sound_events(shot_phone, None, {"shot_id": "shot_01"}, [], selected_skill="zach-d-films")
        intents = {e["intent"]: e for e in evs}
        self.assertIn("glass_tap_ui", intents)
        # Visual adapter T_TAP = dur * 0.42 = 0.840s -> exact frame match!
        self.assertAlmostEqual(intents["glass_tap_ui"]["time_sec"], 0.84, places=3)
        self.assertIn("transition_sweep", intents)

        # Ungrounded abstract shot MUST NOT invent sword/phone/cosmic/subsea cues
        shot_clean = {
            "shot_id": "shot_01",
            "index": 1,
            "engine": "minimalistic-graphics",
            "beat_role": "mechanism",
            "start": 2.0,
            "end": 5.0,
            "setup_type": "rising_hairline_steps",
            "procedural_generator": "mg_svg:geometric_minimal",
            "transition_out": "cut",
            "camera": {"framing": "WS", "movement": "parabolic_hop_climb"},
            "staging": {"grounded_props": ["abstract_step"]},
            "narration_text": "Quiet motion feels like a sword of ocean stars ringing on a phone.",
        }
        evs_clean = extract_sound_events(shot_clean, shot_phone, None, [], selected_skill="minimalistic-graphics")
        bad_intents = {e["intent"] for e in evs_clean}
        self.assertFalse(bad_intents & {"glass_tap_ui", "subsea_bubble_hum", "cosmic_swell", "sword_blade_ring"})

    def test_k_fault_injection_validation_fails_closed(self) -> None:
        parsed = _make_mock_parsed_script(["First clause happens here.", "Second clause lands calmly."])
        g = extract_semantic_visual_events(parsed, selected_skill="stick-figure")
        # Out-of-bounds event duration MUST raise ValueError
        g_bad = json.loads(json.dumps(g))
        g_bad["events"][0]["end_sec"] = 999.0
        with self.assertRaises(ValueError):
            validate_visual_event_graph(g_bad, locked_skill="stick-figure", duration_sec=g["total_duration_sec"])

        # Coverage with duplicated narration split inside same beat MUST fail closed
        cov = plan_editorial_coverage(g, parsed, selected_skill="stick-figure")
        cov_bad = json.loads(json.dumps(cov))
        if len(cov_bad["shots"]) >= 2:
            cov_bad["shots"][1]["beat_id"] = cov_bad["shots"][0]["beat_id"]
            cov_bad["shots"][1]["narration_text"] = cov_bad["shots"][0]["narration_text"]
            with self.assertRaises(ValueError):
                validate_coverage(cov_bad, g, selected_skill="stick-figure")


if __name__ == "__main__":
    unittest.main()
