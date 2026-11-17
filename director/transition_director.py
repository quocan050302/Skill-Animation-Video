"""STEP 3B (ZDF-MOTION-01): Motivated Transition Director & Frame-Precise Transition EDL.

Strictly separates `planned_transition` (at STEP 3 planning) from `executed_in_renderer`
and `verification_status` (verified ONLY after rendering telemetry + decoded MP4 frame audit).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


SUPPORTED_ENGINE_TRANSITIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "zach-d-films": {
        "cut": {"duration_sec": 0.0, "type": "hard_cut", "realization_kind": "hard_cut"},
        "cut_on_action": {"duration_sec": 0.0, "type": "action_matched_cut", "realization_kind": "hard_cut"},
        "dip_to_black": {"duration_sec": 0.34, "type": "fade_envelope", "realization_kind": "optical_transition"},
        "whip_pan": {"duration_sec": 0.24, "type": "webgl_two_source_whip_sweep", "realization_kind": "optical_transition"},
        "zoom_through": {"duration_sec": 0.30, "type": "webgl_two_source_portal_plunge", "realization_kind": "shot_match_bridge"},
        "match_cut": {"duration_sec": 0.24, "type": "webgl_two_source_focal_match", "realization_kind": "shot_match_bridge"},
        "object_wipe": {"duration_sec": 0.26, "type": "webgl_two_source_foreground_wipe", "realization_kind": "optical_transition"},
    },
    "stick-figure": {
        "cut": {"duration_sec": 0.0, "type": "hard_cut", "realization_kind": "hard_cut"},
        "cut_on_action": {"duration_sec": 0.0, "type": "action_matched_cut", "realization_kind": "hard_cut"},
        "whip": {"duration_sec": 0.18, "type": "canvas2d_whip_blur", "realization_kind": "optical_transition"},
        "iris_mask": {"duration_sec": 0.34, "type": "canvas2d_iris_clip", "realization_kind": "optical_transition"},
        "match_zoom": {"duration_sec": 0.24, "type": "canvas2d_zoom_plunge", "realization_kind": "optical_transition"},
        "object_wipe": {"duration_sec": 0.24, "type": "canvas2d_bar_wipe", "realization_kind": "optical_transition"},
    },
    "minimalistic-graphics": {
        "cut": {"duration_sec": 0.0, "type": "hard_cut", "realization_kind": "hard_cut"},
        "cut_on_action": {"duration_sec": 0.0, "type": "action_matched_cut", "realization_kind": "hard_cut"},
        "match_zoom": {"duration_sec": 0.26, "type": "svg_scale_morph_dissolve", "realization_kind": "optical_transition"},
    },
    "graph": {
        "cut": {"duration_sec": 0.0, "type": "hard_cut", "realization_kind": "hard_cut"},
        "cut_on_action": {"duration_sec": 0.0, "type": "action_matched_cut", "realization_kind": "hard_cut"},
        "match_zoom": {"duration_sec": 0.26, "type": "svg_viewport_zoom_ramp", "realization_kind": "optical_transition"},
    },
    "map-route": {
        "cut": {"duration_sec": 0.0, "type": "hard_cut", "realization_kind": "hard_cut"},
        "cut_on_action": {"duration_sec": 0.0, "type": "action_matched_cut", "realization_kind": "hard_cut"},
        "match_zoom": {"duration_sec": 0.26, "type": "camera_altitude_match_ease", "realization_kind": "optical_transition"},
    },
    "breakdown": {
        "cut": {"duration_sec": 0.0, "type": "hard_cut", "realization_kind": "hard_cut"},
        "cut_on_action": {"duration_sec": 0.0, "type": "action_matched_cut", "realization_kind": "hard_cut"},
        "match_zoom": {"duration_sec": 0.26, "type": "camera_viewoffset_dolly_ease", "realization_kind": "optical_transition"},
    },
}


def design_transition(
    shot_a: Dict[str, Any],
    shot_b: Dict[str, Any],
    mode: str = "motivated",
    continuity_hint: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Design the planned seam transition between `shot_a` and `shot_b` (NEVER pre-claims executed_in_renderer=True)."""
    skill = str(shot_a.get("engine") or "zach-d-films")
    supported = SUPPORTED_ENGINE_TRANSITIONS.get(skill, SUPPORTED_ENGINE_TRANSITIONS["zach-d-films"])
    requested = str(shot_a.get("transition_out") or "cut_on_action")

    if mode == "simple":
        actual = "cut_on_action" if requested not in ("cut", "dip_to_black") else requested
        degraded = None
    elif requested in supported:
        actual = requested
        degraded = None
    else:
        actual = "match_zoom" if "match_zoom" in supported else "cut_on_action"
        degraded = f"Requested transition `{requested}` unsupported in engine `{skill}`; degraded cleanly to `{actual}`."

    spec = supported.get(actual, {"duration_sec": 0.0, "type": "action_matched_cut", "realization_kind": "hard_cut"})
    strat = (continuity_hint or {}).get("continuity_strategy", "directional_flow_match")
    real_kind = spec.get("realization_kind", "hard_cut")
    if actual == "zoom_through" and (shot_a.get("scene_family") == shot_b.get("scene_family")):
        real_kind = "true_world_continuity"

    return {
        "requested_method": requested,
        "actual_method": actual,
        "renderer_mechanism": spec["type"],
        "realization_kind": real_kind,
        "duration_sec": spec["duration_sec"],
        "continuity_strategy": strat,
        "execution_status": "PLANNED",
        "executed_in_renderer": False,
        "degraded_reason": degraded,
    }


