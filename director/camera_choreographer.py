"""STEP 3A (ZDF-MOTION-01): Continuous Seeded Camera Path Choreographer & Continuity Matcher.

All camera paths are pure deterministic functions `f(local_t / dur)` within locked scene bounds,
anchored to real scene `focal_anchor` coordinates (`sd-camera-exec-1`), respecting `--visual-plan-in`
locked keys, and enforced directly inside Three.js (`camera_executor.js`).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from .camera_execution import SCHEMA_VERSION as CAMERA_EXEC_SCHEMA, evaluate_camera_path_py
from .scene_asset_factory import ZDF_ARCHETYPE_REGISTRY, _map_family_to_generator


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


def _resolve_zdf_scene_meta(shot: Dict[str, Any]) -> Dict[str, Any]:
    gen = str(shot.get("procedural_generator") or "")
    if not gen or gen not in ZDF_ARCHETYPE_REGISTRY:
        staging = shot.get("staging") or {}
        fam = str(shot.get("scene_family") or staging.get("scene_family") or "human_studio")
        prop = str(staging.get("visual_metaphor") or "idea_spark")
        gen = _map_family_to_generator("zach-d-films", fam, prop)
    reg = ZDF_ARCHETYPE_REGISTRY.get(gen) or {}
    return {
        "generator": gen,
        "focal_anchor": dict(reg.get("focal_anchor") or {"anchor_id": "stage_center", "world_pos": [0.0, 1.18, 0.0], "radius_m": 0.25}),
        "bounds": dict(reg.get("bounds") or DEFAULT_SCENE_BOUNDS),
        "collider_boxes": list(reg.get("collider_boxes") or []),
    }


def _zdf_keyframes_for_generator(
    gen: str,
    shot: Dict[str, Any],
    anchor_pos: List[float],
    move: str,
    fov: int,
    sx: float,
    seed_off: float,
) -> List[Dict[str, Any]]:
    idx = int(shot.get("index", 0))
    staging = shot.get("staging") or {}
    setup = str(shot.get("setup_type") or "")
    low = str(shot.get("narration_text") or "").lower()
    ax, ay, az = [float(v) for v in anchor_pos]
    is_hold = bool(staging.get("intentional_hold", False)) or ("hold" in move)

    if gen == "zach3d:roman_historical_stage":
        # Preserve Roman artistic camera sweeps while making them canonical keyframes
        if idx == 0:
            return [
                {"t_norm": 0.0, "pos": [-0.35, 1.26, 4.05], "look": [0.0, 0.90, 0.10], "fov": 39, "roll": 0.0, "ease": "cubic"},
                {"t_norm": 1.0, "pos": [0.15, 1.12, 3.35], "look": [0.0, 0.90, 0.10], "fov": 39, "roll": 0.0, "ease": "cubic"},
            ]
        if "final blow" in low or "doesn't come" in low:
            return [
                {"t_norm": 0.0, "pos": [0.62, 1.22, 1.98], "look": [0.02, 1.00, 0.16], "fov": 36, "roll": 0.0, "ease": "cubic"},
                {"t_norm": 1.0, "pos": [0.40, 1.14, 1.66], "look": [0.02, 1.00, 0.16], "fov": 36, "roll": 0.0, "ease": "cubic"},
            ]
        if "fifty times" in low or "catch" in low:
            return [
                {"t_norm": 0.0, "pos": [-0.28, 1.18, 3.45], "look": [0.0, 0.96, 0.05], "fov": 39, "roll": 0.0, "ease": "cubic"},
                {"t_norm": 1.0, "pos": [0.20, 1.26, 3.05], "look": [0.0, 0.96, 0.05], "fov": 39, "roll": 0.0, "ease": "cubic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [round(-0.34 * sx, 3), 1.20, 3.35], "look": [0.0, 0.96, 0.08], "fov": 39, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 1.0, "pos": [round(0.24 * sx, 3), 1.16, 3.02], "look": [0.0, 0.96, 0.08], "fov": 39, "roll": 0.0, "ease": "cubic"},
        ]

    if gen == "zach3d:tacoma_hook_telephoto_stage":
        # Oblique telephoto looking straight down the undulating continuous roadway + 1940 sedan
        return [
            {"t_norm": 0.0, "pos": [-4.25, 3.35, 2.35], "look": [0.0, 2.48, 0.0], "fov": 28, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 0.55, "pos": [-3.65, 3.30, 2.08], "look": [0.0, 2.48, 0.0], "fov": 28, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 1.0, "pos": [-3.05, 3.25, 1.88], "look": [0.0, 2.48, 0.0], "fov": 27, "roll": 0.0, "ease": "cubic"},
        ]

    if gen == "zach3d:tacoma_wide_establish_stage":
        # Framing fills center portrait band with towers & full span without 75% empty sea
        if setup == "tacoma_wide_strait_aerial":
            return [
                {"t_norm": 0.0, "pos": [2.85, 4.95, 7.25], "look": [-0.35, 2.55, 0.0], "fov": 42, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 0.50, "pos": [1.35, 4.75, 7.65], "look": [-0.20, 2.55, 0.0], "fov": 41, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [-0.45, 4.55, 8.05], "look": [0.0, 2.55, 0.0], "fov": 40, "roll": 0.0, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [-2.65, 4.45, 7.65], "look": [0.0, 2.55, 0.0], "fov": 40, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.50, "pos": [0.0, 4.55, 7.90], "look": [0.0, 2.55, 0.0], "fov": 40, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [2.45, 4.65, 8.15], "look": [0.0, 2.55, 0.0], "fov": 40, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:tacoma_roadway_wave_stage":
        return [
            {"t_norm": 0.0, "pos": [-2.35, 3.32, 2.55], "look": [0.0, 2.45, 0.0], "fov": 35, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.50, "pos": [-0.75, 3.28, 2.75], "look": [0.0, 2.45, 0.0], "fov": 34, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.95, 3.22, 2.55], "look": [0.0, 2.45, 0.0], "fov": 34, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:tacoma_under_deck_girder_stage":
        return [
            {"t_norm": 0.0, "pos": [-0.95, 1.85, 3.15], "look": [0.0, 2.28, 0.25], "fov": 40, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.52, "pos": [0.0, 1.82, 2.95], "look": [0.0, 2.28, 0.25], "fov": 39, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.90, 1.88, 3.10], "look": [0.0, 2.28, 0.25], "fov": 40, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:tacoma_torsion_twist_stage":
        # Longitudinal 3/4 view down deck axis so opposing left/right deck edges stay inside 9:16 frame & tilted!
        if setup == "tacoma_torsion_twist_longitudinal":
            return [
                {"t_norm": 0.0, "pos": [3.55, 3.75, 3.85], "look": [0.15, 2.48, 0.0], "fov": 44, "roll": 0.008, "ease": "quintic"},
                {"t_norm": 0.50, "pos": [2.65, 3.55, 3.65], "look": [0.15, 2.48, 0.0], "fov": 43, "roll": -0.01, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [1.85, 3.42, 3.55], "look": [0.15, 2.48, 0.0], "fov": 44, "roll": 0.006, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [-3.75, 3.65, 3.75], "look": [0.20, 2.48, 0.0], "fov": 43, "roll": -0.008, "ease": "quintic"},
            {"t_norm": 0.50, "pos": [-2.85, 3.52, 3.55], "look": [0.20, 2.48, 0.0], "fov": 42, "roll": 0.012, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [-1.95, 3.45, 3.65], "look": [0.20, 2.48, 0.0], "fov": 43, "roll": -0.006, "ease": "quintic"},
        ]

    if gen == "zach3d:tacoma_shore_onlooker_stage":
        return [
            {"t_norm": 0.0, "pos": [-1.15, 1.72, 3.15], "look": [0.18, 1.32, -0.35], "fov": 36, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 0.52, "pos": [-0.85, 1.68, 3.45], "look": [0.18, 1.32, -0.35], "fov": 36, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 1.0, "pos": [-0.55, 1.66, 3.70], "look": [0.18, 1.32, -0.35], "fov": 36, "roll": 0.0, "ease": "cubic"},
        ]

    if gen == "zach3d:tacoma_collapse_plunge_stage":
        return [
            {"t_norm": 0.0, "pos": [0.15, 4.15, 8.35], "look": [-0.30, 1.65, 0.0], "fov": 52, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.45, "pos": [0.0, 3.70, 8.05], "look": [-0.28, 1.40, 0.0], "fov": 52, "roll": 0.01, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [-0.15, 3.15, 7.75], "look": [-0.25, 1.05, 0.0], "fov": 52, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:tacoma_aftermath_stage":
        return [
            {"t_norm": 0.0, "pos": [-1.15, 3.45, 7.35], "look": [0.0, 1.15, 0.0], "fov": 42, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 0.55, "pos": [0.0, 3.75, 8.05], "look": [0.0, 1.10, 0.0], "fov": 42, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 1.0, "pos": [1.15, 4.05, 8.75], "look": [0.0, 1.05, 0.0], "fov": 43, "roll": 0.0, "ease": "cubic"},
        ]

    if gen == "zach3d:skyscraper_street_hook_stage":
        return [
            {"t_norm": 0.0, "pos": [-2.10, 1.10, 5.25], "look": [-0.20, 3.75, -2.20], "fov": 62, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 0.55, "pos": [-1.85, 1.14, 5.10], "look": [-0.20, 3.85, -2.20], "fov": 62, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 1.0, "pos": [-1.65, 1.18, 4.95], "look": [-0.20, 3.95, -2.20], "fov": 61, "roll": 0.0, "ease": "cubic"},
        ]

    if gen == "zach3d:skyscraper_skyline_wide_stage":
        return [
            {"t_norm": 0.0, "pos": [-3.80, 6.20, 11.50], "look": [0.0, 4.40, -0.80], "fov": 46, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.50, "pos": [0.20, 6.40, 11.20], "look": [0.0, 4.40, -0.80], "fov": 46, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [3.60, 6.60, 10.90], "look": [0.0, 4.40, -0.80], "fov": 46, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:skyscraper_wind_vortex_stage":
        return [
            {"t_norm": 0.0, "pos": [-2.40, 5.80, 4.20], "look": [0.0, 5.80, -0.80], "fov": 42, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.50, "pos": [-0.80, 6.00, 3.80], "look": [0.0, 5.80, -0.80], "fov": 41, "roll": 0.008, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [1.00, 5.90, 4.00], "look": [0.0, 5.80, -0.80], "fov": 42, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:skyscraper_plumb_drift_stage":
        return [
            {"t_norm": 0.0, "pos": [0.35, 5.20, 6.55], "look": [0.42, 5.45, -0.80], "fov": 49, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.52, "pos": [0.55, 5.55, 6.15], "look": [0.45, 5.65, -0.80], "fov": 48, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.75, 5.75, 6.45], "look": [0.45, 5.70, -0.80], "fov": 49, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:skyscraper_office_interior_stage":
        return [
            {"t_norm": 0.0, "pos": [1.55, 1.48, 3.65], "look": [0.06, 1.24, -0.15], "fov": 48, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 0.55, "pos": [1.18, 1.44, 3.40], "look": [0.06, 1.24, -0.15], "fov": 47, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 1.0, "pos": [0.82, 1.40, 3.15], "look": [0.08, 1.24, -0.15], "fov": 46, "roll": 0.0, "ease": "cubic"},
        ]

    if gen == "zach3d:skyscraper_tmd_cutaway_stage":
        return [
            {"t_norm": 0.0, "pos": [-2.40, 2.20, 5.15], "look": [0.0, 1.45, 0.05], "fov": 46, "roll": -0.008, "ease": "quintic"},
            {"t_norm": 0.52, "pos": [-0.65, 2.00, 4.75], "look": [0.0, 1.45, 0.05], "fov": 45, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [1.45, 1.90, 4.85], "look": [0.0, 1.45, 0.05], "fov": 45, "roll": 0.008, "ease": "quintic"},
        ]

    if gen == "zach3d:skyscraper_counterphase_stage":
        return [
            {"t_norm": 0.0, "pos": [2.05, 2.15, 5.05], "look": [0.0, 1.75, 0.15], "fov": 46, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.50, "pos": [0.35, 2.05, 4.65], "look": [0.0, 1.75, 0.15], "fov": 45, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [-1.55, 2.00, 4.85], "look": [0.0, 1.75, 0.15], "fov": 45, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:skyscraper_before_after_stage":
        return [
            {"t_norm": 0.0, "pos": [-0.35, 3.90, 10.60], "look": [0.0, 3.40, 0.0], "fov": 48, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.55, "pos": [0.0, 4.00, 10.20], "look": [0.0, 3.40, 0.0], "fov": 47, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.35, 4.10, 10.45], "look": [0.0, 3.40, 0.0], "fov": 47, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:skyscraper_dusk_resolution_stage":
        return [
            {"t_norm": 0.0, "pos": [-2.80, 5.20, 8.40], "look": [0.0, 4.60, -1.0], "fov": 45, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.55, "pos": [0.0, 5.80, 9.60], "look": [0.0, 4.60, -1.0], "fov": 45, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [2.60, 6.40, 10.80], "look": [0.0, 4.60, -1.0], "fov": 46, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:london_fog_street_hook_stage":
        return [
            {"t_norm": 0.0, "pos": [-1.35, 2.15, 5.65], "look": [0.15, 1.85, -1.2], "fov": 44, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.52, "pos": [-0.55, 2.00, 4.65], "look": [0.22, 1.90, -1.2], "fov": 42, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.40, 1.92, 3.85], "look": [0.25, 1.95, -1.2], "fov": 40, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:london_coal_combustion_cutaway_stage":
        if "chimneys" in low or "chilly winter air" in low or idx >= 2:
            return [
                {"t_norm": 0.0, "pos": [1.75, 2.35, 5.10], "look": [0.0, 2.25, -0.55], "fov": 44, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 0.50, "pos": [0.65, 2.75, 4.95], "look": [0.0, 2.55, -0.75], "fov": 43, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [-0.85, 3.15, 5.20], "look": [0.0, 2.75, -0.95], "fov": 44, "roll": 0.0, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [-1.85, 1.55, 4.75], "look": [0.0, 1.65, -0.35], "fov": 42, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.50, "pos": [-0.75, 1.85, 4.35], "look": [0.0, 1.78, -0.35], "fov": 40, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.75, 2.30, 4.55], "look": [0.0, 2.00, -0.45], "fov": 41, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:london_atmospheric_inversion_stage":
        if "sideways" in low or "vertical mixing" in low:
            return [
                {"t_norm": 0.0, "pos": [2.25, 2.65, 7.20], "look": [0.0, 2.40, -0.3], "fov": 44, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 0.52, "pos": [0.85, 2.35, 6.45], "look": [-0.2, 2.25, -0.2], "fov": 43, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [-1.45, 2.20, 6.10], "look": [-0.3, 2.15, -0.2], "fov": 42, "roll": 0.0, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [-2.35, 3.15, 8.20], "look": [0.0, 2.85, -0.5], "fov": 47, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.52, "pos": [0.0, 3.28, 7.95], "look": [0.0, 2.95, -0.5], "fov": 46, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [2.25, 3.40, 8.15], "look": [0.0, 2.95, -0.5], "fov": 46, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:london_bus_visibility_stage":
        return [
            {"t_norm": 0.0, "pos": [2.25, 1.55, 5.20], "look": [0.25, 1.25, 1.15], "fov": 42, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.50, "pos": [1.85, 1.48, 4.45], "look": [0.28, 1.25, 1.35], "fov": 40, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [1.45, 1.42, 3.75], "look": [0.35, 1.25, 1.50], "fov": 39, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:london_pedestrian_reaction_stage":
        return [
            {"t_norm": 0.0, "pos": [-1.25, 1.52, 3.35], "look": [0.0, 1.36, 0.22], "fov": 38, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.52, "pos": [-0.65, 1.48, 2.95], "look": [0.0, 1.38, 0.24], "fov": 37, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.22, 1.46, 2.75], "look": [0.0, 1.38, 0.24], "fov": 36, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:london_clean_air_aftermath_stage":
        return [
            {"t_norm": 0.0, "pos": [-1.25, 2.35, 5.10], "look": [0.0, 1.90, -0.6], "fov": 44, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.55, "pos": [0.0, 2.75, 5.85], "look": [0.0, 2.05, -0.8], "fov": 45, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [1.35, 3.15, 6.60], "look": [0.0, 2.15, -1.0], "fov": 46, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:boston_street_hook_stage":
        if setup == "boston_street_hook_alley_pan":
            return [
                {"t_norm": 0.0, "pos": [1.95, 2.55, 3.65], "look": [-0.05, 1.32, -0.20], "fov": 45, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 0.52, "pos": [1.55, 2.38, 3.25], "look": [-0.04, 1.34, -0.15], "fov": 44, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [1.15, 2.25, 2.85], "look": [-0.02, 1.35, -0.10], "fov": 43, "roll": 0.0, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [-1.42, 1.52, 3.85], "look": [0.05, 1.32, 0.25], "fov": 38, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.52, "pos": [-0.62, 1.44, 3.05], "look": [0.02, 1.35, 0.22], "fov": 36, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.22, 1.40, 2.38], "look": [0.0, 1.36, 0.18], "fov": 35, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:boston_molasses_reveal_stage":
        return [
            {"t_norm": 0.0, "pos": [1.65, 2.35, 4.45], "look": [0.0, 1.05, -0.35], "fov": 44, "roll": -0.008, "ease": "quintic"},
            {"t_norm": 0.45, "pos": [0.75, 2.40, 4.05], "look": [0.0, 1.05, -0.25], "fov": 43, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [-0.25, 2.45, 3.85], "look": [0.0, 1.08, -0.20], "fov": 42, "roll": 0.006, "ease": "quintic"},
        ]

    if gen == "zach3d:boston_tank_leak_stage":
        if setup == "boston_tank_scale_payoff":
            return [
                {"t_norm": 0.0, "pos": [-1.85, 1.82, 3.65], "look": [-0.20, 1.22, 0.45], "fov": 42, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 0.52, "pos": [-1.35, 2.04, 3.45], "look": [-0.22, 1.24, 0.50], "fov": 41, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [-0.88, 2.26, 3.25], "look": [-0.24, 1.26, 0.55], "fov": 40, "roll": 0.0, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [0.95, 1.05, 2.75], "look": [-0.20, 1.08, 0.55], "fov": 36, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.55, "pos": [0.58, 1.32, 2.42], "look": [-0.18, 1.18, 0.55], "fov": 34, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.22, 1.62, 2.22], "look": [-0.15, 1.32, 0.52], "fov": 33, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:boston_tank_rupture_stage":
        if setup == "boston_tank_rupture_surge":
            return [
                {"t_norm": 0.0, "pos": [1.95, 1.65, 4.15], "look": [0.0, 1.22, 0.42], "fov": 44, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 0.48, "pos": [0.85, 1.72, 3.75], "look": [0.0, 1.26, 0.45], "fov": 43, "roll": -0.008, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [-0.65, 1.85, 3.55], "look": [0.0, 1.28, 0.45], "fov": 42, "roll": 0.0, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [-1.25, 1.42, 2.85], "look": [0.0, 1.28, 0.45], "fov": 37, "roll": -0.008, "ease": "quintic"},
            {"t_norm": 0.48, "pos": [-0.32, 1.44, 2.38], "look": [0.0, 1.30, 0.45], "fov": 35, "roll": 0.012, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.68, 1.58, 2.72], "look": [0.04, 1.24, 0.40], "fov": 38, "roll": -0.006, "ease": "quintic"},
        ]

    if gen == "zach3d:boston_wave_street_stage":
        if setup == "boston_wave_speed_sweep":
            return [
                {"t_norm": 0.0, "pos": [1.55, 2.25, 5.45], "look": [-0.05, 1.05, 0.35], "fov": 41, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 0.52, "pos": [0.95, 2.02, 4.65], "look": [0.0, 1.06, 0.35], "fov": 39, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [-0.95, 1.96, 4.15], "look": [0.0, 1.08, 0.45], "fov": 39, "roll": 0.0, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [-0.24, 1.58, 3.65], "look": [0.0, 1.08, 0.35], "fov": 39, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.55, "pos": [-0.42, 1.76, 4.35], "look": [0.0, 1.10, 0.50], "fov": 40, "roll": -0.006, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [-0.58, 1.94, 5.05], "look": [0.0, 1.12, 0.65], "fov": 41, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:boston_elevated_rail_impact_stage":
        if setup == "boston_elevated_rail_truss_tilt":
            return [
                {"t_norm": 0.0, "pos": [-1.65, 1.88, 4.05], "look": [0.08, 1.25, 0.05], "fov": 43, "roll": -0.008, "ease": "quintic"},
                {"t_norm": 0.50, "pos": [-1.05, 1.80, 3.65], "look": [0.06, 1.28, 0.05], "fov": 42, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [-0.35, 1.76, 3.35], "look": [0.04, 1.32, 0.05], "fov": 41, "roll": 0.008, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [2.22, 2.25, 4.35], "look": [-0.35, 1.95, 0.05], "fov": 40, "roll": 0.008, "ease": "quintic"},
            {"t_norm": 0.50, "pos": [1.75, 2.08, 3.72], "look": [-0.28, 1.92, 0.05], "fov": 39, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [1.18, 2.18, 3.35], "look": [-0.20, 1.95, 0.05], "fov": 38, "roll": -0.006, "ease": "quintic"},
        ]

    if gen == "zach3d:boston_rescue_aftermath_stage":
        if setup == "boston_rescue_lantern_wade":
            return [
                {"t_norm": 0.0, "pos": [1.18, 1.30, 2.78], "look": [0.05, 0.92, 0.22], "fov": 34, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 0.52, "pos": [0.62, 1.24, 2.42], "look": [0.02, 0.90, 0.22], "fov": 33, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [0.12, 1.20, 2.18], "look": [0.0, 0.88, 0.20], "fov": 32, "roll": 0.0, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [-0.95, 1.56, 3.55], "look": [0.0, 0.96, 0.20], "fov": 36, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 0.5, "pos": [-0.25, 1.48, 3.28], "look": [0.0, 0.94, 0.20], "fov": 36, "roll": 0.0, "ease": "cubic"},
            {"t_norm": 1.0, "pos": [0.45, 1.44, 3.12], "look": [0.0, 0.92, 0.18], "fov": 35, "roll": 0.0, "ease": "cubic"},
        ]

    if gen == "zach3d:boston_engineering_cutaway_stage":
        return [
            {"t_norm": 0.0, "pos": [-1.55, 1.62, 3.25], "look": [0.0, 1.24, 0.08], "fov": 38, "roll": -0.008, "ease": "quintic"},
            {"t_norm": 0.52, "pos": [0.18, 1.42, 2.75], "look": [0.0, 1.24, 0.08], "fov": 36, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [1.45, 1.36, 2.95], "look": [0.0, 1.24, 0.08], "fov": 37, "roll": 0.008, "ease": "quintic"},
        ]

    if gen == "zach3d:boston_harbor_payoff_stage":
        return [
            {"t_norm": 0.0, "pos": [-1.05, 3.35, 4.95], "look": [0.0, 0.72, -0.45], "fov": 39, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.55, "pos": [0.22, 4.35, 6.15], "look": [0.0, 0.68, -0.55], "fov": 40, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [1.35, 5.25, 7.25], "look": [0.0, 0.65, -0.65], "fov": 42, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:airplane_window_hole_stage":
        if setup == "airplane_window_layers_exploded":
            return [
                {"t_norm": 0.0, "pos": [-1.36, 1.48, 2.04], "look": [0.0, 1.20, 0.0], "fov": 38, "roll": -0.01, "ease": "quintic"},
                {"t_norm": 0.52, "pos": [-0.58, 1.38, 2.12], "look": [0.0, 1.20, 0.0], "fov": 37, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [1.18, 1.32, 2.02], "look": [0.0, 1.18, 0.0], "fov": 36, "roll": 0.01, "ease": "quintic"},
            ]
        if setup == "airplane_window_pressure_equalize":
            return [
                {"t_norm": 0.0, "pos": [-0.88, 1.34, 1.98], "look": [0.0, 1.18, 0.0], "fov": 36, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 0.5, "pos": [0.08, 1.26, 1.76], "look": [0.0, 1.14, 0.0], "fov": 35, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [0.78, 1.20, 1.88], "look": [0.0, 1.10, 0.0], "fov": 34, "roll": 0.008, "ease": "quintic"},
            ]
        if setup == "airplane_window_failsafe_cutaway":
            return [
                {"t_norm": 0.0, "pos": [1.18, 1.46, 1.66], "look": [0.0, 1.20, -0.02], "fov": 36, "roll": 0.01, "ease": "quintic"},
                {"t_norm": 0.55, "pos": [0.84, 1.32, 1.52], "look": [0.0, 1.16, 0.0], "fov": 35, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [0.42, 1.22, 1.62], "look": [0.0, 1.12, 0.0], "fov": 33, "roll": -0.008, "ease": "quintic"},
            ]
        if setup == "airplane_window_moisture_vent":
            return [
                {"t_norm": 0.0, "pos": [0.38, 1.10, 1.18], "look": [0.0, 1.065, 0.0], "fov": 31, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 0.55, "pos": [-0.22, 1.18, 1.46], "look": [0.0, 1.16, 0.0], "fov": 34, "roll": -0.006, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [-0.52, 1.32, 1.88], "look": [0.0, 1.22, 0.0], "fov": 37, "roll": 0.0, "ease": "quintic"},
            ]
        # Default / hook macro focus on lower bleed hole orifice [0.0, 1.065, 0.0] with full oval bezel framing
        side_sign = -1.0 if (idx % 2 == 1) else 1.0
        z_shift = 0.16 if idx >= 4 else 0.0
        return [
            {"t_norm": 0.0, "pos": [round(0.40 * side_sign, 3), 1.26 + (0.08 if idx >= 4 else 0.0), round(1.66 + z_shift, 3)], "look": [0.0, 1.14, 0.0], "fov": 35, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.55, "pos": [round(-0.16 * side_sign, 3), 1.15, round(1.30 + z_shift, 3)], "look": [0.0, 1.08, 0.0], "fov": 32, "roll": round(-0.006 * side_sign, 3), "ease": "quintic"},
            {"t_norm": 1.0, "pos": [round(-0.42 * side_sign, 3), 1.11, round(1.14 + z_shift, 3)], "look": [0.0, 1.065, 0.0], "fov": 30, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:elevator_lobby_button_stage":
        # Frame hero + reaching forearm cleanly pressing the illuminated hall plunger inside portrait safe box
        return [
            {"t_norm": 0.0, "pos": [-0.88, 1.44, 2.08], "look": [0.02, 1.20, 0.20], "fov": 36, "roll": -0.01, "ease": "quintic"},
            {"t_norm": 0.48, "pos": [-0.62, 1.30, 1.42], "look": [0.06, 1.18, 0.22], "fov": 32, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [-0.46, 1.22, 1.12], "look": [0.16, 1.16, 0.24], "fov": 29, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:controller_cabinet_cutaway_stage":
        if setup == "controller_relay_bus_macro":
            return [
                {"t_norm": 0.0, "pos": [0.46, 1.38, 1.26], "look": [ax, ay, az], "fov": 30, "roll": 0.008, "ease": "quintic"},
                {"t_norm": 0.55, "pos": [0.10, 1.28, 0.96], "look": [ax, ay, az], "fov": 26, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [-0.32, 1.18, 1.12], "look": [ax, ay, az], "fov": 28, "roll": -0.008, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [round(-0.42 + seed_off, 3), 1.34, 1.48], "look": [ax, ay, az], "fov": max(26, min(36, fov)), "roll": -0.008, "ease": "quintic"},
            {"t_norm": 0.55, "pos": [0.06, 1.26, 1.06], "look": [ax, ay, az], "fov": max(24, min(34, fov - 2)), "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.34, 1.23, 0.86], "look": [ax, ay, az], "fov": max(24, min(32, fov - 3)), "roll": 0.008, "ease": "quintic"},
        ]

    if gen == "zach3d:traction_machine_room_stage":
        if setup == "traction_caliper_brake_macro" or any(k in low for k in ("brake", "caliper", "clamp", "slow", "stop")):
            # Distinct tight right-side close-up onto red brake caliper pads clamping steel sheave
            return [
                {"t_norm": 0.0, "pos": [0.68, 1.62, 1.18], "look": [0.12, 1.36, 0.0], "fov": 29, "roll": 0.01, "ease": "quintic"},
                {"t_norm": 0.55, "pos": [0.38, 1.48, 0.94], "look": [0.08, 1.36, 0.0], "fov": 26, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [0.16, 1.42, 0.82], "look": [0.04, 1.36, 0.0], "fov": 25, "roll": -0.006, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [-1.25, 1.72, 1.72], "look": [ax, ay, az], "fov": max(28, min(38, fov)), "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.55, "pos": [0.05, 1.54, 1.92], "look": [ax, ay, az], "fov": max(28, min(36, fov)), "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [1.08, 1.38, 1.58], "look": [ax, ay - 0.06, az], "fov": max(27, min(35, fov - 1)), "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:elevator_shaft_cutaway_stage":
        if is_hold:
            return [
                {"t_norm": 0.0, "pos": [0.22, 1.34, 3.05], "look": [ax, ay, az], "fov": 35, "roll": 0.0, "hold": True, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [0.22, 1.34, 3.05], "look": [ax, ay, az], "fov": 35, "roll": 0.0, "ease": "quintic"},
            ]
        if setup == "elevator_shaft_sensors_close":
            return [
                {"t_norm": 0.0, "pos": [0.62, 1.12, 2.38], "look": [0.06, 1.24, 0.04], "fov": 34, "roll": 0.0, "ease": "quintic"},
                {"t_norm": 1.0, "pos": [0.48, 1.56, 2.24], "look": [0.06, 1.38, 0.04], "fov": 33, "roll": 0.0, "ease": "quintic"},
            ]
        return [
            {"t_norm": 0.0, "pos": [round(-0.44 + seed_off, 3), 1.54, 3.22], "look": [0.05, 1.32, az], "fov": 35, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.5, "pos": [0.14, 1.36, 2.95], "look": [0.05, 1.26, az], "fov": 34, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.42, 1.18, 2.72], "look": [0.05, 1.16, az], "fov": 33, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:elevator_landing_doors_stage":
        return [
            {"t_norm": 0.0, "pos": [-0.28, 1.36, 2.86], "look": [0.02, 1.18, 0.18], "fov": 35, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.55, "pos": [0.10, 1.38, 3.08], "look": [0.02, 1.18, 0.16], "fov": 36, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.34, 1.40, 3.28], "look": [0.02, 1.18, 0.14], "fov": 36, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:human_device_stage":
        return [
            {"t_norm": 0.0, "pos": [0.55, 1.50, 2.76], "look": [0.04, 1.22, 0.14], "fov": max(30, min(38, fov)), "roll": -0.01, "ease": "quintic"},
            {"t_norm": 0.55, "pos": [0.38, 1.42, 2.34], "look": [0.12, 1.24, 0.18], "fov": max(28, min(36, fov - 1)), "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.22, 1.36, 1.98], "look": [ax, ay, az], "fov": max(26, min(34, fov - 2)), "roll": 0.008, "ease": "quintic"},
        ]

    if gen == "zach3d:device_cutaway_stage":
        return [
            {"t_norm": 0.0, "pos": [-0.46, 1.44, 1.92], "look": [ax, ay, az], "fov": max(26, min(35, fov)), "roll": -0.01, "ease": "quintic"},
            {"t_norm": 0.5, "pos": [0.08, 1.36, 1.66], "look": [ax, ay, az], "fov": max(26, min(34, fov)), "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.52, 1.30, 1.48], "look": [ax, ay, az], "fov": max(25, min(33, fov - 1)), "roll": 0.01, "ease": "quintic"},
        ]

    if gen == "zach3d:network_relay_stage":
        return [
            {"t_norm": 0.0, "pos": [-1.20, 1.28, 2.82], "look": [0.0, 1.65, 0.0], "fov": 36, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.85, 2.45, 2.25], "look": [0.0, 2.25, 0.0], "fov": 34, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:subsea_fiber_stage":
        return [
            {"t_norm": 0.0, "pos": [-1.55, 1.38, 2.82], "look": [ax, ay, az], "fov": 34, "roll": -0.01, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [1.35, 0.98, 2.25], "look": [ax, ay, az], "fov": 32, "roll": 0.01, "ease": "quintic"},
        ]

    if gen == "zach3d:datacenter_aisle_stage":
        return [
            {"t_norm": 0.0, "pos": [-0.14, 1.32, 2.82], "look": [0.0, 1.18, -2.4], "fov": 38, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.12, 1.50, 0.65], "look": [0.0, 1.18, -2.4], "fov": 36, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:power_turbine_stage":
        return [
            {"t_norm": 0.0, "pos": [-0.72, 1.52, 1.72], "look": [ax, ay, az], "fov": 34, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.5, "pos": [0.04, 1.38, 1.88], "look": [ax, ay, az], "fov": 34, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.82, 1.24, 1.65], "look": [ax, ay, az], "fov": 33, "roll": 0.0, "ease": "quintic"},
        ]

    if gen == "zach3d:cosmic_scale_bridge_stage":
        return [
            {"t_norm": 0.0, "pos": [-0.52, 1.32, 2.15], "look": [ax, ay, az], "fov": 36, "roll": -0.01, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.72, 1.92, 3.60], "look": [ax, ay, az], "fov": 40, "roll": 0.01, "ease": "quintic"},
        ]

    if gen == "zach3d:anatomical_cutaway_stage":
        return [
            {"t_norm": 0.0, "pos": [0.55, 1.32, 1.58], "look": [ax, ay, az], "fov": 32, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [0.14, 1.30, 1.15], "look": [ax, ay, az], "fov": 30, "roll": 0.0, "ease": "quintic"},
        ]

    # Default / schematic / studio demonstrator anchored cleanly to `focal_anchor`
    if move in ("macro_push_in", "focus_push_to_organ", "slowmo_track_impact", "push_toward_core"):
        return [
            {"t_norm": 0.0, "pos": [round(ax + 0.45 * sx + seed_off, 3), ay + 0.22, az + 1.85], "look": [ax, ay, az], "fov": fov + 2, "roll": round(-0.015 * sx, 3), "ease": "quintic"},
            {"t_norm": 1.0, "pos": [round(ax + 0.14 * sx - seed_off, 3), ay + 0.06, az + 1.12], "look": [ax, ay, az], "fov": max(22, fov - 2), "roll": round(0.012 * sx, 3), "ease": "quintic"},
        ]
    if move in ("peel_orbit_reveal", "arc_around_rotor", "orbit_right"):
        ang0 = 0.35 * sx
        ang1 = ang0 + 0.68 * sx
        r0, r1 = 1.92, 1.56
        return [
            {"t_norm": 0.0, "pos": [round(ax + math.sin(ang0) * r0, 3), ay + 0.38, round(az + math.cos(ang0) * r0, 3)], "look": [ax, ay, az], "fov": fov, "roll": 0.0, "ease": "quintic"},
            {"t_norm": 0.5, "pos": [round(ax + math.sin((ang0 + ang1) * 0.5) * ((r0 + r1) * 0.5), 3), ay + 0.28, round(az + math.cos((ang0 + ang1) * 0.5) * ((r0 + r1) * 0.5), 3)], "look": [ax, ay, az], "fov": fov, "roll": 0.008 * sx, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [round(ax + math.sin(ang1) * r1, 3), ay + 0.16, round(az + math.cos(ang1) * r1, 3)], "look": [ax, ay, az], "fov": max(22, fov - 1), "roll": 0.0, "ease": "quintic"},
        ]
    if move in ("crane_tilt_follow", "scale_pullback_cosmos", "pull_back_crane"):
        return [
            {"t_norm": 0.0, "pos": [round(ax - 0.32 * sx + seed_off, 3), max(0.35, ay - 0.18), az + 1.55], "look": [ax, ay, az], "fov": fov, "roll": -0.008 * sx, "ease": "quintic"},
            {"t_norm": 1.0, "pos": [round(ax + 0.32 * sx, 3), ay + 0.72, az + 2.85], "look": [ax, ay, az], "fov": min(48, fov + 4), "roll": 0.0, "ease": "quintic"},
        ]
    return [
        {"t_norm": 0.0, "pos": [round(ax - 0.52 * sx, 3), ay + 0.24, az + 2.35], "look": [ax, ay, az], "fov": fov, "roll": round(-0.01 * sx, 3), "ease": "quintic"},
        {"t_norm": 1.0, "pos": [round(ax + 0.38 * sx + seed_off, 3), ay + 0.10, az + 1.48], "look": [ax, ay, az], "fov": max(22, fov - 2), "roll": round(0.01 * sx, 3), "ease": "quintic"},
    ]


def plan_camera_path(
    shot: Dict[str, Any],
    scene_bounds: Optional[Dict[str, Any]],
    selected_skill: str,
    fps: int = 30,
    seed: int = 42,
    scene_anchor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return engine-specific deterministic camera/viewport keyframes anchored to real world bounds."""
    idx = int(shot.get("index", 0))
    cam_meta = shot.get("camera") or {}
    staging = shot.get("staging") or {}
    setup = str(shot.get("setup_type") or "")
    move = str(cam_meta.get("movement") or "dolly_push_in")
    focal = int(cam_meta.get("focal_length_mm") or 35)
    placement = str(staging.get("subject_placement") or "center")
    sx = _sign_x(placement, idx)
    seed_off = (((seed + idx * 71) % 19) - 9) * 0.012

    if selected_skill == "zach-d-films":
        scene_meta = _resolve_zdf_scene_meta(shot)
        focal_anchor = scene_anchor or scene_meta["focal_anchor"]
        bounds = scene_bounds or scene_meta["bounds"] or DEFAULT_SCENE_BOUNDS
        fov = 26 if focal >= 65 else (30 if focal >= 45 else (34 if focal >= 30 else 38))

        # Honor locked/pinned keyframes from --visual-plan-in without silent mutation
        pinned_kfs = shot.get("locked_camera_keyframes") or cam_meta.get("locked_camera_keyframes")
        camera_locked = bool(shot.get("camera_locked") or cam_meta.get("camera_locked") or (shot.get("manual") and pinned_kfs))
        if pinned_kfs:
            keyframes = [dict(k) for k in pinned_kfs]
        else:
            keyframes = _zdf_keyframes_for_generator(
                scene_meta["generator"], shot, focal_anchor["world_pos"], move, fov, sx, seed_off
            )

        p0 = evaluate_camera_path_py({"keyframes": keyframes}, 0.0)["pos"]
        pm = evaluate_camera_path_py({"keyframes": keyframes}, 0.5)["pos"]
        p1 = evaluate_camera_path_py({"keyframes": keyframes}, 1.0)["pos"]
        return {
            "schema_version": CAMERA_EXEC_SCHEMA,
            "shot_id": shot["shot_id"],
            "rig_id": f"cam_rig_{shot['shot_id']}",
            "engine": selected_skill,
            "path_family": move,
            "space": "world_3d",
            "camera_locked": camera_locked,
            "focal_anchor": focal_anchor,
            "collision_constraints": {
                "min_dist_m": 0.25,
                "ground_min_y": 0.08,
                "collider_boxes": scene_meta["collider_boxes"],
            },
            "entry_vector": [round(pm[k] - p0[k], 3) for k in range(3)],
            "exit_vector": [round(p1[k] - pm[k], 3) for k in range(3)],
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
        plan_camera_path(s, None, selected_skill=selected_skill, fps=fps, seed=seed)
        for s in shots
    ]
    seams = [
        plan_camera_continuity(shots[i], shots[i + 1], paths[i], paths[i + 1], event_graph=event_graph)
        for i in range(max(0, len(shots) - 1))
    ]
    doc: Dict[str, Any] = {
        "schema_version": "sd-camera-paths-2",
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
