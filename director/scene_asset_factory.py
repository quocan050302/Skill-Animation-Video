"""STEP 4A (SD-VISUAL-01): Procedural Scene Entity Compiler, Re-Usable Registry & Bounds Validator.

Compiles `VisualEventGraph` entities into typed procedural asset blueprints strictly within the
locked `selected_skill` without falling back to Roman armor on non-Roman scripts or touching
any foreign visual engine.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set, Tuple

from . import VALID_SKILLS


class UnsupportedSceneError(RuntimeError):
    """Fail-closed exception when a scene cannot be rendered honestly in the locked engine."""


# Parametric 3D / 2D bounding extents (width, height, depth in logical meters or view coords)
ENTITY_BOUNDS_M: Dict[str, Tuple[float, float, float]] = {
    "phone_screen": (0.16, 0.30, 0.04),
    "microchip_pcb": (0.48, 0.36, 0.24),
    "battery_cell": (0.32, 0.56, 0.22),
    "cell_tower_wave": (0.90, 2.20, 0.90),
    "subsea_fiber_cable": (2.20, 0.70, 1.20),
    "datacenter_rack": (1.60, 2.10, 2.40),
    "power_turbine": (1.40, 1.40, 1.20),
    "cosmic_origin": (2.20, 2.20, 2.20),
    "atom_crystal": (0.95, 0.95, 0.95),
    "brain_neuron": (0.85, 0.95, 0.85),
    "heart_organ": (0.75, 0.95, 0.75),
    "roman_arena": (2.40, 1.85, 2.40),
    "roman_ledger": (1.10, 1.45, 0.90),
    "sword_blade": (0.80, 1.65, 0.80),
    "shield_impact": (0.85, 1.75, 0.85),
    "vault_gear": (1.15, 1.35, 0.90),
    "clock_timer": (0.85, 1.40, 0.65),
    "coin_treasure": (0.95, 1.20, 0.95),
    "coffee_cup": (0.55, 1.15, 0.55),
    "balance_scale": (1.10, 1.35, 0.70),
    "rain_courtyard": (1.80, 1.70, 1.80),
    "data_chart": (1.0, 1.2, 0.2),
    "route_street": (3.0, 2.0, 3.0),
    "exploded_device": (1.8, 2.8, 1.8),
    "idea_spark": (0.90, 1.45, 0.75),
}


def make_or_reuse_licensed_procedural_asset(
    entity_spec: Dict[str, Any],
    selected_skill: str,
    existing_registry: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Register or reuse a deterministic procedural asset cleanly inside `selected_skill`."""
    prop = str(entity_spec.get("relevant_prop") or "idea_spark")
    fam = str(entity_spec.get("scene_family") or "human_studio")
    key = f"{selected_skill}:{fam}:{prop}"

    if key in existing_registry:
        entry = dict(existing_registry[key])
        entry["reused_for_callback"] = True
        return entry

    bounds = ENTITY_BOUNDS_M.get(prop, (1.0, 1.5, 1.0))
    asset = {
        "asset_key": key,
        "origin_skill": selected_skill,
        "license_type": "procedural_mit_derived",
        "prop_id": prop,
        "scene_family": fam,
        "bounds_m": list(bounds),
        "procedural_generator": _map_family_to_generator(selected_skill, fam, prop),
        "reused_for_callback": False,
        "seed": int(entity_spec.get("seed", 42)),
    }
    existing_registry[key] = dict(asset)
    return asset


