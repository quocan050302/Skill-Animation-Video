"""STEP 3B (SD-RETENTION-04.R1): Action-Driven Camera Intent & Information Gain Director.

Sits cleanly above `camera_choreographer.py` while keeping `camera_execution.py`
single-authority. Requires every shot to justify its framing, placement, and movement
by answering Q1-Q5 via a structured `CameraIntentContract` and maximizing real visual
information gain instead of gratuitous push-ins, spins, or dead-center subject framing.

Persists `<run>/camera_intent_report.json`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = "sd-camera-intent-report-1"


class CameraIntentError(ValueError):
    """Raised when camera selection fails Q1-Q5 justification or proof visibility rules."""


@dataclass
class CameraIntentContract:
    shot_id: str
    causal_event_id: str
    proof_type: str
    # Q1: Why does this shot exist in causal sequence?
    why_this_shot: str
    # Q2: What visible fact does the viewer learn even muted?
    what_viewer_learns: str
    # Q3: Exact physical action feature + fixed reference landmark proving motion/change
    target_causal_feature_id: str
    reference_anchor_id: str
    semantic_region_of_change: str
    # Q4: Why THIS placement/move/framing rather than dead-center or unmotivated orbit
    camera_justification_rule: str
    focal_path_rationale: str
    framing: str
    angle: str
    movement: str
    preferred_subject_uv_band: Tuple[float, float, float, float]
    # Q5: What breaks if omitted or replaced by static/centered shot?
    counterfactual_loss_if_omitted: str
    # Structured info-gain evaluation
    info_gain_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["preferred_subject_uv_band"] = list(self.preferred_subject_uv_band)
        return d


# Rule lookup mapping causal proof type -> optimal camera rule & rule-of-thirds / comparison framing band
_PROOF_CAMERA_RULES: Dict[str, Dict[str, Any]] = {
    "displacement_relative_to_fixed_reference": {
        "rule": "lock_horizon_and_offset_reference_landmark",
        "uv_band": (0.20, 0.34, 0.80, 0.72),
        "rationale": "Keep fixed reference landmark (tower/curb/plumb/lamppost) inside frame margin so subject displacement reads cleanly against static datum.",
    },
    "contact_transfer": {
        "rule": "anticipate_and_lock_contact_normal",
        "uv_band": (0.18, 0.36, 0.82, 0.72),
        "rationale": "Frame performer limb and target surface orthogonally enough for zero-gap physical contact impulse to read clearly.",
    },
    "material_deformation": {
        "rule": "oblique_silhouette_edge_accent",
        "uv_band": (0.18, 0.32, 0.84, 0.70),
        "rationale": "Hold oblique perspective on opposing edges/seams so torsion roll, curvature, or crack propagation creates strong angular contrast.",
    },
    "particle_path_propagation": {
        "rule": "track_source_to_plume_expansion_vector",
        "uv_band": (0.16, 0.30, 0.84, 0.72),
        "rationale": "Lead downstream slightly along emission/advection direction so source chimney/breach and propagating front stay legible together.",
    },
    "occlusion_visibility_change": {
        "rule": "depth_corridor_foreground_to_vanishing_landmark",
        "uv_band": (0.16, 0.30, 0.86, 0.72),
        "rationale": "Align foreground subject (lamp/bus/headlights) with recessed distant landmark along depth corridor to prove visibility drop-off.",
    },
    "pressure_flow_difference": {
        "rule": "cross_section_layered_elevation_split",
        "uv_band": (0.14, 0.28, 0.86, 0.70),
        "rationale": "Frame lower trapped medium vs upper cap layer synchronously in one cutaway elevation without cropping top inversion boundary.",
    },
    "internal_mechanism_cutaway": {
        "rule": "stepped_cutaway_entry_with_shell_context",
        "uv_band": (0.20, 0.32, 0.82, 0.70),
        "rationale": "Preserve outer casing margin while pulling cleanly to sliced interior so viewer knows exact physical location inside the machine/building.",
    },
    "human_reaction_consequence": {
        "rule": "rule_of_thirds_subject_and_hazard_line",
        "uv_band": (0.18, 0.30, 0.78, 0.72),
        "rationale": "Give character breathing lead room on safe horizon axis with hazard cue visible rather than dead-centering upper body.",
    },
    "comparative_split_reference": {
        "rule": "symmetric_dual_state_comparison_frame",
        "uv_band": (0.12, 0.30, 0.88, 0.70),
        "rationale": "Maintain balanced dual-column parallax so before/after or damped/undamped divergence stays simultaneously comparable.",
    },
    "state_change_before_after": {
        "rule": "aftermath_landscape_evidence_hold",
        "uv_band": (0.15, 0.28, 0.85, 0.72),
        "rationale": "Calm wide pullback or restrained lateral drift revealing lasting environmental transformation after mitigation/collapse.",
    },
    "context_establish": {
        "rule": "elevated_scale_establishing_sweep",
        "uv_band": (0.15, 0.28, 0.85, 0.72),
        "rationale": "Establish spatial hierarchy, period architecture, and scale anchors before closing onto micro causal mechanism.",
    },
}


def score_camera_information_gain(
    shot_candidate: Dict[str, Any],
    causal_event: Optional[Dict[str, Any]] = None,
    prev_shot: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Score genuine visual information gain of a shot/camera candidate vs centered or gimmicky motion."""
    cam = shot_candidate.get("camera") or {}
    st = shot_candidate.get("staging") or {}
    framing = str(cam.get("framing") or shot_candidate.get("framing") or "MS")
    move = str(cam.get("movement") or shot_candidate.get("movement") or "gentle_drift")
    angle = str(cam.get("angle") or shot_candidate.get("angle") or "three_quarter")
    proof = str((causal_event or {}).get("proof_type") or shot_candidate.get("proof_type") or "state_change_before_after")
    anchor_pos = list(
        st.get("salient_action_world_pos")
        or (cam.get("focus_target_world") or [0.0, 1.2, 0.0])
    )
    anchor_id = str(st.get("salient_action_anchor") or (causal_event or {}).get("feature_id") or "")

    # 1. Causal visibility gain (does framing match scale required by proof_type?)
    if proof in ("internal_mechanism_cutaway", "contact_transfer") and any(k in framing for k in ("CU", "ECU", "MCU")):
        causal_vis = 0.94
    elif proof in ("pressure_flow_difference", "comparative_split_reference", "occlusion_visibility_change", "context_establish", "state_change_before_after") and any(k in framing for k in ("WS", "VWS", "MS")):
        causal_vis = 0.92
    elif proof in ("particle_path_propagation", "material_deformation", "human_reaction_consequence"):
        causal_vis = 0.90
    else:
        causal_vis = 0.78

    # 2. Action anchoring (dedicated non-generic anchor attached to physical object)
    action_anchor_score = 0.92 if (anchor_id and anchor_id not in ("stage_center", "default")) else 0.45

    # 3. Novel evidence gain vs previous shot
    prev_fam = str((prev_shot or {}).get("scene_family") or "")
    cur_fam = str(shot_candidate.get("scene_family") or "")
    prev_act = str((prev_shot or {}).get("physical_action") or "")
    cur_act = str(shot_candidate.get("physical_action") or "")
    if not prev_shot:
        novel_gain = 0.95
    elif cur_fam != prev_fam and cur_act != prev_act:
        novel_gain = 0.94
    elif cur_act != prev_act:
        novel_gain = 0.84
    else:
        novel_gain = 0.52

    # 4. Camera motion justification (avoid gratuitous fast orbit / shake on calm/split/aftermath!)
    move_low = move.lower()
    is_calm_or_split = proof in ("comparative_split_reference", "state_change_before_after", "pressure_flow_difference")
    if is_calm_or_split and any(k in move_low for k in ("whip", "spin", "shake", "barrel")):
        cam_just = 0.32
    elif proof == "particle_path_propagation" and any(k in move_low for k in ("track", "tilt", "pan", "glide", "creep", "push", "drift")):
        cam_just = 0.92
    elif proof == "internal_mechanism_cutaway" and any(k in move_low for k in ("peel", "push", "orbit", "reveal", "arc", "glide")):
        cam_just = 0.92
    elif "static" in move_low and not st.get("intentional_hold"):
        cam_just = 0.40
    else:
        cam_just = 0.86

    # 5. Context preservation
    ctx_pres = 0.90 if ("VWS" in framing or "WS" in framing or "MS" in framing or "cutaway" in angle.lower() or "three" in angle.lower()) else 0.78

    # 6. Impact understanding
    impact_und = round(0.5 * (causal_vis + cam_just), 3)

    # 7. Subject dead-centering penalty when proof benefits from off-center lead room or reference pairing
    # Penalize pure [0, y, 0] camera offset only if neither anchor_offset nor wide reference framing exists
    cam_pos = cam.get("pos") or cam.get("eye_start") or [0.0, 1.4, 3.0]
    dead_centered_x = abs(float(anchor_pos[0])) < 0.02 and abs(float(cam_pos[0])) < 0.02 and framing in ("CU", "MS")
    center_penalty = 0.14 if (dead_centered_x and proof in ("displacement_relative_to_fixed_reference", "particle_path_propagation", "human_reaction_consequence")) else 0.0

    composite = (
        0.24 * causal_vis
        + 0.18 * action_anchor_score
        + 0.18 * novel_gain
        + 0.18 * cam_just
        + 0.12 * ctx_pres
        + 0.10 * impact_und
        - center_penalty
    )
    planned_score = round(max(0.0, min(1.0, composite)), 3)
    return {
        "causal_visibility_gain": round(causal_vis, 3),
        "action_anchoring": round(action_anchor_score, 3),
        "novel_evidence_gain": round(novel_gain, 3),
        "camera_motion_justification": round(cam_just, 3),
        "context_preservation": round(ctx_pres, 3),
        "impact_understanding": round(impact_und, 3),
        "subject_centering_penalty": round(center_penalty, 3),
        "planned_camera_info_gain": planned_score,
        "total_info_gain_score": planned_score,
        "is_planning_heuristic": True,
        "metric_authority": "PLANNING_HEURISTIC_NOT_DECODED_PROOF",
    }


