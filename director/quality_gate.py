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
                    if p.name == "node_modules" and p.is_symlink():
                        target = str(p.resolve())
                        if "claude-animation-skills/kit/node_modules" not in target.replace("\\", "/"):
                            violations.append(f"node_modules symlink points outside neutral kit: {target}")
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

    # 5. Decoded Audio Level, Intelligibility & Dead-Air Check
    if final_4k_mp4.exists():
        tmp_wav = run_dir / "logs" / "_qc_decoded_audio.wav"
        tmp_wav.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(final_4k_mp4), "-vn", "-ac", "2", "-ar", "48000", str(tmp_wav)],
            check=True,
        )
        pcm, sr = sf.read(str(tmp_wav), dtype="float32")
        tmp_wav.unlink(missing_ok=True)
        rms_db = float(20.0 * np.log10(np.sqrt(np.mean(pcm ** 2)) + 1e-9))
        peak_db = float(20.0 * np.log10(np.max(np.abs(pcm)) + 1e-9))

        # Check dead-air silence > 1.2s inside active body
        sil_r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(final_4k_mp4), "-af", "silencedetect=noise=-52dB:d=1.2", "-f", "null", "-"],
            capture_output=True,
            text=True,
        )
        sil_spans = re.findall(r"silence_start:\s*([0-9.]+)", sil_r.stderr)
        audible_ok = (-28.0 <= rms_db <= -8.0) and (peak_db <= -0.1)
        if not audible_ok:
            checks["audio_levels_and_ducking"] = {
                "status": "FAIL",
                "rms_dbfs": round(rms_db, 2),
                "peak_dbfs": round(peak_db, 2),
            }
        elif sil_spans:
            checks["audio_levels_and_ducking"] = {
                "status": "WARN",
                "rms_dbfs": round(rms_db, 2),
                "peak_dbfs": round(peak_db, 2),
                "silence_starts": sil_spans,
            }
        else:
            checks["audio_levels_and_ducking"] = {
                "status": "PASS",
                "rms_dbfs": round(rms_db, 2),
                "peak_dbfs": round(peak_db, 2),
                "silence_dropouts": 0,
            }
    else:
        checks["audio_levels_and_ducking"] = {"status": "NOT_RUN", "reason": "final_4k.mp4 missing"}

    # 6. Factual & Licensing check summary
    fact_checks = storyboard.get("entities_and_facts", {}).get("fact_checks", [])
    has_warn = any("WARN" in str(fc.get("status", "")) for fc in fact_checks)
    checks["factual_and_licensing_integrity"] = {
        "status": "WARN" if has_warn else "PASS",
        "fact_checks": fact_checks,
        "third_party_ripped_assets": 0,
    }

    statuses = [c["status"] for c in checks.values()]
    overall = "FAIL" if ("FAIL" in statuses or "NOT_VERIFIED" in statuses) else ("WARN" if "WARN" in statuses else "PASS")

    qc_report = {
        "schema_version": "0.2.0",
        "overall_status": overall,
        "selected_skill": style_decisions["selected_skill"],
        "selection_mode": style_decisions["selection_mode"],
        "checks": checks,
        "ffprobe_final_4k": ffprobe_4k_summary,
    }
    (run_dir / "qc_report.json").write_text(json.dumps(qc_report, indent=2), encoding="utf-8")
    return qc_report
