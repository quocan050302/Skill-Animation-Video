"""T01-T20 Comprehensive Verification & Negative Tampering Matrix for ZDF-MOTION-01."""

from __future__ import annotations

import json
import math
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from director.assets import build_locked_engine_workspace
from director.audio_narrative import build_audio_narrative_plan
from director.build_storyboard import build_storyboard_and_bible
from director.camera_choreographer import build_camera_plan
from director.camera_execution import (
    collect_camera_trace_samples,
    evaluate_camera_path_py,
    evaluate_camera_trace_accuracy,
)
from director.preflight import DiskBudgetGuard, run_preflight
from director.provenance_guard import ProvenanceGuard, StyleLockViolationError
from director.render_scene import _run_render_node
from director.route_styles import route_and_lock_style
from director.scene_asset_factory import (
    UnsupportedSceneError,
    compile_scene_entities,
    evaluate_scene_silhouette_and_camera_bounds,
    validate_entity_continuity,
)
from director.scene_diversity_qa import (
    audit_camera_execution,
    audit_intra_shot_motion,
    audit_transition_continuity,
    detect_adjacent_repetitions,
    run_scene_diversity_qa,
    sample_perceptual_frames,
)
from director.shot_director import plan_editorial_coverage, validate_coverage
from director.transition_director import emit_transition_edl, finalize_transition_edl_verification
from director.visual_event_graph import (
    classify_visual_clause,
    extract_semantic_visual_events,
    validate_visual_event_graph,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

ELEVATOR_HERO_SCRIPT = (
    "When you press an elevator call button, a finger pushes a microswitch inside the hall panel. "
    "Electrical wires send that request straight into a controller cabinet packed with logic relays and drives. "
    "Inside the machine room above, an electric traction motor spins a grooved steel sheave. "
    "Heavy steel hoist cables wrap over that pulley, balancing the passenger car against a sliding counterweight inside the shaft. "
    "When the controller matches your floor, caliper brakes gently lock the sheave and the landing doors glide open."
)


def _mock_parsed(prompt: str, sec_per_sentence: float = 2.6) -> dict:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", prompt.strip()) if p.strip()]
    beats = []
    words = []
    t = 0.0
    for idx, sent in enumerate(parts):
        toks = [w for w in sent.split() if w.strip()]
        dur = max(1.6, round(max(sec_per_sentence, len(toks) * 0.24), 3))
        step = dur / max(1, len(toks))
        b_words = []
        for k, tok in enumerate(toks):
            wobj = {
                "w": tok,
                "s": round(t + k * step, 3),
                "e": round(t + (k + 0.9) * step, 3),
                "line": idx,
            }
            words.append(wobj)
            b_words.append(wobj)
        role = "hook" if idx == 0 else ("payoff" if idx == len(parts) - 1 else "mechanism")
        beats.append({
            "beat_index": idx,
            "index": idx,
            "role": role,
            "text": sent,
            "start": round(t, 3),
            "end": round(t + dur, 3),
            "duration": round(dur, 3),
            "word_count": len(toks),
            "words": b_words,
        })
        t += dur + 0.06
    return {
        "raw_prompt": prompt,
        "sentences": parts,
        "beats": beats,
        "voice": {"vo_duration_sec": round(t, 3), "alignment_method": "mock_aligned", "words": words},
        "entities_and_facts": {"detected_motifs": [], "fact_checks": []},
    }


def _make_synthetic_video(out_mp4: Path, duration_sec: float, fps: int = 30, draw_fn=None) -> Path:
    """Create a deterministic portrait 270x480 test MP4 via ffmpeg rawvideo pipe."""
    w, h = 270, 480
    n_frames = max(2, int(round(duration_sec * fps)))
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv420p",
        str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for f in range(n_frames):
            t = f / fps
            img = Image.new("RGB", (w, h), (22, 34, 56))
            if draw_fn is not None:
                draw_fn(img, t, f, n_frames)
            proc.stdin.write(img.tobytes())
    finally:
        proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"Synthetic video encode failed ({rc})")
    return out_mp4


