#!/usr/bin/env python3
"""Short Director v0.2.0 — Main Orchestrator CLI (STEP 0 through STEP 9).

Usage examples:
  python3 -m director.run --skill stick-figure "Why does a 20-minute power nap sharpen memory while a 60-minute nap makes you groggy?"
  python3 -m director.run "/short-director --skill graph Monthly users grew from 1200 in Jan to 4800 in Mar, 19500 in Jun, and 84000 in Sep"
  python3 -m director.run "Home to the harbour cafe, 3.2 km in 10 minutes"
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .assets import build_locked_engine_workspace
from .build_storyboard import build_storyboard_and_bible
from .edit_timeline import assemble_preview_and_final
from .mix_audio import mix_production_audio
from .parse_script import parse_script_and_build_voice
from .preflight import run_preflight
from .provenance_guard import ProvenanceGuard, StyleLockViolationError
from .quality_gate import run_final_quality_gate
from .route_styles import parse_skill_request, route_and_lock_style


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def execute_short_director_run(
    raw_prompt: str,
    out_dir: Path,
    cli_skill: Optional[str] = None,
    fps: int = 30,
    seed: int = 42,
    lang: str = "en",
    voice_file: Optional[Path] = None,
    workers: Optional[int] = None,
    render_4k_mode: str = "native",
    min_duration: float = 0.0,
) -> Dict[str, Any]:
    """Run STEP 0 -> STEP 9 end-to-end and return the verified `run_manifest`."""
    t_start = time.time()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "logs").mkdir(parents=True, exist_ok=True)

    if fps not in (30, 60):
        raise ValueError(f"Requested fps must be 30 or 60, got {fps}")

    try:
        # STEP 0A: Parse explicit selected skill BEFORE any visual setup!
        pre_mode, pre_skill, _ = parse_skill_request(raw_prompt, cli_skill=cli_skill)

        # STEP 0B: Preflight toolchain, browser, WebGL, voice language coverage & disk quota
        pf = run_preflight(
            project_root=PROJECT_ROOT,
            selected_skill=pre_skill,
            lang=lang,
            user_voice_file=voice_file,
            requested_workers=workers,
        )
        (out_dir / "logs" / "preflight.json").write_text(json.dumps(pf.to_dict(), indent=2), encoding="utf-8")
        if not pf.ok:
            raise RuntimeError(f"Preflight failed: {'; '.join(pf.errors)}")

        # STEP 0C & STEP 2: Engage ProvenanceGuard & lock single skill
        style_decisions, cleaned_script, guard = route_and_lock_style(
            project_root=PROJECT_ROOT,
            raw_input=raw_prompt,
            cli_skill=cli_skill,
            upstream_sha=pf.upstream_sha,
        )
        (out_dir / "style_decisions.json").write_text(json.dumps(style_decisions, ensure_ascii=False, indent=2), encoding="utf-8")
        selected_skill = style_decisions["selected_skill"]

        # STEP 1: Parse script into beats, check facts, synthesize/ingest voice & align word timings
        kit_dir = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"
        parsed_script = parse_script_and_build_voice(
            raw_script=cleaned_script,
            selected_skill=selected_skill,
            run_dir=out_dir,
            kit_dir=kit_dir,
            lang=lang,
            user_voice_file=voice_file,
        )

        # STEP 3: Build per-shot storyboard, multi-angle blocking, art bible & asset inventory
        storyboard = build_storyboard_and_bible(
            parsed_script=parsed_script,
            style_decisions=style_decisions,
            run_dir=out_dir,
            fps=fps,
            seed=seed,
            target_min_duration=min_duration,
        )

        # STEP 4: Generate bespoke single-skill scene assets & pure deterministic update(t) code
        engine_project = build_locked_engine_workspace(
            selected_skill=selected_skill,
            project_root=PROJECT_ROOT,
            run_dir=out_dir,
            storyboard=storyboard,
            parsed_script=parsed_script,
        )

        # STEP 5: Fail-closed pre-render style-lock audit -> stills + visual check -> bounded parallel render
        from .render_scene import render_stills_and_shots
        render_info = render_stills_and_shots(
            project_root=PROJECT_ROOT,
            run_dir=out_dir,
            style_decisions=style_decisions,
            storyboard=storyboard,
            engine_project=engine_project,
            browser_exe=pf.browser_executable,
            webgl_backend=pf.webgl_backend,
            workers=pf.recommended_workers,
            render_4k_mode=render_4k_mode,
        )

        # STEP 6: Synthesize SFX/underscore/ambience, duck music under VO & assemble editorial timeline
        audio_info = mix_production_audio(
            storyboard=storyboard,
            parsed_script=parsed_script,
            run_dir=out_dir,
            seed=seed,
        )
        timeline_info = assemble_preview_and_final(
            run_dir=out_dir,
            storyboard=storyboard,
            parsed_script=parsed_script,
            render_info=render_info,
            audio_info=audio_info,
        )

        # STEP 7: Post-render style-lock audit + ffprobe + decoded frame/cut/4K-truth/audio QC gate
        guard_snapshot = guard.snapshot_report()
        qc_report = run_final_quality_gate(
            run_dir=out_dir,
            style_decisions=style_decisions,
            storyboard=storyboard,
            engine_project=engine_project,
            guard_snapshot=guard_snapshot,
            render_info=render_info,
            preview_mp4=Path(timeline_info["preview_1080_mp4"]),
            final_4k_mp4=Path(timeline_info["final_4k_mp4"]),
        )

        total_elapsed = round(time.time() - t_start, 2)
        delivered = qc_report["overall_status"] in ("PASS", "WARN")

        # STEP 9: Truthful Run Manifest
        manifest: Dict[str, Any] = {
            "schema_version": "0.2.0",
            "delivered": delivered,
            "overall_qc_status": qc_report["overall_status"],
            "selection_mode": style_decisions["selection_mode"],
            "selected_skill": selected_skill,
            "style_lock": style_decisions["style_lock"],
            "origin_skills": [selected_skill],
            "upstream_commit_sha": pf.upstream_sha,
            "upstream_clean_unmodified": pf.upstream_clean,
            "video_contract": {
                "aspect_ratio": "9:16",
                "fps": fps,
                "preview_resolution": [1080, 1920],
                "final_resolution": [2160, 3840],
                "native_4k": render_info["native_4k"],
                "delivery_4k_declaration": render_info["delivery_4k_declaration"],
                "duration_sec": storyboard["total_duration_sec"],
            },
            "artifacts": {
                "storyboard_json": str((out_dir / "storyboard.json").resolve()),
                "style_decisions_json": str((out_dir / "style_decisions.json").resolve()),
                "art_bible_md": str((out_dir / "art_bible.md").resolve()),
                "style_lock_audit_json": str((out_dir / "style_lock_audit.json").resolve()),
                "qc_report_json": str((out_dir / "qc_report.json").resolve()),
                "preview_1080_mp4": timeline_info["preview_1080_mp4"] if delivered else None,
                "final_4k_mp4": timeline_info["final_4k_mp4"] if delivered else None,
                "contact_sheet_jpg": timeline_info["contact_sheet_jpg"],
                "captions_srt": timeline_info["captions_srt"],
            },
            "timing_and_resources": {
                "total_elapsed_sec": total_elapsed,
                "stills_elapsed_sec": render_info["stills_elapsed_sec"],
                "scene_render_elapsed_sec": render_info["render_elapsed_sec"],
                "workers_used": render_info["workers_used"],
                "webgl_backend": pf.webgl_backend,
                "disk_free_gb_at_start": pf.disk_free_gb,
            },
        }
        (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        if not delivered:
            raise RuntimeError(f"Final QC gate FAILED (see {out_dir / 'qc_report.json'})")

        return manifest
    finally:
        ProvenanceGuard.deactivate()


def main(argv: Optional[ list[str] ] = None) -> int:
    parser = argparse.ArgumentParser(description="Short Director v0.2.0 — Strict Single-Skill Vertical Shorts Director")
    parser.add_argument("prompt", help="Script or topic prompt (supports inline `--skill <name>` or `Skill: <name>`)")
    parser.add_argument("--skill", default=None, help="Explicitly lock one of the 6 skills")
    parser.add_argument("--out-dir", default=None, help="Output directory for this run")
    parser.add_argument("--fps", type=int, default=30, choices=[30, 60], help="Output frame rate (30 or 60)")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic RNG seed")
    parser.add_argument("--lang", default="en", help="Language code (e.g. en, vi)")
    parser.add_argument("--voice-file", default=None, help="Optional path to user voiceover audio")
    parser.add_argument("--workers", type=int, default=None, help="Bounded parallel render workers")
    parser.add_argument("--render-4k-mode", default="native", choices=["native", "upscale"], help="Native 4K vs Lanczos upscale")
    parser.add_argument("--min-duration", type=float, default=0.0, help="Minimum short duration in seconds")
    args = parser.parse_args(argv)

    ts_slug = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else (PROJECT_ROOT / "runs" / f"run_{ts_slug}")
    voice_p = Path(args.voice_file).resolve() if args.voice_file else None

    try:
        manifest = execute_short_director_run(
            raw_prompt=args.prompt,
            out_dir=out_dir,
            cli_skill=args.skill,
            fps=args.fps,
            seed=args.seed,
            lang=args.lang,
            voice_file=voice_p,
            workers=args.workers,
            render_4k_mode=args.render_4k_mode,
            min_duration=args.min_duration,
        )
        print(json.dumps(manifest, indent=2))
        return 0
    except StyleLockViolationError as exc:
        print(f"[STYLE LOCK VIOLATION] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[SHORT DIRECTOR ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
