#!/usr/bin/env python3
"""DAG-ordered bounded-parallel async test & validation runner for ZDF-MOTION-01.

Uses asyncio.create_subprocess_exec, Semaphore worker caps, wait_for timeouts,
explicit child process termination on cancellation/timeout, and structured JSON/text logs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ValidationTask:
    task_id: str
    cmd: List[str]
    deps: List[str] = field(default_factory=list)
    timeout_sec: float = 300.0
    description: str = ""


def build_task_graph(mode: str) -> List[ValidationTask]:
    py = sys.executable
    tasks: List[ValidationTask] = [
        ValidationTask(
            task_id="unit_and_negative",
            cmd=[py, "-m", "unittest", "tests.test_unit_and_negative", "-v"],
            deps=[],
            timeout_sec=120.0,
            description="Style-lock negative & routing contracts",
        ),
        ValidationTask(
            task_id="visual_event_coverage",
            cmd=[py, "-m", "unittest", "tests.test_visual_event_and_coverage", "-v"],
            deps=[],
            timeout_sec=120.0,
            description="VisualEventGraph, coverage, bounds & fault-injection unit contracts",
        ),
        ValidationTask(
            task_id="audio_determinism",
            cmd=[py, "-m", "unittest", "tests.test_audio_mix_determinism", "-v"],
            deps=[],
            timeout_sec=180.0,
            description="Audio DSP determinism & mastering LUFS/TP checks",
        ),
        ValidationTask(
            task_id="zdf_motion01_matrix",
            cmd=[py, "-m", "unittest", "tests.test_zdf_motion01", "-v"],
            deps=["unit_and_negative", "visual_event_coverage"],
            timeout_sec=420.0,
            description="T01-T20 ZDF-MOTION-01 contracts, IK, cutaway, transition & QA tamper traps",
        ),
    ]

    if mode in ("focused", "full"):
        tasks.append(
            ValidationTask(
                task_id="visual_scene_factory_e2e",
                cmd=[py, "-m", "unittest", "tests.test_visual_scene_factory_and_diversity", "-v"],
                deps=["zdf_motion01_matrix"],
                timeout_sec=420.0,
                description="ZDF non-Roman cutaway stills, determinism hashes & E2E pipeline",
            )
        )
    if mode == "full":
        tasks.extend([
            ValidationTask(
                task_id="determinism_and_resources",
                cmd=[py, "-m", "unittest", "tests.test_determinism_and_resources", "-v"],
                deps=["unit_and_negative"],
                timeout_sec=240.0,
                description="Seeded TTS/storyboard/resource budget determinism",
            ),
            ValidationTask(
                task_id="smoke_all_engines",
                cmd=[py, "-m", "unittest", "tests.test_smoke_all_engines", "-v"],
                deps=["zdf_motion01_matrix"],
                timeout_sec=540.0,
                description="All remaining 5 visual engines smoke + upstream isolation check",
            ),
        ])
    return tasks


async def _terminate_proc(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=3.0)
    except Exception:
        try:
            proc.kill()
            await proc.wait()
        except Exception:
            pass


async def _run_one_task(
    task: ValidationTask,
    sem: asyncio.Semaphore,
    log_dir: Path,
    timeout_override: Optional[float],
) -> Dict[str, object]:
    t_timeout = float(timeout_override or task.timeout_sec)
    log_file = log_dir / f"{task.task_id}.log"
    async with sem:
        t0 = time.monotonic()
        proc: Optional[asyncio.subprocess.Process] = None
        status = "FAIL"
        exit_code = -1
        timed_out = False
        stdout_text = ""
        stderr_text = ""
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            proc = await asyncio.create_subprocess_exec(
                *task.cmd,
                cwd=str(REPO_ROOT),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            try:
                out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=t_timeout)
                exit_code = int(proc.returncode if proc.returncode is not None else -1)
                stdout_text = out_b.decode("utf-8", errors="replace")
                stderr_text = err_b.decode("utf-8", errors="replace")
                status = "PASS" if exit_code == 0 else "FAIL"
            except asyncio.TimeoutError:
                timed_out = True
                await _terminate_proc(proc)
                status = "TIMEOUT"
        except asyncio.CancelledError:
            if proc is not None:
                await _terminate_proc(proc)
            raise
        except Exception as exc:
            stderr_text += f"\nRunner exception: {exc}"
            if proc is not None:
                await _terminate_proc(proc)
            status = "ERROR"

        elapsed = round(time.monotonic() - t0, 2)
        log_file.write_text(
            f"TASK: {task.task_id}\nCMD: {' '.join(task.cmd)}\nSTATUS: {status} (exit={exit_code}, elapsed={elapsed}s)\n"
            f"\n--- STDOUT ---\n{stdout_text}\n--- STDERR ---\n{stderr_text}\n",
            encoding="utf-8",
        )
        print(f"[{status:7s}] {task.task_id:<26s} ({elapsed:6.2f}s) -> {log_file.name}", flush=True)
        return {
            "task_id": task.task_id,
            "description": task.description,
            "cmd": task.cmd,
            "deps": task.deps,
            "status": status,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "elapsed_sec": elapsed,
            "log_path": str(log_file.resolve()),
        }


async def run_dag(mode: str, workers: int, log_dir: Path, timeout_override: Optional[float]) -> Dict[str, object]:
    log_dir.mkdir(parents=True, exist_ok=True)
    tasks = build_task_graph(mode)
    task_map = {t.task_id: t for t in tasks}
    sem = asyncio.Semaphore(max(1, min(4, workers)))

    results: Dict[str, Dict[str, object]] = {}
    pending = set(task_map.keys())
    in_flight: Dict[str, asyncio.Task[Dict[str, object]]] = {}
    t_all = time.monotonic()

    while pending or in_flight:
        ready = [
            tid for tid in sorted(pending)
            if all(dep in results for dep in task_map[tid].deps)
        ]
        for tid in ready:
            pending.remove(tid)
            t = task_map[tid]
            blocked_deps = [d for d in t.deps if results[d]["status"] != "PASS"]
            if blocked_deps:
                results[tid] = {
                    "task_id": tid,
                    "description": t.description,
                    "cmd": t.cmd,
                    "deps": t.deps,
                    "status": "SKIPPED_DEP_FAILED",
                    "blocked_by": blocked_deps,
                    "exit_code": None,
                    "elapsed_sec": 0.0,
                    "log_path": None,
                }
                print(f"[SKIP   ] {tid:<26s} blocked by {blocked_deps}", flush=True)
            else:
                in_flight[tid] = asyncio.create_task(_run_one_task(t, sem, log_dir, timeout_override))

        if not in_flight:
            if pending:
                # Cycle or unresolved dependency safety fail-closed
                for tid in sorted(pending):
                    results[tid] = {
                        "task_id": tid,
                        "status": "ERROR_UNRESOLVED_DEP",
                        "deps": task_map[tid].deps,
                    }
                break
            continue

        done, _ = await asyncio.wait(in_flight.values(), return_when=asyncio.FIRST_COMPLETED)
        for fut in done:
            res = await fut
            tid = str(res["task_id"])
            in_flight.pop(tid, None)
            results[tid] = res

    ordered = [results[t.task_id] for t in tasks if t.task_id in results]
    all_pass = all(r["status"] == "PASS" for r in ordered)
    summary = {
        "schema_version": "sd-async-validation-1",
        "mode": mode,
        "workers": max(1, min(4, workers)),
        "overall_status": "PASS" if all_pass else "FAIL",
        "total_elapsed_sec": round(time.monotonic() - t_all, 2),
        "tasks": ordered,
    }
    (log_dir / "validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded-parallel DAG validation runner for Short Director ZDF-MOTION-01")
    parser.add_argument("--mode", default="focused", choices=["fast", "focused", "full"])
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--log-dir", default="docs/implementation_runs/ZDF-MOTION-01_20261117_0131Z/logs")
    parser.add_argument("--timeout-sec", type=float, default=None)
    args = parser.parse_args(argv)

    summary = asyncio.run(
        run_dag(
            mode=args.mode,
            workers=args.workers,
            log_dir=Path(args.log_dir).resolve(),
            timeout_override=args.timeout_sec,
        )
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "tasks"}, indent=2))
    return 0 if summary["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
