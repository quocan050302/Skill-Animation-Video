"""STEP 3B (SD-VISUAL-01): Motivated Transition Director & Frame-Precise Transition EDL.

Ensures every planned `transition_out` maps honestly to an actual rendered transition mechanism
inside the locked visual engine (`executed_in_renderer=True`) or degrades cleanly with an explicit audit note.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


SUPPORTED_ENGINE_TRANSITIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "zach-d-films": {
        "cut": {"duration_sec": 0.0, "type": "hard_cut"},
        "cut_on_action": {"duration_sec": 0.0, "type": "action_matched_cut"},
        "dip_to_black": {"duration_sec": 0.34, "type": "fade_envelope"},
        "whip_pan": {"duration_sec": 0.22, "type": "webgl_camera_whip_sweep"},
        "zoom_through": {"duration_sec": 0.28, "type": "webgl_fov_portal_plunge"},
        "match_cut": {"duration_sec": 0.20, "type": "scale_focal_align_blend"},
        "object_wipe": {"duration_sec": 0.24, "type": "foreground_silhouette_wipe"},
    },
    "stick-figure": {
        "cut": {"duration_sec": 0.0, "type": "hard_cut"},
        "cut_on_action": {"duration_sec": 0.0, "type": "action_matched_cut"},
        "whip": {"duration_sec": 0.18, "type": "canvas2d_whip_blur"},
        "iris_mask": {"duration_sec": 0.34, "type": "canvas2d_iris_clip"},
        "match_zoom": {"duration_sec": 0.24, "type": "canvas2d_zoom_plunge"},
        "object_wipe": {"duration_sec": 0.24, "type": "canvas2d_bar_wipe"},
    },
    "minimalistic-graphics": {
        "cut": {"duration_sec": 0.0, "type": "hard_cut"},
        "cut_on_action": {"duration_sec": 0.0, "type": "action_matched_cut"},
        "match_zoom": {"duration_sec": 0.26, "type": "svg_scale_morph_dissolve"},
    },
    "graph": {
        "cut": {"duration_sec": 0.0, "type": "hard_cut"},
        "cut_on_action": {"duration_sec": 0.0, "type": "action_matched_cut"},
        "match_zoom": {"duration_sec": 0.26, "type": "svg_viewport_zoom_ramp"},
    },
    "map-route": {
        "cut": {"duration_sec": 0.0, "type": "hard_cut"},
        "cut_on_action": {"duration_sec": 0.0, "type": "action_matched_cut"},
        "match_zoom": {"duration_sec": 0.26, "type": "camera_altitude_match_ease"},
    },
    "breakdown": {
        "cut": {"duration_sec": 0.0, "type": "hard_cut"},
        "cut_on_action": {"duration_sec": 0.0, "type": "action_matched_cut"},
        "match_zoom": {"duration_sec": 0.26, "type": "camera_viewoffset_dolly_ease"},
    },
}


def design_transition(
    shot_a: Dict[str, Any],
    shot_b: Dict[str, Any],
    mode: str = "motivated",
    continuity_hint: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Design or validate the seam transition between `shot_a` and `shot_b` cleanly inside one skill."""
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
        # Never invent or import a foreign skill wipe; fall back honestly inside locked engine
        actual = "match_zoom" if "match_zoom" in supported else "cut_on_action"
        degraded = f"Requested transition `{requested}` unsupported in engine `{skill}`; degraded cleanly to `{actual}`."

    spec = supported.get(actual, {"duration_sec": 0.0, "type": "action_matched_cut"})
    strat = (continuity_hint or {}).get("continuity_strategy", "directional_flow_match")
    return {
        "requested_method": requested,
        "actual_method": actual,
        "renderer_mechanism": spec["type"],
        "duration_sec": spec["duration_sec"],
        "continuity_strategy": strat,
        "executed_in_renderer": True,
        "degraded_reason": degraded,
    }


def emit_transition_edl(
    shots: List[Dict[str, Any]],
    camera_plan: Dict[str, Any],
    selected_skill: str,
    fps: int = 30,
    mode: str = "motivated",
    run_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Emit `<run>/transition_edl.json` and sync each shot's `transition_out` to actual rendered method."""
    seams = {f"{s['from_shot']}->{s['to_shot']}": s for s in camera_plan.get("seams", [])}
    entries: List[Dict[str, Any]] = []

    for i in range(len(shots) - 1):
        sa = shots[i]
        sb = shots[i + 1]
        hint = seams.get(f"{sa['shot_id']}->{sb['shot_id']}")
        tr = design_transition(sa, sb, mode=mode, continuity_hint=hint)
        # Keep shot spec strictly in sync with what renderer will actually execute (no metadata-only lies!)
        sa["transition_out"] = tr["actual_method"]
        sa["transition_meta"] = tr

        t_bound = float(sa["end"])
        f_bound = int(round(t_bound * fps))
        half_w = max(2, int(round((tr["duration_sec"] * fps) * 0.5))) if tr["duration_sec"] > 0 else 2
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
            "duration_sec": tr["duration_sec"],
            "continuity_strategy": tr["continuity_strategy"],
            "executed_in_renderer": tr["executed_in_renderer"],
            "degraded_reason": tr["degraded_reason"],
            "verification_status": "PENDING_DECODED_CHECK",
        })

    if shots:
        shots[-1]["transition_out"] = "cut"
        shots[-1]["transition_meta"] = {
            "requested_method": "cut",
            "actual_method": "cut",
            "renderer_mechanism": "hard_cut_end",
            "duration_sec": 0.0,
            "executed_in_renderer": True,
            "degraded_reason": None,
        }

    edl = {
        "schema_version": "sd-transition-edl-1",
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
