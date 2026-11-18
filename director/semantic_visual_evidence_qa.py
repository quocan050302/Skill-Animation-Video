"""STEP 7D (SD-RETENTION-04.R1): Decoded Semantic Visual Evidence, Pointer Semantics & Causal Continuity QA.

Audits rendered pixels, WebGL semantic object-ID mattes, runtime camera/world telemetry,
and editorial overlays against `CausalEvent` + `VisualEvidenceContract`s without trusting
self-declared text labels.

Outputs persisted in `run_dir`:
- `visual_claim_coverage.json`
- `pointer_semantics.json`
- `causal_evidence_gaps.csv`
- `semantic_matte_alignment.json`
- `causal_gates_status.json`
- `event_aligned_before_action_after.jpg`
- `qa_failures_visual_examples/` (annotated crops for any diagnostic findings or sample failures)
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .decoded_visual_quality import REF_ANALYSIS_H, REF_ANALYSIS_W, render_subject_id_matte_at_t
from .quality_gate import _decode_frame_rgb
from .visual_causality_director import EVIDENCE_SUPPORTED, validate_world_state_conservation


SCHEMA_VERSION = "sd-semantic-visual-evidence-qa-1"


def _load_detailed_matte_channels(matte_path: Path, overlay_boxes_1080: Optional[Sequence[Sequence[float]]] = None) -> Dict[str, Any]:
    """Decode WebGL semantic ID matte into fine-grained cause/effect/reference/character masks."""
    base = render_subject_id_matte_at_t(
        matte_path,
        overlay_boxes_1080=overlay_boxes_1080,
        width=REF_ANALYSIS_W,
        height=REF_ANALYSIS_H,
    )
    if base.get("status") != "PASS":
        return base
    with Image.open(matte_path) as im:
        arr = np.asarray(im.convert("RGB").resize((REF_ANALYSIS_W, REF_ANALYSIS_H), Image.Resampling.NEAREST), dtype=np.float32)

    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    # Preserve R2 compatibility while separating encoded roles cleanly:
    # causal_feature=0x00ff00, cause_source=0x00e060, effect_result=0x20ff20,
    # reference_fixed=0xe00050, character=0x0000ff, subject=0xff0000
    cause_source = (g > 175.0) & (r < 60.0) & (b >= 60.0) & (b < 140.0)
    effect_result = (g > 175.0) & (r >= 18.0) & (r < 95.0) & (b < 60.0)
    reference_fixed = (r > 175.0) & (g < 65.0) & (b >= 45.0) & (b < 120.0)
    causal_all = (g > 110.0) & (r < 95.0)
    character = (b > 110.0) & (r < 95.0) & (g < 95.0)
    subject = ((r > 110.0) & (g < 95.0) & (b < 95.0)) | causal_all

    total_px = float(arr.shape[0] * arr.shape[1])

    def _centroid_norm(m: np.ndarray) -> Optional[List[float]]:
        ys, xs = np.where(m)
        if len(xs) < 6:
            return None
        return [round(float(xs.mean() / REF_ANALYSIS_W), 4), round(float(ys.mean() / REF_ANALYSIS_H), 4)]

    return {
        **base,
        "cause_source_mask": cause_source,
        "effect_result_mask": effect_result,
        "reference_fixed_mask": reference_fixed,
        "causal_mask": causal_all,
        "character_mask": character,
        "subject_mask": subject,
        "role_ratios": {
            "causal_feature": round(float(causal_all.sum() / total_px), 4),
            "cause_source": round(float(cause_source.sum() / total_px), 4),
            "effect_result": round(float(effect_result.sum() / total_px), 4),
            "reference_fixed": round(float(reference_fixed.sum() / total_px), 4),
            "character": round(float(character.sum() / total_px), 4),
            "subject": round(float(subject.sum() / total_px), 4),
        },
        "centroids": {
            "causal": _centroid_norm(causal_all),
            "reference_fixed": _centroid_norm(reference_fixed),
            "character": _centroid_norm(character),
            "subject": _centroid_norm(subject),
        },
    }


def _resolve_matte_near_t(
    ts: float,
    matte_frames: List[Dict[str, Any]],
    qa_dir: Path,
    require_matte: bool = False,
) -> Dict[str, Any]:
    if not matte_frames:
        return {"status": "FAIL" if require_matte else "NOT_VERIFIED", "reason": "No semantic matte frames found"}
    match = min(matte_frames, key=lambda mf: abs(float(mf.get("t_sec", -99.0)) - ts))
    if abs(float(match.get("t_sec", -99.0)) - ts) > 0.65:
        return {"status": "FAIL" if require_matte else "NOT_VERIFIED", "reason": f"No matte within 0.65s of t={ts:.2f}s"}
    mp = Path(str(match.get("matte_path") or ""))
    if not mp.is_absolute():
        mp = qa_dir / "mattes" / mp.name
    if not mp.exists():
        cand = qa_dir / "mattes" / mp.name
        if cand.exists():
            mp = cand
        else:
            return {"status": "FAIL" if require_matte else "NOT_VERIFIED", "reason": f"Missing matte image {mp.name}"}
    return _load_detailed_matte_channels(mp, overlay_boxes_1080=match.get("overlay_boxes_1080"))


def audit_visual_claim_coverage(
    causal_graph: Dict[str, Any],
    evidence_contracts: Dict[str, Any],
    storyboard: Dict[str, Any],
    video_mp4: Optional[Path] = None,
    matte_manifest: Optional[Dict[str, Any]] = None,
    qa_dir: Optional[Path] = None,
    raw_traces: Optional[List[Dict[str, Any]]] = None,
    require_decoded_frames: bool = True,
) -> Dict[str, Any]:
    """Verify each causal claim actually changes decoded pixels & matte roles across before -> action -> after."""
    events = list(causal_graph.get("causal_events") or [])
    contracts = dict(evidence_contracts.get("by_event_id") or {})
    shots = list(storyboard.get("shots") or [])
    shots_by_cevid = {str(s.get("causal_event_id")): s for s in shots if s.get("causal_event_id")}
    shots_by_nevid = {str(s.get("narrative_event_id")): s for s in shots if s.get("narrative_event_id")}

    matte_frames = list((matte_manifest or {}).get("frames") or [])
    can_decode = bool(video_mp4 and Path(video_mp4).exists())
    total_dur = float(storyboard.get("total_duration_sec") or 10.0)

    if require_decoded_frames and not can_decode:
        return {
            "schema_version": "sd-visual-claim-coverage-1",
            "status": "FAIL",
            "issues": ["Missing decoded video_mp4 for pixel claim verification"],
            "warnings": [],
            "claims": [],
        }

    issues: List[str] = []
    warnings: List[str] = []
    claim_rows: List[Dict[str, Any]] = []
    matte_alignment_rows: List[Dict[str, Any]] = []
    gaps: List[Dict[str, Any]] = []

    for idx, ev in enumerate(events):
        cevid = str(ev.get("causal_event_id") or f"cev_{idx:03d}")
        nevid = str(ev.get("narrative_event_id") or f"nev_{idx:03d}")
        proof_type = str(ev.get("proof_type") or "state_change_before_after")
        contract = contracts.get(cevid) or {}
        exp = dict(contract.get("expected_visible_consequence") or {})
        ev_status = str(ev.get("evidence_status") or EVIDENCE_SUPPORTED)

        sh = shots_by_cevid.get(cevid) or shots_by_nevid.get(nevid) or (shots[idx] if idx < len(shots) else {})
        st = float(ev.get("onset_sec") if ev.get("onset_sec") is not None else sh.get("start", 0.0))
        en = float(ev.get("settle_sec") if ev.get("settle_sec") is not None else sh.get("end", st + 1.5))
        dur = max(0.3, en - st)
        t_before = round(max(0.02, min(total_dur - 0.12, st + min(0.12, dur * 0.14))), 3)
        t_action = round(max(t_before + 0.04, min(total_dur - 0.08, st + dur * 0.52)), 3)
        t_after = round(max(t_action + 0.04, min(total_dur - 0.03, en - min(0.12, dur * 0.14))), 3)

        if ev_status != EVIDENCE_SUPPORTED:
            claim_rows.append({
                "causal_event_id": cevid,
                "narrative_claim_id": ev.get("narrative_claim_id"),
                "shot_id": sh.get("shot_id"),
                "proof_type": proof_type,
                "evidence_status": ev_status,
                "status": "UNVERIFIED_UNSUPPORTED",
                "t_before": t_before,
                "t_action": t_action,
                "t_after": t_after,
            })
            gaps.append({
                "causal_event_id": cevid,
                "shot_id": sh.get("shot_id"),
                "severity": "advisory_unsupported",
                "gap_type": ev_status,
                "detail": "Event marked unsupported in locked engine; no invented visual proof.",
            })
            warnings.append(f"Advisory: event {cevid} marked {ev_status}")
            continue

        mad_ba = None
        mad_pa = None
        pixel_proof_ok = True
        if can_decode:
            selected_skill = str(storyboard.get("selected_skill") or causal_graph.get("selected_skill") or "zach-d-films")
            f0 = _decode_frame_rgb(Path(video_mp4), t_before, scale_w=REF_ANALYSIS_W, scale_h=REF_ANALYSIS_H).astype(np.float32)
            f1 = _decode_frame_rgb(Path(video_mp4), t_action, scale_w=REF_ANALYSIS_W, scale_h=REF_ANALYSIS_H).astype(np.float32)
            f2 = _decode_frame_rgb(Path(video_mp4), t_after, scale_w=REF_ANALYSIS_W, scale_h=REF_ANALYSIS_H).astype(np.float32)
            mad_ba = round(float(max(np.mean(np.abs(f1 - f0)), np.mean(np.abs(f2 - f0)))), 3)
            mad_pa = round(float(np.mean(np.abs(f2 - f1))), 3)
            changed_ratio = float(max(
                np.mean(np.max(np.abs(f1 - f0), axis=-1) > 12.0),
                np.mean(np.max(np.abs(f2 - f0), axis=-1) > 12.0),
            ))
            is_sparse_2d = selected_skill in ("minimalistic-graphics", "graph")
            is_frozen = (mad_ba < 0.08 and changed_ratio < 0.0005) if is_sparse_2d else (mad_ba < 0.8)
            if is_frozen:
                pixel_proof_ok = False
                msg = f"N01/N05: Static frozen pixel proof for {cevid} ({sh.get('shot_id')}) across [{t_before:.2f}..{t_after:.2f}s] (mad={mad_ba:.2f} < 0.8)"
                issues.append(msg)
                gaps.append({"causal_event_id": cevid, "shot_id": sh.get("shot_id"), "severity": "blocking", "gap_type": "frozen_pixels", "detail": msg})

        # Verify semantic matte presence for expected role
        req_role = str(exp.get("requires_matte_role") or "subject")
        matte_ok = True
        role_ratio = None
        ref_ratio = None
        if matte_frames and qa_dir is not None:
            m_pk = _resolve_matte_near_t(t_action, matte_frames, qa_dir, require_matte=False)
            if m_pk.get("status") == "PASS":
                ratios = m_pk.get("role_ratios") or {}
                if req_role == "character":
                    role_ratio = float(ratios.get("character", 0.0))
                elif req_role == "causal_feature":
                    role_ratio = float(ratios.get("causal_feature", 0.0))
                else:
                    role_ratio = float(ratios.get("subject", 0.0))
                ref_ratio = float(ratios.get("reference_fixed", 0.0))
                min_ratio = 0.004 if req_role in ("character", "causal_feature") else 0.02
                if role_ratio < min_ratio:
                    matte_ok = False
                    msg = f"N02: Claim {cevid} requires matte role '{req_role}' >= {min_ratio:.3f}, got {role_ratio:.4f} at t={t_action:.2f}s"
                    issues.append(msg)
                    gaps.append({"causal_event_id": cevid, "shot_id": sh.get("shot_id"), "severity": "blocking", "gap_type": "missing_matte_role", "detail": msg})

                matte_alignment_rows.append({
                    "causal_event_id": cevid,
                    "shot_id": sh.get("shot_id"),
                    "t_sec": t_action,
                    "required_matte_role": req_role,
                    "role_ratios": ratios,
                    "centroids": m_pk.get("centroids"),
                    "matte_ok": matte_ok,
                })

        row_status = "PASS" if (pixel_proof_ok and matte_ok) else "FAIL"
        claim_rows.append({
            "causal_event_id": cevid,
            "narrative_claim_id": ev.get("narrative_claim_id"),
            "shot_id": sh.get("shot_id"),
            "proof_type": proof_type,
            "evidence_status": ev_status,
            "expected_signal": exp.get("observable_signal"),
            "t_before": t_before,
            "t_action": t_action,
            "t_after": t_after,
            "frame_mad_before_action_or_after": mad_ba,
            "frame_mad_action_after": mad_pa,
            "required_matte_role": req_role,
            "matte_role_ratio": role_ratio,
            "reference_fixed_ratio": ref_ratio,
            "status": row_status,
        })

    supported_total = sum(1 for r in claim_rows if r.get("evidence_status") == EVIDENCE_SUPPORTED)
    supported_passed = sum(1 for r in claim_rows if r.get("evidence_status") == EVIDENCE_SUPPORTED and r.get("status") == "PASS")
    cov_ratio = round(supported_passed / float(max(1, supported_total)), 3)

    status = "FAIL" if issues else ("WARN" if warnings else "PASS")
    return {
        "schema_version": "sd-visual-claim-coverage-1",
        "status": status,
        "claims_total": len(claim_rows),
        "supported_claims_count": supported_total,
        "supported_claims_verified_count": supported_passed,
        "claim_coverage_ratio": cov_ratio,
        "claims": claim_rows,
        "matte_alignment": matte_alignment_rows,
        "gaps": gaps,
        "issues": issues,
        "warnings": warnings,
    }


def audit_relative_motion_evidence(
    causal_graph: Dict[str, Any],
    storyboard: Dict[str, Any],
    raw_traces: Optional[List[Dict[str, Any]]] = None,
    matte_manifest: Optional[Dict[str, Any]] = None,
    qa_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Verify motion claims are physically measurable vs fixed reference, not faked by orbiting a frozen mesh."""
    events = list(causal_graph.get("causal_events") or [])
    shots = list(storyboard.get("shots") or [])
    shots_by_id = {str(s.get("shot_id")): s for s in shots}
    shots_by_cevid = {str(s.get("causal_event_id")): s for s in shots if s.get("causal_event_id")}
    matte_frames = list((matte_manifest or {}).get("frames") or [])

    traces_by_sid: Dict[str, List[Dict[str, Any]]] = {}
    for rec in (raw_traces or []):
        tel = rec.get("telemetry") or {}
        sid = str(rec.get("shot_id") or tel.get("shot_id") or "")
        if sid:
            traces_by_sid.setdefault(sid, []).append(tel)

    issues: List[str] = []
    warnings: List[str] = []
    checked = 0

    for idx, ev in enumerate(events):
        proof_type = str(ev.get("proof_type") or "")
        if proof_type not in (
            "displacement_relative_to_fixed_reference",
            "particle_path_propagation",
            "material_deformation",
            "pressure_flow_difference",
        ):
            continue
        sh = shots_by_cevid.get(str(ev.get("causal_event_id"))) or (shots[idx] if idx < len(shots) else {})
        sid = str(sh.get("shot_id") or "")
        checked += 1

        # 1. Check physical_motion telemetry non-zero physical displacement
        tels = traces_by_sid.get(sid, [])
        if tels:
            vdisp = max(
                float((t.get("physical_motion") or {}).get("vertex_disp_max_m") or 0.0)
                for t in tels
            )
            clarity_vals = [
                float((t.get("physical_motion") or {}).get("air_clarity_recovery"))
                for t in tels
                if (t.get("physical_motion") or {}).get("air_clarity_recovery") is not None
            ]
            obsc_vals = [
                float((t.get("physical_motion") or {}).get("visibility_obscuration"))
                for t in tels
                if (t.get("physical_motion") or {}).get("visibility_obscuration") is not None
            ]
            char_disps = [
                float((t.get("character_performance") or {}).get("root_disp_m") or 0.0)
                for t in tels
                if isinstance(t.get("character_performance"), dict)
            ]
            span_obsc = (max(obsc_vals) - min(obsc_vals)) if len(obsc_vals) >= 2 else 0.0
            span_clr = (max(clarity_vals) - min(clarity_vals)) if len(clarity_vals) >= 2 else 0.0
            max_char_d = max(char_disps) if char_disps else 0.0

            if max(vdisp, span_obsc, span_clr, max_char_d) < 0.015:
                issues.append(
                    f"N04/N06: Shot {sid} claims '{proof_type}' yet physical telemetry reported negligible state change (vdisp={vdisp:.4f}m)"
                )

        # 2. If fixed reference anchor is expected in matte manifest across start->end of shot, confirm relative separation or motion
        if proof_type == "displacement_relative_to_fixed_reference" and matte_frames and qa_dir is not None and sh:
            st, en = float(sh.get("start", 0.0)), float(sh.get("end", 1.0))
            m0 = _resolve_matte_near_t(st + 0.12, matte_frames, qa_dir)
            m2 = _resolve_matte_near_t(max(st + 0.18, en - 0.12), matte_frames, qa_dir)
            if m0.get("status") == "PASS" and m2.get("status") == "PASS":
                ref_r = float((m2.get("role_ratios") or {}).get("reference_fixed", 0.0))
                if ref_r <= 0.0005:
                    warnings.append(
                        f"Advisory: Shot {sid} claims relative displacement without prominent `reference_fixed` pixels in matte"
                    )

    return {
        "schema_version": "sd-relative-motion-evidence-1",
        "status": "FAIL" if issues else ("WARN" if warnings else "PASS"),
        "checked_motion_claims": checked,
        "issues": issues,
        "warnings": warnings,
    }


