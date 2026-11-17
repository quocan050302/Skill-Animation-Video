#!/usr/bin/env python3
"""Short Director v0.3.0 — Main Orchestrator CLI (STEP 0 through STEP 9 + Music & SFX Director).

Usage examples:
  python3 -m director.run --skill stick-figure "Why does a 20-minute power nap sharpen memory while a 60-minute nap makes you groggy?"
  python3 -m director.run --skill zach-d-films --music-mode auto --sfx-density detailed "..."
  python3 -m director.run --audio-only --out-dir runs/my_short --music-gain-db -4.0
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .assets import build_locked_engine_workspace
from .audio_narrative import build_audio_narrative_plan
from .build_storyboard import build_storyboard_and_bible
from .edit_timeline import assemble_preview_and_final, remix_existing_video_audio
from .mix_audio import mix_production_audio
from .parse_script import parse_script_and_build_voice
from .preflight import preflight_audio_assets, resolve_qa_audio_root, run_preflight
from .provenance_guard import ProvenanceGuard, StyleLockViolationError
from .quality_gate import run_audio_quality_gate, run_final_quality_gate
from .route_styles import parse_skill_request, route_and_lock_style
from .voice_prosody import render_voice_ab_probe


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _build_manifest_audio_fields(
    audio_info: Dict[str, Any],
    audio_plan: Dict[str, Any],
    aqc_report: Dict[str, Any],
    music_mode: str,
    sfx_mode: str,
) -> Dict[str, Any]:
    audio_dir = Path(audio_info["audio_asset_manifest_json_path"]).parent
    asset_manifest = json.loads(Path(audio_info["audio_asset_manifest_json_path"]).read_text(encoding="utf-8"))
    asset_hashes = {
        a["asset_id"]: a["sha256"]
        for a in asset_manifest.get("assets", [])
        if a.get("selected_uses") and a.get("sha256")
    }
    stem_hashes = {
        k: v.get("pcm_sha256")
        for k, v in (audio_info.get("stems") or {}).items()
        if isinstance(v, dict) and v.get("pcm_sha256")
    }

    reasons: List[str] = []
    for cname, cres in (aqc_report.get("checks") or {}).items():
        if cres.get("status") in ("WARN", "FAIL"):
            reasons.append(f"{cname}:{cres.get('status')}({cres.get('reason') or cres.get('problems') or cres.get('violations') or ''})")

    aqc_checks = aqc_report.get("checks") or {}
    lic_status = (aqc_checks.get("licenses_and_credits") or {}).get("status", "NOT_VERIFIED")
    metrics = aqc_report.get("metrics") or {}

    return {
        "audio_engine_version": __version__,
        "audio_source_mode": {"music": music_mode, "sfx": sfx_mode},
        "qa_audio_root_available": asset_manifest.get("qa_audio_root_status") == "QA_LIBRARY_MOUNTED_READONLY",
        "qa_audio_root_status": asset_manifest.get("qa_audio_root_status"),
        "music_cues_count": int(audio_info.get("music_segments_count", 0)),
        "sfx_cues_expected_count": len(audio_plan.get("sfx", [])),
        "sfx_cues_rendered_count": int(audio_info.get("sfx_cue_count", 0)),
        "rejected_assets_count": int(asset_manifest.get("rejected_assets_count", 0)),
        "license_audit_status": lic_status,
        "manual_edits_preserved": bool(audio_plan.get("manual_edits_preserved", False)),
        "audio_hash": audio_info.get("mix_pcm_sha256"),
        "stem_hashes": stem_hashes,
        "asset_hashes": asset_hashes,
        "final_post_encode_integrated_lufs": metrics.get("integrated_lufs"),
        "final_post_encode_true_peak_dbtp": metrics.get("true_peak_dbtp"),
        "audio_qc_status": aqc_report.get("overall_status"),
        "audio_qc_reasons": reasons,
        "subjective_editorial_listening": aqc_report.get("subjective_editorial_listening", "NOT_VERIFIED"),
    }


def execute_audio_only_remix(
    out_dir: Path,
    cli_skill: Optional[str] = None,
    seed: int = 42,
    qa_audio_root: Optional[Path] = None,
    music_mode: str = "auto",
    sfx_mode: str = "auto",
    sfx_density: str = "balanced",
    music_file: Optional[Path] = None,
    music_rights_confirmed: bool = False,
    music_gain_db: float = 0.0,
    sfx_gain_db: float = 0.0,
    music_intensity: Optional[str] = None,
    audio_plan_in: Optional[Path] = None,
    voice_mode: str = "auto",
    force_audio_replan: bool = False,
    preserve_original_files: bool = False,
) -> Dict[str, Any]:
    """Remix/re-master audio onto verified existing picture WITHOUT re-rendering video frames."""
    t_start = time.time()
    out_dir = out_dir.resolve()
    sb_path = out_dir / "storyboard.json"
    sd_path = out_dir / "style_decisions.json"
    if not sb_path.exists() or not sd_path.exists():
        raise RuntimeError(f"--audio-only requires existing storyboard.json and style_decisions.json in {out_dir}")

    storyboard = json.loads(sb_path.read_text(encoding="utf-8"))
    style_decisions = json.loads(sd_path.read_text(encoding="utf-8"))
    locked_skill = style_decisions["selected_skill"]
    if cli_skill and cli_skill != locked_skill:
        raise StyleLockViolationError(
            f"--audio-only cannot switch visual skill from existing '{locked_skill}' to '{cli_skill}'"
        )

    qa_root_res, qa_status, _ = resolve_qa_audio_root(PROJECT_ROOT, qa_audio_root)
    pf_audio = preflight_audio_assets(
        project_root=PROJECT_ROOT,
        qa_audio_root=qa_root_res,
        qa_status=qa_status,
        music_mode=music_mode,
        sfx_mode=sfx_mode,
        music_file=music_file,
        music_rights_confirmed=music_rights_confirmed,
        disk_free_gb=5.0,
    )
    if not pf_audio["ok"]:
        raise RuntimeError(f"Audio preflight failed: {'; '.join(pf_audio['errors'])}")

    words_path = out_dir / "audio" / "words.json"
    lines_path = out_dir / "audio" / "lines.json"
    vo_wav = out_dir / "audio" / "vo.wav"
    words = json.loads(words_path.read_text(encoding="utf-8")) if words_path.exists() else []
    lines = json.loads(lines_path.read_text(encoding="utf-8")) if lines_path.exists() else []
    parsed_stub: Dict[str, Any] = {
        "entities_and_facts": storyboard.get("entities_and_facts", {}),
        "beats": lines,
        "voice": {
            "vo_wav_path": str(vo_wav) if vo_wav.exists() else None,
            "words": words,
        },
    }

    existing_plan: Optional[Dict[str, Any]] = None
    if audio_plan_in is not None:
        existing_plan = json.loads(audio_plan_in.read_text(encoding="utf-8"))
    elif not force_audio_replan and (out_dir / "audio" / "audio_plan.json").exists():
        existing_plan = json.loads((out_dir / "audio" / "audio_plan.json").read_text(encoding="utf-8"))

    voice_expected = (voice_mode != "off") and bool(vo_wav.exists())
    audio_plan = build_audio_narrative_plan(
        parsed_script=parsed_stub,
        storyboard=storyboard,
        run_dir=out_dir,
        music_mode=music_mode,
        sfx_mode=sfx_mode,
        sfx_density=sfx_density,
        music_intensity=music_intensity,
        voice_expected=voice_expected,
        existing_plan=existing_plan,
        music_gain_db=music_gain_db,
        sfx_gain_db=sfx_gain_db,
    )

    audio_info = mix_production_audio(
        storyboard=storyboard,
        parsed_script=parsed_stub,
        run_dir=out_dir,
        seed=seed,
        audio_plan=audio_plan,
        catalog=pf_audio["catalog"],
        qa_audio_root=qa_root_res,
        music_mode=music_mode,
        sfx_mode=sfx_mode,
        sfx_density=sfx_density,
        music_file=music_file,
        music_rights_confirmed=music_rights_confirmed,
        music_gain_db=music_gain_db,
        sfx_gain_db=sfx_gain_db,
        music_intensity=music_intensity,
        voice_expected=voice_expected,
        existing_plan=existing_plan,
    )

    def _verify_remux_candidate(cand_prev: Path, cand_4k: Path) -> tuple[bool, str]:
        aqc_cand = run_audio_quality_gate(
            preview_mp4=cand_prev,
            final_mp4=cand_4k,
            audio_dir=out_dir / "audio",
            audio_plan=audio_plan,
            mix_report=audio_info,
            logs_dir=out_dir / "logs",
        )
        ok_status = aqc_cand["overall_status"] in ("PASS", "WARN")
        return ok_status, "" if ok_status else json.dumps(aqc_cand["checks"])

    remix_info = remix_existing_video_audio(
        run_dir=out_dir,
        storyboard=storyboard,
        audio_info=audio_info,
        preserve_original_files=preserve_original_files,
        verify_candidate_fn=_verify_remux_candidate,
    )

    aqc_final = json.loads((out_dir / "audio" / "audio_qc_report.json").read_text(encoding="utf-8"))
    manifest_p = out_dir / "run_manifest.json"
    prior_manifest = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.exists() else {}
    audio_manifest_fields = _build_manifest_audio_fields(audio_info, audio_plan, aqc_final, music_mode, sfx_mode)
    prior_manifest.update({
        "schema_version": __version__,
        "audio_only_remix": True,
        "video_packets_unchanged": True,
        "video_packet_md5_4k": remix_info["video_packet_md5_4k"],
        "video_packet_md5_preview": remix_info["video_packet_md5_preview"],
        **audio_manifest_fields,
        "audio": audio_manifest_fields,
        "remix_elapsed_sec": round(time.time() - t_start, 2),
    })
    prior_manifest.setdefault("artifacts", {}).update({
        "preview_1080_mp4": remix_info["preview_1080_mp4"],
        "final_4k_mp4": remix_info["final_4k_mp4"],
        "audio_plan_json": audio_info["audio_plan_json_path"],
        "music_cue_sheet_json": audio_info["music_cue_sheet_json_path"],
        "sfx_cue_sheet_json": audio_info["sfx_cue_sheet_json_path"],
        "audio_asset_manifest_json": audio_info["audio_asset_manifest_json_path"],
        "audio_mix_report_json": str((out_dir / "audio" / "audio_mix_report.json").resolve()),
        "audio_qc_report_json": str((out_dir / "audio" / "audio_qc_report.json").resolve()),
        "credits_audio_txt": audio_info["credits_audio_txt_path"],
    })
    manifest_p.write_text(json.dumps(prior_manifest, indent=2), encoding="utf-8")
    return prior_manifest


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
    qa_audio_root: Optional[Path] = None,
    music_mode: str = "auto",
    sfx_mode: str = "auto",
    sfx_density: str = "balanced",
    music_file: Optional[Path] = None,
    music_rights_confirmed: bool = False,
    music_gain_db: float = 0.0,
    sfx_gain_db: float = 0.0,
    music_intensity: Optional[str] = None,
    audio_plan_in: Optional[Path] = None,
    audio_only: bool = False,
    voice_mode: str = "auto",
    force_audio_replan: bool = False,
    prepare_qa_audio_library: bool = False,
    preserve_original_on_remix: bool = False,
    edit_energy: str = "balanced",
    scene_novelty: str = "standard",
    transition_policy: str = "motivated",
    max_static_hold_sec: Optional[float] = None,
    visual_plan_in: Optional[Path] = None,
    voice_style: Optional[str] = None,
    voice_backend: str = "auto",
    voice_id: Optional[str] = None,
    voice_prosody_in: Optional[Path] = None,
    voice_pause_strength: float = 1.0,
    voice_compare_ab: bool = False,
    caption_mode: str = "kinetic",
    callout_mode: str = "smart",
    editorial_theme: str = "role-aware",
    curiosity_layer: str = "auto",
    verified_numbers: Optional[List[Dict[str, Any]]] = None,
    historical_claims: Optional[Dict[str, Any]] = None,
    factual_sources_note: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run STEP 0 -> STEP 9 end-to-end (or --audio-only lossless remix) and return `run_manifest`."""
    if audio_only:
        return execute_audio_only_remix(
            out_dir=out_dir,
            cli_skill=cli_skill,
            seed=seed,
            qa_audio_root=qa_audio_root,
            music_mode=music_mode,
            sfx_mode=sfx_mode,
            sfx_density=sfx_density,
            music_file=music_file,
            music_rights_confirmed=music_rights_confirmed,
            music_gain_db=music_gain_db,
            sfx_gain_db=sfx_gain_db,
            music_intensity=music_intensity,
            audio_plan_in=audio_plan_in,
            voice_mode=voice_mode,
            force_audio_replan=force_audio_replan,
            preserve_original_files=preserve_original_on_remix,
        )

    t_start = time.time()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "logs").mkdir(parents=True, exist_ok=True)

    if fps not in (30, 60):
        raise ValueError(f"Requested fps must be 30 or 60, got {fps}")

    try:
        # STEP 0A: Parse explicit selected skill BEFORE any visual or audio setup!
        pre_mode, pre_skill, _ = parse_skill_request(raw_prompt, cli_skill=cli_skill)

        # STEP 0B: Preflight toolchain, browser, WebGL, voice language, disk quota & QA root resolution
        pf = run_preflight(
            project_root=PROJECT_ROOT,
            selected_skill=pre_skill,
            lang=lang,
            user_voice_file=voice_file,
            requested_workers=workers,
            qa_audio_root=qa_audio_root,
            voice_mode=voice_mode,
            voice_backend=voice_backend,
        )
        (out_dir / "logs" / "preflight.json").write_text(json.dumps(pf.to_dict(), indent=2), encoding="utf-8")
        if not pf.ok:
            raise RuntimeError(f"Preflight failed: {'; '.join(pf.errors)}")

        # Early audio preflight (fails closed BEFORE expensive 4K visual render if QA library / rights missing!)
        qa_root_path = Path(pf.qa_audio_root) if pf.qa_audio_root else None
        pf_audio = preflight_audio_assets(
            project_root=PROJECT_ROOT,
            qa_audio_root=qa_root_path,
            qa_status=pf.qa_audio_status,
            music_mode=music_mode,
            sfx_mode=sfx_mode,
            music_file=music_file,
            music_rights_confirmed=music_rights_confirmed,
            disk_free_gb=pf.disk_free_gb,
            prepare_qa_audio_library=prepare_qa_audio_library,
        )
        (out_dir / "logs" / "audio_preflight.json").write_text(
            json.dumps({k: v for k, v in pf_audio.items() if k != "catalog"}, indent=2),
            encoding="utf-8",
        )
        if not pf_audio["ok"]:
            raise RuntimeError(f"Audio preflight failed: {'; '.join(pf_audio['errors'])}")

        # STEP 0C & STEP 2: Engage ProvenanceGuard & lock single visual skill
        style_decisions, cleaned_script, guard = route_and_lock_style(
            project_root=PROJECT_ROOT,
            raw_input=raw_prompt,
            cli_skill=cli_skill,
            upstream_sha=pf.upstream_sha,
        )
        (out_dir / "style_decisions.json").write_text(json.dumps(style_decisions, ensure_ascii=False, indent=2), encoding="utf-8")
        selected_skill = style_decisions["selected_skill"]

        if historical_claims is not None:
            (out_dir / "historical_claims.json").write_text(
                json.dumps(historical_claims, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if factual_sources_note is not None and factual_sources_note.exists():
            import shutil as _shutil_notes
            _shutil_notes.copy2(factual_sources_note, out_dir / "factual_sources_note.md")

        # STEP 1: Parse script into beats, check facts, synthesize/ingest expressive voice & align word timings
        kit_dir = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"
        parsed_script = parse_script_and_build_voice(
            raw_script=cleaned_script,
            selected_skill=selected_skill,
            run_dir=out_dir,
            kit_dir=kit_dir,
            lang=lang,
            user_voice_file=voice_file,
            voice_mode=voice_mode,
            voice_style=voice_style,
            voice_backend=voice_backend,
            voice_id=voice_id,
            voice_prosody_in=voice_prosody_in,
            voice_pause_strength=voice_pause_strength,
        )
        voice_ab_info: Optional[Dict[str, Any]] = None
        if voice_compare_ab and voice_mode != "off" and voice_file is None:
            import shutil as _shutil
            probe_dir = out_dir / "_tmp_voice_ab_a"
            try:
                probe_a = parse_script_and_build_voice(
                    raw_script=cleaned_script,
                    selected_skill=selected_skill,
                    run_dir=probe_dir,
                    kit_dir=kit_dir,
                    lang=lang,
                    voice_mode=voice_mode,
                    voice_style="legacy",
                    voice_backend=voice_backend,
                    voice_id=voice_id,
                )
                voice_ab_info = render_voice_ab_probe(
                    legacy_wav=Path(probe_a["voice"]["vo_wav_path"]),
                    enhanced_wav=Path(parsed_script["voice"]["vo_wav_path"]),
                    out_wav=out_dir / "ab_comparison" / "voice_ab_probe.wav",
                    report_a=probe_a["voice"]["voice_delivery_report"],
                    report_b=parsed_script["voice"]["voice_delivery_report"],
                )
                (out_dir / "ab_comparison" / "voice_ab_metrics.json").write_text(
                    json.dumps(voice_ab_info, indent=2), encoding="utf-8"
                )
            finally:
                _shutil.rmtree(probe_dir, ignore_errors=True)

        # STEP 3: Build semantic visual event graph, novel shot coverage, camera paths, transitions & entity inventory
        existing_visual_plan: Optional[Dict[str, Any]] = None
        if visual_plan_in is not None:
            existing_visual_plan = json.loads(visual_plan_in.read_text(encoding="utf-8"))
            if existing_visual_plan.get("selected_skill") and existing_visual_plan.get("selected_skill") != selected_skill:
                raise StyleLockViolationError(
                    f"--visual-plan-in visual skill {existing_visual_plan.get('selected_skill')!r} != locked {selected_skill!r}"
                )

        storyboard = build_storyboard_and_bible(
            parsed_script=parsed_script,
            style_decisions=style_decisions,
            run_dir=out_dir,
            fps=fps,
            seed=seed,
            target_min_duration=min_duration,
            edit_energy=edit_energy,
            scene_novelty=scene_novelty,
            transition_policy=transition_policy,
            max_static_hold_sec=max_static_hold_sec,
            existing_visual_plan=existing_visual_plan,
            caption_mode=caption_mode,
            callout_mode=callout_mode,
            verified_numbers=verified_numbers,
            historical_claims=historical_claims,
            editorial_theme=editorial_theme,
            curiosity_layer=curiosity_layer,
        )

        # NEW STEP 3.5: Plan Narrative Music Score & Grounded SFX BEFORE 4K visual render
        existing_plan: Optional[Dict[str, Any]] = None
        if audio_plan_in is not None:
            existing_plan = json.loads(audio_plan_in.read_text(encoding="utf-8"))
        elif not force_audio_replan and (out_dir / "audio" / "audio_plan.json").exists():
            existing_plan = json.loads((out_dir / "audio" / "audio_plan.json").read_text(encoding="utf-8"))

        voice_expected = (voice_mode != "off")
        audio_plan = build_audio_narrative_plan(
            parsed_script=parsed_script,
            storyboard=storyboard,
            run_dir=out_dir,
            music_mode=music_mode,
            sfx_mode=sfx_mode,
            sfx_density=sfx_density,
            music_intensity=music_intensity,
            voice_expected=voice_expected,
            existing_plan=existing_plan,
            music_gain_db=music_gain_db,
            sfx_gain_db=sfx_gain_db,
        )

        # STEP 4: Generate bespoke single-skill visual scene assets & pure deterministic update(t) code
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

        # STEP 6: Resolve licensed/procedural audio beds & SFX, mix stems & ducking, assemble timeline
        audio_info = mix_production_audio(
            storyboard=storyboard,
            parsed_script=parsed_script,
            run_dir=out_dir,
            seed=seed,
            audio_plan=audio_plan,
            catalog=pf_audio["catalog"],
            qa_audio_root=qa_root_path,
            music_mode=music_mode,
            sfx_mode=sfx_mode,
            sfx_density=sfx_density,
            music_file=music_file,
            music_rights_confirmed=music_rights_confirmed,
            music_gain_db=music_gain_db,
            sfx_gain_db=sfx_gain_db,
            music_intensity=music_intensity,
            voice_expected=voice_expected,
            existing_plan=existing_plan,
        )
        timeline_info = assemble_preview_and_final(
            run_dir=out_dir,
            storyboard=storyboard,
            parsed_script=parsed_script,
            render_info=render_info,
            audio_info=audio_info,
        )

        # STEP 7: Post-render style-lock audit + ffprobe + decoded frame/cut/4K-truth + deep Audio QC gate
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
            max_static_hold_sec=max_static_hold_sec,
            historical_claims=historical_claims,
        )
        aqc_report = json.loads((out_dir / "audio" / "audio_qc_report.json").read_text(encoding="utf-8"))

        total_elapsed = round(time.time() - t_start, 2)
        delivered = qc_report["overall_status"] in ("PASS", "WARN")
        audio_manifest_fields = _build_manifest_audio_fields(audio_info, audio_plan, aqc_report, music_mode, sfx_mode)

        # STEP 9: Truthful Run Manifest
        ed_fin_chk = (qc_report.get("checks", {}).get("editorial_retention_finish") or {})
        manifest: Dict[str, Any] = {
            "schema_version": __version__,
            "delivered": delivered,
            "overall_qc_status": qc_report["overall_status"],
            "release_status": qc_report.get("release_status", "TECHNICAL_ACCEPTANCE_PASS" if delivered else "FAIL"),
            "subjective_visual_review": qc_report.get("subjective_visual_review", "NOT_VERIFIED"),
            "subjective_editorial_listening": aqc_report.get("subjective_editorial_listening", "NOT_VERIFIED"),
            "subjective_voice_quality_status": qc_report.get("subjective_voice_quality_status", "NOT_VERIFIED"),
            "viewer_retention_status": qc_report.get("viewer_retention_status", "NOT_VERIFIED"),
            "selection_mode": style_decisions["selection_mode"],
            "selected_skill": selected_skill,
            "style_lock": style_decisions["style_lock"],
            "origin_skills": [selected_skill],
            "upstream_commit_sha": pf.upstream_sha,
            "upstream_clean_unmodified": pf.upstream_clean,
            **audio_manifest_fields,
            "editorial_finish": {
                "voice_style": parsed_script.get("voice", {}).get("voice_style"),
                "word_anchor_confidence": parsed_script.get("voice", {}).get("word_anchor_confidence", "ESTIMATED"),
                "caption_mode": storyboard.get("caption_mode", caption_mode),
                "callout_mode": storyboard.get("callout_mode", callout_mode),
                "editorial_theme": storyboard.get("editorial_theme", editorial_theme),
                "curiosity_layer": storyboard.get("curiosity_layer", curiosity_layer),
                "editorial_roles_used": (storyboard.get("editorial_timeline_summary") or {}).get("editorial_roles_used", []),
                "editorial_finish_status": ed_fin_chk.get("status"),
                "checks_summary": ed_fin_chk.get("checks_summary", {}),
                "voice_ab_probe": voice_ab_info,
            },
            "scene_diversity": {
                "edit_energy": storyboard.get("edit_energy", edit_energy),
                "scene_novelty": scene_novelty,
                "transition_policy": transition_policy,
                "max_static_hold_sec": max_static_hold_sec,
                "shot_count": len(storyboard.get("shots", [])),
                "diversity_summary": storyboard.get("diversity_summary", {}),
                "scene_diversity_status": (qc_report.get("checks", {}).get("scene_diversity_and_retention") or {}).get("status"),
                "camera_execution_status": (qc_report.get("checks", {}).get("camera_execution") or {}).get("status"),
                "subjective_visual_review": (qc_report.get("checks", {}).get("scene_diversity_and_retention") or {}).get("subjective_visual_review", "NOT_VERIFIED"),
            },
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
                "story_action_graph_json": str((out_dir / "story_action_graph.json").resolve()) if (out_dir / "story_action_graph.json").exists() else None,
                "visual_storytelling_qa_report_json": str((out_dir / "visual_storytelling_qa_report.json").resolve()) if (out_dir / "visual_storytelling_qa_report.json").exists() else None,
                "visual_events_json": str((out_dir / "visual_events.json").resolve()),
                "shot_coverage_json": str((out_dir / "shot_coverage.json").resolve()),
                "camera_paths_json": str((out_dir / "camera_paths.json").resolve()),
                "camera_execution_trace_json": render_info.get("camera_execution_trace_json"),
                "raw_render_telemetry_json": render_info.get("raw_render_telemetry_json"),
                "transition_edl_json": str((out_dir / "transition_edl.json").resolve()),
                "scene_diversity_report_json": str((out_dir / "scene_diversity_report.json").resolve()),
                "visual_qc_timeline_json": (qc_report.get("checks", {}).get("scene_diversity_and_retention") or {}).get("visual_qc_timeline_json"),
                "style_decisions_json": str((out_dir / "style_decisions.json").resolve()),
                "art_bible_md": str((out_dir / "art_bible.md").resolve()),
                "style_lock_audit_json": str((out_dir / "style_lock_audit.json").resolve()),
                "qc_report_json": str((out_dir / "qc_report.json").resolve()),
                "preview_1080_mp4": timeline_info["preview_1080_mp4"] if delivered else None,
                "final_4k_mp4": timeline_info["final_4k_mp4"] if delivered else None,
                "contact_sheet_jpg": timeline_info["contact_sheet_jpg"],
                "captions_srt": timeline_info["captions_srt"],
                "audio_plan_json": audio_info["audio_plan_json_path"],
                "audio_director_notes_md": str((out_dir / "audio" / "audio_director_notes.md").resolve()),
                "music_cue_sheet_json": audio_info["music_cue_sheet_json_path"],
                "sfx_cue_sheet_json": audio_info["sfx_cue_sheet_json_path"],
                "audio_asset_manifest_json": audio_info["audio_asset_manifest_json_path"],
                "audio_mix_report_json": str((out_dir / "audio" / "audio_mix_report.json").resolve()),
                "audio_qc_report_json": str((out_dir / "audio" / "audio_qc_report.json").resolve()),
                "credits_audio_txt": audio_info["credits_audio_txt_path"],
                "voice_prosody_plan_json": (parsed_script.get("voice", {}).get("prosody_artifacts") or {}).get("voice_prosody_plan_json"),
                "voice_delivery_report_json": (parsed_script.get("voice", {}).get("prosody_artifacts") or {}).get("voice_delivery_report_json"),
                "prosody_script_md": (parsed_script.get("voice", {}).get("prosody_artifacts") or {}).get("prosody_script_md"),
                "editorial_timeline_json": str((out_dir / "editorial_timeline.json").resolve()) if (out_dir / "editorial_timeline.json").exists() else None,
                "overlay_plan_json": str((out_dir / "overlay_plan.json").resolve()) if (out_dir / "overlay_plan.json").exists() else None,
                "overlay_coverage_json": str((out_dir / "overlay_coverage.json").resolve()) if (out_dir / "overlay_coverage.json").exists() else None,
                "editorial_qa_report_json": ed_fin_chk.get("editorial_qa_report"),
                "editorial_attention_timeline_json": ed_fin_chk.get("editorial_attention_timeline_json"),
                "editorial_design_tokens_json": str((out_dir / "editorial_design_tokens.json").resolve()) if (out_dir / "editorial_design_tokens.json").exists() else None,
                "editorial_roles_plan_json": str((out_dir / "editorial_roles_plan.json").resolve()) if (out_dir / "editorial_roles_plan.json").exists() else None,
                "composition_report_json": str((out_dir / "composition_report.json").resolve()) if (out_dir / "composition_report.json").exists() else None,
                "pointer_tracking_json": str((out_dir / "pointer_tracking.json").resolve()) if (out_dir / "pointer_tracking.json").exists() else None,
                "character_performance_telemetry_json": str((out_dir / "character_performance_telemetry.json").resolve()) if (out_dir / "character_performance_telemetry.json").exists() else None,
                "world_state_telemetry_json": str((out_dir / "world_state_telemetry.json").resolve()) if (out_dir / "world_state_telemetry.json").exists() else None,
                "stems": {
                    "voice_wav": audio_info["voice_wav_path"],
                    "music_wav": audio_info["music_wav_path"],
                    "sfx_wav": audio_info["sfx_wav_path"],
                    "ambience_wav": audio_info["ambience_wav_path"],
                    "master_pre_wav": audio_info["master_pre_wav_path"],
                    "mix_wav": audio_info["mix_wav_path"],
                },
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


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Short Director v0.4.0 — Strict Single-Skill Continuous Visual & Audio Shorts Director")
    parser.add_argument("prompt", nargs="?", default="", help="Script or topic prompt (optional when --audio-only)")
    parser.add_argument("--skill", default=None, help="Explicitly lock one of the 6 visual skills")
    parser.add_argument("--out-dir", default=None, help="Output directory for this run")
    parser.add_argument("--fps", type=int, default=30, choices=[30, 60], help="Output frame rate (30 or 60)")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic RNG seed")
    parser.add_argument("--lang", default="en", help="Language code (e.g. en, vi)")
    parser.add_argument("--voice-file", default=None, help="Optional path to user voiceover audio")
    parser.add_argument("--voice-mode", default="auto", choices=["auto", "off"], help="Voiceover synthesis mode")
    parser.add_argument("--workers", type=int, default=None, help="Bounded parallel render workers")
    parser.add_argument("--render-4k-mode", default="native", choices=["native", "upscale"], help="Native 4K vs Lanczos upscale")
    parser.add_argument("--min-duration", type=float, default=0.0, help="Minimum short duration in seconds")

    # Continuous Shot & Visual Direction options (`SD-VISUAL-01`)
    parser.add_argument("--edit-energy", default="balanced", choices=["calm", "balanced", "dynamic"], help="Pacing & visual beat frequency")
    parser.add_argument("--scene-novelty", default="standard", choices=["standard", "high"], help="Anti-repetition novelty penalty weight")
    parser.add_argument("--transition-policy", default="motivated", choices=["motivated", "simple"], help="Transition direction mode")
    parser.add_argument("--max-static-hold-sec", type=float, default=None, help="Maximum duration before forcing beat update or split")
    parser.add_argument("--visual-plan-in", default=None, help="Optional path to manual shot_coverage/storyboard JSON to respect locked shots")

    # Audio Director options (all optional, preserve backward compatibility)
    parser.add_argument("--qa-audio-root", default=None, help="Optional read-only path to QA-Unified-Video-Studio audio library")
    parser.add_argument("--music-mode", default="auto", choices=["auto", "procedural", "qa-library", "file", "off"], help="Music source selection")
    parser.add_argument("--sfx-mode", default="auto", choices=["auto", "procedural", "qa-library", "off"], help="SFX source selection")
    parser.add_argument("--sfx-density", default="balanced", choices=["sparse", "balanced", "detailed"], help="Grounded SFX cue density")
    parser.add_argument("--music-file", default=None, help="Custom music WAV path when --music-mode file")
    parser.add_argument("--music-rights-confirmed", action="store_true", help="Explicit confirmation of usage rights for --music-file")
    parser.add_argument("--music-gain-db", type=float, default=0.0, help="Music gain offset in dB")
    parser.add_argument("--sfx-gain-db", type=float, default=0.0, help="SFX gain offset in dB")
    parser.add_argument("--music-intensity", default=None, choices=["calm", "medium", "high"], help="Override score intensity")
    parser.add_argument("--audio-plan-in", default=None, help="Path to existing audio_plan.json to preserve/reuse")
    parser.add_argument("--audio-only", action="store_true", help="Remix audio losslessly onto verified existing visuals without re-rendering")
    parser.add_argument("--force-audio-replan", action="store_true", help="Re-generate audio plan ignoring unpinned prior plan")
    parser.add_argument("--prepare-qa-audio-library", action="store_true", help="Explicit opt-in acknowledgement for optional QA audio preparation")
    parser.add_argument("--preserve-original-on-remix", action="store_true", help="Write *_remixed.mp4 leaving source MP4 files intact")

    # Expressive Editorial Options (`SD-RETENTION-01`)
    parser.add_argument("--voice-style", default=None, choices=["legacy", "natural", "cinematic"], help="Semantic voice prosody mode")
    parser.add_argument("--voice-backend", default="auto", choices=["auto", "kokoro", "windows_sapi", "macos_say"], help="Local voice synthesis backend")
    parser.add_argument("--voice-id", default=None, help="Explicit local voice ID (e.g., 'Microsoft Zira Desktop')")
    parser.add_argument("--voice-prosody-in", default=None, help="Optional JSON path overriding planned phrase prosody")
    parser.add_argument("--voice-pause-strength", type=float, default=1.0, help="Multiplier for inter-phrase pause breaks (0.35..2.0)")
    parser.add_argument("--voice-compare-ab", action="store_true", help="Also generate legacy A vs active B voice comparison WAV probe")
    parser.add_argument("--caption-mode", default="kinetic", choices=["plain", "kinetic", "phrase"], help="On-screen caption rendering mode")
    parser.add_argument("--callout-mode", default="smart", choices=["off", "smart"], help="3D world-tracked smart editorial overlays in ZDF")
    parser.add_argument("--editorial-theme", default="role-aware", choices=["role-aware", "legacy"], help="Multi-theme editorial styling engine (ZDF only)")
    parser.add_argument("--curiosity-layer", default="auto", choices=["auto", "off"], help="Curiosity hero headlines and smart impact pointers (ZDF only)")
    parser.add_argument("--verified-numbers-json", default=None, help="Optional JSON list of curated verified numeric facts for counters")
    parser.add_argument("--historical-claims-json", default=None, help="Optional JSON path containing verified historical claims & uncertainty metadata")
    parser.add_argument("--factual-sources-note", default=None, help="Optional Markdown file listing factual sources for traceability")

    args = parser.parse_args(argv)
    if not args.audio_only and not str(args.prompt).strip():
        parser.error("prompt is required unless --audio-only is passed")

    ts_slug = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else (PROJECT_ROOT / "runs" / f"run_{ts_slug}")
    voice_p = Path(args.voice_file).resolve() if args.voice_file else None
    qa_p = Path(args.qa_audio_root).resolve() if args.qa_audio_root else None
    mus_p = Path(args.music_file).resolve() if args.music_file else None
    plan_in_p = Path(args.audio_plan_in).resolve() if args.audio_plan_in else None
    vis_in_p = Path(args.visual_plan_in).resolve() if args.visual_plan_in else None
    vpros_p = Path(args.voice_prosody_in).resolve() if args.voice_prosody_in else None
    vnums = json.loads(Path(args.verified_numbers_json).read_text(encoding="utf-8")) if args.verified_numbers_json else None
    hclaims = json.loads(Path(args.historical_claims_json).read_text(encoding="utf-8")) if args.historical_claims_json else None
    fsources_p = Path(args.factual_sources_note).resolve() if args.factual_sources_note else None

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
            qa_audio_root=qa_p,
            music_mode=args.music_mode,
            sfx_mode=args.sfx_mode,
            sfx_density=args.sfx_density,
            music_file=mus_p,
            music_rights_confirmed=args.music_rights_confirmed,
            music_gain_db=args.music_gain_db,
            sfx_gain_db=args.sfx_gain_db,
            music_intensity=args.music_intensity,
            audio_plan_in=plan_in_p,
            audio_only=args.audio_only,
            voice_mode=args.voice_mode,
            force_audio_replan=args.force_audio_replan,
            prepare_qa_audio_library=args.prepare_qa_audio_library,
            preserve_original_on_remix=args.preserve_original_on_remix,
            edit_energy=args.edit_energy,
            scene_novelty=args.scene_novelty,
            transition_policy=args.transition_policy,
            max_static_hold_sec=args.max_static_hold_sec,
            visual_plan_in=vis_in_p,
            voice_style=args.voice_style,
            voice_backend=args.voice_backend,
            voice_id=args.voice_id,
            voice_prosody_in=vpros_p,
            voice_pause_strength=args.voice_pause_strength,
            voice_compare_ab=args.voice_compare_ab,
            caption_mode=args.caption_mode,
            callout_mode=args.callout_mode,
            editorial_theme=args.editorial_theme,
            curiosity_layer=args.curiosity_layer,
            verified_numbers=vnums,
            historical_claims=hclaims,
            factual_sources_note=fsources_p,
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
