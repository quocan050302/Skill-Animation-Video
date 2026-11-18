"""Curiosity, Hero Headline & Smart Attention Pointer Planner (`SD-RETENTION-03` Workstream 2).

Selects at most 2 high-hierarchy hero headlines per 35-45s narrative, binds large
3D-tracked arrows/rings strictly to real physical feature anchors, enforces spoken-word
reveal gates (never spoiling answers prematurely), and scores editorial clarity via
explicit rule-based accounting rather than fabricated engagement claims.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .editorial_design_system import EditorialRole


class CuriosityPolicyError(ValueError):
    """Fail closed when hero headlines violate reveal locks, repeat verbatim, or lack anchors."""


def _norm(w: str) -> str:
    return re.sub(r"^[^\w\.]+|[^\w\.]+$", "", str(w).lower())


def _find_spoken_time(words: List[Dict[str, Any]], tokens: Tuple[str, ...], t_min: float, t_max: float) -> Optional[float]:
    for w in words:
        ws = float(w.get("s", 0.0))
        if ws < t_min - 0.15 or ws > t_max + 0.15:
            continue
        wn = _norm(w.get("w", ""))
        if any((wn == t or (len(t) >= 4 and t in wn)) for t in tokens):
            return ws
    return None


def find_curiosity_beats(
    script: str,
    story_actions: List[Dict[str, Any]],
    phrase_timings: Optional[List[Dict[str, Any]]] = None,
    max_headlines: int = 2,
) -> List[Dict[str, Any]]:
    """Select <=2 high-hierarchy curiosity headlines from hook and confirmed twist beats."""
    if not story_actions:
        return []

    full_low = str(script or "").lower()
    selected: List[Dict[str, Any]] = []

    # 1. Early Hook Headline (0..3s window, grounded without giving away late spoilers)
    first = story_actions[0]
    f_low = str(first.get("narration_text") or "").lower()
    hook_text = ""
    hook_target = str((first.get("required_anchors") or [""])[0] or "")
    hook_secondary: Optional[str] = None
    hook_ptr_shape = "impact_arrow"
    if "tacoma" in full_low or "galloping gertie" in full_low or ("bridge" in full_low and "twist" in full_low):
        hook_text = "THE ROAD / WAS MOVING!"
        hook_target = "bridge_midspan_twist"
        hook_ptr_shape = "impact_arrow"
    elif any(k in full_low for k in ("skyscraper", "sway in the wind", "tuned mass damper")):
        hook_text = "THE BUILDING / IS MOVING!"
        hook_target = hook_target or "rooftop_sway_apex"
        hook_secondary = "static_skyline_ref"
        hook_ptr_shape = "sway_bracket"
    elif "boston" in full_low and "molasses" in full_low:
        hook_text = "WATCH THE / ALLEYWALL!" if "alley" in f_low else "SOMETHING / SHOOK BOSTON"
        hook_target = hook_target or "street_hero_look"
    elif "bleed" in full_low and "window" in full_low:
        hook_text = "WHY THAT / TINY HOLE?"
        hook_target = hook_target or "middle_bleed_hole"
    else:
        # Neutral domain-generalized semantic headline templates (mechanism / contradiction / detail)
        if any(k in f_low for k in ("despite", "without", "even though", "but ", "impossible", "quiet")):
            hook_text = "HIDDEN / MECHANISM"
        elif any(k in f_low for k in ("damage", "fail", "crack", "snap", "collapse", "overload")):
            hook_text = "CRITICAL / STRESS POINT"
        else:
            toks = [t for t in re.findall(r"[A-Za-z0-9']+", str(first.get("narration_text") or "")) if len(t) >= 3]
            if len(toks) >= 4:
                hook_text = f"{toks[0].upper()} {toks[1].upper()} / {toks[2].upper()} {toks[3].upper()}?"
            elif toks:
                hook_text = "HOW IT / ACTUALLY WORKS"
            else:
                hook_text = "HOW DID / IT HAPPEN?"

    selected.append({
        "beat_index": 0,
        "narrative_event_id": first.get("narrative_event_id"),
        "role": EditorialRole.CURIOSITY_HEADLINE.value,
        "headline_kind": "hook",
        "label": hook_text,
        "target_anchor_id": hook_target or "subject_primary_feature",
        "secondary_anchor_id": hook_secondary,
        "pointer_shape": hook_ptr_shape,
        "start_hint": round(max(0.15, float(first.get("start_sec", 0.0)) + 0.15), 3),
        "end_hint": round(min(float(first.get("end_sec", 3.0)) - 0.15, float(first.get("start_sec", 0.0)) + 2.25), 3),
        "spoiler_risk": "guarded",
        "why_selected": "Opening curiosity hook guides viewer eye immediately without revealing ending",
    })

    # 2. Twist / Escalation Hero Headline (strictly when real escalation happens)
    if max_headlines >= 2 and len(story_actions) >= 4:
        twist_idx = None
        for idx, ev in enumerate(story_actions[1:], start=1):
            ev_low = str(ev.get("narration_text") or "").lower()
            act = str(ev.get("physical_action") or "").lower()
            intent = str(ev.get("editorial_intent") or "").lower()
            if intent == "twist_escalation" or any(
                k in act or k in ev_low
                for k in ("started twisting", "violent twist", "gave way", "rupture", "torsion", "fail-safe", "backup", "opposite phase", "counterphase")
            ):
                twist_idx = idx
                break
        if twist_idx is not None:
            tw = story_actions[twist_idx]
            tw_low = str(tw.get("narration_text") or "").lower()
            tw_act = str(tw.get("physical_action") or "").lower()
            tw_secondary: Optional[str] = None
            tw_ptr = "impact_arrow"
            if "twist" in tw_low or "torsion" in tw_act:
                tw_label = "THEN IT / STARTED TWISTING"
                tw_secondary = "deck_twist_edge_r"
                tw_ptr = "torsion_bracket"
            elif "counterphase" in tw_act or "opposite" in tw_low:
                tw_label = "OPPOSITE / PHASE SWING!"
                tw_secondary = "counterphase_tower_frame"
                tw_ptr = "torsion_bracket"
            elif "gave way" in tw_low or "rupture" in tw_act:
                tw_label = "THEN THE / SEAM BLEW"
            else:
                tw_label = "KEY / TURNING POINT"
            tw_target = str((tw.get("required_anchors") or [""])[0] or "")
            selected.append({
                "beat_index": twist_idx,
                "narrative_event_id": tw.get("narrative_event_id"),
                "role": EditorialRole.CURIOSITY_HEADLINE.value,
                "headline_kind": "twist",
                "label": tw_label,
                "target_anchor_id": tw_target or "bridge_midspan_twist",
                "secondary_anchor_id": tw_secondary,
                "pointer_shape": tw_ptr,
                "start_hint": round(float(tw.get("start_sec", 0.0)) + 0.12, 3),
                "end_hint": round(min(float(tw.get("end_sec", 20.0)) - 0.14, float(tw.get("start_sec", 0.0)) + 2.30), 3),
                "spoiler_risk": "authorized_twist",
                "why_selected": "Twist hero headline fires alongside confirmed structural escalation",
            })

    return selected[:max_headlines]


def plan_attention_pointer(
    beat: Dict[str, Any],
    scene_entity_registry: Optional[Dict[str, Any]] = None,
    camera_path: Optional[Dict[str, Any]] = None,
    geometry_anchors: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Select an explicit physical feature anchor and non-occluding pointer geometry."""
    anchors = list(beat.get("required_anchors") or [])
    anchor_id = str(beat.get("target_anchor_id") or (anchors[0] if anchors else "")).strip()
    reg_props = (scene_entity_registry or {}).get("props") or {}

    if (not anchor_id or anchor_id in ("stage_center", "default")) and geometry_anchors:
        for k in geometry_anchors:
            if k not in ("default", "stage_center"):
                anchor_id = str(k)
                break
    if (not anchor_id or anchor_id in ("stage_center", "default")) and reg_props:
        for pk in reg_props:
            if pk not in ("stage_center", "default"):
                anchor_id = str(pk)
                break

    if not anchor_id or anchor_id in ("stage_center", "default"):
        raise CuriosityPolicyError(
            f"N04: Beat {beat.get('narrative_event_id')} has no specific physical 3D anchor (got '{anchor_id}')"
        )

    role = str(beat.get("role") or EditorialRole.EXPLANATION.value)
    explicit_ptr = beat.get("pointer_shape")
    secondary_anchor = beat.get("secondary_anchor_id")
    if explicit_ptr:
        ptr = str(explicit_ptr)
    elif role == EditorialRole.CURIOSITY_HEADLINE.value or role == EditorialRole.WARNING_DANGER.value:
        ptr = "torsion_bracket" if (role == EditorialRole.WARNING_DANGER.value and anchor_id in ("bridge_midspan_twist", "deck_twist_edge_l")) else "impact_arrow"
    elif role == EditorialRole.VERIFIED_FACT.value:
        ptr = "mini_fact_tag"
    elif role == EditorialRole.AFTERMATH_SOBER.value or role == EditorialRole.LOCATION_TIME.value:
        ptr = "none"
    else:
        ptr = "curved_leader"

    # Grounded semantic target metadata (R2.5 Pointer Meaning)
    target_region_world = list(beat.get("target_region_world") or [0.0, 2.0, 0.0])
    if geometry_anchors and isinstance(geometry_anchors.get(anchor_id), dict):
        ga = geometry_anchors[anchor_id]
        if isinstance(ga.get("world_pos"), list):
            target_region_world = list(ga["world_pos"])
    mesh_map = {
        "bridge_midspan_twist": ["intact_roadway_ribbon", "left_curb_ribbon", "right_curb_ribbon"],
        "deck_twist_edge_l": ["left_curb_ribbon", "left_girder_ribbon"],
        "deck_twist_edge_r": ["right_curb_ribbon", "right_girder_ribbon"],
        "plate_girder_windward": ["left_girder_ribbon", "wind_vortex_ribbons"],
        "collapse_break_seam": ["falling_center_chunks", "break_seam_fracture"],
        "rooftop_sway_apex": ["hero_tower_crown", "hero_tower_mullions"],
        "plumb_drift_tip": ["hero_tower_crown", "red_plumb_reference_mast"],
        "windward_facade_vortex": ["wind_vortex_ribbons", "hero_tower_tiers"],
        "damper_pendulum_sphere": ["tmd_sphere", "hydraulic_pistons"],
        "counterphase_tower_frame": ["penthouse_frame", "opposing_force_bars"],
        "damped_tower_top": ["damped_tower", "undamped_tower"],
    }
    target_meshes = mesh_map.get(anchor_id, [anchor_id])
    pointer_reason = str(
        beat.get("pointer_reason")
        or (
            "Highlights opposed left/right deck torsion displacement across whole center span"
            if anchor_id in ("bridge_midspan_twist", "deck_twist_edge_l")
            else ("Highlights lateral roof sway relative to fixed vertical reference"
                  if anchor_id in ("rooftop_sway_apex", "plumb_drift_tip")
                  else f"Draws viewer eye directly to physical feature `{anchor_id}`")
        )
    )

    # Alternate box/pointer side dynamically away from lower caption zone & center obstruction
    idx = int(beat.get("beat_index", 0) or 0)
    preferred_side = "left" if (idx % 2 == 0) else "right"
    if role == EditorialRole.CURIOSITY_HEADLINE.value:
        slot_box = [104, 210, 976, 448] if idx == 0 else [104, 230, 976, 468]
    elif role == EditorialRole.LOCATION_TIME.value:
        slot_box = [104, 185, 640, 275]
    elif role == EditorialRole.AFTERMATH_SOBER.value:
        slot_box = [116, 235, 964, 345]
    elif preferred_side == "left":
        slot_box = [108, 300 + (idx % 3) * 58, 536, 412 + (idx % 3) * 58]
    else:
        slot_box = [544, 300 + (idx % 3) * 58, 972, 412 + (idx % 3) * 58]

    return {
        "anchor_id": anchor_id,
        "secondary_anchor_id": secondary_anchor,
        "target_semantic_id": anchor_id,
        "target_mesh_ids": target_meshes,
        "target_region_world": target_region_world,
        "target_region_screen": None,
        "target_motion_vector": [0.0, 0.0],
        "is_feature_visible": True,
        "pointer_reason": pointer_reason,
        "do_not_pointer_to_this_if_target_ambiguous": True,
        "pointer_shape": ptr,
        "preferred_side": preferred_side,
        "placement_box": slot_box,
        "avoid_caption_y": 1350,
    }