def select_camera_intent(
    candidates: List[Dict[str, Any]],
    causal_event: Optional[Dict[str, Any]] = None,
    prev_shot: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    """Select the shot/camera candidate maximizing total information gain for the causal event."""
    if not candidates:
        raise CameraIntentError("No camera/shot candidates supplied to select_camera_intent")
    scored: List[Tuple[float, int, Dict[str, Any], Dict[str, float]]] = []
    for idx, cand in enumerate(candidates):
        metrics = score_camera_information_gain(cand, causal_event=causal_event, prev_shot=prev_shot)
        scored.append((metrics["total_info_gain_score"], -idx, cand, metrics))
    scored.sort(reverse=True)
    _, _, best, best_metrics = scored[0]
    return best, best_metrics


def _extract_keyframe_target(kf: Dict[str, Any], default: List[float]) -> List[float]:
    if not isinstance(kf, dict):
        return list(default)
    for key in ("look", "target", "pos"):
        val = kf.get(key)
        if isinstance(val, (list, tuple)) and len(val) >= 2:
            coords = [float(v) for v in val[:3]]
            if len(coords) == 2:
                coords.append(0.0)
            return coords
    if "x" in kf and "y" in kf:
        return [float(kf["x"]), float(kf["y"]), float(kf.get("z", 1.0))]
    if "dx" in kf and "y" in kf:
        return [float(kf["dx"]), float(kf["y"]), float(kf.get("dz", 0.0))]
    if "pan_x" in kf and "pan_y" in kf:
        return [float(kf["pan_x"]), float(kf["pan_y"]), float(kf.get("zoom", 1.0))]
    return list(default)


def resolve_causal_focal_path(
    shot: Dict[str, Any],
    causal_event: Optional[Dict[str, Any]] = None,
    camera_path: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ensure focal anchor world coordinates & vertical framing keep causal zone clear of UI bands."""
    st = shot.get("staging") or {}
    proof = str((causal_event or {}).get("proof_type") or "state_change_before_after")
    rule_spec = _PROOF_CAMERA_RULES.get(proof, _PROOF_CAMERA_RULES["state_change_before_after"])
    kfs = list((camera_path or shot.get("camera_path") or {}).get("keyframes") or [])
    default_look = list(st.get("salient_action_world_pos") or [0.0, 1.2, 0.0])
    look_start = _extract_keyframe_target(kfs[0], default_look) if kfs else default_look
    look_end = _extract_keyframe_target(kfs[-1], look_start) if kfs else list(look_start)

    return {
        "proof_type": proof,
        "camera_justification_rule": rule_spec["rule"],
        "preferred_subject_uv_band": list(rule_spec["uv_band"]),
        "look_start_world": [round(float(v), 3) for v in look_start],
        "look_end_world": [round(float(v), 3) for v in look_end],
        "reference_entity_id": str((causal_event or {}).get("reference_entity_id") or "fixed_world_reference"),
        "target_causal_feature_id": str(
            (causal_event or {}).get("feature_id")
            or st.get("salient_action_anchor")
            or shot.get("shot_id")
        ),
    }


def build_camera_intent_contract(
    shot: Dict[str, Any],
    causal_event: Optional[Dict[str, Any]] = None,
    evidence_contract: Optional[Dict[str, Any]] = None,
    prev_shot: Optional[Dict[str, Any]] = None,
) -> CameraIntentContract:
    """Compile explicit Q1-Q5 `CameraIntentContract` for one shot without mutating camera solver authority."""
    cam = shot.get("camera") or {}
    st = shot.get("staging") or {}
    proof = str((causal_event or {}).get("proof_type") or "state_change_before_after")
    rule_spec = _PROOF_CAMERA_RULES.get(proof, _PROOF_CAMERA_RULES["state_change_before_after"])
    info_gain = score_camera_information_gain(shot, causal_event=causal_event, prev_shot=prev_shot)

    feat_id = str(
        (causal_event or {}).get("feature_id")
        or st.get("salient_action_anchor")
        or f"{shot.get('shot_id')}_feature"
    )
    ref_id = str((causal_event or {}).get("reference_entity_id") or "fixed_world_reference")
    reg_id = str((causal_event or {}).get("semantic_region_of_change") or "primary_causal_zone")
    act_name = str(shot.get("physical_action") or (causal_event or {}).get("physical_action") or "state_shift")
    nar_txt = str(shot.get("narration_text") or (causal_event or {}).get("clause_text") or "").strip()

    why_shot = (
        f"Demonstrates '{act_name}' via proof '{proof}' tying '{(causal_event or {}).get('cause_entity_id', 'cause')}' "
        f"-> '{(causal_event or {}).get('effect_entity_id', 'effect')}'."
    )
    what_learns = (
        f"Viewer visually observes '{feat_id}' relative to '{ref_id}'"
        + (f" matching claim: {nar_txt[:96]}" if nar_txt else ".")
    )
    cf_loss = str(
        ((evidence_contract or {}).get("counterfactual_failure") or {}).get("omitted_proof_reason")
        or f"Omitting or de-anchoring '{feat_id}' leaves causal step '{act_name}' unverified visually."
    )

    return CameraIntentContract(
        shot_id=str(shot.get("shot_id")),
        causal_event_id=str((causal_event or {}).get("causal_event_id") or shot.get("narrative_event_id") or shot.get("shot_id")),
        proof_type=proof,
        why_this_shot=why_shot,
        what_viewer_learns=what_learns,
        target_causal_feature_id=feat_id,
        reference_anchor_id=ref_id,
        semantic_region_of_change=reg_id,
        camera_justification_rule=rule_spec["rule"],
        focal_path_rationale=rule_spec["rationale"],
        framing=str(cam.get("framing") or "MS"),
        angle=str(cam.get("angle") or "three_quarter"),
        movement=str(cam.get("movement") or "gentle_drift"),
        preferred_subject_uv_band=tuple(rule_spec["uv_band"]),
        counterfactual_loss_if_omitted=cf_loss,
        info_gain_metrics=info_gain,
    )


def validate_camera_proof_visibility(
    contracts: List[Dict[str, Any]],
    storyboard: Dict[str, Any],
) -> Dict[str, Any]:
    """Verify Q1-Q5 completeness, non-generic targeting, and non-gimmicky info gain across all shots."""
    shots = list(storyboard.get("shots") or [])
    by_sid = {str(c.get("shot_id")): c for c in contracts}
    issues: List[str] = []
    warnings: List[str] = []

    for sh in shots:
        sid = str(sh.get("shot_id"))
        c = by_sid.get(sid)
        if not c:
            issues.append(f"Shot {sid} missing CameraIntentContract")
            continue
        for req_q in (
            "why_this_shot",
            "what_viewer_learns",
            "target_causal_feature_id",
            "camera_justification_rule",
            "counterfactual_loss_if_omitted",
        ):
            if not str(c.get(req_q) or "").strip():
                issues.append(f"Shot {sid} CameraIntentContract missing required field '{req_q}'")
        if str(c.get("target_causal_feature_id") or "") in ("stage_center", "default"):
            issues.append(f"Shot {sid} targets generic anchor '{c.get('target_causal_feature_id')}'")
        ig = c.get("info_gain_metrics") or {}
        if float(ig.get("camera_motion_justification") or 0.0) < 0.45:
            issues.append(
                f"Shot {sid} unmotivated camera gimmick (motion_justification={ig.get('camera_motion_justification')})"
            )
        if float(ig.get("total_info_gain_score") or 0.0) < 0.65:
            warnings.append(
                f"Shot {sid} modest camera information gain ({ig.get('total_info_gain_score')})"
            )

    status = "FAIL" if issues else ("WARN" if warnings else "PASS")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "shots_checked": len(shots),
        "issues": issues,
        "warnings": warnings,
    }


def plan_action_driven_camera(
    storyboard: Dict[str, Any],
    causal_graph: Optional[Dict[str, Any]] = None,
    evidence_contracts: Optional[Dict[str, Any]] = None,
    camera_plan: Optional[Dict[str, Any]] = None,
    run_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Attach `CameraIntentContract` + Q1-Q5 info gain to every shot and persist `camera_intent_report.json`."""
    shots = list(storyboard.get("shots") or [])
    cev_by_nev = {
        str(ev.get("narrative_event_id") or ""): ev
        for ev in (causal_graph or {}).get("causal_events", [])
    }
    vec_by_cevid = dict((evidence_contracts or {}).get("by_event_id") or {})
    paths_by_sid = {
        str(p.get("shot_id")): p for p in ((camera_plan or {}).get("paths") or [])
    }

    contracts_out: List[Dict[str, Any]] = []
    for idx, sh in enumerate(shots):
        nev_id = str(sh.get("narrative_event_id") or f"nev_{idx:03d}")
        cev = cev_by_nev.get(nev_id)
        vec = vec_by_cevid.get(str(cev.get("causal_event_id"))) if cev else None
        prev_sh = shots[idx - 1] if idx > 0 else None

        contract = build_camera_intent_contract(
            sh,
            causal_event=cev,
            evidence_contract=vec,
            prev_shot=prev_sh,
        )
        cdict = contract.to_dict()
        cdict["focal_path_resolved"] = resolve_causal_focal_path(
            sh,
            causal_event=cev,
            camera_path=paths_by_sid.get(str(sh.get("shot_id"))),
        )
        sh["camera_intent"] = cdict
        if cev:
            sh["causal_event_id"] = cev.get("causal_event_id")
            sh["proof_type"] = cev.get("proof_type")
            sh["semantic_region_of_change"] = cev.get("semantic_region_of_change")
        contracts_out.append(cdict)

    val = validate_camera_proof_visibility(contracts_out, storyboard)
    mean_gain = (
        round(sum(float(c["info_gain_metrics"]["total_info_gain_score"]) for c in contracts_out) / len(contracts_out), 3)
        if contracts_out
        else 0.0
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": val["status"],
        "shots_count": len(contracts_out),
        "planned_camera_info_gain": mean_gain,
        "is_planning_heuristic": True,
        "metric_authority": "PLANNING_HEURISTIC_NOT_DECODED_PROOF",
        "mean_info_gain_score": mean_gain,
        "validation": val,
        "contracts": contracts_out,
    }
    if run_dir is not None:
        (run_dir / "camera_intent_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return report