def _map_family_to_generator(selected_skill: str, fam: str, prop: str) -> str:
    if selected_skill == "zach-d-films":
        if fam in ("roman_historical",) or prop in ("roman_arena", "roman_ledger"):
            return "zach3d:roman_historical_stage"
        if fam in ("human_device",):
            return "zach3d:human_device_stage"
        if fam in ("electromechanical",) or prop in ("microchip_pcb", "battery_cell", "vault_gear"):
            return "zach3d:device_cutaway_stage"
        if fam == "network_link" or prop == "cell_tower_wave":
            return "zach3d:network_relay_stage"
        if fam == "ocean_infrastructure" or prop == "subsea_fiber_cable":
            return "zach3d:subsea_fiber_stage"
        if fam == "datacenter_compute" or prop == "datacenter_rack":
            return "zach3d:datacenter_aisle_stage"
        if fam == "energy_grid" or prop == "power_turbine":
            return "zach3d:power_turbine_stage"
        if fam in ("cosmic_scale", "micro_matter") or prop in ("cosmic_origin", "atom_crystal"):
            return "zach3d:cosmic_scale_bridge_stage"
        if fam == "anatomical_cutaway" or prop in ("brain_neuron", "heart_organ"):
            return "zach3d:anatomical_cutaway_stage"
        return "zach3d:studio_demonstrator_stage"
    if selected_skill == "stick-figure":
        return f"sf2d:{fam}"
    if selected_skill == "minimalistic-graphics":
        return f"mg_svg:{fam}"
    if selected_skill == "graph":
        return "graph_svg:data_curve"
    if selected_skill == "map-route":
        return "map3d:schematic_route"
    if selected_skill == "breakdown":
        return f"breakdown3d:{fam}"
    raise UnsupportedSceneError(f"Unknown visual engine: {selected_skill!r}")


