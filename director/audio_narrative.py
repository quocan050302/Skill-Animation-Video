"""Audio Narrative Analyzer, Grounded SFX Event Extractor, and Dynamic Score Planner.

Analyzes actual storyboard shots, camera motion, visual metaphors/props, transitions,
and timed words to schedule purposeful music arcs and visually grounded SFX cues
(zero blind per-cut whooshes, zero hallucinated ungrounded objects).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_POLICY = {
    "target_lufs": -14.0,
    "lufs_tolerance_db": 2.0,
    "max_true_peak_dbtp": -1.5,
    "hard_clip_limit_dbtp": -1.0,
    "onset_tolerance_frames": 1,
}


def _finite(val: float, name: str) -> float:
    f = float(val)
    if not math.isfinite(f):
        raise ValueError(f"Non-finite float for '{name}': {val!r}")
    return f


def _derive_story_theme(selected_skill: str, motifs: List[str], narration_joined: str) -> Tuple[str, str, int]:
    """Choose ONE cohesive musical key/theme and BPM appropriate to the script & engine."""
    low = narration_joined.lower()
    mset = set(motifs)

    if selected_skill == "minimalistic-graphics":
        return "calm", "C_pentatonic", 88
    if "roman_gladiator" in mset or any(k in low for k in ("gladiator", "danger", "killing", "death", "penalty")):
        return "tension", "D_dorian", 104
    if selected_skill == "zach-d-films":
        return "tension", "E_minor", 106
    if selected_skill == "breakdown":
        return "mystery", "A_minor", 100
    if selected_skill == "map-route":
        return "wonder", "F_lydian", 108
    if selected_skill == "graph":
        return "curious", "G_mixolydian", 112
    # Default narrative stick-figure
    return "curious", "D_minor", 108


def _shot_visual_evidence(shot: Dict[str, Any], global_motifs: List[str]) -> Dict[str, Any]:
    """Inspect only grounded visual properties explicitly planned on this shot."""
    staging = shot.get("staging") or {}
    cam = shot.get("camera") or {}
    grounded_props = staging.get("grounded_props")
    vis_metaphor = str(staging.get("visual_metaphor") or "").lower()
    sec_prop = str(staging.get("secondary_prop") or "").lower()

    if isinstance(grounded_props, list):
        props = {str(p).lower() for p in grounded_props}
        strict_props_only = True
    else:
        props = {p for p in (vis_metaphor, sec_prop) if p}
        strict_props_only = False

    return {
        "engine": str(shot.get("engine") or ""),
        "setup_type": str(shot.get("setup_type") or ""),
        "scene_family": str(shot.get("scene_family") or staging.get("scene_family") or ""),
        "domain": str(shot.get("domain") or staging.get("domain") or ""),
        "beat_role": str(shot.get("beat_role") or ""),
        "transition_out": str(shot.get("transition_out") or "cut"),
        "framing": str(cam.get("framing") or ""),
        "cam_movement": str(cam.get("movement") or ""),
        "novel": bool(shot.get("novel_non_template", False)),
        "props": props,
        "strict_props_only": strict_props_only,
        "global_motifs": {str(m).lower() for m in global_motifs},
        "narration_low": str(shot.get("narration_text") or "").lower(),
        "contact_action": staging.get("contact_action") if isinstance(staging.get("contact_action"), dict) else None,
    }


def extract_sound_events(
    shot: Dict[str, Any],
    previous_shot: Optional[Dict[str, Any]],
    next_shot: Optional[Dict[str, Any]],
    words: List[Dict[str, Any]],
    selected_skill: Optional[str] = None,
    global_motifs: Optional[List[str]] = None,
    density: str = "balanced",
) -> List[Dict[str, Any]]:
    """Derive grounded, time-accurate Sound Events for a single storyboard shot.

    - Strictly ties cues to on-screen visual actions/props or motivated camera transitions.
    - Omits weak or ungrounded cues cleanly (zero sword clashes on non-sword scenes).
    """
    st = float(shot.get("start", 0.0))
    en = float(shot.get("end", st + 1.0))
    dur = max(0.05, en - st)
    sid = str(shot.get("shot_id") or f"shot_{int(shot.get('index', 0)):02d}")
    ev = _shot_visual_evidence(shot, global_motifs or [])
    eng = selected_skill or ev["engine"]
    setup = ev["setup_type"]
    props = ev["props"]
    strict_props = ev["strict_props_only"]
    nar = ev["narration_low"]
    tr = ev["transition_out"]

    events: List[Dict[str, Any]] = []

    def _add(rel_t: float, event_name: str, intent: str, kind: str, gain_db: float, pan: float,
             conf: float, emph: float, prio: int, evidence: str, depth: str = "mid", uncert: float = 0.02) -> None:
        if rel_t < 0.0 or rel_t >= dur - 0.03:
            return
        abs_t = round(st + rel_t, 3)
        events.append({
            "time_sec": abs_t,
            "shot_relative_sec": round(rel_t, 3),
            "shot_id": sid,
            "event": event_name,
            "intent": intent,
            "kind": kind,
            "gain_db": round(gain_db, 2),
            "pan": round(max(-0.6, min(0.6, pan)), 2),
            "depth": depth,
            "confidence": round(conf, 2),
            "emphasis": round(emph, 2),
            "priority": prio,
            "time_uncertainty_sec": round(uncert, 3),
            "manual": False,
            "evidence": evidence,
        })

    # 1. Grounded hook anticipation / reveal (NO automatic hardcoded pop unless camera/action starts fast!)
    is_shot_roman = (
        ev["domain"] == "historical_roman"
        or "roman" in ev["setup_type"]
        or ("roman_gladiator" in ev["global_motifs"] and not ev["domain"] and not strict_props)
    )
    if previous_shot is None:
        if eng == "minimalistic-graphics":
            # Subtle solitary dot pulse in quiet negative space
            _add(0.14, "dot_breath_pulse", "brain_spark_chime", "ui", -18.0, 0.0, 0.72, 0.45, 3, f"{sid}.setup:{setup}", depth="far", uncert=0.05)
        elif eng == "zach-d-films" and is_shot_roman:
            _add(0.18, "arena_sword_draw", "sword_draw_scrape", "foley", -10.5, -0.18, 0.88, 0.70, 2, f"{sid}.gladius_raise", depth="mid", uncert=0.04)
            _add(0.45, "gold_stack_settle", "coin_clink_cascade", "foley", -12.0, 0.14, 0.85, 0.65, 3, f"{sid}.coins_plinth", depth="mid", uncert=0.05)
        elif ("push" in ev["cam_movement"] or "launch" in setup or "drop" in str(ev["props"])) and str(shot.get("procedural_generator") or "") != "zach3d:elevator_lobby_button_stage":
            _add(0.10, "hook_reveal", "soft_impact", "reveal", -12.5, 0.0, 0.78, 0.58, 3, f"{sid}.camera:{ev['cam_movement']}", depth="mid", uncert=0.04)

    # 2. Engine + Setup + Procedural Generator Visually Grounded Action Foley
    proc_gen = str(shot.get("procedural_generator") or "")
    ca = ev.get("contact_action")
    if eng == "zach-d-films":
        is_roman = (
            ev["domain"] == "historical_roman"
            or "roman" in setup
            or (("roman_gladiator" in ev["global_motifs"] or "roman_ledger_50x" in ev["global_motifs"]) and not ev["domain"] and not strict_props)
        )
        if proc_gen == "zach3d:elevator_lobby_button_stage":
            # Sync strictly to exact physical fingertip contact timestamp `hit_time_rel_sec` (<= 1 frame tolerance)
            hit_rel = float(ca.get("hit_time_rel_sec", dur * 0.44)) if isinstance(ca, dict) else dur * 0.44
            _add(hit_rel, "elevator_call_button_press", "elevator_button_click", "impact", -8.0, 0.06, 0.98, 0.94, 1, f"{sid}.finger_button_contact.hit={hit_rel:.3f}", depth="near", uncert=0.015)
        elif proc_gen == "zach3d:controller_cabinet_cutaway_stage":
            _add(min(dur * 0.22, 0.28), "cabinet_cutaway_open", "mechanical_click", "foley", -10.5, -0.06, 0.90, 0.78, 2, f"{sid}.cabinet_clip_plane", depth="near", uncert=0.025)
            _add(dur * 0.44, "relay_contactor_snap", "relay_cabinet_click", "foley", -9.5, 0.08, 0.94, 0.84, 1, f"{sid}.relay_contactor_close", depth="near", uncert=0.02)
            _add(min(dur - 0.12, dur * 0.68), "vfd_bus_signal_pulse", "electric_spark_pulse", "foley", -12.0, 0.0, 0.86, 0.70, 2, f"{sid}.vfd_inverter_trace", depth="near", uncert=0.03)
        elif proc_gen == "zach3d:traction_machine_room_stage":
            _add(min(dur * 0.24, 0.30), "traction_motor_engage", "motor_drive_hum", "foley", -11.0, 0.0, 0.92, 0.80, 2, f"{sid}.traction_sheave_drive", depth="mid", uncert=0.025)
            if "brake" in nar or "slow" in nar or "caliper" in nar:
                _add(dur * 0.56, "caliper_brake_lock", "relay_cabinet_click", "foley", -9.5, -0.08, 0.90, 0.78, 1, f"{sid}.disc_brake_clamp", depth="near", uncert=0.025)
        elif proc_gen == "zach3d:elevator_shaft_cutaway_stage":
            _add(min(dur * 0.22, 0.26), "shaft_cutaway_reveal", "mechanical_click", "foley", -11.0, 0.0, 0.88, 0.72, 2, f"{sid}.hoistway_clip_plane", depth="mid", uncert=0.03)
            _add(dur * 0.46, "hoist_cable_pulley_whir", "sheave_cable_whir", "foley", -10.5, 0.06, 0.90, 0.78, 2, f"{sid}.steel_ropes_counterweight", depth="mid", uncert=0.03)
        elif proc_gen == "zach3d:elevator_landing_doors_stage":
            _add(min(dur * 0.25, 0.30), "floor_arrival_ding", "elevator_arrival_chime", "emphasis", -8.5, 0.0, 0.96, 0.90, 1, f"{sid}.hall_lantern_chime", depth="near", uncert=0.02)
            _add(min(dur - 0.14, dur * 0.44), "steel_doors_glide_open", "door_slide_open", "foley", -10.5, 0.0, 0.90, 0.78, 2, f"{sid}.bi_parting_doors", depth="mid", uncert=0.025)
        elif proc_gen == "zach3d:schematic_mechanism_stage":
            _add(dur * 0.30, "schematic_linkage_engage", "mechanical_click", "foley", -10.5, 0.0, 0.88, 0.74, 2, f"{sid}.schematic_linkage", depth="near", uncert=0.03)
        elif proc_gen == "zach3d:human_device_stage":
            if "phone_screen" in props or not strict_props:
                t_tap = float(ca.get("hit_time_rel_sec", dur * 0.42)) if isinstance(ca, dict) else dur * 0.42
                _add(t_tap, "screen_tap_send", "glass_tap_ui", "ui", -9.5, 0.08, 0.94, 0.86, 1, f"{sid}.phone_tap_T_TAP", depth="near", uncert=0.015)
        elif proc_gen == "zach3d:device_cutaway_stage":
            if "microchip_pcb" in props or "battery_cell" in props or "phone_screen" in props or not strict_props:
                _add(min(dur * 0.25, 0.24), "chassis_shell_peel", "mechanical_click", "foley", -10.5, -0.08, 0.90, 0.78, 2, f"{sid}.frontGlass_peel", depth="near", uncert=0.02)
                _add(dur * 0.55, "circuit_signal_arc", "electric_spark_pulse", "foley", -12.0, 0.12, 0.88, 0.72, 2, f"{sid}.pcb_copper_pulses", depth="near", uncert=0.03)
        elif proc_gen == "zach3d:network_relay_stage":
            if "cell_tower_wave" in props or not strict_props:
                _add(dur * 0.30, "rf_wavefront_pulse", "electric_spark_pulse", "foley", -11.5, 0.0, 0.88, 0.74, 2, f"{sid}.tower_rfRings", depth="mid", uncert=0.03)
        elif proc_gen == "zach3d:subsea_fiber_stage":
            if "subsea_fiber_cable" in props or "ocean_nature" in props or not strict_props:
                _add(dur * 0.32, "subsea_water_surge", "subsea_bubble_hum", "foley", -12.5, -0.10, 0.88, 0.70, 2, f"{sid}.subsea_cable_seabed", depth="mid", uncert=0.04)
                if density != "sparse":
                    _add(dur * 0.65, "fiber_photon_ping", "brain_spark_chime", "emphasis", -13.5, 0.12, 0.82, 0.60, 3, f"{sid}.fiber_pulses", depth="near", uncert=0.03)
        elif proc_gen == "zach3d:datacenter_aisle_stage":
            if "datacenter_rack" in props or not strict_props:
                _add(dur * 0.30, "server_rack_switch", "clock_tick", "foley", -12.5, 0.0, 0.86, 0.65, 2, f"{sid}.datacenter_packets", depth="mid", uncert=0.03)
        elif proc_gen == "zach3d:power_turbine_stage":
            if "power_turbine" in props or "battery_cell" in props or not strict_props:
                _add(dur * 0.35, "turbine_stator_charge", "electric_spark_pulse", "foley", -11.0, 0.08, 0.90, 0.76, 2, f"{sid}.power_turbine_rotor", depth="near", uncert=0.025)
        elif proc_gen == "zach3d:cosmic_scale_bridge_stage":
            if "cosmic_origin" in props or "atom_crystal" in props or not strict_props:
                _add(dur * 0.24, "cosmic_genesis_swell", "cosmic_swell", "reveal", -10.5, 0.0, 0.90, 0.82, 2, f"{sid}.cosmic_star_core", depth="far", uncert=0.03)
        elif proc_gen == "zach3d:anatomical_cutaway_stage":
            if "brain_neuron" in props or "heart_organ" in props or not strict_props:
                _add(dur * 0.35, "organ_synapse_pulse", "soft_impact" if "heart_organ" in props else "brain_spark_chime", "foley", -11.5, 0.0, 0.88, 0.74, 2, f"{sid}.anatomical_cutaway", depth="near", uncert=0.03)
        elif setup == "novel_slowmo_ripple_cutaway":
            # Exact blade halt / projectile impact time matches adapter TI = dur * 0.46 (roman) or 0.48 (armor)
            ti = dur * (0.46 if is_roman else 0.48)
            _add(max(0.05, ti - 0.34), "slowmo_blade_sweep", "riser_tension", "emphasis", -12.5, 0.12, 0.90, 0.72, 2, f"{sid}.slowmo_blade_descent", depth="near", uncert=0.02)
            _add(ti, "halted_blade_ring" if is_roman else "impact_ripple_pulse", "sword_blade_ring" if is_roman else "heavy_thud", "impact", -7.5, 0.0, 0.96, 0.95, 1, f"{sid}.{setup}.TI={ti:.2f}", depth="near", uncert=0.015)
        elif setup == "mechanism_cross_section_3d":
            tslam = dur * 0.24 if is_roman else dur * 0.28
            if is_roman:
                _add(tslam, "scale_50x_coin_slam", "coin_clink_cascade", "foley", -7.5, 0.16, 0.95, 0.92, 1, f"{sid}.balanceScale50x.TSLAM={tslam:.2f}", depth="near", uncert=0.015)
                _add(tslam + 0.02, "scale_beam_impact", "heavy_thud", "impact", -9.0, 0.14, 0.92, 0.88, 1, f"{sid}.balanceScale50x.beam", depth="near", uncert=0.02)
            else:
                _add(tslam, "cutaway_slab_separate", "mechanical_click", "foley", -10.0, 0.0, 0.88, 0.76, 2, f"{sid}.cutawaySlabStack.sep", depth="near", uncert=0.03)
        elif is_roman:
            if "knocked into the sand" in nar or "stands over him" in nar:
                if "knocked" in nar:
                    _add(min(dur * 0.45, 0.28), "gladiator_sand_fall", "sand_thud", "foley", -8.5, -0.16, 0.90, 0.82, 1, f"{sid}.sand_impact_dust", depth="mid", uncert=0.04)
                elif density != "sparse":
                    _add(min(dur * 0.40, 0.75), "sword_raise_steel", "sword_draw_scrape", "foley", -12.0, -0.10, 0.82, 0.62, 2, f"{sid}.ikArm_sword_raise", depth="mid", uncert=0.05)
            elif "train" in nar or "feed" in nar or "prepare" in nar:
                th = min(dur * 0.72, 1.25)
                _add(th, "training_palus_strike", "metal_shield_clang", "foley", -8.5, 0.14, 0.92, 0.84, 1, f"{sid}.trainingPalus.TH=1.25", depth="mid", uncert=0.02)
            elif "rented" in nar or "owners" in nar:
                _add(0.45, "rental_coin_stack", "coin_clink_cascade", "foley", -11.5, 0.0, 0.84, 0.65, 2, f"{sid}.denariusStack", depth="mid", uncert=0.05)
            elif "mercy" in nar or "investment" in nar or "financial sense" in nar:
                if density == "detailed":
                    _add(min(dur * 0.48, 0.8), "mercy_relief_chime", "brain_spark_chime", "emphasis", -14.0, 0.0, 0.78, 0.55, 3, f"{sid}.romanScrollTablet", depth="far", uncert=0.06)
        elif props and density != "sparse":
            if "vault_gear" in props or "clock_timer" in props:
                _add(dur * 0.35, "studio_gear_click", "mechanical_click", "foley", -13.0, 0.10, 0.82, 0.58, 3, f"{sid}.vault_gears", depth="mid", uncert=0.04)

    elif eng == "stick-figure":
        if setup == "novel_mechanism_cutaway":
            # Wave threshold crossing at ~0.52 / 1.25 = 0.42 of shot dur
            t_cross = dur * 0.42
            _add(t_cross, "cutaway_threshold_cross", "brain_spark_chime", "emphasis", -10.5, 0.12, 0.90, 0.80, 2, f"{sid}.waveProg_threshold", depth="near", uncert=0.03)
            if density == "detailed":
                for k in range(3):
                    tk = 0.22 + k * 0.22
                    if tk < t_cross - 0.05:
                        _add(tk, "diagram_scan_tick", "clock_tick", "ui", -16.0, -0.12 + k * 0.12, 0.76, 0.45, 3, f"{sid}.wave_tracer", depth="near", uncert=0.02)
        elif setup == "split_comparison_stage":
            _add(0.28, "split_figure_hop", "ui_pop_subtle", "foley", -13.0, -0.25, 0.80, 0.62, 2, f"{sid}.jumpY_hop", depth="mid", uncert=0.05)
        elif ("turn" in ev["beat_role"]) and dur >= 1.2:
            _add(0.20, "turn_snap_impact", "heavy_thud", "impact", -9.5, 0.0, 0.86, 0.78, 2, f"{sid}.beat_turn_ecu", depth="near", uncert=0.03)
        elif props:
            # Grounded motif foley ONLY for objects explicitly listed in props
            if "clock" in props and density != "sparse":
                _add(0.35, "clock_prop_tick", "clock_tick", "foley", -15.5, 0.18, 0.76, 0.42, 3, f"{sid}.prop:clock", depth="mid", uncert=0.04)
            elif "scale" in props and density != "sparse":
                _add(min(dur * 0.5, 0.55), "balance_scale_clink", "coin_clink_cascade", "foley", -13.5, 0.15, 0.74, 0.50, 3, f"{sid}.prop:scale", depth="mid", uncert=0.05)

    elif eng == "minimalistic-graphics":
        if "pendulum" in setup:
            _add(dur * 0.50, "pendulum_arc_crossing", "step_gravel", "foley", -16.0, 0.0, 0.80, 0.55, 2, f"{sid}.motifPendulum", depth="far", uncert=0.04)
        elif "steps" in setup and density == "detailed":
            _add(dur * 0.35, "hairline_step_hop", "ui_pop_subtle", "ui", -17.0, 0.08, 0.72, 0.42, 3, f"{sid}.rising_hairline_steps", depth="far", uncert=0.06)

    elif eng == "graph":
        if "inflection" in setup:
            _add(dur * 0.48, "inflection_tangent_lock", "clock_tick", "ui", -13.0, 0.08, 0.86, 0.68, 2, f"{sid}.inflection_slope", depth="near", uncert=0.03)
        elif "payoff" in ev["beat_role"] or next_shot is None:
            _add(dur * 0.35, "final_metric_settle", "brain_spark_chime", "emphasis", -12.0, 0.0, 0.84, 0.70, 2, f"{sid}.final_metric", depth="near", uncert=0.05)

    elif eng == "map-route":
        if "arrival" in setup or next_shot is None:
            _add(min(dur * 0.42, 0.55), "destination_pin_drop", "ui_pin_drop", "ui", -10.5, 0.0, 0.90, 0.82, 1, f"{sid}.bouncing_pin_drop", depth="near", uncert=0.03)
        elif "bridge" in setup and density != "sparse":
            _add(dur * 0.35, "aerial_bridge_glide", "transition_sweep", "foley", -15.5, 0.0, 0.72, 0.45, 3, f"{sid}.bridge_crossing", depth="far", uncert=0.06)

    elif eng == "breakdown":
        if "separation" in setup:
            _add(0.25, "axial_layer_unlock", "mechanical_click", "foley", -11.5, -0.10, 0.88, 0.74, 2, f"{sid}.axial_layer_separation", depth="near", uncert=0.03)
        elif "core" in setup:
            _add(0.30, "internal_core_focus", "clock_tick", "ui", -13.5, 0.05, 0.82, 0.60, 2, f"{sid}.internal_core_macro", depth="near", uncert=0.03)
        elif "callout" in setup and density != "sparse":
            _add(0.28, "callout_leader_tick", "mechanical_click", "ui", -14.0, 0.16, 0.80, 0.55, 3, f"{sid}.elbow_leader_lines", depth="near", uncert=0.04)

    # Explicit custom visual_events list in shot staging (e.g. for custom objects/props dropped on screen)
    for ve in (shot.get("staging") or {}).get("visual_events", []):
        if not isinstance(ve, dict):
            continue
        rel = float(ve.get("shot_relative_sec", 0.25))
        intent = str(ve.get("intent") or "soft_impact")
        _add(
            rel,
            str(ve.get("event") or intent),
            intent,
            str(ve.get("kind") or "foley"),
            float(ve.get("gain_db", -9.0)),
            float(ve.get("pan", 0.0)),
            float(ve.get("confidence", 0.9)),
            float(ve.get("emphasis", 0.75)),
            int(ve.get("priority", 1)),
            f"{sid}.visual_event:{ve.get('evidence', 'explicit')}",
            uncert=0.02,
        )

    # 3. Grounded Payoff Resolve (skip automatic sparkle if minimalistic-graphics/quiet!)
    if next_shot is None and eng not in ("minimalistic-graphics",):
        if density != "sparse" or not events:
            _add(min(dur * 0.30, 0.40), "payoff_resolve", "brain_spark_chime", "reveal", -12.0, 0.0, 0.82, 0.70, 2, f"{sid}.payoff_hold", depth="mid", uncert=0.05)

    # 4. Motivated Camera Transition SFX (ONLY on genuine visual animated transitions, NOT bare hard cuts!)
    if next_shot is not None:
        if tr in ("whip", "whip_pan"):
            _add(max(0.05, dur - 0.14), f"{tr}_transition", "whoosh_pan", "transition", -12.5, -0.25 if shot.get("index", 0) % 2 == 0 else 0.25, 0.90, 0.72, 2, f"{sid}.transition_out:{tr}", depth="near", uncert=0.02)
        elif tr in ("iris_mask", "match_zoom", "zoom_through", "match_cut", "object_wipe"):
            _add(max(0.05, dur - 0.12), f"{tr}_transition", "transition_sweep", "transition", -14.0, 0.0, 0.85, 0.62, 2, f"{sid}.transition_out:{tr}", depth="near", uncert=0.02)
        elif tr == "dip_to_black":
            _add(max(0.05, dur - 0.06), "dip_to_black_drop", "heavy_thud", "transition", -10.0, 0.0, 0.92, 0.82, 1, f"{sid}.transition_out:dip_to_black", depth="near", uncert=0.02)
        # Note: hard `cut` and `cut_on_action` stay clean unless the action itself generates impact!

    # Respect density bounds
    if density == "sparse":
        events = [e for e in events if e["priority"] <= 2 or e["kind"] in ("impact", "transition")]

    return events


def plan_music_arc(
    beats: List[Dict[str, Any]],
    shots: List[Dict[str, Any]],
    emotion_tags: List[str],
    duration: float,
    selected_skill: str,
    narration_joined: str,
    available_beds: Optional[List[Any]] = None,
    manual_locks: Optional[List[Dict[str, Any]]] = None,
    intensity_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Build ONE coherent narrative music arc aligned to actual shot/beat turn & payoff times."""
    theme, musical_key, bpm = _derive_story_theme(selected_skill, emotion_tags, narration_joined)
    inten_mult = {"calm": 0.72, "medium": 1.0, "high": 1.24}.get((intensity_override or "medium").lower(), 1.0)

    if not shots or duration <= 6.0 or selected_skill == "minimalistic-graphics":
        segments = [{
            "segment_id": "seg_00",
            "start_sec": 0.0,
            "end_sec": round(duration, 3),
            "mood": "calm" if selected_skill == "minimalistic-graphics" else theme,
            "musical_key": musical_key,
            "bpm": bpm,
            "intensity": round(min(0.95, 0.30 * inten_mult), 3),
            "bed_id": "resolved_at_runtime",
            "crossfade_sec": 0.0,
            "source": "generated",
            "manual": False,
        }]
        return {
            "narrative_arc": ["unified_theme"],
            "theme": theme,
            "musical_key": musical_key,
            "bpm": bpm,
            "segments": segments,
        }

    # Find real turn / mechanism boundary & real payoff start from ordered shots
    n = len(shots)
    turn_idx = next((i for i, s in enumerate(shots) if "turn" in str(s.get("beat_role", "")) or s.get("novel_non_template")), max(1, n // 3))
    turn_idx = min(max(1, turn_idx), max(1, n - 1))
    payoff_idx = next((i for i in range(n - 1, 0, -1) if "payoff" in str(shots[i].get("beat_role", "")) and shots[i].get("setup_type") == "payoff_full_stage_reveal"), n - 1)
    if "payoff" not in str(shots[payoff_idx].get("beat_role", "")) and n >= 3:
        payoff_idx = n - 1

    t_turn = float(shots[turn_idx]["start"])
    t_payoff = float(shots[payoff_idx]["start"])
    if t_payoff <= t_turn + 1.5:
        t_payoff = max(t_turn + 1.5, float(shots[-1]["start"]))
    if t_payoff >= duration - 0.6:
        t_payoff = max(0.0, duration - 1.5)

    # Keep coherent single-theme progression across 3 structural movements (never 3 conflicting random tracks)
    if t_turn >= 1.8 and t_payoff > t_turn + 1.2:
        raw_segs = [
            {"start": 0.0, "end": t_turn, "mood": "mystery" if theme == "tension" else theme, "intensity": 0.34 * inten_mult, "xfade": 0.35, "stage": "setup"},
            {"start": t_turn, "end": t_payoff, "mood": "tension" if theme in ("tension", "curious") else "wonder", "intensity": 0.66 * inten_mult, "xfade": 0.42, "stage": "escalation"},
            {"start": t_payoff, "end": duration, "mood": "triumph" if theme != "mystery" else "emotional", "intensity": 0.72 * inten_mult, "xfade": 0.35, "stage": "payoff"},
        ]
        arc = ["hook", "setup", "escalation", "twist", "payoff"]
    else:
        raw_segs = [
            {"start": 0.0, "end": max(1.5, float(shots[-1]["start"])), "mood": theme, "intensity": 0.42 * inten_mult, "xfade": 0.30, "stage": "setup"},
            {"start": max(1.5, float(shots[-1]["start"])), "end": duration, "mood": "triumph", "intensity": 0.68 * inten_mult, "xfade": 0.30, "stage": "payoff"},
        ]
        arc = ["setup", "payoff"]

    segments: List[Dict[str, Any]] = []
    for idx, rs in enumerate(raw_segs):
        s_t = round(rs["start"], 3)
        e_t = round(rs["end"], 3)
        seg_dur = e_t - s_t
        if seg_dur < 0.25:
            continue
        xf = min(float(rs["xfade"]), round(seg_dur * 0.35, 3)) if idx > 0 else 0.0
        segments.append({
            "segment_id": f"seg_{len(segments):02d}",
            "stage": rs["stage"],
            "start_sec": s_t,
            "end_sec": e_t,
            "mood": rs["mood"],
            "musical_key": musical_key,
            "bpm": bpm,
            "intensity": round(min(0.95, max(0.10, rs["intensity"])), 3),
            "bed_id": "resolved_at_runtime",
            "crossfade_sec": round(xf, 3),
            "source": "generated",
            "manual": False,
        })

    if segments:
        segments[-1]["end_sec"] = round(duration, 3)

    return {
        "narrative_arc": arc,
        "theme": theme,
        "musical_key": musical_key,
        "bpm": bpm,
        "segments": segments,
    }


def preserve_manual_audio_events(
    existing_plan: Optional[Dict[str, Any]],
    generated_plan: Dict[str, Any],
    mode: str = "preserve",
) -> Dict[str, Any]:
    """Preserve user-pinned SFX cues, gain offsets, and manual music segments across re-plans."""
    if not existing_plan or mode == "overwrite":
        return generated_plan

    out = json.loads(json.dumps(generated_plan))
    collisions: List[str] = []

    # 1. Preserve manually locked music segments
    ext_music = existing_plan.get("music") or {}
    ext_segs = [s for s in ext_music.get("segments", []) if isinstance(s, dict) and s.get("manual")]
    if ext_segs:
        # Manual music segments win overlapping time windows
        kept_auto: List[Dict[str, Any]] = []
        for auto_s in out.get("music", {}).get("segments", []):
            a0, a1 = float(auto_s["start_sec"]), float(auto_s["end_sec"])
            overlaps_manual = any(
                not (a1 <= float(ms["start_sec"]) or a0 >= float(ms["end_sec"]))
                for ms in ext_segs
            )
            if overlaps_manual:
                collisions.append(f"Dropped/replaced auto music segment {auto_s.get('segment_id')} due to manual music lock.")
            else:
                kept_auto.append(auto_s)
        merged_segs = kept_auto + [dict(ms, manual=True) for ms in ext_segs]
        merged_segs.sort(key=lambda x: float(x["start_sec"]))
        out.setdefault("music", {})["segments"] = merged_segs

    # 2. Gather manual SFX cues from either `sfx` items with `manual: true` or `manual_locked_events`
    manual_sfx: List[Dict[str, Any]] = []
    seen_manual_sig = set()
    for item in list(existing_plan.get("sfx", [])) + list(existing_plan.get("manual_locked_events", [])):
        if not isinstance(item, dict):
            continue
        if item.get("manual", False) or item in existing_plan.get("manual_locked_events", []):
            sig = (round(float(item.get("time_sec", 0.0)), 3), str(item.get("event", item.get("intent", "custom"))))
            if sig in seen_manual_sig:
                continue
            seen_manual_sig.add(sig)
            pinned = dict(item)
            pinned["manual"] = True
            pinned.setdefault("priority", 0)
            manual_sfx.append(pinned)

    if manual_sfx:
        surviving_auto: List[Dict[str, Any]] = []
        for ae in out.get("sfx", []):
            at = float(ae["time_sec"])
            collides = any(abs(at - float(ms["time_sec"])) < 0.18 for ms in manual_sfx)
            if collides:
                collisions.append(
                    f"Dropped colliding auto SFX '{ae['event']}' at t={at:.3f}s in favor of manual cue"
                )
            else:
                surviving_auto.append(ae)
        merged_sfx = manual_sfx + surviving_auto
        merged_sfx.sort(key=lambda x: (float(x["time_sec"]), int(x.get("priority", 2))))
        out["sfx"] = merged_sfx
        out["manual_locked_events"] = manual_sfx

    out["manual_edits_preserved"] = bool(ext_segs or manual_sfx)
    out["manual_collision_notes"] = collisions
    return out


def validate_audio_plan(
    plan: Dict[str, Any],
    fps: int = 30,
    duration: Optional[float] = None,
) -> Dict[str, Any]:
    """Enforce bounds, finite numbers, dedup, reasonable cue ceiling, and valid fade ranges."""
    dur = float(duration if duration is not None else plan.get("total_duration_sec", 0.0))
    _finite(dur, "total_duration_sec")
    if dur <= 0.0:
        raise ValueError(f"Audio plan duration must be positive, got {dur}")

    # Validate music segments
    music = plan.get("music") or {}
    clean_segs: List[Dict[str, Any]] = []
    for idx, seg in enumerate(music.get("segments", [])):
        s_t = max(0.0, min(dur, _finite(seg.get("start_sec", 0.0), "music.start_sec")))
        e_t = max(0.0, min(dur, _finite(seg.get("end_sec", dur), "music.end_sec")))
        if e_t <= s_t + 0.02:
            raise ValueError(f"Invalid music segment bounds [{s_t}, {e_t}] at index {idx}")
        inten = max(0.0, min(1.0, _finite(seg.get("intensity", 0.5), "music.intensity")))
        xf = max(0.0, min((e_t - s_t) * 0.45, _finite(seg.get("crossfade_sec", 0.0), "music.crossfade_sec")))
        s_copy = dict(seg)
        s_copy["start_sec"] = round(s_t, 3)
        s_copy["end_sec"] = round(e_t, 3)
        s_copy["intensity"] = round(inten, 3)
        s_copy["crossfade_sec"] = round(xf, 3)
        clean_segs.append(s_copy)
    if "music" in plan:
        plan["music"]["segments"] = clean_segs

    # Validate SFX events: finite 0 <= t < dur, clamped gain/pan, deduplicated, capped well below 200
    max_allowed = min(120, max(12, int(dur * 3.0) + 6))
    raw_sfx = sorted(plan.get("sfx", []), key=lambda x: (_finite(x.get("time_sec", 0.0), "sfx.time_sec"), 0 if x.get("manual") else int(x.get("priority", 2))))
    clean_sfx: List[Dict[str, Any]] = []
    for item in raw_sfx:
        t_raw = _finite(item.get("time_sec", 0.0), "sfx.time_sec")
        if t_raw < 0.0 or t_raw >= dur:
            if item.get("manual"):
                raise ValueError(f"Manual SFX timestamp out of bounds [0, {dur}): {t_raw}")
            continue
        gdb = max(-48.0, min(6.0, _finite(item.get("gain_db", -10.0), "sfx.gain_db")))
        pan = max(-1.0, min(1.0, _finite(item.get("pan", 0.0), "sfx.pan")))
        # Deduplicate near-identical timestamp+intent (manual wins because sorted first)
        dup = any(abs(t_raw - float(prev["time_sec"])) < 0.04 and str(item.get("intent")) == str(prev.get("intent")) for prev in clean_sfx)
        if dup:
            continue
        c_item = dict(item)
        c_item["time_sec"] = round(t_raw, 3)
        c_item["gain_db"] = round(gdb, 2)
        c_item["pan"] = round(pan, 2)
        clean_sfx.append(c_item)
        if len(clean_sfx) >= max_allowed:
            break

    plan["sfx"] = clean_sfx
    return plan


def build_audio_narrative_plan(
    parsed_script: Dict[str, Any],
    storyboard: Dict[str, Any],
    run_dir: Optional[Path] = None,
    music_mode: str = "auto",
    sfx_mode: str = "auto",
    sfx_density: str = "balanced",
    music_intensity: Optional[str] = None,
    voice_expected: bool = True,
    existing_plan: Optional[Dict[str, Any]] = None,
    music_gain_db: float = 0.0,
    sfx_gain_db: float = 0.0,
) -> Dict[str, Any]:
    """Analyze storyboard + script -> validated `audio/audio_plan.json` + `audio_director_notes.md`."""
    selected_skill = storyboard["selected_skill"]
    shots = storyboard.get("shots", [])
    fps = int(storyboard.get("fps", 30))
    total_dur = float(storyboard.get("total_duration_sec", 15.0))
    motifs = list(parsed_script.get("entities_and_facts", {}).get("detected_motifs", []))
    words = list(parsed_script.get("voice", {}).get("words", []))
    beats = list(parsed_script.get("beats", []))
    joined_nar = " ".join(s.get("narration_text", "") for s in shots)

    # Music score plan
    music_plan = plan_music_arc(
        beats=beats,
        shots=shots,
        emotion_tags=motifs,
        duration=total_dur,
        selected_skill=selected_skill,
        narration_joined=joined_nar,
        intensity_override=music_intensity,
    )
    music_plan["enabled"] = (music_mode != "off")
    music_plan["mode"] = music_mode
    music_plan["gain_offset_db"] = round(float(music_gain_db), 2)
    if music_mode == "off":
        music_plan["segments"] = []
        music_plan["intentional_silence_note"] = "Music disabled by --music-mode off."

    # Sound events per ordered shot
    all_events: List[Dict[str, Any]] = []
    if sfx_mode != "off":
        for i, shot in enumerate(shots):
            prev_s = shots[i - 1] if i > 0 else None
            next_s = shots[i + 1] if i < len(shots) - 1 else None
            shot_words = [w for w in words if float(shot["start"]) <= float(w.get("s", 0.0)) <= float(shot["end"])]
            evs = extract_sound_events(
                shot=shot,
                previous_shot=prev_s,
                next_shot=next_s,
                words=shot_words,
                selected_skill=selected_skill,
                global_motifs=motifs,
                density=sfx_density,
            )
            all_events.extend(evs)

    # Scene-appropriate ambience
    is_outdoor = any(k in joined_nar.lower() for k in ("rome", "arena", "sand", "bridge", "river", "walk", "outside"))
    amb_kind = "minimal_quiet" if selected_skill == "minimalistic-graphics" else ("arena_wind_ambience" if is_outdoor else "studio_room_ambience")

    generated_plan: Dict[str, Any] = {
        "schema_version": "sd-audio-1",
        "selected_skill": selected_skill,
        "origin_skills": list(storyboard.get("origin_skills", [selected_skill])),
        "total_duration_sec": round(total_dur, 3),
        "fps": fps,
        "music": music_plan,
        "sfx_mode": sfx_mode,
        "sfx_density": sfx_density,
        "sfx_gain_offset_db": round(float(sfx_gain_db), 2),
        "sfx": all_events,
        "ambience": {
            "enabled": (selected_skill != "minimalistic-graphics") or (music_mode != "off"),
            "generator_name": amb_kind,
            "gain_db": -36.0 if selected_skill == "minimalistic-graphics" else -31.0,
        },
        "voice": {
            "expected": voice_expected,
            "duck_music_under_voice": voice_expected,
            "duck_depth_db": -10.5,
            "attack_ms": 35.0,
            "release_ms": 260.0,
        },
        "quality_policy": dict(DEFAULT_POLICY),
        "manual_locked_events": [],
        "manual_edits_preserved": False,
        "intentional_silences": [],
    }

    if not voice_expected and music_mode == "off" and sfx_mode == "off":
        generated_plan["intentional_silences"].append({"start_sec": 0.0, "end_sec": round(total_dur, 3), "reason": "All audio tracks explicitly disabled"})

    merged = preserve_manual_audio_events(existing_plan, generated_plan, mode="preserve")
    validated = validate_audio_plan(merged, fps=fps, duration=total_dur)

    if run_dir is not None:
        audio_dir = run_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        (audio_dir / "audio_plan.json").write_text(json.dumps(validated, ensure_ascii=False, indent=2), encoding="utf-8")

        # Readable Sound Director Notes
        notes = [
            f"# Audio Director Notes — `{selected_skill}`",
            "",
            f"- **Duration / FPS**: `{total_dur:.3f}s` @ `{fps} fps`",
            f"- **Music Arc**: `enabled={validated['music']['enabled']}` | `mode={music_mode}` | `theme={validated['music']['theme']}` (`{validated['music']['musical_key']}` @ `{validated['music']['bpm']} BPM`)",
            f"- **SFX Strategy**: `mode={sfx_mode}` | `density={sfx_density}` | `cues={len(validated['sfx'])}`",
            f"- **Voice / Hierarchy**: `voice_expected={voice_expected}` | Priority: Voice > Grounded Action SFX > Music / Ambience",
            "",
            "## Music Segments",
        ]
        for seg in validated["music"]["segments"]:
            notes.append(
                f"- `{seg['segment_id']}` ({seg['start_sec']:.2f}–{seg['end_sec']:.2f}s): mood=`{seg['mood']}`, intensity=`{seg['intensity']}`, xfade=`{seg['crossfade_sec']}s`, manual=`{seg.get('manual', False)}`"
            )
        notes.extend(["", "## Scheduled Grounded SFX Cues"])
        for ev in validated["sfx"]:
            notes.append(
                f"- `t={ev['time_sec']:.3f}s` (`+{ev.get('shot_relative_sec', 0):.2f}s` in `{ev['shot_id']}`): **{ev['event']}** (`{ev['intent']}`, {ev['kind']}, {ev['gain_db']} dB, pan={ev['pan']}) — evidence: `{ev['evidence']}`"
            )
        if validated.get("manual_collision_notes"):
            notes.extend(["", "## Manual Edit Precedence Log", *[f"- {x}" for x in validated["manual_collision_notes"]]])

        (audio_dir / "audio_director_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    return validated


def analyze_audio_beats(
    parsed_script: Dict[str, Any],
    storyboard: Dict[str, Any],
    run_dir: Optional[Path] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Alias matching the audio beat analyzer entrypoint for programmatic callers."""
    return build_audio_narrative_plan(
        parsed_script=parsed_script,
        storyboard=storyboard,
        run_dir=run_dir,
        **kwargs,
    )
