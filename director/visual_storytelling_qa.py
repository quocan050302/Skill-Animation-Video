"""STEP 7C (R2.6): Event-Driven Visual Storytelling, Reveal Order, Period Integrity & Claims QA.

Audits decoded renders, WebGL/DOM telemetry (`raw_render_telemetry.json`), captions,
historical claims, and A/B alignment without false passes:
- `audit_story_action_coverage`: requires distinct locations & physical actions (no setup rename tricks)
- `audit_reveal_order_decoded`: verifies rendered traces/overlays never spoil reveals before spoken word
- `audit_spatiotemporal_variety`: catches pseudo-novelty across decoded frame pairs
- `audit_world_state_causality`: verifies cause -> effect action chronology & telemetry evolution
- `audit_period_integrity`: blocks modern anachronisms in pre-1940 historical scenes
- `audit_motion_dynamics`: verifies non-frozen subjects/cameras across shot durations
- `audit_caption_layout`: catches DOM word collisions / overflow (`getBoundingClientRect`)
- `audit_historical_claims`: verifies surfaced numbers match sources with uncertainty qualifiers
- `build_ab_alignment`: aligns A vs B timelines by `narrative_event_id` / `beat_id`
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .character_performance import validate_character_grounding
from .physical_motion import plan_physics_telemetry
from .visual_storytelling_director import (
    score_story_diversity,
    validate_narrative_causality,
    validate_reveal_order,
)


SCHEMA_VERSION = "sd-visual-storytelling-qa-1"


def audit_story_action_coverage(
    action_graph: Dict[str, Any],
    storyboard: Dict[str, Any],
    raw_traces: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    shots = list(storyboard.get("shots") or [])
    div = score_story_diversity(shots, action_graph)
    issues = list(div.get("problems") or [])

    period_year = action_graph.get("period_year")
    is_historical = period_year is not None or any(
        str(s.get("scene_family") or "").startswith(("boston_", "tacoma_")) for s in shots
    )
    if is_historical and len(shots) >= 6:
        if div["distinct_locations_count"] < 4:
            issues.append(
                f"Historical story uses only {div['distinct_locations_count']} distinct locations (< 4)"
            )
        has_cutaway = any("cutaway" in str(s.get("procedural_generator") or "").lower() or "cutaway" in str(s.get("setup_type") or "").lower() for s in shots)
        if not has_cutaway:
            issues.append("Historical story missing dedicated structural/engineering cutaway stage")

    if raw_traces:
        trace_actions = {
            str(((tr.get("telemetry") or {}).get("narrative_action") or {}).get("physical_action") or "")
            for tr in raw_traces
        } - {""}
        if trace_actions and len(shots) >= 6 and len(trace_actions) < 4:
            issues.append(
                f"Decoded runtime telemetry recorded only {len(trace_actions)} distinct physical_actions (< 4)"
            )

    return {
        "status": "FAIL" if issues else "PASS",
        "distinct_actions_count": div["distinct_actions_count"],
        "distinct_locations_count": div["distinct_locations_count"],
        "max_unchanged_asset_run": div["max_unchanged_asset_run"],
        "max_unchanged_state_sec": div["max_unchanged_state_sec"],
        "issues": issues,
    }


def audit_reveal_order_decoded(
    action_graph: Dict[str, Any],
    editorial_timeline: Dict[str, Any],
    raw_traces: Optional[List[Dict[str, Any]]] = None,
    words: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    plan_res = validate_reveal_order(action_graph, editorial_timeline, words=words)
    issues = list(plan_res.get("violations") or [])
    token_gates = dict(plan_res.get("token_gates") or {})

    if raw_traces and token_gates:
        ov_lookup = {str(o.get("overlay_id")): o for o in (editorial_timeline.get("overlays") or [])}
        for rec in raw_traces:
            rt = float(rec.get("time", 0.0))
            ov_tel = (((rec.get("telemetry") or {}).get("overlay") or {}).get("overlays")) or []
            for item in ov_tel:
                if not item.get("visible"):
                    continue
                oid = str(item.get("overlay_id") or "")
                meta = ov_lookup.get(oid, {})
                lbl = f"{item.get('label', '')} {meta.get('label', '')} {meta.get('sublabel', '')}".lower()
                for tok, min_t in token_gates.items():
                    matched = (tok in lbl) if len(tok) >= 4 else bool(re.search(rf"(?<![0-9.]){re.escape(tok)}(?![0-9])", lbl))
                    if matched and rt + 0.08 < float(min_t):
                        issues.append(
                            f"Rendered frame at t={rt:.2f}s displays '{tok}' in {oid} before spoken cue at t={min_t:.2f}s"
                        )
                        break

    return {
        "status": "FAIL" if issues else "PASS",
        "token_gates": token_gates,
        "issues": issues,
    }


def audit_spatiotemporal_variety(
    storyboard: Dict[str, Any],
    scene_diversity_report: Optional[Dict[str, Any]],
    action_graph: Dict[str, Any],
) -> Dict[str, Any]:
    shots = list(storyboard.get("shots") or [])
    issues: List[str] = []

    adj_pairs = list((scene_diversity_report or {}).get("adjacent_perceptual_pairs") or [])
    for idx, pair in enumerate(adj_pairs):
        sa = shots[idx] if idx < len(shots) else {}
        sb = shots[idx + 1] if idx + 1 < len(shots) else {}
        ssim = float(pair.get("ssim_masked", 0.0))
        mad = float(pair.get("roi_mad", 99.0))
        if sa.get("setup_type") != sb.get("setup_type") and ssim > 0.965 and mad < 0.9:
            issues.append(
                f"Pseudo-variety detected between {sa.get('shot_id')} ({sa.get('setup_type')}) and "
                f"{sb.get('shot_id')} ({sb.get('setup_type')}): decoded SSIM={ssim:.4f}, roi_mad={mad:.2f}"
            )

    div = score_story_diversity(shots, action_graph)
    if div["status"] == "FAIL":
        issues.extend(div["problems"])

    return {
        "status": "FAIL" if issues else "PASS",
        "checked_adjacent_pairs": len(adj_pairs),
        "issues": issues,
    }


def audit_world_state_causality(
    action_graph: Dict[str, Any],
    storyboard: Dict[str, Any],
    raw_traces: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    base_chk = validate_narrative_causality(action_graph, storyboard)
    issues = list(base_chk.get("violations") or [])

    if raw_traces:
        # Check physical action progression inside traces for rupture & wave flow shots
        rupture_vals = [
            float(((((rec.get("telemetry") or {}).get("narrative_action") or {}).get("structural_state") or {}).get("ruptureProgress")) or 0.0)
            for rec in raw_traces
            if str(((rec.get("telemetry") or {}).get("narrative_action") or {}).get("physical_action") or "") == "tank_panel_rupture"
        ]
        if len(rupture_vals) >= 2 and (max(rupture_vals) - min(rupture_vals)) < 0.15:
            issues.append(f"Rupture shot telemetry showed negligible deformation progression ({min(rupture_vals)} -> {max(rupture_vals)})")

        wave_vals = [
            float(((rec.get("telemetry") or {}).get("narrative_action") or {}).get("fluid_front_pos"))
            for rec in raw_traces
            if ((rec.get("telemetry") or {}).get("narrative_action") or {}).get("fluid_front_pos") is not None
        ]
        if len(wave_vals) >= 2 and (max(wave_vals) - min(wave_vals)) < 0.20:
            issues.append(f"Wave flow telemetry showed near-static fluid front ({min(wave_vals)} -> {max(wave_vals)})")

    return {
        "status": "FAIL" if issues else "PASS",
        "period_year": base_chk.get("period_year"),
        "issues": issues,
    }


def audit_period_integrity(
    storyboard: Dict[str, Any],
    action_graph: Dict[str, Any],
    audio_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    period_year = action_graph.get("period_year")
    shots = list(storyboard.get("shots") or [])
    issues: List[str] = []

    if period_year is not None and int(period_year) <= 1940:
        for sh in shots:
            gen = str(sh.get("procedural_generator") or "")
            props = [str(p).lower() for p in (sh.get("staging") or {}).get("grounded_props", [])]
            if gen in (
                "zach3d:human_device_stage",
                "zach3d:device_cutaway_stage",
                "zach3d:datacenter_aisle_stage",
                "zach3d:network_relay_stage",
                "zach3d:roman_historical_stage",
            ):
                issues.append(f"Period anachronism in {sh.get('shot_id')}: generator '{gen}' invalid for {period_year}")
            for bad_prop in ("phone_screen", "cell_tower_wave", "datacenter_rack", "roman_arena"):
                if bad_prop in props:
                    issues.append(f"Period anachronism prop '{bad_prop}' in {sh.get('shot_id')} ({period_year})")

        if audio_plan:
            amb_gen = str(((audio_plan.get("ambience") or {}).get("generator_name")) or "")
            if amb_gen == "arena_wind_ambience":
                issues.append("Historical 1919 urban run used Roman 'arena_wind_ambience' instead of period street ambience")

    return {
        "status": "FAIL" if issues else "PASS",
        "period_year": period_year,
        "issues": issues,
    }


def audit_motion_dynamics(
    storyboard: Dict[str, Any],
    scene_diversity_report: Optional[Dict[str, Any]] = None,
    raw_traces: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    shots = list(storyboard.get("shots") or [])
    samples = list((scene_diversity_report or {}).get("perceptual_samples") or [])
    sample_by_id = {str(x.get("shot_id")): x for x in samples}
    issues: List[str] = []

    for sh in shots:
        sid = str(sh.get("shot_id") or "")
        dur = float(sh.get("duration") or 0.0)
        is_hold = bool((sh.get("staging") or {}).get("intentional_hold", False))
        smp = sample_by_id.get(sid)
        if smp and dur >= 1.2 and not is_hold:
            mad_roi = float(smp.get("intra_mad_roi", 0.0))
            if mad_roi < 0.22:
                issues.append(f"Shot {sid} appears visually static in central ROI (intra_mad_roi={mad_roi:.3f} < 0.22)")

    if raw_traces and len(shots) >= 1:
        by_shot: Dict[str, List[Dict[str, Any]]] = {}
        for rec in raw_traces:
            by_shot.setdefault(str(rec.get("shot_id") or ""), []).append(rec)
        for sh in shots:
            sid = str(sh.get("shot_id") or "")
            is_hold = bool((sh.get("staging") or {}).get("intentional_hold", False))
            recs = by_shot.get(sid, [])
            if len(recs) >= 2 and not is_hold:
                poses = [
                    ((r.get("telemetry") or {}).get("camera") or {}).get("world_pos")
                    for r in recs
                ]
                poses = [p for p in poses if isinstance(p, list) and len(p) == 3]
                if len(poses) >= 2:
                    p0, p1 = poses[0], poses[-1]
                    disp = ((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2 + (p1[2] - p0[2]) ** 2) ** 0.5
                    if disp < 0.06 and float(sh.get("duration") or 0.0) >= 1.2:
                        issues.append(f"Shot {sid} camera barely moved in WebGL telemetry (disp={disp:.3f}m)")

    return {
        "status": "FAIL" if issues else "PASS",
        "checked_shots": len(shots),
        "issues": issues,
    }


def audit_physical_and_character_telemetry(
    storyboard: Dict[str, Any],
    raw_traces: Optional[List[Dict[str, Any]]] = None,
    run_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Verify decoded physical deformation telemetry (N13-N15, N21) & foot-grounded character motion (N17-N19)."""
    shots = list(storyboard.get("shots") or [])
    shots_by_id = {str(s.get("shot_id")): s for s in shots}
    issues: List[str] = []

    traces = list(raw_traces or [])
    phys_summary = plan_physics_telemetry(traces) if traces else {
        "max_vertex_disp_m": 0.0,
        "max_deck_roll_span_rad": 0.0,
        "collapse_onset_observed_sec": None,
        "cables_attached_all": True,
        "nan_detected": False,
    }
    if phys_summary["nan_detected"]:
        issues.append("N21: Non-finite NaN/Inf physical_motion value detected in telemetry")
    if not phys_summary["cables_attached_all"]:
        issues.append("N22: Bridge suspender cables disconnected (dist <= 0 or non-finite)")

    by_shot_phys: Dict[str, List[Dict[str, Any]]] = {}
    char_samples: List[Dict[str, Any]] = []
    torsion_seen_t: Optional[float] = None

    for rec in traces:
        tel = rec.get("telemetry") or {}
        sid = str(rec.get("shot_id") or tel.get("shot_id") or "")
        t_rec = float(rec.get("time_sec", rec.get("time", 0.0)))
        ph = tel.get("physical_motion")
        if isinstance(ph, dict):
            by_shot_phys.setdefault(sid, []).append(ph)
            if float(ph.get("deck_roll_span_rad") or 0.0) >= 0.05 and torsion_seen_t is None:
                torsion_seen_t = t_rec
            if ph.get("collapse_active") and ("collapse" not in str(shots_by_id.get(sid, {}).get("procedural_generator") or "")):
                issues.append(f"N15: Unexpected collapse_active inside non-collapse shot {sid} at t={t_rec:.2f}s")
        cp = tel.get("character_performance")
        if isinstance(cp, dict):
            char_samples.append({"time_sec": t_rec, "shot_id": sid, **cp})

    for sid, recs in by_shot_phys.items():
        sh = shots_by_id.get(sid, {})
        gen = str(sh.get("procedural_generator") or "").lower()
        act = str(sh.get("physical_action") or "").lower()
        dur = float(sh.get("duration") or 0.0)
        is_aftermath = ("aftermath" in gen) or ("aftermath" in act)
        needs_deform = (not is_aftermath) and any(k in gen or k in act for k in ("wave", "torsion", "twist", "collapse"))
        if needs_deform and dur >= 1.2:
            vmax = max(float(r.get("vertex_disp_max_m") or 0.0) for r in recs)
            if vmax < 0.03:
                issues.append(f"N13/N14: Claimed deforming stage '{gen}' ({sid}) had negligible displacement {vmax:.4f}m")

    if phys_summary["collapse_onset_observed_sec"] is not None and torsion_seen_t is not None:
        if phys_summary["collapse_onset_observed_sec"] < torsion_seen_t:
            issues.append(
                f"N15: Observed collapse onset ({phys_summary['collapse_onset_observed_sec']:.2f}s) before torsion buildup ({torsion_seen_t:.2f}s)"
            )

    char_audit = validate_character_grounding(char_samples, require_motion=bool(char_samples))
    if char_audit["status"] == "FAIL":
        issues.extend(char_audit["issues"])

    out_world = {
        "schema_version": "sd-world-state-telemetry-1",
        "status": "FAIL" if issues else "PASS",
        "physics_summary": phys_summary,
        "shot_physics_counts": {k: len(v) for k, v in by_shot_phys.items()},
        "issues": issues,
    }
    if run_dir is not None:
        (run_dir / "world_state_telemetry.json").write_text(json.dumps(out_world, indent=2), encoding="utf-8")
        char_doc = {
            "schema_version": "sd-char-perf-telemetry-1",
            **char_audit,
            "samples": char_samples[:120],
        }
        (run_dir / "character_performance_telemetry.json").write_text(json.dumps(char_doc, indent=2), encoding="utf-8")

    return {
        "status": "FAIL" if issues else "PASS",
        "physics_summary": phys_summary,
        "character_grounding": char_audit,
        "issues": issues,
    }


