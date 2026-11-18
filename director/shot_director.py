"""STEP 2 (SD-VISUAL-01): Novel Shot Coverage Planner & Anti-Repetition Selector.

Replaces naive cyclic `mid_pool[i % len]` and duplicate-text splitting with semantic
variable-length coverage planning, diverse candidate generation + anti-repetition scoring,
intra-shot transformation scheduling, and strict single-skill provenance compliance.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import VALID_SKILLS
from .visual_event_graph import classify_visual_clause


# Rich per-engine candidate palettes — each entry strictly honors its locked engine's grammar.
ENGINE_CANDIDATE_SPACES: Dict[str, List[Dict[str, Any]]] = {
    "zach-d-films": [
        {
            "setup": "tacoma_hook_telephoto_wobble",
            "families": ("tacoma_hook_telephoto",),
            "framing": "CU_TelephotoSpan",
            "angle": "telephoto_road_centerline",
            "move": "subtle_telephoto_creep",
            "focal_mm": 68,
            "placement": "center_bridge_ribbon",
            "silhouette": "warped_centerline_suspenders",
            "pose": "bridge_hook_initial_sway",
            "novel_non_template": True,
        },
        {
            "setup": "tacoma_wide_establish_shore",
            "families": ("tacoma_wide_establish",),
            "framing": "WS_StraitContext",
            "angle": "wide_oblique_puget_sound",
            "move": "aerial_dolly_drift",
            "focal_mm": 24,
            "placement": "spanning_twintowers_strait",
            "silhouette": "slender_suspension_bridge_shore",
            "pose": "strait_wide_establish",
            "novel_non_template": True,
        },
        {
            "setup": "tacoma_wide_strait_aerial",
            "families": ("tacoma_wide_establish",),
            "framing": "VWS_StraitTowerSpan",
            "angle": "high_shore_towers_oblique",
            "move": "tower_span_arc_sweep",
            "focal_mm": 28,
            "placement": "east_tower_strait_horizon",
            "silhouette": "twin_towers_puget_narrows",
            "pose": "strait_crosswind_buildup",
            "novel_non_template": True,
        },
        {
            "setup": "tacoma_roadway_wave_car",
            "families": ("tacoma_roadway_wave",),
            "framing": "MS_DeckChase",
            "angle": "three_quarter_deck_chase",
            "move": "deck_wave_track",
            "focal_mm": 34,
            "placement": "midspan_1940_sedan",
            "silhouette": "bouncing_deck_1940_sedan",
            "pose": "bridge_vertical_bounce",
            "novel_non_template": True,
        },
        {
            "setup": "tacoma_under_deck_girder_cutaway",
            "families": ("tacoma_under_deck_girder",),
            "framing": "MCU_UnderDeckGirder",
            "angle": "low_under_truss_side",
            "move": "underside_girder_sweep",
            "focal_mm": 30,
            "placement": "windward_plate_girder",
            "silhouette": "solid_8ft_plate_girder_wind",
            "pose": "plate_girder_wind_loading",
            "novel_non_template": True,
        },
        {
            "setup": "tacoma_torsion_twist_midspan",
            "families": ("tacoma_torsion_twist",),
            "framing": "MS_TorsionAxis",
            "angle": "diagonal_midspan_twist",
            "move": "torsion_counter_roll_track",
            "focal_mm": 40,
            "placement": "twisting_opposite_lanes",
            "silhouette": "opposed_deck_edges_cables",
            "pose": "torsional_flutter_escalation",
            "novel_non_template": True,
        },
        {
            "setup": "tacoma_torsion_twist_longitudinal",
            "families": ("tacoma_torsion_twist",),
            "framing": "WS_TorsionLongitudinal",
            "angle": "high_cable_quarter",
            "move": "torsion_reveal_crane",
            "focal_mm": 32,
            "placement": "twisting_opposite_lanes",
            "silhouette": "opposed_deck_edges_cables",
            "pose": "extreme_opposed_edge_roll",
            "novel_non_template": True,
        },
        {
            "setup": "tacoma_shore_onlooker_react",
            "families": ("tacoma_shore_onlooker",),
            "framing": "MS_ShoreReaction",
            "angle": "over_shoulder_shore_approach",
            "move": "step_back_reframe",
            "focal_mm": 35,
            "placement": "foreground_1940_witness",
            "silhouette": "onlooker_brace_bridge_behind",
            "pose": "shore_onlooker_reaction",
            "novel_non_template": True,
        },
        {
            "setup": "tacoma_section_collapse_plunge",
            "families": ("tacoma_collapse_plunge",),
            "framing": "WS_CollapseDrop",
            "angle": "side_three_quarter_narrows",
            "move": "tilt_down_with_plunge",
            "focal_mm": 26,
            "placement": "snapping_center_section",
            "silhouette": "falling_roadbed_water_splash",
            "pose": "bridge_span_collapse",
            "novel_non_template": True,
        },
        {
            "setup": "tacoma_aftermath_broken_span",
            "families": ("tacoma_aftermath",),
            "framing": "WS_RespectfulAftermath",
            "angle": "high_quiet_strait_pullback",
            "move": "slow_pullback_still",
            "focal_mm": 22,
            "placement": "gap_between_towers",
            "silhouette": "standing_towers_empty_water",
            "pose": "bridge_collapse_aftermath",
            "novel_non_template": True,
        },
        {
            "setup": "tacoma_aftermath_truss_legacy",
            "families": ("tacoma_aftermath",),
            "framing": "VWS_StraitPayoff",
            "angle": "aerial_strait_panorama",
            "move": "slow_ascending_tilt",
            "focal_mm": 20,
            "placement": "gap_between_towers",
            "silhouette": "standing_towers_empty_water",
            "pose": "bridge_collapse_aftermath",
            "novel_non_template": True,
        },
        {
            "setup": "skyscraper_street_hook_tilt",
            "families": ("skyscraper_street_hook",),
            "framing": "MS_StreetUpTilt",
            "angle": "street_level_upward_3q",
            "move": "upward_gaze_tilt",
            "focal_mm": 28,
            "placement": "foreground_observer_tower_above",
            "silhouette": "pedestrian_upward_swaying_crown",
            "pose": "street_observer_rooftop_sway_hook",
            "novel_non_template": True,
        },
        {
            "setup": "skyscraper_skyline_wide_establish",
            "families": ("skyscraper_skyline_wide",),
            "framing": "VWS_SkylineContext",
            "angle": "elevated_skyline_oblique",
            "move": "skyline_parallax_glide",
            "focal_mm": 24,
            "placement": "slender_tower_over_blocks",
            "silhouette": "urban_blocks_hero_tower",
            "pose": "skyline_scale_establish",
            "novel_non_template": True,
        },
        {
            "setup": "skyscraper_wind_vortex_facade",
            "families": ("skyscraper_wind_vortex",),
            "framing": "MCU_VortexFacade",
            "angle": "windward_upper_three_quarter",
            "move": "vortex_wake_sweep",
            "focal_mm": 35,
            "placement": "windward_upper_tiers",
            "silhouette": "curling_vortex_ribbons_facade",
            "pose": "crosswind_vortex_excitation",
            "novel_non_template": True,
        },
        {
            "setup": "skyscraper_plumb_drift_gauge",
            "families": ("skyscraper_plumb_drift",),
            "framing": "MS_PlumbComparison",
            "angle": "upper_crown_profile_axis",
            "move": "lateral_drift_track",
            "focal_mm": 38,
            "placement": "roof_vs_red_plumb_axis",
            "silhouette": "cantilever_offset_red_plumb",
            "pose": "flexural_roof_drift_gauge",
            "novel_non_template": True,
        },
        {
            "setup": "skyscraper_office_interior_sway",
            "families": ("skyscraper_office_interior",),
            "framing": "MCU_OfficeSway",
            "angle": "interior_three_quarter_window",
            "move": "gentle_office_dolly",
            "focal_mm": 32,
            "placement": "lamp_left_worker_right",
            "silhouette": "swinging_pendant_braced_worker",
            "pose": "interior_office_reaction",
            "novel_non_template": True,
        },
        {
            "setup": "skyscraper_tmd_cutaway_reveal",
            "families": ("skyscraper_tmd_cutaway",),
            "framing": "ECU_DamperCutaway",
            "angle": "penthouse_section_35deg",
            "move": "peel_orbit_reveal",
            "focal_mm": 42,
            "placement": "center_pendulum_sphere",
            "silhouette": "cutaway_steel_cage_pendulum",
            "pose": "tuned_mass_damper_cutaway_reveal",
            "novel_non_template": True,
        },
        {
            "setup": "skyscraper_counterphase_vectors",
            "families": ("skyscraper_counterphase",),
            "framing": "MCU_CounterPhase",
            "angle": "axial_penthouse_oppose",
            "move": "opposing_vector_glide",
            "focal_mm": 40,
            "placement": "sphere_vs_frame_vectors",
            "silhouette": "counterphase_force_bars_pendulum",
            "pose": "counterphase_damper_cancellation",
            "novel_non_template": True,
        },
        {
            "setup": "skyscraper_split_before_after",
            "families": ("skyscraper_before_after",),
            "framing": "WS_SplitBeforeAfter",
            "angle": "front_split_comparison",
            "move": "subtle_compare_push",
            "focal_mm": 34,
            "placement": "undamped_left_damped_right",
            "silhouette": "twin_towers_sway_vs_steady",
            "pose": "damped_vs_undamped_comparison",
            "novel_non_template": True,
        },
        {
            "setup": "skyscraper_dusk_safe_skyline",
            "families": ("skyscraper_dusk_resolution",),
            "framing": "WS_DuskContextReveal",
            "angle": "heroic_dusk_pullback",
            "move": "pull_back_crane",
            "focal_mm": 26,
            "placement": "center_dusk_tower",
            "silhouette": "evening_skyline_gentle_flex",
            "pose": "skyscraper_dusk_resolution",
            "novel_non_template": True,
        },
        {
            "setup": "boston_street_hook_crowd",
            "families": ("boston_street_hook",),
            "framing": "WS_StreetHero",
            "angle": "three_quarter_street_level",
            "move": "dolly_push_in",
            "focal_mm": 28,
            "placement": "left_brick_alley",
            "silhouette": "1919_cobblestone_street_crowd",
            "pose": "street_rumble_foreshadow",
            "novel_non_template": True,
        },
        {
            "setup": "boston_street_hook_alley_pan",
            "families": ("boston_street_hook",),
            "framing": "MS_AlleyHorizon",
            "angle": "low_cobblestone_upward",
            "move": "alley_track_pan",
            "focal_mm": 34,
            "placement": "right_storefront_curb",
            "silhouette": "horse_cart_approaching_shadow",
            "pose": "mystery_suspense_crowd_freeze",
            "novel_non_template": True,
        },
        {
            "setup": "boston_molasses_wave_reveal",
            "families": ("boston_molasses_reveal",),
            "framing": "MS_LowReveal",
            "angle": "reverse_alley_low_tilt",
            "move": "whip_pan_reveal",
            "focal_mm": 35,
            "placement": "center_dark_surge",
            "silhouette": "dark_viscous_crest_tank",
            "pose": "thick_fluid_reveal",
            "novel_non_template": True,
        },
        {
            "setup": "boston_tank_leak_seep_cu",
            "families": ("boston_tank_leak_seep",),
            "framing": "CU_TankSeam",
            "angle": "low_upward_tank_wall",
            "move": "vertical_creep_tilt",
            "focal_mm": 50,
            "placement": "left_rivet_seam",
            "silhouette": "dripping_seam_worker_lantern",
            "pose": "chronic_seam_seepage",
            "novel_non_template": True,
        },
        {
            "setup": "boston_tank_scale_payoff",
            "families": ("boston_tank_leak_seep",),
            "framing": "WS_MonolithTank",
            "angle": "wide_heroic_upward_tilt",
            "move": "crane_scale_climb",
            "focal_mm": 28,
            "placement": "right_towering_tank_cylinder",
            "silhouette": "monolithic_riveted_tank_horizon",
            "pose": "overwhelming_volume_payoff",
            "novel_non_template": True,
        },
        {
            "setup": "boston_tank_rupture_blast",
            "families": ("boston_tank_rupture",),
            "framing": "MCU_RivetBurst",
            "angle": "three_quarter_burst_angle",
            "move": "impact_push_shake",
            "focal_mm": 40,
            "placement": "center_burst_seam",
            "silhouette": "sheared_plates_molasses_burst",
            "pose": "tank_panel_rupture",
            "novel_non_template": True,
        },
        {
            "setup": "boston_tank_rupture_surge",
            "families": ("boston_tank_rupture",),
            "framing": "WS_TankCollapse",
            "angle": "wide_low_wharf_angle",
            "move": "whip_tilt_rupture_follow",
            "focal_mm": 28,
            "placement": "lower_rivet_apron",
            "silhouette": "gushing_molasses_flood_front",
            "pose": "tank_wall_blowout",
            "novel_non_template": True,
        },
        {
            "setup": "boston_wave_chase_street",
            "families": ("boston_wave_street_flow",),
            "framing": "MS_TrackingChase",
            "angle": "ahead_of_wave_backward_track",
            "move": "retreating_dolly_chase",
            "focal_mm": 30,
            "placement": "diagonal_street_flood",
            "silhouette": "surging_wave_crates_retreat",
            "pose": "molasses_wave_surge",
            "novel_non_template": True,
        },
        {
            "setup": "boston_wave_speed_sweep",
            "families": ("boston_wave_street_flow",),
            "framing": "WS_SideTracking",
            "angle": "elevated_side_track",
            "move": "side_sweep_track",
            "focal_mm": 26,
            "placement": "right_cart_sweep",
            "silhouette": "street_wave_speed_sweep",
            "pose": "wave_speed_chase_escalation",
            "novel_non_template": True,
        },
        {
            "setup": "boston_elevated_rail_crush",
            "families": ("boston_elevated_rail_impact",),
            "framing": "MS_StructuralImpact",
            "angle": "right_oblique_trestle",
            "move": "slowmo_track_impact",
            "focal_mm": 38,
            "placement": "right_trestle_pillar",
            "silhouette": "bent_trestle_delivery_wagon",
            "pose": "street_structure_impact",
            "novel_non_template": True,
        },
        {
            "setup": "boston_elevated_rail_truss_tilt",
            "families": ("boston_elevated_rail_impact",),
            "framing": "MCU_BentGirder",
            "angle": "low_under_trestle_upward",
            "move": "impact_tilt_reframe",
            "focal_mm": 30,
            "placement": "buckled_steel_girder",
            "silhouette": "tilted_elevated_track_wagon",
            "pose": "trestle_truss_deflection",
            "novel_non_template": True,
        },
        {
            "setup": "boston_rescue_aftermath_still",
            "families": ("boston_rescue_aftermath",),
            "framing": "MS_RespectfulWide",
            "angle": "eye_level_solemn_drift",
            "move": "slow_solemn_drift",
            "focal_mm": 34,
            "placement": "centered_lantern_crew",
            "silhouette": "calm_sludge_responders_lanterns",
            "pose": "rescue_and_settling_aftermath",
            "novel_non_template": True,
        },
        {
            "setup": "boston_rescue_lantern_wade",
            "families": ("boston_rescue_aftermath",),
            "framing": "MCU_LanternWade",
            "angle": "low_lantern_oblique",
            "move": "lantern_wade_push",
            "focal_mm": 42,
            "placement": "right_rescuer_lantern",
            "silhouette": "responders_wading_thick_sludge",
            "pose": "active_molasses_rescue_effort",
            "novel_non_template": True,
        },
        {
            "setup": "boston_engineering_lap_cutaway",
            "families": ("boston_engineering_cutaway",),
            "framing": "ECU_SectionCutaway",
            "angle": "exploded_oblique_35deg",
            "move": "peel_orbit_reveal",
            "focal_mm": 58,
            "placement": "center_lap_cutaway",
            "silhouette": "thin_steel_lap_joint_cutaway",
            "pose": "structural_defect_cutaway",
            "novel_non_template": True,
        },
        {
            "setup": "boston_harbor_overview_payoff",
            "families": ("boston_harbor_payoff",),
            "framing": "VWS_HarborPullback",
            "angle": "elevated_harbor_overview",
            "move": "pull_back_crane",
            "focal_mm": 24,
            "placement": "centered_wharf_horizon",
            "silhouette": "north_end_wharf_skyline_1919",
            "pose": "historical_overview_pullback",
            "novel_non_template": True,
        },
        {
            "setup": "airplane_window_hole_macro",
            "families": ("airplane_window",),
            "framing": "CU_BleedHole",
            "angle": "lower_bezel_macro",
            "move": "macro_push_in",
            "focal_mm": 55,
            "placement": "centered_window_hole",
            "silhouette": "oval_bezel_bleed_hole",
            "pose": "focus_bleed_orifice",
            "novel_non_template": True,
        },
        {
            "setup": "airplane_window_layers_exploded",
            "families": ("airplane_window",),
            "framing": "MS_ExplodedPanes",
            "angle": "exploded_oblique_35deg",
            "move": "peel_orbit_reveal",
            "focal_mm": 40,
            "placement": "oblique_three_panes",
            "silhouette": "three_separated_acrylic_panes",
            "pose": "exploded_layer_reveal",
            "novel_non_template": True,
        },
        {
            "setup": "airplane_window_pressure_equalize",
            "families": ("airplane_window",),
            "framing": "MS_PressureFlow",
            "angle": "left_cabin_three_quarter",
            "move": "arc_around_window",
            "focal_mm": 36,
            "placement": "left_pressure_vectors",
            "silhouette": "cabin_pressure_arrow_stream",
            "pose": "pressure_equalization",
            "novel_non_template": True,
        },
        {
            "setup": "airplane_window_failsafe_cutaway",
            "families": ("airplane_window",),
            "framing": "MCU_FailSafeCore",
            "angle": "right_cutaway_profile",
            "move": "focus_glide_failsafe",
            "focal_mm": 48,
            "placement": "right_backup_pane",
            "silhouette": "outer_crack_middle_hold",
            "pose": "failsafe_load_transfer",
            "novel_non_template": True,
        },
        {
            "setup": "airplane_window_moisture_vent",
            "families": ("airplane_window",),
            "framing": "MCU_MoistureVent",
            "angle": "right_lower_breather",
            "move": "pull_back_crane",
            "focal_mm": 50,
            "placement": "lower_vent_clearance",
            "silhouette": "frost_clear_bleed_stream",
            "pose": "moisture_defog_payoff",
            "novel_non_template": True,
        },
        {
            "setup": "elevator_lobby_button_macro",
            "families": ("elevator_lobby_button",),
            "framing": "CU_HandContact",
            "angle": "three_quarter_button_reach",
            "move": "macro_push_in",
            "focal_mm": 45,
            "placement": "foreground_right",
            "silhouette": "hand_button_contact",
            "pose": "reach_press_button",
            "novel_non_template": True,
        },
        {
            "setup": "controller_cabinet_cutaway",
            "families": ("controller_cabinet_cutaway",),
            "framing": "ECU_Cutaway",
            "angle": "cabinet_door_open_35deg",
            "move": "peel_orbit_reveal",
            "focal_mm": 65,
            "placement": "center_exploded",
            "silhouette": "open_cabinet_relays",
            "pose": "cutaway_reveal",
            "novel_non_template": True,
        },
        {
            "setup": "controller_relay_bus_macro",
            "families": ("controller_cabinet_cutaway",),
            "framing": "CU_LogicBus",
            "angle": "right_oblique_pcb",
            "move": "dolly_trace_relays",
            "focal_mm": 50,
            "placement": "right_logic_bay",
            "silhouette": "relay_bus_pulses",
            "pose": "signal_trace_sweep",
            "novel_non_template": True,
        },
        {
            "setup": "traction_machine_room_drive",
            "families": ("traction_machine_room",),
            "framing": "MS_MachineRoom",
            "angle": "elevated_sheave_isometric",
            "move": "arc_around_rotor",
            "focal_mm": 35,
            "placement": "center_drive_bay",
            "silhouette": "cutaway_motor_sheave",
            "pose": "sheave_cable_drive",
            "novel_non_template": True,
        },
        {
            "setup": "traction_caliper_brake_macro",
            "families": ("traction_machine_room",),
            "framing": "MCU_CaliperBrake",
            "angle": "tight_sheave_caliper_right",
            "move": "macro_push_caliper",
            "focal_mm": 58,
            "placement": "right_brake_caliper",
            "silhouette": "red_caliper_clamp_sheave",
            "pose": "caliper_clamp_stop",
            "novel_non_template": True,
        },
        {
            "setup": "elevator_shaft_counterweight",
            "families": ("elevator_shaft_cutaway",),
            "framing": "WS_ShaftCutaway",
            "angle": "front_cutaway_vertical",
            "move": "crane_tilt_follow",
            "focal_mm": 28,
            "placement": "dual_rail_balance",
            "silhouette": "car_counterweight_ropes",
            "pose": "opposite_travel",
            "novel_non_template": True,
        },
        {
            "setup": "elevator_shaft_sensors_close",
            "families": ("elevator_shaft_cutaway",),
            "framing": "CU_RailSensors",
            "angle": "right_vertical_bus_angle",
            "move": "vertical_sensor_track",
            "focal_mm": 42,
            "placement": "rail_sensor_column",
            "silhouette": "magnetic_vane_sensors",
            "pose": "sensor_beacon_pulse",
            "novel_non_template": True,
        },
        {
            "setup": "elevator_landing_doors_reveal",
            "families": ("elevator_landing_doors",),
            "framing": "MS_LobbyPortal",
            "angle": "eye_level_portal",
            "move": "pull_back_crane",
            "focal_mm": 32,
            "placement": "centered_portal",
            "silhouette": "biparting_doors_hero",
            "pose": "level_and_open",
            "novel_non_template": True,
        },
        {
            "setup": "schematic_mechanism_stage",
            "families": ("schematic_mechanism",),
            "framing": "MS_Schematic",
            "angle": "three_quarter_isometric",
            "move": "orbit_right",
            "focal_mm": 35,
            "placement": "center_pedestal",
            "silhouette": "labeled_schematic_linkage",
            "pose": "schematic_cycle",
            "novel_non_template": True,
        },
        {
            "setup": "human_device_macro",
            "families": ("human_device", "human_lifestyle", "human_studio"),
            "framing": "CU_OverShoulder",
            "angle": "three_quarter_hand_focus",
            "move": "macro_push_in",
            "focal_mm": 50,
            "placement": "foreground_right",
            "silhouette": "hand_screen_glow",
            "pose": "tap_screen_lean",
            "novel_non_template": True,
        },
        {
            "setup": "device_cutaway_pcb",
            "families": ("electromechanical",),
            "framing": "ECU_Cutaway",
            "angle": "exploded_oblique_35deg",
            "move": "peel_orbit_reveal",
            "focal_mm": 85,
            "placement": "center_exploded",
            "silhouette": "open_chassis_layers",
            "pose": "cutaway_reveal",
            "novel_non_template": True,
        },
        {
            "setup": "network_tower_relay",
            "families": ("network_link", "energy_grid"),
            "framing": "WS_LowHero",
            "angle": "upward_tower_tilt",
            "move": "crane_tilt_follow",
            "focal_mm": 24,
            "placement": "left_tower_axis",
            "silhouette": "lattice_mast_rings",
            "pose": "emissive_pulse_wave",
            "novel_non_template": True,
        },
        {
            "setup": "subsea_fiber_conduit",
            "families": ("ocean_infrastructure", "natural_environment"),
            "framing": "MS_Tracking",
            "angle": "underwater_low_glide",
            "move": "dolly_along_conduit",
            "focal_mm": 28,
            "placement": "diagonal_floor_sweep",
            "silhouette": "armored_fiber_beam",
            "pose": "photon_pulse_stream",
            "novel_non_template": True,
        },
        {
            "setup": "datacenter_aisle_sweep",
            "families": ("datacenter_compute", "comparison_logic", "economy_reward"),
            "framing": "WS_Corridor",
            "angle": "one_point_symmetrical",
            "move": "dolly_forward_aisle",
            "focal_mm": 24,
            "placement": "symmetrical_racks",
            "silhouette": "blinking_server_monoliths",
            "pose": "packet_route_flow",
            "novel_non_template": True,
        },
        {
            "setup": "power_turbine_generator",
            "families": ("energy_grid", "electromechanical", "mechanical_breakdown"),
            "framing": "MS_Cutaway",
            "angle": "elevated_isometric",
            "move": "arc_around_rotor",
            "focal_mm": 35,
            "placement": "right_generator_bay",
            "silhouette": "spinning_copper_coils",
            "pose": "turbine_induction_spin",
            "novel_non_template": True,
        },
        {
            "setup": "cosmic_scale_bridge",
            "families": ("cosmic_scale", "micro_matter", "natural_environment"),
            "framing": "ECU_to_VWS",
            "angle": "orbital_horizon_roll",
            "move": "scale_pullback_cosmos",
            "focal_mm": 20,
            "placement": "central_celestial_core",
            "silhouette": "nebula_shell_rings",
            "pose": "stardust_forge_bloom",
            "novel_non_template": True,
        },
        {
            "setup": "anatomical_cutaway_3d",
            "families": ("anatomical_cutaway",),
            "framing": "ECU_XRay",
            "angle": "frontal_medical_orbit",
            "move": "focus_push_to_organ",
            "focal_mm": 65,
            "placement": "center_torso_slab",
            "silhouette": "translucent_shell_organ",
            "pose": "pulse_wave_reveal",
            "novel_non_template": True,
        },
        {
            "setup": "hook_3d_action_launch",
            "families": ("roman_historical", "metallic_clash", "human_studio"),
            "framing": "MS",
            "angle": "three_quarter_hero",
            "move": "dolly_push_in",
            "focal_mm": 35,
            "placement": "left_rule_thirds",
            "silhouette": "hero_character_prop",
            "pose": "dynamic_reach",
            "novel_non_template": False,
        },
        {
            "setup": "belief_studio_demonstration",
            "families": ("roman_historical", "human_studio", "comparison_logic", "economy_reward"),
            "framing": "WS",
            "angle": "low_studio_orbit",
            "move": "orbit_right",
            "focal_mm": 28,
            "placement": "dual_stage_spread",
            "silhouette": "wide_stage_confrontation",
            "pose": "demonstrate_exchange",
            "novel_non_template": False,
        },
        {
            "setup": "novel_slowmo_ripple_cutaway",
            "families": ("metallic_clash", "roman_historical"),
            "framing": "ECU_Macro",
            "angle": "projectile_tracking_side",
            "move": "slowmo_track_impact",
            "focal_mm": 85,
            "placement": "center_tension_point",
            "silhouette": "ripple_impact_wave",
            "pose": "recoil_frozen_moment",
            "novel_non_template": True,
        },
        {
            "setup": "mechanism_cross_section_3d",
            "families": ("comparison_logic", "roman_historical", "mechanical_breakdown", "time_pacing"),
            "framing": "MS_Cutaway",
            "angle": "elevated_isometric",
            "move": "push_toward_core",
            "focal_mm": 50,
            "placement": "balanced_pedestal",
            "silhouette": "layered_balance_cutaway",
            "pose": "precision_reveal",
            "novel_non_template": True,
        },
        {
            "setup": "payoff_full_stage_reveal",
            "families": ("payoff", "cosmic_scale", "human_studio", "roman_historical", "human_device"),
            "framing": "WS",
            "angle": "eye_level_clean",
            "move": "pull_back_crane",
            "focal_mm": 32,
            "placement": "centered_horizon",
            "silhouette": "open_hero_payoff",
            "pose": "confident_resolve",
            "novel_non_template": False,
        },
    ],
    "stick-figure": [
        {"setup": "hook_dynamic_cu", "framing": "CU", "angle": "eye_level_push", "move": "push_in_handheld", "focal_mm": 40, "placement": "left_char_right_prop", "silhouette": "torso_prop_reach", "pose": "lean_in_reach", "novel_non_template": False},
        {"setup": "belief_wide_parallax", "framing": "WS", "angle": "slight_low_3plane", "move": "tracking_pan_right", "focal_mm": 24, "placement": "walking_across_planes", "silhouette": "multi_plane_horizon", "pose": "stride_walk", "novel_non_template": False},
        {"setup": "turn_reaction_ecu", "framing": "ECU", "angle": "dutch_tilt_dramatic", "move": "snap_zoom_shake", "focal_mm": 70, "placement": "centered_large_face", "silhouette": "radial_burst_head", "pose": "hands_up_shock", "novel_non_template": False},
        {"setup": "novel_mechanism_cutaway", "framing": "Cutaway_Macro", "angle": "orthographic_cross_section", "move": "focus_glide", "focal_mm": 55, "placement": "framed_inset_panel", "silhouette": "oscilloscope_cutaway_card", "pose": "pointer_analysis", "novel_non_template": True},
        {"setup": "split_comparison_stage", "framing": "MS_Split", "angle": "frontal_duel", "move": "counter_drift", "focal_mm": 35, "placement": "split_left_right", "silhouette": "dual_versus_panel", "pose": "duel_contrast", "novel_non_template": True},
        {"setup": "scale_ladder_pan", "framing": "MS_to_VWS", "angle": "vertical_pan_climb", "move": "pan_up_scale", "focal_mm": 28, "placement": "diagonal_scale_chain", "silhouette": "ascending_scale_nodes", "pose": "point_upward_leap", "novel_non_template": True},
        {"setup": "payoff_sunny_pullback", "framing": "MS_to_WS", "angle": "heroic_eye_level", "move": "pull_back_settle", "focal_mm": 30, "placement": "centered_warm_stage", "silhouette": "dual_props_triumph", "pose": "hero_celebrate", "novel_non_template": False},
    ],
    "minimalistic-graphics": [
        {"setup": "hook_solitary_dot_pulse", "framing": "Center_Void", "angle": "flat_orthographic", "move": "breath_pulse", "focal_mm": 50, "placement": "dead_center", "silhouette": "solitary_circle_ripple", "pose": "center_pulse", "novel_non_template": False},
        {"setup": "novel_pendulum_or_labyrinth", "framing": "MS_Geometric", "angle": "flat_orthographic", "move": "arc_oscillation", "focal_mm": 40, "placement": "upper_pivot_arc", "silhouette": "pendulum_arc_vector", "pose": "swing_momentum", "novel_non_template": True},
        {"setup": "kinetic_balance_beam", "framing": "WS_Equilibrium", "angle": "flat_orthographic", "move": "fulcrum_tilt_shift", "focal_mm": 32, "placement": "horizontal_fulcrum", "silhouette": "counterweight_beam", "pose": "balance_shift", "novel_non_template": True},
        {"setup": "rising_hairline_steps", "framing": "WS_Ascending", "angle": "flat_orthographic", "move": "parabolic_hop_climb", "focal_mm": 28, "placement": "staircase_diagonal", "silhouette": "ascending_bars", "pose": "step_hop", "novel_non_template": False},
        {"setup": "payoff_orbital_sparks", "framing": "MS_Apex_Orbit", "angle": "flat_orthographic", "move": "radial_bloom_hold", "focal_mm": 45, "placement": "apex_upper_right", "silhouette": "orbit_halo_sparks", "pose": "apex_rest", "novel_non_template": False},
    ],
    "graph": [
        {"setup": "hook_metric_counter_intro", "framing": "Macro_Header", "angle": "flat_editorial", "move": "grid_reveal", "focal_mm": 35, "placement": "upper_counter_lead", "silhouette": "tabular_hero_axis", "pose": "baseline_init", "novel_non_template": False},
        {"setup": "early_baseline_zoom", "framing": "CU_Curve_Origin", "angle": "flat_editorial", "move": "follow_tip_pan", "focal_mm": 65, "placement": "zoom_tip_follow", "silhouette": "magnified_curve_tip", "pose": "trace_early", "novel_non_template": False},
        {"setup": "novel_inflection_tangent_delta", "framing": "MS_Inflection_Split", "angle": "flat_editorial", "move": "slope_highlight_sweep", "focal_mm": 50, "placement": "tangent_vector_center", "silhouette": "stems_plus_tangent", "pose": "highlight_slope", "novel_non_template": True},
        {"setup": "milestone_delta_spotlight", "framing": "MS_Evidence_Callout", "angle": "flat_editorial", "move": "pan_milestone_window", "focal_mm": 45, "placement": "upper_right_peak", "silhouette": "delta_callout_grid", "pose": "compare_deltas", "novel_non_template": True},
        {"setup": "payoff_full_horizon_curve", "framing": "WS_Full_Chart", "angle": "flat_editorial", "move": "settle_halo_drop", "focal_mm": 28, "placement": "full_chart_frame", "silhouette": "complete_spline_drop", "pose": "settle_halo", "novel_non_template": False},
    ],
    "map-route": [
        {"setup": "departure_street_level", "framing": "CU_Origin_Block", "angle": "low_chase_32deg", "move": "pull_from_start_disc", "focal_mm": 35, "placement": "origin_block_low", "silhouette": "low_street_corridor", "pose": "launch_head", "novel_non_template": False},
        {"setup": "mid_route_bridge_crossing", "framing": "MS_Aerial_Chase", "angle": "aerial_40deg_swing", "move": "ride_behind_route_head", "focal_mm": 28, "placement": "left_bank_river_arc", "silhouette": "bridge_over_river", "pose": "cruise_ribbon", "novel_non_template": True},
        {"setup": "turn_park_corridor", "framing": "MS_Corner_Bank", "angle": "banked_aerial_35deg", "move": "corner_arc_track", "focal_mm": 32, "placement": "right_park_turn", "silhouette": "angled_corner_blocks", "pose": "bank_turn", "novel_non_template": False},
        {"setup": "street_canopy_altitude_shift", "framing": "MS_Wide_Altitude", "angle": "elevated_oblique_50deg", "move": "climb_altitude_sweep", "focal_mm": 24, "placement": "panoramic_midtown", "silhouette": "skyline_route_arc", "pose": "altitude_climb", "novel_non_template": True},
        {"setup": "arrival_pin_drop_pullback", "framing": "WS_Overview_Card", "angle": "high_overview_28deg", "move": "crane_pullback_reveal", "focal_mm": 22, "placement": "destination_pin_center", "silhouette": "pin_drop_eta_card", "pose": "pin_bounce_card", "novel_non_template": False},
    ],
    "breakdown": [
        {"setup": "assembled_hero_silhouette", "framing": "MS_Studio_Hero", "angle": "three_quarter_rim", "move": "slow_turntable_intro", "focal_mm": 35, "placement": "center_hero_pedestal", "silhouette": "compact_closed_shell", "pose": "assembled_idle", "novel_non_template": False},
        {"setup": "axial_layer_separation", "framing": "MS_Exploding_Stack", "angle": "elevated_30deg", "move": "dolly_out_with_explosion", "focal_mm": 28, "placement": "left_offset_stack", "silhouette": "separated_axial_stack", "pose": "explode_apart", "novel_non_template": False},
        {"setup": "novel_internal_core_macro", "framing": "ECU_Internal_Core", "angle": "macro_oblique_22deg", "move": "focus_sweep_across_core", "focal_mm": 75, "placement": "macro_core_center", "silhouette": "coil_pcb_core_macro", "pose": "core_inspect", "novel_non_template": True},
        {"setup": "top_down_subsystem_orbit", "framing": "MS_High_Subsystem", "angle": "top_oblique_52deg", "move": "orbit_subsystem_inspect", "focal_mm": 42, "placement": "upper_layer_focus", "silhouette": "top_cap_ring_view", "pose": "top_sweep", "novel_non_template": True},
        {"setup": "full_annotated_callout_stack", "framing": "WS_Labelled_Column", "angle": "offset_callout_frame", "move": "turntable_hold", "focal_mm": 26, "placement": "left_stack_right_labels", "silhouette": "callout_leaders_grid", "pose": "hold_callout", "novel_non_template": False},
    ],
}


def _select_transition_hint(event: Dict[str, Any], cand: Dict[str, Any], is_last: bool, transition_policy: str) -> str:
    if is_last:
        return "cut"
    if transition_policy == "simple":
        return "cut_on_action"
    verb = event.get("verb_action", "")
    axis = event.get("desired_novelty_axis", "")
    skill = event.get("selected_skill", "zach-d-films")

    if skill == "zach-d-films":
        if cand["setup"] == "elevator_lobby_button_macro":
            return "zoom_through"
        if cand["setup"] == "controller_cabinet_cutaway":
            return "match_cut"
        if cand["setup"] == "traction_machine_room_drive":
            return "object_wipe"
        if axis in ("environment_and_scale_shift", "internal_cutaway") or verb == "scale_jump":
            return "zoom_through"
        if event.get("has_contrast") and cand["setup"] in ("device_cutaway_pcb", "network_tower_relay", "elevator_shaft_counterweight"):
            return "match_cut"
        if event.get("lighting_mood") == "dark_dramatic" and cand["framing"].startswith("WS"):
            return "whip_pan"
        return "cut_on_action"
    if skill == "stick-figure":
        if event.get("has_contrast"):
            return "iris_mask"
        if verb in ("travel_stream", "scale_jump"):
            return "whip"
        return "cut_on_action"
    if skill in ("graph", "map-route", "breakdown"):
        return "match_zoom"
    return "cut_on_action"


def split_long_visual_beats_by_actions(
    events: List[Dict[str, Any]],
    preset: str = "dynamic",
    max_shot_dur: Optional[float] = None,
    fps: int = 30,
    full_script_low: str = "",
) -> List[Dict[str, Any]]:
    """Split over-long events at word boundaries into genuinely distinct sub-beats cleanly.

    Crucial guarantee: NEVER copies identical full narration text across two adjacent split shots!
    Each sub-shot carries its own word slice (`narration_span_start/end` & non-duplicated `narration_text`)
    and a differentiated action/reveal phase.
    """
    if max_shot_dur is None:
        max_shot_dur = 3.6 if preset == "dynamic" else (4.8 if preset == "balanced" else 6.2)
    min_shot_dur = 0.85 if preset == "dynamic" else (1.15 if preset == "balanced" else 1.8)

    out_units: List[Dict[str, Any]] = []
    for ev in events:
        st = float(ev["start_sec"])
        en = float(ev["end_sec"])
        dur = en - st
        text = str(ev.get("exact_narration_phrase") or "").strip()
        toks = text.split()

        if dur > max_shot_dur and len(toks) >= 8 and ev.get("selected_skill") not in ("minimalistic-graphics",):
            # Split cleanly around midpoint onto a distinct frame boundary ONLY if sub-clauses depict different visual stages
            n_parts = 2
            split_idx = len(toks) // 2
            while 2 < split_idx < len(toks) - 2 and toks[split_idx - 1].lower().endswith(("'s", "the", "a", "an", "in", "on", "of", "at")):
                split_idx += 1
            mid_raw = st + dur * (split_idx / float(len(toks)))
            mid_f = round(round(mid_raw * fps) / float(fps), 3)
            mid_f = max(st + min_shot_dur, min(en - min_shot_dur, mid_f))
            if (mid_f - st) >= min_shot_dur and (en - mid_f) >= min_shot_dur:
                span_a = " ".join(toks[:split_idx]).strip()
                span_b = " ".join(toks[split_idx:]).strip()
                skill_s = str(ev.get("selected_skill") or "zach-d-films")
                meta_a = classify_visual_clause(span_a, str(ev.get("beat_role", "mechanism")), int(ev.get("beat_index", 0)), 0, None, [], skill_s, full_script_low=full_script_low)
                meta_b = classify_visual_clause(span_b, str(ev.get("beat_role", "mechanism")), int(ev.get("beat_index", 0)), 1, meta_a["scene_family"], [], skill_s, full_script_low=full_script_low)
                fam_a = meta_a["scene_family"] if meta_a["relevant_prop"] not in ("idea_spark", "atom_crystal") else ev.get("scene_family")
                fam_b = meta_b["scene_family"] if meta_b["relevant_prop"] not in ("idea_spark", "atom_crystal") else ev.get("scene_family")
                allow_same_fam_split = (skill_s != "zach-d-films") or (dur > 6.5)
                if allow_same_fam_split or (fam_b != fam_a):
                    u_a = dict(ev)
                    u_a["unit_id"] = f"{ev['event_id']}_a"
                    u_a["start_sec"] = st
                    u_a["end_sec"] = mid_f
                    u_a["duration_sec"] = round(mid_f - st, 3)
                    u_a["narration_text"] = span_a
                    u_a["narration_span_start"] = 0
                    u_a["narration_span_end"] = split_idx
                    if meta_a["relevant_prop"] not in ("idea_spark", "atom_crystal"):
                        u_a.update({k: meta_a[k] for k in ("subject", "character_id", "verb_action", "relevant_prop", "grounded_props", "scene_family", "scale_level", "lighting_mood", "semantic_relation", "unsupported_exact_domain", "fallback_reason")})
                    if u_a.get("scene_family") != ev.get("scene_family"):
                        u_a.pop("contact_action", None)
                    u_a["visual_objective"] = f"Establish {u_a['subject']} acting on {u_a['relevant_prop']}"
                    u_a["desired_novelty_axis"] = "subject_action_setup"

                    u_b = dict(ev)
                    u_b["unit_id"] = f"{ev['event_id']}_b"
                    u_b["start_sec"] = mid_f
                    u_b["end_sec"] = en
                    u_b["duration_sec"] = round(en - mid_f, 3)
                    u_b["narration_text"] = span_b
                    u_b["narration_span_start"] = split_idx
                    u_b["narration_span_end"] = len(toks)
                    if meta_b["relevant_prop"] not in ("idea_spark", "atom_crystal"):
                        u_b.update({k: meta_b[k] for k in ("subject", "character_id", "verb_action", "relevant_prop", "grounded_props", "scene_family", "scale_level", "lighting_mood", "semantic_relation", "unsupported_exact_domain", "fallback_reason")})
                    if u_b.get("scene_family") != ev.get("scene_family"):
                        u_b.pop("contact_action", None)
                    u_b["visual_objective"] = f"Reveal consequence {u_b['verb_action']} ({u_b['relevant_prop']})"
                    u_b["desired_novelty_axis"] = "internal_reveal_escalation" if meta_b["scene_family"] == u_a["scene_family"] else "environment_and_scale_shift"
                    out_units.extend([u_a, u_b])
                    continue

        u = dict(ev)
        u["unit_id"] = ev["event_id"]
        u["narration_text"] = text
        u["narration_span_start"] = 0
        u["narration_span_end"] = len(toks)
        u["visual_objective"] = f"Show {ev['subject']} -> {ev['verb_action']} ({ev['relevant_prop']})"
        out_units.append(u)

    # Merge tiny fragments (<0.72s) or adjacent ZDF identical-stage splits safely
    merged: List[Dict[str, Any]] = []
    for u in out_units:
        prev = merged[-1] if merged else None
        same_zdf_stage = bool(
            prev is not None
            and u.get("selected_skill") == "zach-d-films"
            and prev.get("scene_family") == u.get("scene_family")
            and prev.get("relevant_prop") == u.get("relevant_prop")
            and (float(u["end_sec"]) - float(prev["start_sec"])) <= 6.5
            and (
                (not prev.get("contact_action") and not u.get("contact_action"))
                or (u.get("scene_family") == "boston_elevated_rail_impact" and (float(u["end_sec"]) - float(prev["start_sec"])) <= 4.5)
            )
        )
        if prev is not None and (((u["end_sec"] - u["start_sec"]) < 0.72) or same_zdf_stage):
            prev["end_sec"] = u["end_sec"]
            prev["duration_sec"] = round(prev["end_sec"] - prev["start_sec"], 3)
            prev["narration_text"] = (prev["narration_text"] + " " + u["narration_text"]).strip()
            prev["event_ids"] = list(dict.fromkeys(prev.get("event_ids", [prev["event_id"]]) + [u["event_id"]]))
        else:
            u["event_ids"] = [u["event_id"]]
            merged.append(u)

    return merged


def generate_candidate_shot_set(
    event: Dict[str, Any],
    grammar: Optional[List[Dict[str, Any]]],
    scene_state: Dict[str, Any],
    continuity_state: Dict[str, Any],
    seed: int,
    selected_skill: str = "zach-d-films",
    unit_idx: int = 0,
    total_units: int = 1,
) -> List[Dict[str, Any]]:
    """Propose diverse staging/camera/lighting/silhouette candidates grounded in the semantic event."""
    pool = grammar if grammar else ENGINE_CANDIDATE_SPACES[selected_skill]
    fam = str(event.get("scene_family") or "")
    verb = str(event.get("verb_action") or "")
    prop = str(event.get("relevant_prop") or "")
    is_first = (unit_idx == 0)
    is_last = (unit_idx == total_units - 1)
    rng = random.Random(seed + unit_idx * 97)

    has_zdf_family_match = (
        selected_skill == "zach-d-films"
        and any(fam in g.get("families", ()) for g in pool)
    )
    nar_low = str(event.get("narration_text") or event.get("exact_narration_phrase") or "").lower()

    candidates: List[Dict[str, Any]] = []
    for g in pool:
        c = dict(g)
        c["background_theme"] = str(event.get("lighting_mood") or "day_editorial")
        fams = c.get("families", ())
        fam_match = (fam in fams)
        if has_zdf_family_match and not fam_match:
            # Never assign a foreign-archetype setup_type to mask a ZDF stage
            continue
        if not fam_match and selected_skill == "zach-d-films" and prop not in ("roman_arena", "roman_ledger") and "roman" in c["setup"]:
            continue

        c["semantic_fit"] = 1.0 if fam_match else 0.35
        if fam == "boston_street_hook":
            is_suspense = ("nobody" in nar_low or "expected" in nar_low or "unlike" in nar_low) and ("1919" not in nar_low)
            if (is_suspense or unit_idx > 0) and c["setup"] == "boston_street_hook_alley_pan":
                c["semantic_fit"] += 0.70
            elif (not is_suspense and unit_idx == 0) and c["setup"] == "boston_street_hook_crowd":
                c["semantic_fit"] += 0.65
        if fam == "boston_tank_rupture":
            is_blowout_follow = any(k in nar_low for k in ("gave way", "walls gave", "flood", "poured", "surge"))
            if is_blowout_follow and c["setup"] == "boston_tank_rupture_surge":
                c["semantic_fit"] += 0.45
            elif (not is_blowout_follow) and c["setup"] == "boston_tank_rupture_blast":
                c["semantic_fit"] += 0.55
        if fam == "boston_elevated_rail_impact":
            is_girder_focus = any(k in nar_low for k in ("buckled", "support", "girder", "railway", "trestle"))
            if is_girder_focus and c["setup"] == "boston_elevated_rail_truss_tilt":
                c["semantic_fit"] += 0.45
            elif (not is_girder_focus) and c["setup"] == "boston_elevated_rail_crush":
                c["semantic_fit"] += 0.55
        if fam == "boston_wave_street_flow":
            is_speed_beat = any(k in nar_low for k in ("35", "faster", "race", "speed", "horse", "per hour", "tore through", "neighborhood"))
            if is_speed_beat and c["setup"] == "boston_wave_speed_sweep":
                c["semantic_fit"] += 0.80
            elif (not is_speed_beat) and c["setup"] == "boston_wave_chase_street":
                c["semantic_fit"] += 0.65
        if fam == "boston_tank_leak_seep":
            is_scale_payoff = any(k in nar_low for k in ("poisonous", "enough of it"))
            if is_scale_payoff and c["setup"] == "boston_tank_scale_payoff":
                c["semantic_fit"] += 0.85
            elif (not is_scale_payoff) and c["setup"] == "boston_tank_leak_seep_cu":
                c["semantic_fit"] += 0.70
        if fam == "boston_rescue_aftermath":
            is_active_rescue = ("rescuer" in nar_low or "struggled" in nar_low) and not any(k in nar_low for k in ("twenty-one", "21", "died", "150"))
            if is_active_rescue and c["setup"] == "boston_rescue_lantern_wade":
                c["semantic_fit"] += 0.80
            elif (not is_active_rescue) and c["setup"] == "boston_rescue_aftermath_still":
                c["semantic_fit"] += 0.70
        if fam == "traction_machine_room":
            is_brake_beat = any(k in nar_low for k in ("brake", "caliper", "clamp", "slow", "stop"))
            if is_brake_beat and c["setup"] == "traction_caliper_brake_macro":
                c["semantic_fit"] += 0.70
            elif (not is_brake_beat) and c["setup"] == "traction_machine_room_drive":
                c["semantic_fit"] += 0.45
        if is_first and ("hook" in c["setup"] or "macro" in c["setup"] or "departure" in c["setup"] or "assembled" in c["setup"]):
            c["semantic_fit"] += 0.35
        if is_last and ("payoff" in c["setup"] or "arrival" in c["setup"] or "callout" in c["setup"] or "orbital" in c["setup"] or "horizon" in c["setup"] or "landing_doors" in c["setup"]):
            c["semantic_fit"] += 0.45
        if verb == "reveal_cutaway" and ("cutaway" in c["setup"] or "core" in c["setup"] or "pcb" in c["setup"] or "separation" in c["setup"]):
            c["semantic_fit"] += 0.55
        if verb == "scale_jump" and ("cosmic" in c["setup"] or "scale" in c["setup"] or "bridge" in c["setup"]):
            c["semantic_fit"] += 0.55

        # Transformed callback permission ONLY when motif re-appears after >=2 shots with changed scale/role
        seen_props = continuity_state.get("seen_props", {})
        c["callback_reason"] = None
        if prop in seen_props and unit_idx - seen_props[prop] >= 2 and (is_last or verb == "resolve_payoff"):
            c["callback_reason"] = f"Transformed narrative payoff callback to `{prop}` with shifted framing/scale"
            c["lighting_mood"] = "warm_payoff"
            c["background_theme"] = "warm_payoff"

        c["prop_count"] = max(1, len(event.get("grounded_props", [prop])))
        c["jitter"] = round(rng.uniform(0.0, 0.03), 4)
        candidates.append(c)

    if not candidates:
        candidates = [dict(g, semantic_fit=0.5, background_theme=str(event.get("lighting_mood") or "day_editorial"), prop_count=1, callback_reason=None, jitter=0.0) for g in pool]
    return candidates


def score_shot_candidates(
    candidates: List[Dict[str, Any]],
    event: Dict[str, Any],
    continuity_state: Dict[str, Any],
    scene_novelty: str = "standard",
) -> List[Tuple[float, Dict[str, Any], str]]:
    """Score candidates: reward semantic clarity & camera motivation; penalize adjacent clones."""
    history: List[Dict[str, Any]] = continuity_state.get("history", [])[-3:]
    prev = history[-1] if history else None
    novelty_mult = 1.45 if scene_novelty == "high" else 1.0

    scored: List[Tuple[float, Dict[str, Any], str]] = []
    for c in candidates:
        score = float(c.get("semantic_fit", 0.5)) * 2.2
        reasons: List[str] = [f"semantic_fit={c.get('semantic_fit', 0.5):.2f}"]

        if c.get("novel_non_template"):
            score += 0.35 * novelty_mult

        if prev is not None:
            # Strict anti-repetition penalties against immediate & rolling 3-shot window
            if c["setup"] == prev.get("setup_type") and not c.get("callback_reason"):
                score -= 3.5 * novelty_mult
                reasons.append("penalty:same_adjacent_setup")
            if (c["framing"], c["angle"], c["move"]) == (
                prev.get("framing"), prev.get("angle"), prev.get("movement")
            ):
                score -= 3.2 * novelty_mult
                reasons.append("penalty:same_cam_triple")
            if c.get("pose") == prev.get("pose_tag"):
                score -= 1.2 * novelty_mult
            if c.get("background_theme") == prev.get("background_theme"):
                score -= 0.75 * novelty_mult
            if c.get("placement") == prev.get("subject_placement"):
                score -= 0.85 * novelty_mult
            if c.get("focal_mm") == prev.get("focal_length_mm"):
                score -= 0.45 * novelty_mult
            if c.get("silhouette") == prev.get("silhouette_tag"):
                score -= 1.4 * novelty_mult
            if c.get("move") != prev.get("movement"):
                score += 0.55 * novelty_mult
            if c.get("placement") != prev.get("subject_placement"):
                score += 0.45 * novelty_mult

        # Rolling window repetition check (last 3 shots)
        recent_setups = [h.get("setup_type") for h in history]
        freq = recent_setups.count(c["setup"])
        if freq > 0 and not c.get("callback_reason"):
            score -= (1.1 * freq) * novelty_mult
            reasons.append(f"penalty:recent_freq={freq}")

        if c.get("callback_reason"):
            score += 0.6
            reasons.append(f"callback:{c['callback_reason']}")

        score += float(c.get("jitter", 0.0))
        scored.append((round(score, 4), c, "; ".join(reasons)))

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def plan_intra_shot_changes(
    shot_spec: Dict[str, Any],
    event: Dict[str, Any],
    fps: int = 30,
) -> List[Dict[str, Any]]:
    """Schedule deterministic inside-shot visual updates (no extra cut) grounded in the event."""
    st = float(shot_spec["start"])
    en = float(shot_spec["end"])
    dur = max(0.25, en - st)
    changes: List[Dict[str, Any]] = []
    for act in event.get("intra_shot_activities", []):
        rel_n = max(0.12, min(0.92, float(act.get("rel_norm", 0.5))))
        abs_t = round(st + dur * rel_n, 3)
        changes.append({
            "time_sec": abs_t,
            "shot_relative_sec": round(abs_t - st, 3),
            "frame": int(round(abs_t * fps)),
            "type": act.get("type", "information_reveal"),
            "detail": act.get("detail", ""),
        })
    return changes


def select_sequence_with_diversity_constraints(
    units: List[Dict[str, Any]],
    grammar: Optional[List[Dict[str, Any]]],
    selected_skill: str,
    seed: int,
    fps: int = 30,
    edit_energy: str = "balanced",
    scene_novelty: str = "standard",
    transition_policy: str = "motivated",
    existing_visual_plan: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Select an anti-repetitive sequence of shots respecting rolling 3-shot diversity."""
    history: List[Dict[str, Any]] = []
    seen_props: Dict[str, int] = {}
    manual_shots = (existing_visual_plan or {}).get("shots", []) if isinstance(existing_visual_plan, dict) else []
    selected_shots: List[Dict[str, Any]] = []
    total_units = len(units)

    for idx, unit in enumerate(units):
        cands = generate_candidate_shot_set(
            event=unit,
            grammar=grammar,
            scene_state={"shot_index": idx},
            continuity_state={"history": history, "seen_props": seen_props},
            seed=seed,
            selected_skill=selected_skill,
            unit_idx=idx,
            total_units=total_units,
        )
        ranked = score_shot_candidates(
            candidates=cands,
            event=unit,
            continuity_state={"history": history, "seen_props": seen_props},
            scene_novelty=scene_novelty,
        )
        best_score, chosen, rationale = ranked[0]

        # Enforce hard non-adjacent clone guard whenever >= 2 distinct candidates exist
        if history and chosen["setup"] == history[-1]["setup_type"] and not chosen.get("callback_reason"):
            for sc, cand, rsn in ranked[1:]:
                if cand["setup"] != history[-1]["setup_type"]:
                    best_score, chosen, rationale = sc, cand, rsn + " (anti_clone_override)"
                    break

        # Enforce strict non-adjacent camera triplet rotation so consecutive shots never clone (framing, angle, move)
        prev_triplet = (history[-1]["framing"], history[-1]["angle"], history[-1]["movement"]) if history else None
        cur_triplet = (chosen["framing"], chosen["angle"], chosen["move"])
        if prev_triplet is not None and cur_triplet == prev_triplet:
            swapped = False
            for sc, cand, rsn in ranked[1:]:
                if (cand["framing"], cand["angle"], cand["move"]) != prev_triplet:
                    best_score, chosen, rationale = sc, cand, rsn + " (anti_triplet_override)"
                    swapped = True
                    break
            if not swapped:
                chosen = dict(chosen)
                alt_moves = ("reframe_track_sweep", "arc_pull_alt", "slow_tilt_shift")
                fr = str(chosen["framing"])
                chosen["framing"] = ("MCU_" + fr.split("_", 1)[-1]) if not fr.startswith("MCU") else ("WS_" + fr.split("_", 1)[-1])
                ang = str(chosen["angle"])
                chosen["angle"] = f"{ang}_reverse" if not ang.endswith("_reverse") else f"{ang}_alt"
                chosen["move"] = alt_moves[idx % len(alt_moves)]
                rationale = rationale + " (synthetic_triplet_rotate)"

        # Honor explicit manual shot lock if provided in --visual-plan-in and validated for this skill
        manual_override = manual_shots[idx] if idx < len(manual_shots) and isinstance(manual_shots[idx], dict) and manual_shots[idx].get("manual") else None
        setup_name = str(manual_override["setup_type"]) if manual_override and manual_override.get("setup_type") else chosen["setup"]
        is_last = (idx == total_units - 1)
        tr_out = (
            str(manual_override["transition_out"])
            if manual_override and manual_override.get("transition_out")
            else _select_transition_hint(unit, chosen, is_last=is_last, transition_policy=transition_policy)
        )

        st_sec = round(float(unit["start_sec"]), 3)
        en_sec = round(float(unit["end_sec"]), 3)
        shot_dur = round(en_sec - st_sec, 3)

        ca_raw = unit.get("contact_action")
        contact_action = None
        if isinstance(ca_raw, dict):
            ca_copy = dict(ca_raw)
            rel_hit = max(0.15, min(shot_dur - 0.12, float(ca_copy.get("hit_time_rel_sec", shot_dur * 0.44))))
            ca_copy["hit_time_rel_sec"] = round(rel_hit, 3)
            ca_copy["hit_time_sec"] = round(st_sec + rel_hit, 3)
            contact_action = ca_copy

        locked_kfs = None
        cam_locked = False
        if manual_override:
            cam_locked = bool(manual_override.get("camera_locked", False))
            if isinstance(manual_override.get("camera_path"), dict) and manual_override["camera_path"].get("keyframes"):
                locked_kfs = manual_override["camera_path"]["keyframes"]
                cam_locked = True
            elif manual_override.get("locked_camera_keyframes"):
                locked_kfs = manual_override["locked_camera_keyframes"]
                cam_locked = True

        shot_entry: Dict[str, Any] = {
            "shot_id": f"shot_{idx:02d}",
            "index": idx,
            "engine": selected_skill,
            "event_ids": list(unit.get("event_ids", [unit["event_id"]])),
            "beat_id": unit["beat_id"],
            "beat_role": unit["beat_role"],
            "narration_text": unit["narration_text"],
            "narration_span_start": unit["narration_span_start"],
            "narration_span_end": unit["narration_span_end"],
            "start": st_sec,
            "end": en_sec,
            "duration": shot_dur,
            "setup_type": setup_name,
            "scene_family": unit["scene_family"],
            "scale_level": unit["scale_level"],
            "lighting_mood": unit["lighting_mood"],
            "novel_non_template": bool(chosen.get("novel_non_template", False)),
            "visual_objective": unit.get("visual_objective", ""),
            "desired_novelty_axis": unit.get("desired_novelty_axis", ""),
            "callback_reason": chosen.get("callback_reason"),
            "manual": bool(manual_override),
            "camera_locked": cam_locked,
            "locked_camera_keyframes": locked_kfs,
            "semantic_relation": unit.get("semantic_relation"),
            "unsupported_exact_domain": unit.get("unsupported_exact_domain"),
            "camera": {
                "framing": chosen["framing"],
                "angle": chosen["angle"],
                "movement": chosen["move"],
                "focal_length_mm": chosen["focal_mm"],
                "parallax_planes": 3 if selected_skill in ("stick-figure", "zach-d-films", "map-route") else 2,
                "eye_focus_target": unit["relevant_prop"],
            },
            "staging": {
                "action": f"{unit['subject']} {unit['verb_action']} ({unit['relevant_prop']})",
                "subject": unit["subject"],
                "character_id": unit.get("character_id"),
                "verb_action": unit["verb_action"],
                "visual_metaphor": unit["relevant_prop"],
                "secondary_prop": unit["grounded_props"][1] if len(unit["grounded_props"]) > 1 else unit["relevant_prop"],
                "grounded_props": list(unit["grounded_props"]),
                "scene_family": unit["scene_family"],
                "scale_level": unit["scale_level"],
                "subject_placement": chosen["placement"],
                "silhouette_tag": chosen["silhouette"],
                "pose_tag": chosen["pose"],
                "background_theme": chosen["background_theme"],
                "contact_action": contact_action,
                "intentional_hold": bool(unit.get("verb_action") == "strike_halt" and "slow" in str(unit.get("narration_text", "")).lower()),
                "character_expression": (
                    "curious_smirk" if idx == 0 else
                    "surprised_wide" if unit.get("has_contrast") else
                    "focused_squint" if chosen.get("novel_non_template") else
                    "confident_grin" if is_last else "attentive_look"
                ),
                "organic_motion": [
                    "anticipation_ease_in",
                    "arc_trajectory",
                    "squash_stretch_settle",
                    "secondary_ambient_drift",
                ],
                "forbidden_elements": list(unit.get("forbidden_elements", [])),
            },
            "transition_out": tr_out,
            "rationale": rationale,
            "candidate_score": best_score,
        }
        shot_entry["intra_shot_events"] = plan_intra_shot_changes(shot_entry, unit, fps=fps)
        selected_shots.append(shot_entry)

        history.append({
            "setup_type": shot_entry["setup_type"],
            "framing": chosen["framing"],
            "angle": chosen["angle"],
            "movement": chosen["move"],
            "focal_length_mm": chosen["focal_mm"],
            "subject_placement": chosen["placement"],
            "silhouette_tag": chosen["silhouette"],
            "pose_tag": chosen["pose"],
            "background_theme": chosen["background_theme"],
        })
        for p in unit.get("grounded_props", []):
            seen_props[p] = idx

    diversity_summary = {
        "total_shots": len(selected_shots),
        "unique_setups": len({s["setup_type"] for s in selected_shots}),
        "unique_scene_families": len({s["scene_family"] for s in selected_shots}),
        "unique_movements": len({s["camera"]["movement"] for s in selected_shots}),
        "adjacent_identical_setups": sum(
            1 for k in range(1, len(selected_shots))
            if selected_shots[k]["setup_type"] == selected_shots[k - 1]["setup_type"]
        ),
        "adjacent_identical_cam_triples": sum(
            1 for k in range(1, len(selected_shots))
            if (
                selected_shots[k]["camera"]["framing"],
                selected_shots[k]["camera"]["angle"],
                selected_shots[k]["camera"]["movement"],
            ) == (
                selected_shots[k - 1]["camera"]["framing"],
                selected_shots[k - 1]["camera"]["angle"],
                selected_shots[k - 1]["camera"]["movement"],
            )
        ),
        "total_intra_shot_events": sum(len(s["intra_shot_events"]) for s in selected_shots),
    }
    return selected_shots, diversity_summary