def audit_claim_pointer_semantics(
    editorial_timeline: Dict[str, Any],
    causal_graph: Optional[Dict[str, Any]] = None,
    raw_traces: Optional[List[Dict[str, Any]]] = None,
    matte_manifest: Optional[Dict[str, Any]] = None,
    qa_dir: Optional[Path] = None,
    max_tip_error_px: float = 36.0,
) -> Dict[str, Any]:
    """Audit pointer & overlay semantic bindings, decoded causal-feature target hits, and spoilers (`pointer_semantics.json`)."""
    overlays = list((editorial_timeline or {}).get("overlays") or [])
    ov_by_id = {str(o.get("overlay_id")): o for o in overlays if o.get("overlay_id")}
    cev_by_id = {str(e.get("causal_event_id")): e for e in ((causal_graph or {}).get("causal_events") or [])}
    matte_frames = list((matte_manifest or {}).get("frames") or [])

    issues: List[str] = []
    warnings: List[str] = []
    entries: List[Dict[str, Any]] = []

    for ov in overlays:
        oid = str(ov.get("overlay_id") or "")
        cevid = ov.get("causal_event_id")
        claim_id = ov.get("narrative_claim_id")
        t_ent = ov.get("target_entity_id") or ov.get("anchor_id")
        t_feat = ov.get("target_feature_id") or ov.get("target_semantic_id") or ov.get("anchor_id")
        p_tgt = ov.get("proof_target_id") or t_feat
        s_reg = ov.get("semantic_region_of_change")
        why_ov = ov.get("why_this_overlay") or ov.get("pointer_reason") or ov.get("why_role")
        ptr_shape = str(ov.get("pointer_shape") or "none")

        missing = [
            fld for fld, val in (
                ("narrative_claim_id", claim_id),
                ("target_entity_id", t_ent),
                ("target_feature_id", t_feat),
                ("proof_target_id", p_tgt),
                ("semantic_region_of_change", s_reg),
                ("why_this_overlay", why_ov),
            )
            if not str(val or "").strip()
        ]
        if missing:
            issues.append(f"N08: Overlay {oid} missing semantic proof bindings: {missing}")

        if str(t_feat) in ("stage_center", "default") and ptr_shape != "none":
            issues.append(f"N08: Pointer {oid} targeted generic '{t_feat}' instead of specific physical feature")

        cev = cev_by_id.get(str(cevid or ""))
        if cev and ptr_shape not in ("none", "") and cev.get("feature_id") and str(t_feat) == "stage_center":
            issues.append(f"N08: Pointer {oid} ignored causal feature '{cev.get('feature_id')}'")

        entries.append({
            "overlay_id": oid,
            "shot_id": ov.get("shot_id"),
            "causal_event_id": cevid,
            "narrative_claim_id": claim_id,
            "role": ov.get("role"),
            "pointer_shape": ptr_shape,
            "target_entity_id": t_ent,
            "target_feature_id": t_feat,
            "proof_target_id": p_tgt,
            "semantic_region_of_change": s_reg,
            "why_this_overlay": why_ov,
            "start": ov.get("start"),
            "end": ov.get("end"),
            "missing_fields": missing,
        })

    # Inspect rendered pointer tip pixel alignment against WebGL matte masks when traces + mattes present
    checked_settled = 0
    worst_err_px = 0.0
    for rec in (raw_traces or []):
        rt = float(rec.get("time_sec", rec.get("time", 0.0)))
        ov_list = (((rec.get("telemetry") or {}).get("overlay") or {}).get("overlays")) or []
        for item in ov_list:
            if not item.get("visible"):
                continue
            alpha = float(item.get("alpha") or 0.0)
            if alpha < 0.85:
                continue
            oid = str(item.get("overlay_id") or "")
            plan_ov = ov_by_id.get(oid, {})
            err = item.get("tip_target_error_px")
            if err is not None:
                checked_settled += 1
                err_f = float(err)
                worst_err_px = max(worst_err_px, err_f)
                if err_f > max_tip_error_px:
                    issues.append(f"N09: Pointer {oid} tip error {err_f:.1f}px > {max_tip_error_px:.0f}px at t={rt:.2f}s")
            # Check decoded matte pixel neighborhood around tip_xy if matte available
            tip_xy = item.get("tip_xy")
            if isinstance(tip_xy, (list, tuple)) and len(tip_xy) == 2 and matte_frames and qa_dir is not None:
                m_res = _resolve_matte_near_t(rt, matte_frames, qa_dir)
                if m_res.get("status") == "PASS":
                    ux = max(0, min(REF_ANALYSIS_W - 1, int(round(float(tip_xy[0]) / 1080.0 * REF_ANALYSIS_W))))
                    vy = max(0, min(REF_ANALYSIS_H - 1, int(round(float(tip_xy[1]) / 1920.0 * REF_ANALYSIS_H))))
                    r_box = 14
                    subj_m = m_res["subject_mask"] | m_res["character_mask"]
                    patch = subj_m[max(0, vy - r_box):min(REF_ANALYSIS_H, vy + r_box + 1), max(0, ux - r_box):min(REF_ANALYSIS_W, ux + r_box + 1)]
                    if not patch.any():
                        warnings.append(
                            f"Advisory: Pointer {oid} ({plan_ov.get('target_feature_id')}) tip at ({ux},{vy}) fell outside foreground matte patch at t={rt:.2f}s"
                        )

    return {
        "schema_version": "sd-pointer-semantics-1",
        "status": "FAIL" if issues else ("WARN" if warnings else "PASS"),
        "overlays_count": len(overlays),
        "checked_settled_tips": checked_settled,
        "worst_tip_target_error_px": round(worst_err_px, 2),
        "overlays": entries,
        "issues": issues,
        "warnings": warnings,
    }


