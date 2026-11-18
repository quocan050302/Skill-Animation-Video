"""STEP 4A (ZDF-MOTION-01): Procedural Scene Entity Compiler, Archetype & Character Registry, and Bounds Validator.

Compiles `VisualEventGraph` entities into typed procedural asset blueprints strictly within the
locked `selected_skill`, maintaining persistent `character_registry` / `prop_registry` across shots,
explicitly rejecting or truthfully labeling unsupported exact mechanisms (`UNSUPPORTED_SCENE_REQUIRED`),
and never falling back to Roman armor on non-Roman shots.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from . import VALID_SKILLS


class UnsupportedSceneError(RuntimeError):
    """Fail-closed exception when a scene cannot be rendered honestly in the locked engine."""


# Parametric 3D / 2D bounding extents (width, height, depth in logical meters or view coords)
ENTITY_BOUNDS_M: Dict[str, Tuple[float, float, float]] = {
    "elevator_button": (0.85, 1.72, 0.70),
    "controller_pcb": (0.68, 0.85, 0.42),
    "traction_motor_sheave": (1.45, 1.35, 1.15),
    "shaft_car_counterweight": (1.55, 2.25, 1.15),
    "elevator_doors": (1.40, 2.15, 0.80),
    "schematic_mechanism": (1.10, 1.35, 0.80),
    "phone_screen": (0.55, 1.55, 0.50),
    "microchip_pcb": (0.48, 0.56, 0.32),
    "battery_cell": (0.36, 0.56, 0.24),
    "cell_tower_wave": (0.90, 2.20, 0.90),
    "subsea_fiber_cable": (2.20, 0.80, 1.20),
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
    "tacoma_bridge_hook_rig": (6.5, 4.8, 1.8),
    "tacoma_wide_establish_rig": (14.5, 5.2, 2.2),
    "tacoma_roadway_wave_rig": (8.5, 4.6, 1.8),
    "tacoma_girder_wind_rig": (6.5, 3.6, 2.2),
    "tacoma_torsion_span_rig": (9.5, 4.6, 2.0),
    "tacoma_shore_onlooker_rig": (2.8, 2.2, 4.5),
    "tacoma_collapse_span_rig": (10.5, 5.5, 2.4),
    "tacoma_aftermath_rig": (14.5, 5.2, 2.2),
    "skyscraper_street_hook_rig": (3.2, 8.8, 3.2),
    "skyscraper_skyline_wide_rig": (4.5, 9.2, 4.5),
    "skyscraper_wind_vortex_rig": (3.6, 8.8, 3.2),
    "skyscraper_plumb_drift_rig": (3.2, 9.0, 2.8),
    "skyscraper_office_interior_rig": (3.8, 2.8, 3.6),
    "skyscraper_tmd_cutaway_rig": (2.6, 2.9, 2.4),
    "skyscraper_counterphase_rig": (2.8, 2.9, 2.4),
    "skyscraper_before_after_rig": (4.2, 6.8, 2.4),
    "skyscraper_dusk_resolution_rig": (4.5, 9.2, 4.5),
    "fog_street_hook_rig": (9.0, 5.2, 12.0),
    "coal_combustion_cutaway_rig": (2.8, 3.6, 2.4),
    "atmospheric_inversion_rig": (10.5, 6.8, 7.5),
    "bus_visibility_dropoff_rig": (4.6, 3.2, 8.2),
    "pedestrian_smog_reaction_rig": (2.8, 2.4, 4.0),
    "clean_air_aftermath_rig": (10.5, 6.8, 8.5),
}


# Explicit per-generator capabilities, real world focal anchors, scene bounds & colliders for ZDF 3D stages
ZDF_ARCHETYPE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "zach3d:airplane_window_hole_stage": {
        "capabilities": ["layered_cutaway", "multi_pane_window", "pierced_bleed_hole", "schematic_pressure_flow"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "middle_bleed_hole", "world_pos": [0.0, 1.065, 0.0], "radius_m": 0.032},
        "bounds": {"x_min": -2.4, "x_max": 2.4, "y_min": 0.12, "y_max": 3.2, "z_min": -1.8, "z_max": 3.8},
        "collider_boxes": [
            {"id": "fuselage_bulkhead_wall", "min": [-0.72, 0.30, -0.22], "max": [0.72, 2.20, -0.02]},
        ],
    },
    "zach3d:elevator_lobby_button_stage": {
        "capabilities": ["human_character", "arm_ik_contact", "physical_button_plunger"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "call_button_01", "world_pos": [0.24, 1.16, 0.24], "radius_m": 0.028},
        "bounds": {"x_min": -2.4, "x_max": 2.4, "y_min": 0.12, "y_max": 3.4, "z_min": -2.2, "z_max": 3.8},
        "collider_boxes": [
            {"id": "lobby_wall_panel", "min": [0.16, 0.0, -0.35], "max": [0.65, 2.4, 0.22]},
        ],
    },
    "zach3d:controller_cabinet_cutaway_stage": {
        "capabilities": ["layered_cutaway", "pcb_relays", "signal_flow"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "controller_pcb_core", "world_pos": [0.0, 1.24, 0.06], "radius_m": 0.18},
        "bounds": {"x_min": -2.2, "x_max": 2.2, "y_min": 0.12, "y_max": 3.2, "z_min": -1.8, "z_max": 3.6},
        "collider_boxes": [
            {"id": "cabinet_chassis", "min": [-0.32, 0.88, -0.18], "max": [0.32, 1.62, 0.04]},
        ],
    },
    "zach3d:traction_machine_room_stage": {
        "capabilities": ["layered_cutaway", "drive_motor", "traction_sheave", "brake_calipers"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "traction_sheave_hub", "world_pos": [0.06, 1.28, 0.0], "radius_m": 0.28},
        "bounds": {"x_min": -2.8, "x_max": 2.8, "y_min": 0.12, "y_max": 3.6, "z_min": -2.4, "z_max": 4.2},
        "collider_boxes": [
            {"id": "drive_bedplate", "min": [-0.75, 0.0, -0.55], "max": [0.75, 0.92, 0.55]},
        ],
    },
    "zach3d:elevator_shaft_cutaway_stage": {
        "capabilities": ["layered_cutaway", "counterweight_kinematics", "position_sensors"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "car_counterweight_span", "world_pos": [0.0, 1.24, 0.04], "radius_m": 0.36},
        "bounds": {"x_min": -3.2, "x_max": 3.2, "y_min": 0.12, "y_max": 4.0, "z_min": -2.4, "z_max": 4.8},
        "collider_boxes": [
            {"id": "shaft_backwall", "min": [-0.85, 0.0, -0.52], "max": [0.85, 2.7, -0.26]},
        ],
    },
    "zach3d:elevator_landing_doors_stage": {
        "capabilities": ["human_character", "leveling_interlock", "biparting_doors", "callback_reveal"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "landing_doors_center", "world_pos": [0.0, 1.18, 0.12], "radius_m": 0.35},
        "bounds": {"x_min": -3.0, "x_max": 3.0, "y_min": 0.12, "y_max": 3.6, "z_min": -2.2, "z_max": 4.4},
        "collider_boxes": [
            {"id": "landing_frame", "min": [-0.85, 0.0, -0.35], "max": [0.85, 2.45, 0.02]},
        ],
    },
    "zach3d:schematic_mechanism_stage": {
        "capabilities": ["stylized_schematic", "generic_linkage"],
        "fidelity_mode": "stylized_schematic",
        "focal_anchor": {"anchor_id": "schematic_linkage_core", "world_pos": [0.0, 1.18, 0.05], "radius_m": 0.25},
        "bounds": {"x_min": -2.8, "x_max": 2.8, "y_min": 0.12, "y_max": 3.4, "z_min": -2.4, "z_max": 4.2},
        "collider_boxes": [],
    },
    "zach3d:human_device_stage": {
        "capabilities": ["human_character", "arm_ik_contact", "smartphone_rig"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "phone_tap_target", "world_pos": [0.24, 1.32, 0.28], "radius_m": 0.06},
        "bounds": {"x_min": -2.6, "x_max": 2.6, "y_min": 0.12, "y_max": 3.4, "z_min": -2.0, "z_max": 4.2},
        "collider_boxes": [],
    },
    "zach3d:device_cutaway_stage": {
        "capabilities": ["layered_cutaway", "smartphone_internals"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "device_pcb_core", "world_pos": [0.0, 1.24, 0.02], "radius_m": 0.18},
        "bounds": {"x_min": -2.4, "x_max": 2.4, "y_min": 0.12, "y_max": 3.2, "z_min": -2.0, "z_max": 4.0},
        "collider_boxes": [],
    },
    "zach3d:network_relay_stage": {
        "capabilities": ["radio_tower", "rf_wavefronts"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "tower_beacon", "world_pos": [0.0, 1.85, 0.0], "radius_m": 0.25},
        "bounds": {"x_min": -3.5, "x_max": 3.5, "y_min": 0.12, "y_max": 4.5, "z_min": -3.5, "z_max": 5.0},
        "collider_boxes": [],
    },
    "zach3d:subsea_fiber_stage": {
        "capabilities": ["layered_cutaway", "subsea_cable", "photon_flow"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "fiber_glass_core", "world_pos": [0.0, 0.38, 0.0], "radius_m": 0.20},
        "bounds": {"x_min": -3.5, "x_max": 3.5, "y_min": 0.12, "y_max": 3.4, "z_min": -3.2, "z_max": 4.8},
        "collider_boxes": [],
    },
    "zach3d:datacenter_aisle_stage": {
        "capabilities": ["server_racks", "packet_flow"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "datacenter_trunk", "world_pos": [0.0, 1.25, -0.90], "radius_m": 0.40},
        "bounds": {"x_min": -3.2, "x_max": 3.2, "y_min": 0.12, "y_max": 3.8, "z_min": -3.8, "z_max": 4.8},
        "collider_boxes": [],
    },
    "zach3d:power_turbine_stage": {
        "capabilities": ["spinning_rotor", "induction_coils"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "turbine_rotor_hub", "world_pos": [0.0, 1.15, 0.0], "radius_m": 0.30},
        "bounds": {"x_min": -3.0, "x_max": 3.0, "y_min": 0.12, "y_max": 3.4, "z_min": -2.8, "z_max": 4.2},
        "collider_boxes": [],
    },
    "zach3d:cosmic_scale_bridge_stage": {
        "capabilities": ["celestial_orbits", "stylized_scale_bridge"],
        "fidelity_mode": "stylized_schematic",
        "focal_anchor": {"anchor_id": "stellar_core", "world_pos": [0.0, 1.25, 0.0], "radius_m": 0.38},
        "bounds": {"x_min": -4.5, "x_max": 4.5, "y_min": 0.12, "y_max": 4.8, "z_min": -4.5, "z_max": 5.5},
        "collider_boxes": [],
    },
    "zach3d:anatomical_cutaway_stage": {
        "capabilities": ["layered_cutaway", "stylized_organ"],
        "fidelity_mode": "stylized_schematic",
        "focal_anchor": {"anchor_id": "organ_core", "world_pos": [0.0, 1.25, 0.02], "radius_m": 0.24},
        "bounds": {"x_min": -2.6, "x_max": 2.6, "y_min": 0.12, "y_max": 3.2, "z_min": -2.2, "z_max": 3.8},
        "collider_boxes": [],
    },
    "zach3d:roman_historical_stage": {
        "capabilities": ["roman_arena", "gladiator_rig", "roman_props"],
        "fidelity_mode": "exact_archetype",
        "focal_anchor": {"anchor_id": "arena_center", "world_pos": [0.0, 0.96, 0.08], "radius_m": 0.45},
        "bounds": {"x_min": -4.2, "x_max": 4.2, "y_min": 0.12, "y_max": 3.8, "z_min": -4.2, "z_max": 5.2},
        "collider_boxes": [],
    },
    "zach3d:boston_street_hook_stage": {
        "capabilities": ["north_end_1919", "brick_storefronts", "horse_cart_1919", "period_crowd"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "street_hero_look", "world_pos": [0.0, 1.35, 0.20], "radius_m": 0.48},
        "bounds": {"x_min": -5.0, "x_max": 5.0, "y_min": 0.12, "y_max": 4.8, "z_min": -6.0, "z_max": 6.2},
        "collider_boxes": [],
    },
    "zach3d:boston_molasses_reveal_stage": {
        "capabilities": ["alley_reveal", "viscous_molasses_front", "dark_tank_silhouette"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "molasses_reveal_crest", "world_pos": [0.0, 1.25, 0.15], "radius_m": 0.50},
        "bounds": {"x_min": -4.8, "x_max": 4.8, "y_min": 0.12, "y_max": 4.8, "z_min": -5.5, "z_max": 5.8},
        "collider_boxes": [],
    },
    "zach3d:boston_tank_leak_stage": {
        "capabilities": ["riveted_tank_wall", "viscous_seep_drips", "dock_worker_1919"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "tank_seam_drip", "world_pos": [-0.25, 1.15, 0.65], "radius_m": 0.35},
        "bounds": {"x_min": -4.5, "x_max": 4.5, "y_min": 0.12, "y_max": 5.2, "z_min": -5.0, "z_max": 5.8},
        "collider_boxes": [],
    },
    "zach3d:boston_tank_rupture_stage": {
        "capabilities": ["riveted_seam_failure", "plate_split", "shear_rivet_ejection", "initial_surge"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "tank_rivet_seam", "world_pos": [0.0, 1.32, 0.45], "radius_m": 0.42},
        "bounds": {"x_min": -4.8, "x_max": 4.8, "y_min": 0.12, "y_max": 5.2, "z_min": -5.2, "z_max": 5.8},
        "collider_boxes": [],
    },
    "zach3d:boston_wave_street_stage": {
        "capabilities": ["gravity_current_wave", "commercial_street_corridor", "period_crowd_retreat", "debris_rafts"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "wave_front_crest", "world_pos": [0.0, 1.15, 0.40], "radius_m": 0.55},
        "bounds": {"x_min": -5.8, "x_max": 5.8, "y_min": 0.12, "y_max": 4.8, "z_min": -6.2, "z_max": 6.4},
        "collider_boxes": [],
    },
    "zach3d:boston_elevated_rail_impact_stage": {
        "capabilities": ["elevated_railway_truss", "delivery_wagon", "structural_deflection"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "elevated_rail_column", "world_pos": [0.12, 1.48, 0.10], "radius_m": 0.48},
        "bounds": {"x_min": -5.2, "x_max": 5.2, "y_min": 0.12, "y_max": 5.8, "z_min": -5.8, "z_max": 6.0},
        "collider_boxes": [],
    },
    "zach3d:boston_rescue_aftermath_stage": {
        "capabilities": ["calm_sludge_field", "rescue_responders_1919", "lantern_lighting"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "rescue_aftermath_center", "world_pos": [0.0, 0.92, 0.20], "radius_m": 0.52},
        "bounds": {"x_min": -5.0, "x_max": 5.0, "y_min": 0.12, "y_max": 4.5, "z_min": -5.5, "z_max": 5.8},
        "collider_boxes": [],
    },
    "zach3d:boston_engineering_cutaway_stage": {
        "capabilities": ["steel_plate_cutaway", "lap_joint_strain", "rivet_failure_zones"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "lap_joint_defect", "world_pos": [0.0, 1.24, 0.08], "radius_m": 0.28},
        "bounds": {"x_min": -3.4, "x_max": 3.4, "y_min": 0.12, "y_max": 3.8, "z_min": -3.2, "z_max": 4.5},
        "collider_boxes": [],
    },
    "zach3d:boston_harbor_payoff_stage": {
        "capabilities": ["north_end_wharf_overview", "harbor_skyline_1919", "memorial_footprint"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "boston_overview_center", "world_pos": [0.0, 1.10, -0.35], "radius_m": 0.60},
        "bounds": {"x_min": -6.8, "x_max": 6.8, "y_min": 0.12, "y_max": 6.8, "z_min": -6.8, "z_max": 7.2},
        "collider_boxes": [],
    },
    "zach3d:tacoma_hook_telephoto_stage": {
        "capabilities": ["suspension_bridge_span", "torsion_wobble", "suspender_cables_coupled"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "bridge_midspan_twist", "world_pos": [0.0, 2.50, 0.0], "radius_m": 0.65},
        "bounds": {"x_min": -10.5, "x_max": 10.5, "y_min": 0.12, "y_max": 8.0, "z_min": -6.0, "z_max": 10.5},
        "collider_boxes": [],
    },
    "zach3d:tacoma_wide_establish_stage": {
        "capabilities": ["puget_sound_shores", "deco_towers", "period_car_1940"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "bridge_midspan_twist", "world_pos": [0.0, 2.60, 0.0], "radius_m": 0.90},
        "bounds": {"x_min": -12.0, "x_max": 12.0, "y_min": 0.12, "y_max": 10.0, "z_min": -8.0, "z_max": 13.5},
        "collider_boxes": [],
    },
    "zach3d:tacoma_roadway_wave_stage": {
        "capabilities": ["vertical_standing_wave", "period_car_1940", "coupled_suspenders"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "bridge_midspan_twist", "world_pos": [0.0, 2.55, 0.0], "radius_m": 0.70},
        "bounds": {"x_min": -10.0, "x_max": 10.0, "y_min": 0.12, "y_max": 7.5, "z_min": -6.5, "z_max": 8.5},
        "collider_boxes": [],
    },
    "zach3d:tacoma_under_deck_girder_stage": {
        "capabilities": ["solid_plate_girder_8ft", "illustrative_wind_streams"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "plate_girder_windward", "world_pos": [0.0, 2.38, 0.60], "radius_m": 0.45},
        "bounds": {"x_min": -9.0, "x_max": 9.0, "y_min": 0.25, "y_max": 6.5, "z_min": -5.5, "z_max": 6.5},
        "collider_boxes": [],
    },
    "zach3d:tacoma_torsion_twist_stage": {
        "capabilities": ["asymmetric_deck_torsion", "coupled_suspender_cables", "period_car_1940"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "deck_twist_edge_l", "world_pos": [0.0, 2.55, 0.60], "radius_m": 0.55},
        "bounds": {"x_min": -10.5, "x_max": 10.5, "y_min": 0.12, "y_max": 7.5, "z_min": -6.5, "z_max": 8.5},
        "collider_boxes": [],
    },
    "zach3d:tacoma_shore_onlooker_stage": {
        "capabilities": ["grounded_human_1940", "foot_lock_retreat", "background_twisting_bridge"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "shore_onlooker_head", "world_pos": [0.35, 1.55, 0.65], "radius_m": 0.35},
        "bounds": {"x_min": -11.0, "x_max": 11.0, "y_min": 0.12, "y_max": 7.5, "z_min": -12.0, "z_max": 6.5},
        "collider_boxes": [],
    },
    "zach3d:tacoma_collapse_plunge_stage": {
        "capabilities": ["staged_span_collapse", "water_splash_ring", "free_fall_trajectory"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "collapse_break_seam", "world_pos": [-1.2, 2.25, 0.2], "radius_m": 0.70},
        "bounds": {"x_min": -12.0, "x_max": 12.0, "y_min": 0.12, "y_max": 9.5, "z_min": -8.0, "z_max": 12.0},
        "collider_boxes": [],
    },
    "zach3d:tacoma_aftermath_stage": {
        "capabilities": ["broken_center_span", "standing_towers", "calm_puget_sound"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "aftermath_broken_gap", "world_pos": [0.0, 2.45, 0.0], "radius_m": 0.90},
        "bounds": {"x_min": -12.0, "x_max": 12.0, "y_min": 0.12, "y_max": 10.5, "z_min": -8.5, "z_max": 14.0},
        "collider_boxes": [],
    },
    "zach3d:skyscraper_street_hook_stage": {
        "capabilities": ["flexing_tower_tiers", "static_reference_tower", "street_observer_human"],
        "fidelity_mode": "stylized_illustrative",
        "focal_anchor": {"anchor_id": "rooftop_sway_apex", "world_pos": [-0.25, 7.6, -3.2], "radius_m": 0.75},
        "bounds": {"x_min": -6.0, "x_max": 6.0, "y_min": 0.12, "y_max": 10.5, "z_min": -6.0, "z_max": 8.5},
        "collider_boxes": [],
    },
    "zach3d:skyscraper_skyline_wide_stage": {
        "capabilities": ["city_skyline_blocks", "moving_vehicles", "flexing_tower_tiers"],
        "fidelity_mode": "stylized_illustrative",
        "focal_anchor": {"anchor_id": "tower_mid_profile", "world_pos": [0.0, 5.4, -0.4], "radius_m": 0.85},
        "bounds": {"x_min": -10.0, "x_max": 10.0, "y_min": 0.12, "y_max": 12.5, "z_min": -8.0, "z_max": 13.5},
        "collider_boxes": [],
    },
    "zach3d:skyscraper_wind_vortex_stage": {
        "capabilities": ["windward_vortex_ribbons", "flexing_tower_tiers"],
        "fidelity_mode": "stylized_illustrative",
        "focal_anchor": {"anchor_id": "windward_facade_vortex", "world_pos": [0.0, 5.6, -0.4], "radius_m": 0.75},
        "bounds": {"x_min": -8.0, "x_max": 8.0, "y_min": 0.12, "y_max": 11.5, "z_min": -6.5, "z_max": 9.5},
        "collider_boxes": [],
    },
    "zach3d:skyscraper_plumb_drift_stage": {
        "capabilities": ["plumb_reference_mast", "lateral_cantilever_flex"],
        "fidelity_mode": "stylized_illustrative",
        "focal_anchor": {"anchor_id": "plumb_drift_tip", "world_pos": [0.0, 7.8, -1.0], "radius_m": 0.65},
        "bounds": {"x_min": -7.5, "x_max": 7.5, "y_min": 0.12, "y_max": 11.5, "z_min": -6.5, "z_max": 9.5},
        "collider_boxes": [],
    },
    "zach3d:skyscraper_office_interior_stage": {
        "capabilities": ["office_interior", "swinging_pendant_lamp", "shifting_window_horizon", "worker_brace_reaction"],
        "fidelity_mode": "stylized_illustrative",
        "focal_anchor": {"anchor_id": "office_pendant_lamp", "world_pos": [-0.35, 1.76, -0.15], "radius_m": 0.35},
        "bounds": {"x_min": -4.0, "x_max": 4.0, "y_min": 0.12, "y_max": 2.9, "z_min": -2.5, "z_max": 4.2},
        "collider_boxes": [],
    },
    "zach3d:skyscraper_tmd_cutaway_stage": {
        "capabilities": ["layered_cutaway", "tuned_mass_damper_sphere", "hydraulic_pistons"],
        "fidelity_mode": "stylized_illustrative",
        "focal_anchor": {"anchor_id": "damper_pendulum_sphere", "world_pos": [0.0, 1.32, 0.25], "radius_m": 0.55},
        "bounds": {"x_min": -5.0, "x_max": 5.0, "y_min": 0.12, "y_max": 5.0, "z_min": -4.0, "z_max": 6.5},
        "collider_boxes": [],
    },
    "zach3d:skyscraper_counterphase_stage": {
        "capabilities": ["counterphase_oscillation", "opposing_force_bars", "hydraulic_pistons"],
        "fidelity_mode": "stylized_illustrative",
        "focal_anchor": {"anchor_id": "counterphase_tower_frame", "world_pos": [0.0, 2.45, 0.5], "radius_m": 0.60},
        "bounds": {"x_min": -5.0, "x_max": 5.0, "y_min": 0.12, "y_max": 5.0, "z_min": -4.0, "z_max": 6.5},
        "collider_boxes": [],
    },
    "zach3d:skyscraper_before_after_stage": {
        "capabilities": ["split_undamped_vs_damped_towers", "amplitude_contrast"],
        "fidelity_mode": "stylized_illustrative",
        "focal_anchor": {"anchor_id": "damped_tower_top", "world_pos": [1.35, 6.2, 0.0], "radius_m": 0.70},
        "bounds": {"x_min": -9.0, "x_max": 9.0, "y_min": 0.12, "y_max": 10.5, "z_min": -6.0, "z_max": 12.5},
        "collider_boxes": [],
    },
    "zach3d:skyscraper_dusk_resolution_stage": {
        "capabilities": ["dusk_skyline_overview", "gentle_controlled_flex"],
        "fidelity_mode": "stylized_illustrative",
        "focal_anchor": {"anchor_id": "rooftop_sway_apex", "world_pos": [0.0, 6.8, -1.2], "radius_m": 0.85},
        "bounds": {"x_min": -10.5, "x_max": 10.5, "y_min": 0.12, "y_max": 12.5, "z_min": -8.0, "z_max": 13.5},
        "collider_boxes": [],
    },
    "zach3d:london_fog_street_hook_stage": {
        "capabilities": ["london_1952_street", "streetlamp_halo_visibility", "volumetric_smog_front"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "streetlamp_halo_visibility", "world_pos": [0.25, 2.35, -1.2], "radius_m": 0.55},
        "bounds": {"x_min": -7.5, "x_max": 7.5, "y_min": 0.12, "y_max": 8.0, "z_min": -8.0, "z_max": 10.0},
        "collider_boxes": [],
    },
    "zach3d:london_coal_combustion_cutaway_stage": {
        "capabilities": ["layered_cutaway", "coal_firebox_cutaway", "sulfur_soot_plume"],
        "fidelity_mode": "stylized_illustrative",
        "focal_anchor": {"anchor_id": "chimney_flue_combustion", "world_pos": [0.0, 1.55, 0.0], "radius_m": 0.45},
        "bounds": {"x_min": -4.5, "x_max": 4.5, "y_min": 0.12, "y_max": 6.2, "z_min": -4.5, "z_max": 6.5},
        "collider_boxes": [],
    },
    "zach3d:london_atmospheric_inversion_stage": {
        "capabilities": ["warm_inversion_air_layer", "cold_ground_air", "deflected_smoke_streamlines", "illustrative_airflow_label"],
        "fidelity_mode": "stylized_illustrative",
        "focal_anchor": {"anchor_id": "inversion_thermal_boundary", "world_pos": [0.0, 3.15, -0.6], "radius_m": 0.85},
        "bounds": {"x_min": -9.5, "x_max": 9.5, "y_min": 0.12, "y_max": 8.5, "z_min": -7.5, "z_max": 10.5},
        "collider_boxes": [],
    },
    "zach3d:london_bus_visibility_stage": {
        "capabilities": ["double_decker_bus_1952", "headlight_scatter_cone", "pedestrian_guide_lantern", "visibility_obscuration"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "bus_headlight_cone", "world_pos": [0.35, 1.15, 1.4], "radius_m": 0.65},
        "bounds": {"x_min": -7.5, "x_max": 7.5, "y_min": 0.12, "y_max": 6.5, "z_min": -8.0, "z_max": 10.0},
        "collider_boxes": [],
    },
    "zach3d:london_pedestrian_reaction_stage": {
        "capabilities": ["human_character", "foot_grounded_cough_brace", "streetlamp_halo_visibility", "smog_aerosol_density"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "pedestrian_respiratory_stance_zone", "world_pos": [0.0, 1.42, 0.25], "radius_m": 0.40},
        "bounds": {"x_min": -5.5, "x_max": 5.5, "y_min": 0.12, "y_max": 5.8, "z_min": -5.5, "z_max": 7.5},
        "collider_boxes": [],
    },
    "zach3d:london_clean_air_aftermath_stage": {
        "capabilities": ["smokeless_hearth_transition", "reappearing_st_pauls_dome", "before_after_skyline"],
        "fidelity_mode": "stylized_historical",
        "focal_anchor": {"anchor_id": "smokeless_hearth_transition", "world_pos": [0.0, 2.45, -1.6], "radius_m": 0.85},
        "bounds": {"x_min": -9.5, "x_max": 9.5, "y_min": 0.12, "y_max": 8.8, "z_min": -9.0, "z_max": 11.0},
        "collider_boxes": [],
    },
    "zach3d:studio_demonstrator_stage": {
        "capabilities": ["human_character", "studio_gear_pedestal"],
        "fidelity_mode": "stylized_schematic",
        "focal_anchor": {"anchor_id": "studio_core", "world_pos": [0.06, 1.18, 0.06], "radius_m": 0.26},
        "bounds": {"x_min": -2.8, "x_max": 2.8, "y_min": 0.12, "y_max": 3.4, "z_min": -2.4, "z_max": 4.2},
        "collider_boxes": [],
    },
}


def build_character_and_prop_registry(
    event_graph: Dict[str, Any],
    selected_skill: str,
    seed: int = 42,
) -> Dict[str, Any]:
    """Build immutable per-run `character_registry` & `prop_registry` so identities stay locked across shots."""
    events = list(event_graph.get("events") or [])
    has_roman = any(ev.get("scene_family") == "roman_historical" for ev in events)
    has_boston = any(str(ev.get("scene_family") or "").startswith("boston_") for ev in events)
    has_tacoma = any(str(ev.get("scene_family") or "").startswith("tacoma_") for ev in events)
    has_skyscraper = any(str(ev.get("scene_family") or "").startswith("skyscraper_") for ev in events)
    has_smog_london = any(
        str(ev.get("scene_family") or "") in (
            "fog_street_hook", "coal_combustion_cutaway", "atmospheric_inversion_cap",
            "vehicle_visibility_dropoff", "pedestrian_smog_reaction", "air_quality_aftermath",
        )
        for ev in events
    )
    has_modern_human = (not has_boston and not has_tacoma and not has_skyscraper and not has_smog_london) and any(
        "human" in str(ev.get("subject", ""))
        or ev.get("scene_family") in ("human_device", "elevator_lobby_button", "elevator_landing_doors", "human_studio")
        for ev in events
    )

    characters: Dict[str, Dict[str, Any]] = {}
    if has_smog_london:
        characters["char_london_pedestrian_01"] = {
            "character_id": "char_london_pedestrian_01",
            "role": "london_pedestrian_1952",
            "outfit_style": "trenchcoat_scarf_1952",
            "height_m": 1.74,
            "scale": 1.0,
            "handedness": "right",
            "shirt_hex": 0x475569,
            "shirt_material_id": "mat_1952_trenchcoat_475569",
            "pants_hex": 0x1E293B,
            "collar_hex": 0x9F1239,
            "skin_hex": 0xD9A484,
            "allowed_states": ["walk_lantern_guide", "shield_airway_cough", "step_back_brace"],
        }
    elif has_skyscraper:
        characters["char_street_observer_01"] = {
            "character_id": "char_street_observer_01",
            "role": "street_observer",
            "outfit_style": "modern_casual_jacket",
            "height_m": 1.74,
            "scale": 1.0,
            "handedness": "right",
            "shirt_hex": 0x2563EB,
            "shirt_material_id": "mat_skyscraper_street_2563eb",
            "pants_hex": 0x1E293B,
            "collar_hex": 0xF1F5F9,
            "skin_hex": 0xD9A484,
            "allowed_states": ["notice_gaze", "step_back_brace", "braced_hold"],
        }
        characters["char_office_worker_01"] = {
            "character_id": "char_office_worker_01",
            "role": "office_worker",
            "outfit_style": "modern_office_shirt",
            "height_m": 1.74,
            "scale": 1.0,
            "handedness": "right",
            "shirt_hex": 0x0EA5E9,
            "shirt_material_id": "mat_skyscraper_office_0ea5e9",
            "pants_hex": 0x1E293B,
            "collar_hex": 0xF8FAFC,
            "skin_hex": 0xD9A484,
            "allowed_states": ["notice_gaze", "step_back_brace", "braced_hold"],
        }
    elif has_tacoma:
        characters["char_onlooker_1940_01"] = {
            "character_id": "char_onlooker_1940_01",
            "role": "shore_onlooker_1940",
            "outfit_style": "coat_and_fedora_1940",
            "height_m": 1.74,
            "scale": 1.0,
            "handedness": "right",
            "shirt_hex": 0x463D34,
            "shirt_material_id": "mat_1940_overcoat_463d34",
            "pants_hex": 0x26292E,
            "skin_hex": 0xD9A484,
            "allowed_states": ["notice_gaze", "step_back_brace", "braced_hold"],
        }
    elif has_boston:
        characters["char_resident_1919_01"] = {
            "character_id": "char_resident_1919_01",
            "role": "boston_resident_1919",
            "outfit_style": "wool_coat_1919",
            "height_m": 1.72,
            "scale": 1.0,
            "handedness": "right",
            "shirt_hex": 0x4A3F35,
            "shirt_material_id": "mat_1919_wool_4a3f35",
            "pants_hex": 0x2F2A26,
            "skin_hex": 0xD9A484,
            "allowed_states": ["street_walk_1919", "alarm_retreat"],
        }
        characters["char_worker_1919_01"] = {
            "character_id": "char_worker_1919_01",
            "role": "dock_worker_1919",
            "outfit_style": "canvas_apron_flatcap_1919",
            "height_m": 1.74,
            "scale": 1.0,
            "handedness": "right",
            "shirt_hex": 0x5A493A,
            "shirt_material_id": "mat_1919_canvas_5a493a",
            "pants_hex": 0x35322F,
            "skin_hex": 0xD69E7E,
            "allowed_states": ["inspect_leak", "step_back"],
        }
        characters["char_rescuer_1919_01"] = {
            "character_id": "char_rescuer_1919_01",
            "role": "rescue_responder_1919",
            "outfit_style": "heavy_greatcoat_1919",
            "height_m": 1.75,
            "scale": 1.0,
            "handedness": "right",
            "shirt_hex": 0x26323E,
            "shirt_material_id": "mat_1919_greatcoat_26323e",
            "pants_hex": 0x1E242B,
            "skin_hex": 0xD6A080,
            "allowed_states": ["lantern_search", "assist_aftermath"],
        }
    elif has_modern_human or selected_skill == "zach-d-films":
        # Immutable modern hero identity locked across every shot in the run (never shot_index % palette!)
        shirt_choices = [0x2563EB, 0x0D9488, 0x1D4ED8]
        shirt_hex = shirt_choices[abs(int(seed)) % len(shirt_choices)]
        characters["char_protagonist_01"] = {
            "character_id": "char_protagonist_01",
            "role": "protagonist",
            "outfit_style": "modern_jacket",
            "height_m": 1.72,
            "scale": 1.0,
            "handedness": "right",
            "shirt_hex": shirt_hex,
            "shirt_material_id": f"mat_shirt_{shirt_hex:06x}",
            "pants_hex": 0x1E293B,
            "collar_hex": 0xE2E8F0,
            "skin_hex": 0xD9A484,
            "hair_hex": 0x2B211C,
            "allowed_states": ["lobby_arrival", "button_press", "door_arrival_callback"],
        }

    if has_roman:
        characters["char_fighter_01"] = {
            "character_id": "char_fighter_01",
            "role": "roman_fighter",
            "outfit_style": "vest",
            "height_m": 1.74,
            "scale": 1.0,
            "handedness": "right",
            "crest_hex": 0xC92A2A,
            "shirt_material_id": "mat_roman_vest_c92a2a",
            "allowed_states": ["combat_ready", "fallen", "mercy_alive"],
        }
        characters["char_opponent_01"] = {
            "character_id": "char_opponent_01",
            "role": "roman_opponent",
            "outfit_style": "plate",
            "height_m": 1.78,
            "scale": 1.0,
            "handedness": "right",
            "crest_hex": 0xD9A441,
            "shirt_material_id": "mat_roman_plate_d9a441",
            "allowed_states": ["duel", "standing_over"],
        }
        characters["char_organizer_01"] = {
            "character_id": "char_organizer_01",
            "role": "roman_organizer",
            "outfit_style": "vest_toga",
            "height_m": 1.73,
            "scale": 1.0,
            "handedness": "right",
            "sash_hex": 0xA4161A,
            "shirt_material_id": "mat_roman_toga_a4161a",
            "allowed_states": ["contract_negotiation", "ledger_review"],
        }

    props: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        pid = str(ev.get("relevant_prop") or "idea_spark")
        if pid not in props:
            props[pid] = {
                "prop_id": pid,
                "canonical_material_id": f"mat_{pid}",
                "bounds_m": list(ENTITY_BOUNDS_M.get(pid, (1.0, 1.5, 1.0))),
                "immutable_scale": 1.0,
            }
    return {"characters": characters, "props": props}


def make_or_reuse_licensed_procedural_asset(
    entity_spec: Dict[str, Any],
    selected_skill: str,
    existing_registry: Dict[str, Dict[str, Any]],
    require_exact_scene: bool = False,
) -> Dict[str, Any]:
    """Register or reuse a deterministic procedural asset cleanly inside `selected_skill`."""
    prop = str(entity_spec.get("relevant_prop") or "idea_spark")
    fam = str(entity_spec.get("scene_family") or "human_studio")
    unsupported_domain = entity_spec.get("unsupported_exact_domain")
    key = f"{selected_skill}:{fam}:{prop}"

    if key in existing_registry:
        entry = dict(existing_registry[key])
        entry["reused_for_callback"] = True
        return entry

    gen = _map_family_to_generator(
        selected_skill, fam, prop, unsupported_exact_domain=unsupported_domain, require_exact_scene=require_exact_scene
    )
    reg_info = ZDF_ARCHETYPE_REGISTRY.get(gen, {})
    bounds = ENTITY_BOUNDS_M.get(prop, (1.0, 1.5, 1.0))
    representation = (
        "UNSUPPORTED_EXACT_ARCHETYPE_FALLBACK_SCHEMATIC"
        if unsupported_domain
        else reg_info.get("fidelity_mode", "stylized_schematic")
    )
    asset = {
        "asset_key": key,
        "origin_skill": selected_skill,
        "license_type": "procedural_mit_derived",
        "prop_id": prop,
        "scene_family": fam,
        "bounds_m": list(bounds),
        "procedural_generator": gen,
        "representation": representation,
        "unsupported_exact_domain": unsupported_domain,
        "focal_anchor": dict(reg_info.get("focal_anchor") or {"anchor_id": prop, "world_pos": [0.0, 1.18, 0.0], "radius_m": 0.25}),
        "scene_bounds": dict(reg_info.get("bounds") or {"x_min": -3.5, "x_max": 3.5, "y_min": 0.12, "y_max": 4.2, "z_min": -4.0, "z_max": 5.2}),
        "collider_boxes": list(reg_info.get("collider_boxes") or []),
        "reused_for_callback": False,
        "seed": int(entity_spec.get("seed", 42)),
    }
    existing_registry[key] = dict(asset)
    return asset


def _map_family_to_generator(
    selected_skill: str,
    fam: str,
    prop: str,
    unsupported_exact_domain: Optional[str] = None,
    require_exact_scene: bool = False,
) -> str:
    if selected_skill == "zach-d-films":
        if unsupported_exact_domain:
            if require_exact_scene:
                raise UnsupportedSceneError(
                    f"UNSUPPORTED_SCENE_REQUIRED: no exact 3D archetype exists in `zach-d-films` for domain '{unsupported_exact_domain}'."
                )
            return "zach3d:schematic_mechanism_stage"
        if fam in ("roman_historical",) or prop in ("roman_arena", "roman_ledger"):
            return "zach3d:roman_historical_stage"
        if fam == "boston_street_hook" or prop == "north_end_street_1919":
            return "zach3d:boston_street_hook_stage"
        if fam == "boston_molasses_reveal" or prop == "molasses_gravity_wave":
            return "zach3d:boston_molasses_reveal_stage"
        if fam == "boston_tank_leak_seep" or prop == "tank_seam_leak_rig":
            return "zach3d:boston_tank_leak_stage"
        if fam == "boston_tank_rupture" or prop == "rivet_rupture_assembly":
            return "zach3d:boston_tank_rupture_stage"
        if fam == "boston_wave_street_flow" or prop == "molasses_gravity_current":
            return "zach3d:boston_wave_street_stage"
        if fam == "boston_elevated_rail_impact" or prop == "elevated_rail_impact_rig":
            return "zach3d:boston_elevated_rail_impact_stage"
        if fam == "boston_rescue_aftermath" or prop == "rescue_aftermath_rig":
            return "zach3d:boston_rescue_aftermath_stage"
        if fam == "boston_engineering_cutaway" or prop == "steel_section_cutaway_rig":
            return "zach3d:boston_engineering_cutaway_stage"
        if fam == "boston_harbor_payoff" or prop == "boston_overview_stage":
            return "zach3d:boston_harbor_payoff_stage"
        if fam == "tacoma_hook_telephoto" or prop == "tacoma_bridge_hook_rig":
            return "zach3d:tacoma_hook_telephoto_stage"
        if fam == "tacoma_wide_establish" or prop == "tacoma_wide_establish_rig":
            return "zach3d:tacoma_wide_establish_stage"
        if fam == "tacoma_roadway_wave" or prop == "tacoma_roadway_wave_rig":
            return "zach3d:tacoma_roadway_wave_stage"
        if fam == "tacoma_under_deck_girder" or prop == "tacoma_girder_wind_rig":
            return "zach3d:tacoma_under_deck_girder_stage"
        if fam == "tacoma_torsion_twist" or prop == "tacoma_torsion_span_rig":
            return "zach3d:tacoma_torsion_twist_stage"
        if fam == "tacoma_shore_onlooker" or prop == "tacoma_shore_onlooker_rig":
            return "zach3d:tacoma_shore_onlooker_stage"
        if fam == "tacoma_collapse_plunge" or prop == "tacoma_collapse_span_rig":
            return "zach3d:tacoma_collapse_plunge_stage"
        if fam == "tacoma_aftermath" or prop == "tacoma_aftermath_rig":
            return "zach3d:tacoma_aftermath_stage"
        if fam == "skyscraper_street_hook" or prop == "skyscraper_street_hook_rig":
            return "zach3d:skyscraper_street_hook_stage"
        if fam == "skyscraper_skyline_wide" or prop == "skyscraper_skyline_wide_rig":
            return "zach3d:skyscraper_skyline_wide_stage"
        if fam == "skyscraper_wind_vortex" or prop == "skyscraper_wind_vortex_rig":
            return "zach3d:skyscraper_wind_vortex_stage"
        if fam == "skyscraper_plumb_drift" or prop == "skyscraper_plumb_drift_rig":
            return "zach3d:skyscraper_plumb_drift_stage"
        if fam == "skyscraper_office_interior" or prop == "skyscraper_office_interior_rig":
            return "zach3d:skyscraper_office_interior_stage"
        if fam == "skyscraper_tmd_cutaway" or prop == "skyscraper_tmd_cutaway_rig":
            return "zach3d:skyscraper_tmd_cutaway_stage"
        if fam == "skyscraper_counterphase" or prop == "skyscraper_counterphase_rig":
            return "zach3d:skyscraper_counterphase_stage"
        if fam == "skyscraper_before_after" or prop == "skyscraper_before_after_rig":
            return "zach3d:skyscraper_before_after_stage"
        if fam == "skyscraper_dusk_resolution" or prop == "skyscraper_dusk_resolution_rig":
            return "zach3d:skyscraper_dusk_resolution_stage"
        if fam == "fog_street_hook" or prop == "fog_street_hook_rig":
            return "zach3d:london_fog_street_hook_stage"
        if fam == "coal_combustion_cutaway" or prop == "coal_combustion_cutaway_rig":
            return "zach3d:london_coal_combustion_cutaway_stage"
        if fam == "atmospheric_inversion_cap" or prop == "atmospheric_inversion_rig":
            return "zach3d:london_atmospheric_inversion_stage"
        if fam == "vehicle_visibility_dropoff" or prop == "bus_visibility_dropoff_rig":
            return "zach3d:london_bus_visibility_stage"
        if fam == "pedestrian_smog_reaction" or prop == "pedestrian_smog_reaction_rig":
            return "zach3d:london_pedestrian_reaction_stage"
        if fam == "air_quality_aftermath" or prop == "clean_air_aftermath_rig":
            return "zach3d:london_clean_air_aftermath_stage"
        if fam == "airplane_window" or prop == "airplane_window_bleed":
            return "zach3d:airplane_window_hole_stage"
        if fam == "elevator_lobby_button" or prop == "elevator_button":
            return "zach3d:elevator_lobby_button_stage"
        if fam == "controller_cabinet_cutaway" or prop == "controller_pcb":
            return "zach3d:controller_cabinet_cutaway_stage"
        if fam == "traction_machine_room" or prop == "traction_motor_sheave":
            return "zach3d:traction_machine_room_stage"
        if fam == "elevator_shaft_cutaway" or prop == "shaft_car_counterweight":
            return "zach3d:elevator_shaft_cutaway_stage"
        if fam == "elevator_landing_doors" or prop == "elevator_doors":
            return "zach3d:elevator_landing_doors_stage"
        if fam == "schematic_mechanism" or prop == "schematic_mechanism":
            return "zach3d:schematic_mechanism_stage"
        if fam in ("human_device",) or prop == "phone_screen":
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
    require_exact_scene: bool = False,
) -> Dict[str, Any]:
    """Compile all semantic events in `event_graph` into typed entity, character, and generator specs."""
    if selected_skill not in VALID_SKILLS:
        raise ValueError(f"Invalid selected_skill: {selected_skill!r}")
    if event_graph.get("selected_skill") != selected_skill:
        raise UnsupportedSceneError(
            f"Event graph skill {event_graph.get('selected_skill')!r} != locked {selected_skill!r}"
        )

    char_prop_reg = build_character_and_prop_registry(event_graph, selected_skill=selected_skill, seed=seed)
    registry: Dict[str, Dict[str, Any]] = {}
    compiled_items: List[Dict[str, Any]] = []
    for idx, ev in enumerate(event_graph.get("events", [])):
        spec = {
            "relevant_prop": ev.get("relevant_prop"),
            "scene_family": ev.get("scene_family"),
            "unsupported_exact_domain": ev.get("unsupported_exact_domain"),
            "seed": seed + idx * 101,
        }
        asset = make_or_reuse_licensed_procedural_asset(
            spec,
            selected_skill=selected_skill,
            existing_registry=registry,
            require_exact_scene=require_exact_scene,
        )
        char_id = ev.get("character_id")
        if not char_id and "char_protagonist_01" in char_prop_reg["characters"] and (
            ev.get("scene_family") in ("human_device", "elevator_lobby_button", "elevator_landing_doors", "human_studio")
            or "human" in str(ev.get("subject", ""))
        ):
            char_id = "char_protagonist_01"

        compiled_items.append({
            "event_id": ev["event_id"],
            "subject": ev.get("subject"),
            "verb_action": ev.get("verb_action"),
            "character_id": char_id,
            "prop_id": ev.get("relevant_prop"),
            "grounded_props": list(ev.get("grounded_props", [])),
            "scene_family": ev.get("scene_family"),
            "scale_level": ev.get("scale_level"),
            "lighting_mood": ev.get("lighting_mood"),
            "forbidden_elements": list(ev.get("forbidden_elements", [])),
            "unsupported_exact_domain": ev.get("unsupported_exact_domain"),
            "asset": asset,
        })

    return {
        "schema_version": "sd-scene-entities-2",
        "selected_skill": selected_skill,
        "origin_skills": [selected_skill],
        "unique_asset_count": len(registry),
        "character_registry": char_prop_reg["characters"],
        "prop_registry": char_prop_reg["props"],
        "registry": registry,
        "by_event": {it["event_id"]: it for it in compiled_items},
    }


def evaluate_scene_silhouette_and_camera_bounds(
    shot_spec: Dict[str, Any],
    camera_path: Dict[str, Any],
    entity_info: Dict[str, Any],
) -> Dict[str, Any]:
    """Check 3D / logical framing geometry before render: prevents clipping, tiny subjects & collider penetrations."""
    issues: List[str] = []
    prop = str(entity_info.get("prop_id") or shot_spec.get("staging", {}).get("visual_metaphor") or "idea_spark")
    bw, bh, bd = ENTITY_BOUNDS_M.get(prop, (1.0, 1.5, 1.0))
    asset = entity_info.get("asset") or {}
    colliders = list((camera_path.get("collision_constraints") or {}).get("collider_boxes") or asset.get("collider_boxes") or [])
    focal_anchor = camera_path.get("focal_anchor") or asset.get("focal_anchor")

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
            for box in colliders:
                mn, mx = box.get("min", [0, 0, 0]), box.get("max", [0, 0, 0])
                pad = 0.04
                if (mn[0] - pad <= px <= mx[0] + pad) and (mn[1] - pad <= py <= mx[1] + pad) and (mn[2] - pad <= pz <= mx[2] + pad):
                    issues.append(f"Keyframe {kf_idx} camera penetrates collider '{box.get('id')}'")
            # Check focal anchor stays roughly within camera forward cone
            if isinstance(focal_anchor, dict) and isinstance(focal_anchor.get("world_pos"), list):
                ax, ay, az = [float(v) for v in focal_anchor["world_pos"]]
                fwd = (lx - px, ly - py, lz - pz)
                to_a = (ax - px, ay - py, az - pz)
                nf = math.sqrt(sum(c * c for c in fwd)) or 1.0
                na = math.sqrt(sum(c * c for c in to_a)) or 1.0
                cos_ang = max(-1.0, min(1.0, sum((fwd[k] / nf) * (to_a[k] / na) for k in range(3))))
                ang_deg = math.degrees(math.acos(cos_ang))
                # Vertical half-FOV covers ~0.55*fov, diagonal slightly more
                if ang_deg > max(28.0, fov * 0.95):
                    issues.append(f"Keyframe {kf_idx} focal anchor off-axis by {ang_deg:.1f} deg (> {fov * 0.95:.1f} deg)")
            # Estimated vertical fill fraction at distance `dist`
            half_view_h = dist * math.tan(math.radians(fov * 0.5))
            fill_frac = min(1.5, bh / max(0.05, 2.0 * half_view_h))
            if fill_frac < 0.06:
                issues.append(f"Keyframe {kf_idx} subject height fill={fill_frac:.3f} is critically tiny")

    forbidden = set(entity_info.get("forbidden_elements", []))
    gen = str(asset.get("procedural_generator") or "")
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
    shot_fam = str(shot_spec.get("scene_family") or "")
    if not ent or (shot_fam and ent.get("scene_family") != shot_fam):
        shot_prop = str(shot_spec.get("staging", {}).get("visual_metaphor") or ent.get("prop_id") or "idea_spark")
        gen = _map_family_to_generator(
            selected_skill,
            shot_fam or str(ent.get("scene_family") or "human_studio"),
            shot_prop,
            unsupported_exact_domain=shot_spec.get("unsupported_exact_domain"),
        )
        reg_info = ZDF_ARCHETYPE_REGISTRY.get(gen, {})
        ent = {
            "event_id": primary_eid or shot_spec["shot_id"],
            "prop_id": shot_prop,
            "scene_family": shot_fam or str(ent.get("scene_family") or "human_studio"),
            "lighting_mood": shot_spec.get("lighting_mood", "day_editorial"),
            "forbidden_elements": shot_spec.get("staging", {}).get("forbidden_elements", []),
            "character_id": (shot_spec.get("staging") or {}).get("character_id"),
            "asset": {
                "origin_skill": selected_skill,
                "procedural_generator": gen,
                "representation": reg_info.get("fidelity_mode", "stylized_schematic"),
                "focal_anchor": dict(reg_info.get("focal_anchor") or {"anchor_id": "stage_center", "world_pos": [0.0, 1.18, 0.0], "radius_m": 0.25}),
                "scene_bounds": dict(reg_info.get("bounds") or {"x_min": -3.5, "x_max": 3.5, "y_min": 0.12, "y_max": 4.2, "z_min": -4.0, "z_max": 5.2}),
                "collider_boxes": list(reg_info.get("collider_boxes") or []),
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
        "representation": ent["asset"].get("representation", "stylized_schematic"),
        "unsupported_exact_domain": ent.get("unsupported_exact_domain"),
        "focal_anchor": ent["asset"].get("focal_anchor"),
        "scene_bounds": ent["asset"].get("scene_bounds"),
        "character_id": ent.get("character_id"),
        "prop_id": ent["prop_id"],
        "scene_family": ent["scene_family"],
        "bounds_check": bounds_check,
    }


def validate_entity_continuity(
    shots: List[Dict[str, Any]],
    entity_inventory: Dict[str, Any],
    selected_skill: str,
) -> Dict[str, Any]:
    """Verify entity provenance, immutable character/prop identity, and zero Roman armor leaks."""
    if entity_inventory.get("origin_skills") != [selected_skill]:
        raise UnsupportedSceneError("Entity inventory origin_skills violates strict single-skill lock.")

    char_reg = entity_inventory.get("character_registry") or {}
    prop_reg = entity_inventory.get("prop_registry") or {}
    seen_char_appearance: Dict[str, Tuple[Any, Any]] = {}
    seen_prop_mat: Dict[str, Tuple[Any, Any]] = {}

    violations: List[str] = []
    used_generators: List[str] = []
    for s in shots:
        mat = materialize_engine_scene(s, entity_inventory, selected_skill=selected_skill)
        used_generators.append(mat["procedural_generator"])
        forbidden = set((s.get("staging") or {}).get("forbidden_elements", []))
        if "roman_gladiator_armor" in forbidden and "roman" in mat["procedural_generator"]:
            violations.append(f"{s['shot_id']} used Roman generator `{mat['procedural_generator']}` illegally")

        # Check character material / scale lock across appearances
        st = s.get("staging") or {}
        cid = st.get("character_id") or mat.get("character_id")
        if cid and cid in char_reg:
            creg = char_reg[cid]
            declared_mat = st.get("character_material_id") or creg.get("shirt_material_id")
            declared_scale = st.get("character_scale") or creg.get("scale", 1.0)
            sig = (declared_mat, round(float(declared_scale), 4))
            if cid in seen_char_appearance and seen_char_appearance[cid] != sig:
                violations.append(
                    f"{s['shot_id']} mutated locked character '{cid}' identity {seen_char_appearance[cid]} -> {sig}"
                )
            else:
                seen_char_appearance[cid] = sig

        # Check prop continuity
        pid = mat["prop_id"]
        if pid in prop_reg:
            preg = prop_reg[pid]
            p_mat = st.get("prop_material_id") or preg.get("canonical_material_id")
            p_scale = st.get("prop_scale") or preg.get("immutable_scale", 1.0)
            psig = (p_mat, round(float(p_scale), 4))
            if pid in seen_prop_mat and seen_prop_mat[pid] != psig and not s.get("callback_reason"):
                violations.append(f"{s['shot_id']} mutated locked prop '{pid}' identity {seen_prop_mat[pid]} -> {psig}")
            else:
                seen_prop_mat[pid] = psig

    if violations:
        raise UnsupportedSceneError("; ".join(violations))

    return {
        "ok": True,
        "shots_checked": len(shots),
        "unique_generators": len(set(used_generators)),
        "generators_per_shot": used_generators,
        "locked_characters": sorted(seen_char_appearance.keys()),
        "locked_props": sorted(seen_prop_mat.keys()),
    }