def _bridge_contract(
    shot_a: Dict[str, Any],
    shot_b: Dict[str, Any],
    path_a: Optional[Dict[str, Any]],
    path_b: Optional[Dict[str, Any]],
    tr: Dict[str, Any],
    fps: int,
) -> Dict[str, Any]:
    st_a = shot_a.get("staging") or {}
    st_b = shot_b.get("staging") or {}
    fa = (path_a or {}).get("focal_anchor") or {"anchor_id": st_a.get("visual_metaphor", "subject_a"), "world_pos": [0.0, 1.18, 0.0]}
    fb = (path_b or {}).get("focal_anchor") or {"anchor_id": st_b.get("visual_metaphor", "subject_b"), "world_pos": [0.0, 1.18, 0.0]}
    half_w = max(2, int(round((float(tr["duration_sec"]) * fps) * 0.5))) if tr["duration_sec"] > 0 else 0
    f_bound = int(round(float(shot_a["end"]) * fps))

    return {
        "from_actor": st_a.get("character_id") or st_a.get("subject", "actor_a"),
        "exit_anchor": fa,
        "exit_pose": (path_a or {}).get("keyframes", [{}])[-1].get("pos") if path_a else None,
        "exit_velocity": (path_a or {}).get("exit_vector"),
        "to_actor": st_b.get("character_id") or st_b.get("subject", "actor_b"),
        "entry_anchor": fb,
        "entry_pose": (path_b or {}).get("keyframes", [{}])[0].get("pos") if path_b else None,
        "entry_velocity": (path_b or {}).get("entry_vector"),
        "transition_window_frames": [max(0, f_bound - half_w), f_bound + half_w] if half_w > 0 else [f_bound, f_bound],
        "realization_kind": tr["realization_kind"],
    }


def emit_transition_edl(
    shots: List[Dict[str, Any]],
    camera_plan: Dict[str, Any],
    selected_skill: str,
    fps: int = 30,
    mode: str = "motivated",
    run_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Emit `<run>/transition_edl.json` with planned bridge contracts (verification happens post-render)."""
    seams = {f"{s['from_shot']}->{s['to_shot']}": s for s in camera_plan.get("seams", [])}
    paths_by_id = {p["shot_id"]: p for p in camera_plan.get("paths", [])}
    entries: List[Dict[str, Any]] = []

    for i in range(len(shots) - 1):
        sa = shots[i]
        sb = shots[i + 1]
        hint = seams.get(f"{sa['shot_id']}->{sb['shot_id']}")
        tr = design_transition(sa, sb, mode=mode, continuity_hint=hint)
        sa["transition_out"] = tr["actual_method"]
        sa["transition_meta"] = tr

        t_bound = float(sa["end"])
        f_bound = int(round(t_bound * fps))
        half_w = max(2, int(round((tr["duration_sec"] * fps) * 0.5))) if tr["duration_sec"] > 0 else 2
        bridge = _bridge_contract(sa, sb, paths_by_id.get(sa["shot_id"]), paths_by_id.get(sb["shot_id"]), tr, fps)

        entries.append({
            "transition_id": f"tr_{i:02d}",
            "from_shot": sa["shot_id"],
            "to_shot": sb["shot_id"],
            "boundary_sec": round(t_bound, 3),
            "boundary_frame": f_bound,
            "window_frames": [max(0, f_bound - half_w), f_bound + half_w],
            "requested_method": tr["requested_method"],
            "actual_method": tr["actual_method"],
            "renderer_mechanism": tr["renderer_mechanism"],
            "realization_kind": tr["realization_kind"],
            "duration_sec": tr["duration_sec"],
            "continuity_strategy": tr["continuity_strategy"],
            "bridge_contract": bridge,
            "execution_status": "PLANNED",
            "executed_in_renderer": False,
            "degraded_reason": tr["degraded_reason"],
            "verification_status": "PLANNED_UNVERIFIED",
            "sampled_alphas": [],
            "evidence_path": None,
        })

    if shots:
        shots[-1]["transition_out"] = "cut"
        shots[-1]["transition_meta"] = {
            "requested_method": "cut",
            "actual_method": "cut",
            "renderer_mechanism": "hard_cut_end",
            "realization_kind": "hard_cut",
            "duration_sec": 0.0,
            "execution_status": "PLANNED",
            "executed_in_renderer": False,
            "degraded_reason": None,
        }

    edl = {
        "schema_version": "sd-transition-edl-2",
        "selected_skill": selected_skill,
        "origin_skills": [selected_skill],
        "fps": fps,
        "transition_policy": mode,
        "transitions_count": len(entries),
        "transitions": entries,
    }
    if run_dir is not None:
        (run_dir / "transition_edl.json").write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")
    return edl


def finalize_transition_edl_verification(
    edl: Dict[str, Any],
    audit_details: List[Dict[str, Any]],
    evidence_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Update EDL execution & verification flags ONLY from post-render telemetry + decoded checks."""
    by_id = {d["transition_id"]: d for d in audit_details}
    for tr in edl.get("transitions", []):
        det = by_id.get(tr["transition_id"])
        if not det:
            tr["execution_status"] = "UNVERIFIED"
            tr["executed_in_renderer"] = False
            tr["verification_status"] = "FAIL"
            continue
        ver = str(det.get("verification_status", "FAIL"))
        tr["verification_status"] = ver
        tr["executed_in_renderer"] = (ver == "VERIFIED_DECODED")
        tr["execution_status"] = "VERIFIED" if ver == "VERIFIED_DECODED" else "FAILED_VERIFICATION"
        tr["sampled_alphas"] = det.get("sampled_alphas", [])
        tr["evidence_path"] = evidence_path
    return edl
