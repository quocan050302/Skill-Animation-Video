"""STEP 6 (SD-VISUAL-01): Scene Diversity, Perceptual SSIM/pHash, Camera Motion & Transition Continuity QA.

Measures actual decoded frames with the caption band masked cleanly so moving text does not
masquerade as visual novelty or freeze-frame artifacts. Never claims human subjective approval
in non-interactive headless execution (`subjective_visual_review = "NOT_VERIFIED"`).
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from . import VALID_SKILLS


def _decode_scaled_rgb(video_path: Path, t_sec: float, w: int = 270, h: int = 480) -> np.ndarray:
    cmd = [
        "ffmpeg", "-v", "error",
        "-ss", f"{max(0.0, t_sec):.3f}",
        "-i", str(video_path),
        "-vf", f"scale={w}:{h}:flags=bilinear",
        "-frames:v", "1",
        "-f", "image2pipe", "-vcodec", "png", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, check=True)
    img = Image.open(io.BytesIO(res.stdout)).convert("RGB")
    return np.asarray(img, dtype=np.float32)


def _mask_caption_band(arr: np.ndarray) -> np.ndarray:
    """Zero/neutralize bottom caption zone (`y` in 64%..82%) so caption changes don't bias diversity."""
    out = arr.copy()
    h = out.shape[0]
    y0, y1 = int(h * 0.64), int(h * 0.82)
    out[y0:y1, :, :] = float(out[:y0, :, :].mean()) if y0 > 0 else 128.0
    return out


def _dhash_64(gray: np.ndarray) -> str:
    pil = Image.fromarray(np.clip(gray, 0, 255).astype(np.uint8)).resize((9, 8), Image.Resampling.BILINEAR)
    px = np.asarray(pil, dtype=np.float32)
    bits = (px[:, 1:] > px[:, :-1]).flatten()
    val = 0
    for b in bits:
        val = (val << 1) | int(bool(b))
    return f"{val:016x}"


def _dhash_hamming(h1: str, h2: str) -> int:
    return int(bin(int(h1, 16) ^ int(h2, 16)).count("1"))


def _global_ssim(a_rgb: np.ndarray, b_rgb: np.ndarray) -> float:
    """Compute structural similarity over masked grayscale image cleanly with zero extra deps."""
    xa = a_rgb.mean(axis=2)
    xb = b_rgb.mean(axis=2)
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    mu_a = float(xa.mean())
    mu_b = float(xb.mean())
    va = float(xa.var())
    vb = float(xb.var())
    cov = float(((xa - mu_a) * (xb - mu_b)).mean())
    num = (2.0 * mu_a * mu_b + c1) * (2.0 * cov + c2)
    den = (mu_a * mu_a + mu_b * mu_b + c1) * (va + vb + c2)
    return round(float(max(-1.0, min(1.0, num / max(1e-6, den)))), 4)


