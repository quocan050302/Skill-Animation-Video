"""STEP 5: Pre-Render Style-Lock Gate, Still Inspection & Bounded Parallel Scene Renderer."""

from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .camera_execution import collect_camera_trace_samples, evaluate_camera_trace_accuracy
from .preflight import DiskBudgetGuard, check_disk_quota
from .provenance_guard import ProvenanceGuard, StyleLockViolationError
from .quality_gate import audit_style_lock, inspect_pre_render_stills


def _run_render_node(
    node_bin: str,
    render_mjs: Path,
    args: List[str],
    browser_exe: Optional[str],
    log_path: Path,
) -> Dict[str, Any]:
    env = os.environ.copy()
    if browser_exe:
        env["PLAYWRIGHT_CHROME_PATH"] = browser_exe
    cmd = [node_bin, str(render_mjs), *args]
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"CMD: {' '.join(cmd)}\nEXIT: {res.returncode}\n--- STDOUT ---\n{res.stdout}\n--- STDERR ---\n{res.stderr}\n",
        encoding="utf-8",
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"render_node.mjs failed (exit={res.returncode}): {res.stderr[-800:] or res.stdout[-800:]}"
        )
    lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip().startswith("{")]
    return json.loads(lines[-1]) if lines else {"ok": True}