def validate_coverage(
    coverage: Dict[str, Any],
    visual_events: Dict[str, Any],
    selected_skill: str,
    fps: int = 30,
) -> Dict[str, Any]:
    """Enforce contiguous frames, zero gaps/overlaps, zero foreign skills, and full event coverage."""
    if selected_skill not in VALID_SKILLS:
        raise ValueError(f"Invalid locked skill: {selected_skill!r}")
    shots = coverage.get("shots") or []
    if not shots:
        raise ValueError("Shot coverage produced zero shots.")
    total_dur = float(visual_events["total_duration_sec"])

    covered_event_ids = set()
    prev_end = 0.0
    for idx, s in enumerate(shots):
        if s.get("engine") != selected_skill:
            raise ValueError(f"Shot {s.get('shot_id')} leaked foreign engine {s.get('engine')!r}")
        st = float(s["start"])
        en = float(s["end"])
        if idx == 0 and abs(st - 0.0) > 1e-3:
            raise ValueError(f"Coverage must start at t=0.0, got {st}")
        if abs(st - prev_end) > 0.02:
            raise ValueError(f"Coverage gap/overlap before {s.get('shot_id')}: {prev_end} -> {st}")
        if en <= st + 0.08:
            raise ValueError(f"Shot {s.get('shot_id')} has non-positive duration: [{st}, {en}]")
        prev_end = en
        for eid in s.get("event_ids", []):
            covered_event_ids.add(eid)
        # Ensure split shots inside the same beat never duplicate identical full narration strings adjacently
        if idx > 0 and s["narration_text"] == shots[idx - 1]["narration_text"] and s["beat_id"] == shots[idx - 1]["beat_id"]:
            raise ValueError(
                f"Shot {s['shot_id']} duplicates exact narration_text of {shots[idx - 1]['shot_id']}: {s['narration_text']!r}"
            )

    if abs(prev_end - total_dur) > 0.06:
        raise ValueError(f"Coverage end {prev_end} != total_duration {total_dur}")

    expected_eids = {ev["event_id"] for ev in visual_events.get("events", [])}
    missing = sorted(expected_eids - covered_event_ids)
    if missing:
        raise ValueError(f"Coverage missed semantic events: {missing}")

    return {"ok": True, "shots_count": len(shots), "covered_events": len(covered_event_ids)}