class TestZdfMotion01Matrix(unittest.TestCase):
    def test_t01_t02_t03_single_authority_camera_and_collision_tamper(self) -> None:
        """T01/T02/T03: Planned camera_path == Three.js WebGL telemetry; tamper pos & collider fail closed."""
        pf = run_preflight(PROJECT_ROOT, selected_skill="zach-d-films", requested_workers=1)
        self.assertTrue(pf.ok, pf.errors)
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "t01"
            run_dir.mkdir(parents=True)
            parsed = _mock_parsed(ELEVATOR_HERO_SCRIPT)
            style_dec, _, _ = route_and_lock_style(project_root=PROJECT_ROOT, raw_input=ELEVATOR_HERO_SCRIPT, cli_skill="zach-d-films")
            try:
                sb = build_storyboard_and_bible(parsed, style_dec, run_dir, fps=30, seed=2026, edit_energy="dynamic", scene_novelty="high", transition_policy="motivated")
                cam_plan = json.loads((run_dir / "camera_paths.json").read_text(encoding="utf-8"))
                edl = json.loads((run_dir / "transition_edl.json").read_text(encoding="utf-8"))
                eng = build_locked_engine_workspace("zach-d-films", PROJECT_ROOT, run_dir, sb, parsed)

                times = collect_camera_trace_samples(sb, fps=30)
                trace_res = _run_render_node(
                    "node", PROJECT_ROOT / "director" / "render_node.mjs",
                    ["trace", eng["entry_html"], ",".join(f"{t:.4f}" for t in times), "1", pf.webgl_backend],
                    pf.browser_executable, run_dir / "trace.log",
                )
                traces = list(trace_res.get("traces") or [])
                acc = evaluate_camera_trace_accuracy(sb, cam_plan, traces, transition_edl=edl)
                self.assertEqual(acc["status"], "PASS", acc["failures"])
                self.assertLessEqual(acc["worst_pos_err_m"], 0.02)
                self.assertLessEqual(acc["worst_ori_err_deg"], 0.65)
                self.assertLessEqual(acc["worst_fov_err_deg"], 0.65)

                # T02: Tamper camera realized_pos (simulating hardcoded `place(...)` ignoring planned pos!)
                tampered_traces = json.loads(json.dumps(traces))
                tampered_traces[1]["telemetry"]["camera"]["realized_pos"][0] += 0.45
                fail_pos = evaluate_camera_trace_accuracy(sb, cam_plan, tampered_traces, transition_edl=edl)
                self.assertEqual(fail_pos["status"], "FAIL")

                # T03: Tamper camera penetration below floor & collider intersection
                col_traces = json.loads(json.dumps(traces))
                col_traces[0]["telemetry"]["camera"]["realized_pos"][1] = 0.02
                fail_col = evaluate_camera_trace_accuracy(sb, cam_plan, col_traces, transition_edl=edl)
                self.assertEqual(fail_col["status"], "FAIL")
                self.assertTrue(fail_col["collision_violations"])

                # Also verify planner bounds rejection on collider overlap
                bad_path = json.loads(json.dumps(cam_plan["paths"][0]))
                bad_path["keyframes"][0]["pos"] = [0.40, 1.15, 0.10]  # inside lobby wall collider box
                inv = compile_scene_entities(json.loads((run_dir / "visual_events.json").read_text(encoding="utf-8")), "zach-d-films", seed=2026)
                ev0 = inv["by_event"][sb["shots"][0]["event_ids"][0]]
                bc = evaluate_scene_silhouette_and_camera_bounds(sb["shots"][0], bad_path, ev0)
                self.assertFalse(bc["ok"], bc)
            finally:
                ProvenanceGuard.deactivate()

    def test_t04_t05_transition_truth_and_anti_spoofing(self) -> None:
        """T04/T05: Planned transitions start unverified; hard-cut spoofed as zoom_through or pre-True FAILS."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            ev_g = extract_semantic_visual_events(_mock_parsed(ELEVATOR_HERO_SCRIPT), selected_skill="zach-d-films", seed=9)
            cov = plan_editorial_coverage(ev_g, _mock_parsed(ELEVATOR_HERO_SCRIPT), "zach-d-films", edit_energy="dynamic", transition_policy="motivated", run_dir=td_path)
            cam_p = build_camera_plan(cov["shots"], "zach-d-films", fps=30, seed=9, run_dir=td_path)
            edl = emit_transition_edl(cov["shots"], cam_p, "zach-d-films", fps=30, mode="motivated", run_dir=td_path)
            for tr in edl["transitions"]:
                self.assertFalse(tr["executed_in_renderer"])
                self.assertEqual(tr["execution_status"], "PLANNED")
                self.assertEqual(tr["verification_status"], "PLANNED_UNVERIFIED")

            # Build a 4-second synthetic MP4 containing a HARD CUT at t=2.0s (pure blue -> pure orange)
            mp4 = _make_synthetic_video(
                td_path / "hard_cut.mp4", 4.0, fps=30,
                draw_fn=lambda img, t, f, n: ImageDraw.Draw(img).rectangle([0, 0, 270, 480], fill=(20, 90, 210) if t < 2.0 else (230, 110, 25)),
            )
            fake_edl = {
                "transitions": [{
                    "transition_id": "tr_spoof",
                    "from_shot": "shot_00",
                    "to_shot": "shot_01",
                    "boundary_sec": 2.0,
                    "duration_sec": 0.24,
                    "actual_method": "zoom_through",
                    "executed_in_renderer": True,  # T05 spoof!
                    "verification_status": "PLANNED_UNVERIFIED",
                }]
            }
            audit = audit_transition_continuity(mp4, fake_edl, cov["shots"][:2], "zach-d-films", fps=30, raw_traces=None)
            self.assertEqual(audit["status"], "FAIL", audit)

            # T04: Now encode a TRUE smooth 2-source cross/wipe transition over [1.88, 2.12]
            def draw_real_wipe(img, t, f, n):
                dr = ImageDraw.Draw(img)
                if t < 1.88:
                    dr.rectangle([0, 0, 270, 480], fill=(20, 90, 210))
                elif t > 2.12:
                    dr.rectangle([0, 0, 270, 480], fill=(230, 110, 25))
                else:
                    p = (t - 1.88) / 0.24
                    split_x = int(270 * p)
                    dr.rectangle([0, 0, 270, 480], fill=(20, 90, 210))
                    dr.rectangle([0, 0, split_x, 480], fill=(230, 110, 25))

            mp4_real = _make_synthetic_video(td_path / "real_wipe.mp4", 4.0, fps=30, draw_fn=draw_real_wipe)
            real_edl = {
                "transitions": [{
                    "transition_id": "tr_wipe",
                    "from_shot": "shot_00",
                    "to_shot": "shot_01",
                    "boundary_sec": 2.0,
                    "duration_sec": 0.24,
                    "actual_method": "object_wipe",
                    "executed_in_renderer": False,
                    "verification_status": "PLANNED_UNVERIFIED",
                }]
            }
            audit_ok = audit_transition_continuity(mp4_real, real_edl, cov["shots"][:2], "zach-d-films", fps=30, raw_traces=None)
            self.assertEqual(audit_ok["status"], "PASS", audit_ok)
            finalize_transition_edl_verification(real_edl, audit_ok["details"], evidence_path="scene_diversity_report.json")
            self.assertTrue(real_edl["transitions"][0]["executed_in_renderer"])
            self.assertEqual(real_edl["transitions"][0]["verification_status"], "VERIFIED_DECODED")

    def test_t06_t07_t08_character_identity_button_ik_and_layered_cutaway_webgl(self) -> None:
        """T06/T07/T08: Real Three.js IK fingertip-to-button contact + LayeredCutaway + identity lock."""
        pf = run_preflight(PROJECT_ROOT, selected_skill="zach-d-films", requested_workers=1)
        self.assertTrue(pf.ok, pf.errors)
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "ik_cutaway"
            run_dir.mkdir(parents=True)
            parsed = _mock_parsed(ELEVATOR_HERO_SCRIPT)
            style_dec, _, _ = route_and_lock_style(project_root=PROJECT_ROOT, raw_input=ELEVATOR_HERO_SCRIPT, cli_skill="zach-d-films")
            try:
                sb = build_storyboard_and_bible(parsed, style_dec, run_dir, fps=30, seed=77, edit_energy="dynamic", scene_novelty="high")
                eng = build_locked_engine_workspace("zach-d-films", PROJECT_ROOT, run_dir, sb, parsed)

                # T06: Character registry invariant across shots & no shot-index palette permutation
                shots_js = (Path(eng["entry_html"]).parent / "src" / "shots.js").read_text(encoding="utf-8")
                self.assertNotIn("shirt_palette", shots_js)
                char_reg = sb.get("character_registry") or {}
                self.assertIn("char_protagonist_01", char_reg)
                inv = compile_scene_entities(json.loads((run_dir / "visual_events.json").read_text(encoding="utf-8")), "zach-d-films", seed=77)
                cont = validate_entity_continuity(sb["shots"], inv, "zach-d-films")
                self.assertTrue(cont["ok"], cont)

                # Negative T06: Mutate shirt_material_id on a second human shot -> MUST FAIL continuity check
                bad_shots = json.loads(json.dumps(sb["shots"]))
                for s in bad_shots:
                    if s.get("procedural_generator") in ("zach3d:elevator_lobby_button_stage", "zach3d:elevator_landing_doors_stage"):
                        s["staging"]["character_id"] = "char_protagonist_01"
                        s["staging"]["character_material_id"] = "mat_mutated_shirt"
                        break
                # Guarantee at least two shots reference same char_protagonist_01 with different material
                bad_shots[0]["staging"]["character_id"] = "char_protagonist_01"
                bad_shots[0]["staging"]["character_material_id"] = "mat_original"
                bad_shots[-1]["staging"]["character_id"] = "char_protagonist_01"
                bad_shots[-1]["staging"]["character_material_id"] = "mat_mutated"
                with self.assertRaises(UnsupportedSceneError):
                    validate_entity_continuity(bad_shots, inv, "zach-d-films")

                # T07 & T08: Sample Three.js WebGL telemetry on elevator shots (button contact & cutaways)
                sample_t = collect_camera_trace_samples(sb, fps=30)
                trace_res = _run_render_node(
                    "node", PROJECT_ROOT / "director" / "render_node.mjs",
                    ["trace", eng["entry_html"], ",".join(f"{t:.4f}" for t in sample_t), "1", pf.webgl_backend],
                    pf.browser_executable, run_dir / "trace_ik.log",
                )
                traces = list(trace_res.get("traces") or [])
                contact_hits = [
                    r["telemetry"]["contact"] for r in traces
                    if isinstance((r.get("telemetry") or {}).get("contact"), dict)
                    and r["telemetry"]["contact"].get("phase") == "contact_press"
                ]
                self.assertTrue(contact_hits, "Expected at least one physical elevator button contact_press sample")
                best_err = min(float(c["world_error_m"]) for c in contact_hits)
                self.assertLessEqual(best_err, 0.025, f"Fingertip missed physical elevator button: {contact_hits}")
                self.assertTrue(any(float(c.get("button_depress_m", 0.0)) >= 0.004 for c in contact_hits))

                cutaways = [
                    r["telemetry"]["cutaway"] for r in traces
                    if isinstance((r.get("telemetry") or {}).get("cutaway"), dict)
                ]
                self.assertGreaterEqual(len(cutaways), 2, "Expected layered cutaway telemetry on cabinet & shaft shots")
                for cw in cutaways:
                    self.assertGreaterEqual(int(cw.get("layers_count", 0)), 3, cw)
                    self.assertGreaterEqual(int(cw.get("components_count", 0)), 2, cw)

                # Negative T07 & T08: Missing/missed contact & single-layer cutaway fail audit_camera_execution
                cam_trace = evaluate_camera_trace_accuracy(sb, json.loads((run_dir / "camera_paths.json").read_text(encoding="utf-8")), traces)
                bad_traces = json.loads(json.dumps(traces))
                for r in bad_traces:
                    if isinstance((r.get("telemetry") or {}).get("contact"), dict):
                        r["telemetry"]["contact"]["world_error_m"] = 0.095
                    if isinstance((r.get("telemetry") or {}).get("cutaway"), dict):
                        r["telemetry"]["cutaway"]["layers_count"] = 1
                        r["telemetry"]["cutaway"]["components_count"] = 1
                perc_stub = [{"shot_id": s["shot_id"], "intra_mad_masked": 4.0} for s in sb["shots"]]
                audit_bad = audit_camera_execution(sb, perc_stub, cam_trace, bad_traces, "zach-d-films")
                self.assertEqual(audit_bad["status"], "FAIL", audit_bad)
                self.assertTrue(any("contact IK error" in msg for msg in audit_bad["issues"]), audit_bad["issues"])
                self.assertTrue(any("cutaway" in msg for msg in audit_bad["issues"]), audit_bad["issues"])
            finally:
                ProvenanceGuard.deactivate()

    def test_t09_t10_mixed_domain_dispatch_and_unsupported_domain_reporting(self) -> None:
        """T09/T10: Per-shot multi-domain routing (Roman->phone->cosmos) & bicycle unsupported-domain guard."""
        mixed_script = (
            "A Roman gladiator stepped onto the arena sand holding a silver denarius. "
            "Centuries later, your finger taps send on a smartphone screen to message a friend. "
            "Instantly, the signal leaps into the stars of deep cosmic space."
        )
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "mixed"
            run_dir.mkdir(parents=True)
            parsed = _mock_parsed(mixed_script)
            style_dec, _, _ = route_and_lock_style(project_root=PROJECT_ROOT, raw_input=mixed_script, cli_skill="zach-d-films")
            try:
                sb = build_storyboard_and_bible(parsed, style_dec, run_dir, fps=30, seed=51)
                gens = [s["procedural_generator"] for s in sb["shots"]]
                self.assertIn("zach3d:roman_historical_stage", gens)
                self.assertIn("zach3d:human_device_stage", gens)
                self.assertIn("zach3d:cosmic_scale_bridge_stage", gens)
                eng = build_locked_engine_workspace("zach-d-films", PROJECT_ROOT, run_dir, sb, parsed)
                shots_js = (Path(eng["entry_html"]).parent / "src" / "shots.js").read_text(encoding="utf-8")
                self.assertIn("makeSmartphoneRig", shots_js)
                self.assertIn("makeCosmicGenesisRig", shots_js)
                self.assertIn("arenaStage", shots_js)
            finally:
                ProvenanceGuard.deactivate()

        # T10: Unsupported specific domain ("bicycle shifts gears") must flag explicitly & fail when exact required
        bike_script = "When a bicycle shifts gears, the rear derailleur pushes the steel chain across cassette sprockets."
        bike_parsed = _mock_parsed(bike_script)
        bike_ev = extract_semantic_visual_events(bike_parsed, selected_skill="zach-d-films", seed=12)
        self.assertEqual(bike_ev["events"][0]["unsupported_exact_domain"], "bicycle_drivetrain")
        with self.assertRaises(UnsupportedSceneError):
            compile_scene_entities(bike_ev, "zach-d-films", seed=12, require_exact_scene=True)
        # Non-strict mode marks explicit `stylized_schematic` representation (never silently pretends exact armor)
        inv_fallback = compile_scene_entities(bike_ev, "zach-d-films", seed=12, require_exact_scene=False)
        item0 = next(iter(inv_fallback["by_event"].values()))
        self.assertIn("SCHEMATIC", item0["asset"]["representation"])
        self.assertIn("UNSUPPORTED", item0["asset"]["representation"])
        self.assertEqual(item0["asset"]["procedural_generator"], "zach3d:schematic_mechanism_stage")

    def test_t11_t12_non_adjacent_clone_and_caption_only_motion_traps(self) -> None:
        """T11/T12: Catch non-adjacent duplicates with renamed metadata AND catch caption-only fake motion."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)

            # T11: Shot 0 and Shot 2 have identical visual content while Shot 1 is different; metadata labels differ!
            def draw_clone_trap(img, t, f, n):
                dr = ImageDraw.Draw(img)
                if 1.0 <= t < 2.0:
                    dr.rectangle([0, 0, 270, 480], fill=(18, 120, 80))
                    dr.ellipse([60, 120, 210, 270], fill=(240, 210, 40))
                else:
                    dr.rectangle([0, 0, 270, 480], fill=(28, 36, 74))
                    dr.rectangle([45, 95, 225, 240], fill=(210, 75, 45))

            mp4_dup = _make_synthetic_video(td_path / "dup_trap.mp4", 3.0, fps=30, draw_fn=draw_clone_trap)
            fake_shots = [
                {"shot_id": "shot_00", "start": 0.0, "end": 1.0, "duration": 1.0, "setup_type": "alpha_stage", "scene_family": "a", "scale_level": "wide", "camera": {"framing": "WS", "angle": "eye", "movement": "push_in"}, "staging": {"subject": "sub_a", "background_theme": "day", "verb_action": "idle"}},
                {"shot_id": "shot_01", "start": 1.0, "end": 2.0, "duration": 1.0, "setup_type": "beta_stage", "scene_family": "b", "scale_level": "cu", "camera": {"framing": "CU", "angle": "low", "movement": "orbit"}, "staging": {"subject": "sub_b", "background_theme": "dusk", "verb_action": "spin"}},
                {"shot_id": "shot_02", "start": 2.0, "end": 3.0, "duration": 1.0, "setup_type": "gamma_renamed_stage", "scene_family": "c", "scale_level": "ecu", "camera": {"framing": "ECU", "angle": "high", "movement": "crane"}, "staging": {"subject": "sub_c", "background_theme": "night", "verb_action": "glow"}},
            ]
            from director.scene_diversity_qa import build_shot_semantic_fingerprints
            fps = build_shot_semantic_fingerprints(fake_shots)
            perc = sample_perceptual_frames(mp4_dup, fake_shots, mask_captions=True)
            rep = detect_adjacent_repetitions(fake_shots, fps, perceptual_pairs=perc["adjacent_pairs"], all_pairs=perc["all_pairs"])
            self.assertEqual(rep["status"], "FAIL", rep)
            self.assertIn("shot_00->shot_02", rep["hard_clones"])

            # T12: Freeze 3D scene completely; animate bright flashing text ONLY in caption zone (y=64%..82%)
            def draw_caption_only_motion(img, t, f, n):
                dr = ImageDraw.Draw(img)
                dr.rectangle([40, 80, 230, 220], fill=(95, 130, 175))
                cap_c = (255, 255, 255) if (f % 4 < 2) else (10, 10, 10)
                dr.rectangle([20, int(480 * 0.67), 250, int(480 * 0.78)], fill=cap_c)

            mp4_cap = _make_synthetic_video(td_path / "caption_only.mp4", 2.0, fps=30, draw_fn=draw_caption_only_motion)
            static_shots = [{"shot_id": "shot_00", "start": 0.0, "end": 2.0, "duration": 2.0, "setup_type": "demo", "camera": {}, "staging": {}}]
            perc_cap = sample_perceptual_frames(mp4_cap, static_shots, mask_captions=True)
            mot = audit_intra_shot_motion(perc_cap["samples"], static_shots, "zach-d-films", max_static_hold_sec=1.0)
            self.assertEqual(mot["status"], "FAIL", mot)
            self.assertEqual(mot["max_static_hold_sec_limit"], 1.0)

    def test_t13_to_t20_audio_sync_style_lock_disk_determinism_and_camera_lock(self) -> None:
        """T13/T14/T16/T17/T18/T19/T20: Button SFX contact lock, style-lock error, seed determinism, disk guard, camera lock."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "contracts"
            run_dir.mkdir(parents=True)
            parsed = _mock_parsed(ELEVATOR_HERO_SCRIPT)
            style_dec, _, _ = route_and_lock_style(project_root=PROJECT_ROOT, raw_input=ELEVATOR_HERO_SCRIPT, cli_skill="zach-d-films")
            try:
                sb1 = build_storyboard_and_bible(parsed, style_dec, run_dir, fps=30, seed=404, edit_energy="dynamic", scene_novelty="high")
                cam1 = json.loads((run_dir / "camera_paths.json").read_text(encoding="utf-8"))
                # T16: Re-run with identical seed -> identical camera_paths.json
                run_dir2 = Path(td) / "contracts2"
                run_dir2.mkdir(parents=True)
                sb2 = build_storyboard_and_bible(parsed, style_dec, run_dir2, fps=30, seed=404, edit_energy="dynamic", scene_novelty="high")
                cam2 = json.loads((run_dir2 / "camera_paths.json").read_text(encoding="utf-8"))
                self.assertEqual(cam1, cam2)
                self.assertEqual(sb1["shots"][0]["staging"]["character_id"], sb2["shots"][0]["staging"]["character_id"])

                # T13: Audio SFX alignment on elevator button press (within 1 frame @ 30fps = 0.033s)
                ap = build_audio_narrative_plan(parsed, sb1, run_dir, sfx_density="balanced")
                btn_shots = [s for s in sb1["shots"] if s.get("procedural_generator") == "zach3d:elevator_lobby_button_stage"]
                self.assertTrue(btn_shots)
                ca = btn_shots[0]["staging"]["contact_action"]
                hit_abs = float(ca["hit_time_sec"])
                btn_cues = [e for e in ap["sfx"] if e.get("intent") == "elevator_button_click"]
                self.assertTrue(btn_cues, ap["sfx"])
                self.assertLessEqual(abs(float(btn_cues[0]["time_sec"]) - hit_abs), 0.034)

                # T20: Elevator storyline uses >= 4 distinct mechanical/architectural archetypes
                gens = {s["procedural_generator"] for s in sb1["shots"]}
                self.assertGreaterEqual(len(gens), 4, gens)

                # T19: Explicit camera lock preserves exact keyframes untouched
                locked_kfs = [
                    {"t_norm": 0.0, "pos": [0.99, 1.55, 2.22], "look": [0.0, 1.15, 0.0], "fov": 28.0, "roll": 0.0, "ease": "linear"},
                    {"t_norm": 1.0, "pos": [0.99, 1.55, 2.22], "look": [0.0, 1.15, 0.0], "fov": 28.0, "roll": 0.0, "ease": "linear"},
                ]
                custom_shot = json.loads(json.dumps(sb1["shots"][0]))
                custom_shot["camera"]["camera_locked"] = True
                custom_shot["camera"]["locked_camera_keyframes"] = locked_kfs
                inv = compile_scene_entities(json.loads((run_dir / "visual_events.json").read_text(encoding="utf-8")), "zach-d-films", seed=404)
                cp_locked = build_camera_plan([custom_shot], "zach-d-films", fps=30, seed=404)
                self.assertEqual(cp_locked["paths"][0]["keyframes"], locked_kfs)

                # T14: Cross-engine forbidden path triggers StyleLockViolationError via audit hook
                with self.assertRaises(StyleLockViolationError):
                    (PROJECT_ROOT / "vendor" / "claude-animation-skills" / "skills" / "graph" / "build.py").read_text(encoding="utf-8")

                # T17: DiskBudgetGuard fail-closed when required bytes exceed disk headroom
                dg = DiskBudgetGuard(run_dir)
                blocked = dg.check(required_bytes=10 ** 15)
                self.assertFalse(blocked["ok"])
                self.assertEqual(blocked["status"], "DISK_BUDGET_BLOCKED")

                # T18: validate_coverage and validate_visual_event_graph fail closed on bad timings/missing ZDF trace
                bad_ev = json.loads((run_dir / "visual_events.json").read_text(encoding="utf-8"))
                bad_ev["events"][0]["start_sec"] = 5.0
                bad_ev["events"][0]["end_sec"] = 2.0
                with self.assertRaises(ValueError):
                    validate_visual_event_graph(bad_ev, "zach-d-films")

                qa_missing_trace = run_scene_diversity_qa(run_dir, Path(td) / "nonexistent.mp4", sb1)
                self.assertEqual(qa_missing_trace["overall_status"], "FAIL")
            finally:
                ProvenanceGuard.deactivate()


if __name__ == "__main__":
    unittest.main()