def render_stills_and_shots(
    project_root: Path,
    run_dir: Path,
    style_decisions: Dict[str, Any],
    storyboard: Dict[str, Any],
    engine_project: Dict[str, Any],
    browser_exe: Optional[str],
    webgl_backend: str = "metal",
    workers: int = 2,
    render_4k_mode: str = "native",  # "native" | "upscale"
    min_free_gb: float = 1.5,
    camera_plan: Optional[Dict[str, Any]] = None,
    transition_edl: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute STEP 5 strictly in order:
    1) Fail-closed style-lock audit
    2) First + busiest + end stills per shot + automated visual inspection
    3) Bounded parallel shot rendering with disk-quota protection & exit status verification
    """
    node_bin = shutil.which("node") or "node"
    render_mjs = (project_root / "director" / "render_node.mjs").resolve()
    logs_dir = run_dir / "logs"
    stills_dir = run_dir / "stills"
    shots_dir = run_dir / "shots"
    tmp_dir = run_dir / "tmp"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stills_dir.mkdir(parents=True, exist_ok=True)
    shots_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fail-closed Pre-Render Style-Lock Audit
    guard = ProvenanceGuard.current()
    guard_snap = guard.snapshot_report() if guard else None
    pre_audit = audit_style_lock(
        style_decisions=style_decisions,
        storyboard=storyboard,
        engine_project=engine_project,
        guard_snapshot=guard_snap,
        stage="pre_render",
    )
    (run_dir / "style_lock_audit.json").write_text(json.dumps(pre_audit, indent=2), encoding="utf-8")
    if pre_audit["status"] != "PASS":
        raise StyleLockViolationError(
            f"Pre-render style-lock audit {pre_audit['status']}: {pre_audit['violations'] or pre_audit['unverified_reasons']}"
        )

    # 2. Check Disk Quota & Adaptive Budget Guard BEFORE rendering
    disk_ok, _, free_gb = check_disk_quota(run_dir, min_free_gb=min_free_gb)
    if not disk_ok:
        raise RuntimeError(f"Aborting render: free disk {free_gb:.2f} GiB < quota {min_free_gb:.2f} GiB")

    can_native_4k = bool(engine_project.get("supports_native_4k", False))
    use_native_4k = (render_4k_mode == "native") and can_native_4k
    fps = int(storyboard["fps"])
    total_dur = float(storyboard.get("total_duration_sec") or 30.0)
    disk_guard = DiskBudgetGuard(run_dir)
    est_bytes = DiskBudgetGuard.estimate_render_bytes(
        duration_sec=total_dur,
        native_4k=use_native_4k,
        workers=workers,
    )
    pre_budget = disk_guard.check(est_bytes)
    if not pre_budget["ok"]:
        raise RuntimeError(
            f"DISK_BUDGET_BLOCKED before stills: free={pre_budget['free_bytes']} < needed={pre_budget['needed_total_bytes']}"
        )

    # Load camera_plan & transition_edl from run_dir if not passed explicitly
    if camera_plan is None and (run_dir / "camera_paths.json").exists():
        camera_plan = json.loads((run_dir / "camera_paths.json").read_text(encoding="utf-8"))
    if transition_edl is None and (run_dir / "transition_edl.json").exists():
        transition_edl = json.loads((run_dir / "transition_edl.json").read_text(encoding="utf-8"))

    # 3. Render Stills (first frame + busiest midpoint + end frame + contact hits + transition midpoints)
    shots = storyboard["shots"]
    still_times: List[float] = []
    for s in shots:
        st, en = float(s["start"]), float(s["end"])
        still_times.extend([
            round(st + 0.04, 3),
            round(0.5 * (st + en), 3),
            round(max(st + 0.08, en - 0.06), 3),
        ])
        ca = (s.get("staging") or {}).get("contact_action")
        if isinstance(ca, dict) and ca.get("hit_time_sec") is not None:
            ht = max(st + 0.02, min(en - 0.02, float(ca["hit_time_sec"])))
            still_times.append(round(ht, 3))
    for tr in (transition_edl or {}).get("transitions", []):
        if str(tr.get("actual_method") or "cut") not in ("cut", "cut_on_action"):
            b = float(tr.get("boundary_sec") or 0.0)
            if 0.02 < b < total_dur - 0.02:
                still_times.append(round(b, 3))
    still_times = sorted(set(still_times))
    times_arg = ",".join(f"{t:.3f}" for t in still_times)

    t0_stills = time.time()
    _run_render_node(
        node_bin=node_bin,
        render_mjs=render_mjs,
        args=["stills", engine_project["entry_html"], str(stills_dir), times_arg, "1", webgl_backend],
        browser_exe=browser_exe,
        log_path=logs_dir / "stills_render.log",
    )
    still_paths = sorted(stills_dir.glob("still_*.png"))
    still_qc = inspect_pre_render_stills(still_paths, style_decisions["selected_skill"])
    (logs_dir / "stills_inspection.json").write_text(json.dumps(still_qc, indent=2), encoding="utf-8")
    if still_qc["status"] != "PASS":
        raise RuntimeError(f"Pre-render visual still inspection FAILED: {still_qc['failures']}")
    stills_elapsed = round(time.time() - t0_stills, 2)

    # 3b. Single-Authority Camera & Transition Telemetry Trace (for ZDF WebGL engine)
    raw_telemetry_path = logs_dir / "raw_render_telemetry.json"
    cam_trace_path = run_dir / "camera_execution_trace.json"
    cam_trace_doc: Optional[Dict[str, Any]] = None
    if style_decisions.get("selected_skill") == "zach-d-films":
        trace_times = set(collect_camera_trace_samples(storyboard, fps=fps))
        ed_tl_p = run_dir / "editorial_timeline.json"
        if ed_tl_p.exists():
            ed_doc = json.loads(ed_tl_p.read_text(encoding="utf-8"))
            for ov in ed_doc.get("overlays", []):
                ov_mid = 0.5 * (float(ov.get("start", 0.0)) + float(ov.get("end", 0.0)))
                if 0.02 < ov_mid < total_dur - 0.02:
                    trace_times.add(round(ov_mid, 4))
        for tr in (transition_edl or {}).get("transitions", []):
            d_tr = float(tr.get("duration_sec") or 0.0)
            if str(tr.get("actual_method") or "cut") not in ("cut", "cut_on_action") and d_tr > 0.0:
                b_tr = float(tr.get("boundary_sec") or 0.0)
                for mul in (-0.36, -0.18, 0.0, 0.18, 0.36):
                    tk = max(0.0, min(total_dur - 0.002, b_tr + mul * d_tr))
                    trace_times.add(round(tk, 4))
        sorted_trace_times = sorted(trace_times)
        trace_res = _run_render_node(
            node_bin=node_bin,
            render_mjs=render_mjs,
            args=[
                "trace",
                engine_project["entry_html"],
                ",".join(f"{t:.4f}" for t in sorted_trace_times),
                "1",
                webgl_backend,
            ],
            browser_exe=browser_exe,
            log_path=logs_dir / "camera_trace.log",
        )
        raw_telemetry_path.write_text(json.dumps(trace_res, indent=2), encoding="utf-8")
        if isinstance(camera_plan, dict):
            cam_trace_doc = evaluate_camera_trace_accuracy(
                storyboard=storyboard,
                camera_plan=camera_plan,
                trace_records=list(trace_res.get("traces") or []),
                transition_edl=transition_edl,
            )
            cam_trace_path.write_text(json.dumps(cam_trace_doc, indent=2), encoding="utf-8")
            if cam_trace_doc["status"] != "PASS":
                raise RuntimeError(
                    f"Camera execution trace FAILED accuracy/collision check: {cam_trace_doc['failures'][:6]}"
                )

        # 3c. Deterministic Semantic Object-ID Matte Extraction (3 samples per shot: start/peak/end)
        matte_times: List[float] = []
        for s in shots:
            st, en = float(s["start"]), float(s["end"])
            dur_s = max(0.2, en - st)
            t0_m = round(min(total_dur - 0.04, st + min(0.10, dur_s * 0.14)), 3)
            tp_m = round(min(total_dur - 0.03, st + dur_s * 0.52), 3)
            t2_m = round(min(total_dur - 0.02, max(tp_m + 0.04, en - min(0.10, dur_s * 0.14))), 3)
            matte_times.extend([t0_m, tp_m, t2_m])
        mattes_dir = run_dir / "qa" / "mattes"
        _run_render_node(
            node_bin=node_bin,
            render_mjs=render_mjs,
            args=[
                "mattes",
                engine_project["entry_html"],
                str(mattes_dir),
                ",".join(f"{t:.3f}" for t in sorted(set(matte_times))),
                "1",
                webgl_backend,
            ],
            browser_exe=browser_exe,
            log_path=logs_dir / "mattes_render.log",
        )

    # 4. Determine Native 4K vs Explicit Upscale
    scale = 2 if use_native_4k else 1
    total_frames = int(round(total_dur * fps))

    # Build contiguous non-overlapping frame ranges per shot so concat has exact total_frames
    shot_jobs: List[Dict[str, Any]] = []
    for i, s in enumerate(shots):
        f0 = 0 if i == 0 else shot_jobs[i - 1]["f_end"]
        f1 = total_frames if i == len(shots) - 1 else max(f0 + 1, int(round(float(s["end"]) * fps)))
        out_clip = shots_dir / f"shot_{i:02d}.mp4"
        shot_jobs.append({
            "index": i,
            "shot_id": s["shot_id"],
            "f_start": f0,
            "f_end": f1,
            "out_mp4": out_clip,
        })

    # 5. Bounded Parallel Scene Render Jobs (await ALL exit statuses!)
    pre_parallel_budget = disk_guard.check(est_bytes)
    if not pre_parallel_budget["ok"]:
        raise RuntimeError(
            f"DISK_BUDGET_BLOCKED before parallel render: free={pre_parallel_budget['free_bytes']} < needed={pre_parallel_budget['needed_total_bytes']}"
        )
    bounded_workers = max(1, min(workers, len(shot_jobs), 4))
    t0_render = time.time()

    def _render_one_job(job: Dict[str, Any]) -> Dict[str, Any]:
        ok_q, _, cur_free = check_disk_quota(run_dir, min_free_gb=min_free_gb * 0.8)
        if not ok_q:
            raise RuntimeError(f"Disk quota breached mid-render ({cur_free:.2f} GiB free)")
        res = _run_render_node(
            node_bin=node_bin,
            render_mjs=render_mjs,
            args=[
                "segment",
                engine_project["entry_html"],
                str(job["out_mp4"]),
                str(fps),
                str(job["f_start"]),
                str(job["f_end"]),
                str(scale),
                engine_project["capture_mode"],
                webgl_backend,
            ],
            browser_exe=browser_exe,
            log_path=logs_dir / f"render_shot_{job['index']:02d}.log",
        )
        if not job["out_mp4"].exists() or job["out_mp4"].stat().st_size == 0:
            raise RuntimeError(f"Shot clip missing after render: {job['out_mp4']}")
        return {
            "shot_id": job["shot_id"],
            "index": job["index"],
            "path": str(job["out_mp4"]),
            "frames": job["f_end"] - job["f_start"],
            "bytes": job["out_mp4"].stat().st_size,
            "renderer_response": res,
        }

    completed_shots: List[Dict[str, Any]] = []
    errors: List[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=bounded_workers) as pool:
        future_map = {pool.submit(_render_one_job, j): j for j in shot_jobs}
        for fut in concurrent.futures.as_completed(future_map):
            job = future_map[fut]
            try:
                completed_shots.append(fut.result())
            except Exception as exc:
                errors.append(f"{job['shot_id']}: {exc}")

    # Clean up ONLY owned run tmp directory (never global caches!)
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if errors or len(completed_shots) != len(shot_jobs):
        raise RuntimeError(f"Scene render job(s) failed: {errors}")

    completed_shots.sort(key=lambda x: x["index"])
    render_elapsed = round(time.time() - t0_render, 2)

    declaration = (
        "native_4k"
        if use_native_4k
        else "upscaled_lanczos_from_1080x1920"
    )

    return {
        "native_4k": use_native_4k,
        "raster_resolution": [2160, 3840] if use_native_4k else [1080, 1920],
        "delivery_4k_declaration": declaration,
        "fps": fps,
        "total_frames": total_frames,
        "workers_used": bounded_workers,
        "webgl_backend": webgl_backend,
        "stills_count": len(still_paths),
        "stills_elapsed_sec": stills_elapsed,
        "render_elapsed_sec": render_elapsed,
        "camera_execution_trace_json": str(cam_trace_path.resolve()) if cam_trace_path.exists() else None,
        "camera_execution_trace_status": cam_trace_doc["status"] if isinstance(cam_trace_doc, dict) else "NOT_APPLICABLE",
        "raw_render_telemetry_json": str(raw_telemetry_path.resolve()) if raw_telemetry_path.exists() else None,
        "disk_budget_pre_render": pre_budget,
        "shots": completed_shots,
    }