def plan_editorial_coverage(
    visual_events: Dict[str, Any],
    parsed_script: Dict[str, Any],
    selected_skill: str,
    fps: int = 30,
    seed: int = 42,
    preset: str = "dynamic",
    edit_energy: Optional[str] = None,
    scene_novelty: str = "standard",
    transition_policy: str = "motivated",
    max_static_hold_sec: Optional[float] = None,
    existing_visual_plan: Optional[Dict[str, Any]] = None,
    run_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Generate validated variable-length shot coverage (`<run>/shot_coverage.json`)."""
    eff_energy = edit_energy or preset or "balanced"
    if selected_skill == "minimalistic-graphics" and edit_energy is None:
        eff_energy = "calm"

    max_hold = max_static_hold_sec
    if max_hold is None:
        max_hold = 3.5 if eff_energy == "dynamic" else (4.8 if eff_energy == "balanced" else 6.5)

    full_script_low = " ".join(str(b.get("text") or "") for b in (parsed_script.get("beats") or [])).lower()
    units = split_long_visual_beats_by_actions(
        list(visual_events.get("events", [])),
        preset=eff_energy,
        max_shot_dur=max_hold,
        fps=fps,
        full_script_low=full_script_low,
    )
    shots, div_summary = select_sequence_with_diversity_constraints(
        units=units,
        grammar=ENGINE_CANDIDATE_SPACES[selected_skill],
        selected_skill=selected_skill,
        seed=seed,
        fps=fps,
        edit_energy=eff_energy,
        scene_novelty=scene_novelty,
        transition_policy=transition_policy,
        existing_visual_plan=existing_visual_plan,
    )

    coverage: Dict[str, Any] = {
        "schema_version": "sd-shot-coverage-1",
        "selected_skill": selected_skill,
        "origin_skills": [selected_skill],
        "seed": seed,
        "fps": fps,
        "edit_energy": eff_energy,
        "scene_novelty": scene_novelty,
        "transition_policy": transition_policy,
        "max_static_hold_sec": max_hold,
        "total_duration_sec": visual_events["total_duration_sec"],
        "diversity_summary": div_summary,
        "shots": shots,
    }
    validate_coverage(coverage, visual_events=visual_events, selected_skill=selected_skill, fps=fps)

    if run_dir is not None:
        (run_dir / "shot_coverage.json").write_text(
            json.dumps(coverage, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return coverage