def audit_pointer_tracking(
    raw_traces: Optional[List[Dict[str, Any]]],
    editorial_timeline: Dict[str, Any],
    max_tip_error_px: float = 36.0,
    run_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Audit rendered pointer tip accuracy, settled coverage, and semantic feature intersection.

    Fail-closed rules (R2.1 / R2.5):
    - When `callout_mode != 'off'` and `editorial_timeline` schedules pointer overlays,
      `checked_settled_tips == 0` MUST NEVER return PASS.
    - Pointer tip must meet `<= max_tip_error_px` AND reference a valid causal semantic anchor
      (not generic `stage_center` / wrong feature ID).
    """
    ov_mode = str(editorial_timeline.get("callout_mode", "off"))
    planned_overlays = list(editorial_timeline.get("overlays") or [])
    ov_plan_by_id = {str(o.get("overlay_id")): o for o in planned_overlays if o.get("overlay_id")}
    planned_pointers = [
        o for o in planned_overlays
        if str(o.get("pointer_shape") or "").lower() not in ("none", "")
        or (not o.get("pointer_shape") and o.get("type") in ("focus_ring", "tracked_arrow"))
    ]

    issues: List[str] = []
    worst_err_px = 0.0
    checked_tips = 0
    rows: List[Dict[str, Any]] = []
    justified_skips: List[Dict[str, Any]] = []

    if ov_mode != "off" and raw_traces:
        for rec in raw_traces:
            rt = float(rec.get("time_sec", rec.get("time", 0.0)))
            ov_list = (((rec.get("telemetry") or {}).get("overlay") or {}).get("overlays")) or []
            for item in ov_list:
                oid = str(item.get("overlay_id") or "")
                plan_ov = ov_plan_by_id.get(oid, {})
                if not item.get("visible"):
                    hr = str(item.get("hidden_reason") or "")
                    if hr in ("occluded_3d_geometry", "offscreen", "behind_or_missing_anchor"):
                        justified_skips.append({"time_sec": round(rt, 3), "overlay_id": oid, "reason": hr})
                    continue

                err = item.get("tip_target_error_px")
                alpha = float(item.get("alpha") or 0.0)
                if err is not None:
                    err_f = float(err)
                    if alpha >= 0.85:
                        checked_tips += 1
                        worst_err_px = max(worst_err_px, err_f)
                        t_sem_item = str(item.get("target_semantic_id") or item.get("anchor_id") or "")
                        t_sem_plan = str(plan_ov.get("target_semantic_id") or plan_ov.get("anchor_id") or "")
                        rows.append({
                            "time_sec": round(rt, 3),
                            "overlay_id": oid,
                            "role": item.get("role"),
                            "target_semantic_id": t_sem_item or None,
                            "anchor_px": item.get("anchor_projected_xy"),
                            "tip_xy": item.get("tip_xy"),
                            "tip_target_error_px": err_f,
                            "is_feature_visible": item.get("is_feature_visible", True),
                        })
                        if err_f > max_tip_error_px:
                            issues.append(
                                f"N29: Pointer tip misaligned for {oid} at t={rt:.2f}s (error={err_f:.1f}px > {max_tip_error_px:.0f}px)"
                            )
                        if t_sem_item in ("stage_center", "default"):
                            issues.append(
                                f"T08: Pointer {oid} targeted generic '{t_sem_item}' instead of specific physical feature"
                            )
                        if t_sem_plan and t_sem_item and t_sem_plan != t_sem_item:
                            issues.append(
                                f"T08: Pointer {oid} hit '{t_sem_item}' instead of planned causal feature '{t_sem_plan}'"
                            )
                        if item.get("pointer_hits_causal_feature") is False:
                            issues.append(
                                f"T08: Pointer {oid} tip missed causal feature mask at t={rt:.2f}s"
                            )
                        treg = item.get("target_region_screen")
                        if isinstance(treg, (list, tuple)) and len(treg) == 4:
                            span_360 = max(abs(float(treg[2]) - float(treg[0])), abs(float(treg[3]) - float(treg[1]))) * (360.0 / 1080.0)
                            if span_360 < 14.0:
                                issues.append(
                                    f"T06/T08: Pointer {oid} target region too tiny on 360px phone ({span_360:.1f}px < 14px)"
                                )

    status = "FAIL" if issues else "PASS"
    if ov_mode != "off" and planned_pointers and checked_tips == 0:
        if justified_skips and len(justified_skips) >= len(planned_pointers):
            status = "NOT_VERIFIED"
            issues.append(
                f"T09: 0 settled pointer tips rendered ({len(justified_skips)} SKIP_JUSTIFIED); technical pointer gate NOT_VERIFIED"
            )
        else:
            status = "FAIL"
            issues.append(
                f"T09: {len(planned_pointers)} pointer overlay(s) planned in editorial_timeline, but checked_settled_tips=0"
            )

    rep = {
        "schema_version": "sd-pointer-tracking-2",
        "status": status,
        "planned_pointer_overlays": len(planned_pointers),
        "checked_settled_tips": checked_tips,
        "justified_skips": justified_skips[:40],
        "worst_tip_target_error_px": round(worst_err_px, 2),
        "max_allowed_error_px": max_tip_error_px,
        "samples": rows[:80],
        "issues": issues,
    }
    if run_dir is not None:
        (run_dir / "pointer_tracking.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    return rep


def audit_caption_layout(
    raw_traces: Optional[List[Dict[str, Any]]] = None,
    editorial_timeline: Optional[Dict[str, Any]] = None,
    mobile_smoke_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    issues: List[str] = []
    min_gap_seen: Optional[float] = None
    checked_chunks = 0

    for rec in (raw_traces or []):
        cap = ((rec.get("telemetry") or {}).get("overlay") or {}).get("caption") or {}
        lay = cap.get("caption_layout")
        if not isinstance(lay, dict):
            continue
        checked_chunks += 1
        ov_cnt = int(lay.get("word_overlap_count", 0))
        mgap = lay.get("min_word_gap_px")
        in_safe = bool(lay.get("in_safe_area", True))
        if ov_cnt > 0:
            issues.append(
                f"Kinetic caption word overlap ({ov_cnt} overlaps) in chunk {cap.get('chunk_id')} at t={rec.get('time')}s"
            )
        if mgap is not None:
            min_gap_seen = float(mgap) if min_gap_seen is None else min(min_gap_seen, float(mgap))
            if float(mgap) < 1.5:
                issues.append(
                    f"Cramped word spacing ({mgap}px < 1.5px) in chunk {cap.get('chunk_id')} at t={rec.get('time')}s"
                )
        if not in_safe:
            issues.append(f"Caption bounding box left safe region at t={rec.get('time')}s")

    if isinstance(mobile_smoke_report, dict):
        for vp, res in (mobile_smoke_report.get("viewports") or {}).items():
            if not res.get("ok", True):
                issues.append(f"Mobile width {vp}px caption layout failure: {res.get('reason')}")

    # Ensure timeline chunks do not have merged glued tokens without spaces
    for ch in (editorial_timeline or {}).get("caption_chunks", []):
        txt = str(ch.get("text") or "")
        for ws in ch.get("words") or []:
            w = str(ws.get("w") or "")
            if len(w) > 22 and "-" not in w and "/" not in w:
                issues.append(f"Suspicious merged token '{w}' in caption chunk '{txt}'")

    return {
        "status": "FAIL" if issues else "PASS",
        "checked_trace_chunks": checked_chunks,
        "min_word_gap_px": min_gap_seen,
        "issues": issues,
    }


def audit_historical_claims(
    historical_claims: Optional[Dict[str, Any]],
    editorial_timeline: Dict[str, Any],
) -> Dict[str, Any]:
    if not historical_claims:
        return {"status": "PASS", "checked_overlays": 0, "note": "No historical claims manifest provided."}

    claims = list(historical_claims.get("claims") or [])
    overlays = list(editorial_timeline.get("overlays") or [])
    issues: List[str] = []

    known_values = []
    for c in claims:
        for k in ("display_token", "unit", "text", "canonical_value", "numeric_value", "secondary_value"):
            if c.get(k) is not None:
                known_values.append(str(c.get(k)).lower())

    estimated_claims = [
        c for c in claims
        if str(c.get("uncertainty") or c.get("qualifier") or "").lower() in ("estimated", "approximate", "approximated")
    ]

    for ov in overlays:
        lbl = f"{ov.get('label', '')} {ov.get('sublabel', '')}".lower()
        nums = re.findall(r"\d+(?:\.\d+)?", lbl)
        if not nums:
            continue
        for num in nums:
            if num in ("1915", "1919", "21", "150", "2.3", "35"):
                matched_claim = next(
                    (
                        c for c in claims
                        if num in str(c.get("canonical_value", ""))
                        or num in str(c.get("numeric_value", ""))
                        or num in str(c.get("secondary_value", ""))
                        or num in str(c.get("display_token", ""))
                        or num in str(c.get("text", ""))
                    ),
                    None,
                )
                if not matched_claim:
                    issues.append(f"Overlay {ov.get('overlay_id')} surfaces ungrounded figure '{num}' absent from historical_claims.json")
                elif matched_claim in estimated_claims:
                    needs_q = (num in ("35", "2.3", "150"))
                    if needs_q and not any(q in lbl for q in ("~", "est", "about", "approx")):
                        issues.append(
                            f"Estimated claim figure '{num}' in {ov.get('overlay_id')} ('{ov.get('label')}') missing '~', 'about', or 'EST.' uncertainty qualifier"
                        )
            else:
                matched_est = next(
                    (
                        c for c in estimated_claims
                        if num == str(c.get("canonical_value", "")).strip()
                        or num == str(c.get("numeric_value", "")).strip()
                    ),
                    None,
                )
                if matched_est and not any(q in lbl for q in ("~", "est", "about", "approx")):
                    issues.append(
                        f"Estimated claim figure '{num}' in {ov.get('overlay_id')} ('{ov.get('label')}') missing '~', 'about', or 'EST.' uncertainty qualifier"
                    )
                elif not any(num in kv for kv in known_values):
                    issues.append(f"Overlay {ov.get('overlay_id')} displays unverified number '{num}' ({ov.get('label')})")

    return {
        "status": "FAIL" if issues else "PASS",
        "claims_count": len(claims),
        "checked_overlays": len(overlays),
        "issues": issues,
    }


def build_ab_alignment(
    run_a: Path,
    run_b: Path,
    out_dir: Path,
    sample_times: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Align Version A vs B timelines by narrative_event_id / beat_id rather than drifting raw clocks."""
    out_dir.mkdir(parents=True, exist_ok=True)
    sb_a_p = run_a / "storyboard.json"
    sb_b_p = run_b / "storyboard.json"
    sc_a_p = run_a / "script.json"
    sc_b_p = run_b / "script.json"

    script_sim: Optional[float] = None
    issues: List[str] = []
    if sc_a_p.exists() and sc_b_p.exists():
        txt_a = " ".join(json.loads(sc_a_p.read_text(encoding="utf-8"))).lower()
        txt_b = " ".join(json.loads(sc_b_p.read_text(encoding="utf-8"))).lower()
        script_sim = round(float(SequenceMatcher(None, txt_a, txt_b).ratio()), 4)
        if script_sim < 0.85:
            issues.append(f"N25: A/B script mismatch: similarity={script_sim:.3f} < 0.85")

    pairs: List[Dict[str, Any]] = []
    sb_a = json.loads(sb_a_p.read_text(encoding="utf-8")) if sb_a_p.exists() else {}
    sb_b = json.loads(sb_b_p.read_text(encoding="utf-8")) if sb_b_p.exists() else {}
    shots_a = list(sb_a.get("shots") or [])
    shots_b = list(sb_b.get("shots") or [])

    if sample_times is None and shots_a and shots_b:
        by_nev_a = {s.get("narrative_event_id"): s for s in shots_a if s.get("narrative_event_id")}
        by_beat_a = {}
        for s in shots_a:
            if s.get("beat_id") is not None:
                by_beat_a.setdefault(s.get("beat_id"), s)

        for idx, sb in enumerate(shots_b):
            sa = None
            align_key = ""
            nev = sb.get("narrative_event_id")
            bid = sb.get("beat_id")
            if nev and nev in by_nev_a:
                sa = by_nev_a[nev]
                align_key = f"narrative_event_id:{nev}"
            elif bid is not None and bid in by_beat_a:
                sa = by_beat_a[bid]
                align_key = f"beat_id:{bid}"
            else:
                issues.append(
                    f"N25: Shot {sb.get('shot_id')} (nev={nev!r}, beat={bid!r}) has no matching event in run_a"
                )
                continue

            ta = round(0.5 * (float(sa["start"]) + float(sa["end"])), 3)
            tb = round(0.5 * (float(sb["start"]) + float(sb["end"])), 3)
            pairs.append({
                "pair_index": idx,
                "align_method": align_key,
                "shot_id_a": sa.get("shot_id"),
                "shot_id_b": sb.get("shot_id"),
                "narrative_event_id": nev,
                "beat_id": bid,
                "t_a": ta,
                "t_b": tb,
                "delta_clock_sec": round(tb - ta, 3),
            })
    else:
        times = sample_times or [1.5, 4.5, 8.5, 13.5, 19.5, 25.5]
        for idx, t in enumerate(times):
            pairs.append({
                "pair_index": idx,
                "align_method": "explicit_clock",
                "shot_id_a": None,
                "shot_id_b": None,
                "narrative_event_id": None,
                "beat_id": None,
                "t_a": round(float(t), 3),
                "t_b": round(float(t), 3),
                "delta_clock_sec": 0.0,
            })

    payload = {
        "schema_version": "sd-ab-alignment-1",
        "alignment_status": "FAIL" if issues else "PASS",
        "script_similarity": script_sim,
        "duration_a_sec": sb_a.get("total_duration_sec"),
        "duration_b_sec": sb_b.get("total_duration_sec"),
        "pairs_count": len(pairs),
        "pairs": pairs,
        "issues": issues,
    }
    align_p = out_dir / "ab_alignment.json"
    align_p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def run_visual_storytelling_qa(
    run_dir: Path,
    storyboard: Dict[str, Any],
    action_graph: Dict[str, Any],
    editorial_timeline: Dict[str, Any],
    scene_diversity_report: Optional[Dict[str, Any]] = None,
    raw_traces: Optional[List[Dict[str, Any]]] = None,
    audio_plan: Optional[Dict[str, Any]] = None,
    historical_claims: Optional[Dict[str, Any]] = None,
    words: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run all event-driven visual storytelling checks and persist `visual_storytelling_qa_report.json`."""
    c_action = audit_story_action_coverage(action_graph, storyboard, raw_traces=raw_traces)
    c_reveal = audit_reveal_order_decoded(action_graph, editorial_timeline, raw_traces=raw_traces, words=words)
    c_variety = audit_spatiotemporal_variety(storyboard, scene_diversity_report, action_graph)
    c_causality = audit_world_state_causality(action_graph, storyboard, raw_traces=raw_traces)
    c_period = audit_period_integrity(storyboard, action_graph, audio_plan=audio_plan)
    c_motion = audit_motion_dynamics(storyboard, scene_diversity_report=scene_diversity_report, raw_traces=raw_traces)
    c_phys_char = audit_physical_and_character_telemetry(storyboard, raw_traces=raw_traces, run_dir=run_dir)
    c_pointer = audit_pointer_tracking(raw_traces, editorial_timeline, run_dir=run_dir)
    c_caption = audit_caption_layout(raw_traces=raw_traces, editorial_timeline=editorial_timeline)
    c_claims = audit_historical_claims(historical_claims, editorial_timeline)

    checks = {
        "story_action_coverage": c_action,
        "reveal_order_decoded": c_reveal,
        "spatiotemporal_variety": c_variety,
        "world_state_causality": c_causality,
        "period_integrity": c_period,
        "motion_dynamics": c_motion,
        "physical_and_character_telemetry": c_phys_char,
        "pointer_tracking": c_pointer,
        "caption_layout": c_caption,
        "historical_claims": c_claims,
    }
    statuses = [c["status"] for c in checks.values()]
    overall = "FAIL" if ("FAIL" in statuses or "NOT_VERIFIED" in statuses) else ("WARN" if "WARN" in statuses else "PASS")

    rep = {
        "schema_version": SCHEMA_VERSION,
        "overall_status": overall,
        "subjective_visual_review": "NOT_VERIFIED",
        "viewer_retention_status": "NOT_VERIFIED",
        "checks": checks,
    }
    (run_dir / "visual_storytelling_qa_report.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return rep
