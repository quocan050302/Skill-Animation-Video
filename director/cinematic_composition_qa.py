"""Post-Render Cinematic Composition & Collision QA Gate (`SD-RETENTION-03` Workstream 5).

Verifies rendered DOM/WebGL telemetry (`raw_render_telemetry.json`), decoded overlay vs
caption/face separation, scale variety, and safe margins on mobile 320/360/390 & 1080p.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .cinematic_composition import (
    design_frame_for_action,
    score_visual_progression,
    write_composition_report,
)


def audit_cinematic_composition(
    run_dir: Optional[Path],
    storyboard: Dict[str, Any],
    editorial_timeline: Dict[str, Any],
    raw_traces: Optional[List[Dict[str, Any]]] = None,
    decoded_qa_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Audit storyboard framing variety plus decoded occupancy/mobile/caption non-collision."""
    shots = list(storyboard.get("shots") or [])
    overlays = list(editorial_timeline.get("overlays") or [])

    frame_designs: List[Dict[str, Any]] = []
    for sh in shots:
        sid = sh.get("shot_id")
        sh_ovs = [o for o in overlays if o.get("shot_id") == sid]
        frame_designs.append(design_frame_for_action(sh, editorial_layout=sh_ovs))

    prog = score_visual_progression(shots, frame_designs)
    issues = list(prog.get("issues") or [])

    # Inspect rendered DOM/WebGL traces for runtime caption overlap or safe-area leaks
    checked_frames = 0
    for rec in (raw_traces or []):
        checked_frames += 1
        ov_items = (((rec.get("telemetry") or {}).get("overlay") or {}).get("overlays")) or []
        for item in ov_items:
            if not item.get("visible"):
                continue
            if item.get("caption_overlap"):
                issues.append(
                    f"N07: Rendered overlay {item.get('overlay_id')} overlapped caption band at t={rec.get('time')}s"
                )
            if item.get("in_safe_area") is False:
                issues.append(
                    f"Rendered overlay {item.get('overlay_id')} left 9:16 safe area at t={rec.get('time')}s"
                )

    # Fold in independent decoded visual prominence & mobile 360px proof if executed
    decoded_status = None
    if isinstance(decoded_qa_report, dict):
        decoded_status = decoded_qa_report.get("status")
        if decoded_status == "FAIL":
            issues.extend(list(decoded_qa_report.get("issues") or [])[:12])

    status = "FAIL" if issues else ("NOT_VERIFIED" if decoded_status == "NOT_VERIFIED" else "PASS")
    report = {
        "schema_version": "sd-cinematic-composition-qa-2",
        "status": status,
        "subjective_visual_quality": "NOT_VERIFIED",
        "HUMAN_REVIEW_REQUIRED": True,
        "checked_runtime_frames": checked_frames,
        "decoded_visual_evidence_status": decoded_status or "PRE_RENDER_PLAN_ONLY",
        "unique_framings_count": prog["unique_framings_count"],
        "unique_angles_count": prog["unique_angles_count"],
        "unique_moves_count": prog["unique_moves_count"],
        "frames": prog["frames"],
        "issues": issues,
    }
    if run_dir is not None:
        write_composition_report(run_dir, report)
    return report
