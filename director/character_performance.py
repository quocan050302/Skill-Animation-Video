"""Grounded Character Performance Planner & Biomechanical Validator (`SD-RETENTION-03` Workstream 4).

Maps narrative beats and threat direction into structured physical performance plans
(`notice`, `look_at`, `brace`, `take_step`, `retreat`, `run`, `reach`, `stumble`, `recover`,
`point`, `inspect`, `help`) and fails closed on foot sliding, ground penetration,
heading errors against threats, or teleporting roots.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


class CharacterGroundingError(ValueError):
    """Fail closed if character feet penetrate ground, slide excessively, or move into threat."""


SUPPORTED_ACTIONS = {
    "notice", "look_at", "brace", "take_step", "retreat", "run",
    "reach", "stumble", "recover", "point", "inspect", "help",
}


def plan_character_action(
    beat: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    threat_vector: Optional[List[float]] = None,
    obstacles: Optional[List[Dict[str, Any]]] = None,
    ground_y: float = 0.0,
) -> Dict[str, Any]:
    """Derive grounded multi-phase character performance parameters from story action context."""
    act = str(beat.get("physical_action") or "").lower()
    text = str(beat.get("narration_text") or "").lower()
    dur = float(beat.get("duration_sec") or beat.get("duration") or 3.5)
    role = str((context or {}).get("role") or "onlooker")
    threat = list(threat_vector or [0.0, 1.4, -4.5])

    if "retreat" in act or "wave" in act or "speed" in act or "outran" in text or "sweep" in act:
        intent = "retreat"
        phases = ["notice", "take_step", "retreat", "run"]
        retreat_dist = 2.15
    elif "react" in act or "onlooker" in role or "shore" in act:
        intent = "brace"
        phases = ["look_at", "notice", "take_step", "brace"]
        retreat_dist = 0.65
    elif "inspect" in act or "seep" in act or "leak" in act:
        intent = "inspect"
        phases = ["inspect", "notice", "take_step", "brace"]
        retreat_dist = 0.35
    elif "rescue" in act or "aftermath" in act or "help" in act:
        intent = "help"
        phases = ["look_at", "point", "help"]
        retreat_dist = 0.0
    elif "street" in act:
        intent = "take_step"
        phases = ["take_step", "notice", "look_at"]
        retreat_dist = 0.55
    else:
        intent = "look_at"
        phases = ["look_at", "brace"]
        retreat_dist = 0.20

    return {
        "schema_version": "sd-char-perf-1",
        "primary_intent": intent,
        "phases": phases,
        "duration_sec": round(dur, 3),
        "ground_y": float(ground_y),
        "threat_world": [float(v) for v in threat],
        "retreat_distance_m": retreat_dist,
        "reaction_onset_sec": round(min(0.45, dur * 0.14), 3),
        "step_cadence_hz": 1.85 if intent == "retreat" else 1.25,
    }


def validate_character_grounding(
    telemetry_samples: List[Dict[str, Any]],
    max_slide_m: float = 0.08,
    max_penetration_m: float = 0.03,
    max_speed_mps: float = 6.5,
    require_motion: bool = True,
) -> Dict[str, Any]:
    """Audit foot-ground contact, stance slide, threat-away retreat heading, and root continuity."""
    if not telemetry_samples:
        return {"status": "PASS", "checked_samples": 0, "note": "No character telemetry present."}

    issues: List[str] = []
    worst_pen = 0.0
    worst_slide = 0.0
    max_spd = 0.0
    min_pelvis_y = 99.0
    pelvis_xs: List[float] = []
    pelvis_zs: List[float] = []

    prev_t: Optional[float] = None
    prev_root: Optional[List[float]] = None
    prev_shot_id: Optional[str] = None
    by_shot_xz: Dict[str, List[Tuple[float, float, str]]] = {}

    for rec in telemetry_samples:
        t = float(rec.get("time_sec", rec.get("time", 0.0)))
        sid = str(rec.get("shot_id") or ((rec.get("telemetry") or {}).get("shot_id")) or "_single")
        if prev_shot_id is not None and sid != prev_shot_id:
            # Separate scene/shot cut resets cross-shot root delta check
            prev_root = None
            prev_t = None
        prev_shot_id = sid
        cp = (rec.get("telemetry") or {}).get("character_performance") if "telemetry" in rec else rec
        if not isinstance(cp, dict):
            continue

        for foot_k in ("left_foot_ground_err_m", "right_foot_ground_err_m"):
            val = cp.get(foot_k)
            if val is not None and not math.isfinite(float(val)):
                issues.append(f"Non-finite character foot telemetry {foot_k} at t={t:.2f}s")
            elif val is not None:
                # Negative error or sole_y below ground indicates floor penetration
                pen = max(0.0, -float(val))
                worst_pen = max(worst_pen, pen)
                if pen > max_penetration_m:
                    issues.append(
                        f"N18: Character {foot_k}={float(val):.4f}m penetrates floor by {pen:.4f}m > {max_penetration_m:.3f}m at t={t:.2f}s"
                    )

        slide = cp.get("stance_slide_m")
        if slide is not None:
            sl_val = float(slide)
            worst_slide = max(worst_slide, sl_val)
            if sl_val > max_slide_m:
                issues.append(
                    f"N17: Character stance foot sliding {sl_val:.4f}m > {max_slide_m:.3f}m at t={t:.2f}s"
                )

        root = cp.get("world_pelvis")
        intent = str(cp.get("action_intent") or "")
        if isinstance(root, list) and len(root) == 3:
            pelvis_xs.append(float(root[0]))
            pelvis_zs.append(float(root[2]))
            by_shot_xz.setdefault(sid, []).append((float(root[0]), float(root[2]), intent))
            min_pelvis_y = min(min_pelvis_y, float(root[1]))
            if prev_root is not None and prev_t is not None and t > prev_t + 1e-4:
                dt = t - prev_t
                dist = math.sqrt(sum((float(root[k]) - float(prev_root[k])) ** 2 for k in range(3)))
                spd = dist / dt
                max_spd = max(max_spd, spd)
                if spd > max_speed_mps:
                    issues.append(
                        f"N18: Character root teleport / spike velocity {spd:.2f}m/s > {max_speed_mps:.1f}m/s at t={t:.2f}s"
                    )
            prev_root = [float(x) for x in root]
            prev_t = t

        move_dot_threat = cp.get("move_toward_threat_dot")
        if intent == "retreat" and move_dot_threat is not None and float(move_dot_threat) > 0.35:
            issues.append(
                f"N19: Retreat character moving toward threat (dot={float(move_dot_threat):.3f}) at t={t:.2f}s"
            )

    if require_motion:
        for sid, pts in by_shot_xz.items():
            if len(pts) >= 2 and any(it == "retreat" for _, _, it in pts):
                xs = [p[0] for p in pts]
                zs = [p[1] for p in pts]
                span = math.hypot(max(xs) - min(xs), max(zs) - min(zs))
                if span < 0.15:
                    issues.append(f"Character in shot {sid} claimed retreat motion but displacement span was only {span:.3f}m")

    return {
        "status": "FAIL" if issues else "PASS",
        "checked_samples": len(telemetry_samples),
        "worst_penetration_m": round(worst_pen, 4),
        "worst_stance_slide_m": round(worst_slide, 4),
        "max_root_speed_mps": round(max_spd, 3),
        "issues": issues,
    }
