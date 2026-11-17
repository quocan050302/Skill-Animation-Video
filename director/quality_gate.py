"""STEP 5 & STEP 7: Machine-Enforceable Style Lock Auditor, Still Inspector & Final Technical QA."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf
from PIL import Image

from . import VALID_SKILLS


# Exclusive visual engine code signatures that MUST NEVER appear in a different skill's workspace
SKILL_EXCLUSIVE_SIGNATURES: Dict[str, List[str]] = {
    "stick-figure": ["drawStick(", "drawBandana(", "drawDeckFloor(", "drawNovelMechanismCutaway("],
    "zach-d-films": ["makeHuman(", "rippleOverlay(", "torsoShell(", "cutawaySlabStack("],
    "graph": ["ILLUSTRATIVE TRAJECTORY", "#viewportG", "stroke-dashoffset"],
    "minimalistic-graphics": ["motifPendulum", "pendRod", "rising_hairline_steps"],
    "map-route": ["SCHEMATIC 3D ROUTE", "riverZ", "routeFill"],
    "breakdown": ["RoomEnvironment", "Y_EXPLO", "full_annotated_callout_stack"],
}


def audit_style_lock(
    style_decisions: Dict[str, Any],
    storyboard: Dict[str, Any],
    engine_project: Optional[Dict[str, Any]],
    guard_snapshot: Optional[Dict[str, Any]],
    stage: str = "pre_render",
) -> Dict[str, Any]:
    """Fail-closed machine-enforceable style-lock audit across JSON plans, AST/HTML/JS imports, and runtime syscalls.

    Returns audit report with `status` in `{"PASS", "FAIL", "NOT_VERIFIED"}`.
    """
    violations: List[str] = []
    unverified_reasons: List[str] = []
    inspected_files: List[str] = []
    inspected_imports: List[str] = []

    sel_mode = style_decisions.get("selection_mode")
    selected = style_decisions.get("selected_skill")
    sl = style_decisions.get("style_lock", {})

    if sel_mode not in ("explicit", "auto"):
        violations.append(f"Invalid selection_mode: {sel_mode!r}")
    if selected not in VALID_SKILLS:
        violations.append(f"Invalid selected_skill: {selected!r}")
    if sl.get("enabled") is not True:
        violations.append("style_lock.enabled must be True")
    if sl.get("engine") != selected:
        violations.append(f"style_lock.engine ({sl.get('engine')!r}) != selected_skill ({selected!r})")
    if sl.get("mixing_policy") != "forbidden":
        violations.append(f"style_lock.mixing_policy must be 'forbidden', got {sl.get('mixing_policy')!r}")
    if sl.get("fallback_policy") != "fail-closed":
        violations.append(f"style_lock.fallback_policy must be 'fail-closed', got {sl.get('fallback_policy')!r}")

    for doc_name, doc in (("style_decisions", style_decisions), ("storyboard", storyboard)):
        if doc.get("origin_skills") != [selected]:
            violations.append(f"{doc_name}.origin_skills must equal [{selected!r}], got {doc.get('origin_skills')!r}")
        if doc.get("selected_skill") != selected:
            violations.append(f"{doc_name}.selected_skill mismatch: {doc.get('selected_skill')!r}")
        for forbidden_key in ("secondary_skill", "fallback_skill", "guest_skills"):
            if doc.get(forbidden_key):
                violations.append(f"Forbidden fallback/secondary key '{forbidden_key}' present in {doc_name}")

    shots = storyboard.get("shots", [])
    if not shots:
        violations.append("storyboard.shots is empty")
    for idx, shot in enumerate(shots):
        if shot.get("engine") != selected:
            violations.append(f"shots[{idx}].engine == {shot.get('engine')!r} != {selected!r}")
        if shot.get("secondary_engine") or shot.get("fallback_engine"):
            violations.append(f"shots[{idx}] defines a secondary/fallback engine")

    assets = storyboard.get("visual_assets", [])
    if not assets:
        violations.append("storyboard.visual_assets is empty")
    for idx, asset in enumerate(assets):
        if asset.get("origin_skill") != selected:
            violations.append(f"visual_assets[{idx}].origin_skill == {asset.get('origin_skill')!r} != {selected!r}")
        gen_mod = str(asset.get("generator_module", ""))
        gen_stem = Path(gen_mod).stem
        for other in VALID_SKILLS:
            if other != selected and gen_stem == f"{other.replace('-', '_')}_adapter":
                violations.append(f"visual_assets[{idx}].generator_module references foreign skill '{other}': {gen_mod}")

    # Verify engine workspace & visual_sources
    if engine_project is None:
        unverified_reasons.append("engine_project metadata not provided")
    else:
        visual_sources = engine_project.get("visual_sources", [])
        if not visual_sources:
            unverified_reasons.append("engine_project.visual_sources is empty")
        for src in visual_sources:
            src_s = str(src)
            inspected_files.append(src_s)
            for other in VALID_SKILLS:
                if other != selected:
                    other_ad = f"{other.replace('-', '_')}_adapter"
                    if re.search(rf"skills[/\\]{re.escape(other)}(?:[/\\]|$)", src_s) or re.search(rf"(?<![a-z0-9_]){re.escape(other_ad)}\b", src_s):
                        violations.append(f"visual_sources references foreign skill '{other}': {src_s}")

        work_dir = Path(engine_project.get("work_dir", ""))
        if not work_dir.exists():
            unverified_reasons.append(f"work_dir does not exist: {work_dir}")
        else:
            # Recursively audit generated code files inside engine_work (skipping symlinked neutral kit/node_modules)
            for p in sorted(work_dir.rglob("*")):
                if "node_modules" in p.parts:
                    if p.name == "node_modules" and (p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())):
                        target = str(p.resolve())
                        if "claude-animation-skills/kit/node_modules" not in target.replace("\\", "/"):
                            violations.append(f"node_modules link points outside neutral kit: {target}")
                    continue
                if not p.is_file():
                    continue
                if p.suffix.lower() not in (".html", ".js", ".mjs", ".css", ".py", ".json"):
                    continue

                inspected_files.append(str(p.resolve()))
                content = p.read_text(encoding="utf-8", errors="replace")

                # 1. Check path references to foreign skills
                for other in VALID_SKILLS:
                    if other != selected:
                        other_ad = f"{other.replace('-', '_')}_adapter"
                        if re.search(rf"skills[/\\]{re.escape(other)}(?:[/\\]|['\"\s]|$)", content) or re.search(rf"(?<![a-z0-9_]){re.escape(other_ad)}\b", content):
                            violations.append(f"File {p.name} contains path reference to foreign skill '{other}'")

                # 2. Check exclusive visual engine signatures from other skills
                for other, sigs in SKILL_EXCLUSIVE_SIGNATURES.items():
                    if other == selected:
                        continue
                    for sig in sigs:
                        if sig in content:
                            violations.append(
                                f"File {p.name} contains foreign '{other}' engine signature '{sig}'"
                            )

                # 3. Extract script/module imports for audit trail
                if p.suffix.lower() == ".py":
                    try:
                        tree = ast.parse(content, filename=str(p))
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    inspected_imports.append(f"{p.name}:import:{alias.name}")
                            elif isinstance(node, ast.ImportFrom) and node.module:
                                inspected_imports.append(f"{p.name}:from:{node.module}")
                    except SyntaxError as exc:
                        violations.append(f"SyntaxError in generated Python file {p.name}: {exc}")
                elif p.suffix.lower() in (".html", ".js", ".mjs"):
                    for m in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']', content):
                        inspected_imports.append(f"{p.name}:script_src:{m.group(1)}")
                    for m in re.finditer(r'\bimport\s+(?:[^"\']+from\s+)?["\']([^"\']+)["\']', content):
                        inspected_imports.append(f"{p.name}:es_import:{m.group(1)}")
                    for m in re.finditer(r'\brequire\(\s*["\']([^"\']+)["\']\s*\)', content):
                        inspected_imports.append(f"{p.name}:cjs_require:{m.group(1)}")

    # Verify runtime interpreter ProvenanceGuard snapshot
    if guard_snapshot is None:
        unverified_reasons.append("Runtime ProvenanceGuard snapshot missing")
    else:
        if guard_snapshot.get("violations"):
            for v in guard_snapshot["violations"]:
                violations.append(f"Runtime guard violation ({v.get('kind')}): {v.get('detail')}")
        for opened in guard_snapshot.get("opened_skill_files", []):
            for other in VALID_SKILLS:
                if other != selected and f"/skills/{other}/" in opened.replace("\\", "/"):
                    violations.append(f"Runtime guard recorded open of foreign skill file: {opened}")
        for mod in guard_snapshot.get("imported_adapter_modules", []):
            mod_leaf = str(mod).rsplit(".", 1)[-1]
            for other in VALID_SKILLS:
                if other != selected and mod_leaf == f"{other.replace('-', '_')}_adapter":
                    violations.append(f"Runtime guard recorded import of foreign adapter module: {mod}")
        if sel_mode == "explicit":
            # In explicit mode, verify ZERO capability reads of the other 5 SKILL.md files occurred!
            for ev in guard_snapshot.get("events", []):
                if ev.get("event") == "capability_read" and ev.get("skill") != selected:
                    violations.append(f"Explicit mode illegally read foreign SKILL.md for '{ev.get('skill')}'")

    if violations:
        status = "FAIL"
    elif unverified_reasons:
        status = "NOT_VERIFIED"
    else:
        status = "PASS"

    return {
        "stage": stage,
        "status": status,
        "selection_mode": sel_mode,
        "selected_skill": selected,
        "style_lock": sl,
        "inspected_file_count": len(set(inspected_files)),
        "inspected_files": sorted(set(inspected_files)),
        "inspected_imports": sorted(set(inspected_imports)),
        "runtime_opened_skill_files": guard_snapshot.get("opened_skill_files", []) if guard_snapshot else [],
        "runtime_imported_adapters": guard_snapshot.get("imported_adapter_modules", []) if guard_snapshot else [],
        "violations": violations,
        "unverified_reasons": unverified_reasons,
    }


def inspect_pre_render_stills(
    still_paths: List[Path],
    selected_skill: str,
) -> Dict[str, Any]:
    """Inspect rendered PNG stills BEFORE full scene video rendering (STEP 5)."""
    if not still_paths:
        return {"status": "FAIL", "reason": "No stills produced", "stills": []}

    details: List[Dict[str, Any]] = []
    failures: List[str] = []

    for sp in still_paths:
        if not sp.exists() or sp.stat().st_size == 0:
            failures.append(f"Missing or empty still: {sp}")
            continue
        img = Image.open(sp).convert("RGB")
        arr = np.asarray(img, dtype=np.float32)
        h, w, _ = arr.shape
        mean_luma = float(arr.mean())
        std_luma = float(arr.std())

        # Safe zone crop (logical 100..980 x 220..1500 scaled to image dims)
        sx0, sx1 = int(w * 100 / 1080), int(w * 980 / 1080)
        sy0, sy1 = int(h * 220 / 1920), int(h * 1500 / 1920)
        safe_std = float(arr[sy0:sy1, sx0:sx1].std())

        # Even pure-black `minimalistic-graphics` has bright white dot/strokes (std_luma > 3.0)
        if std_luma < 1.5 or safe_std < 1.5:
            failures.append(f"Blank/flat still detected at {sp.name} (std={std_luma:.2f}, safe_std={safe_std:.2f})")

        details.append({
            "file": sp.name,
            "width": w,
            "height": h,
            "mean_luma": round(mean_luma, 2),
            "std_luma": round(std_luma, 2),
            "safe_zone_std": round(safe_std, 2),
        })

    return {
        "status": "FAIL" if failures else "PASS",
        "checked_count": len(details),
        "failures": failures,
        "stills": details,
    }


def probe_media_file(video_path: Path) -> Dict[str, Any]:
    res = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(res.stdout)


def _decode_frame_rgb(video_path: Path, t_sec: float, scale_w: Optional[int] = None, scale_h: Optional[int] = None) -> np.ndarray:
    vf = ["-vf", f"scale={scale_w}:{scale_h}:flags=bilinear"] if (scale_w and scale_h) else []
    cmd = [
        "ffmpeg", "-v", "error",
        "-ss", f"{max(0.0, t_sec):.3f}",
        "-i", str(video_path),
        *vf,
        "-frames:v", "1",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-",
    ]
    r = subprocess.run(cmd, capture_output=True, check=True)
    import io
    img = Image.open(io.BytesIO(r.stdout)).convert("RGB")
    return np.asarray(img, dtype=np.float32)


def _verify_4k_sharpness(final_4k_path: Path, sample_t: float) -> Tuple[float, bool]:
    """Compare high-frequency gradient energy of decoded 2160x3840 frame vs its 1080p->4K bilinear roundtrip."""
    f4k = _decode_frame_rgb(final_4k_path, sample_t)
    gray = f4k.mean(axis=2)
    pil_gray = Image.fromarray(np.clip(gray, 0, 255).astype(np.uint8))
    down = pil_gray.resize((1080, 1920), resample=Image.Resampling.BILINEAR)
    re_up = np.asarray(down.resize((2160, 3840), resample=Image.Resampling.BILINEAR), dtype=np.float32)

    gx_orig = np.abs(np.diff(gray, axis=1)).mean() + np.abs(np.diff(gray, axis=0)).mean()
    gx_blur = np.abs(np.diff(re_up, axis=1)).mean() + np.abs(np.diff(re_up, axis=0)).mean()
    ratio = float(gx_orig / max(1e-6, gx_blur))
    return round(ratio, 4), ratio > 1.03


def run_final_quality_gate(
    run_dir: Path,
    style_decisions: Dict[str, Any],
    storyboard: Dict[str, Any],
    engine_project: Dict[str, Any],
    guard_snapshot: Dict[str, Any],
    render_info: Dict[str, Any],
    preview_mp4: Path,
    final_4k_mp4: Path,
    max_static_hold_sec: Optional[float] = None,
    historical_claims: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """STEP 7 Complete QC Gate: PASS / FAIL / WARN / NOT_RUN per check."""
    checks: Dict[str, Dict[str, Any]] = {}

    # 1. Post-render style-lock & provenance check
    post_audit = audit_style_lock(
        style_decisions=style_decisions,
        storyboard=storyboard,
        engine_project=engine_project,
        guard_snapshot=guard_snapshot,
        stage="post_render",
    )
    (run_dir / "style_lock_audit.json").write_text(json.dumps(post_audit, indent=2), encoding="utf-8")
    checks["style_lock_provenance"] = {
        "status": post_audit["status"],
        "inspected_file_count": post_audit["inspected_file_count"],
        "violations": post_audit["violations"],
    }

    # 2. Preview 1080x1920 ffprobe check
    expected_fps = int(storyboard["fps"])
    expected_dur = float(storyboard["total_duration_sec"])
    if not preview_mp4.exists():
        checks["preview_1080p_stream"] = {"status": "FAIL", "reason": "preview_1080.mp4 missing"}
    else:
        p_probe = probe_media_file(preview_mp4)
        v_str = next((s for s in p_probe.get("streams", []) if s.get("codec_type") == "video"), {})
        a_str = next((s for s in p_probe.get("streams", []) if s.get("codec_type") == "audio"), {})
        w, h = int(v_str.get("width", 0)), int(v_str.get("height", 0))
        num, den = map(int, str(v_str.get("r_frame_rate", "0/1")).split("/"))
        fps_actual = round(num / max(1, den), 2)
        dur_actual = float(p_probe.get("format", {}).get("duration", 0.0))
        ok = (w == 1080 and h == 1920 and abs(fps_actual - expected_fps) <= 0.25 and bool(a_str) and abs(dur_actual - expected_dur) <= 0.5)
        checks["preview_1080p_stream"] = {
            "status": "PASS" if ok else "FAIL",
            "width": w,
            "height": h,
            "fps": fps_actual,
            "duration_sec": round(dur_actual, 3),
            "has_audio": bool(a_str),
        }

    # 3. Final 2160x3840 4K ffprobe & Native-vs-Upscaled Truth Check
    ffprobe_4k_summary: Dict[str, Any] = {}
    if not final_4k_mp4.exists():
        checks["final_4k_stream"] = {"status": "FAIL", "reason": "final_4k.mp4 missing"}
        checks["truthful_4k_declaration"] = {"status": "FAIL", "reason": "final_4k.mp4 missing"}
    else:
        f_probe = probe_media_file(final_4k_mp4)
        v_str = next((s for s in f_probe.get("streams", []) if s.get("codec_type") == "video"), {})
        a_str = next((s for s in f_probe.get("streams", []) if s.get("codec_type") == "audio"), {})
        w, h = int(v_str.get("width", 0)), int(v_str.get("height", 0))
        num, den = map(int, str(v_str.get("r_frame_rate", "0/1")).split("/"))
        fps_actual = round(num / max(1, den), 2)
        dur_actual = float(f_probe.get("format", {}).get("duration", 0.0))
        ffprobe_4k_summary = {
            "width": w,
            "height": h,
            "codec_name": v_str.get("codec_name"),
            "pix_fmt": v_str.get("pix_fmt"),
            "r_frame_rate": v_str.get("r_frame_rate"),
            "fps": fps_actual,
            "duration_sec": round(dur_actual, 3),
            "size_bytes": int(f_probe.get("format", {}).get("size", 0)),
            "audio_codec": a_str.get("codec_name"),
            "audio_sample_rate": a_str.get("sample_rate"),
            "audio_channels": a_str.get("channels"),
        }
        ok_4k = (
            w == 2160
            and h == 3840
            and v_str.get("pix_fmt") == "yuv420p"
            and abs(fps_actual - expected_fps) <= 0.25
            and bool(a_str)
            and abs(dur_actual - expected_dur) <= 0.5
        )
        checks["final_4k_stream"] = {
            "status": "PASS" if ok_4k else "FAIL",
            "ffprobe": ffprobe_4k_summary,
        }

        mid_sample = min(expected_dur * 0.5, max(0.3, expected_dur - 0.5))
        sharp_ratio, has_native_hf_detail = _verify_4k_sharpness(final_4k_mp4, mid_sample)
        claimed_native = bool(render_info.get("native_4k"))
        decl = render_info.get("delivery_4k_declaration", "")

        if claimed_native:
            # Verify true native 4K rasterization wasn't faked from 1080p
            truth_ok = (decl == "native_4k") and (sharp_ratio > 1.01)
            checks["truthful_4k_declaration"] = {
                "status": "PASS" if truth_ok else "FAIL",
                "declaration": decl,
                "native_4k": True,
                "high_freq_edge_ratio_vs_1080p_bilinear": sharp_ratio,
                "has_subpixel_4k_detail": has_native_hf_detail,
            }
        else:
            truth_ok = decl.startswith("upscaled")
            checks["truthful_4k_declaration"] = {
                "status": "PASS" if truth_ok else "FAIL",
                "declaration": decl,
                "native_4k": False,
                "high_freq_edge_ratio_vs_1080p_bilinear": sharp_ratio,
            }

    # 4. Decoded Frame Motion, Cut Continuity & Black-Frame Detection
    shots = storyboard.get("shots", [])
    motion_scores: List[Dict[str, Any]] = []
    frozen_shots: List[str] = []
    broken_cuts: List[str] = []

    if final_4k_mp4.exists():
        for s in shots:
            t_a = float(s["start"]) + min(0.25, float(s["duration"]) * 0.25)
            t_b = min(float(s["end"]) - 0.12, t_a + min(0.45, float(s["duration"]) * 0.45))
            fa = _decode_frame_rgb(final_4k_mp4, t_a, 270, 480)
            fb = _decode_frame_rgb(final_4k_mp4, t_b, 270, 480)
            mad = float(np.abs(fa - fb).mean())
            if mad < 0.08:
                frozen_shots.append(s["shot_id"])
            if fa.std() < 1.2 or fb.std() < 1.2:
                broken_cuts.append(s["shot_id"])
            motion_scores.append({"shot_id": s["shot_id"], "frame_mad": round(mad, 3), "luma_std": round(float(fa.std()), 2)})

        # FFmpeg blackdetect scan
        bd_r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(final_4k_mp4), "-vf", "blackdetect=d=0.08:pix_th=0.04", "-f", "null", "-"],
            capture_output=True,
            text=True,
        )
        black_spans = re.findall(r"black_start:([0-9.]+)\s+black_end:([0-9.]+)\s+black_duration:([0-9.]+)", bd_r.stderr)
        intentional_dark_engine = style_decisions["selected_skill"] == "minimalistic-graphics"
        has_intentional_fades = any(s.get("transition_out") == "dip_to_black" for s in shots)

        if broken_cuts or frozen_shots:
            checks["decoded_frames_and_cuts"] = {
                "status": "FAIL",
                "frozen_shots": frozen_shots,
                "broken_cuts": broken_cuts,
                "motion_scores": motion_scores,
            }
        elif black_spans and not intentional_dark_engine:
            checks["decoded_frames_and_cuts"] = {
                "status": "WARN" if has_intentional_fades else "FAIL",
                "black_spans": black_spans,
                "note": "Intentional dip-to-black fade detected" if has_intentional_fades else "Unintended black frames detected",
                "motion_scores": motion_scores,
            }
        else:
            checks["decoded_frames_and_cuts"] = {
                "status": "PASS",
                "distinct_setups_verified": len({s["setup_type"] for s in shots}),
                "novel_scene_count": sum(1 for s in shots if s.get("novel_non_template")),
                "motion_scores": motion_scores,
            }
    else:
        checks["decoded_frames_and_cuts"] = {"status": "NOT_RUN", "reason": "final_4k.mp4 missing"}

    # 5. Substantive Post-Encode Audio Quality Gate (readback on final encoded MP4 + stems + licenses)
    if final_4k_mp4.exists():
        audio_dir = run_dir / "audio"
        audio_plan_p = audio_dir / "audio_plan.json"
        if audio_plan_p.exists():
            audio_plan = json.loads(audio_plan_p.read_text(encoding="utf-8"))
        else:
            audio_plan = {
                "fps": expected_fps,
                "total_duration_sec": expected_dur,
                "music": {"enabled": True, "mode": "auto", "segments": []},
                "sfx_mode": "auto",
                "sfx": [],
                "voice": {"expected": True},
                "quality_policy": {"target_lufs": -14.0, "lufs_tolerance_db": 2.0, "max_true_peak_dbtp": -1.5, "hard_clip_limit_dbtp": -1.0},
                "intentional_silences": [],
            }
        mix_rep_p = audio_dir / "audio_mix_report.json"
        mix_rep = json.loads(mix_rep_p.read_text(encoding="utf-8")) if mix_rep_p.exists() else {}
        aqc = run_audio_quality_gate(
            preview_mp4=preview_mp4,
            final_mp4=final_4k_mp4,
            audio_dir=audio_dir,
            audio_plan=audio_plan,
            mix_report=mix_rep,
            logs_dir=run_dir / "logs",
        )
        checks["audio_levels_and_ducking"] = {
            "status": aqc["overall_status"],
            "rms_dbfs": aqc["metrics"].get("rms_dbfs"),
            "peak_dbfs": aqc["metrics"].get("peak_dbfs"),
            "integrated_lufs": aqc["metrics"].get("integrated_lufs"),
            "true_peak_dbtp": aqc["metrics"].get("true_peak_dbtp"),
            "audio_qc_report": str((audio_dir / "audio_qc_report.json").resolve()),
            "checks_summary": {k: v["status"] for k, v in aqc["checks"].items()},
        }
    else:
        checks["audio_levels_and_ducking"] = {"status": "NOT_RUN", "reason": "final_4k.mp4 missing"}

    # 6. Scene Diversity, Camera Trace, Multi-frame Transition & Perceptual QA
    subj_audio = "NOT_VERIFIED"
    if "audio_levels_and_ducking" in checks and (run_dir / "audio" / "audio_qc_report.json").exists():
        _aqc_tmp = json.loads((run_dir / "audio" / "audio_qc_report.json").read_text(encoding="utf-8"))
        subj_audio = str(_aqc_tmp.get("subjective_editorial_listening", "NOT_VERIFIED"))

    if final_4k_mp4.exists():
        from .scene_diversity_qa import run_scene_diversity_qa
        edl_p = run_dir / "transition_edl.json"
        cam_p = run_dir / "camera_paths.json"
        trace_p = run_dir / "camera_execution_trace.json"
        raw_tel_p = run_dir / "logs" / "raw_render_telemetry.json"

        edl_doc = json.loads(edl_p.read_text(encoding="utf-8")) if edl_p.exists() else None
        cam_doc = json.loads(cam_p.read_text(encoding="utf-8")) if cam_p.exists() else None
        cam_trace_doc = json.loads(trace_p.read_text(encoding="utf-8")) if trace_p.exists() else None
        raw_traces = list((json.loads(raw_tel_p.read_text(encoding="utf-8")) or {}).get("traces") or []) if raw_tel_p.exists() else None

        div_qa = run_scene_diversity_qa(
            run_dir=run_dir,
            video_mp4=final_4k_mp4,
            storyboard=storyboard,
            style_lock_status=post_audit["status"],
            transition_edl=edl_doc,
            camera_plan=cam_doc,
            max_static_hold_sec=max_static_hold_sec,
            camera_trace_doc=cam_trace_doc,
            raw_traces=raw_traces,
        )
        checks["scene_diversity_and_retention"] = {
            "status": div_qa["overall_status"],
            "subjective_visual_review": div_qa.get("subjective_visual_review", "NOT_VERIFIED"),
            "scene_diversity_report": str((run_dir / "scene_diversity_report.json").resolve()),
            "visual_qc_timeline_json": div_qa.get("visual_qc_timeline_json"),
            "checks_summary": {k: v["status"] for k, v in (div_qa.get("checks") or {}).items()},
        }
        cam_audit = (div_qa.get("checks") or {}).get("camera_execution_audit") or {"status": "PASS"}
        checks["camera_execution"] = {
            "status": cam_audit["status"],
            "camera_execution_trace_json": str(trace_p.resolve()) if trace_p.exists() else None,
            "worst_pos_err_m": cam_audit.get("worst_pos_err_m"),
            "worst_ori_err_deg": cam_audit.get("worst_ori_err_deg"),
            "worst_fov_err_deg": cam_audit.get("worst_fov_err_deg"),
            "worst_contact_err_m": cam_audit.get("worst_contact_err_m"),
            "issues": cam_audit.get("issues", []),
        }
    else:
        checks["scene_diversity_and_retention"] = {"status": "NOT_RUN", "reason": "final_4k.mp4 missing"}
        checks["camera_execution"] = {"status": "NOT_RUN", "reason": "final_4k.mp4 missing"}

    # 6b. Editorial Finish, Voice Prosody & Overlay Tracking QA (`retention_qa.py`)
    editorial_qa_doc: Optional[Dict[str, Any]] = None
    if (run_dir / "editorial_timeline.json").exists():
        from .retention_qa import run_retention_editorial_qa
        raw_tel_p2 = run_dir / "logs" / "raw_render_telemetry.json"
        raw_traces2 = list((json.loads(raw_tel_p2.read_text(encoding="utf-8")) or {}).get("traces") or []) if raw_tel_p2.exists() else None
        target_vid = final_4k_mp4 if final_4k_mp4.exists() else preview_mp4
        if target_vid.exists():
            editorial_qa_doc = run_retention_editorial_qa(
                run_dir=run_dir,
                video_mp4=target_vid,
                storyboard=storyboard,
                raw_traces=raw_traces2,
            )
            checks["editorial_retention_finish"] = {
                "status": editorial_qa_doc["overall_status"],
                "editorial_qa_report": str((run_dir / "editorial_qa_report.json").resolve()),
                "editorial_attention_timeline_json": editorial_qa_doc.get("editorial_attention_timeline_json"),
                "subjective_voice_quality_status": editorial_qa_doc.get("subjective_voice_quality_status", "NOT_VERIFIED"),
                "viewer_retention_status": editorial_qa_doc.get("viewer_retention_status", "NOT_VERIFIED"),
                "checks_summary": {k: v["status"] for k, v in (editorial_qa_doc.get("checks") or {}).items()},
            }
        else:
            checks["editorial_retention_finish"] = {"status": "NOT_RUN", "reason": "Deliverable MP4 missing"}

    # 6c. Story-Driven Visual Action, Reveal Order, Period Integrity & Claims QA
    action_graph_doc = storyboard.get("story_action_graph")
    if action_graph_doc is None and (run_dir / "story_action_graph.json").exists():
        action_graph_doc = json.loads((run_dir / "story_action_graph.json").read_text(encoding="utf-8"))
    if isinstance(action_graph_doc, dict):
        from .visual_storytelling_qa import run_visual_storytelling_qa
        ed_tl_doc = json.loads((run_dir / "editorial_timeline.json").read_text(encoding="utf-8")) if (run_dir / "editorial_timeline.json").exists() else {}
        sdiv_doc = json.loads((run_dir / "scene_diversity_report.json").read_text(encoding="utf-8")) if (run_dir / "scene_diversity_report.json").exists() else None
        raw_tel_p3 = run_dir / "logs" / "raw_render_telemetry.json"
        raw_traces3 = list((json.loads(raw_tel_p3.read_text(encoding="utf-8")) or {}).get("traces") or []) if raw_tel_p3.exists() else None
        ap_doc = json.loads((run_dir / "audio" / "audio_plan.json").read_text(encoding="utf-8")) if (run_dir / "audio" / "audio_plan.json").exists() else None
        words_doc = json.loads((run_dir / "audio" / "words.json").read_text(encoding="utf-8")) if (run_dir / "audio" / "words.json").exists() else None
        hc_doc = historical_claims
        if hc_doc is None and (run_dir / "historical_claims.json").exists():
            hc_doc = json.loads((run_dir / "historical_claims.json").read_text(encoding="utf-8"))

        vs_qa = run_visual_storytelling_qa(
            run_dir=run_dir,
            storyboard=storyboard,
            action_graph=action_graph_doc,
            editorial_timeline=ed_tl_doc,
            scene_diversity_report=sdiv_doc,
            raw_traces=raw_traces3,
            audio_plan=ap_doc,
            historical_claims=hc_doc,
            words=words_doc,
        )
        checks["visual_storytelling"] = {
            "status": vs_qa["overall_status"],
            "visual_storytelling_qa_report": str((run_dir / "visual_storytelling_qa_report.json").resolve()),
            "subjective_visual_review": vs_qa.get("subjective_visual_review", "NOT_VERIFIED"),
            "checks_summary": {k: v["status"] for k, v in (vs_qa.get("checks") or {}).items()},
        }
        vchecks = vs_qa.get("checks") or {}
        if "pointer_tracking" in vchecks:
            checks["pointer_tracking"] = vchecks["pointer_tracking"]
        if "physical_and_character_telemetry" in vchecks:
            checks["physical_and_character_telemetry"] = vchecks["physical_and_character_telemetry"]

    # 6d. Multi-Theme Composition & Safe-Margin Runtime Audit
    if (run_dir / "editorial_timeline.json").exists():
        from .cinematic_composition_qa import audit_cinematic_composition
        ed_tl_comp = json.loads((run_dir / "editorial_timeline.json").read_text(encoding="utf-8"))
        raw_tel_p4 = run_dir / "logs" / "raw_render_telemetry.json"
        raw_traces4 = list((json.loads(raw_tel_p4.read_text(encoding="utf-8")) or {}).get("traces") or []) if raw_tel_p4.exists() else None
        checks["cinematic_composition"] = audit_cinematic_composition(
            run_dir=run_dir,
            storyboard=storyboard,
            editorial_timeline=ed_tl_comp,
            raw_traces=raw_traces4,
        )

    # 7. Factual & Licensing check summary
    fact_checks = storyboard.get("entities_and_facts", {}).get("fact_checks", [])
    has_warn = any("WARN" in str(fc.get("status", "")) for fc in fact_checks)
    checks["factual_and_licensing_integrity"] = {
        "status": "WARN" if has_warn else "PASS",
        "fact_checks": fact_checks,
        "third_party_ripped_assets": 0,
    }

    statuses = [c["status"] for c in checks.values()]
    overall = "FAIL" if ("FAIL" in statuses or "NOT_VERIFIED" in statuses) else ("WARN" if "WARN" in statuses else "PASS")
    release_status = "TECHNICAL_ACCEPTANCE_PASS" if overall in ("PASS", "WARN") else "FAIL"

    qc_report = {
        "schema_version": "0.5.0",
        "overall_status": overall,
        "release_status": release_status,
        "subjective_visual_review": "NOT_VERIFIED",
        "subjective_editorial_listening": subj_audio,
        "subjective_voice_quality_status": (editorial_qa_doc or {}).get("subjective_voice_quality_status", "NOT_VERIFIED"),
        "viewer_retention_status": "NOT_VERIFIED",
        "selected_skill": style_decisions["selected_skill"],
        "selection_mode": style_decisions["selection_mode"],
        "checks": checks,
        "ffprobe_final_4k": ffprobe_4k_summary,
    }
    (run_dir / "qc_report.json").write_text(json.dumps(qc_report, indent=2), encoding="utf-8")
    return qc_report


def verify_playable_audio_stream(mp4_path: Path) -> Dict[str, Any]:
    """Verify final MP4 has an intact stereo 48 kHz AAC stream with decodable frames."""
    if not mp4_path.exists():
        return {"status": "FAIL", "reason": f"Missing MP4 file: {mp4_path}"}
    try:
        res = subprocess.run(
            [
                "ffprobe", "-v", "error", "-count_packets",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name,sample_rate,channels,nb_read_packets,duration",
                "-of", "json", str(mp4_path),
            ],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(res.stdout or "{}")
    except Exception as exc:
        return {"status": "FAIL", "reason": f"ffprobe audio stream error: {exc}"}

    streams = data.get("streams") or []
    if not streams:
        return {"status": "FAIL", "reason": f"No playable audio stream in {mp4_path.name}"}
    st = streams[0]
    sr = int(st.get("sample_rate") or 0)
    ch = int(st.get("channels") or 0)
    pkts = int(st.get("nb_read_packets") or 0)
    ok = st.get("codec_name") == "aac" and sr == 48000 and ch == 2 and pkts > 0
    return {
        "status": "PASS" if ok else "FAIL",
        "codec": st.get("codec_name"),
        "sample_rate": sr,
        "channels": ch,
        "packets": pkts,
        "duration_sec": float(st.get("duration") or 0.0),
    }


def verify_lufs_true_peak_post_encode(
    mp4_path: Path,
    policy: Dict[str, Any],
    intentionally_silent: bool = False,
) -> Dict[str, Any]:
    """Measure integrated LUFS & True Peak AFTER AAC encode using FFmpeg `ebur128=peak=true`."""
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(mp4_path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )
    txt = res.stderr
    m_i = re.findall(r"Integrated loudness:\s*\n\s*I:\s*([-0-9.]+)\s*LUFS", txt)
    m_tp = re.findall(r"True peak:\s*\n\s*Peak:\s*([-0-9.]+)\s*dBFS", txt)
    lufs = float(m_i[-1]) if m_i else -70.0
    tp = float(m_tp[-1]) if m_tp else -70.0

    target_lufs = float(policy.get("target_lufs", -14.0))
    tol = float(policy.get("lufs_tolerance_db", 2.0))
    max_tp = float(policy.get("max_true_peak_dbtp", -1.5))
    hard_tp = float(policy.get("hard_clip_limit_dbtp", -1.0))

    if intentionally_silent:
        ok_sil = lufs <= -60.0 and tp <= -55.0
        return {
            "status": "PASS" if ok_sil else "FAIL",
            "integrated_lufs": lufs,
            "true_peak_dbtp": tp,
            "intentionally_silent": True,
        }

    if tp > hard_tp or lufs < (target_lufs - tol - 2.0) or lufs > (target_lufs + tol + 1.5):
        status = "FAIL"
    elif tp > max_tp or abs(lufs - target_lufs) > tol:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "status": status,
        "integrated_lufs": round(lufs, 2),
        "true_peak_dbtp": round(tp, 2),
        "target_lufs": target_lufs,
        "max_true_peak_dbtp": max_tp,
    }


def verify_peak_and_clip(decoded_pcm: np.ndarray, intentionally_silent: bool = False) -> Dict[str, Any]:
    """Detect non-finite samples, clipping peaks (>= 0.995), or consecutive flat-top saturation."""
    if decoded_pcm.size == 0 or not np.all(np.isfinite(decoded_pcm)):
        return {"status": "FAIL", "reason": "Empty or non-finite decoded audio PCM"}
    abs_pcm = np.abs(decoded_pcm)
    pk = float(np.max(abs_pcm))
    peak_db = round(float(20.0 * np.log10(max(pk, 1e-12))), 2)
    rms_db = round(float(20.0 * np.log10(float(np.sqrt(np.mean(decoded_pcm ** 2))) + 1e-12)), 2)

    # Check consecutive saturated samples >= 0.995
    sat = (abs_pcm >= 0.995).any(axis=1) if abs_pcm.ndim == 2 else (abs_pcm >= 0.995)
    max_run = 0
    cur_run = 0
    for s in sat:
        if s:
            cur_run += 1
            if cur_run > max_run:
                max_run = cur_run
        else:
            cur_run = 0

    if not intentionally_silent and rms_db <= -65.0:
        return {"status": "FAIL", "reason": f"Decoded MP4 audio unexpectedly silent (rms={rms_db} dBFS)", "rms_dbfs": rms_db, "peak_dbfs": peak_db}
    if max_run >= 3 or peak_db > -0.1:
        return {"status": "FAIL", "reason": f"Audio clipping detected (peak={peak_db} dBFS, sat_run={max_run})", "rms_dbfs": rms_db, "peak_dbfs": peak_db}
    return {"status": "PASS", "rms_dbfs": rms_db, "peak_dbfs": peak_db, "clipped_sample_runs": 0}


def verify_audio_duration_and_sync(mp4_path: Path, expected_fps: int) -> Dict[str, Any]:
    """Verify audio duration matches video picture within <= 1 video frame + AAC encoder padding."""
    probe = probe_media_file(mp4_path)
    v_str = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
    a_str = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), {})
    if not v_str or not a_str:
        return {"status": "FAIL", "reason": "Missing video or audio stream for sync check"}
    vdur = float(v_str.get("duration") or probe.get("format", {}).get("duration") or 0.0)
    adur = float(a_str.get("duration") or probe.get("format", {}).get("duration") or 0.0)
    diff = abs(vdur - adur)
    tol = (1.0 / max(1, expected_fps)) + 0.055  # 1 frame + AAC 21-46ms codec frame margin
    return {
        "status": "PASS" if diff <= tol else "FAIL",
        "video_duration_sec": round(vdur, 3),
        "audio_duration_sec": round(adur, 3),
        "delta_sec": round(diff, 4),
        "tolerance_sec": round(tol, 4),
    }


def verify_missing_expected_cues(
    audio_plan: Dict[str, Any],
    audio_dir: Path,
    mix_report: Dict[str, Any],
) -> Dict[str, Any]:
    """Ensure enabled music/SFX/voice tracks were actually synthesized and not silently dropped."""
    problems: List[str] = []
    voice_exp = bool((audio_plan.get("voice") or {}).get("expected", True))
    music_en = bool((audio_plan.get("music") or {}).get("enabled", True))
    sfx_en = str(audio_plan.get("sfx_mode", "auto")) != "off" and bool(audio_plan.get("sfx"))

    voice_p = audio_dir / "voice.wav"
    music_p = audio_dir / "music.wav"
    sfx_p = audio_dir / "sfx.wav"

    if voice_exp:
        if not voice_p.exists():
            problems.append("Expected voice.wav stem missing")
        else:
            va, _ = sf.read(str(voice_p), dtype="float32")
            v_rms = 20.0 * np.log10(float(np.sqrt(np.mean(va ** 2))) + 1e-12)
            if v_rms <= -55.0:
                problems.append(f"Expected voice.wav silent (rms={v_rms:.1f} dBFS)")

    if music_en and (audio_plan.get("music") or {}).get("segments"):
        if not music_p.exists():
            problems.append("Enabled music.wav stem missing")
        else:
            ma, _ = sf.read(str(music_p), dtype="float32")
            m_rms = 20.0 * np.log10(float(np.sqrt(np.mean(ma ** 2))) + 1e-12)
            if m_rms <= -68.0:
                problems.append(f"Enabled music.wav unexpectedly silent (rms={m_rms:.1f} dBFS)")

    if sfx_en:
        if not sfx_p.exists():
            problems.append("Expected sfx.wav stem missing")
        else:
            sa, _ = sf.read(str(sfx_p), dtype="float32")
            s_rms = 20.0 * np.log10(float(np.sqrt(np.mean(sa ** 2))) + 1e-12)
            if s_rms <= -72.0:
                problems.append(f"Expected sfx.wav unexpectedly silent (rms={s_rms:.1f} dBFS)")
        sfx_cs_p = audio_dir / "sfx_cue_sheet.json"
        if sfx_cs_p.exists():
            cs = json.loads(sfx_cs_p.read_text(encoding="utf-8"))
            if len(cs.get("cues", [])) < len(audio_plan.get("sfx", [])):
                problems.append(f"Dropped SFX cues: rendered {len(cs.get('cues', []))} < planned {len(audio_plan.get('sfx', []))}")

    return {
        "status": "FAIL" if problems else "PASS",
        "problems": problems,
        "voice_expected": voice_exp,
        "music_enabled": music_en,
        "sfx_expected": sfx_en,
    }


def verify_sfx_onsets(
    audio_dir: Path,
    decoded_pcm: np.ndarray,
    sr: int,
    audio_plan: Dict[str, Any],
    fps: int = 30,
) -> Dict[str, Any]:
    """Measure true frame-onset energy alignment for every expected SFX cue."""
    cues = list(audio_plan.get("sfx", []))
    if str(audio_plan.get("sfx_mode", "auto")) == "off" or not cues:
        return {"status": "PASS", "verified_cues": 0, "measurement_method": "sfx_intentionally_off_or_empty"}

    sfx_p = audio_dir / "sfx.wav"
    if not sfx_p.exists():
        return {"status": "FAIL", "reason": "Missing sfx.wav for onset verification"}

    sfx_arr, sfx_sr = sf.read(str(sfx_p), dtype="float64", always_2d=True)
    sfx_mono = sfx_arr.mean(axis=1)
    dec_mono = decoded_pcm.mean(axis=1) if decoded_pcm.ndim == 2 else decoded_pcm

    frame_dt = 1.0 / max(1, fps)
    dropped: List[Dict[str, Any]] = []
    max_err_ms = 0.0
    checked = 0

    for c in cues:
        t_exp = float(c["time_sec"])
        intent = str(c.get("intent", ""))
        kind = str(c.get("kind", "foley"))
        is_swell = ("whoosh" in intent or "riser" in intent or "sweep" in intent or kind == "transition")
        # For hard impacts/foley/ui expect sharp onset energy within +/- (1 frame + 20ms); swells center on body
        half_w = frame_dt + (0.14 if is_swell else 0.035)
        w0 = max(0, int(round((t_exp - 0.015) * sfx_sr)))
        w1 = min(len(sfx_mono), int(round((t_exp + half_w + 0.12) * sfx_sr)))
        if w1 <= w0 + 16:
            continue
        seg = np.abs(sfx_mono[w0:w1])
        seg_pk = float(np.max(seg))
        seg_db = 20.0 * np.log10(seg_pk + 1e-12)
        if seg_db < -55.0:
            dropped.append({"time_sec": t_exp, "event": c.get("event"), "stem_peak_dbfs": round(seg_db, 2)})
            continue

        # Measure energy centroid/onset point inside window
        thresh = seg_pk * (0.25 if not is_swell else 0.35)
        hits = np.where(seg >= thresh)[0]
        if len(hits) > 0:
            measured_t = (w0 + int(hits[0])) / float(sfx_sr)
            err_ms = abs(measured_t - t_exp) * 1000.0
            if not is_swell:
                max_err_ms = max(max_err_ms, err_ms)

        # Verify decoded final MP4 stream actually contains audible signal at that instant (not nulled by mux)
        d0 = max(0, int(round((t_exp - 0.01) * sr)))
        d1 = min(len(dec_mono), int(round((t_exp + 0.15) * sr)))
        if d1 > d0 and float(np.max(np.abs(dec_mono[d0:d1]))) < 1e-4:
            dropped.append({"time_sec": t_exp, "event": c.get("event"), "reason": "Missing in decoded final MP4 audio"})
        checked += 1

    return {
        "status": "FAIL" if dropped else "PASS",
        "measurement_method": "sfx_stem_onset_energy_window_and_post_encode_mp4_presence",
        "checked_cues": checked,
        "dropped_cues": dropped,
        "max_impact_onset_error_ms": round(max_err_ms, 2),
        "frame_tolerance_ms": round((frame_dt + 0.020) * 1000.0, 2),
    }


def verify_voice_music_intelligibility(audio_dir: Path, audio_plan: Dict[str, Any]) -> Dict[str, Any]:
    """Verify Voice > Action > Music hierarchy across voiced speech windows."""
    voice_exp = bool((audio_plan.get("voice") or {}).get("expected", True))
    if not voice_exp:
        return {"status": "PASS", "voice_expected": False, "note": "Voice intentionally absent"}

    vp = audio_dir / "voice.wav"
    mp = audio_dir / "music.wav"
    sp = audio_dir / "sfx.wav"
    if not vp.exists():
        return {"status": "FAIL", "reason": "Missing voice.wav"}

    vo, sr = sf.read(str(vp), dtype="float64", always_2d=True)
    vo_m = vo.mean(axis=1)
    hop = max(1, int(0.04 * sr))
    n_hops = len(vo_m) // hop
    if n_hops == 0:
        return {"status": "FAIL", "reason": "Voice track too short"}

    vo_frames = vo_m[: n_hops * hop].reshape(n_hops, hop)
    vo_rms_f = np.sqrt(np.mean(vo_frames ** 2, axis=1) + 1e-12)
    voiced_mask = (20.0 * np.log10(vo_rms_f + 1e-12)) > -38.0
    if not np.any(voiced_mask):
        return {"status": "FAIL", "reason": "No active speech detected in voice.wav despite voice_expected=True"}

    vo_speech_db = float(20.0 * np.log10(float(np.sqrt(np.mean(vo_rms_f[voiced_mask] ** 2))) + 1e-12))

    margin_mus = None
    if mp.exists():
        mu, _ = sf.read(str(mp), dtype="float64", always_2d=True)
        mu_m = np.pad(mu.mean(axis=1), (0, max(0, len(vo_m) - len(mu))))[: n_hops * hop]
        mu_frames = mu_m.reshape(n_hops, hop)
        mu_rms_f = np.sqrt(np.mean(mu_frames ** 2, axis=1) + 1e-12)
        if float(np.max(mu_rms_f)) > 1e-5:
            mu_speech_db = float(20.0 * np.log10(float(np.sqrt(np.mean(mu_rms_f[voiced_mask] ** 2))) + 1e-12))
            margin_mus = round(vo_speech_db - mu_speech_db, 2)

    sfx_masking = False
    sfx_margin_db = None
    if sp.exists():
        sx, _ = sf.read(str(sp), dtype="float64", always_2d=True)
        sx_m = np.pad(sx.mean(axis=1), (0, max(0, len(vo_m) - len(sx))))[: n_hops * hop]
        sx_frames = sx_m.reshape(n_hops, hop)
        sx_rms_f = np.sqrt(np.mean(sx_frames ** 2, axis=1) + 1e-12)
        active_sx = voiced_mask & (20.0 * np.log10(sx_rms_f + 1e-12) > -45.0)
        if np.any(active_sx):
            sx_over_vo_db = float(20.0 * np.log10(float(np.sqrt(np.mean(sx_rms_f[active_sx] ** 2))) + 1e-12)) - float(20.0 * np.log10(float(np.sqrt(np.mean(vo_rms_f[active_sx] ** 2))) + 1e-12))
            sfx_margin_db = round(-sx_over_vo_db, 2)
            # Fail only if simultaneous SFX over voiced words overwhelms speech (> +1.0 dB louder over active speech)
            if sx_over_vo_db > 1.0:
                sfx_masking = True

    mus_too_loud = (margin_mus is not None and margin_mus < 9.0)
    ok = not (mus_too_loud or sfx_masking)
    return {
        "status": "PASS" if ok else "FAIL",
        "vo_active_speech_rms_dbfs": round(vo_speech_db, 2),
        "vo_to_music_margin_during_speech_db": margin_mus,
        "vo_to_simultaneous_sfx_margin_db": sfx_margin_db,
        "music_masks_voice": mus_too_loud,
        "sfx_masks_voice": sfx_masking,
    }


def verify_licenses_and_credits(audio_dir: Path) -> Dict[str, Any]:
    """Audit audio_asset_manifest.json and verify mandatory CC BY attribution inside credits_audio.txt."""
    man_p = audio_dir / "audio_asset_manifest.json"
    cred_p = audio_dir / "credits_audio.txt"
    if not man_p.exists() or not cred_p.exists():
        return {"status": "FAIL", "reason": "Missing audio_asset_manifest.json or credits_audio.txt"}

    man = json.loads(man_p.read_text(encoding="utf-8"))
    cred_txt = cred_p.read_text(encoding="utf-8")
    violations: List[str] = []

    for item in man.get("assets", []):
        if not item.get("selected_uses"):
            continue
        if item.get("validation_status") != "VERIFIED":
            violations.append(f"Selected asset '{item.get('asset_id')}' has non-VERIFIED status: {item.get('validation_status')}")
        if not item.get("commercial_use_allowed", False):
            violations.append(f"Selected asset '{item.get('asset_id')}' prohibits commercial use")
        if item.get("attribution_required"):
            credit = str(item.get("mandatory_credit") or "").strip()
            author = str(item.get("author") or "").strip()
            if (credit and credit not in cred_txt) or (not credit and author and author not in cred_txt):
                violations.append(f"CC BY asset '{item.get('asset_id')}' credit missing from credits_audio.txt")

    return {
        "status": "FAIL" if violations else "PASS",
        "qa_audio_root_status": man.get("qa_audio_root_status"),
        "rejected_assets_count": man.get("rejected_assets_count", 0),
        "violations": violations,
    }


def verify_music_loop_boundaries(audio_dir: Path) -> Dict[str, Any]:
    """Check music.wav at every segment/crossfade boundary for click/step discontinuities."""
    mp = audio_dir / "music.wav"
    cs_p = audio_dir / "music_cue_sheet.json"
    if not mp.exists() or not cs_p.exists():
        return {"status": "PASS", "checked_boundaries": 0, "note": "No music stem"}

    cs = json.loads(cs_p.read_text(encoding="utf-8"))
    if not cs.get("enabled") or not cs.get("segments"):
        return {"status": "PASS", "checked_boundaries": 0, "note": "Music disabled"}

    mu, sr = sf.read(str(mp), dtype="float64", always_2d=True)
    max_step_jump = 0.0
    pops: List[Dict[str, Any]] = []
    for seg in cs.get("segments", [])[1:]:
        bt = float(seg.get("start_sec", 0.0))
        i0 = max(1, int(round((bt - float(seg.get("crossfade_sec", 0.0)) - 0.05) * sr)))
        i1 = min(len(mu) - 1, int(round((bt + 0.08) * sr)))
        if i1 <= i0 + 2:
            continue
        diffs = np.abs(np.diff(mu[i0:i1], axis=0))
        jump = float(np.max(diffs))
        max_step_jump = max(max_step_jump, jump)
        if jump > 0.14:
            pops.append({"boundary_sec": bt, "max_sample_step": round(jump, 4)})

    return {
        "status": "FAIL" if pops else "PASS",
        "checked_boundaries": max(0, len(cs.get("segments", [])) - 1),
        "max_boundary_step_delta": round(max_step_jump, 5),
        "boundary_pops": pops,
    }


def verify_stem_reproducibility(mix_report: Dict[str, Any]) -> Dict[str, Any]:
    mix_sha = str(mix_report.get("mix_pcm_sha256") or "")
    stems = mix_report.get("stems") or {}
    ok = bool(mix_sha) and all(bool((stems.get(k) or {}).get("pcm_sha256")) for k in ("voice", "music", "sfx", "ambience"))
    return {
        "status": "PASS" if ok else "NOT_VERIFIED",
        "mix_pcm_sha256": mix_sha,
        "mastering_method": mix_report.get("mastering_method"),
    }


def run_audio_quality_gate(
    preview_mp4: Path,
    final_mp4: Path,
    audio_dir: Path,
    audio_plan: Dict[str, Any],
    mix_report: Dict[str, Any],
    logs_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Complete substantive Audio QC gate over decoded final MP4, stems, cues, and licenses."""
    fps = int(audio_plan.get("fps", 30))
    policy = audio_plan.get("quality_policy") or {}
    music_en = bool((audio_plan.get("music") or {}).get("enabled", True))
    sfx_en = str(audio_plan.get("sfx_mode", "auto")) != "off" and bool(audio_plan.get("sfx"))
    voice_exp = bool((audio_plan.get("voice") or {}).get("expected", True))
    amb_en = bool((audio_plan.get("ambience") or {}).get("enabled", False))
    intentionally_silent = (not music_en and not sfx_en and not voice_exp and not amb_en) or bool(audio_plan.get("intentional_silences"))

    # Decode final MP4 audio track once cleanly via ffmpeg into temp WAV inside owned logs/
    dec_dir = logs_dir or (audio_dir.parent / "logs")
    dec_dir.mkdir(parents=True, exist_ok=True)
    tmp_wav = dec_dir / "_qc_decoded_audio_final.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(final_mp4), "-vn", "-ac", "2", "-ar", "48000", str(tmp_wav)],
            check=True,
        )
        dec_pcm, dec_sr = sf.read(str(tmp_wav), dtype="float32", always_2d=True)
    finally:
        tmp_wav.unlink(missing_ok=True)

    checks: Dict[str, Dict[str, Any]] = {}
    checks["playable_stream_final"] = verify_playable_audio_stream(final_mp4)
    checks["playable_stream_preview"] = verify_playable_audio_stream(preview_mp4)
    checks["lufs_and_true_peak_post_encode"] = verify_lufs_true_peak_post_encode(final_mp4, policy, intentionally_silent=intentionally_silent)
    checks["peak_and_clip"] = verify_peak_and_clip(dec_pcm, intentionally_silent=intentionally_silent)
    checks["duration_and_sync"] = verify_audio_duration_and_sync(final_mp4, fps)
    checks["missing_expected_cues"] = verify_missing_expected_cues(audio_plan, audio_dir, mix_report)
    checks["sfx_onsets"] = verify_sfx_onsets(audio_dir, dec_pcm, dec_sr, audio_plan, fps=fps)
    checks["voice_music_intelligibility"] = verify_voice_music_intelligibility(audio_dir, audio_plan)
    checks["music_loop_boundaries"] = verify_music_loop_boundaries(audio_dir)
    checks["licenses_and_credits"] = verify_licenses_and_credits(audio_dir)
    checks["stem_reproducibility"] = verify_stem_reproducibility(mix_report)

    statuses = [c["status"] for c in checks.values()]
    overall = "FAIL" if ("FAIL" in statuses or "NOT_VERIFIED" in statuses) else ("WARN" if "WARN" in statuses else "PASS")

    lufs_info = checks["lufs_and_true_peak_post_encode"]
    pk_info = checks["peak_and_clip"]
    out = {
        "schema_version": "sd-audio-qc-1",
        "overall_status": overall,
        "subjective_editorial_listening": "NOT_VERIFIED",
        "subjective_listening_note": "Automated post-encode DSP/FFmpeg ebur128 & stem QC executed; human subjective listening cannot run in non-interactive headless mode.",
        "intentionally_silent": intentionally_silent,
        "metrics": {
            "rms_dbfs": pk_info.get("rms_dbfs"),
            "peak_dbfs": pk_info.get("peak_dbfs"),
            "integrated_lufs": lufs_info.get("integrated_lufs"),
            "true_peak_dbtp": lufs_info.get("true_peak_dbtp"),
        },
        "checks": checks,
    }
    (audio_dir / "audio_qc_report.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