def audit_causal_transition_visibility(
    storyboard: Dict[str, Any],
    causal_graph: Dict[str, Any],
    transition_edl: Optional[Dict[str, Any]] = None,
    video_mp4: Optional[Path] = None,
) -> Dict[str, Any]:
    """Verify cross-cut world state conservation & actual decoded bridge transition visibility."""
    shots = list(storyboard.get("shots") or [])
    cons = validate_world_state_conservation(list(causal_graph.get("causal_events") or []))
    issues = list(cons.get("violations") or [])
    warnings: List[str] = []

    trs = list((transition_edl or {}).get("transitions") or [])
    can_decode = bool(video_mp4 and Path(video_mp4).exists())
    checked_bridges = 0

    for tr in trs:
        method = str(tr.get("actual_method") or "cut")
        b_sec = float(tr.get("boundary_sec") or 0.0)
        if b_sec <= 0.05:
            continue
        checked_bridges += 1
        if can_decode and method not in ("cut", "cut_on_action"):
            f_pre = _decode_frame_rgb(Path(video_mp4), max(0.02, b_sec - 0.14), scale_w=REF_ANALYSIS_W, scale_h=REF_ANALYSIS_H).astype(np.float32)
            f_mid = _decode_frame_rgb(Path(video_mp4), b_sec, scale_w=REF_ANALYSIS_W, scale_h=REF_ANALYSIS_H).astype(np.float32)
            f_post = _decode_frame_rgb(Path(video_mp4), b_sec + 0.14, scale_w=REF_ANALYSIS_W, scale_h=REF_ANALYSIS_H).astype(np.float32)
            mean_luma = float(f_mid.mean())
            if mean_luma < 4.0 and method != "dip_to_black":
                issues.append(f"N10: Transition {tr.get('transition_id')} ({method}) produced near-black frame (luma={mean_luma:.1f}) at t={b_sec:.2f}s")
            mad = float(np.mean(np.abs(f_post - f_pre)))
            if mad < 0.5:
                issues.append(f"N10: Transition {tr.get('transition_id')} frozen across boundary t={b_sec:.2f}s (mad={mad:.2f})")

    return {
        "schema_version": "sd-causal-transition-visibility-1",
        "status": "FAIL" if issues else ("WARN" if warnings else "PASS"),
        "world_state_conservation_status": cons["status"],
        "transitions_checked": checked_bridges,
        "issues": issues,
        "warnings": warnings,
    }


