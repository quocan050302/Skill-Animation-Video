"""Deterministic Physical Motion Intent Planner & Parameter Validator (`SD-RETENTION-03` Workstream 3).

Produces referentially transparent motion parameters (`pose(t, seed, params)` with
zero accumulated state), structural torsion/collapse schedules, viscous surface wave specs,
and camera-locked deformation QA contracts.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


class PhysicalMotionSpecError(ValueError):
    """Fail closed if physical motion params contain NaNs, invalid timing, or ungrounded claims."""


def validate_motion_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate motion parameters: finite floats, positive scales, ordered failure onset."""
    errors: List[str] = []
    for k, v in params.items():
        if isinstance(v, (int, float)):
            if not math.isfinite(float(v)):
                errors.append(f"Non-finite parameter {k}={v!r}")
    dur = float(params.get("duration_sec", 3.0))
    if dur <= 0.0:
        errors.append(f"Invalid duration_sec={dur}")
    if "collapse_onset_sec" in params and "torsion_onset_sec" in params:
        co = float(params["collapse_onset_sec"])
        to = float(params["torsion_onset_sec"])
        if co < to:
            errors.append(f"N15: collapse_onset_sec ({co:.2f}s) precedes torsion_onset_sec ({to:.2f}s)")
    if "amplitude" in params and float(params["amplitude"]) < 0.0:
        errors.append(f"Negative amplitude={params['amplitude']}")
    if errors:
        raise PhysicalMotionSpecError("; ".join(errors))
    return dict(params)


def plan_motion_intent(
    shot: Dict[str, Any],
    story_event: Optional[Dict[str, Any]] = None,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compile explicit deterministic physical motion spec for WebGL primitive evaluators."""
    act = str((story_event or {}).get("physical_action") or shot.get("physical_action") or "")
    gen = str(shot.get("procedural_generator") or "")
    dur = float(shot.get("duration") or max(0.5, float(shot.get("end", 3.0)) - float(shot.get("start", 0.0))))

    if "molasses" in act or "wave" in gen:
        spec = {
            "motion_type": "continuous_viscous_surface",
            "duration_sec": dur,
            "amplitude": 0.42,
            "freq_hz": 1.35,
            "viscosity": 0.78,
            "min_vertex_disp_m": 0.14,
            "fidelity_disclosure": "stylized_illustrative",
            "seed": int(seed),
        }
    elif "torsion" in act or "twist" in gen or "girder" in gen or "tacoma_hook" in gen or "tacoma_roadway" in gen:
        is_heavy_twist = "torsion" in act or "twist" in gen or "onlooker" in gen
        is_under = "under" in gen or "girder" in gen
        spec = {
            "motion_type": "torsion_span",
            "duration_sec": dur,
            "torsion_onset_sec": 0.0,
            "vertical_amp_m": 0.22 if not is_heavy_twist else 0.16,
            "torsion_rad": 0.36 if is_heavy_twist else (0.14 if is_under else 0.10),
            "wave_mode": 2,
            "min_vertex_disp_m": 0.16 if is_heavy_twist else 0.06,
            "fidelity_disclosure": "stylized_illustrative",
            "seed": int(seed),
        }
    elif "collapse" in act or "collapse" in gen:
        spec = {
            "motion_type": "staged_span_collapse",
            "duration_sec": dur,
            "torsion_onset_sec": 0.0,
            "collapse_onset_sec": round(dur * 0.38, 3),
            "torsion_rad": 0.42,
            "gravity_mps2": 9.81,
            "min_vertex_disp_m": 0.45,
            "fidelity_disclosure": "stylized_illustrative",
            "seed": int(seed),
        }
    else:
        spec = {
            "motion_type": "damped_articulation",
            "duration_sec": dur,
            "amplitude": 0.08,
            "freq_hz": 1.2,
            "min_vertex_disp_m": 0.02,
            "fidelity_disclosure": "stylized_illustrative",
            "seed": int(seed),
        }
    return validate_motion_params(spec)


def plan_contact_schedule(
    shots: List[Dict[str, Any]],
    action_graph: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Extract normalized contact/impact timestamps per shot/narrative_event_id."""
    sched: List[Dict[str, Any]] = []
    for sh in shots:
        st = float(sh.get("start", 0.0))
        dur = float(sh.get("duration") or max(0.2, float(sh.get("end", st + 1.0)) - st))
        ca = (sh.get("staging") or {}).get("contact_action")
        act = str(sh.get("physical_action") or "")
        hit_abs = None
        if isinstance(ca, dict) and ca.get("hit_time_sec") is not None:
            hit_abs = float(ca["hit_time_sec"])
        elif "collapse" in act:
            hit_abs = round(st + dur * 0.38, 3)
        elif "twist" in act or "torsion" in act:
            hit_abs = round(st + dur * 0.28, 3)
        if hit_abs is not None:
            sched.append({
                "shot_id": sh.get("shot_id"),
                "narrative_event_id": sh.get("narrative_event_id"),
                "physical_action": act,
                "hit_time_sec": round(hit_abs, 3),
                "hit_time_rel_sec": round(hit_abs - st, 3),
            })
    return sched


def plan_physics_telemetry(
    raw_traces: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Summarize geometric deformation across rendered traces cleanly for QA."""
    max_disp = 0.0
    max_roll = 0.0
    collapse_onset_obs: Optional[float] = None
    cables_attached_all = True
    nan_detected = False

    for rec in raw_traces:
        ph = (rec.get("telemetry") or {}).get("physical_motion")
        if not isinstance(ph, dict):
            continue
        for val in (ph.get("vertex_disp_max_m"), ph.get("deck_roll_span_rad"), ph.get("collapse_drop_m")):
            if val is not None and not math.isfinite(float(val)):
                nan_detected = True
        if ph.get("vertex_disp_max_m") is not None:
            max_disp = max(max_disp, float(ph["vertex_disp_max_m"]))
        if ph.get("deck_roll_span_rad") is not None:
            max_roll = max(max_roll, float(ph["deck_roll_span_rad"]))
        if ph.get("collapse_active") and collapse_onset_obs is None:
            collapse_onset_obs = float(rec.get("time", 0.0))
        if ph.get("cables_attached") is False:
            cables_attached_all = False

    return {
        "max_vertex_disp_m": round(max_disp, 4),
        "max_deck_roll_span_rad": round(max_roll, 4),
        "collapse_onset_observed_sec": collapse_onset_obs,
        "cables_attached_all": cables_attached_all,
        "nan_detected": nan_detected,
    }
