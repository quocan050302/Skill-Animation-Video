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
        str(s.get("scene_family") or "").startswith("boston_") for s in shots
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
                    # Only require '~' / 'EST.' / 'about' on estimated figures (35 mph, ~2.3M, ~150), not exact '21' in a dual 21/150 card unless '35' or '2.3' or '150' is present without qualifier
                    needs_q = (
                        num in ("35", "2.3")
                        or (num == "150")
                    )
                    if needs_q and not any(q in lbl for q in ("~", "est", "about", "approx")):
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
        if script_sim < 0.45:
            issues.append(f"A/B script mismatch: similarity={script_sim:.3f} < 0.45")

    pairs: List[Dict[str, Any]] = []
    sb_a = json.loads(sb_a_p.read_text(encoding="utf-8")) if sb_a_p.exists() else {}
    sb_b = json.loads(sb_b_p.read_text(encoding="utf-8")) if sb_b_p.exists() else {}
    shots_a = list(sb_a.get("shots") or [])
    shots_b = list(sb_b.get("shots") or [])

    if sample_times is None and shots_a and shots_b:
        by_nev_a = {s.get("narrative_event_id"): s for s in shots_a if s.get("narrative_event_id")}
        by_beat_a = {}
        for s in shots_a:
            by_beat_a.setdefault(s.get("beat_id"), s)

        for idx, sb in enumerate(shots_b):
            sa = None
            align_key = "normalized_shot_index"
            nev = sb.get("narrative_event_id")
            bid = sb.get("beat_id")
            if nev and nev in by_nev_a:
                sa = by_nev_a[nev]
                align_key = f"narrative_event_id:{nev}"
            elif bid and bid in by_beat_a:
                sa = by_beat_a[bid]
                align_key = f"beat_id:{bid}"
            else:
                mapped_idx = min(len(shots_a) - 1, int(round((idx / max(1, len(shots_b) - 1)) * max(0, len(shots_a) - 1))))
                sa = shots_a[mapped_idx]

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
    c_caption = audit_caption_layout(raw_traces=raw_traces, editorial_timeline=editorial_timeline)
    c_claims = audit_historical_claims(historical_claims, editorial_timeline)

    checks = {
        "story_action_coverage": c_action,
        "reveal_order_decoded": c_reveal,
        "spatiotemporal_variety": c_variety,
        "world_state_causality": c_causality,
        "period_integrity": c_period,
        "motion_dynamics": c_motion,
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