def audit_story_silent_comprehension_proxies(
    storyboard: Dict[str, Any],
    causal_graph: Dict[str, Any],
    claim_cov: Dict[str, Any],
    camera_intent_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute strict structural muted-comprehension proxies without claiming verified human understanding."""
    shots = list(storyboard.get("shots") or [])
    events = list(causal_graph.get("causal_events") or [])
    distinct_proofs = sorted({str(e.get("proof_type")) for e in events if e.get("proof_type")})
    distinct_fams = sorted({str(s.get("scene_family")) for s in shots if s.get("scene_family")})

    cov_ratio = float(claim_cov.get("claim_coverage_ratio", 0.0))
    mean_cam_gain = float((camera_intent_report or {}).get("mean_info_gain_score", 0.0))

    issues: List[str] = []
    warnings: List[str] = []
    selected_skill = str(storyboard.get("selected_skill") or "zach-d-films")
    if selected_skill == "zach-d-films" and len(events) >= 4 and len(distinct_proofs) < 3:
        issues.append(f"Only {len(distinct_proofs)} distinct causal proof types across {len(events)} events (< 3)")
    elif selected_skill != "zach-d-films" and events and not distinct_proofs:
        issues.append("No causal proof types assigned to storyboard events")
    if cov_ratio < 0.85:
        issues.append(f"Supported causal visual claim coverage {cov_ratio:.2f} < 0.85")
    if camera_intent_report and mean_cam_gain < 0.65:
        warnings.append(f"Advisory: mean camera info-gain score {mean_cam_gain:.2f} < 0.65")

    return {
        "schema_version": "sd-silent-comprehension-proxy-1",
        "status": "FAIL" if issues else ("WARN" if warnings else "PASS"),
        "subjective_visual_review": "NOT_VERIFIED",
        "distinct_proof_types_count": len(distinct_proofs),
        "distinct_scene_families_count": len(distinct_fams),
        "claim_coverage_ratio": cov_ratio,
        "mean_camera_info_gain": mean_cam_gain,
        "issues": issues,
        "warnings": warnings,
    }


def render_event_aligned_before_action_after_strip(
    video_mp4: Path,
    claim_rows: List[Dict[str, Any]],
    out_path: Path,
    max_events: int = 7,
) -> Optional[Path]:
    """Render 3-column decoded Before/Action/After proof sheet for visual inspection."""
    if not video_mp4.exists() or not claim_rows:
        return None
    picked = claim_rows[:max_events]
    cell_w, cell_h = 270, 480
    hdr_h = 34
    cols = 3
    rows = len(picked)
    canvas = Image.new("RGB", (cols * cell_w, rows * (cell_h + hdr_h)), (14, 18, 28))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    for r_idx, row in enumerate(picked):
        y0 = r_idx * (cell_h + hdr_h)
        times = [
            ("BEFORE", float(row.get("t_before", 0.1))),
            ("ACTION", float(row.get("t_action", 0.5))),
            ("AFTER", float(row.get("t_after", 0.9))),
        ]
        for c_idx, (tag, ts) in enumerate(times):
            x0 = c_idx * cell_w
            rgb = _decode_frame_rgb(video_mp4, ts, scale_w=cell_w, scale_h=cell_h)
            canvas.paste(Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)), (x0, y0 + hdr_h))
            lbl = f"{row.get('causal_event_id')} {tag} {ts:.2f}s | {str(row.get('proof_type'))[:16]}"
            draw.text((x0 + 6, y0 + 10), lbl, fill=(240, 245, 255), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(out_path), quality=90)
    return out_path


def write_qa_failure_examples(
    out_dir: Path,
    video_mp4: Optional[Path],
    claim_rows: List[Dict[str, Any]],
    issues: List[str],
) -> None:
    """Persist diagnostic visual crops into `qa_failures_visual_examples/` cleanly."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: List[Dict[str, Any]] = []
    if video_mp4 and Path(video_mp4).exists():
        # Include any failed rows first; otherwise include up to 2 clean baseline examples clearly labeled CLEAN
        failed = [r for r in claim_rows if r.get("status") == "FAIL"]
        targets = failed[:4] if failed else claim_rows[:2]
        for r in targets:
            ts = float(r.get("t_action", 0.5))
            rgb = _decode_frame_rgb(Path(video_mp4), ts, scale_w=REF_ANALYSIS_W, scale_h=REF_ANALYSIS_H)
            im = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
            dr = ImageDraw.Draw(im)
            tag = "FAIL_DIAGNOSTIC" if r.get("status") == "FAIL" else "VERIFIED_SAMPLE"
            dr.rectangle([6, 6, REF_ANALYSIS_W - 6, 36], fill=(15, 23, 42))
            dr.text((12, 14), f"{tag}: {r.get('causal_event_id')} t={ts:.2f}s ({r.get('proof_type')})", fill=(255, 220, 120))
            fname = f"{tag.lower()}_{r.get('causal_event_id')}.jpg"
            im.save(str(out_dir / fname), quality=90)
            manifest.append({"file": fname, "status": r.get("status"), "causal_event_id": r.get("causal_event_id"), "t_sec": ts})
    (out_dir / "examples_index.json").write_text(
        json.dumps({"issues_logged": issues, "examples": manifest}, indent=2),
        encoding="utf-8",
    )


def audit_ab_vo_and_metric_consistency(run_a: Path, run_b: Path) -> Dict[str, Any]:
    """Verify exact A/B `vo.wav` PCM SHA256 identity AND detect stale/tampered JSON summaries (`METRIC_INCONSISTENCY`)."""
    import wave

    def _pcm_sha(wav_p: Path) -> Optional[str]:
        if not wav_p.exists():
            return None
        with wave.open(str(wav_p), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            return hashlib.sha256(frames).hexdigest()

    vo_a = run_a / "audio" / "vo.wav"
    vo_b = run_b / "audio" / "vo.wav"
    if not vo_a.exists():
        vo_a = run_a / "voice.wav"
    if not vo_b.exists():
        vo_b = run_b / "voice.wav"

    sha_a = _pcm_sha(vo_a)
    sha_b = _pcm_sha(vo_b)
    issues: List[str] = []
    if sha_a is None or sha_b is None:
        issues.append(f"Missing A/B VO audio for parity check (a={sha_a is not None}, b={sha_b is not None})")
    elif sha_a != sha_b:
        issues.append(f"A/B VO PCM SHA256 mismatch: run_a={sha_a[:12]} != run_b={sha_b[:12]}")

    # Check report metric consistency on each run dir
    for label, rdir in (("run_a", run_a), ("run_b", run_b)):
        vdr_p = rdir / "audio" / "voice_delivery_report.json"
        if not vdr_p.exists():
            vdr_p = rdir / "voice_delivery_report.json"
        if vdr_p.exists():
            vdr = json.loads(vdr_p.read_text(encoding="utf-8"))
            recorded_sha = vdr.get("vo_pcm_sha256") or vdr.get("voice_pcm_sha256")
            cur_sha = sha_a if label == "run_a" else sha_b
            if recorded_sha and cur_sha and recorded_sha != cur_sha:
                issues.append(f"METRIC_INCONSISTENCY: {label} voice_delivery_report stale SHA {recorded_sha[:12]} != {cur_sha[:12]}")
            if vdr.get("status") == "PASS" and vdr.get("issues"):
                issues.append(f"METRIC_INCONSISTENCY: {label} voice_delivery_report claims PASS while issues={vdr.get('issues')}")

    return {
        "schema_version": "sd-ab-vo-consistency-1",
        "status": "FAIL" if issues else "PASS",
        "vo_a_pcm_sha256": sha_a,
        "vo_b_pcm_sha256": sha_b,
        "pcm_identical": bool(sha_a and sha_b and sha_a == sha_b),
        "issues": issues,
    }


def run_semantic_visual_evidence_qa(
    run_dir: Path,
    storyboard: Dict[str, Any],
    causal_graph: Dict[str, Any],
    evidence_contracts: Dict[str, Any],
    editorial_timeline: Optional[Dict[str, Any]] = None,
    transition_edl: Optional[Dict[str, Any]] = None,
    camera_intent_report: Optional[Dict[str, Any]] = None,
    video_mp4: Optional[Path] = None,
    raw_traces: Optional[List[Dict[str, Any]]] = None,
    matte_manifest: Optional[Dict[str, Any]] = None,
    require_decoded_frames: bool = True,
) -> Dict[str, Any]:
    """Run complete SD-RETENTION-04.R1 decoded semantic QA & persist all evidence files."""
    run_dir = Path(run_dir)
    qa_dir = run_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    if matte_manifest is None and (qa_dir / "mattes" / "matte_manifest.json").exists():
        matte_manifest = json.loads((qa_dir / "mattes" / "matte_manifest.json").read_text(encoding="utf-8"))
    if raw_traces is None and (run_dir / "logs" / "raw_render_telemetry.json").exists():
        raw_traces = list((json.loads((run_dir / "logs" / "raw_render_telemetry.json").read_text(encoding="utf-8")) or {}).get("traces") or [])

    c_claim = audit_visual_claim_coverage(
        causal_graph=causal_graph,
        evidence_contracts=evidence_contracts,
        storyboard=storyboard,
        video_mp4=video_mp4,
        matte_manifest=matte_manifest,
        qa_dir=qa_dir,
        raw_traces=raw_traces,
        require_decoded_frames=require_decoded_frames,
    )
    c_rel = audit_relative_motion_evidence(
        causal_graph=causal_graph,
        storyboard=storyboard,
        raw_traces=raw_traces,
        matte_manifest=matte_manifest,
        qa_dir=qa_dir,
    )
    c_ptr = audit_claim_pointer_semantics(
        editorial_timeline=editorial_timeline or {},
        causal_graph=causal_graph,
        raw_traces=raw_traces,
        matte_manifest=matte_manifest,
        qa_dir=qa_dir,
    )
    c_trans = audit_causal_transition_visibility(
        storyboard=storyboard,
        causal_graph=causal_graph,
        transition_edl=transition_edl,
        video_mp4=video_mp4,
    )
    c_comp = audit_story_silent_comprehension_proxies(
        storyboard=storyboard,
        causal_graph=causal_graph,
        claim_cov=c_claim,
        camera_intent_report=camera_intent_report,
    )

    checks = {
        "visual_claim_coverage": c_claim,
        "relative_motion_evidence": c_rel,
        "claim_pointer_semantics": c_ptr,
        "causal_transition_visibility": c_trans,
        "silent_comprehension_proxy": c_comp,
    }
    blocking_issues: List[str] = []
    advisory_warnings: List[str] = []
    blocking_warnings: List[str] = []

    for cname, chk in checks.items():
        blocking_issues.extend(chk.get("issues") or [])
        for w in chk.get("warnings") or []:
            if "blocking" in str(w).lower() or cname == "visual_claim_coverage" and "unsupported" not in str(w).lower():
                blocking_warnings.append(w)
            else:
                advisory_warnings.append(w)

    statuses = [c["status"] for c in checks.values()]
    if "FAIL" in statuses or "NOT_VERIFIED" in statuses or blocking_issues:
        overall = "FAIL"
    elif blocking_warnings:
        overall = "WARN"
    elif "WARN" in statuses or advisory_warnings:
        overall = "WARN"
    else:
        overall = "PASS"

    # Persist structured deliverables
    (run_dir / "visual_claim_coverage.json").write_text(json.dumps(c_claim, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "pointer_semantics.json").write_text(json.dumps(c_ptr, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "semantic_matte_alignment.json").write_text(
        json.dumps({"schema_version": "sd-semantic-matte-align-1", "frames": c_claim.get("matte_alignment", [])}, indent=2),
        encoding="utf-8",
    )

    gaps_csv = run_dir / "causal_evidence_gaps.csv"
    with gaps_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["causal_event_id", "shot_id", "severity", "gap_type", "detail"])
        for g in c_claim.get("gaps", []):
            w.writerow([g.get("causal_event_id"), g.get("shot_id"), g.get("severity"), g.get("gap_type"), g.get("detail")])

    if video_mp4 and Path(video_mp4).exists():
        render_event_aligned_before_action_after_strip(
            Path(video_mp4),
            c_claim.get("claims", []),
            qa_dir / "event_aligned_before_action_after.jpg",
        )
    write_qa_failure_examples(qa_dir / "qa_failures_visual_examples", video_mp4, c_claim.get("claims", []), blocking_issues)

    gates_doc = {
        "schema_version": SCHEMA_VERSION,
        "overall_status": overall,
        "subjective_visual_review": "NOT_VERIFIED",
        "viewer_retention_status": "NOT_VERIFIED",
        "blocking_issues": blocking_issues,
        "blocking_warnings": blocking_warnings,
        "advisory_warnings": advisory_warnings,
        "checks_summary": {k: v["status"] for k, v in checks.items()},
        "checks": checks,
    }
    (run_dir / "causal_gates_status.json").write_text(json.dumps(gates_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return gates_doc
