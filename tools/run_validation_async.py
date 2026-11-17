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
import shutil
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
    resource_class: str = "cpu"  # "cpu" (bounded pool) or "gpu" (strictly serialized 1 at a time)


def build_task_graph(mode: str) -> List[ValidationTask]:
    py = sys.executable
    tasks: List[ValidationTask] = [
        ValidationTask(
            task_id="unit_and_negative",
            cmd=[py, "-m", "unittest", "tests.test_unit_and_negative", "-v"],
            deps=[],
            timeout_sec=120.0,
            description="Style-lock negative & routing contracts",
            resource_class="cpu",
        ),
        ValidationTask(
            task_id="visual_event_coverage",
            cmd=[py, "-m", "unittest", "tests.test_visual_event_and_coverage", "-v"],
            deps=[],
            timeout_sec=120.0,
            description="VisualEventGraph, coverage, bounds & fault-injection unit contracts",
            resource_class="cpu",
        ),
        ValidationTask(
            task_id="visual_storytelling_dir",
            cmd=[py, "-m", "unittest", "tests.test_visual_storytelling_director", "-v"],
            deps=["visual_event_coverage"],
            timeout_sec=150.0,
            description="R2.1 story action graph, world-state causality, reveal order & period integrity",
            resource_class="cpu",
        ),
        ValidationTask(
            task_id="storytelling_qa",
            cmd=[py, "-m", "unittest", "tests.test_storytelling_qa", "-v"],
            deps=["visual_storytelling_dir"],
            timeout_sec=150.0,
            description="R2.6 false-pass-proof overlay diff, A/B event alignment & N11-N24 QA traps",
            resource_class="cpu",
        ),
        ValidationTask(
            task_id="audio_determinism",
            cmd=[py, "-m", "unittest", "tests.test_audio_mix_determinism", "-v"],
            deps=[],
            timeout_sec=180.0,
            description="Audio DSP determinism & mastering LUFS/TP checks",
            resource_class="cpu",
        ),
        ValidationTask(
            task_id="zdf_motion01_matrix",
            cmd=[py, "-m", "unittest", "tests.test_zdf_motion01", "-v"],
            deps=["unit_and_negative", "visual_event_coverage"],
            timeout_sec=420.0,
            description="T01-T20 ZDF-MOTION-01 contracts, IK, cutaway, transition & QA tamper traps",
            resource_class="gpu",
        ),
        ValidationTask(
            task_id="audio_catalog_licenses",
            cmd=[py, "-m", "unittest", "tests.test_audio_catalog_and_licenses", "-v"],
            deps=[],
            timeout_sec=120.0,
            description="Audio catalog, license policy & Windows portable traversal guard",
            resource_class="cpu",
        ),
        ValidationTask(
            task_id="voice_prosody",
            cmd=[py, "-m", "unittest", "tests.test_voice_prosody", "-v"],
            deps=[],
            timeout_sec=150.0,
            description="R1/R2.3 semantic voice prosody, candidate eval & traps N1-N3/N15",
            resource_class="cpu",
        ),
        ValidationTask(
            task_id="editorial_overlays",
            cmd=[py, "-m", "unittest", "tests.test_editorial_overlays", "-v"],
            deps=["voice_prosody"],
            timeout_sec=240.0,
            description="R2.4 kinetic captions across mobile widths, 3D tracking, occlusion & N4-N9/N16",
            resource_class="gpu",
        ),
        ValidationTask(
            task_id="boston_molasses_scenes",
            cmd=[py, "-m", "unittest", "tests.test_boston_molasses_scenes", "-v"],
            deps=["visual_storytelling_dir"],
            timeout_sec=240.0,
            description="R2.2 modular 1919 Boston WebGL scenes, rupture/wave dynamics & determinism",
            resource_class="gpu",
        ),
        ValidationTask(
            task_id="retention_audio_sync",
            cmd=[py, "-m", "unittest", "tests.test_retention_audio_sync", "-v"],
            deps=["audio_determinism", "editorial_overlays"],
            timeout_sec=180.0,
            description="R2.5 bespoke SFX sync, isolation & traps N10-N12/N14",
            resource_class="cpu",
        ),
        ValidationTask(
            task_id="editorial_design_system",
            cmd=[py, "-m", "unittest", "tests.test_editorial_design_system", "-v"],
            deps=[],
            timeout_sec=120.0,
            description="SD-RETENTION-03 semantic roles, mobile widths, design tokens & N01-N04/N31",
            resource_class="cpu",
        ),
        ValidationTask(
            task_id="curiosity_director",
            cmd=[py, "-m", "unittest", "tests.test_curiosity_director", "-v"],
            deps=["editorial_design_system"],
            timeout_sec=120.0,
            description="SD-RETENTION-03 <=2 curiosity headlines, pointer planning & N09-N10",
            resource_class="cpu",
        ),
        ValidationTask(
            task_id="cinematic_composition",
            cmd=[py, "-m", "unittest", "tests.test_cinematic_composition", "-v"],
            deps=[],
            timeout_sec=120.0,
            description="SD-RETENTION-03 9:16 negative-space framing, progression & collision QA",
            resource_class="cpu",
        ),
        ValidationTask(
            task_id="physical_motion",
            cmd=[py, "-m", "unittest", "tests.test_physical_motion", "-v"],
            deps=["visual_storytelling_dir"],
            timeout_sec=240.0,
            description="SD-RETENTION-03 deterministic torsion/collapse/viscous waves, seek determinism & N13-N15/N20-N22",
            resource_class="gpu",
        ),
        ValidationTask(
            task_id="character_performance",
            cmd=[py, "-m", "unittest", "tests.test_character_performance", "-v"],
            deps=["visual_storytelling_dir"],
            timeout_sec=240.0,
            description="SD-RETENTION-03 human.js foot-lock grounding, non-slide retreat & N17-N19",
            resource_class="gpu",
        ),
    ]

    if mode in ("focused", "full"):
        tasks.extend([
            ValidationTask(
                task_id="visual_scene_factory_e2e",
                cmd=[py, "-m", "unittest", "tests.test_visual_scene_factory_and_diversity", "-v"],
                deps=["zdf_motion01_matrix"],
                timeout_sec=420.0,
                description="ZDF non-Roman cutaway stills, determinism hashes & E2E pipeline",
                resource_class="gpu",
            ),
            ValidationTask(
                task_id="retention_e2e",
                cmd=[py, "-m", "unittest", "tests.test_retention_e2e", "-v"],
                deps=["editorial_overlays", "retention_audio_sync", "storytelling_qa", "boston_molasses_scenes"],
                timeout_sec=300.0,
                description="3-pane WebGL cutaway, determinism & trap N13",
                resource_class="gpu",
            ),
            ValidationTask(
                task_id="retention03_integration",
                cmd=[py, "-m", "unittest", "tests.test_retention03_integration", "-v"],
                deps=["editorial_design_system", "curiosity_director", "cinematic_composition", "physical_motion", "character_performance", "storytelling_qa"],
                timeout_sec=300.0,
                description="SD-RETENTION-03 Tacoma Narrows WebGL integration, role SFX sync, isolation & N25/N29",
                resource_class="gpu",
            ),
        ])
    if mode == "full":
        tasks.extend([
            ValidationTask(
                task_id="determinism_and_resources",
                cmd=[py, "-m", "unittest", "tests.test_determinism_and_resources", "-v"],
                deps=["unit_and_negative"],
                timeout_sec=240.0,
                description="Seeded TTS/storyboard/resource budget determinism",
                resource_class="cpu",
            ),
            ValidationTask(
                task_id="smoke_all_engines",
                cmd=[py, "-m", "unittest", "tests.test_smoke_all_engines", "-v"],
                deps=["zdf_motion01_matrix"],
                timeout_sec=540.0,
                description="All remaining 5 visual engines smoke + upstream isolation check",
                resource_class="gpu",
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
    cpu_sem: asyncio.Semaphore,
    gpu_sem: asyncio.Semaphore,
    log_dir: Path,
    timeout_override: Optional[float],
) -> Dict[str, object]:
    t_timeout = float(timeout_override or task.timeout_sec)
    log_file = log_dir / f"{task.task_id}.log"
    res_sem = gpu_sem if task.resource_class == "gpu" else cpu_sem
    async with res_sem:
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
    disk_usage = shutil.disk_usage(str(log_dir))
    free_gb = round(disk_usage.free / float(1024 ** 3), 2)
    if free_gb < 1.5:
        raise RuntimeError(f"Insufficient free disk ({free_gb} GiB < 1.5 GiB) before running async validation DAG.")

    tasks = build_task_graph(mode)
    task_map = {t.task_id: t for t in tasks}
    cpu_sem = asyncio.Semaphore(max(1, min(4, workers)))
    gpu_sem = asyncio.Semaphore(1)

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
                in_flight[tid] = asyncio.create_task(_run_one_task(t, cpu_sem, gpu_sem, log_dir, timeout_override))

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