def score_editorial_value(
    candidate: Dict[str, Any],
    beat: Dict[str, Any],
    story_actions: List[Dict[str, Any]],
    prior_candidates: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Transparent rule-engine scoring editorial value without predictive hype claims."""
    prior = list(prior_candidates or [])
    label = str(candidate.get("label") or "").strip()
    low = label.lower()
    role = str(candidate.get("role") or "")

    relevance = 1.0 if candidate.get("anchor_id") else 0.2
    new_info = 1.0 if not any(str(p.get("label") or "").lower() == low for p in prior) else 0.0
    words_cnt = len(label.replace("/", " ").split())
    clarity = 1.0 if 1 <= words_cnt <= 7 else 0.4
    contrast = 1.0 if role in (EditorialRole.CURIOSITY_HEADLINE.value, EditorialRole.VERIFIED_FACT.value) else 0.8

    clutter_pen = 0.35 * sum(
        1 for p in prior
        if not (float(candidate.get("end", 0)) <= float(p.get("start", 0)) + 0.05 or float(p.get("end", 0)) <= float(candidate.get("start", 0)) + 0.05)
    )
    spoiler_pen = 1.5 if candidate.get("early_spoiler_violation") else 0.0
    rep_pen = 0.8 if prior and prior[-1].get("label", "").lower() == low else 0.0
    masking_pen = 0.6 if (candidate.get("placement_box") or [0, 0, 0, 0])[3] > 1345 else 0.0

    total = round(relevance + new_info + clarity + contrast - clutter_pen - spoiler_pen - rep_pen - masking_pen, 3)
    return {
        "score": total,
        "rules": {
            "relevance": relevance,
            "new_information": new_info,
            "clarity": clarity,
            "semantic_contrast": contrast,
            "clutter_penalty": clutter_pen,
            "spoiler_penalty": spoiler_pen,
            "repetition_penalty": rep_pen,
            "masking_penalty": masking_pen,
        },
        "keep": total >= 1.5 and spoiler_pen == 0.0,
    }


def bind_pointer_and_headline_timing(
    candidates: List[Dict[str, Any]],
    words: List[Dict[str, Any]],
    story_actions: List[Dict[str, Any]],
    contact_schedule: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Bind headline and pointer onset to real contact action frames and spoken word timings."""
    out: List[Dict[str, Any]] = []
    ev_by_id = {e.get("narrative_event_id"): e for e in story_actions if e.get("narrative_event_id")}
    contacts_by_ev = {c.get("narrative_event_id"): c for c in (contact_schedule or []) if c.get("narrative_event_id")}

    for cand in candidates:
        c = dict(cand)
        ev = ev_by_id.get(c.get("narrative_event_id"), {})
        ev_start = float(ev.get("start_sec", c.get("start", 0.0)))
        ev_end = float(ev.get("end_sec", c.get("end", ev_start + 2.0)))
        rev_sec = ev.get("reveal_after_sec")

        contact = contacts_by_ev.get(c.get("narrative_event_id"))
        if contact and contact.get("hit_time_sec") is not None:
            hit_t = float(contact["hit_time_sec"])
            start_t = max(ev_start, hit_t - 0.08)
        else:
            start_t = float(c.get("start", ev_start + 0.15))

        if rev_sec is not None:
            start_t = max(start_t, float(rev_sec))

        end_t = min(ev_end - 0.12, max(start_t + 0.90, float(c.get("end", start_t + 2.2))))
        if end_t - start_t >= 0.75:
            c["start"] = round(start_t, 3)
            c["end"] = round(end_t, 3)
            c["reveal_sfx_at_sec"] = round(start_t, 3)
            out.append(c)
    return out


def validate_reveal_lock(
    overlays: List[Dict[str, Any]],
    story_actions: List[Dict[str, Any]],
    words: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Fail closed if collapse/twist/spoiler headline fires ahead of authorized reveal timing."""
    wlist = list(words or [])
    violations: List[str] = []

    collapse_t = None
    twist_t = None
    for ev in story_actions:
        act = str(ev.get("physical_action") or "").lower()
        low = str(ev.get("narration_text") or "").lower()
        st = float(ev.get("start_sec", 0.0))
        if twist_t is None and ("torsion" in act or "started twisting" in low or "violent twist" in low):
            twist_t = st
        if collapse_t is None and ("collapse" in act or "broke free" in low or "plunged" in low):
            collapse_t = st

    if wlist:
        sp_col = _find_spoken_time(wlist, ("collapsed", "broke", "plunged"), 0.0, 999.0)
        if sp_col is not None:
            collapse_t = min(collapse_t, sp_col) if collapse_t is not None else sp_col
        sp_tw = _find_spoken_time(wlist, ("twisting", "twist"), 0.0, 999.0)
        if sp_tw is not None:
            twist_t = min(twist_t, sp_tw) if twist_t is not None else sp_tw

    seen_headlines: List[Tuple[str, float]] = []
    for ov in overlays:
        st = float(ov.get("start", 0.0))
        lbl_low = f"{ov.get('label', '')} {ov.get('sublabel', '')}".lower()
        role = str(ov.get("role") or "")

        if collapse_t is not None and any(k in lbl_low for k in ("collapsed", "broke free", "plunged")) and st + 0.35 < collapse_t:
            violations.append(
                f"N09: Early collapse reveal '{ov.get('label')}' at t={st:.2f}s before collapse t={collapse_t:.2f}s"
            )
        if twist_t is not None and "started twisting" in lbl_low and st + 0.40 < twist_t:
            violations.append(
                f"N09: Early twist headline '{ov.get('label')}' at t={st:.2f}s before twist beat t={twist_t:.2f}s"
            )

        if role == EditorialRole.CURIOSITY_HEADLINE.value:
            for prev_l, prev_t in seen_headlines:
                if prev_l == lbl_low and abs(st - prev_t) < 5.0:
                    violations.append(
                        f"N10: Duplicate headline '{ov.get('label')}' repeated within {abs(st - prev_t):.2f}s"
                    )
            seen_headlines.append((lbl_low, st))

    return {
        "status": "FAIL" if violations else "PASS",
        "violations": violations,
    }
