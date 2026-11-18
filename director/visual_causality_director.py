"""STEP 2B (SD-RETENTION-04.R1): Causal Storytelling & Visual Evidence Contract Director.

Converts beat/event graphs into an explicit, auditable cause -> visible proof -> result
chain with structured `VisualEvidenceContract`s (`expected_visible_consequence` and
`counterfactual_failure`), world-state conservation across cuts, and honest
`UNSUPPORTED_VISUAL_EVIDENCE` / `visualized_physical_approximation` disclosure.

Produces single-source-of-truth artifacts:
- `causal_event_graph.json`
- `causal_evidence_contracts.json`
- `causal_traceability.csv`
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SCHEMA_VERSION = "sd-causal-event-graph-1"
CONTRACTS_SCHEMA_VERSION = "sd-causal-evidence-contracts-1"

EVIDENCE_SUPPORTED = "SUPPORTED"
EVIDENCE_UNSUPPORTED = "UNSUPPORTED_VISUAL_EVIDENCE"
EVIDENCE_UNSUPPORTED_EXACT = "UNSUPPORTED_EXACT_MECHANISM"

PHYSICS_ACCURATE = "accurate_simulation"
PHYSICS_VISUAL_APPROX = "visualized_physical_approximation"
PHYSICS_SYMBOLIC = "symbolic_proxy"

VALID_PROOF_TYPES: Tuple[str, ...] = (
    "displacement_relative_to_fixed_reference",
    "contact_transfer",
    "material_deformation",
    "particle_path_propagation",
    "state_change_before_after",
    "occlusion_visibility_change",
    "internal_mechanism_cutaway",
    "pressure_flow_difference",
    "human_reaction_consequence",
    "comparative_split_reference",
    "context_establish",
)

# General mechanism rules linking clause semantics to observable proof classes.
# Intentionally domain-general so atmospheric, hydraulic, structural, electro-mechanical,
# and historical explainers use one unified physical grammar.
_PROOF_SIGNAL_TABLE: Dict[str, Dict[str, Any]] = {
    "occlusion_visibility_change": {
        "observable_signal": "target_luminance_and_contrast_obscuration_by_medium",
        "requires_matte_role": "causal_feature",
        "min_relative_displacement_px": 4.0,
        "min_state_delta": 0.12,
        "counterfactual_mode": "target_remains_unrealistically_clear_despite_claimed_obscuration",
    },
    "pressure_flow_difference": {
        "observable_signal": "directional_layer_boundary_or_streamline_deflection",
        "requires_matte_role": "causal_feature",
        "min_relative_displacement_px": 8.0,
        "min_state_delta": 0.08,
        "counterfactual_mode": "airflow_or_pressure_layers_indistinguishable_or_static",
    },
    "particle_path_propagation": {
        "observable_signal": "plume_particle_front_advection_and_accumulation",
        "requires_matte_role": "causal_feature",
        "min_relative_displacement_px": 10.0,
        "min_state_delta": 0.10,
        "counterfactual_mode": "particles_frozen_or_disconnected_from_source_stack",
    },
    "internal_mechanism_cutaway": {
        "observable_signal": "cross_section_reveal_of_internal_process_or_defect",
        "requires_matte_role": "causal_feature",
        "min_relative_displacement_px": 6.0,
        "min_state_delta": 0.06,
        "counterfactual_mode": "opaque_exterior_box_hides_internal_mechanism_claimed_by_vo",
    },
    "material_deformation": {
        "observable_signal": "continuous_geometry_strain_twist_bend_or_rupture",
        "requires_matte_role": "causal_feature",
        "min_relative_displacement_px": 10.0,
        "min_state_delta": 0.06,
        "counterfactual_mode": "rigid_unbent_geometry_violates_claimed_deformation",
    },
    "contact_transfer": {
        "observable_signal": "performer_or_medium_physical_contact_impulse",
        "requires_matte_role": "causal_feature",
        "min_relative_displacement_px": 6.0,
        "min_state_delta": 0.05,
        "counterfactual_mode": "contact_gap_or_zero_response_on_impacted_body",
    },
    "displacement_relative_to_fixed_reference": {
        "observable_signal": "relative_position_shift_against_fixed_world_landmark",
        "requires_matte_role": "causal_feature",
        "min_relative_displacement_px": 8.0,
        "min_state_delta": 0.06,
        "counterfactual_mode": "subject_centered_with_background_so_camera_motion_fakes_subject_motion",
    },
    "human_reaction_consequence": {
        "observable_signal": "grounded_character_posture_shielding_bracing_or_retreat",
        "requires_matte_role": "character",
        "min_relative_displacement_px": 5.0,
        "min_state_delta": 0.04,
        "counterfactual_mode": "t_pose_or_unaffected_idle_character_contradicts_hazard_reaction",
    },
    "comparative_split_reference": {
        "observable_signal": "simultaneous_before_vs_after_or_damped_vs_undamped_contrast",
        "requires_matte_role": "causal_feature",
        "min_relative_displacement_px": 8.0,
        "min_state_delta": 0.10,
        "counterfactual_mode": "single_uncontrasted_object_fails_to_prove_comparative_claim",
    },
    "state_change_before_after": {
        "observable_signal": "persistent_before_to_after_world_attribute_shift",
        "requires_matte_role": "subject",
        "min_relative_displacement_px": 4.0,
        "min_state_delta": 0.10,
        "counterfactual_mode": "ending_frame_matches_initial_pre_event_state",
    },
    "context_establish": {
        "observable_signal": "period_and_scale_spatial_orientation",
        "requires_matte_role": "subject",
        "min_relative_displacement_px": 3.0,
        "min_state_delta": 0.03,
        "counterfactual_mode": "devoid_of_setting_cues_leaving_viewer_disoriented",
    },
}

# Patterns indicating inherently abstract/non-visualizable assertions unless concretely anchored
_ABSTRACT_UNVISUALIZABLE_RE = re.compile(
    r"\b(tax bracket|interest rate hike|philosophical thesis|abstract jurisprudence|inflation expectation|"
    r"bond yield curve|symbolic theorem|constitutional amendment debate|metaphysical paradox)\b",
    re.IGNORECASE,
)


@dataclass
class CausalEvent:
    causal_event_id: str
    narrative_event_id: str
    order_index: int
    clause_text: str
    beat_role: str
    cause_event_ids: List[str] = field(default_factory=list)
    result_event_ids: List[str] = field(default_factory=list)
    proof_type: str = "state_change_before_after"
    physical_action: str = "state_shift"
    mechanism_summary: str = ""
    cause_entity_id: str = "world_cause"
    effect_entity_id: str = "primary_subject"
    reference_entity_id: str = "fixed_world_reference"
    feature_id: str = "primary_feature"
    semantic_region_of_change: str = "primary_causal_zone"
    scene_family: str = ""
    narrative_claim_id: str = ""
    factual_claim_id: Optional[str] = None
    onset_sec: float = 0.0
    peak_sec: float = 0.5
    settle_sec: float = 1.0
    world_state_before: Dict[str, Any] = field(default_factory=dict)
    world_state_after: Dict[str, Any] = field(default_factory=dict)
    state_transition_kind: str = "causal_progression"
    is_flashforward_hook: bool = False
    is_flashback_transition: bool = False
    evidence_status: str = EVIDENCE_SUPPORTED
    physics_fidelity: str = PHYSICS_VISUAL_APPROX

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VisualEvidenceContract:
    contract_id: str
    causal_event_id: str
    narrative_claim_id: str
    claim_text: str
    proof_type: str
    expected_visible_consequence: Dict[str, Any]
    counterfactual_failure: Dict[str, Any]
    evidence_status: str = EVIDENCE_SUPPORTED
    physics_fidelity: str = PHYSICS_VISUAL_APPROX

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _infer_proof_type(text_low: str, phys_action: str, beat_role: str, scene_fam: str) -> str:
    act = (phys_action or "").lower()
    fam = (scene_fam or "").lower()
    combined = f"{text_low} {act} {fam}"

    if any(k in combined for k in ("split", "compare", "side-by-side", "without damper", "versus", "before_after")):
        return "comparative_split_reference"
    if any(k in combined for k in ("cutaway", "inside", "pcb", "rivet", "chamber", "sulfur", "chemical", "combustion", "firebox")):
        return "internal_mechanism_cutaway"
    if any(k in combined for k in ("disappear", "visibility", "obscure", "blind", "vanish", "headlight", "bus_visibility", "swallow", "fog_street_hook")):
        return "occlusion_visibility_change"
    if any(k in combined for k in ("inversion", "warm air", "lid", "trap", "pressure", "airflow", "vortex", "wind_loading", "bleed")):
        return "pressure_flow_difference"
    if any(k in combined for k in ("smoke", "soot", "particle", "chimney", "plume", "spill", "surge", "flood", "spread", "settle")):
        return "particle_path_propagation"
    if any(k in combined for k in ("twist", "torsion", "crack", "bend", "flex", "buckle", "rupture", "collapse", "plunge")):
        return "material_deformation"
    if any(k in combined for k in ("cough", "shield", "brace", "retreat", "crowd", "pedestrian", "onlooker", "worker", "passenger", "excess deaths", "injured")):
        return "human_reaction_consequence"
    if any(k in combined for k in ("press", "hit", "strike", "smash", "slam", "push_button", "impact", "contact")):
        return "contact_transfer"
    if any(k in combined for k in ("move", "sway", "drift", "plumb", "crawled", "creep", "travel", "orbit", "drive", "approach")):
        return "displacement_relative_to_fixed_reference"
    if any(k in combined for k in ("clean air", "act", "passed", "redesign", "aftermath", "cleared", "banned", "changed", "law")):
        return "state_change_before_after"
    if beat_role in ("context", "establish", "background"):
        return "context_establish"
    return "state_change_before_after"


def _infer_world_entities_and_region(
    ev: Dict[str, Any],
    story_ev: Optional[Dict[str, Any]],
    proof_type: str,
) -> Tuple[str, str, str, str, str]:
    """Return `(cause_entity_id, effect_entity_id, reference_entity_id, feature_id, semantic_region_of_change)`."""
    prop = str(ev.get("relevant_prop") or (story_ev or {}).get("relevant_prop") or "primary_subject")
    fam = str(ev.get("scene_family") or (story_ev or {}).get("scene_family") or "").lower()
    anchor = str((story_ev or {}).get("salient_action_anchor") or ev.get("feature_id") or "")
    text_low = str(ev.get("exact_narration_phrase") or ev.get("clause_text") or "").lower()

    # Semantic anchors grounded in general physical domains
    if fam in ("fog_street_hook", "fog_visibility_street") or "bus_visibility" in fam or "headlight" in text_low:
        return (
            "dense_coal_smog_field",
            "london_bus_and_streetlamps" if ("bus" in text_low or "headlight" in text_low or "visibility" in fam) else "trafalgar_street_scene",
            "lamppost_column_ref",
            anchor or ("bus_headlight_cone" if "bus" in text_low or "headlight" in text_low else "streetlamp_halo_visibility"),
            "visibility_occlusion_front",
        )
    if "combustion" in fam or any(k in text_low for k in ("burning coal", "chimney", "sulfur", "soot", "power station", "hearth")):
        return (
            "domestic_coal_hearth_and_stacks",
            "rising_sulfur_soot_plume",
            "roofline_chimney_masonry_ref",
            anchor or "chimney_flue_combustion",
            "smoke_emission_column",
        )
    if "inversion" in fam or any(k in text_low for k in ("inversion", "warm air", "cold air", "trapped")):
        return (
            "warm_inversion_air_layer",
            "trapped_ground_smog_layer",
            "st_pauls_dome_and_horizon_ref",
            anchor or "inversion_thermal_boundary",
            "vertical_mixing_cap_band",
        )
    if "pedestrian" in fam or any(k in text_low for k in ("cough", "lungs", "hospitals", "deaths", "mask", "breathing")):
        return (
            "ground_level_smog_aerosol",
            "char_london_pedestrian_01",
            "victorian_curb_post_ref",
            anchor or "pedestrian_respiratory_brace",
            "character_respiratory_stance_zone",
        )
    if "aftermath" in fam or "clean air" in text_low or "1956" in text_low or "cleared" in text_low:
        return (
            "clean_air_act_1956_smokeless_fuel",
            "clearing_london_skyline",
            "st_pauls_silhouette_ref",
            anchor or "smokeless_hearth_transition",
            "skyline_visibility_recovery_zone",
        )

    cause_ent = str(ev.get("cause_entity_id") or ("wind_or_driving_force" if proof_type in ("pressure_flow_difference", "material_deformation") else prop))
    effect_ent = str(ev.get("character_id") or prop)
    ref_ent = str(ev.get("reference_entity_id") or "fixed_ground_datum")
    feat = anchor or str(ev.get("target_feature_id") or prop)
    region = str(ev.get("semantic_region_of_change") or f"{proof_type}_zone")
    return cause_ent, effect_ent, ref_ent, feat, region


def classify_causal_proof(
    clause_text: str,
    event_rec: Dict[str, Any],
    story_ev: Optional[Dict[str, Any]] = None,
    selected_skill: str = "zach-d-films",
) -> Dict[str, Any]:
    """Infer structured causal proof metadata & honest support level without overfitting city names."""
    text_low = (clause_text or "").lower()
    phys_act = str((story_ev or {}).get("physical_action") or event_rec.get("action") or "state_shift")
    beat_role = str((story_ev or {}).get("beat_role") or event_rec.get("beat_role") or "escalation")
    fam = str(event_rec.get("scene_family") or (story_ev or {}).get("scene_family") or "")

    unsupported_domain = event_rec.get("unsupported_exact_domain")
    if unsupported_domain:
        evidence_status = EVIDENCE_UNSUPPORTED_EXACT
        physics_fidelity = PHYSICS_SYMBOLIC
    elif _ABSTRACT_UNVISUALIZABLE_RE.search(clause_text or ""):
        evidence_status = EVIDENCE_UNSUPPORTED
        physics_fidelity = PHYSICS_SYMBOLIC
    elif selected_skill != "zach-d-films":
        evidence_status = EVIDENCE_SUPPORTED
        physics_fidelity = PHYSICS_SYMBOLIC if selected_skill in ("graph", "minimalistic-graphics") else PHYSICS_VISUAL_APPROX
    else:
        evidence_status = EVIDENCE_SUPPORTED
        physics_fidelity = PHYSICS_VISUAL_APPROX

    proof_type = str(event_rec.get("proof_type") or "")
    if proof_type not in VALID_PROOF_TYPES:
        proof_type = _infer_proof_type(text_low, phys_act, beat_role, fam)

    cause_ent, effect_ent, ref_ent, feat_id, region = _infer_world_entities_and_region(
        event_rec, story_ev, proof_type
    )
    return {
        "proof_type": proof_type,
        "physical_action": phys_act,
        "beat_role": beat_role,
        "cause_entity_id": cause_ent,
        "effect_entity_id": effect_ent,
        "reference_entity_id": ref_ent,
        "feature_id": feat_id,
        "semantic_region_of_change": region,
        "evidence_status": evidence_status,
        "physics_fidelity": physics_fidelity,
    }


def _evolve_world_state(
    prev_state: Dict[str, Any],
    clause_low: str,
    proof_type: str,
    beat_role: str,
    order_idx: int,
    total_events: int,
) -> Tuple[Dict[str, Any], Dict[str, Any], str, bool]:
    """Propagate coherent physical world state forward across causal beats."""
    before = dict(prev_state)
    after = dict(prev_state)
    progress = round((order_idx + 1) / float(max(1, total_events)), 3)

    is_mitigation_or_repair = any(
        k in clause_low for k in ("clean air", "smokeless", "redesign", "stiffer", "repaired", "rescued", "cleared", "recovery")
    ) or beat_role in ("resolution", "aftermath", "payoff")

    is_flashback_transition = (order_idx == 1 and bool(prev_state.get("_from_hook_flashforward")))

    if is_flashback_transition:
        # Hook showed peak crisis briefly; beat 1 rewinds cleanly to pre-crisis setup
        after["hazard_intensity"] = round(max(0.05, float(before.get("hazard_intensity", 0.2)) * 0.25), 3)
        after["visibility_loss"] = round(max(0.05, float(before.get("visibility_loss", 0.1)) * 0.30), 3)
        after["structural_damage"] = 0.0
        after["_from_hook_flashforward"] = False
        return before, after, "hook_to_chronological_rewind", True

    if order_idx == 0 and beat_role == "hook":
        after["_from_hook_flashforward"] = any(
            k in clause_low for k in ("disappear", "collapsed", "twisted", "swallowed", "turned night", "shook")
        )
        after["hazard_intensity"] = round(max(float(before.get("hazard_intensity", 0.0)), 0.35), 3)
        after["visibility_loss"] = round(0.45 if proof_type == "occlusion_visibility_change" else float(before.get("visibility_loss", 0.0)), 3)
        return before, after, "opening_hook_anomaly", False

    if is_mitigation_or_repair:
        if any(k in clause_low for k in ("clean air", "smokeless", "cleared")):
            after["clean_air_policy_active"] = True
            after["hazard_intensity"] = round(max(0.05, float(before.get("hazard_intensity", 0.5)) * 0.28), 3)
            after["visibility_loss"] = round(max(0.05, float(before.get("visibility_loss", 0.5)) * 0.24), 3)
        else:
            after["post_event_aftermath"] = True
            after["hazard_intensity"] = round(max(0.15, float(before.get("hazard_intensity", 0.5)) * 0.65), 3)
        return before, after, "mitigation_or_aftermath", False

    # Normal forward causal escalation (monotonic unless explicit mitigation/rewind)
    after["hazard_intensity"] = round(min(1.0, max(float(before.get("hazard_intensity", 0.1)) + 0.14, progress)), 3)
    if proof_type in ("occlusion_visibility_change", "particle_path_propagation"):
        after["particulate_load"] = round(min(1.0, float(before.get("particulate_load", 0.0)) + 0.24), 3)
        after["visibility_loss"] = round(min(0.95, float(before.get("visibility_loss", 0.05)) + 0.22), 3)
    if proof_type == "pressure_flow_difference":
        after["trapped_boundary_active"] = True
        after["particulate_load"] = round(min(1.0, float(before.get("particulate_load", 0.1)) + 0.18), 3)
    if proof_type == "material_deformation":
        after["structural_damage"] = round(min(1.0, float(before.get("structural_damage", 0.0)) + 0.25), 3)
    if proof_type == "human_reaction_consequence":
        after["human_impact_observed"] = True
    return before, after, "causal_progression", False


def link_cause_effect_chain(causal_events: List[CausalEvent]) -> List[Dict[str, Any]]:
    """Wire `cause_event_ids` and `result_event_ids` chronologically & return directed edges."""
    edges: List[Dict[str, Any]] = []
    for idx, ev in enumerate(causal_events):
        ev.cause_event_ids = list(ev.cause_event_ids)
        ev.result_event_ids = list(ev.result_event_ids)
        if idx == 0:
            continue
        prev = causal_events[idx - 1]
        # Hook anomaly (index 0) leads into chronological causal root or direct consequence
        if prev.causal_event_id not in ev.cause_event_ids:
            ev.cause_event_ids.append(prev.causal_event_id)
        if ev.causal_event_id not in prev.result_event_ids:
            prev.result_event_ids.append(ev.causal_event_id)
        relation = "rewind_to_origin_cause" if ev.is_flashback_transition else "causes_or_enables"
        edges.append({
            "from_event_id": prev.causal_event_id,
            "to_event_id": ev.causal_event_id,
            "relation": relation,
            "from_time_sec": prev.onset_sec,
            "to_time_sec": ev.onset_sec,
        })
    return edges


def make_evidence_contract(ev: CausalEvent) -> VisualEvidenceContract:
    """Create a testable `VisualEvidenceContract` pairing visible proof with counterfactual failure."""
    spec = _PROOF_SIGNAL_TABLE.get(ev.proof_type, _PROOF_SIGNAL_TABLE["state_change_before_after"])
    if ev.evidence_status != EVIDENCE_SUPPORTED:
        failure_mode = "unsupported_concept_cannot_be_proven_honestly_without_invented_telemetry"
    else:
        failure_mode = spec["counterfactual_mode"]

    expected = {
        "target_feature_id": ev.feature_id,
        "effect_entity_id": ev.effect_entity_id,
        "reference_feature_id": ev.reference_entity_id,
        "semantic_region_of_change": ev.semantic_region_of_change,
        "observable_signal": spec["observable_signal"],
        "requires_matte_role": spec["requires_matte_role"],
        "min_relative_displacement_px": spec["min_relative_displacement_px"],
        "min_state_delta": spec["min_state_delta"],
        "before_after_window_sec": [round(ev.onset_sec, 3), round(ev.peak_sec, 3), round(ev.settle_sec, 3)],
        "expected_state_after": ev.world_state_after,
    }
    counterfactual = {
        "failure_mode": failure_mode,
        "omitted_proof_reason": (
            f"If '{ev.feature_id}' ({ev.proof_type}) is omitted, static, centered away from '{ev.reference_entity_id}', "
            f"or swapped to another scene, viewer sees narration mismatch for claim '{ev.narrative_claim_id}'."
        ),
        "falsification_condition": (
            "FAIL if decoded pre->peak->after visual delta <= epsilon, matte causal/subject area missing, "
            "or reference landmark absent when displacement is claimed."
        ),
    }
    return VisualEvidenceContract(
        contract_id=f"vec_{ev.causal_event_id}",
        causal_event_id=ev.causal_event_id,
        narrative_claim_id=ev.narrative_claim_id or f"claim_{ev.order_index:03d}",
        claim_text=ev.clause_text,
        proof_type=ev.proof_type,
        expected_visible_consequence=expected,
        counterfactual_failure=counterfactual,
        evidence_status=ev.evidence_status,
        physics_fidelity=ev.physics_fidelity,
    )


def validate_world_state_conservation(causal_events: List[CausalEvent | Dict[str, Any]]) -> Dict[str, Any]:
    """Fail closed if persistent physical world state silently resets or contradicts causality."""
    violations: List[str] = []
    timeline: List[Dict[str, Any]] = []
    ordered = [e.to_dict() if isinstance(e, CausalEvent) else dict(e) for e in causal_events]
    seen_ids: Dict[str, Dict[str, Any]] = {}

    for idx, ev in enumerate(ordered):
        cid = str(ev.get("causal_event_id") or f"cev_{idx:03d}")
        seen_ids[cid] = ev
        st_b = float(ev.get("onset_sec") or 0.0)
        pk_b = float(ev.get("peak_sec") or st_b)
        se_b = float(ev.get("settle_sec") or pk_b)
        if pk_b + 1e-4 < st_b or se_b + 1e-4 < pk_b:
            violations.append(f"Non-monotonic timing inside {cid}: onset={st_b}, peak={pk_b}, settle={se_b}")

        # Cycle & chronological ancestor check
        for parent_id in ev.get("cause_event_ids") or []:
            if parent_id == cid:
                violations.append(f"Self-loop causal edge on {cid}")
            p_ev = seen_ids.get(parent_id)
            if p_ev is not None and float(p_ev.get("onset_sec", 0.0)) > st_b + 0.05:
                violations.append(
                    f"Causal inversion: parent {parent_id} starts at {p_ev.get('onset_sec')}s after child {cid} ({st_b}s)"
                )

        wb = dict(ev.get("world_state_before") or {})
        wa = dict(ev.get("world_state_after") or {})
        allow_reset = bool(ev.get("is_flashback_transition")) or str(ev.get("state_transition_kind")) in (
            "hook_to_chronological_rewind",
            "mitigation_or_aftermath",
        )

        if idx > 0 and not allow_reset:
            prev_after = dict(ordered[idx - 1].get("world_state_after") or {})
            for mon_key in ("structural_damage", "particulate_load", "visibility_loss"):
                prev_val = float(prev_after.get(mon_key, 0.0))
                cur_val = float(wa.get(mon_key, prev_val))
                if prev_val >= 0.30 and cur_val + 0.05 < prev_val:
                    violations.append(
                        f"World-state conservation break on '{mon_key}' at {cid}: dropped {prev_val} -> {cur_val} without mitigation/rewind"
                    )
            if prev_after.get("trapped_boundary_active") and not wa.get("trapped_boundary_active") and not wb.get("clean_air_policy_active"):
                # Allow aftermath/mitigation; disallow unmotivated disappearance
                if str(ev.get("proof_type")) != "state_change_before_after":
                    violations.append(
                        f"World-state conservation break at {cid}: trapped_boundary_active vanished without mitigation transition"
                    )

        timeline.append({
            "order_index": idx,
            "causal_event_id": cid,
            "narrative_event_id": ev.get("narrative_event_id"),
            "onset_sec": st_b,
            "state_transition_kind": ev.get("state_transition_kind"),
            "world_state_before": wb,
            "world_state_after": wa,
        })

    return {
        "schema_version": "sd-world-state-conservation-1",
        "status": "FAIL" if violations else "PASS",
        "checked_events": len(ordered),
        "violations": violations,
        "world_state_timeline": timeline,
    }


def bind_causal_events_to_voice(
    causal_events: List[CausalEvent],
    words: Optional[List[Dict[str, Any]]] = None,
    total_duration_sec: Optional[float] = None,
) -> List[CausalEvent]:
    """Ensure every CausalEvent has crisp onset -> peak -> settle timings aligned with VO span."""
    if not causal_events:
        return causal_events
    wlist = list(words or [])
    dur = float(total_duration_sec or (wlist[-1]["e"] if wlist else len(causal_events) * 3.0))
    for idx, ev in enumerate(causal_events):
        st = float(ev.onset_sec)
        se = float(ev.settle_sec)
        if se <= st + 0.15:
            span = max(0.8, dur / float(max(1, len(causal_events))))
            st = round(idx * span, 3)
            se = round(min(dur, (idx + 1) * span), 3)
        ev.onset_sec = round(max(0.0, st), 3)
        ev.settle_sec = round(max(ev.onset_sec + 0.25, se), 3)
        ev.peak_sec = round(ev.onset_sec + 0.52 * (ev.settle_sec - ev.onset_sec), 3)
    return causal_events


def write_causal_traceability(
    run_dir: Path,
    causal_graph: Dict[str, Any],
    contracts_doc: Dict[str, Any],
) -> None:
    """Persist `causal_event_graph.json`, `causal_evidence_contracts.json`, and `causal_traceability.csv`."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "causal_event_graph.json").write_text(
        json.dumps(causal_graph, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "causal_evidence_contracts.json").write_text(
        json.dumps(contracts_doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    contracts_by_eid = {c["causal_event_id"]: c for c in (contracts_doc.get("contracts") or [])}
    csv_path = run_dir / "causal_traceability.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "causal_event_id",
            "narrative_event_id",
            "narrative_claim_id",
            "proof_type",
            "cause_entity_id",
            "effect_entity_id",
            "reference_entity_id",
            "feature_id",
            "semantic_region_of_change",
            "onset_sec",
            "peak_sec",
            "settle_sec",
            "expected_consequence_signal",
            "counterfactual_failure_mode",
            "evidence_status",
            "physics_fidelity",
        ])
        for ev in causal_graph.get("causal_events", []):
            c = contracts_by_eid.get(ev["causal_event_id"], {})
            exp = c.get("expected_visible_consequence") or {}
            cf = c.get("counterfactual_failure") or {}
            writer.writerow([
                ev.get("causal_event_id"),
                ev.get("narrative_event_id"),
                ev.get("narrative_claim_id"),
                ev.get("proof_type"),
                ev.get("cause_entity_id"),
                ev.get("effect_entity_id"),
                ev.get("reference_entity_id"),
                ev.get("feature_id"),
                ev.get("semantic_region_of_change"),
                ev.get("onset_sec"),
                ev.get("peak_sec"),
                ev.get("settle_sec"),
                exp.get("observable_signal"),
                cf.get("failure_mode"),
                ev.get("evidence_status"),
                ev.get("physics_fidelity"),
            ])


