"""STEP 1 (ZDF-MOTION-01): Semantic-Driven Visual Event Graph, Contact Action & Relation Grounder.

Parses narration clauses, agent/verb/patient/cause-effect relations, physical contact targets,
scale shifts, unsupported exact domains, and verified voice word timings into an engine-compatible,
fact-grounded `<run>/visual_events.json` without importing any foreign visual engine.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import VALID_SKILLS


# Concrete domain prop lexicons -> strictly derived from explicit words in narration
DOMAIN_PROP_RULES: List[Tuple[str, str, str, Tuple[str, ...]]] = [
    # (prop_id, scene_family, default_scale, trigger keywords)
    ("elevator_button", "elevator_lobby_button", "macro_hand", ("elevator button", "call button", "lobby button", "press an elevator", "tiny elevator", "hall panel")),
    ("controller_pcb", "controller_cabinet_cutaway", "micro_circuit", ("controller cabinet", "control cabinet", "relay", "relays", "inverter", "tracks where", "decides when", "sends a request", "controller")),
    ("traction_motor_sheave", "traction_machine_room", "industrial_scale", ("machine room", "traction motor", "traction sheave", "brake caliper", "brake calipers", "calipers", "caliper", "sheave", "traction elevator", "above the shaft", "motor turns", "motor slows", "motor")),
    ("shaft_car_counterweight", "elevator_shaft_cutaway", "room_architecture", ("counterweight", "steel ropes", "hoist cables", "passenger cabin", "opposite directions", "hoistway", "rail switches", "rail sensors", "car's position", "car position", "approaches your floor", "the shaft")),
    ("elevator_doors", "elevator_landing_doors", "human_environment", ("doors open", "doors glide open", "landing doors", "landing", "levels with", "car levels", "elevator doors", "coordinated a whole machine", "locked at level")),
    ("power_turbine", "energy_grid", "industrial_scale", ("turbine", "turbines", "generator", "generators", "substation", "grid", "power plant", "transformer", "magnet", "steam", "spun")),
    ("datacenter_rack", "datacenter_compute", "room_architecture", ("data center", "datacenter", "server", "servers", "rack", "racks", "cluster", "cloud", "cooling", "compute", "packet", "packets")),
    ("subsea_fiber_cable", "ocean_infrastructure", "deep_ocean", ("fiber", "optic", "optical", "subsea", "undersea", "cable", "cables", "ocean", "sea", "photon", "laser", "glass strand", "deep water")),
    ("cosmic_origin", "cosmic_scale", "planetary_cosmic", ("star", "stars", "supernova", "cosmos", "universe", "solar", "sun", "galaxy", "nebula", "cosmic", "space", "earth", "atmosphere", "planet", "planets", "gravity", "stardust")),
    ("cell_tower_wave", "network_link", "street_aerial", ("tower", "towers", "antenna", "radio", "signal", "signals", "wifi", "router", "transmit", "frequency", "wave", "waves")),
    ("microchip_pcb", "electromechanical", "micro_circuit", ("chip", "chips", "microchip", "pcb", "circuit", "circuits", "processor", "electron", "electrons", "voltage", "current", "transistor", "copper trace", "copper traces", "wiring")),
    ("phone_screen", "human_device", "macro_hand", ("phone", "phones", "smartphone", "screen", "app", "chat", "message", "thumb", "finger", "text", "tap", "taps", "send", "button")),
    ("battery_cell", "electromechanical", "macro_object", ("battery", "batteries", "charge", "recharge", "lithium", "volt", "energy")),
    ("atom_crystal", "micro_matter", "atomic_scale", ("atom", "atoms", "proton", "molecule", "crystal", "quartz", "silicon", "elements", "forged")),
    ("brain_neuron", "anatomical_cutaway", "micro_bio", ("brain", "neuron", "cortex", "synapse", "sleep", "adenosine", "memory", "focus", "nap", "groggy")),
    ("heart_organ", "anatomical_cutaway", "macro_bio", ("heart", "pulse", "artery", "vein", "blood", "lung", "muscle", "nerve", "xray", "x-ray")),
    ("roman_arena", "roman_historical", "arena_human", ("gladiator", "rome", "roman", "arena", "colosseum", "sand", "opponent", "messenger")),
    ("roman_ledger", "roman_historical", "macro_object", ("fifty times", "rental fee", "rented", "denarius", "bill", "owner", "ledger", "contract", "fortune", "mercy")),
    ("sword_blade", "metallic_clash", "macro_object", ("sword", "blade", "gladius", "steel", "arrow", "bullet")),
    ("shield_impact", "metallic_clash", "macro_object", ("shield", "armor", "armour", "plate", "barrier", "protect")),
    ("vault_gear", "electromechanical", "macro_object", ("vault", "lock", "dial", "gear", "gears", "spring", "lever", "switch", "mechanism")),
    ("clock_timer", "time_pacing", "macro_object", ("clock", "timer", "minute", "minutes", "hour", "second", "seconds", "tick", "ticking", "schedule")),
    ("coin_treasure", "economy_reward", "macro_object", ("coin", "coins", "gold", "chest", "treasure", "money", "cost", "worth")),
    ("coffee_cup", "human_lifestyle", "macro_object", ("coffee", "caffeine", "cup", "mug", "morning")),
    ("balance_scale", "comparison_logic", "macro_object", ("compare", "versus", "balance", "scale", "tradeoff", "weight", "cost")),
    ("rain_courtyard", "natural_environment", "human_environment", ("rain", "water", "stone", "tile", "tiles", "courtyard", "wet", "river")),
    ("data_chart", "data_trajectory", "chart_view", ("growth", "followers", "users", "stars", "revenue", "curve", "percent", "%", "metric", "q1", "q2", "q3", "q4")),
    ("route_street", "map_navigation", "city_aerial", ("route", "street", "avenue", "bridge", "station", "block", "trip", "km", "mile", "mi", "destination")),
    ("exploded_device", "mechanical_breakdown", "studio_assembly", ("anatomy", "layer", "layers", "casing", "shell", "housing", "switch", "exploded", "inside")),
]

# Mechanisms that lack a dedicated exact 3D archetype in ZDF and must fail closed or disclose stylized schematic
UNSUPPORTED_EXACT_DOMAIN_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("bicycle_drivetrain", ("bicycle", "derailleur", "cassette", "chainring", "shifts gears", "shift gears", "bike gear")),
    ("espresso_pressure_valve", ("coffee machine", "espresso machine", "pressure valve", "steam wand", "portafilter")),
]

VERB_PATTERNS: List[Tuple[str, Tuple[str, ...]]] = [
    ("tap_activate", ("tap", "taps", "tapped", "press", "presses", "pressed", "click", "clicks", "clicked", "send", "sends", "sent", "trigger", "triggers", "triggered")),
    ("travel_stream", ("travel", "travels", "traveled", "race", "races", "raced", "flash", "flashes", "shoot", "shoots", "zip", "pulse", "pulses", "flow", "flows", "route", "routes", "cross", "crosses", "thread", "move", "moves", "moved")),
    ("reveal_cutaway", ("inside", "beneath", "within", "under", "peel", "cutaway", "open", "opens", "opened", "separate", "separates", "decode", "decodes", "reveal", "reveals", "tracks", "track")),
    ("transform_convert", ("convert", "converts", "turn into", "turns into", "become", "becomes", "shift", "shifts", "shifted", "translate", "encode", "forge", "forged", "coordinated")),
    ("scale_jump", ("zoom", "expand", "expands", "stretch", "stretches", "shrink", "shrinks", "from tiny", "cosmic", "universe", "stars", "ocean")),
    ("strike_halt", ("hit", "hits", "strike", "strikes", "knock", "knocked", "stop", "stops", "stopped", "halt", "halts", "slow", "slows", "slowed", "swing", "swings", "clash", "block")),
    ("escalate_tick", ("tick", "ticks", "climb", "climbs", "accelerate", "accelerates", "build", "builds", "compounding", "spin", "spins", "turn", "turns", "turned", "report", "reports", "approaches", "approach")),
    ("compare_weigh", ("compare", "cost", "owe", "worth", "tradeoff", "between", "versus", "more than", "less than", "decides", "decide")),
    ("resolve_payoff", ("glow", "gleam", "spark", "bright", "complete", "arrive", "arrived", "alive", "survive", "triumph", "answer", "result", "level", "levels", "leveled")),
]

ENGINE_PHYSICAL_CAPABILITY: Dict[str, Dict[str, Any]] = {
    "zach-d-films": {
        "mode": "true_3d_webgl",
        "supports_cutaway": True,
        "supports_scale_bridge": True,
        "supports_morph": True,
        "supports_camera_orbit": True,
        "notes": "Three.js 3D PBR stage, articulated human rig with arm IK, layered cutaways, two-source transitions",
    },
    "stick-figure": {
        "mode": "2d_canvas_ik",
        "supports_cutaway": True,
        "supports_scale_bridge": True,
        "supports_morph": False,
        "supports_camera_orbit": False,
        "notes": "2D Canvas2D IK character + 3-plane parallax + wipe/iris masks + cutaway window",
    },
    "minimalistic-graphics": {
        "mode": "2d_svg_minimal",
        "supports_cutaway": False,
        "supports_scale_bridge": False,
        "supports_morph": True,
        "supports_camera_orbit": False,
        "notes": "Minimalist B&W SVG lines, solitary dot, negative space morphing and quiet geometric balance",
    },
    "graph": {
        "mode": "2d_svg_data",
        "supports_cutaway": False,
        "supports_scale_bridge": False,
        "supports_morph": False,
        "supports_camera_orbit": False,
        "notes": "Data trajectory spline, region focus pan/zoom, axes, slope tangent & delta stems (real numbers only)",
    },
    "map-route": {
        "mode": "3d_schematic_city",
        "supports_cutaway": False,
        "supports_scale_bridge": True,
        "supports_morph": False,
        "supports_camera_orbit": True,
        "notes": "Schematic 3D city massing, aerial chase, waypoint turn/bridge framing, ETA & pin drop",
    },
    "breakdown": {
        "mode": "3d_exploded_studio",
        "supports_cutaway": True,
        "supports_scale_bridge": False,
        "supports_morph": False,
        "supports_camera_orbit": True,
        "notes": "Dark studio PBR exploded axial stack, cutaway core macro, leader lines & turntable orbit",
    },
}


def plan_contact_action(
    verb: str,
    performer_id: str,
    target_id: str,
    hit_time: float,
    duration: float,
    target_world: Optional[List[float]] = None,
    target_normal: Optional[List[float]] = None,
    target_radius_m: float = 0.028,
) -> Dict[str, Any]:
    """Build a geometric world-space contact schedule (anticipation -> touch/depress -> hold -> release)."""
    hit_t = round(max(0.18, min(duration - 0.14, hit_time)), 3)
    app_t = round(max(0.0, hit_t - 0.48), 3)
    rel_t = round(min(duration, hit_t + 0.46), 3)
    return {
        "verb": verb,
        "performer_id": performer_id,
        "target_id": target_id,
        "hit_time_rel_sec": hit_t,
        "approach_start_rel_sec": app_t,
        "hold_duration_sec": 0.16,
        "release_end_rel_sec": rel_t,
        "target_world": list(target_world or [0.24, 1.16, 0.24]),
        "target_normal": list(target_normal or [-1.0, 0.0, 0.0]),
        "target_radius_m": float(target_radius_m),
        "button_depress_m": 0.008,
    }


def _finite(val: float, label: str) -> float:
    f = float(val)
    if not math.isfinite(f):
        raise ValueError(f"Non-finite float for {label}: {val!r}")
    return f


def _split_beat_into_action_clauses(text: str, dur: float) -> List[str]:
    """Split a long beat (or causal chain sentence) into distinct visual action phrases cleanly."""
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []

    raw_parts = re.split(r"\s*(?:->|;)\s*", clean)
    expanded: List[str] = []
    for seg in raw_parts:
        s_toks = seg.split()
        if dur >= 2.2 or len(s_toks) >= 8:
            clauses = re.split(
                r",\s+(?=(?:and\s+then|and|then|before|until|while|but|yet|however|instead|suddenly|from\s+there|across|through|into|inside|down|up|a\s+controller|a\s+modern|and\s+a)\b)"
                r"|\s+(?=(?:and\s+then|and\s+plunge|and\s+decides|before\s+(?:a|an|the|it|they|water|light|atoms|signals|one|you|every)|while\s+(?:a|an|the|tiny|your)|until\s+(?:a|an|the|it|you)|powered\s+by\b|using\s+(?:turbines|a|an|the)|traces?\s+back\s+to\b|beneath\s+(?:distant|ancient|dark)|into\s+(?:a|an|the)\s+(?:dark|subsea|massive|glowing|distant))\b)",
                seg,
                flags=re.IGNORECASE,
            )
            if len(clauses) == 1 and (dur >= 3.8 or len(s_toks) >= 13) and seg.count(",") >= 1:
                cand_comma = [c.strip() for c in seg.split(",") if c.strip()]
                if (
                    len(cand_comma) >= 2
                    and all(len(c.split()) >= 5 for c in cand_comma)
                    and not re.match(r"^(?:up\s+in|inside\s+the\s+machine|approaching|only\s+when)\b", cand_comma[0], flags=re.IGNORECASE)
                ):
                    clauses = cand_comma
            if len(clauses) >= 2:
                expanded.extend(c.strip() for c in clauses if c.strip())
                continue
        expanded.append(seg)

    merged: List[str] = []
    for part in expanded:
        toks = part.split()
        if not toks:
            continue
        if len(toks) < 3 and merged:
            merged[-1] = f"{merged[-1]}, {part}".strip(" ,")
        elif merged and len(merged[-1].split()) < 3:
            merged[-1] = f"{merged[-1]} {part}".strip()
        else:
            merged.append(part)
    return merged or [clean]


def classify_visual_clause(
    phrase: str,
    beat_role: str,
    beat_index: int,
    clause_index: int,
    prev_family: Optional[str],
    global_motifs: List[str],
    selected_skill: str,
    full_script_low: str = "",
) -> Dict[str, Any]:
    low = phrase.lower()

    # Detect explicit unsupported exact mechanical domains first
    unsupported_domain: Optional[str] = None
    for dom_name, dom_kws in UNSUPPORTED_EXACT_DOMAIN_RULES:
        if any((re.search(rf"\b{re.escape(kw)}\b", low) if " " not in kw else kw in low) for kw in dom_kws):
            unsupported_domain = dom_name
            break

    # 1. Grounded Props & Scene Family
    matched_props: List[str] = []
    families: List[str] = []
    scales: List[str] = []

    if unsupported_domain:
        matched_props = ["schematic_mechanism"]
        families = ["schematic_mechanism"]
        scales = ["macro_object"]
    else:
        for prop_id, fam, sc, kws in DOMAIN_PROP_RULES:
            if any(
                (re.search(rf"\b{re.escape(kw)}\b", low) if " " not in kw else kw in low)
                for kw in kws
            ):
                if prop_id not in matched_props:
                    matched_props.append(prop_id)
                if fam not in families:
                    families.append(fam)
                if sc not in scales:
                    scales.append(sc)

    is_elevator_story = any(k in full_script_low for k in ("elevator", "sheave", "counterweight", "traction"))

    # Disambiguate elevator story hardware & short anaphoric phrases without pulling unrelated smartphone/chip templates
    if is_elevator_story:
        if any(k in low for k in ("copper wiring", "voltage surges", "rail switches", "floor positions", "micro circuit", "micro controller", "relay")):
            matched_props = ["controller_pcb"]
            families = ["controller_cabinet_cutaway"]
            scales = ["micro_circuit"]
        elif not matched_props:
            if "request" in low or "signal" in low or "track" in low or "decide" in low:
                matched_props = ["controller_pcb"]
                families = ["controller_cabinet_cutaway"]
                scales = ["micro_circuit"]
            elif "tap" in low or "machine" in low or "coordinated" in low:
                matched_props = ["elevator_doors"]
                families = ["elevator_landing_doors"]
                scales = ["human_environment"]

    # Engine-specific defaults when narration uses poetic/abstract words without explicit hardware nouns
    fallback_reason: Optional[str] = None
    confidence = 0.90
    if unsupported_domain:
        confidence = 0.45
        fallback_reason = (
            f"Unsupported exact 3D archetype '{unsupported_domain}'; routed to labeled stylized schematic mechanism."
        )
    elif not matched_props:
        if selected_skill == "graph":
            matched_props = ["data_chart"]
            families = ["data_trajectory"]
            scales = ["chart_view"]
        elif selected_skill == "map-route":
            matched_props = ["route_street"]
            families = ["map_navigation"]
            scales = ["city_aerial"]
        elif selected_skill == "breakdown":
            matched_props = ["exploded_device"]
            families = ["mechanical_breakdown"]
            scales = ["studio_assembly"]
        elif selected_skill == "minimalistic-graphics":
            matched_props = ["balance_scale"]
            families = ["geometric_minimal"]
            scales = ["abstract_plane"]
        else:
            fallback_prop = "atom_crystal" if any(k in low for k in ("every", "world", "origin", "tiny", "light", "energy")) else "idea_spark"
            matched_props = [fallback_prop]
            families = ["human_studio"]
            scales = ["human_environment"]
            confidence = 0.60
            fallback_reason = f"No domain-specific noun in clause; defaulted to '{fallback_prop}' studio demonstrator."

    primary_prop = matched_props[0]
    scene_family = families[0]
    scale_level = scales[0]

    # Per-clause Roman gating (NO global override!)
    clause_is_roman = scene_family == "roman_historical"
    forbidden: List[str] = []
    if not clause_is_roman:
        forbidden.extend(["roman_gladiator_armor", "medieval_sword_default"])
    if selected_skill == "map-route":
        forbidden.append("fake_gis_accuracy_claim")

    # 2. Subject & character extraction
    subject = "narrator_subject"
    character_id: Optional[str] = None
    if any(k in low for k in ("you", "finger", "thumb", "person", "user", "human", "explorer", "hero", "gladiator", "opponent", "organizer", "messenger", "tap", "button")):
        if "gladiator" in low or "opponent" in low or "messenger" in low:
            subject = "gladiator_character"
            character_id = "char_fighter_01"
        elif "organizer" in low:
            subject = "organizer_character"
            character_id = "char_organizer_01"
        elif "finger" in low or "thumb" in low or "elevator button" in low or ("tap" in low and scene_family in ("human_device", "elevator_lobby_button", "elevator_landing_doors")):
            subject = "human_hand_finger"
            character_id = "char_protagonist_01"
        elif "explorer" in low:
            subject = "explorer_character"
            character_id = "char_protagonist_01"
        else:
            subject = "human_protagonist"
            character_id = "char_protagonist_01"
    elif primary_prop in ("elevator_button", "elevator_doors") and (is_elevator_story or beat_index == 0 or beat_role == "payoff"):
        subject = "human_protagonist"
        character_id = "char_protagonist_01"
    elif primary_prop in ("phone_screen", "microchip_pcb", "battery_cell", "exploded_device", "controller_pcb", "traction_motor_sheave", "shaft_car_counterweight"):
        subject = primary_prop
    elif primary_prop in ("cell_tower_wave", "subsea_fiber_cable", "datacenter_rack", "power_turbine", "schematic_mechanism"):
        subject = primary_prop
    elif primary_prop in ("cosmic_origin", "atom_crystal", "ocean_nature"):
        subject = primary_prop
    elif primary_prop == "data_chart":
        subject = "trajectory_curve"
    elif primary_prop == "route_street":
        subject = "route_path_head"

    # 3. Verb / Action extraction
    verb_action = "present_focus"
    for act, kws in VERB_PATTERNS:
        if any(re.search(rf"\b{re.escape(k)}\b", low) if " " not in k else k in low for k in kws):
            verb_action = act
            break
    if beat_index == 0 and clause_index == 0 and verb_action == "present_focus":
        verb_action = "tap_activate" if primary_prop == "elevator_button" else "hook_launch"
    elif "turn" in beat_role and verb_action == "present_focus":
        verb_action = "contrast_reveal"
    elif beat_role == "payoff" and verb_action == "present_focus":
        verb_action = "resolve_payoff"

    # 4. Logical contrast / causality / lighting / novelty axis
    has_contrast = bool(re.search(r"\b(but|however|yet|instead|unless|never|caught|catch|suddenly|doesn't|does not|only then)\b", low))
    causality_link = (
        "contrasts_with_previous" if has_contrast
        else ("scales_from_previous" if verb_action == "scale_jump"
              else ("resolves_story" if beat_role == "payoff"
                    else ("hooks_viewer" if beat_index == 0 and clause_index == 0 else "drives_next_step")))
    )

    if any(k in low for k in ("dark", "night", "deep ocean", "subsea", "space", "universe", "star", "cosmos", "tension", "trap", "danger")):
        lighting_mood = "dark_dramatic"
    elif beat_role == "payoff" or any(k in low for k in ("sun", "gold", "triumph", "spark", "bright", "morning", "warm", "open", "coordinated")):
        lighting_mood = "warm_payoff"
    elif primary_prop in ("microchip_pcb", "controller_pcb", "traction_motor_sheave", "shaft_car_counterweight", "datacenter_rack", "cell_tower_wave", "brain_neuron", "heart_organ"):
        lighting_mood = "tech_cool_studio"
    else:
        lighting_mood = "day_editorial"

    if primary_prop in ("brain_neuron", "heart_organ", "phone_screen", "microchip_pcb", "controller_pcb", "traction_motor_sheave", "shaft_car_counterweight", "exploded_device", "vault_gear") and (
        verb_action == "reveal_cutaway" or "inside" in low or "beneath" in low or "stage" in low or "layer" in low or "controller" in low or "shaft" in low
    ):
        novelty_axis = "internal_cutaway"
    elif prev_family and scene_family != prev_family:
        novelty_axis = "environment_and_scale_shift" if verb_action == "scale_jump" else "subject_environment_change"
    elif has_contrast:
        novelty_axis = "dramatic_contrast_framing"
    elif verb_action in ("travel_stream", "escalate_tick"):
        novelty_axis = "kinetic_tracking_arc"
    else:
        novelty_axis = "camera_angle_and_reveal"

    # Explicit semantic relation grounding
    cause_from = prev_family or "narration_hook"
    effect_to = primary_prop
    semantic_relation = {
        "agent": subject,
        "verb": verb_action,
        "patient": primary_prop,
        "location": scene_family,
        "cause_from": cause_from,
        "effect_to": effect_to,
        "scale": scale_level,
        "evidence_excerpt": phrase[:120],
        "confidence": confidence,
        "fallback_reason": fallback_reason,
    }

    return {
        "subject": subject,
        "character_id": character_id,
        "verb_action": verb_action,
        "relevant_prop": primary_prop,
        "grounded_props": matched_props,
        "scene_family": scene_family,
        "scale_level": scale_level,
        "lighting_mood": lighting_mood,
        "causality_link": causality_link,
        "has_contrast": has_contrast,
        "desired_novelty_axis": novelty_axis,
        "forbidden_elements": forbidden,
        "unsupported_exact_domain": unsupported_domain,
        "confidence": confidence,
        "fallback_reason": fallback_reason,
        "semantic_relation": semantic_relation,
    }


def _build_intra_shot_activities(ev_meta: Dict[str, Any], dur: float) -> List[Dict[str, Any]]:
    """Populate intra-shot actions/reveals when an uninterrupted shot spans >= 1.2s."""
    acts: List[Dict[str, Any]] = []
    prop = ev_meta["relevant_prop"]
    verb = ev_meta["verb_action"]
    if prop == "elevator_button" or (prop == "phone_screen" and verb == "tap_activate"):
        acts.append({"rel_norm": 0.42, "type": "physical_button_contact", "detail": f"{ev_meta['subject']} reaches and depresses {prop}"})
    elif prop == "controller_pcb":
        acts.append({"rel_norm": 0.30, "type": "cabinet_door_open", "detail": "Cutaway door opens revealing DIN rail and logic PCB"})
        acts.append({"rel_norm": 0.68, "type": "relay_latch_pulse", "detail": "Controller relay latches and dispatches drive signal"})
    elif prop == "traction_motor_sheave":
        acts.append({"rel_norm": 0.40, "type": "sheave_drive_engage", "detail": "Brake releases and motor accelerates traction sheave"})
    elif prop == "shaft_car_counterweight":
        acts.append({"rel_norm": 0.50, "type": "counterweight_motion_sensor", "detail": "Car and counterweight travel in opposite directions past floor sensor"})
    elif prop == "elevator_doors":
        acts.append({"rel_norm": 0.38, "type": "landing_level_lock", "detail": "Car levels with landing sill before doors unlock"})
        acts.append({"rel_norm": 0.65, "type": "doors_slide_open", "detail": "Bi-parting landing and car doors slide open smoothly"})
    elif verb in ("tap_activate", "strike_halt"):
        acts.append({"rel_norm": 0.38, "type": "action_impact", "detail": f"{ev_meta['subject']} executes {verb} on {prop}"})
    elif verb == "reveal_cutaway":
        acts.append({"rel_norm": 0.35, "type": "shell_peel_open", "detail": f"Cutaway opens outer layer of {prop}"})
        acts.append({"rel_norm": 0.72, "type": "internal_macro_push", "detail": f"Camera pushes inside revealed core of {prop}"})
    elif verb == "scale_jump":
        acts.append({"rel_norm": 0.55, "type": "scale_portal_bridge", "detail": f"Motivated scale transition into {ev_meta['scale_level']}"})
    else:
        acts.append({"rel_norm": 0.45, "type": "information_reveal", "detail": f"Secondary layer / prop state update on {prop}"})
    if dur >= 3.2:
        acts.append({"rel_norm": 0.78, "type": "camera_reframe_settle", "detail": "Continuous camera orbit/push reframes payoff state"})
    return acts


def _norm_tok(s: str) -> str:
    return re.sub(r"[^\w%]", "", s.lower())


def bind_events_to_voice_words(
    events: List[Dict[str, Any]],
    words: List[Dict[str, Any]],
    beats: List[Dict[str, Any]],
    fps: int = 30,
    alignment_method: str = "unknown",
) -> List[Dict[str, Any]]:
    """Anchor every visual event to nearest speech words & exact frame index cleanly."""
    is_uncertain_source = alignment_method in ("silent_syllabic_pacing", "unknown", "estimated", "") or not words
    word_cursor_by_line: Dict[int, int] = {}
    words_by_line: Dict[int, List[Tuple[int, Dict[str, Any]]]] = {}
    for g_idx, w in enumerate(words):
        li = int(w.get("line", 0))
        words_by_line.setdefault(li, []).append((g_idx, w))

    bound: List[Dict[str, Any]] = []
    for ev in events:
        b_idx = int(ev.get("beat_index", 0))
        line_words = words_by_line.get(b_idx, [])
        phrase_toks = [_norm_tok(t) for t in str(ev.get("exact_narration_phrase", "")).split() if _norm_tok(t)]
        c_pos = word_cursor_by_line.get(b_idx, 0)

        matched_pairs: List[Tuple[int, Dict[str, Any]]] = []
        if line_words and phrase_toks:
            rem = line_words[c_pos:]
            needed = min(len(rem), len(phrase_toks))
            if needed > 0:
                matched_pairs = rem[:needed]
                word_cursor_by_line[b_idx] = c_pos + needed
        elif line_words:
            matched_pairs = line_words

        if matched_pairs:
            w0_idx, w0 = matched_pairs[0]
            w1_idx, w1 = matched_pairs[-1]
            s_t = float(w0["s"])
            anchor_w = str(w0["w"])
            content = [p for p in matched_pairs if len(_norm_tok(p[1]["w"])) >= 4]
            if content:
                anchor_pair = content[0]
                anchor_w = str(anchor_pair[1]["w"])
                anchor_t = float(anchor_pair[1]["s"])
            else:
                anchor_t = s_t
            nearest_f = int(round(anchor_t * fps))
            offset_sec = round(nearest_f / float(fps) - anchor_t, 4)
            uncertain = bool(is_uncertain_source)
            conf_label = "estimated_uncertain" if uncertain else "waveform_aligned"
        else:
            s_t = float(ev.get("start_sec", 0.0))
            w0_idx, w1_idx = -1, -1
            anchor_w = ""
            anchor_t = s_t
            nearest_f = int(round(s_t * fps))
            offset_sec = round(nearest_f / float(fps) - s_t, 4)
            uncertain = True
            conf_label = "estimated_uncertain"

        ev_copy = dict(ev)
        ev_copy["word_anchor"] = {
            "start_word_idx": w0_idx,
            "end_word_idx": w1_idx,
            "anchor_word": anchor_w,
            "anchor_sec": round(anchor_t, 3),
            "nearest_frame": nearest_f,
            "frame_offset_sec": offset_sec,
            "timing_confidence": conf_label,
            "uncertain": uncertain,
        }

        # Schedule physical contact action if this clause involves pressing/tapping a target
        if ev_copy.get("relevant_prop") in ("elevator_button", "phone_screen") and ev_copy.get("verb_action") == "tap_activate":
            ev_dur = float(ev_copy["duration_sec"])
            # Snap contact hit near 0.44 * dur (and near button/tap word anchor when inside span)
            rel_hit = round(ev_dur * 0.44, 3)
            for _, mw in matched_pairs:
                if any(k in _norm_tok(mw["w"]) for k in ("button", "tap", "press", "send")):
                    rel_cand = float(mw["s"]) - float(ev_copy["start_sec"])
                    if 0.25 <= rel_cand <= ev_dur - 0.20:
                        rel_hit = round(rel_cand, 3)
                    break
            target_id = "call_button_01" if ev_copy["relevant_prop"] == "elevator_button" else "phone_send_button_01"
            target_world = [0.24, 1.16, 0.24] if ev_copy["relevant_prop"] == "elevator_button" else [0.24, 1.32, 0.28]
            target_norm = [-1.0, 0.0, 0.0] if ev_copy["relevant_prop"] == "elevator_button" else [0.0, 0.0, 1.0]
            target_rad = 0.028 if ev_copy["relevant_prop"] == "elevator_button" else 0.055
            ev_copy["contact_action"] = plan_contact_action(
                verb="press_button",
                performer_id=ev_copy.get("character_id") or "char_protagonist_01",
                target_id=target_id,
                hit_time=rel_hit,
                duration=ev_dur,
                target_world=target_world,
                target_normal=target_norm,
                target_radius_m=target_rad,
            )

        bound.append(ev_copy)
    return bound


def build_visual_beat_constraints(
    events: List[Dict[str, Any]],
    locked_skill: str,
) -> List[Dict[str, Any]]:
    """Derive explicit per-event requirements, novelty imperatives, and forbidden visual elements."""
    cap = ENGINE_PHYSICAL_CAPABILITY.get(locked_skill, ENGINE_PHYSICAL_CAPABILITY["zach-d-films"])
    constraints: List[Dict[str, Any]] = []
    seen_families: List[str] = []

    for idx, ev in enumerate(events):
        fam = ev["scene_family"]
        prop = ev["relevant_prop"]
        must_happen = f"{ev['subject']} visibly performs `{ev['verb_action']}` involving `{prop}`"
        must_change = (
            f"Break away from previous family `{seen_families[-1]}` into `{fam}` ({ev['scale_level']})"
            if seen_families and seen_families[-1] != fam
            else f"Advance `{ev['desired_novelty_axis']}` with distinct camera/reveal framing"
        )
        seen_families.append(fam)

        forbidden = list(ev.get("forbidden_elements", []))
        if not cap["supports_morph"] and ev["verb_action"] == "transform_convert":
            must_happen += " (via discrete step reveal or match cut supported by engine)"

        constraints.append({
            "event_id": ev["event_id"],
            "beat_id": ev["beat_id"],
            "locked_skill": locked_skill,
            "must_be_visibly_happening": must_happen,
            "must_change_from_prev": must_change,
            "reveal_timing_sec": ev["word_anchor"]["anchor_sec"],
            "continuity_entities": ev["grounded_props"],
            "forbidden": forbidden,
            "engine_mode": cap["mode"],
        })
    return constraints


def validate_visual_event_graph(
    graph: Dict[str, Any],
    locked_skill: str,
    duration_sec: Optional[float] = None,
) -> Dict[str, Any]:
    """Fail-closed sanity & schema validator for VisualEventGraph."""
    if locked_skill not in VALID_SKILLS:
        raise ValueError(f"Invalid locked_skill in VisualEventGraph: {locked_skill!r}")
    if graph.get("selected_skill") != locked_skill:
        raise ValueError(
            f"VisualEventGraph skill mismatch: {graph.get('selected_skill')!r} != {locked_skill!r}"
        )
    if graph.get("origin_skills") != [locked_skill]:
        raise ValueError(f"VisualEventGraph origin_skills invalid: {graph.get('origin_skills')!r}")

    events = graph.get("events") or []
    if not events:
        raise ValueError("VisualEventGraph contains zero visual events.")

    max_dur = float(duration_sec if duration_sec is not None else graph.get("total_duration_sec", 0.0))
    _finite(max_dur, "total_duration_sec")
    if max_dur <= 0.0:
        raise ValueError(f"VisualEventGraph duration must be positive, got {max_dur}")

    prev_end = -1e-6
    for idx, ev in enumerate(events):
        st = _finite(ev.get("start_sec", -1.0), f"events[{idx}].start_sec")
        en = _finite(ev.get("end_sec", -1.0), f"events[{idx}].end_sec")
        conf = _finite(ev.get("confidence", 0.0), f"events[{idx}].confidence")
        if st < -1e-4 or en <= st or en > max_dur + 0.05:
            raise ValueError(f"Event {ev.get('event_id')} time window [{st}, {en}] invalid for duration {max_dur}")
        if st < prev_end - 0.05:
            raise ValueError(f"Overlapping backward event timestamp at {ev.get('event_id')}: {st} < {prev_end}")
        prev_end = en
        if ev.get("selected_skill") != locked_skill:
            raise ValueError(f"Event {ev.get('event_id')} leaked foreign skill {ev.get('selected_skill')!r}")
        if not (0.0 <= conf <= 1.0):
            raise ValueError(f"Event {ev.get('event_id')} invalid confidence: {conf}")

    return {"ok": True, "event_count": len(events), "selected_skill": locked_skill}


def extract_semantic_visual_events(
    parsed_script: Dict[str, Any],
    storyboard_context: Optional[Dict[str, Any]] = None,
    fps: int = 30,
    seed: int = 42,
    selected_skill: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze parsed narration & word timestamps into a full semantic `VisualEventGraph`."""
    ctx = storyboard_context or {}
    locked_skill = selected_skill or ctx.get("selected_skill") or "zach-d-films"
    if locked_skill not in VALID_SKILLS:
        raise ValueError(f"Invalid selected_skill: {locked_skill!r}")

    beats = list(parsed_script.get("beats", []))
    voice = parsed_script.get("voice") or {}
    words = list(voice.get("words", []))
    alignment_method = str(voice.get("alignment_method") or "unknown")
    motifs = list(parsed_script.get("entities_and_facts", {}).get("detected_motifs", []))
    fact_checks = list(parsed_script.get("entities_and_facts", {}).get("fact_checks", []))
    full_script_low = " ".join(str(b.get("text") or "") for b in beats).lower()

    tail_hold = float(ctx.get("tail_hold_sec", 0.75))
    min_dur = float(ctx.get("target_min_duration", 0.0))
    vo_dur = float(voice.get("vo_duration_sec", sum(float(b.get("duration", 2.0)) for b in beats)))
    total_dur = round(max(vo_dur + tail_hold, min_dur, 0.5), 3)

    beat_spans: List[Tuple[float, float]] = []
    for idx, b in enumerate(beats):
        s_t = 0.0 if idx == 0 else beat_spans[idx - 1][1]
        if idx < len(beats) - 1:
            mid_breath = (float(b.get("end", s_t + 1.5)) + float(beats[idx + 1].get("start", s_t + 1.6))) * 0.5
            e_t = round(max(s_t + 0.25, mid_breath), 3)
        else:
            e_t = round(max(s_t + 0.3, total_dur), 3)
        beat_spans.append((s_t, e_t))

    raw_events: List[Dict[str, Any]] = []
    prev_family: Optional[str] = None
    cap = ENGINE_PHYSICAL_CAPABILITY[locked_skill]

    for b_idx, b in enumerate(beats):
        b_start, b_end = beat_spans[b_idx]
        b_dur = max(0.25, b_end - b_start)
        b_text = str(b.get("text") or "").strip()
        b_role = str(b.get("role") or "mechanism")

        clauses = _split_beat_into_action_clauses(b_text, b_dur)
        if locked_skill in ("minimalistic-graphics", "graph") and len(clauses) > 2:
            clauses = [" ".join(clauses[: len(clauses) // 2]), " ".join(clauses[len(clauses) // 2 :])]

        tok_counts = [max(1, len(c.split())) for c in clauses]
        total_toks = sum(tok_counts)

        cursor = b_start
        for c_idx, clause in enumerate(clauses):
            if c_idx == len(clauses) - 1:
                c_end = b_end
            else:
                frac = tok_counts[c_idx] / float(total_toks)
                c_end = round(min(b_end - 0.35 * (len(clauses) - 1 - c_idx), max(cursor + 0.45, cursor + b_dur * frac)), 3)
            c_dur = max(0.25, round(c_end - cursor, 3))

            meta = classify_visual_clause(
                phrase=clause,
                beat_role=b_role,
                beat_index=b_idx,
                clause_index=c_idx,
                prev_family=prev_family,
                global_motifs=motifs,
                selected_skill=locked_skill,
                full_script_low=full_script_low,
            )
            prev_family = meta["scene_family"]

            ev_id = f"ve_{len(raw_events):02d}"
            raw_events.append({
                "id": ev_id,
                "event_id": ev_id,
                "beat_id": f"beat_{b_idx:02d}",
                "beat_index": b_idx,
                "beat_role": b_role if c_idx == 0 else f"{b_role}_step_{c_idx}",
                "clause_index": c_idx,
                "start_sec": round(cursor, 3),
                "end_sec": round(c_end, 3),
                "duration_sec": c_dur,
                "shot_candidate_window": [round(cursor, 3), round(c_end, 3)],
                "exact_narration_phrase": clause,
                "subject": meta["subject"],
                "character_id": meta["character_id"],
                "verb_action": meta["verb_action"],
                "relevant_prop": meta["relevant_prop"],
                "grounded_props": meta["grounded_props"],
                "scene_family": meta["scene_family"],
                "scale_level": meta["scale_level"],
                "lighting_mood": meta["lighting_mood"],
                "causality_link": meta["causality_link"],
                "has_contrast": meta["has_contrast"],
                "desired_novelty_axis": meta["desired_novelty_axis"],
                "forbidden_elements": meta["forbidden_elements"],
                "unsupported_exact_domain": meta["unsupported_exact_domain"],
                "fallback_reason": meta["fallback_reason"],
                "semantic_relation": meta["semantic_relation"],
                "physical_capability": dict(cap),
                "intra_shot_activities": _build_intra_shot_activities(meta, c_dur),
                "confidence": meta["confidence"] if alignment_method != "silent_syllabic_pacing" else min(meta["confidence"], 0.72),
                "selected_skill": locked_skill,
            })
            cursor = c_end

    if raw_events:
        raw_events[0]["start_sec"] = 0.0
        for idx in range(len(raw_events) - 1):
            t_frame = round(round(raw_events[idx]["end_sec"] * fps) / float(fps), 3)
            t_frame = max(raw_events[idx]["start_sec"] + 0.25, t_frame)
            raw_events[idx]["end_sec"] = t_frame
            raw_events[idx]["duration_sec"] = round(t_frame - raw_events[idx]["start_sec"], 3)
            raw_events[idx]["shot_candidate_window"] = [raw_events[idx]["start_sec"], t_frame]
            raw_events[idx + 1]["start_sec"] = t_frame
        raw_events[-1]["end_sec"] = total_dur
        raw_events[-1]["duration_sec"] = round(max(0.25, total_dur - raw_events[-1]["start_sec"]), 3)
        raw_events[-1]["shot_candidate_window"] = [raw_events[-1]["start_sec"], total_dur]

    bound_events = bind_events_to_voice_words(
        raw_events,
        words=words,
        beats=beats,
        fps=fps,
        alignment_method=alignment_method,
    )
    constraints = build_visual_beat_constraints(bound_events, locked_skill=locked_skill)

    disclosures: List[str] = []
    if locked_skill == "map-route":
        disclosures.append("Schematic 3D city geometry (non-GIS illustrative route).")
    if locked_skill == "graph":
        for fc in fact_checks:
            if fc.get("illustrative_curve_badge"):
                disclosures.append("Intermediate curve trajectory marked ILLUSTRATIVE TRAJECTORY (endpoint numbers only).")
    if any(ev["scene_family"] == "anatomical_cutaway" for ev in bound_events):
        disclosures.append("Simplified schematic/stylized anatomical cross-section (conceptual clarity, not clinical imagery).")
    if any(ev["scene_family"] == "cosmic_scale" for ev in bound_events):
        disclosures.append("Macro-to-cosmic scale transition is stylized conceptual progression, not literal metric scale factor.")
    if any(ev["scene_family"] in ("elevator_lobby_button", "controller_cabinet_cutaway", "traction_machine_room", "elevator_shaft_cutaway", "elevator_landing_doors") for ev in bound_events):
        disclosures.append("Elevator mechanism depicts a traction-type elevator schematic (counterweight + sheave design; not hydraulic).")
    unsupported_found = sorted({ev["unsupported_exact_domain"] for ev in bound_events if ev.get("unsupported_exact_domain")})
    if unsupported_found:
        disclosures.append(
            f"UNSUPPORTED_EXACT_ARCHETYPE_FALLBACK_SCHEMATIC: {', '.join(unsupported_found)} rendered as labeled generic mechanical schematic."
        )

    graph: Dict[str, Any] = {
        "schema_version": "sd-visual-events-2",
        "selected_skill": locked_skill,
        "origin_skills": [locked_skill],
        "seed": seed,
        "fps": fps,
        "total_duration_sec": total_dur,
        "voice_alignment_method": alignment_method,
        "unique_scene_families": sorted({ev["scene_family"] for ev in bound_events}),
        "unsupported_exact_domains": unsupported_found,
        "scale_progression": [ev["scale_level"] for ev in bound_events],
        "factual_disclosures": disclosures,
        "events": bound_events,
        "beat_constraints": constraints,
    }
    validate_visual_event_graph(graph, locked_skill=locked_skill, duration_sec=total_dur)
    return graph


def write_visual_events_artifact(graph: Dict[str, Any], run_dir: Path) -> Path:
    out_path = run_dir / "visual_events.json"
    out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