def build_shot_semantic_fingerprints(shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build compact semantic composition & trajectory descriptors per shot."""
    fps_list: List[Dict[str, Any]] = []
    for s in shots:
        cam = s.get("camera") or {}
        st = s.get("staging") or {}
        fps_list.append({
            "shot_id": s.get("shot_id"),
            "event_ids": list(s.get("event_ids", [])),
            "subject": st.get("subject", "subject"),
            "props": list(st.get("grounded_props", [st.get("visual_metaphor", "prop")])),
            "background_theme": st.get("background_theme", s.get("lighting_mood", "day_editorial")),
            "setup_type": s.get("setup_type"),
            "scene_family": s.get("scene_family", st.get("scene_family", "")),
            "scale_level": s.get("scale_level", st.get("scale_level", "")),
            "framing": cam.get("framing"),
            "angle": cam.get("angle"),
            "camera_path_family": cam.get("movement"),
            "action": st.get("verb_action", st.get("action", "")),
            "dominant_composition": st.get("subject_placement", "center"),
            "silhouette": st.get("silhouette_tag", ""),
            "procedural_generator": s.get("procedural_generator", ""),
            "end_state": s.get("visual_objective", ""),
            "callback_reason": s.get("callback_reason"),
            "novel_non_template": bool(s.get("novel_non_template", False)),
        })
    return fps_list


def sample_perceptual_frames(
    video_mp4: Path,
    shots: List[Dict[str, Any]],
    mask_captions: bool = True,
) -> Dict[str, Any]:
    """Decode start, mid, end frames per shot (+ transition neighbors) with masked caption region."""
    samples: List[Dict[str, Any]] = []
    shot_arrays: List[Tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for s in shots:
        st = float(s["start"])
        en = float(s["end"])
        dur = max(0.2, en - st)
        t0 = st + min(0.08, dur * 0.15)
        tm = 0.5 * (st + en)
        t1 = max(t0 + 0.05, en - min(0.08, dur * 0.15))

        f0 = _decode_scaled_rgb(video_mp4, t0)
        fm = _decode_scaled_rgb(video_mp4, tm)
        f1 = _decode_scaled_rgb(video_mp4, t1)
        if mask_captions:
            f0_m, fm_m, f1_m = _mask_caption_band(f0), _mask_caption_band(fm), _mask_caption_band(f1)
        else:
            f0_m, fm_m, f1_m = f0, fm, f1

        shot_arrays.append((f0_m, fm_m, f1_m))
        mad_internal = float(0.5 * (np.abs(fm_m - f0_m).mean() + np.abs(f1_m - fm_m).mean()))
        samples.append({
            "shot_id": s["shot_id"],
            "times_sampled": [round(t0, 3), round(tm, 3), round(t1, 3)],
            "dhash_mid": _dhash_64(fm_m.mean(axis=2)),
            "intra_mad_masked": round(mad_internal, 3),
            "luma_std_mid": round(float(fm_m.std()), 2),
        })

    adjacent_pairs: List[Dict[str, Any]] = []
    for i in range(1, len(shots)):
        prev_mid = shot_arrays[i - 1][1]
        cur_mid = shot_arrays[i][1]
        ssim = _global_ssim(prev_mid, cur_mid)
        ham = _dhash_hamming(samples[i - 1]["dhash_mid"], samples[i]["dhash_mid"])
        mad_pair = float(np.abs(cur_mid - prev_mid).mean())
        adjacent_pairs.append({
            "from": shots[i - 1]["shot_id"],
            "to": shots[i]["shot_id"],
            "masked_ssim": ssim,
            "dhash_hamming": ham,
            "masked_mad": round(mad_pair, 3),
        })

    return {
        "samples": samples,
        "adjacent_pairs": adjacent_pairs,
        "shot_arrays": shot_arrays,
    }


def detect_adjacent_repetitions(
    shots: List[Dict[str, Any]],
    fingerprints: List[Dict[str, Any]],
    perceptual_pairs: Optional[List[Dict[str, Any]]] = None,
    selected_skill: str = "zach-d-films",
    ssim_hint: float = 0.94,
) -> Dict[str, Any]:
    """Detect adjacent setup/camera/visual duplicates without punishing justified transformed callbacks."""
    flags: List[Dict[str, Any]] = []
    hard_clones: List[str] = []

    pair_map = {(p["from"], p["to"]): p for p in (perceptual_pairs or [])}
    for i in range(1, len(shots)):
        fa = fingerprints[i - 1]
        fb = fingerprints[i]
        has_callback = bool(fb.get("callback_reason"))
        if has_callback:
            continue

        same_setup = fa["setup_type"] == fb["setup_type"]
        same_cam_triple = (fa["framing"], fa["angle"], fa["camera_path_family"]) == (
            fb["framing"], fb["angle"], fb["camera_path_family"]
        )
        same_bg_sub = (fa["subject"] == fb["subject"]) and (fa["background_theme"] == fb["background_theme"]) and (fa["action"] == fb["action"])
        pair = pair_map.get((fa["shot_id"], fb["shot_id"]))
        high_ssim = bool(pair and pair["masked_ssim"] >= ssim_hint and pair["dhash_hamming"] <= 3)

        if (same_setup and same_cam_triple) or (same_setup and same_bg_sub and high_ssim):
            hard_clones.append(f"{fa['shot_id']}->{fb['shot_id']}")
            flags.append({
                "pair": f"{fa['shot_id']}->{fb['shot_id']}",
                "severity": "FAIL",
                "reason": "Near-identical adjacent shot setup/camera/visual composition without transformed callback.",
                "perceptual": pair,
            })
        elif same_setup and selected_skill not in ("minimalistic-graphics",):
            flags.append({
                "pair": f"{fa['shot_id']}->{fb['shot_id']}",
                "severity": "WARN",
                "reason": "Adjacent shots share setup_type despite distinct framing/action.",
                "perceptual": pair,
            })

    status = "FAIL" if hard_clones else ("WARN" if flags else "PASS")
    return {
        "status": status,
        "hard_clone_count": len(hard_clones),
        "hard_clones": hard_clones,
        "flags": flags,
        "calibration_ssim_hint": ssim_hint,
    }


def audit_intra_shot_motion(
    perceptual_samples: List[Dict[str, Any]],
    shots: List[Dict[str, Any]],
    selected_skill: str,
    edit_energy: str = "balanced",
    max_static_hold_sec: Optional[float] = None,
) -> Dict[str, Any]:
    """Verify live intra-shot pixel motion cleanly while respecting intentional minimalist calm holds."""
    frozen: List[str] = []
    long_holds: List[str] = []
    min_mad = 0.03 if selected_skill == "minimalistic-graphics" else 0.08
    hold_limit = max_static_hold_sec if max_static_hold_sec is not None else (6.5 if edit_energy == "calm" else 5.2)

    for samp, s in zip(perceptual_samples, shots):
        dur = float(s["duration"])
        mad = float(samp["intra_mad_masked"])
        is_explicit_hold = bool((s.get("staging") or {}).get("intentional_hold", False))
        if mad < min_mad and not is_explicit_hold:
            frozen.append(f"{s['shot_id']} (masked_mad={mad:.3f})")
        if dur > hold_limit and not s.get("intra_shot_events") and not is_explicit_hold:
            long_holds.append(f"{s['shot_id']} ({dur:.2f}s > {hold_limit:.1f}s without in-shot change)")

    status = "FAIL" if frozen else ("WARN" if long_holds else "PASS")
    return {
        "status": status,
        "frozen_shots": frozen,
        "unmotivated_long_holds": long_holds,
        "min_masked_mad_threshold": min_mad,
    }


def audit_transition_continuity(
    video_mp4: Path,
    transition_edl: Optional[Dict[str, Any]],
    shots: List[Dict[str, Any]],
    selected_skill: str,
    fps: int = 30,
) -> Dict[str, Any]:
    """Verify decoded frames around transition boundaries match EDL without corrupt/unexpected black flashes."""
    if not transition_edl or not transition_edl.get("transitions"):
        return {"status": "PASS", "verified_transitions": 0, "issues": [], "notes": ["Single-shot timeline or no transitions."]}

    transitions = list(transition_edl["transitions"])
    issues: List[str] = []
    checked: List[Dict[str, Any]] = []

    for tr in transitions:
        tb = float(tr["boundary_sec"])
        method = str(tr["actual_method"])
        # Sample safely immediately before seam & immediately after seam
        fa = _mask_caption_band(_decode_scaled_rgb(video_mp4, max(0.0, tb - 0.08)))
        fb = _mask_caption_band(_decode_scaled_rgb(video_mp4, tb + 0.08))
        mad_seam = float(np.abs(fb - fa).mean())
        fa_std, fb_std = float(fa.std()), float(fb.std())

        if (fa_std < 1.0 or fb_std < 1.0) and method != "dip_to_black" and selected_skill != "minimalistic-graphics":
            issues.append(f"{tr['transition_id']} ({method}) produced unexpected flat/black frame at {tb:.2f}s")
            tr["verification_status"] = "FAIL"
        elif mad_seam < 0.05 and tr["from_shot"] != tr["to_shot"]:
            issues.append(f"{tr['transition_id']} ({method}) shows zero visual change across boundary {tb:.2f}s")
            tr["verification_status"] = "WARN"
        else:
            tr["verification_status"] = "VERIFIED_DECODED"

        checked.append({
            "transition_id": tr["transition_id"],
            "actual_method": method,
            "boundary_sec": tb,
            "seam_mad_masked": round(mad_seam, 3),
            "verification_status": tr["verification_status"],
        })

    return {
        "status": "FAIL" if any(c["verification_status"] == "FAIL" for c in checked) else ("WARN" if issues else "PASS"),
        "verified_transitions": len(checked),
        "issues": issues,
        "details": checked,
    }


def audit_scene_novelty(
    shots: List[Dict[str, Any]],
    fingerprints: List[Dict[str, Any]],
    selected_skill: str,
    duration_sec: float,
) -> Dict[str, Any]:
    """Measure semantic visual beat density, environment variety, and scale escalation."""
    n_shots = len(shots)
    n_inshot = sum(len(s.get("intra_shot_events", [])) for s in shots)
    total_visual_beats = n_shots + n_inshot
    unique_fams = len({fp["scene_family"] for fp in fingerprints if fp["scene_family"]})
    unique_setups = len({fp["setup_type"] for fp in fingerprints if fp["setup_type"]})
    unique_moves = len({fp["camera_path_family"] for fp in fingerprints if fp["camera_path_family"]})
    unique_scales = len({fp["scale_level"] for fp in fingerprints if fp["scale_level"]})

    avg_beat_interval = round(duration_sec / max(1, total_visual_beats), 3)
    # Soft advisory diagnostics (never fail merely on rigid beat-count threshold on calm styles)
    notes: List[str] = []
    if selected_skill == "zach-d-films" and duration_sec >= 20.0 and unique_setups < 3:
        notes.append(f"Low scene novelty on {duration_sec:.1f}s 3D video: only {unique_setups} unique setups.")

    return {
        "status": "WARN" if notes else "PASS",
        "shot_count": n_shots,
        "intra_shot_events_count": n_inshot,
        "total_visual_beats": total_visual_beats,
        "avg_sec_per_visual_beat": avg_beat_interval,
        "unique_scene_families": unique_fams,
        "unique_setups": unique_setups,
        "unique_camera_movements": unique_moves,
        "unique_scale_levels": unique_scales,
        "notes": notes,
    }


def audit_visual_skill_lock(
    style_lock_status: str,
    selected_skill: str,
) -> Dict[str, Any]:
    """Verify strict single-skill provenance audit state cleanly."""
    st = style_lock_status if style_lock_status in ("PASS", "FAIL", "NOT_VERIFIED") else "NOT_VERIFIED"
    if selected_skill not in VALID_SKILLS:
        st = "FAIL"
    return {
        "status": st,
        "selected_skill": selected_skill,
        "valid_skill": selected_skill in VALID_SKILLS,
    }


def run_scene_diversity_qa(
    run_dir: Path,
    video_mp4: Path,
    storyboard: Dict[str, Any],
    style_lock_status: str = "PASS",
    transition_edl: Optional[Dict[str, Any]] = None,
    camera_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute complete STEP 6 Scene Diversity & Retention Proxy QA -> `scene_diversity_report.json`."""
    shots = list(storyboard.get("shots", []))
    selected_skill = str(storyboard.get("selected_skill") or "zach-d-films")
    fps = int(storyboard.get("fps", 30))
    dur = float(storyboard.get("total_duration_sec", 0.0))
    edit_energy = str(storyboard.get("edit_energy", "balanced"))

    if not video_mp4.exists() or video_mp4.stat().st_size == 0:
        report = {
            "schema_version": "sd-scene-diversity-qa-1",
            "overall_status": "FAIL",
            "subjective_visual_review": "NOT_VERIFIED",
            "reason": f"Missing or zero-byte deliverable MP4: {video_mp4}",
        }
        (run_dir / "scene_diversity_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    fingerprints = build_shot_semantic_fingerprints(shots)
    perc = sample_perceptual_frames(video_mp4, shots, mask_captions=True)

    rep_audit = detect_adjacent_repetitions(
        shots=shots,
        fingerprints=fingerprints,
        perceptual_pairs=perc["adjacent_pairs"],
        selected_skill=selected_skill,
    )
    motion_audit = audit_intra_shot_motion(
        perceptual_samples=perc["samples"],
        shots=shots,
        selected_skill=selected_skill,
        edit_energy=edit_energy,
    )
    trans_audit = audit_transition_continuity(
        video_mp4=video_mp4,
        transition_edl=transition_edl,
        shots=shots,
        selected_skill=selected_skill,
        fps=fps,
    )
    novelty_audit = audit_scene_novelty(
        shots=shots,
        fingerprints=fingerprints,
        selected_skill=selected_skill,
        duration_sec=dur,
    )
    skill_lock_check = audit_visual_skill_lock(style_lock_status, selected_skill)

    if transition_edl is not None:
        (run_dir / "transition_edl.json").write_text(json.dumps(transition_edl, ensure_ascii=False, indent=2), encoding="utf-8")

    statuses = [
        rep_audit["status"],
        motion_audit["status"],
        trans_audit["status"],
        novelty_audit["status"],
        skill_lock_check["status"],
    ]
    overall = "FAIL" if ("FAIL" in statuses or "NOT_VERIFIED" in statuses) else ("WARN" if "WARN" in statuses else "PASS")

    report = {
        "schema_version": "sd-scene-diversity-qa-1",
        "overall_status": overall,
        "subjective_visual_review": "NOT_VERIFIED",
        "subjective_review_note": "Machine perceptual pHash/SSIM, caption-masked motion, and transition seam checks ran on decoded frames; manual creative playback must be verified explicitly if required.",
        "selected_skill": selected_skill,
        "checks": {
            "visual_skill_lock": skill_lock_check,
            "adjacent_repetition_guard": rep_audit,
            "intra_shot_motion": motion_audit,
            "transition_continuity": trans_audit,
            "scene_novelty_metrics": novelty_audit,
        },
        "fingerprints": fingerprints,
        "perceptual_samples": perc["samples"],
        "adjacent_perceptual_pairs": perc["adjacent_pairs"],
    }
    (run_dir / "scene_diversity_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