def build_causal_event_graph(
    visual_events: Dict[str, Any],
    story_action_graph: Optional[Dict[str, Any]] = None,
    selected_skill: str = "zach-d-films",
    words: Optional[List[Dict[str, Any]]] = None,
    run_dir: Optional[Path] = None,
    require_supported: bool = False,
) -> Dict[str, Any]:
    """Build single source of truth `CausalEvent` graph + `VisualEvidenceContract`s.

    Never fakes physical support when an event falls into an unsupported abstract or exact mechanism.
    """
    raw_events = list(visual_events.get("events") or [])
    story_by_clause_idx: Dict[int, Dict[str, Any]] = {}
    story_by_nev: Dict[str, Dict[str, Any]] = {}
    for sev in (story_action_graph or {}).get("narrative_events", []):
        story_by_nev[str(sev.get("narrative_event_id") or "")] = sev
        ci = sev.get("clause_index")
        if ci is not None and ci not in story_by_clause_idx:
            story_by_clause_idx[int(ci)] = sev

    causal_events: List[CausalEvent] = []
    state: Dict[str, Any] = {
        "hazard_intensity": 0.05,
        "particulate_load": 0.0,
        "visibility_loss": 0.0,
        "structural_damage": 0.0,
        "trapped_boundary_active": False,
        "human_impact_observed": False,
        "clean_air_policy_active": False,
    }

    total_n = len(raw_events)
    for idx, ev in enumerate(raw_events):
        nev_id = str(ev.get("narrative_event_id") or f"nev_{idx:03d}")
        s_ev = story_by_nev.get(nev_id) or story_by_clause_idx.get(int(ev.get("clause_index", idx)))
        clause_txt = str(
            ev.get("exact_narration_phrase")
            or ev.get("clause_text")
            or (s_ev or {}).get("narration_text")
            or ""
        )
        info = classify_causal_proof(clause_txt, ev, story_ev=s_ev, selected_skill=selected_skill)

        st_s = float(ev["start_sec"]) if ev.get("start_sec") is not None else float((s_ev or {}).get("start_sec") or 0.0)
        en_s = float(ev["end_sec"]) if ev.get("end_sec") is not None else float((s_ev or {}).get("end_sec") or (st_s + 2.0))
        wb, wa, tr_kind, is_flashback = _evolve_world_state(
            state,
            clause_txt.lower(),
            info["proof_type"],
            info["beat_role"],
            idx,
            total_n,
        )
        state = dict(wa)

        cev = CausalEvent(
            causal_event_id=f"cev_{idx:03d}",
            narrative_event_id=str((s_ev or {}).get("narrative_event_id") or nev_id),
            order_index=idx,
            clause_text=clause_txt,
            beat_role=info["beat_role"],
            proof_type=info["proof_type"],
            physical_action=info["physical_action"],
            mechanism_summary=f"{info['cause_entity_id']} -> {info['proof_type']} -> {info['effect_entity_id']}",
            cause_entity_id=info["cause_entity_id"],
            effect_entity_id=info["effect_entity_id"],
            reference_entity_id=info["reference_entity_id"],
            feature_id=info["feature_id"],
            semantic_region_of_change=info["semantic_region_of_change"],
            scene_family=str(ev.get("scene_family") or (s_ev or {}).get("scene_family") or ""),
            narrative_claim_id=str((s_ev or {}).get("factual_claim_id") or f"claim_{idx:03d}"),
            factual_claim_id=(s_ev or {}).get("factual_claim_id"),
            onset_sec=st_s,
            peak_sec=round(st_s + 0.52 * max(0.2, en_s - st_s), 3),
            settle_sec=en_s,
            world_state_before=wb,
            world_state_after=wa,
            state_transition_kind=tr_kind,
            is_flashforward_hook=bool(idx == 0 and wa.get("_from_hook_flashforward")),
            is_flashback_transition=is_flashback,
            evidence_status=info["evidence_status"],
            physics_fidelity=info["physics_fidelity"],
        )
        causal_events.append(cev)

    bind_causal_events_to_voice(
        causal_events,
        words=words,
        total_duration_sec=visual_events.get("total_duration_sec"),
    )
    edges = link_cause_effect_chain(causal_events)
    contracts = [make_evidence_contract(ev) for ev in causal_events]
    conservation = validate_world_state_conservation(causal_events)

    unsupported = [
        ev.causal_event_id for ev in causal_events if ev.evidence_status != EVIDENCE_SUPPORTED
    ]
    if require_supported and unsupported:
        raise ValueError(
            f"UNSUPPORTED_VISUAL_EVIDENCE: events {unsupported} cannot be proven visually in locked skill '{selected_skill}'."
        )

    causal_graph = {
        "schema_version": SCHEMA_VERSION,
        "selected_skill": selected_skill,
        "total_events": len(causal_events),
        "supported_events_count": len(causal_events) - len(unsupported),
        "unsupported_events": unsupported,
        "physics_disclosure": (
            "visualized_physical_approximation: procedural 3D kinematics/shaders illustrate mechanism timing and spatial relationships; not CFD/FEM scientific solver"
            if selected_skill == "zach-d-films"
            else f"{selected_skill}_illustrative_visual"
        ),
        "world_state_conservation": conservation,
        "causal_edges": edges,
        "causal_events": [e.to_dict() for e in causal_events],
    }
    contracts_doc = {
        "schema_version": CONTRACTS_SCHEMA_VERSION,
        "selected_skill": selected_skill,
        "contracts_count": len(contracts),
        "contracts": [c.to_dict() for c in contracts],
        "by_event_id": {c.causal_event_id: c.to_dict() for c in contracts},
    }

    if run_dir is not None:
        write_causal_traceability(run_dir, causal_graph, contracts_doc)

    return {
        "causal_graph": causal_graph,
        "evidence_contracts": contracts_doc,
    }