def compile_scene_entities(
    event_graph: Dict[str, Any],
    selected_skill: str,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compile all semantic events in `event_graph` into typed entity & generator specs."""
    if selected_skill not in VALID_SKILLS:
        raise ValueError(f"Invalid selected_skill: {selected_skill!r}")
    if event_graph.get("selected_skill") != selected_skill:
        raise UnsupportedSceneError(
            f"Event graph skill {event_graph.get('selected_skill')!r} != locked {selected_skill!r}"
        )

    registry: Dict[str, Dict[str, Any]] = {}
    compiled_items: List[Dict[str, Any]] = []
    for idx, ev in enumerate(event_graph.get("events", [])):
        spec = {
            "relevant_prop": ev.get("relevant_prop"),
            "scene_family": ev.get("scene_family"),
            "seed": seed + idx * 101,
        }
        asset = make_or_reuse_licensed_procedural_asset(spec, selected_skill=selected_skill, existing_registry=registry)
        compiled_items.append({
            "event_id": ev["event_id"],
            "subject": ev.get("subject"),
            "verb_action": ev.get("verb_action"),
            "prop_id": ev.get("relevant_prop"),
            "grounded_props": list(ev.get("grounded_props", [])),
            "scene_family": ev.get("scene_family"),
            "scale_level": ev.get("scale_level"),
            "lighting_mood": ev.get("lighting_mood"),
            "forbidden_elements": list(ev.get("forbidden_elements", [])),
            "asset": asset,
        })

    return {
        "schema_version": "sd-scene-entities-1",
        "selected_skill": selected_skill,
        "origin_skills": [selected_skill],
        "unique_asset_count": len(registry),
        "registry": registry,
        "by_event": {it["event_id"]: it for it in compiled_items},
    }


def evaluate_scene_silhouette_and_camera_bounds(
    shot_spec: Dict[str, Any],
    camera_path: Dict[str, Any],
    entity_info: Dict[str, Any],
) -> Dict[str, Any]:
    """Check 3D / logical framing geometry before render: prevents clipping, tiny subjects & blind walls."""
    issues: List[str] = []
    prop = str(entity_info.get("prop_id") or shot_spec.get("staging", {}).get("visual_metaphor") or "idea_spark")
    bw, bh, bd = ENTITY_BOUNDS_M.get(prop, (1.0, 1.5, 1.0))

    if camera_path.get("space") == "world_3d":
        for kf_idx, kf in enumerate(camera_path.get("keyframes", [])):
            px, py, pz = [float(v) for v in kf.get("pos", [0, 1.4, 2.0])]
            lx, ly, lz = [float(v) for v in kf.get("look", [0, 1.1, 0])]
            fov = float(kf.get("fov", 34))
            dist = math.sqrt((px - lx) ** 2 + (py - ly) ** 2 + (pz - lz) ** 2)
            if dist < 0.25:
                issues.append(f"Keyframe {kf_idx} camera distance {dist:.2f}m clips inside subject")
            if py < 0.08:
                issues.append(f"Keyframe {kf_idx} camera y={py:.2f}m dips below ground plane")
            # Estimated vertical fill fraction at distance `dist`
            half_view_h = dist * math.tan(math.radians(fov * 0.5))
            fill_frac = min(1.5, bh / max(0.05, 2.0 * half_view_h))
            if fill_frac < 0.06:
                issues.append(f"Keyframe {kf_idx} subject height fill={fill_frac:.3f} is critically tiny")

    forbidden = set(entity_info.get("forbidden_elements", []))
    gen = str((entity_info.get("asset") or {}).get("procedural_generator") or "")
    if "roman_gladiator_armor" in forbidden and "roman" in gen:
        issues.append(f"Forbidden Roman armor generator `{gen}` triggered on non-Roman shot {shot_spec.get('shot_id')}")

    return {
        "ok": len(issues) == 0,
        "shot_id": shot_spec.get("shot_id"),
        "subject_bounds_m": [bw, bh, bd],
        "issues": issues,
    }


def materialize_engine_scene(
    shot_spec: Dict[str, Any],
    entity_inventory: Dict[str, Any],
    selected_skill: str,
    camera_path: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Bind a shot + its compiled scene entity + validated camera bounds cleanly."""
    if shot_spec.get("engine") != selected_skill:
        raise UnsupportedSceneError(f"Shot engine {shot_spec.get('engine')!r} != {selected_skill!r}")

    eids = list(shot_spec.get("event_ids", []))
    primary_eid = eids[0] if eids else None
    ent = (entity_inventory.get("by_event") or {}).get(primary_eid or "", {})
    if not ent:
        # Build on demand from shot metadata safely without Roman armor bias
        ent = {
            "event_id": primary_eid or shot_spec["shot_id"],
            "prop_id": shot_spec.get("staging", {}).get("visual_metaphor", "idea_spark"),
            "scene_family": shot_spec.get("scene_family", "human_studio"),
            "lighting_mood": shot_spec.get("lighting_mood", "day_editorial"),
            "forbidden_elements": shot_spec.get("staging", {}).get("forbidden_elements", []),
            "asset": {
                "origin_skill": selected_skill,
                "procedural_generator": _map_family_to_generator(
                    selected_skill,
                    str(shot_spec.get("scene_family", "human_studio")),
                    str(shot_spec.get("staging", {}).get("visual_metaphor", "idea_spark")),
                ),
            },
        }

    bounds_check = (
        evaluate_scene_silhouette_and_camera_bounds(shot_spec, camera_path, ent)
        if camera_path is not None
        else {"ok": True, "issues": []}
    )
    if not bounds_check["ok"]:
        raise UnsupportedSceneError(f"Camera/silhouette bounds violation on {shot_spec.get('shot_id')}: {bounds_check['issues']}")

    return {
        "shot_id": shot_spec["shot_id"],
        "origin_skill": selected_skill,
        "procedural_generator": ent["asset"]["procedural_generator"],
        "prop_id": ent["prop_id"],
        "scene_family": ent["scene_family"],
        "bounds_check": bounds_check,
    }


def validate_entity_continuity(
    shots: List[Dict[str, Any]],
    entity_inventory: Dict[str, Any],
    selected_skill: str,
) -> Dict[str, Any]:
    """Verify entity provenance, forbidden-armor prevention on non-Roman scripts, and uniqueness."""
    if entity_inventory.get("origin_skills") != [selected_skill]:
        raise UnsupportedSceneError("Entity inventory origin_skills violates strict single-skill lock.")

    violations: List[str] = []
    used_generators: List[str] = []
    for s in shots:
        mat = materialize_engine_scene(s, entity_inventory, selected_skill=selected_skill)
        used_generators.append(mat["procedural_generator"])
        forbidden = set((s.get("staging") or {}).get("forbidden_elements", []))
        if "roman_gladiator_armor" in forbidden and "roman" in mat["procedural_generator"]:
            violations.append(f"{s['shot_id']} used Roman generator `{mat['procedural_generator']}` illegally")

    if violations:
        raise UnsupportedSceneError("; ".join(violations))

    return {
        "ok": True,
        "shots_checked": len(shots),
        "unique_generators": len(set(used_generators)),
        "generators_per_shot": used_generators,
    }
