"""Cinematic Frame Composition & Negative-Space Solver (`SD-RETENTION-03` Workstream 5).

Plans focal regions, portrait 9:16 subject framing, negative space allocation above the
subject for display headlines/arrows, motivated wide/medium/macro scale shifts,
and spatial non-collision against faces, primary mechanisms, and lower captions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = "sd-cinematic-composition-1"


def _boxes_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float], pad: float = 12.0) -> bool:
    return not (
        a[2] + pad <= b[0]
        or b[2] + pad <= a[0]
        or a[3] + pad <= b[1]
        or b[3] + pad <= a[1]
    )


def design_frame_for_action(
    shot: Dict[str, Any],
    action_path: Optional[Dict[str, Any]] = None,
    subject_bound: Optional[Tuple[float, float, float, float]] = None,
    phone_safe_zone: Tuple[float, float, float, float] = (88.0, 170.0, 992.0, 1520.0),
    editorial_layout: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compute portrait 9:16 framing plan separating negative-space overlay band from hero action."""
    sid = str(shot.get("shot_id") or "")
    cam = shot.get("camera") or {}
    framing = str(shot.get("framing") or cam.get("framing") or "MS_Hero")
    act = str(shot.get("physical_action") or (action_path or {}).get("physical_action") or "action")
    # Default central subject occupancy band in 1080x1920 lower-mid portrait region [220..860, 520..1240]
    subj_box = subject_bound or (220.0, 520.0, 860.0, 1240.0)
    sx0, sy0, sx1, sy1 = phone_safe_zone

    # Upper negative space reserved for display headlines & facts cleanly above hero action band
    neg_space_box = [round(sx0 + 16, 1), round(sy0 + 12, 1), round(sx1 - 16, 1), round(min(485.0, subj_box[1] - 24.0), 1)]
    if neg_space_box[3] < neg_space_box[1] + 90.0:
        neg_space_box[3] = neg_space_box[1] + 180.0

    # Check whether any overlay boxes planned for this shot collide with protected face/subject core box
    face_protect = (300.0, 480.0, 780.0, 980.0) if "onlooker" in act or "retreat" in act or "react" in act else None
    collisions: List[str] = []
    for ov in (editorial_layout or []):
        pbox = tuple(float(v) for v in (ov.get("placement_box") or [0, 0, 0, 0]))
        if face_protect and _boxes_overlap(pbox, face_protect, pad=8.0) and ov.get("role") == "curiosity_headline":
            collisions.append(f"Hero headline {ov.get('overlay_id')} intrudes on protected actor/face zone")
        if pbox[3] > 1345.0:
            collisions.append(f"Overlay {ov.get('overlay_id')} intrudes into lower caption zone (y>{1345})")

    return {
        "shot_id": sid,
        "framing": framing,
        "physical_action": act,
        "subject_box_1080": list(subj_box),
        "negative_space_box_1080": neg_space_box,
        "face_protect_box_1080": list(face_protect) if face_protect else None,
        "collisions": collisions,
        "composition_ok": len(collisions) == 0,
    }


def plan_reveal_camera(
    story_events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Verify intentional wide/medium/macro progression arc across the narrative sequence."""
    arc: List[Dict[str, Any]] = []
    for idx, ev in enumerate(story_events):
        act = str(ev.get("physical_action") or "").lower()
        if idx == 0:
            tier = "macro_or_telephoto_hook"
        elif "establish" in act or "wide" in act or "overview" in act or "aftermath" in act:
            tier = "wide_establishing_context"
        elif "under" in act or "cutaway" in act or "seep" in act or "rupture" in act:
            tier = "close_mechanical_detail"
        else:
            tier = "medium_action_dynamics"
        arc.append({
            "narrative_event_id": ev.get("narrative_event_id"),
            "physical_action": act,
            "scale_tier": tier,
        })
    return arc


def score_visual_progression(
    shots: List[Dict[str, Any]],
    frames_composition: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Score narrative scale contrast, silhouette change, and spatial occupancy hygiene."""
    framings = [str(s.get("framing") or (s.get("camera") or {}).get("framing") or "") for s in shots]
    angles = [str(s.get("angle") or (s.get("camera") or {}).get("angle") or "") for s in shots]
    moves = [str(s.get("move") or (s.get("camera") or {}).get("movement") or (s.get("camera") or {}).get("move") or "") for s in shots]
    setups = [str(s.get("setup_type") or "") for s in shots]
    skies = [str((s.get("staging") or {}).get("sky_theme") or "default") for s in shots]

    issues: List[str] = []
    if len(shots) >= 5 and len(set(framings) | set(setups)) < 3:
        issues.append(f"Insufficient framing scale shifts across {len(shots)} shots (unique framings={len(set(framings))})")

    triplets = [(framings[i], angles[i], moves[i]) for i in range(len(shots))]
    for i in range(len(triplets) - 1):
        if any(triplets[i]) and triplets[i] == triplets[i + 1]:
            issues.append(f"Consecutive duplicate camera triplet {triplets[i]} at shot index {i}->{i+1}")

    for fc in frames_composition:
        issues.extend(fc.get("collisions") or [])

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "FAIL" if issues else "PASS",
        "shot_count": len(shots),
        "unique_framings_count": len(set(framings)),
        "unique_angles_count": len(set(angles)),
        "unique_moves_count": len(set(moves)),
        "unique_sky_contexts": len(set(skies)),
        "frames": frames_composition,
        "issues": issues,
    }


def write_composition_report(run_dir: Optional[Path], report: Dict[str, Any]) -> Dict[str, Any]:
    if run_dir is not None:
        (run_dir / "composition_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return report
