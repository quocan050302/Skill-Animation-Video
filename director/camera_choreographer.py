"""STEP 3A (SD-VISUAL-01): Continuous Seeded Camera Path Choreographer & Continuity Matcher.

All camera paths are pure deterministic functions `f(local_t / dur)` within locked engine bounds
(zero wall-clock jitter, matching across serial and parallel workers).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_SCENE_BOUNDS: Dict[str, Any] = {
    "x_min": -3.5, "x_max": 3.5,
    "y_min": 0.12, "y_max": 4.2,
    "z_min": -4.0, "z_max": 5.2,
}


def _sign_x(placement: str, idx: int) -> float:
    low = (placement or "").lower()
    if "left" in low:
        return -1.0
    if "right" in low:
        return 1.0
    return -1.0 if (idx % 2 == 0) else 1.0


def plan_camera_path(
    shot: Dict[str, Any],
    scene_bounds: Optional[Dict[str, Any]],
    selected_skill: str,
    fps: int = 30,
    seed: int = 42,
) -> Dict[str, Any]:
    """Return engine-specific deterministic camera/viewport keyframes for one shot."""
    bounds = scene_bounds or DEFAULT_SCENE_BOUNDS
    idx = int(shot.get("index", 0))
    st = float(shot.get("start", 0.0))
    en = float(shot.get("end", st + 1.0))
    dur = max(0.2, round(en - st, 3))
    cam_meta = shot.get("camera") or {}
    staging = shot.get("staging") or {}
    setup = str(shot.get("setup_type") or "")
    move = str(cam_meta.get("movement") or "dolly_push_in")
    focal = int(cam_meta.get("focal_length_mm") or 35)
    placement = str(staging.get("subject_placement") or "center")
    sx = _sign_x(placement, idx)
    # Deterministic minor spatial offset seeded per shot so repeated angles don't share identical coordinates
    seed_off = (((seed + idx * 71) % 19) - 9) * 0.014

    if selected_skill == "zach-d-films":
        fov = 26 if focal >= 65 else (30 if focal >= 45 else (34 if focal >= 30 else 40))
        if move in ("macro_push_in", "focus_push_to_organ", "slowmo_track_impact", "push_toward_core"):
            keyframes = [
                {"t_norm": 0.0, "pos": [round(0.45 * sx + seed_off, 3), 1.38, 1.85], "look": [0.0, 1.15, 0.06], "fov": fov + 4, "roll": round(-0.02 * sx, 3)},
                {"t_norm": 0.55, "pos": [round(0.24 * sx, 3), 1.28, 1.34], "look": [0.0, 1.18, 0.08], "fov": fov + 1, "roll": 0.0},
                {"t_norm": 1.0, "pos": [round(0.12 * sx - seed_off, 3), 1.22, 1.02], "look": [0.0, 1.20, 0.10], "fov": fov - 2, "roll": round(0.015 * sx, 3)},
            ]
        elif move in ("peel_orbit_reveal", "arc_around_rotor", "orbit_right"):
            ang0 = 0.35 * sx
            ang1 = ang0 + 0.72 * sx
            r0, r1 = 1.95, 1.55
            keyframes = [
                {"t_norm": 0.0, "pos": [round(math.sin(ang0) * r0, 3), 1.58, round(math.cos(ang0) * r0, 3)], "look": [0.0, 1.16, 0.0], "fov": fov, "roll": 0.0},
                {"t_norm": 0.5, "pos": [round(math.sin((ang0 + ang1) * 0.5) * ((r0 + r1) * 0.5), 3), 1.48, round(math.cos((ang0 + ang1) * 0.5) * ((r0 + r1) * 0.5), 3)], "look": [0.0, 1.18, 0.0], "fov": fov, "roll": 0.01 * sx},
                {"t_norm": 1.0, "pos": [round(math.sin(ang1) * r1, 3), 1.36, round(math.cos(ang1) * r1, 3)], "look": [0.0, 1.20, 0.0], "fov": fov - 1, "roll": 0.0},
            ]
        elif move in ("crane_tilt_follow", "scale_pullback_cosmos", "pull_back_crane"):
            keyframes = [
                {"t_norm": 0.0, "pos": [round(-0.35 * sx + seed_off, 3), 0.92, 1.55], "look": [0.0, 1.25, 0.0], "fov": fov, "roll": -0.01 * sx},
                {"t_norm": 0.5, "pos": [round(0.05 * sx, 3), 1.55, 2.35], "look": [0.0, 1.32, 0.0], "fov": fov + 4, "roll": 0.0},
                {"t_norm": 1.0, "pos": [round(0.32 * sx, 3), 2.15, 3.25], "look": [0.0, 1.18, -0.15], "fov": fov + 7, "roll": 0.0},
            ]
        else:
            # Dolly tracking along conduit / datacenter / corridor
            keyframes = [
                {"t_norm": 0.0, "pos": [round(-0.62 * sx, 3), 1.46, 2.65], "look": [0.0, 1.18, -0.35], "fov": fov, "roll": round(-0.012 * sx, 3)},
                {"t_norm": 0.5, "pos": [round(0.0 + seed_off, 3), 1.36, 1.95], "look": [0.0, 1.18, -0.25], "fov": fov, "roll": 0.0},
                {"t_norm": 1.0, "pos": [round(0.42 * sx, 3), 1.28, 1.28], "look": [0.0, 1.18, -0.15], "fov": fov - 2, "roll": round(0.012 * sx, 3)},
            ]
        return {
            "shot_id": shot["shot_id"],
            "engine": selected_skill,
            "path_family": move,
            "space": "world_3d",
            "entry_vector": [round(keyframes[1]["pos"][k] - keyframes[0]["pos"][k], 3) for k in range(3)],
            "exit_vector": [round(keyframes[-1]["pos"][k] - keyframes[1]["pos"][k], 3) for k in range(3)],
            "bounds": bounds,
            "keyframes": keyframes,
        }

    if selected_skill == "stick-figure":
        z0 = 1.02 if "push" in move or "zoom" in move else (1.14 if "pull" in move else 1.0)
        z1 = 1.16 if "push" in move or "zoom" in move else (0.98 if "pull" in move else 1.06)
        keyframes = [
            {"t_norm": 0.0, "x": round(540 - 65 * sx, 1), "y": 950, "z": z0, "r": round(-0.018 * sx, 4)},
            {"t_norm": 1.0, "x": round(540 + 55 * sx, 1), "y": 935 if "climb" not in move else 870, "z": z1, "r": 0.0},
        ]
        return {
            "shot_id": shot["shot_id"],
            "engine": selected_skill,
            "path_family": move,
            "space": "canvas_2d",
            "entry_vector": [round(65 * sx, 1), -10.0, round(z1 - z0, 3)],
            "exit_vector": [round(65 * sx, 1), -10.0, round(z1 - z0, 3)],
            "keyframes": keyframes,
        }

    if selected_skill == "map-route":
        elev0 = 18.0 if "street" in setup else (26.0 if "bridge" in setup else 28.0)
        elev1 = elev0 + (26.0 if "pullback" in move or "altitude" in move else 3.5)
        keyframes = [
            {"t_norm": 0.0, "dx": round(14.0 * sx, 2), "y": elev0, "dz": 20.0},
            {"t_norm": 1.0, "dx": round(16.0 * -sx, 2), "y": elev1, "dz": 24.0 if "pullback" in move else 16.0},
        ]
        return {
            "shot_id": shot["shot_id"],
            "engine": selected_skill,
            "path_family": move,
            "space": "schematic_3d_offset",
            "entry_vector": [round(-2.0 * sx, 2), round(elev1 - elev0, 2), -2.0],
            "exit_vector": [round(-2.0 * sx, 2), round(elev1 - elev0, 2), -2.0],
            "keyframes": keyframes,
        }

    if selected_skill == "breakdown":
        keyframes = [
            {"t_norm": 0.0, "pos": [round(5.5 * sx, 2), 9.0 if "macro" not in setup else 1.4, 24.0 if "macro" not in setup else 14.5], "view_offset_x": 0 if "callout" not in setup else 145},
            {"t_norm": 1.0, "pos": [round(6.5 * sx, 2), 10.5 if "macro" not in setup else 0.9, 30.0 if "macro" not in setup else 11.8], "view_offset_x": 145 if "separation" in setup or "callout" in setup else 0},
        ]
        return {
            "shot_id": shot["shot_id"],
            "engine": selected_skill,
            "path_family": move,
            "space": "studio_3d_orbit",
            "entry_vector": [round(1.0 * sx, 2), 0.5, -2.0],
            "exit_vector": [round(1.0 * sx, 2), 0.5, -2.0],
            "keyframes": keyframes,
        }

    # `graph` and `minimalistic-graphics` orthographic viewport path
    z_start = 1.30 if "zoom" in move or "tip" in move else (1.16 if "inflection" in setup else 1.0)
    z_end = 1.0 if "horizon" in setup or "settle" in move else min(1.36, z_start + 0.06)
    return {
        "shot_id": shot["shot_id"],
        "engine": selected_skill,
        "path_family": move,
        "space": "svg_2d_viewport",
        "entry_vector": [round(25.0 * sx, 1), 0.0, round(z_end - z_start, 3)],
        "exit_vector": [round(25.0 * sx, 1), 0.0, round(z_end - z_start, 3)],
        "keyframes": [
            {"t_norm": 0.0, "zoom": z_start, "pan_x": 0.0, "pan_y": 0.0},
            {"t_norm": 1.0, "zoom": z_end, "pan_x": round(24.0 * sx, 1), "pan_y": -18.0},
        ],
    }


def plan_camera_continuity(
    shot_a: Dict[str, Any],
    shot_b: Dict[str, Any],
    path_a: Dict[str, Any],
    path_b: Dict[str, Any],
    event_graph: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate motion direction, semantic/scale jump, and continuity strategy between shots."""
    same_family = shot_a.get("scene_family") == shot_b.get("scene_family")
    same_scale = shot_a.get("scale_level") == shot_b.get("scale_level")

    va = path_a.get("exit_vector", [0.0, 0.0, -1.0])
    vb = path_b.get("entry_vector", [0.0, 0.0, -1.0])
    na = math.sqrt(sum(float(x) * float(x) for x in va)) or 1.0
    nb = math.sqrt(sum(float(x) * float(x) for x in vb)) or 1.0
    dot = sum((float(va[k]) / na) * (float(vb[k]) / nb) for k in range(min(3, len(va), len(vb))))
    angle_deg = round(math.degrees(math.acos(max(-1.0, min(1.0, dot)))), 2)

    if not same_scale:
        strategy = "scale_bridge_portal"
        honesty_note = (
            f"Discrete scene/scale jump ({shot_a.get('scale_level')} -> {shot_b.get('scale_level')}); "
            "linked via motivated zoom-through/match bridge, NOT claimed as single literal 3D geography."
        )
    elif angle_deg <= 65.0:
        strategy = "directional_flow_match"
        honesty_note = "Exit and entry camera trajectories align within 65 deg screen/3D sector."
    else:
        strategy = "motivated_counter_cut"
        honesty_note = "Intentional angular opposition for contrast/action cut without disorienting jump."

    return {
        "from_shot": shot_a["shot_id"],
        "to_shot": shot_b["shot_id"],
        "same_scene_family": same_family,
        "same_scale": same_scale,
        "motion_vector_angle_deg": angle_deg,
        "continuity_strategy": strategy,
        "disclosure_note": honesty_note,
    }


def build_camera_plan(
    shots: List[Dict[str, Any]],
    selected_skill: str,
    fps: int = 30,
    seed: int = 42,
    event_graph: Optional[Dict[str, Any]] = None,
    run_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build full `<run>/camera_paths.json` tracing every shot's camera path & seams."""
    paths = [
        plan_camera_path(s, DEFAULT_SCENE_BOUNDS, selected_skill=selected_skill, fps=fps, seed=seed)
        for s in shots
    ]
    seams = [
        plan_camera_continuity(shots[i], shots[i + 1], paths[i], paths[i + 1], event_graph=event_graph)
        for i in range(max(0, len(shots) - 1))
    ]
    doc: Dict[str, Any] = {
        "schema_version": "sd-camera-paths-1",
        "selected_skill": selected_skill,
        "origin_skills": [selected_skill],
        "fps": fps,
        "seed": seed,
        "paths": paths,
        "seams": seams,
    }
    if run_dir is not None:
        (run_dir / "camera_paths.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc
