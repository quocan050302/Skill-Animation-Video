"""STEP 3B (R2/R3): Unified Editorial Timeline, Kinetic Captions & Tracked 3D Callout Planner/Renderer.

Produces one authoritative `editorial_timeline.json`, `overlay_plan.json`, and
`overlay_coverage.json` locked to real `voice/words.json` + `voice_prosody_plan.json` +
`storyboard.json` + 3D world anchors, plus deterministic SVG/DOM `editorial_overlay_renderer.js`
scoped strictly to `zach-d-films`.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .visual_storytelling_director import validate_reveal_order
from .editorial_design_system import (
    EditorialRole,
    derive_editorial_role,
    emit_design_tokens_json,
    measure_text_layout,
    select_overlay_variant,
    split_curiosity_lines,
    validate_theme_semantics,
)
from .curiosity_director import (
    bind_pointer_and_headline_timing,
    find_curiosity_beats,
    plan_attention_pointer,
    score_editorial_value,
    validate_reveal_lock,
)
from .assets.editorial_theme_renderer import EDITORIAL_THEME_RENDERER_JS


SCHEMA_VERSION = "sd-editorial-timeline-1"

SAFE_X_MIN = 76
SAFE_X_MAX = 1004
SAFE_Y_MIN = 165
SAFE_Y_MAX = 1520
CAPTION_BAND_Y_MIN = 1335
CAPTION_BAND_Y_MAX = 1500

CONTRAST_WORDS = {"not", "isn't", "doesn't", "wait", "fails", "fail", "never", "crack", "instead", "alone"}
FLOW_TECH_WORDS = {
    "bleed", "breather", "equalizes", "pressure", "outer", "middle", "inner",
    "backup", "fail-safe", "moisture", "condensation", "fogging", "layers", "layer",
    "tiny", "hole", "cabin", "three", "clear", "safe", "slowly",
    "molasses", "flood", "2.3", "million", "gallons", "35", "miles", "leaking",
    "way", "rivet", "smashed", "twenty-one", "21", "150", "injured", "construction",
}


class OverlaySafetyError(ValueError):
    """Raised when overlays violate safe zone, collision, factual grounding, or density caps."""


def _boxes_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float], pad: float = 8.0) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 + pad <= bx0 or bx1 + pad <= ax0 or ay1 + pad <= by0 or by1 + pad <= ay0)


def _point_in_box(px: float, py: float, box: Tuple[float, float, float, float], pad: float = 0.0) -> bool:
    return (box[0] - pad) <= px <= (box[2] + pad) and (box[1] - pad) <= py <= (box[3] + pad)


def plan_kinetic_captions(
    words: List[Dict[str, Any]],
    prosody_plan: Optional[Dict[str, Any]] = None,
    caption_mode: str = "kinetic",
) -> List[Dict[str, Any]]:
    """Group real voiceover words into 1-3 word kinetic caption chunks synchronized to emphasis cues."""
    mode = (caption_mode or "kinetic").lower()
    if mode not in ("plain", "kinetic", "phrase"):
        raise ValueError(f"Unsupported caption_mode: {caption_mode!r}")

    emphasis_lookup: set[str] = set()
    for ph in (prosody_plan or {}).get("phrases", []):
        for ew in ph.get("emphasis_words", []):
            clean = re.sub(r"^[^\w]+|[^\w]+$", "", str(ew).lower())
            if clean:
                emphasis_lookup.add(clean)

    max_words = 4 if mode == "phrase" else 3
    max_chars = 24 if mode == "phrase" else 18

    chunks: List[Dict[str, Any]] = []
    cur: List[Dict[str, Any]] = []
    for idx, w in enumerate(words):
        cur.append(w)
        raw_txt = " ".join(str(x["w"]) for x in cur)
        stop = raw_txt.endswith((".", ",", "?", "!", ";", ":"))
        if stop or len(cur) >= max_words or len(raw_txt) >= max_chars or idx == len(words) - 1:
            start_s = round(float(cur[0]["s"]), 3)
            raw_end = float(cur[-1]["e"])
            next_s = float(words[idx + 1]["s"]) if idx + 1 < len(words) else (raw_end + 0.40)
            end_s = round(min(raw_end + 0.32, next_s), 3) if idx + 1 < len(words) else round(raw_end + 0.35, 3)
            if end_s <= start_s:
                end_s = round(start_s + 0.08, 3)

            chunk_words: List[Dict[str, Any]] = []
            accent_indices: List[int] = []
            for wi, item in enumerate(cur):
                tok = str(item["w"])
                clean_tok = re.sub(r"^[^\w]+|[^\w]+$", "", tok.lower())
                role = "normal"
                color = "#ffffff"
                if clean_tok in CONTRAST_WORDS:
                    role = "contrast"
                    color = "#f87171"
                elif clean_tok in emphasis_lookup or clean_tok in FLOW_TECH_WORDS or re.match(r"^\d", clean_tok):
                    role = "keyword"
                    color = "#fbbf24"
                is_emp = (mode != "plain") and (role != "normal")
                if is_emp and len(accent_indices) < 2:
                    accent_indices.append(wi)
                chunk_words.append({
                    "w": tok,
                    "s": round(float(item["s"]), 3),
                    "e": round(float(item["e"]), 3),
                    "is_emphasis": is_emp,
                    "accent_role": role if is_emp else "normal",
                    "accent_color": color if is_emp else "#ffffff",
                })

            clean_line = " ".join(x["w"] for x in cur).rstrip(".,;:")
            chunks.append({
                "chunk_id": f"cap_{len(chunks):03d}",
                "mode": mode,
                "start": start_s,
                "end": end_s,
                "text": clean_line,
                "words": chunk_words,
                "accent_indices": accent_indices,
                "bbox": [100, 1365, 980, 1485],
            })
            cur = []

    return chunks


def extract_editorial_focus_events(
    storyboard: Dict[str, Any],
    parsed_script: Dict[str, Any],
    verified_numbers: Optional[List[Dict[str, Any]]] = None,
    editorial_theme: str = "role-aware",
    curiosity_layer: str = "auto",
) -> List[Dict[str, Any]]:
    """Derive visually grounded, role-aware editorial callout candidates directly from storyboard anchors & facts."""
    shots = list(storyboard.get("shots", []))
    words = list((parsed_script.get("voice") or {}).get("words", []))
    candidates: List[Dict[str, Any]] = []
    fact_nums = list(verified_numbers or [])
    story_graph = storyboard.get("story_action_graph") or {}
    nevs = list(story_graph.get("narrative_events") or [])
    nev_by_id = {e.get("narrative_event_id"): e for e in nevs if e.get("narrative_event_id")}
    seed = int(storyboard.get("seed", 42))
    full_script = " ".join(str(s) for s in (parsed_script.get("sentences") or []))
    use_role_aware = (editorial_theme or "role-aware").lower() != "legacy"

    curiosity_by_nev: Dict[str, Dict[str, Any]] = {}
    if use_role_aware and (curiosity_layer or "auto").lower() != "off" and nevs:
        for hb in find_curiosity_beats(full_script, nevs, max_headlines=2):
            nid = hb.get("narrative_event_id")
            if nid:
                curiosity_by_nev[str(nid)] = hb

    prior_styled: List[Dict[str, Any]] = []
    seen_location_contexts: set[str] = set()

    for si, shot in enumerate(shots):
        st = float(shot["start"])
        en = float(shot["end"])
        dur = en - st
        if dur < 1.1:
            continue
        shot_id = str(shot["shot_id"])
        nar = str(shot.get("narration_text", ""))
        low = nar.lower()
        gen = str(shot.get("procedural_generator") or "")
        anchor = shot.get("focal_anchor") or (shot.get("camera_path") or {}).get("focal_anchor") or {}
        anchor_id = str(anchor.get("anchor_id") or "stage_center")

        shot_words = [w for w in words if st - 0.05 <= float(w.get("s", 0.0)) <= en - 0.15]
        anchor_t = round(st + min(0.38, dur * 0.22), 3)
        for sw in shot_words:
            cw = re.sub(r"[^\w\-]", "", str(sw["w"]).lower())
            if cw in FLOW_TECH_WORDS or cw in CONTRAST_WORDS:
                anchor_t = round(max(st + 0.12, min(en - 0.65, float(sw["s"]))), 3)
                break

        ov_end = round(min(en - 0.14, anchor_t + min(2.35, max(1.10, dur * 0.56))), 3)
        if ov_end - anchor_t < 0.75:
            continue

        rev_floor = float(shot.get("reveal_after_sec") or 0.0)
        anchor_t = round(max(anchor_t, rev_floor), 3)

        def _word_t(toks: Tuple[str, ...], fallback: float) -> float:
            for sw in shot_words:
                cw = re.sub(r"[^\w\.\-]", "", str(sw["w"]).lower())
                if any(cw == t or (len(t) >= 4 and t in cw) for t in toks):
                    return round(max(st + 0.08, rev_floor, float(sw["s"])), 3)
            return round(max(st + 0.12, rev_floor, fallback), 3)

        nev = nev_by_id.get(shot.get("narrative_event_id"), {})
        if use_role_aware and gen.startswith("zach3d:tacoma_"):
            hb = curiosity_by_nev.get(str(shot.get("narrative_event_id") or ""))
            if hb and gen in ("zach3d:tacoma_hook_telephoto_stage", "zach3d:tacoma_torsion_twist_stage"):
                t_on = round(max(st + 0.14, rev_floor), 3)
                if gen == "zach3d:tacoma_torsion_twist_stage":
                    t_on = _word_t(("pitched", "twist", "skyward", "plunged", "opposite"), st + 0.22)
                t_off = round(min(en - 0.14, t_on + 2.25), 3)
                if t_off - t_on >= 0.75:
                    spec = select_overlay_variant(EditorialRole.CURIOSITY_HEADLINE, contrast_needs="extreme", prior_roles=prior_styled, seed=seed + si)
                    ptr = plan_attention_pointer({
                        "beat_index": si,
                        "role": spec.role,
                        "target_anchor_id": hb["target_anchor_id"],
                        "secondary_anchor_id": hb.get("secondary_anchor_id"),
                        "pointer_shape": hb.get("pointer_shape"),
                        "narrative_event_id": nev.get("narrative_event_id"),
                    })
                    l1, l2 = split_curiosity_lines(hb["label"])
                    lay = measure_text_layout(hb["label"], spec, viewport=1080)
                    cand = {
                        "shot_index": si, "shot_id": shot_id, "narrative_event_id": nev.get("narrative_event_id"),
                        "type": "focus_ring" if gen == "zach3d:tacoma_torsion_twist_stage" else "tracked_arrow",
                        "role": spec.role, "variant_id": spec.variant_id, "style_id": spec.style_id,
                        "why_role": hb.get("why_selected", "High-hierarchy curiosity beat"),
                        "anchor_id": ptr["anchor_id"],
                        "secondary_anchor_id": ptr.get("secondary_anchor_id"),
                        "target_semantic_id": ptr.get("target_semantic_id"),
                        "target_mesh_ids": ptr.get("target_mesh_ids"),
                        "target_region_world": ptr.get("target_region_world"),
                        "target_motion_vector": ptr.get("target_motion_vector"),
                        "pointer_reason": ptr.get("pointer_reason"),
                        "pointer_shape": ptr["pointer_shape"],
                        "label": hb["label"], "display_lines": [ln for ln in (l1, l2) if ln], "sublabel": "",
                        "start": t_on, "end": t_off,
                        "preferred_side": ptr["preferred_side"], "placement_box": ptr["placement_box"],
                        "font_size_1080": lay["font_size_1080"], "stroke_width": spec.stroke_width,
                        "bg_shape": spec.bg_shape, "primary_color": spec.primary_color,
                        "secondary_color": spec.secondary_color, "outline_color": spec.outline_color,
                        "accent_color": spec.secondary_color, "contrast_ratio_min": spec.contrast_ratio_min,
                        "sfx_intent": spec.sfx_intent, "sound_intent": spec.sfx_intent,
                        "priority": 1, "verified": True, "source_fact_ids": [nev.get("factual_claim_id")] if nev.get("factual_claim_id") else [],
                    }
                    candidates.append(cand)
                    prior_styled.append(cand)
                    continue

            role_item: Optional[Tuple[EditorialRole, str, str, str, str, Optional[str], Optional[str]]] = None
            if gen == "zach3d:tacoma_wide_establish_stage" and "tacoma_1940" not in seen_location_contexts:
                seen_location_contexts.add("tacoma_1940")
                role_item = (EditorialRole.LOCATION_TIME, "bridge_midspan_twist", "TACOMA NARROWS", "Washington, 1940", "none", None, None)
            elif gen == "zach3d:tacoma_torsion_twist_stage":
                t_on = _word_t(("pitched", "twist", "skyward", "plunged", "opposite"), st + 0.22)
                role_item = (EditorialRole.WARNING_DANGER, "bridge_midspan_twist", "WHOLE DECK TWISTING", "Left & right edges roll opposite", "torsion_bracket", "FHWA HIF-11-016: asymmetric center-span torsional flutter", "claim_tacoma_torsion_1940")
            elif gen == "zach3d:tacoma_roadway_wave_stage":
                if "2,800" in low or "2800" in low:
                    role_item = (EditorialRole.VERIFIED_FACT, "bridge_midspan_twist", "2,800 FT MAIN SPAN", "Vertical wave bounce (WSDOT)", "mini_fact_tag", "WSDOT / FHWA Structural Specifications", "claim_galloping_gertie_1940")
                else:
                    role_item = (EditorialRole.EXPLANATION, "bridge_midspan_twist", "VERTICAL WAVE MOTION", "Bouncing before torsion", "curved_leader", None, None)
            elif gen == "zach3d:tacoma_under_deck_girder_stage":
                role_item = (EditorialRole.EXPLANATION, "plate_girder_windward", "8-FT PLATE GIRDER", "Solid side girder & wind flow", "curved_leader", "FHWA HIF-11-016: 8-ft solid plate stiffening girders", "claim_tacoma_plate_girder")
            elif gen == "zach3d:tacoma_collapse_plunge_stage":
                t_on = _word_t(("broke", "plunged", "collapsed", "section"), st + float(dur * 0.36))
                role_item = (EditorialRole.WARNING_DANGER, "collapse_break_seam", "SPAN BROKE FREE", "Center section plunged (~11:02 a.m.)", "impact_arrow", "WSDOT Nov 7, 1940 (~11:02 a.m.)", "claim_tacoma_collapse_1940_11_07")
                anchor_t = t_on
            elif gen == "zach3d:tacoma_aftermath_stage":
                if any(k in low for k in ("no human", "died", "redesigned", "rethink", "changed the way", "forever")):
                    role_item = (EditorialRole.AFTERMATH_SOBER, "aftermath_broken_gap", "0 HUMAN FATALITIES", "Aerodynamic trusses mandated worldwide", "none", "WSDOT Historical Archive", "claim_tacoma_witnesses_1940")
                else:
                    role_item = (EditorialRole.VERIFIED_FACT, "aftermath_broken_gap", "NOVEMBER 7, 1940", "WSDOT verified collapse date", "mini_fact_tag", "WSDOT Official Tacoma Narrows History", "claim_tacoma_collapse_1940_11_07")

            if role_item is not None:
                erole, anc_k, lbl_k, sub_k, ptr_k, f_src, f_cid = role_item
                spec = select_overlay_variant(erole, prior_roles=prior_styled, seed=seed + si)
                ptr = plan_attention_pointer({
                    "beat_index": si,
                    "role": erole.value,
                    "target_anchor_id": anc_k,
                    "secondary_anchor_id": "deck_twist_edge_r" if ptr_k == "torsion_bracket" else None,
                    "pointer_shape": ptr_k,
                    "narrative_event_id": nev.get("narrative_event_id"),
                })
                lay = measure_text_layout(lbl_k, spec, viewport=1080)
                t_on = round(max(st + 0.18, rev_floor, anchor_t if gen == "zach3d:tacoma_collapse_plunge_stage" else st + 0.28), 3)
                t_off = round(min(en - 0.14, t_on + spec.max_duration), 3)
                if t_off - t_on >= 0.85:
                    cand = {
                        "shot_index": si, "shot_id": shot_id, "narrative_event_id": nev.get("narrative_event_id"),
                        "type": "focus_ring" if ptr_k in ("focus_circle", "impact_arrow", "torsion_bracket") else "tracked_arrow",
                        "role": spec.role, "variant_id": spec.variant_id, "style_id": spec.style_id,
                        "why_role": f"Semantic role {spec.role} matched to stage {gen}",
                        "anchor_id": ptr["anchor_id"],
                        "secondary_anchor_id": ptr.get("secondary_anchor_id"),
                        "target_semantic_id": ptr.get("target_semantic_id"),
                        "target_mesh_ids": ptr.get("target_mesh_ids"),
                        "target_region_world": ptr.get("target_region_world"),
                        "pointer_reason": ptr.get("pointer_reason"),
                        "pointer_shape": ptr_k,
                        "label": lbl_k, "sublabel": sub_k,
                        "start": t_on, "end": t_off,
                        "preferred_side": ptr["preferred_side"], "placement_box": ptr["placement_box"],
                        "font_size_1080": lay["font_size_1080"], "stroke_width": spec.stroke_width,
                        "bg_shape": spec.bg_shape, "primary_color": spec.primary_color,
                        "secondary_color": spec.secondary_color, "outline_color": spec.outline_color,
                        "accent_color": spec.secondary_color, "contrast_ratio_min": spec.contrast_ratio_min,
                        "sfx_intent": spec.sfx_intent, "sound_intent": spec.sfx_intent,
                        "priority": spec.semantic_priority, "verified": True,
                        "fact_source": f_src, "source_fact_ids": [f_cid] if f_cid else [],
                    }
                    candidates.append(cand)
                    prior_styled.append(cand)
            continue

        if use_role_aware and gen.startswith("zach3d:skyscraper_"):
            hb_s = curiosity_by_nev.get(str(shot.get("narrative_event_id") or ""))
            if hb_s and gen in ("zach3d:skyscraper_street_hook_stage", "zach3d:skyscraper_counterphase_stage"):
                t_on = round(max(st + 0.14, rev_floor), 3)
                t_off = round(min(en - 0.14, t_on + 2.25), 3)
                if t_off - t_on >= 0.75:
                    spec = select_overlay_variant(EditorialRole.CURIOSITY_HEADLINE, contrast_needs="extreme", prior_roles=prior_styled, seed=seed + si)
                    ptr = plan_attention_pointer({
                        "beat_index": si,
                        "role": spec.role,
                        "target_anchor_id": hb_s["target_anchor_id"],
                        "secondary_anchor_id": hb_s.get("secondary_anchor_id"),
                        "pointer_shape": hb_s.get("pointer_shape"),
                        "narrative_event_id": nev.get("narrative_event_id"),
                    })
                    l1, l2 = split_curiosity_lines(hb_s["label"])
                    lay = measure_text_layout(hb_s["label"], spec, viewport=1080)
                    cand = {
                        "shot_index": si, "shot_id": shot_id, "narrative_event_id": nev.get("narrative_event_id"),
                        "type": "tracked_arrow",
                        "role": spec.role, "variant_id": spec.variant_id, "style_id": spec.style_id,
                        "why_role": hb_s.get("why_selected", "Skyscraper curiosity headline"),
                        "anchor_id": ptr["anchor_id"],
                        "secondary_anchor_id": ptr.get("secondary_anchor_id"),
                        "target_semantic_id": ptr.get("target_semantic_id"),
                        "target_mesh_ids": ptr.get("target_mesh_ids"),
                        "target_region_world": ptr.get("target_region_world"),
                        "pointer_reason": ptr.get("pointer_reason"),
                        "pointer_shape": ptr["pointer_shape"],
                        "label": hb_s["label"], "display_lines": [ln for ln in (l1, l2) if ln], "sublabel": "",
                        "start": t_on, "end": t_off,
                        "preferred_side": ptr["preferred_side"], "placement_box": ptr["placement_box"],
                        "font_size_1080": lay["font_size_1080"], "stroke_width": spec.stroke_width,
                        "bg_shape": spec.bg_shape, "primary_color": spec.primary_color,
                        "secondary_color": spec.secondary_color, "outline_color": spec.outline_color,
                        "accent_color": spec.secondary_color, "contrast_ratio_min": spec.contrast_ratio_min,
                        "sfx_intent": spec.sfx_intent, "sound_intent": spec.sfx_intent,
                        "priority": 1, "verified": True, "source_fact_ids": [],
                    }
                    candidates.append(cand)
                    prior_styled.append(cand)
                    continue

            sky_item: Optional[Tuple[EditorialRole, str, Optional[str], str, str, str, Optional[str], Optional[str]]] = None
            if gen == "zach3d:skyscraper_skyline_wide_stage" and "sky_wide" not in seen_location_contexts:
                seen_location_contexts.add("sky_wide")
                sky_item = (EditorialRole.LOCATION_TIME, "tower_mid_profile", None, "SLENDER HIGH-RISE", "Flexes cleanly by design", "none", None, None)
            elif gen == "zach3d:skyscraper_wind_vortex_stage":
                sky_item = (EditorialRole.EXPLANATION, "windward_facade_vortex", None, "VORTEX SHEDDING", "Alternating wind pressure", "curved_leader", None, None)
            elif gen == "zach3d:skyscraper_plumb_drift_stage":
                sky_item = (EditorialRole.EXPLANATION, "plumb_drift_tip", "plumb_static_ref", "LATERAL ROOF DRIFT", "Shifts vs static plumb line", "sway_bracket", None, None)
            elif gen == "zach3d:skyscraper_tmd_cutaway_stage":
                sky_item = (EditorialRole.EXPLANATION, "damper_pendulum_sphere", None, "TUNED MASS DAMPER", "Suspended pendulum counterweight", "curved_leader", None, None)
            elif gen == "zach3d:skyscraper_counterphase_stage":
                sky_item = (EditorialRole.WARNING_DANGER, "damper_pendulum_sphere", "counterphase_tower_frame", "COUNTER-PHASE SWING", "Weight pulls opposite tower motion", "torsion_bracket", None, None)
            elif gen == "zach3d:skyscraper_before_after_stage":
                sky_item = (EditorialRole.VERIFIED_FACT, "damped_tower_top", None, "REDUCED SWAY", "Dampers used in select tall towers", "mini_fact_tag", "ASCE 7 Structural Damping Overview (illustrative model)", "claim_tmd_select_buildings")
            elif gen == "zach3d:skyscraper_dusk_resolution_stage":
                sky_item = (EditorialRole.AFTERMATH_SOBER, "rooftop_sway_apex", None, "DESIGNED TO MOVE", "Some tall buildings use dampers", "none", None, None)

            if sky_item is not None:
                erole, anc_k, sec_k, lbl_k, sub_k, ptr_k, f_src, f_cid = sky_item
                spec = select_overlay_variant(erole, prior_roles=prior_styled, seed=seed + si)
                ptr = plan_attention_pointer({
                    "beat_index": si, "role": erole.value, "target_anchor_id": anc_k,
                    "secondary_anchor_id": sec_k, "pointer_shape": ptr_k,
                    "narrative_event_id": nev.get("narrative_event_id"),
                })
                lay = measure_text_layout(lbl_k, spec, viewport=1080)
                t_on = round(max(st + 0.18, rev_floor, st + 0.25), 3)
                t_off = round(min(en - 0.14, t_on + spec.max_duration), 3)
                if t_off - t_on >= 0.85:
                    cand = {
                        "shot_index": si, "shot_id": shot_id, "narrative_event_id": nev.get("narrative_event_id"),
                        "type": "focus_ring" if ptr_k in ("focus_circle", "impact_arrow", "torsion_bracket", "sway_bracket") else "tracked_arrow",
                        "role": spec.role, "variant_id": spec.variant_id, "style_id": spec.style_id,
                        "why_role": f"Semantic role {spec.role} matched to stage {gen}",
                        "anchor_id": ptr["anchor_id"],
                        "secondary_anchor_id": ptr.get("secondary_anchor_id"),
                        "target_semantic_id": ptr.get("target_semantic_id"),
                        "target_mesh_ids": ptr.get("target_mesh_ids"),
                        "target_region_world": ptr.get("target_region_world"),
                        "pointer_reason": ptr.get("pointer_reason"),
                        "pointer_shape": ptr_k,
                        "label": lbl_k, "sublabel": sub_k,
                        "start": t_on, "end": t_off,
                        "preferred_side": ptr["preferred_side"], "placement_box": ptr["placement_box"],
                        "font_size_1080": lay["font_size_1080"], "stroke_width": spec.stroke_width,
                        "bg_shape": spec.bg_shape, "primary_color": spec.primary_color,
                        "secondary_color": spec.secondary_color, "outline_color": spec.outline_color,
                        "accent_color": spec.secondary_color, "contrast_ratio_min": spec.contrast_ratio_min,
                        "sfx_intent": spec.sfx_intent, "sound_intent": spec.sfx_intent,
                        "priority": spec.semantic_priority, "verified": True,
                        "fact_source": f_src, "source_fact_ids": [f_cid] if f_cid else [],
                    }
                    candidates.append(cand)
                    prior_styled.append(cand)
            continue

        if use_role_aware and gen.startswith("zach3d:london_"):
            hb_l = curiosity_by_nev.get(str(shot.get("narrative_event_id") or ""))
            if hb_l and gen in ("zach3d:london_fog_street_hook_stage", "zach3d:london_atmospheric_inversion_stage"):
                t_on = round(max(st + 0.16, rev_floor), 3)
                t_off = round(min(en - 0.14, t_on + 2.25), 3)
                if t_off - t_on >= 0.75:
                    spec = select_overlay_variant(EditorialRole.CURIOSITY_HEADLINE, contrast_needs="extreme", prior_roles=prior_styled, seed=seed + si)
                    ptr = plan_attention_pointer({
                        "beat_index": si,
                        "role": spec.role,
                        "target_anchor_id": hb_l["target_anchor_id"],
                        "secondary_anchor_id": hb_l.get("secondary_anchor_id"),
                        "pointer_shape": hb_l.get("pointer_shape"),
                        "narrative_event_id": nev.get("narrative_event_id"),
                    })
                    l1, l2 = split_curiosity_lines(hb_l["label"])
                    lay = measure_text_layout(hb_l["label"], spec, viewport=1080)
                    cand = {
                        "shot_index": si, "shot_id": shot_id, "narrative_event_id": nev.get("narrative_event_id"),
                        "type": "tracked_arrow",
                        "role": spec.role, "variant_id": spec.variant_id, "style_id": spec.style_id,
                        "why_role": hb_l.get("why_selected", "Atmospheric smog curiosity hook"),
                        "anchor_id": ptr["anchor_id"],
                        "secondary_anchor_id": ptr.get("secondary_anchor_id"),
                        "target_semantic_id": ptr.get("target_semantic_id"),
                        "target_mesh_ids": ptr.get("target_mesh_ids"),
                        "target_region_world": ptr.get("target_region_world"),
                        "pointer_reason": ptr.get("pointer_reason"),
                        "pointer_shape": ptr["pointer_shape"],
                        "label": hb_l["label"], "display_lines": [ln for ln in (l1, l2) if ln], "sublabel": "",
                        "start": t_on, "end": t_off,
                        "preferred_side": ptr["preferred_side"], "placement_box": ptr["placement_box"],
                        "font_size_1080": lay["font_size_1080"], "stroke_width": spec.stroke_width,
                        "bg_shape": spec.bg_shape, "primary_color": spec.primary_color,
                        "secondary_color": spec.secondary_color, "outline_color": spec.outline_color,
                        "accent_color": spec.secondary_color, "contrast_ratio_min": spec.contrast_ratio_min,
                        "sfx_intent": spec.sfx_intent, "sound_intent": spec.sfx_intent,
                        "priority": 1, "verified": True, "source_fact_ids": [],
                    }
                    candidates.append(cand)
                    prior_styled.append(cand)
                    continue

            lon_item: Optional[Tuple[EditorialRole, str, Optional[str], str, str, str, Optional[str], Optional[str]]] = None
            if gen == "zach3d:london_fog_street_hook_stage" and "lon_1952" not in seen_location_contexts:
                seen_location_contexts.add("lon_1952")
                lon_item = (EditorialRole.LOCATION_TIME, "streetlamp_halo_visibility", "lamppost_column_ref", "DEC 5-9, 1952", "Five-day London smog event", "none", "UK Met Office Great Smog 1952 archive", "claim_dates_dec5_9_1952")
            elif gen == "zach3d:london_coal_combustion_cutaway_stage":
                lon_item = (EditorialRole.EXPLANATION, "chimney_flue_combustion", None, "COAL & SULFUR SMOKE", "Domestic hearths + coal power stacks", "curved_leader", "London Museum 1952 coal smoke overview", "claim_coal_sulfur_smoke")
            elif gen == "zach3d:london_atmospheric_inversion_stage":
                lon_item = (EditorialRole.WARNING_DANGER, "inversion_thermal_boundary", "st_pauls_dome_and_horizon_ref", "WARM AIR LID", "ILLUSTRATIVE AIRFLOW — trapped cold air", "impact_arrow", "UK Met Office temperature inversion explanation", "claim_temperature_inversion_1952")
            elif gen == "zach3d:london_bus_visibility_stage":
                lon_item = (EditorialRole.EXPLANATION, "bus_headlight_cone", "lamppost_column_ref", "NEAR-ZERO VISIBILITY", "Walkers led buses with handheld lanterns", "curved_leader", "London Transport Dec 1952 fog reports", "claim_zero_visibility_Dec1952")
            elif gen == "zach3d:london_pedestrian_reaction_stage":
                if "4,000" in low or "deaths" in low or "four thousand" in low:
                    lon_item = (EditorialRole.VERIFIED_FACT, "pedestrian_respiratory_stance_zone", None, "~4,000 DEATHS EST.", "Estimated monthly excess deaths (City Hall)", "mini_fact_tag", "London City Hall Great Smog 1952 archive", "claim_excess_deaths_est_4000")
                else:
                    lon_item = (EditorialRole.WARNING_DANGER, "pedestrian_respiratory_stance_zone", None, "ACIDIC FOG DROPLETS", "Soot & sulfuric droplets strained airways", "impact_arrow", "UK Met Office health impact note", "claim_respiratory_impact")
            elif gen == "zach3d:london_clean_air_aftermath_stage":
                lon_item = (EditorialRole.AFTERMATH_SOBER, "smokeless_hearth_transition", None, "CLEAN AIR ACT 1956", "Transition toward smokeless coal & clean air", "none", "UK Clean Air Act 1956 record", "claim_clean_air_act_1956")

            if lon_item is not None:
                erole, anc_k, sec_k, lbl_k, sub_k, ptr_k, f_src, f_cid = lon_item
                spec = select_overlay_variant(erole, prior_roles=prior_styled, seed=seed + si)
                ptr = plan_attention_pointer({
                    "beat_index": si, "role": erole.value, "target_anchor_id": anc_k,
                    "secondary_anchor_id": sec_k, "pointer_shape": ptr_k,
                    "narrative_event_id": nev.get("narrative_event_id"),
                })
                lay = measure_text_layout(lbl_k, spec, viewport=1080)
                t_on = round(max(st + 0.18, rev_floor, st + 0.24), 3)
                t_off = round(min(en - 0.14, t_on + spec.max_duration), 3)
                if t_off - t_on >= 0.80:
                    cand = {
                        "shot_index": si, "shot_id": shot_id, "narrative_event_id": nev.get("narrative_event_id"),
                        "type": "focus_ring" if ptr_k in ("focus_circle", "impact_arrow", "torsion_bracket", "sway_bracket") else "tracked_arrow",
                        "role": spec.role, "variant_id": spec.variant_id, "style_id": spec.style_id,
                        "why_role": f"Semantic role {spec.role} matched to atmospheric stage {gen}",
                        "anchor_id": ptr["anchor_id"],
                        "secondary_anchor_id": ptr.get("secondary_anchor_id"),
                        "target_semantic_id": ptr.get("target_semantic_id"),
                        "target_mesh_ids": ptr.get("target_mesh_ids"),
                        "target_region_world": ptr.get("target_region_world"),
                        "pointer_reason": ptr.get("pointer_reason"),
                        "pointer_shape": ptr_k,
                        "label": lbl_k, "sublabel": sub_k,
                        "start": t_on, "end": t_off,
                        "preferred_side": ptr["preferred_side"], "placement_box": ptr["placement_box"],
                        "font_size_1080": lay["font_size_1080"], "stroke_width": spec.stroke_width,
                        "bg_shape": spec.bg_shape, "primary_color": spec.primary_color,
                        "secondary_color": spec.secondary_color, "outline_color": spec.outline_color,
                        "accent_color": spec.secondary_color, "contrast_ratio_min": spec.contrast_ratio_min,
                        "sfx_intent": spec.sfx_intent, "sound_intent": spec.sfx_intent,
                        "priority": spec.semantic_priority, "verified": True,
                        "fact_source": f_src, "source_fact_ids": [f_cid] if f_cid else [],
                    }
                    candidates.append(cand)
                    prior_styled.append(cand)
            continue

        if gen.startswith("zach3d:boston_"):
            hb_b = curiosity_by_nev.get(str(shot.get("narrative_event_id") or "")) if use_role_aware else None
            if hb_b and gen == "zach3d:boston_street_hook_stage" and si == 0:
                h_lbl = "A FLOOD / OF SYRUP?" if "syrup" in low else hb_b["label"]
                t_on = round(max(st + 0.16, rev_floor), 3)
                t_off = round(min(en - 0.14, t_on + 2.25), 3)
                if t_off - t_on >= 0.75:
                    spec = select_overlay_variant(EditorialRole.CURIOSITY_HEADLINE, contrast_needs="extreme", prior_roles=prior_styled, seed=seed + si)
                    ptr = plan_attention_pointer({"beat_index": si, "role": spec.role, "target_anchor_id": "street_hero_look", "narrative_event_id": nev.get("narrative_event_id")})
                    l1, l2 = split_curiosity_lines(h_lbl)
                    lay = measure_text_layout(h_lbl, spec, viewport=1080)
                    cand = {
                        "shot_index": si, "shot_id": shot_id, "narrative_event_id": nev.get("narrative_event_id"),
                        "type": "tracked_arrow",
                        "role": spec.role, "variant_id": spec.variant_id, "style_id": spec.style_id,
                        "why_role": hb_b.get("why_selected", "Opening curiosity hook"),
                        "anchor_id": ptr["anchor_id"], "pointer_shape": ptr["pointer_shape"],
                        "label": h_lbl, "display_lines": [ln for ln in (l1, l2) if ln], "sublabel": "",
                        "start": t_on, "end": t_off,
                        "preferred_side": ptr["preferred_side"], "placement_box": ptr["placement_box"],
                        "font_size_1080": lay["font_size_1080"], "stroke_width": spec.stroke_width,
                        "bg_shape": spec.bg_shape, "primary_color": spec.primary_color,
                        "secondary_color": spec.secondary_color, "outline_color": spec.outline_color,
                        "accent_color": spec.secondary_color, "contrast_ratio_min": spec.contrast_ratio_min,
                        "sfx_intent": spec.sfx_intent, "sound_intent": spec.sfx_intent,
                        "priority": 1, "verified": True, "source_fact_ids": [nev.get("factual_claim_id")] if nev.get("factual_claim_id") else [],
                    }
                    candidates.append(cand)
                    prior_styled.append(cand)
                    continue

            if gen == "zach3d:boston_street_hook_stage":
                # Non-spoiler geographical grounding only (never reveals "molasses" early!)
                t_on = _word_t(("boston", "1919"), st + 0.35)
                if en - t_on >= 0.85:
                    candidates.append({
                        "shot_index": si, "shot_id": shot_id, "type": "tracked_arrow",
                        "anchor_id": "street_hero_look",
                        "label": "NORTH END, BOSTON",
                        "sublabel": "January 15, 1919",
                        "start": t_on, "end": round(min(en - 0.15, t_on + 2.2), 3),
                        "preferred_side": "left", "accent_color": "#fbbf24", "priority": 1, "verified": True,
                    })
            elif gen == "zach3d:boston_molasses_reveal_stage":
                is_survive_twist = any(k in low for k in ("surviving", "wasn't enough", "wasn’t enough", "first impact")) and "molasses" not in low
                t_on = _word_t(("surviving", "impact", "enough"), anchor_t) if is_survive_twist else _word_t(("molasses",), anchor_t)
                if en - t_on >= 0.70:
                    candidates.append({
                        "shot_index": si, "shot_id": shot_id, "type": "focus_ring",
                        "anchor_id": "molasses_reveal_crest",
                        "label": "VISCOUS ENTRAPMENT" if is_survive_twist else "RAW MOLASSES SURGE",
                        "sublabel": "Cold winter surge fills street" if is_survive_twist else "Dense industrial sweetener",
                        "start": t_on, "end": round(min(en - 0.12, t_on + 2.1), 3),
                        "preferred_side": "right", "accent_color": "#f59e0b", "priority": 1, "verified": True,
                    })
            elif gen == "zach3d:boston_tank_leak_stage":
                if shot.get("setup_type") == "boston_tank_scale_payoff":
                    continue
                has_vol_cap = ("million" in low and "gallons" in low and "leaking" not in low)
                t_on = _word_t(("million", "gallons", "tank"), anchor_t) if has_vol_cap else _word_t(("leaking", "years"), anchor_t)
                if en - t_on >= 0.75:
                    candidates.append({
                        "shot_index": si, "shot_id": shot_id, "type": "tracked_arrow",
                        "anchor_id": "tank_seam_drip",
                        "label": "OVER 2M GALLONS" if has_vol_cap else "CHRONIC SEAM LEAKS",
                        "sublabel": "North End tank, Jan 15, 1919" if has_vol_cap else "Documented prior to failure",
                        "start": t_on, "end": round(min(en - 0.12, t_on + 2.25), 3),
                        "preferred_side": "left", "accent_color": "#f59e0b", "priority": 1, "verified": True,
                        **({"fact_source": "Boston.gov / BPL >2M (~2.3M) gallon tank capacity"} if has_vol_cap else {}),
                    })
            elif gen == "zach3d:boston_tank_rupture_stage":
                t_on = _word_t(("way", "burst", "rupture", "afternoon", "gave", "walls"), anchor_t)
                if en - t_on >= 0.60:
                    candidates.append({
                        "shot_index": si, "shot_id": shot_id, "type": "focus_ring",
                        "anchor_id": "tank_rivet_seam",
                        "label": "RIVETED STEEL SEAM",
                        "sublabel": "Plates sheared outward",
                        "start": t_on, "end": round(min(en - 0.12, t_on + 2.20), 3),
                        "preferred_side": "right", "accent_color": "#f87171", "priority": 1, "verified": True,
                    })
            elif gen == "zach3d:boston_wave_street_stage":
                if "35" in low or "faster" in low or "race" in low:
                    t_on = _word_t(("35", "faster", "horse"), anchor_t)
                    if en - t_on >= 0.60:
                        candidates.append({
                            "shot_index": si, "shot_id": shot_id, "type": "focus_ring",
                            "anchor_id": "wave_front_crest",
                            "label": "~35 MPH EST.",
                            "sublabel": "Reported peak initial surge",
                            "start": t_on, "end": round(min(en - 0.12, t_on + 2.25), 3),
                            "preferred_side": "right", "accent_color": "#f87171", "priority": 1, "verified": True,
                            "fact_source": "Historical eyewitness/engineering speed estimate (~35 mph)",
                        })
                elif "2.3" in low or ("million" in low and "gallons" in low):
                    has_23 = "2.3" in low
                    t_on = _word_t(("2.3", "million", "gallons"), anchor_t)
                    if en - t_on >= 0.60:
                        candidates.append({
                            "shot_index": si, "shot_id": shot_id, "type": "tracked_arrow",
                            "anchor_id": "wave_front_crest",
                            "label": "~2.3M GALLONS" if has_23 else "MILLIONS OF GALLONS",
                            "sublabel": "Released across North End",
                            "start": t_on, "end": round(min(en - 0.12, t_on + 2.30), 3),
                            "preferred_side": "left", "accent_color": "#fbbf24", "priority": 1, "verified": True,
                            "fact_source": "Boston.gov / BPL ~2.3 million gallon tank volume estimate",
                        })
                elif any(k in low for k in ("sticky", "debris", "pins", "knocked")):
                    t_on = _word_t(("sticky", "syrup", "debris", "knocked"), anchor_t)
                    if en - t_on >= 0.65:
                        candidates.append({
                            "shot_index": si, "shot_id": shot_id, "type": "tracked_arrow",
                            "anchor_id": "wave_front_crest",
                            "label": "THICK STICKY DEBRIS",
                            "sublabel": "Heavy timber & cold syrup",
                            "start": t_on, "end": round(min(en - 0.12, t_on + 2.20), 3),
                            "preferred_side": "left", "accent_color": "#fbbf24", "priority": 1, "verified": True,
                        })
            elif gen == "zach3d:boston_elevated_rail_impact_stage":
                t_on = _word_t(("smashed", "buildings", "trapped", "wreckage"), anchor_t)
                if en - t_on >= 0.75:
                    candidates.append({
                        "shot_index": si, "shot_id": shot_id, "type": "tracked_arrow",
                        "anchor_id": "elevated_rail_column",
                        "label": "STRUCTURAL IMPACT",
                        "sublabel": "Trestle & timber buildings",
                        "start": t_on, "end": round(min(en - 0.12, t_on + 2.15), 3),
                        "preferred_side": "right", "accent_color": "#f87171", "priority": 1, "verified": True,
                    })
            elif gen == "zach3d:boston_rescue_aftermath_stage":
                if any(k in low for k in ("twenty-one", "21", "died", "150")):
                    t_on = _word_t(("twenty-one", "21", "died", "injured", "150"), anchor_t)
                    if en - t_on >= 0.75:
                        candidates.append({
                            "shot_index": si, "shot_id": shot_id, "type": "tracked_arrow",
                            "anchor_id": "rescue_aftermath_center",
                            "label": "21 LIVES LOST",
                            "sublabel": "About 150 people injured",
                            "start": t_on, "end": round(min(en - 0.14, t_on + 2.35), 3),
                            "preferred_side": "left", "accent_color": "#e2e8f0", "priority": 1, "verified": True,
                            "fact_source": "Boston.gov & BPL official toll: 21 killed, ~150 injured",
                        })
                elif "rescuer" in low:
                    t_on = _word_t(("rescuer", "rescuers", "struggled"), anchor_t)
                    if en - t_on >= 0.75:
                        candidates.append({
                            "shot_index": si, "shot_id": shot_id, "type": "tracked_arrow",
                            "anchor_id": "rescue_aftermath_center",
                            "label": "RESCUE RESPONSE",
                            "sublabel": "Crews wading deep molasses",
                            "start": t_on, "end": round(min(en - 0.14, t_on + 2.15), 3),
                            "preferred_side": "right", "accent_color": "#cbd5e1", "priority": 2, "verified": True,
                        })
            elif gen == "zach3d:boston_engineering_cutaway_stage":
                is_hydro_cut = any(k in low for k in ("kitchen jar", "pours slowly", "escaped at once"))
                t_on = _word_t(("millions", "escaped", "flood"), anchor_t) if is_hydro_cut else _word_t(("construction", "engineers", "steel"), anchor_t)
                if en - t_on >= 0.75:
                    candidates.append({
                        "shot_index": si, "shot_id": shot_id, "type": "tracked_arrow",
                        "anchor_id": "lap_joint_defect",
                        "label": "HYDROSTATIC HEAD" if is_hydro_cut else "THIN STEEL & RIVETS",
                        "sublabel": "Massive column burst at once" if is_hydro_cut else "Post-1919 code overhaul",
                        "start": t_on, "end": round(min(en - 0.14, t_on + 2.25), 3),
                        "preferred_side": "right", "accent_color": "#38bdf8", "priority": 1, "verified": True,
                    })
        elif gen == "zach3d:airplane_window_hole_stage" or "bleed" in low or "airplane window" in low or "hole" in low:
            if "fails" in low or "backup" in low or "fail-safe" in low or "wait" in low:
                candidates.append({
                    "shot_index": si,
                    "shot_id": shot_id,
                    "type": "focus_ring",
                    "anchor_id": "middle_pane_core",
                    "label": "FAIL-SAFE BACKUP",
                    "sublabel": "Middle pane holds load",
                    "start": anchor_t,
                    "end": ov_end,
                    "preferred_side": "right",
                    "accent_color": "#f87171",
                    "priority": 1,
                    "verified": True,
                })
            elif "moisture" in low or "fog" in low or "clear" in low:
                candidates.append({
                    "shot_index": si,
                    "shot_id": shot_id,
                    "type": "tracked_arrow",
                    "anchor_id": "bleed_vent_port",
                    "label": "MOISTURE VENT",
                    "sublabel": "Prevents frost & fogging",
                    "start": anchor_t,
                    "end": ov_end,
                    "preferred_side": "right",
                    "accent_color": "#34d399",
                    "priority": 1,
                    "verified": True,
                })
            elif "three" in low or "layers" in low or ("outer pane" in low and "middle pane" in low):
                candidates.append({
                    "shot_index": si,
                    "shot_id": shot_id,
                    "type": "tracked_arrow",
                    "anchor_id": "window_pane_stack",
                    "label": "3 STRUCTURAL PANES",
                    "sublabel": "Outer pressure + middle backup",
                    "start": anchor_t,
                    "end": ov_end,
                    "preferred_side": "left" if (si % 2 == 0) else "right",
                    "accent_color": "#38bdf8",
                    "priority": 1,
                    "verified": True,
                })
                candidates.append({
                    "shot_index": si,
                    "shot_id": shot_id,
                    "type": "verified_counter",
                    "anchor_id": "window_pane_stack",
                    "target_value": 3,
                    "prefix": "",
                    "suffix": " PANES",
                    "label": "3-PANE ASSEMBLY",
                    "start": round(max(st + 0.20, anchor_t), 3),
                    "end": round(min(en - 0.15, st + 2.40), 3),
                    "placement_box": [112, 255, 518, 363],
                    "accent_color": "#fbbf24",
                    "priority": 2,
                    "verified": True,
                    "fact_source": "14 CFR § 25.775 multi-pane cabin window architecture",
                })
            elif "equalizes" in low or "equalize" in low or "carries" in low or "pressure" in low or "load" in low:
                candidates.append({
                    "shot_index": si,
                    "shot_id": shot_id,
                    "type": "tracked_arrow",
                    "anchor_id": "outer_pressure_pane",
                    "label": "OUTER PANE LOAD",
                    "sublabel": "Carries cabin pressure delta",
                    "start": anchor_t,
                    "end": ov_end,
                    "preferred_side": "left",
                    "accent_color": "#38bdf8",
                    "priority": 1,
                    "verified": True,
                })
            elif si == 0:
                is_bleed_spoken = "bleed" in low or "breather" in low
                candidates.append({
                    "shot_index": si,
                    "shot_id": shot_id,
                    "type": "focus_ring",
                    "anchor_id": "middle_bleed_hole",
                    "label": "BLEED HOLE" if is_bleed_spoken else "WINDOW OPENING",
                    "sublabel": "Intentional breather port" if is_bleed_spoken else "Tiny port near base",
                    "start": anchor_t,
                    "end": ov_end,
                    "preferred_side": "right",
                    "accent_color": "#fbbf24",
                    "priority": 1,
                    "verified": True,
                })
        else:
            # Generic domain-honest tracked focus ring only for first contact / cutaway shots (keep clean restraint)
            ca = (shot.get("staging") or {}).get("contact_action")
            if isinstance(ca, dict) or ("cutaway" in gen and si % 2 == 1):
                candidates.append({
                    "shot_index": si,
                    "shot_id": shot_id,
                    "type": "focus_ring",
                    "anchor_id": anchor_id,
                    "label": "CONTACT POINT" if isinstance(ca, dict) else "CUTAWAY CORE",
                    "sublabel": "",
                    "start": anchor_t,
                    "end": ov_end,
                    "preferred_side": "right" if si % 2 == 0 else "left",
                    "accent_color": "#38bdf8",
                    "priority": 2,
                    "verified": True,
                })

    # Respect user-verified numbers ONLY when verified=True and explicitly supplied
    for fn in fact_nums:
        if not fn.get("verified", False):
            continue
        # Only add if not already covered by a counter
        if not any(c.get("type") == "verified_counter" for c in candidates) and shots:
            candidates.append({
                "shot_index": 0,
                "shot_id": shots[0]["shot_id"],
                "type": "verified_counter",
                "anchor_id": "stage_center",
                "target_value": fn["value"],
                "prefix": str(fn.get("prefix", "")),
                "suffix": str(fn.get("suffix", "")),
                "label": str(fn.get("label", "VERIFIED METRIC")),
                "start": float(fn.get("start", shots[0]["start"] + 0.25)),
                "end": float(fn.get("end", min(shots[0]["end"] - 0.15, shots[0]["start"] + 2.4))),
                "placement_box": [118, 255, 458, 355],
                "accent_color": "#fbbf24",
                "priority": 2,
                "verified": True,
                "fact_source": str(fn.get("source", "script")),
            })

    return candidates


def plan_3d_callouts(
    candidates: List[Dict[str, Any]],
    total_duration: float,
    callout_mode: str = "smart",
    caption_chunks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Select non-overlapping, safe-area-bounded, anti-clutter smart overlays."""
    mode = (callout_mode or "smart").lower()
    if mode not in ("off", "smart"):
        raise ValueError(f"Unsupported callout_mode: {callout_mode!r}")
    if mode == "off":
        return {"mode": "off", "overlays": [], "rejected": []}

    ordered = sorted(candidates, key=lambda c: (float(c["start"]), int(c.get("priority", 2))))
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    beat_card_count = 0

    for idx, cand in enumerate(ordered):
        if not cand.get("verified", True):
            rejected.append({**cand, "reject_reason": "unverified_claim"})
            continue

        st = round(max(0.0, float(cand["start"])), 3)
        en = round(min(total_duration - 0.05, float(cand["end"])), 3)
        if en - st < 0.65:
            rejected.append({**cand, "reject_reason": "too_short"})
            continue

        ctype = str(cand.get("type") or "focus_ring")
        if ctype == "beat_card":
            if beat_card_count >= 2:
                rejected.append({**cand, "reject_reason": "beat_card_cap"})
                continue
            beat_card_count += 1

        # Determine non-overlapping safe screen box
        pbox = cand.get("placement_box")
        if not pbox:
            # Place legible mobile-scaled callouts cleanly inside safe zone above caption band
            slot = len(accepted) % 2
            y0 = 308 + slot * 150
            if cand.get("preferred_side") == "left":
                pbox = [112, y0, 518, y0 + 108]
            else:
                pbox = [562, y0, 968, y0 + 108]

        bx0, by0, bx1, by1 = [float(v) for v in pbox]
        # Guarantee safe area + caption band avoidance
        if bx0 < SAFE_X_MIN or bx1 > SAFE_X_MAX or by0 < SAFE_Y_MIN or by1 > CAPTION_BAND_Y_MIN - 25:
            rejected.append({**cand, "reject_reason": "unsafe_or_caption_overlap"})
            continue

        # Global simultaneous clutter cap <= 2 and spacing check
        concurrent = [a for a in accepted if not (a["end"] <= st + 0.05 or a["start"] >= en - 0.05)]
        if len(concurrent) >= 2:
            rejected.append({**cand, "reject_reason": "max_simultaneous_cap"})
            continue

        # Reposition vertically once if overlapping a concurrent overlay
        cur_box = (bx0, by0, bx1, by1)
        if any(_boxes_overlap(cur_box, tuple(a["placement_box"]), pad=14.0) for a in concurrent):
            shifted_y0 = by0 + 135
            shifted_y1 = by1 + 135
            if shifted_y1 <= CAPTION_BAND_Y_MIN - 25 and not any(
                _boxes_overlap((bx0, shifted_y0, bx1, shifted_y1), tuple(a["placement_box"]), pad=14.0)
                for a in concurrent
            ):
                pbox = [bx0, shifted_y0, bx1, shifted_y1]
            else:
                rejected.append({**cand, "reject_reason": "concurrent_box_collision"})
                continue

        # Prevent identical callout labels on back-to-back shots (anti-clutter & fresh focus)
        if accepted and accepted[-1].get("label") == cand.get("label") and abs(st - float(accepted[-1]["end"])) < 3.5:
            rejected.append({**cand, "reject_reason": "duplicate_label_cooldown"})
            continue

        # Enforce breathing gap if non-anchored overlay repeats immediately within same shot
        same_anchor_recent = [
            a for a in accepted
            if a.get("anchor_id") == cand.get("anchor_id")
            and a.get("shot_id") == cand.get("shot_id")
            and abs(st - float(a["end"])) < 0.45
        ]
        if same_anchor_recent:
            rejected.append({**cand, "reject_reason": "anchor_spam_cooldown"})
            continue

        accepted.append({
            "overlay_id": f"ov_{len(accepted):02d}",
            "shot_index": cand.get("shot_index"),
            "shot_id": cand.get("shot_id"),
            "causal_event_id": cand.get("causal_event_id"),
            "narrative_claim_id": cand.get("narrative_claim_id") or cand.get("factual_claim_id") or f"claim_{cand.get('shot_id') or len(accepted)}",
            "target_entity_id": cand.get("target_entity_id") or str(cand.get("anchor_id") or "stage_center"),
            "target_feature_id": cand.get("target_feature_id") or str(cand.get("target_semantic_id") or cand.get("anchor_id") or "stage_center"),
            "proof_target_id": cand.get("proof_target_id") or str(cand.get("target_semantic_id") or cand.get("anchor_id") or "stage_center"),
            "semantic_region_of_change": cand.get("semantic_region_of_change") or "primary_causal_zone",
            "why_this_overlay": cand.get("why_this_overlay") or cand.get("pointer_reason") or cand.get("why_role") or "Binds caption claim to visible causal region of change",
            "type": ctype,
            "anchor_id": str(cand.get("anchor_id") or "stage_center"),
            "secondary_anchor_id": cand.get("secondary_anchor_id"),
            "target_semantic_id": cand.get("target_semantic_id") or str(cand.get("anchor_id") or "stage_center"),
            "target_mesh_ids": list(cand.get("target_mesh_ids") or [str(cand.get("anchor_id") or "stage_center")]),
            "target_region_world": cand.get("target_region_world"),
            "target_motion_vector": cand.get("target_motion_vector"),
            "pointer_reason": cand.get("pointer_reason"),
            "label": str(cand.get("label") or ""),
            "sublabel": str(cand.get("sublabel") or ""),
            "start": st,
            "end": en,
            "preferred_side": cand.get("preferred_side", "right"),
            "placement_box": [round(float(x), 1) for x in pbox],
            "accent_color": cand.get("accent_color", "#38bdf8"),
            "role": cand.get("role", "explanation"),
            "variant_id": cand.get("variant_id", "legacy"),
            "style_id": cand.get("style_id", "legacy"),
            "why_role": cand.get("why_role", "Legacy callout candidate"),
            "pointer_shape": cand.get("pointer_shape", "curved_leader" if ctype == "tracked_arrow" else "focus_circle"),
            "display_lines": cand.get("display_lines"),
            "font_size_1080": cand.get("font_size_1080", 32),
            "stroke_width": cand.get("stroke_width", 0),
            "bg_shape": cand.get("bg_shape", "capsule"),
            "primary_color": cand.get("primary_color", "#f8fafc"),
            "secondary_color": cand.get("secondary_color", cand.get("accent_color", "#38bdf8")),
            "outline_color": cand.get("outline_color", "#090d16"),
            "contrast_ratio_min": cand.get("contrast_ratio_min", 4.5),
            "sfx_intent": cand.get("sfx_intent"),
            "sound_intent": cand.get("sound_intent"),
            "source_fact_ids": list(cand.get("source_fact_ids") or []),
            "target_value": cand.get("target_value"),
            "prefix": cand.get("prefix", ""),
            "suffix": cand.get("suffix", ""),
            "verified": True,
            "fact_source": cand.get("fact_source"),
            "hide_on_occlusion": True,
            "hide_if_offscreen": True,
        })

    # Ensure >= 20% of timeline frames are overlay-free breathing room for clean visual appreciation
    sample_n = max(10, int(round(total_duration * 2)))
    def _calc_free_ratio(items: List[Dict[str, Any]]) -> float:
        free_ticks = 0
        for k in range(sample_n):
            t = (k + 0.5) / 2.0
            if not any(o["start"] <= t <= o["end"] for o in items):
                free_ticks += 1
        return free_ticks / float(sample_n)

    free_ratio = _calc_free_ratio(accepted)
    while len(accepted) > 2 and free_ratio < 0.20:
        # Drop lowest-priority non-hook item cleanly rather than crowding visuals
        drop_idx = max(
            range(1, len(accepted)),
            key=lambda idx: (int(accepted[idx].get("priority", 2)), -float(accepted[idx].get("start", 0.0))),
        )
        rejected.append({**accepted.pop(drop_idx), "reject_reason": "breathing_room_20pct_cap"})
        free_ratio = _calc_free_ratio(accepted)

    return {
        "mode": mode,
        "overlays": accepted,
        "rejected": rejected,
        "free_screen_ratio": round(free_ratio, 3),
    }


def validate_overlay_plan(timeline: Dict[str, Any]) -> Dict[str, Any]:
    """Fail closed if any overlay is unverified, collides with caption band, or breaks safe area."""
    errors: List[str] = []
    warnings: List[str] = []
    overlays = list(timeline.get("overlays") or [])
    chunks = list(timeline.get("caption_chunks") or [])

    for ov in overlays:
        if not ov.get("verified", False):
            errors.append(f"Unverified fact/number in overlay {ov.get('overlay_id')}: {ov.get('label')}")
        if ov.get("type") == "verified_counter" and not ov.get("fact_source"):
            errors.append(f"verified_counter {ov.get('overlay_id')} lacks grounded fact_source")
        pbox = ov.get("placement_box")
        if not pbox or len(pbox) != 4:
            errors.append(f"Overlay {ov.get('overlay_id')} missing 4-element placement_box")
            continue
        x0, y0, x1, y1 = [float(v) for v in pbox]
        if x0 < SAFE_X_MIN or x1 > SAFE_X_MAX or y0 < SAFE_Y_MIN or y1 > SAFE_Y_MAX:
            errors.append(f"Overlay {ov.get('overlay_id')} box {pbox} outside safe box [{SAFE_X_MIN},{SAFE_Y_MIN},{SAFE_X_MAX},{SAFE_Y_MAX}]")
        if y1 > CAPTION_BAND_Y_MIN:
            errors.append(f"Overlay {ov.get('overlay_id')} intrudes on caption band y>{CAPTION_BAND_Y_MIN}: {pbox}")

    # Concurrent overlap & density check
    for i, oa in enumerate(overlays):
        conc = [oa]
        for j, ob in enumerate(overlays):
            if i >= j:
                continue
            if not (float(oa["end"]) <= float(ob["start"]) + 1e-4 or float(ob["end"]) <= float(oa["start"]) + 1e-4):
                conc.append(ob)
                if _boxes_overlap(tuple(oa["placement_box"]), tuple(ob["placement_box"]), pad=6.0):
                    errors.append(f"Concurrent overlay collision between {oa['overlay_id']} and {ob['overlay_id']}")
        if len(conc) > 2:
            errors.append(f"Simultaneous overlay count {len(conc)} > 2 around {oa['overlay_id']}")

    for ch in chunks:
        if float(ch["end"]) <= float(ch["start"]):
            errors.append(f"Invalid caption chunk time span {ch.get('chunk_id')}")
        bbox = ch.get("bbox", [100, 1365, 980, 1485])
        if bbox[0] < SAFE_X_MIN or bbox[2] > SAFE_X_MAX or bbox[3] > SAFE_Y_MAX:
            errors.append(f"Caption chunk {ch.get('chunk_id')} bbox {bbox} leaves safe margin")

    if errors:
        raise OverlaySafetyError("; ".join(errors))

    return {
        "ok": True,
        "overlay_count": len(overlays),
        "caption_chunk_count": len(chunks),
        "warnings": warnings,
    }


def build_editorial_timeline(
    parsed_script: Dict[str, Any],
    storyboard: Dict[str, Any],
    run_dir: Optional[Path] = None,
    caption_mode: str = "kinetic",
    callout_mode: str = "smart",
    prosody_plan: Optional[Dict[str, Any]] = None,
    verified_numbers: Optional[List[Dict[str, Any]]] = None,
    editorial_theme: str = "role-aware",
    curiosity_layer: str = "auto",
) -> Dict[str, Any]:
    """Assemble and persist `editorial_timeline.json`, `overlay_plan.json`, and `overlay_coverage.json`."""
    voice_info = parsed_script.get("voice") or {}
    words = list(voice_info.get("words") or [])
    total_dur = float(storyboard.get("total_duration_sec") or voice_info.get("vo_duration_sec") or 10.0)
    selected_skill = str(storyboard.get("selected_skill") or "zach-d-films")

    word_conf = str(voice_info.get("word_anchor_confidence") or "ESTIMATED")
    captions = plan_kinetic_captions(words, prosody_plan=prosody_plan, caption_mode=caption_mode)

    # Strict scope lock: rich dynamic callouts & multi-theme editorial engine operate strictly inside zach-d-films
    effective_callout_mode = callout_mode if selected_skill == "zach-d-films" else "off"
    effective_theme = editorial_theme if selected_skill == "zach-d-films" else "legacy"
    cands = (
        extract_editorial_focus_events(
            storyboard,
            parsed_script,
            verified_numbers=verified_numbers,
            editorial_theme=effective_theme,
            curiosity_layer=curiosity_layer,
        )
        if effective_callout_mode != "off"
        else []
    )
    # In role-aware mode, upgrade any legacy Boston/generic candidates seamlessly to semantic roles
    if effective_theme != "legacy" and cands:
        action_graph_ref = storyboard.get("story_action_graph") or {}
        nev_map = {e.get("narrative_event_id"): e for e in (action_graph_ref.get("narrative_events") or [])}
        shots_by_id = {s.get("shot_id"): s for s in (storyboard.get("shots") or [])}
        seen_locs: set[str] = set()
        upgraded: List[Dict[str, Any]] = []
        prior_r: List[Dict[str, Any]] = []
        seed_v = int(storyboard.get("seed", 42))
        for idx_c, c in enumerate(cands):
            if "style_id" in c and c.get("style_id") != "legacy":
                upgraded.append(c)
                prior_r.append(c)
                continue
            sh_ref = shots_by_id.get(c.get("shot_id"), {})
            nev_ref = nev_map.get(sh_ref.get("narrative_event_id"), {})
            c_lbl = str(c.get("label") or "")
            c_sub = str(c.get("sublabel") or "")
            c_type = str(c.get("type") or "")
            c_has_num = bool(c_type == "verified_counter" or c.get("fact_source") or re.search(r"\d", f"{c_lbl} {c_sub}"))
            beat_ctx = {
                "editorial_intent": nev_ref.get("editorial_intent"),
                "physical_action": nev_ref.get("physical_action") or sh_ref.get("physical_action"),
                "beat_role": nev_ref.get("beat_role") or sh_ref.get("beat_role"),
                "candidate_type": c_type,
                "candidate_label": c_lbl,
                "candidate_sublabel": c_sub,
                "narration_text": f"{c_lbl} {c_sub}".strip() or sh_ref.get("narration_text"),
                "factual_claim_id": nev_ref.get("factual_claim_id") if c_has_num else None,
            }
            erole, why_r = derive_editorial_role(beat_ctx, action_graph_ref)
            if "NORTH END" in c_lbl.upper() and "boston_1919" not in seen_locs:
                seen_locs.add("boston_1919")
                erole = EditorialRole.LOCATION_TIME
                why_r = "New historical Boston 1919 street setting establishment"
            elif erole == EditorialRole.CURIOSITY_HEADLINE and "/" not in c_lbl and len(c_lbl.split()) <= 3:
                if any(k in c_lbl.lower() for k in ("boston", "1919", "1940", "tacoma", "north end")):
                    erole = EditorialRole.LOCATION_TIME
                else:
                    erole = EditorialRole.EXPLANATION
            spec = select_overlay_variant(erole, prior_roles=prior_r, seed=seed_v + idx_c)
            c_up = {
                **c,
                "narrative_event_id": sh_ref.get("narrative_event_id"),
                "role": spec.role,
                "variant_id": spec.variant_id,
                "style_id": spec.style_id,
                "why_role": why_r,
                "pointer_shape": "none" if erole in (EditorialRole.LOCATION_TIME, EditorialRole.AFTERMATH_SOBER) else spec.pointer_shape,
                "font_size_1080": max(34, min(62, spec.font_size_1080)),
                "stroke_width": spec.stroke_width,
                "bg_shape": spec.bg_shape,
                "primary_color": spec.primary_color,
                "secondary_color": spec.secondary_color,
                "outline_color": spec.outline_color,
                "contrast_ratio_min": spec.contrast_ratio_min,
                "sfx_intent": spec.sfx_intent,
                "sound_intent": spec.sfx_intent,
            }
            upgraded.append(c_up)
            prior_r.append(c_up)
        # Ensure every candidate carries unified SD-RETENTION-04 causal/semantic region fields
        enriched_cands: List[Dict[str, Any]] = []
        for c in upgraded:
            sh_ref = shots_by_id.get(c.get("shot_id"), {})
            target_feat = str(
                c.get("target_feature_id")
                or c.get("target_semantic_id")
                or sh_ref.get("causal_feature_id")
                or c.get("anchor_id")
                or "primary_feature"
            )
            enriched_cands.append({
                **c,
                "causal_event_id": c.get("causal_event_id") or sh_ref.get("causal_event_id"),
                "narrative_claim_id": c.get("narrative_claim_id") or sh_ref.get("factual_claim_id") or f"claim_{c.get('shot_id') or 'overlay'}",
                "target_entity_id": c.get("target_entity_id") or sh_ref.get("effect_entity_id") or target_feat,
                "target_feature_id": target_feat,
                "proof_target_id": c.get("proof_target_id") or target_feat,
                "semantic_region_of_change": c.get("semantic_region_of_change") or sh_ref.get("semantic_region_of_change") or "primary_causal_zone",
                "why_this_overlay": c.get("why_this_overlay") or c.get("pointer_reason") or c.get("why_role") or "Binds claim directly to visible region of change",
            })
        cands = enriched_cands

    callouts_res = plan_3d_callouts(
        candidates=cands,
        total_duration=total_dur,
        callout_mode=effective_callout_mode,
        caption_chunks=captions,
    )

    timeline: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "selected_skill": selected_skill,
        "total_duration_sec": round(total_dur, 3),
        "fps": int(storyboard.get("fps", 30)),
        "caption_mode": caption_mode,
        "callout_mode": effective_callout_mode,
        "editorial_theme": effective_theme,
        "curiosity_layer": curiosity_layer,
        "word_anchor_confidence": word_conf,
        "word_alignment_method": voice_info.get("alignment_method", "unknown"),
        "voice_phrases": list((prosody_plan or voice_info.get("prosody_plan") or {}).get("phrases", [])),
        "caption_chunks": captions,
        "overlays": callouts_res["overlays"],
        "rejected_overlays": callouts_res.get("rejected", []),
        "free_screen_ratio": callouts_res.get("free_screen_ratio", 1.0),
    }
    val = validate_overlay_plan(timeline)
    timeline["validation"] = val

    # Enforce semantic design tokens & chronological reveal-order lock
    action_graph = storyboard.get("story_action_graph")
    if isinstance(action_graph, dict):
        rev_audit = validate_reveal_order(action_graph, timeline, words=words)
        if rev_audit["status"] == "FAIL":
            raise OverlaySafetyError("; ".join(rev_audit["violations"]))
        if effective_theme != "legacy" and timeline["overlays"]:
            rev2 = validate_reveal_lock(timeline["overlays"], action_graph.get("narrative_events") or [], words=words)
            if rev2["status"] == "FAIL":
                raise OverlaySafetyError("; ".join(rev2["violations"]))

    if effective_theme != "legacy" and timeline["overlays"]:
        validate_theme_semantics(timeline["overlays"], story=action_graph if isinstance(action_graph, dict) else None)

    coverage = {
        "schema_version": "sd-overlay-coverage-1",
        "selected_skill": selected_skill,
        "caption_mode": caption_mode,
        "callout_mode": effective_callout_mode,
        "editorial_theme": effective_theme,
        "caption_chunks_count": len(captions),
        "overlays_accepted": len(callouts_res["overlays"]),
        "overlays_rejected": len(callouts_res.get("rejected", [])),
        "free_screen_ratio": callouts_res.get("free_screen_ratio", 1.0),
        "overlays": callouts_res["overlays"],
    }

    if run_dir is not None:
        (run_dir / "editorial_timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "overlay_plan.json").write_text(json.dumps(callouts_res, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "overlay_coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
        emit_design_tokens_json(
            run_dir=run_dir,
            roles_plan=[
                {
                    "overlay_id": o.get("overlay_id"),
                    "narrative_event_id": o.get("narrative_event_id"),
                    "role": o.get("role"),
                    "variant_id": o.get("variant_id"),
                    "style_id": o.get("style_id"),
                    "why_role": o.get("why_role"),
                    "show_from": o.get("start"),
                    "show_until": o.get("end"),
                    "source_fact_ids": o.get("source_fact_ids", []),
                    "target_anchor_id": o.get("anchor_id"),
                }
                for o in callouts_res["overlays"]
            ],
            selected_skill=selected_skill,
        )

    return timeline



EDITORIAL_OVERLAY_RENDERER_JS = EDITORIAL_THEME_RENDERER_JS
