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


SCHEMA_VERSION = "sd-editorial-timeline-1"

SAFE_X_MIN = 100
SAFE_X_MAX = 980
SAFE_Y_MIN = 220
SAFE_Y_MAX = 1500
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
) -> List[Dict[str, Any]]:
    """Derive visually grounded editorial callout candidates directly from storyboard anchors & verified facts."""
    shots = list(storyboard.get("shots", []))
    words = list((parsed_script.get("voice") or {}).get("words", []))
    candidates: List[Dict[str, Any]] = []
    fact_nums = list(verified_numbers or [])

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

        # Anchor-timed onset aligned to actual spoken keyword in shot if found
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

        # Build concise domain-specific callouts aligned strictly to visible 3D mechanisms
        rev_floor = float(shot.get("reveal_after_sec") or 0.0)
        anchor_t = round(max(anchor_t, rev_floor), 3)
        if gen.startswith("zach3d:boston_"):
            def _word_t(toks: Tuple[str, ...], fallback: float) -> float:
                for sw in shot_words:
                    cw = re.sub(r"[^\w\.\-]", "", str(sw["w"]).lower())
                    if any(cw == t or (len(t) >= 4 and t in cw) for t in toks):
                        return round(max(st + 0.08, rev_floor, float(sw["s"])), 3)
                return round(max(st + 0.12, rev_floor, fallback), 3)

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
                t_on = _word_t(("molasses",), anchor_t)
                if en - t_on >= 0.70:
                    candidates.append({
                        "shot_index": si, "shot_id": shot_id, "type": "focus_ring",
                        "anchor_id": "molasses_reveal_crest",
                        "label": "RAW MOLASSES SURGE",
                        "sublabel": "Dense industrial sweetener",
                        "start": t_on, "end": round(min(en - 0.12, t_on + 2.1), 3),
                        "preferred_side": "right", "accent_color": "#f59e0b", "priority": 1, "verified": True,
                    })
            elif gen == "zach3d:boston_tank_leak_stage":
                t_on = _word_t(("leaking", "years"), anchor_t)
                if en - t_on >= 0.75:
                    candidates.append({
                        "shot_index": si, "shot_id": shot_id, "type": "tracked_arrow",
                        "anchor_id": "tank_seam_drip",
                        "label": "CHRONIC SEAM LEAKS",
                        "sublabel": "Documented prior to failure",
                        "start": t_on, "end": round(min(en - 0.12, t_on + 2.25), 3),
                        "preferred_side": "left", "accent_color": "#f59e0b", "priority": 1, "verified": True,
                    })
            elif gen == "zach3d:boston_tank_rupture_stage":
                t_on = _word_t(("way", "afternoon", "gave", "walls"), anchor_t)
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
                else:
                    t_on = _word_t(("2.3", "million", "gallons"), anchor_t)
                    if en - t_on >= 0.60:
                        candidates.append({
                            "shot_index": si, "shot_id": shot_id, "type": "tracked_arrow",
                            "anchor_id": "wave_front_crest",
                            "label": "~2.3M GALLONS",
                            "sublabel": "Released across North End",
                            "start": t_on, "end": round(min(en - 0.12, t_on + 2.30), 3),
                            "preferred_side": "left", "accent_color": "#fbbf24", "priority": 1, "verified": True,
                            "fact_source": "Boston.gov / BPL ~2.3 million gallon tank volume estimate",
                        })
            elif gen == "zach3d:boston_elevated_rail_impact_stage":
                t_on = _word_t(("smashed", "buildings", "trapped"), anchor_t)
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
            elif gen == "zach3d:boston_engineering_cutaway_stage":
                t_on = _word_t(("construction", "engineers", "steel"), anchor_t)
                if en - t_on >= 0.75:
                    candidates.append({
                        "shot_index": si, "shot_id": shot_id, "type": "tracked_arrow",
                        "anchor_id": "lap_joint_defect",
                        "label": "THIN STEEL & RIVETS",
                        "sublabel": "Post-1919 code overhaul",
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
            "type": ctype,
            "anchor_id": str(cand.get("anchor_id") or "stage_center"),
            "label": str(cand.get("label") or ""),
            "sublabel": str(cand.get("sublabel") or ""),
            "start": st,
            "end": en,
            "preferred_side": cand.get("preferred_side", "right"),
            "placement_box": [round(float(x), 1) for x in pbox],
            "accent_color": cand.get("accent_color", "#38bdf8"),
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
    free_ticks = 0
    for k in range(sample_n):
        t = (k + 0.5) / 2.0
        active = any(o["start"] <= t <= o["end"] for o in accepted)
        if not active:
            free_ticks += 1
    free_ratio = free_ticks / float(sample_n)
    if len(accepted) > 2 and free_ratio < 0.18:
        # Drop lowest-priority tail overlay cleanly rather than suffocating screen
        accepted = accepted[:-1]

    return {
        "mode": mode,
        "overlays": accepted,
        "rejected": rejected,
        "free_screen_ratio": round(free_ticks / float(sample_n), 3),
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
) -> Dict[str, Any]:
    """Assemble and persist `editorial_timeline.json`, `overlay_plan.json`, and `overlay_coverage.json`."""
    voice_info = parsed_script.get("voice") or {}
    words = list(voice_info.get("words") or [])
    total_dur = float(storyboard.get("total_duration_sec") or voice_info.get("vo_duration_sec") or 10.0)
    selected_skill = str(storyboard.get("selected_skill") or "zach-d-films")

    word_conf = str(voice_info.get("word_anchor_confidence") or "ESTIMATED")
    captions = plan_kinetic_captions(words, prosody_plan=prosody_plan, caption_mode=caption_mode)

    # Strict scope lock: rich dynamic callouts operate only inside zach-d-films unless explicit
    effective_callout_mode = callout_mode if selected_skill == "zach-d-films" else "off"
    cands = extract_editorial_focus_events(storyboard, parsed_script, verified_numbers=verified_numbers) if effective_callout_mode != "off" else []
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

    # Enforce chronological reveal-order lock whenever story_action_graph is present
    action_graph = storyboard.get("story_action_graph")
    if isinstance(action_graph, dict):
        rev_audit = validate_reveal_order(action_graph, timeline, words=words)
        if rev_audit["status"] == "FAIL":
            raise OverlaySafetyError("; ".join(rev_audit["violations"]))

    coverage = {
        "schema_version": "sd-overlay-coverage-1",
        "selected_skill": selected_skill,
        "caption_mode": caption_mode,
        "callout_mode": effective_callout_mode,
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

    return timeline


EDITORIAL_OVERLAY_RENDERER_JS = r"""
// Deterministic SVG + Kinetic DOM Editorial Overlay Renderer (ZDF Only).
// Uses zero wall-clock CSS transitions and hides tracked annotations immediately
// whenever an anchor goes offscreen or fails 3D line-of-sight occlusion checks.

const NS = 'http://www.w3.org/2000/svg';
const SAFE = { x0: 100, x1: 980, y0: 220, y1: 1500, capY0: 1335 };

function clamp(x, lo, hi) {
  return Math.max(lo, Math.min(hi, x));
}

function easeOutCubic(u) {
  const x = clamp(u, 0, 1);
  return 1 - Math.pow(1 - x, 3);
}

function el(tag, attrs = {}) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  return node;
}

export class EditorialOverlayController {
  constructor(stageEl, capEl, timeline) {
    this.stageEl = stageEl;
    this.capEl = capEl;
    this.timeline = timeline || { caption_mode: 'plain', callout_mode: 'off', caption_chunks: [], overlays: [] };
    this.svg = document.createElementNS(NS, 'svg');
    this.svg.setAttribute('viewBox', '0 0 1080 1920');
    this.svg.setAttribute('width', '1080');
    this.svg.setAttribute('height', '1920');
    this.svg.style.cssText = 'position:absolute;inset:0;width:1080px;height:1920px;pointer-events:none;z-index:12;overflow:visible;';
    this.stageEl.appendChild(this.svg);
    this.lastTelemetry = { overlays: [], caption: null, active_count: 0 };
  }

  renderAtTime(t, anchorsMap = {}) {
    while (this.svg.firstChild) this.svg.removeChild(this.svg.firstChild);

    const tl = this.timeline || {};
    const chunks = tl.caption_chunks || [];
    const capMode = String(tl.caption_mode || 'kinetic');

    // 1. Render kinetic or plain captions deterministically with non-crowded flex layout
    const activeChunk = chunks.find(c => t >= c.start && t <= c.end) || null;
    let capTel = { text: '', active_word: '', chunk_id: null, mode: capMode, caption_layout: null };
    if (this.capEl) {
      this.capEl.style.display = 'flex';
      this.capEl.style.flexWrap = 'wrap';
      this.capEl.style.justifyContent = 'center';
      this.capEl.style.alignItems = 'baseline';
      this.capEl.style.columnGap = '0.40em';
      this.capEl.style.rowGap = '0.20em';
    }
    if (activeChunk && this.capEl) {
      if (capMode === 'plain') {
        this.capEl.textContent = activeChunk.text || '';
        capTel.text = activeChunk.text || '';
        capTel.chunk_id = activeChunk.chunk_id;
      } else {
        this.capEl.innerHTML = '';
        const ws = activeChunk.words || [];
        let activeW = '';
        const spanEls = [];
        ws.forEach((wObj) => {
          const span = document.createElement('span');
          span.textContent = String(wObj.w || '');
          const isCur = t >= wObj.s && t <= (wObj.e + 0.04);
          const past = t > wObj.e + 0.04;
          let scale = 1.0;
          if (isCur) {
            const p = clamp((t - wObj.s) / Math.max(0.06, wObj.e - wObj.s), 0, 1);
            scale = 1.0 + 0.05 * Math.sin(Math.min(1, p * 2.0) * Math.PI * 0.5);
            activeW = wObj.w || '';
          }
          const isEmp = Boolean(wObj.is_emphasis);
          const color = isCur
            ? (isEmp ? (wObj.accent_color || '#fbbf24') : '#ffffff')
            : (isEmp ? (wObj.accent_color || '#fbbf24') : (past ? 'rgba(241,245,249,0.92)' : 'rgba(226,232,240,0.82)'));
          span.style.display = 'inline-block';
          span.style.transform = `scale(${scale.toFixed(3)})`;
          span.style.transformOrigin = 'center bottom';
          span.style.color = color;
          span.style.margin = '0 2px';
          span.style.padding = '0 4px';
          if (isEmp && isCur) {
            span.style.textDecoration = 'underline';
            span.style.textDecorationColor = wObj.accent_color || '#fbbf24';
            span.style.textUnderlineOffset = '8px';
            span.style.textDecorationThickness = '4px';
          }
          this.capEl.appendChild(span);
          spanEls.push(span);
        });
        // Real DOM getBoundingClientRect telemetry proving zero adjacent word collisions
        const rects = spanEls.map(elNode => elNode.getBoundingClientRect());
        let minGap = 999.0;
        let overlaps = 0;
        const rowYs = [];
        for (let rIdx = 0; rIdx < rects.length; rIdx++) {
          const rA = rects[rIdx];
          if (!rowYs.some(ry => Math.abs(ry - rA.top) < 12)) rowYs.push(rA.top);
          if (rIdx + 1 < rects.length) {
            const rB = rects[rIdx + 1];
            if (Math.abs(rA.top - rB.top) < Math.max(10, rA.height * 0.45)) {
              const gap = rB.left - rA.right;
              minGap = Math.min(minGap, gap);
              if (gap < 1.5) overlaps += 1;
            }
          }
        }
        const capRect = this.capEl.getBoundingClientRect();
        capTel.text = activeChunk.text || '';
        capTel.active_word = activeW;
        capTel.chunk_id = activeChunk.chunk_id;
        capTel.caption_layout = {
          word_count: spanEls.length,
          min_word_gap_px: minGap < 990 ? Number(minGap.toFixed(2)) : null,
          word_overlap_count: overlaps,
          row_count: rowYs.length,
          in_safe_area: capRect.left >= 80 && capRect.right <= 1000 && capRect.bottom <= 1540,
        };
      }
    } else if (this.capEl) {
      this.capEl.textContent = '';
    }

    // 2. Render smart tracked 3D callouts / focus rings / verified counters
    const overlays = tl.overlays || [];
    const ovTel = [];
    let visibleCount = 0;

    if (String(tl.callout_mode || 'smart') !== 'off') {
      for (const ov of overlays) {
        if (t < ov.start || t > ov.end) continue;
        const enter = easeOutCubic((t - ov.start) / 0.22);
        const exit = easeOutCubic((ov.end - t) / 0.20);
        const alpha = clamp(Math.min(enter, exit), 0, 1);

        const anc = anchorsMap[ov.anchor_id] || anchorsMap['default'] || null;
        const requiresTrack = ov.type === 'focus_ring' || ov.type === 'tracked_arrow';

        let anchorPx = null;
        let visible = true;
        let hiddenReason = null;

        if (requiresTrack) {
          if (!anc || !anc.in_front) {
            visible = false;
            hiddenReason = 'behind_or_missing_anchor';
          } else if (anc.occluded) {
            visible = false;
            hiddenReason = 'occluded_3d_geometry';
          } else {
            const px = anc.u * 1080;
            const py = anc.v * 1920;
            if (px < 54 || px > 1026 || py < 120 || py > 1650) {
              visible = false;
              hiddenReason = 'offscreen';
            } else {
              anchorPx = [Number(px.toFixed(1)), Number(py.toFixed(1))];
            }
          }
        }

        if (!visible || alpha <= 0.02) {
          ovTel.push({
            overlay_id: ov.overlay_id,
            type: ov.type,
            anchor_id: ov.anchor_id,
            visible: false,
            hidden_reason: hiddenReason || 'fade_zero',
            anchor_px: anchorPx,
            in_safe_area: true,
          });
          continue;
        }

        visibleCount += 1;
        const g = el('g', { opacity: alpha.toFixed(3) });
        const accent = ov.accent_color || '#38bdf8';

        // Box placed cleanly inside safe box and strictly above caption band
        let [bx0, by0, bx1, by1] = ov.placement_box || [590, 320, 960, 416];
        // Dynamically steer label away if projected 3D anchor sits near default label box
        if (anchorPx) {
          const [ax, ay] = anchorPx;
          if (ax >= bx0 - 55 && ax <= bx1 + 55 && ay >= by0 - 55 && ay <= by1 + 55) {
            const w = bx1 - bx0;
            const h = by1 - by0;
            bx0 = ax > 540 ? SAFE.x0 + 18 : SAFE.x1 - w - 18;
            bx1 = bx0 + w;
            by0 = clamp(ay - 220, SAFE.y0 + 12, SAFE.capY0 - h - 24);
            by1 = by0 + h;
          }
        }
        const bw = bx1 - bx0;
        const bh = by1 - by0;

        if (ov.type === 'focus_ring' && anchorPx) {
          const [ax, ay] = anchorPx;
          const rOuter = 58 + (1 - enter) * 26;
          g.appendChild(el('circle', {
            cx: ax, cy: ay, r: (rOuter * 0.72).toFixed(1),
            fill: 'none', stroke: accent, 'stroke-width': '5.5',
            'stroke-dasharray': `${(2 * Math.PI * rOuter * 0.72 * enter).toFixed(1)} 400`,
          }));
          g.appendChild(el('circle', {
            cx: ax, cy: ay, r: (rOuter * 1.02).toFixed(1),
            fill: 'none', stroke: '#ffffff', 'stroke-width': '2.5', opacity: '0.72',
          }));
        }

        if ((ov.type === 'tracked_arrow' || ov.type === 'focus_ring') && anchorPx && ov.label) {
          const [ax, ay] = anchorPx;
          const sx = bx0 + bw * 0.5 < ax ? bx1 : bx0;
          const sy = by0 + bh * 0.5;
          const dx = ax - sx;
          const dy = ay - sy;
          const len = Math.max(1, Math.hypot(dx, dy));
          const ux = dx / len;
          const uy = dy / len;
          const tx = ax - ux * 44;
          const ty = ay - uy * 44;
          const mx = (sx + tx) * 0.5;
          const pathD = `M ${sx.toFixed(1)} ${sy.toFixed(1)} Q ${mx.toFixed(1)} ${sy.toFixed(1)} ${tx.toFixed(1)} ${ty.toFixed(1)}`;
          g.appendChild(el('path', {
            d: pathD, fill: 'none', stroke: accent, 'stroke-width': '5',
            'stroke-linecap': 'round', opacity: '0.96',
          }));
          g.appendChild(el('circle', { cx: tx.toFixed(1), cy: ty.toFixed(1), r: '6.5', fill: accent }));
        }

        if (ov.label) {
          g.appendChild(el('rect', {
            x: bx0, y: by0, width: bw, height: bh, rx: 16,
            fill: 'rgba(10, 16, 28, 0.88)', stroke: accent, 'stroke-width': '3',
          }));
          const bar = el('rect', {
            x: bx0 + 11, y: by0 + 14, width: 6.5, height: Math.max(20, bh - 28), rx: 3.5, fill: accent,
          });
          g.appendChild(bar);

          const titleText = ov.type === 'verified_counter' && ov.target_value != null
            ? `${ov.prefix || ''}${Math.round(Number(ov.target_value) * enter)}${ov.suffix || ''}`
            : ov.label;
          const tEl = el('text', {
            x: bx0 + 30, y: by0 + (ov.sublabel ? 45 : bh * 0.58),
            fill: '#f8fafc', 'font-family': 'Cap, sans-serif', 'font-weight': '800', 'font-size': '32',
          });
          tEl.textContent = titleText;
          g.appendChild(tEl);

          if (ov.sublabel) {
            const sEl = el('text', {
              x: bx0 + 30, y: by0 + 82,
              fill: '#e2e8f0', 'font-family': 'Cap, sans-serif', 'font-weight': '600', 'font-size': '22',
            });
            sEl.textContent = ov.sublabel;
            g.appendChild(sEl);
          }
        }

        this.svg.appendChild(g);
        const inSafe = bx0 >= SAFE.x0 && bx1 <= SAFE.x1 && by0 >= SAFE.y0 && by1 <= SAFE.capY0;
        const gRect = g.getBoundingClientRect ? g.getBoundingClientRect() : null;
        const domRendered = Boolean(this.svg.contains(g) && g.childElementCount > 0 && (!gRect || (gRect.width > 1 && gRect.height > 1)));
        ovTel.push({
          overlay_id: ov.overlay_id,
          type: ov.type,
          anchor_id: ov.anchor_id,
          label: ov.label || '',
          visible: true,
          dom_rendered: domRendered,
          alpha: Number(alpha.toFixed(3)),
          hidden_reason: null,
          anchor_px: anchorPx,
          label_bbox: [Number(bx0.toFixed(1)), Number(by0.toFixed(1)), Number(bx1.toFixed(1)), Number(by1.toFixed(1))],
          in_safe_area: inSafe,
        });
      }
    }

    this.lastTelemetry = { overlays: ovTel, caption: capTel, active_count: visibleCount };
    return this.lastTelemetry;
  }

  getOverlayTelemetry() {
    return this.lastTelemetry;
  }
}
"""
