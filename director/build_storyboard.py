"""STEP 3: Continuous Visual-Event-Driven Storyboard, Coverage, Camera, Transition & Entity Inventory Builder.

Integrates SD-VISUAL-01 stages:
1) `visual_event_graph.py` -> `<run>/visual_events.json`
2) `shot_director.py` -> `<run>/shot_coverage.json`
3) `camera_choreographer.py` -> `<run>/camera_paths.json`
4) `transition_director.py` -> `<run>/transition_edl.json`
5) `scene_asset_factory.py` -> scene entity compilation & camera/silhouette bounds check

Strict Guarantees:
- Zero cyclic boilerplate repetition or duplicate narration splits.
- Every `shots[i].engine == selected_skill` (zero guest shots, zero secondary inserts).
- Safe-area geometry (`x: 100..980`, `y: 220..1500`) and caption-band clearance preserved.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .assets.style_params import build_style_params
from .camera_choreographer import build_camera_plan
from .scene_asset_factory import (
    compile_scene_entities,
    materialize_engine_scene,
    validate_entity_continuity,
)
from .shot_director import plan_editorial_coverage
from .transition_director import emit_transition_edl
from .visual_event_graph import extract_semantic_visual_events, write_visual_events_artifact


# Preserved per-engine grammar reference for inspectable external callers
ENGINE_CAMERA_GRAMMAR: Dict[str, List[Dict[str, Any]]] = {
    "stick-figure": [
        {"setup": "hook_dynamic_cu", "framing": "CU", "angle": "eye_level_push", "move": "push_in_handheld", "transition": "whip"},
        {"setup": "belief_wide_parallax", "framing": "WS", "angle": "slight_low_3plane", "move": "tracking_pan_right", "transition": "whip"},
        {"setup": "turn_reaction_ecu", "framing": "ECU", "angle": "dutch_tilt_dramatic", "move": "snap_zoom_shake", "transition": "iris_mask"},
        {"setup": "novel_mechanism_cutaway", "framing": "Cutaway_Macro", "angle": "orthographic_cross_section", "move": "focus_glide", "transition": "whip", "novel_non_template": True},
        {"setup": "split_comparison_stage", "framing": "MS_Split", "angle": "frontal_duel", "move": "counter_drift", "transition": "cut_on_action", "novel_non_template": True},
        {"setup": "scale_ladder_pan", "framing": "MS_to_VWS", "angle": "vertical_pan_climb", "move": "pan_up_scale", "transition": "whip", "novel_non_template": True},
        {"setup": "payoff_sunny_pullback", "framing": "MS_to_WS", "angle": "heroic_eye_level", "move": "pull_back_settle", "transition": "cut"},
    ],
    "zach-d-films": [
        {"setup": "human_device_macro", "framing": "CU_OverShoulder", "angle": "three_quarter_hand_focus", "move": "macro_push_in", "transition": "zoom_through", "novel_non_template": True},
        {"setup": "device_cutaway_pcb", "framing": "ECU_Cutaway", "angle": "exploded_oblique_35deg", "move": "peel_orbit_reveal", "transition": "match_cut", "novel_non_template": True},
        {"setup": "network_tower_relay", "framing": "WS_LowHero", "angle": "upward_tower_tilt", "move": "crane_tilt_follow", "transition": "whip_pan", "novel_non_template": True},
        {"setup": "subsea_fiber_conduit", "framing": "MS_Tracking", "angle": "underwater_low_glide", "move": "dolly_along_conduit", "transition": "zoom_through", "novel_non_template": True},
        {"setup": "datacenter_aisle_sweep", "framing": "WS_Corridor", "angle": "one_point_symmetrical", "move": "dolly_forward_aisle", "transition": "cut_on_action", "novel_non_template": True},
        {"setup": "power_turbine_generator", "framing": "MS_Cutaway", "angle": "elevated_isometric", "move": "arc_around_rotor", "transition": "match_cut", "novel_non_template": True},
        {"setup": "cosmic_scale_bridge", "framing": "ECU_to_VWS", "angle": "orbital_horizon_roll", "move": "scale_pullback_cosmos", "transition": "zoom_through", "novel_non_template": True},
        {"setup": "anatomical_cutaway_3d", "framing": "ECU_XRay", "angle": "frontal_medical_orbit", "move": "focus_push_to_organ", "transition": "cut_on_action", "novel_non_template": True},
        {"setup": "hook_3d_action_launch", "framing": "MS", "angle": "three_quarter_hero", "move": "dolly_push_in", "transition": "cut_on_action"},
        {"setup": "belief_studio_demonstration", "framing": "WS", "angle": "low_studio_orbit", "move": "orbit_right", "transition": "dip_to_black"},
        {"setup": "novel_slowmo_ripple_cutaway", "framing": "ECU_Macro", "angle": "projectile_tracking_side", "move": "slowmo_track_impact", "transition": "cut_on_action", "novel_non_template": True},
        {"setup": "mechanism_cross_section_3d", "framing": "MS_Cutaway", "angle": "elevated_isometric", "move": "push_toward_core", "transition": "cut_on_action", "novel_non_template": True},
        {"setup": "payoff_full_stage_reveal", "framing": "WS", "angle": "eye_level_clean", "move": "pull_back_crane", "transition": "cut"},
    ],
    "graph": [
        {"setup": "hook_metric_counter_intro", "framing": "Macro_Header", "angle": "flat_editorial", "move": "grid_reveal", "transition": "match_zoom"},
        {"setup": "early_baseline_zoom", "framing": "CU_Curve_Origin", "angle": "flat_editorial", "move": "follow_tip_pan", "transition": "match_zoom"},
        {"setup": "novel_inflection_tangent_delta", "framing": "MS_Inflection_Split", "angle": "flat_editorial", "move": "slope_highlight_sweep", "transition": "match_zoom", "novel_non_template": True},
        {"setup": "milestone_delta_spotlight", "framing": "MS_Evidence_Callout", "angle": "flat_editorial", "move": "pan_milestone_window", "transition": "match_zoom", "novel_non_template": True},
        {"setup": "payoff_full_horizon_curve", "framing": "WS_Full_Chart", "angle": "flat_editorial", "move": "settle_halo_drop", "transition": "cut"},
    ],
    "minimalistic-graphics": [
        {"setup": "hook_solitary_dot_pulse", "framing": "Center_Void", "angle": "flat_orthographic", "move": "breath_pulse", "transition": "cut_on_action"},
        {"setup": "novel_pendulum_or_labyrinth", "framing": "MS_Geometric", "angle": "flat_orthographic", "move": "arc_oscillation", "transition": "match_zoom", "novel_non_template": True},
        {"setup": "kinetic_balance_beam", "framing": "WS_Equilibrium", "angle": "flat_orthographic", "move": "fulcrum_tilt_shift", "transition": "match_zoom", "novel_non_template": True},
        {"setup": "rising_hairline_steps", "framing": "WS_Ascending", "angle": "flat_orthographic", "move": "parabolic_hop_climb", "transition": "cut_on_action"},
        {"setup": "payoff_orbital_sparks", "framing": "MS_Apex_Orbit", "angle": "flat_orthographic", "move": "radial_bloom_hold", "transition": "cut"},
    ],
    "map-route": [
        {"setup": "departure_street_level", "framing": "CU_Origin_Block", "angle": "low_chase_32deg", "move": "pull_from_start_disc", "transition": "match_zoom"},
        {"setup": "mid_route_bridge_crossing", "framing": "MS_Aerial_Chase", "angle": "aerial_40deg_swing", "move": "ride_behind_route_head", "transition": "match_zoom", "novel_non_template": True},
        {"setup": "turn_park_corridor", "framing": "MS_Corner_Bank", "angle": "banked_aerial_35deg", "move": "corner_arc_track", "transition": "match_zoom"},
        {"setup": "street_canopy_altitude_shift", "framing": "MS_Wide_Altitude", "angle": "elevated_oblique_50deg", "move": "climb_altitude_sweep", "transition": "match_zoom", "novel_non_template": True},
        {"setup": "arrival_pin_drop_pullback", "framing": "WS_Overview_Card", "angle": "high_overview_28deg", "move": "crane_pullback_reveal", "transition": "cut"},
    ],
    "breakdown": [
        {"setup": "assembled_hero_silhouette", "framing": "MS_Studio_Hero", "angle": "three_quarter_rim", "move": "slow_turntable_intro", "transition": "match_zoom"},
        {"setup": "axial_layer_separation", "framing": "MS_Exploding_Stack", "angle": "elevated_30deg", "move": "dolly_out_with_explosion", "transition": "match_zoom"},
        {"setup": "novel_internal_core_macro", "framing": "ECU_Internal_Core", "angle": "macro_oblique_22deg", "move": "focus_sweep_across_core", "transition": "match_zoom", "novel_non_template": True},
        {"setup": "top_down_subsystem_orbit", "framing": "MS_High_Subsystem", "angle": "top_oblique_52deg", "move": "orbit_subsystem_inspect", "transition": "match_zoom", "novel_non_template": True},
        {"setup": "full_annotated_callout_stack", "framing": "WS_Labelled_Column", "angle": "offset_callout_frame", "move": "turntable_hold", "transition": "cut"},
    ],
}


def build_storyboard_and_bible(
    parsed_script: Dict[str, Any],
    style_decisions: Dict[str, Any],
    run_dir: Path,
    fps: int = 30,
    seed: int = 42,
    target_min_duration: float = 0.0,
    edit_energy: str = "balanced",
    scene_novelty: str = "standard",
    transition_policy: str = "motivated",
    max_static_hold_sec: Optional[float] = None,
    existing_visual_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Produce STEP 3 `storyboard.json`, `art_bible.md`, and visual direction artifacts."""
    selected_skill = style_decisions["selected_skill"]
    style_params = build_style_params(selected_skill, seed=seed)

    # 1. Semantic Visual Event Graph (`visual_events.json`)
    visual_events = extract_semantic_visual_events(
        parsed_script=parsed_script,
        storyboard_context={
            "selected_skill": selected_skill,
            "target_min_duration": target_min_duration,
            "tail_hold_sec": 0.75,
        },
        fps=fps,
        seed=seed,
        selected_skill=selected_skill,
    )
    write_visual_events_artifact(visual_events, run_dir)

    # 2. Variable-Length Novel Shot Coverage (`shot_coverage.json`)
    coverage = plan_editorial_coverage(
        visual_events=visual_events,
        parsed_script=parsed_script,
        selected_skill=selected_skill,
        fps=fps,
        seed=seed,
        preset=edit_energy,
        edit_energy=edit_energy,
        scene_novelty=scene_novelty,
        transition_policy=transition_policy,
        max_static_hold_sec=max_static_hold_sec,
        existing_visual_plan=existing_visual_plan,
        run_dir=run_dir,
    )
    raw_shots = coverage["shots"]

    # 3. Entity & Character Registry Compilation (`scene_asset_factory.py`) BEFORE camera planning
    #    so camera choreography uses real scene focal anchors, bounds & colliders.
    entity_inventory = compile_scene_entities(
        event_graph=visual_events,
        selected_skill=selected_skill,
        seed=seed,
    )
    for sc in raw_shots:
        pre_mat = materialize_engine_scene(sc, entity_inventory, selected_skill=selected_skill, camera_path=None)
        sc["procedural_generator"] = pre_mat["procedural_generator"]
        sc["representation"] = pre_mat.get("representation", "stylized_schematic")
        sc["focal_anchor"] = pre_mat.get("focal_anchor")
        if pre_mat.get("character_id") and not sc.get("staging", {}).get("character_id"):
            sc.setdefault("staging", {})["character_id"] = pre_mat["character_id"]

    # 4. Camera Choreography (`camera_paths.json`) & Transition EDL (`transition_edl.json`)
    camera_plan = build_camera_plan(
        shots=raw_shots,
        selected_skill=selected_skill,
        fps=fps,
        seed=seed,
        event_graph=visual_events,
        run_dir=run_dir,
    )
    transition_edl = emit_transition_edl(
        shots=raw_shots,
        camera_plan=camera_plan,
        selected_skill=selected_skill,
        fps=fps,
        mode=transition_policy,
        run_dir=run_dir,
    )
    cam_by_id = {p["shot_id"]: p for p in camera_plan["paths"]}

    shots: List[Dict[str, Any]] = []
    visual_assets: List[Dict[str, Any]] = []
    for i, s in enumerate(raw_shots):
        sc = dict(s)
        cp = cam_by_id.get(sc["shot_id"])
        mat = materialize_engine_scene(sc, entity_inventory, selected_skill=selected_skill, camera_path=cp)
        sc["procedural_generator"] = mat["procedural_generator"]
        sc["representation"] = mat.get("representation", "stylized_schematic")
        sc["focal_anchor"] = mat.get("focal_anchor")
        sc["camera_path"] = cp
        sc["speed_ramp"] = (
            {"enabled": True, "slow_window_norm": [0.42, 0.72], "factor": 0.45}
            if sc.get("novel_non_template") or ("turn" in sc["beat_role"] or "impact" in sc["staging"]["verb_action"])
            else {"enabled": False, "factor": 1.0}
        )
        asset_id = f"asset_{selected_skill.replace('-', '_')}_shot_{i:02d}"
        sc["asset_refs"] = [asset_id]
        sc["safe_zone"] = {
            "x_min": 100, "x_max": 980,
            "y_min": 220, "y_max": 1500,
            "caption_band_y": [1250, 1430],
        }
        shots.append(sc)

        visual_assets.append({
            "asset_id": asset_id,
            "shot_index": i,
            "origin_skill": selected_skill,
            "generator_module": f"director/assets/{selected_skill.replace('-', '_')}_adapter.py",
            "setup_type": sc["setup_type"],
            "procedural_generator": mat["procedural_generator"],
            "representation": mat.get("representation", "stylized_schematic"),
            "scene_family": mat["scene_family"],
            "novel_non_template": bool(sc.get("novel_non_template", False)),
            "motifs": list(sc["staging"].get("grounded_props", [mat["prop_id"]])),
            "deterministic_seed": seed + i * 101,
        })

    entity_check = validate_entity_continuity(shots, entity_inventory, selected_skill=selected_skill)
    total_duration = float(visual_events["total_duration_sec"])

    storyboard: Dict[str, Any] = {
        "schema_version": "0.5.0",
        "selection_mode": style_decisions["selection_mode"],
        "selected_skill": selected_skill,
        "style_lock": style_decisions["style_lock"],
        "origin_skills": [selected_skill],
        "seed": seed,
        "fps": fps,
        "aspect_ratio": "9:16",
        "preview_resolution": [1080, 1920],
        "final_resolution": [2160, 3840],
        "total_duration_sec": round(total_duration, 3),
        "edit_energy": coverage["edit_energy"],
        "scene_novelty": scene_novelty,
        "transition_policy": transition_policy,
        "max_static_hold_sec": coverage.get("max_static_hold_sec"),
        "character_registry": entity_inventory.get("character_registry", {}),
        "prop_registry": entity_inventory.get("prop_registry", {}),
        "style_adapter_params": style_params.to_dict(),
        "entities_and_facts": parsed_script["entities_and_facts"],
        "visual_events_summary": {
            "event_count": len(visual_events["events"]),
            "unique_scene_families": visual_events["unique_scene_families"],
            "factual_disclosures": visual_events["factual_disclosures"],
        },
        "diversity_summary": coverage["diversity_summary"],
        "entity_continuity": entity_check,
        "transition_edl_summary": {
            "transitions_count": transition_edl["transitions_count"],
            "methods": [t["actual_method"] for t in transition_edl["transitions"]],
        },
        "visual_assets": visual_assets,
        "shots": shots,
    }

    (run_dir / "storyboard.json").write_text(json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")

    # Write human-readable Art Bible
    bible_lines = [
        f"# Art Bible — Short Director Run (`{selected_skill}`)",
        "",
        "## 1. Strict Single-Skill Visual Lock",
        f"- **Selection Mode**: `{style_decisions['selection_mode']}`",
        f"- **Locked Engine**: `{selected_skill}`",
        "- **Mixing Policy**: `forbidden` (0 guest shots, 0 secondary skill assets, fail-closed)",
        f"- **Edit Energy / Scene Novelty / Transitions**: `{coverage['edit_energy']}` / `{scene_novelty}` / `{transition_policy}`",
        f"- **Silhouette Language**: `{style_params.silhouette_language}`",
        f"- **Lighting Preset**: `{style_params.lighting_preset}`",
        f"- **Texture & Grain**: `{style_params.texture_treatment}` (grain={style_params.grain_amount}, vignette={style_params.vignette_strength})",
        "",
        "## 2. Color Palette & Typography",
        f"- **Palette**: `{json.dumps(style_params.palette)}`",
        f"- **Caption Typography**: `{json.dumps(style_params.caption_style)}`",
        "- **Safe Area**: `x in [100, 980]`, `y in [220, 1500]` (1080x1920 logical space; scaled 2x to `2160x3840` for 4K).",
        "",
        "## 3. Continuous Shot Coverage & Scene Novelty Matrix",
        "| Shot | Time (s) | Scene Family / Generator | Framing / Camera Move | Transition | Intra-Shot Events |",
        "|---|---|---|---|---|---|",
    ]
    for s in shots:
        bible_lines.append(
            f"| `{s['shot_id']}` | {s['start']:.2f}–{s['end']:.2f} | `{s['scene_family']}` / `{s['procedural_generator']}` | "
            f"{s['camera']['framing']} / {s['camera']['movement']} | `{s['transition_out']}` | {len(s.get('intra_shot_events', []))} |"
        )

    bible_lines.extend(["", "## 4. Factual, Conceptual & Licensing Disclosures"])
    for fc in parsed_script["entities_and_facts"]["fact_checks"]:
        bible_lines.append(f"- **{fc.get('rule', fc.get('type', 'check'))}**: `{fc.get('status')}` — {fc.get('note', '')}")
    for disc in visual_events.get("factual_disclosures", []):
        bible_lines.append(f"- **Visual Disclosure**: {disc}")

    (run_dir / "art_bible.md").write_text("\n".join(bible_lines) + "\n", encoding="utf-8")
    return storyboard
