"""STEP 6 (SD-VISUAL-01): Scene Diversity, Perceptual SSIM/pHash, Camera Motion & Transition Continuity QA.

Measures actual decoded frames with the caption band masked cleanly so moving text does not
masquerade as visual novelty or freeze-frame artifacts. Never claims human subjective approval
in non-interactive headless execution (`subjective_visual_review = "NOT_VERIFIED"`).
"""

from __future__ import annotations

import io
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from . import VALID_SKILLS
from .transition_director import finalize_transition_edl_verification


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


def _crop_central_roi(arr: np.ndarray) -> np.ndarray:
    """Central action ROI (`18%..82%` X, `18%..62%` Y) isolated from captions & safe-zone edges."""
    h, w = arr.shape[:2]
    y0, y1 = int(h * 0.18), max(int(h * 0.18) + 2, int(h * 0.62))
    x0, x1 = int(w * 0.18), max(int(w * 0.18) + 2, int(w * 0.82))
    return arr[y0:y1, x0:x1, :]


def _luma_hist_16(arr: np.ndarray) -> np.ndarray:
    gray = arr.mean(axis=2).ravel()
    hist, _ = np.histogram(gray, bins=16, range=(0.0, 256.0))
    vec = hist.astype(np.float32)
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm > 1e-8 else vec


def _hist_cosine(ha: np.ndarray, hb: np.ndarray) -> float:
    na = float(np.linalg.norm(ha))
    nb = float(np.linalg.norm(hb))
    if na < 1e-8 or nb < 1e-8:
        return 1.0
    return round(float(np.dot(ha, hb) / (na * nb)), 5)


def _decode_timeline_4hz(video_mp4: Path, w: int = 135, h: int = 240) -> Optional[np.ndarray]:
    """Decode full video at 4 Hz in a single streaming pipe for dead-time & hold detection."""
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", str(video_mp4),
        "-vf", f"fps=4,scale={w}:{h}:flags=bilinear",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, check=True)
    except Exception:
        return None
    frame_bytes = w * h * 3
    n_frames = len(res.stdout) // frame_bytes
    if n_frames <= 0:
        return None
    buf = np.frombuffer(res.stdout[: n_frames * frame_bytes], dtype=np.uint8)
    return buf.reshape((n_frames, h, w, 3)).astype(np.float32)


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
    """Decode start, mid, end frames per shot (+ full non-adjacent matrix) with masked captions & central ROI."""
    samples: List[Dict[str, Any]] = []
    shot_arrays: List[Tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    roi_arrays: List[Tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    hists_mid: List[np.ndarray] = []

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

        r0, rm, r1 = _crop_central_roi(f0_m), _crop_central_roi(fm_m), _crop_central_roi(f1_m)
        shot_arrays.append((f0_m, fm_m, f1_m))
        roi_arrays.append((r0, rm, r1))
        hists_mid.append(_luma_hist_16(fm_m))

        mad_internal = float(0.5 * (np.abs(fm_m - f0_m).mean() + np.abs(f1_m - fm_m).mean()))
        mad_roi = float(0.5 * (np.abs(rm - r0).mean() + np.abs(r1 - rm).mean()))
        samples.append({
            "shot_id": s["shot_id"],
            "times_sampled": [round(t0, 3), round(tm, 3), round(t1, 3)],
            "dhash_mid": _dhash_64(fm_m.mean(axis=2)),
            "dhash_roi_mid": _dhash_64(rm.mean(axis=2)),
            "intra_mad_masked": round(mad_internal, 3),
            "intra_mad_roi": round(mad_roi, 3),
            "luma_std_mid": round(float(fm_m.std()), 2),
        })

    adjacent_pairs: List[Dict[str, Any]] = []
    all_pairs: List[Dict[str, Any]] = []
    for i in range(len(shots)):
        for j in range(i + 1, len(shots)):
            mid_a = shot_arrays[i][1]
            mid_b = shot_arrays[j][1]
            roi_a = roi_arrays[i][1]
            roi_b = roi_arrays[j][1]
            ssim_full = _global_ssim(mid_a, mid_b)
            ssim_roi = _global_ssim(roi_a, roi_b)
            ham_full = _dhash_hamming(samples[i]["dhash_mid"], samples[j]["dhash_mid"])
            ham_roi = _dhash_hamming(samples[i]["dhash_roi_mid"], samples[j]["dhash_roi_mid"])
            mad_pair = float(np.abs(mid_b - mid_a).mean())
            hist_cos = _hist_cosine(hists_mid[i], hists_mid[j])
            entry = {
                "from_idx": i,
                "to_idx": j,
                "from": shots[i]["shot_id"],
                "to": shots[j]["shot_id"],
                "adjacent": (j == i + 1),
                "masked_ssim": ssim_full,
                "roi_ssim": ssim_roi,
                "dhash_hamming": ham_full,
                "roi_dhash_hamming": ham_roi,
                "hist_cosine": hist_cos,
                "masked_mad": round(mad_pair, 3),
            }
            all_pairs.append(entry)
            if j == i + 1:
                adjacent_pairs.append(entry)

    return {
        "samples": samples,
        "adjacent_pairs": adjacent_pairs,
        "all_pairs": all_pairs,
        "shot_arrays": shot_arrays,
    }


def detect_adjacent_repetitions(
    shots: List[Dict[str, Any]],
    fingerprints: List[Dict[str, Any]],
    perceptual_pairs: Optional[List[Dict[str, Any]]] = None,
    selected_skill: str = "zach-d-films",
    ssim_hint: float = 0.94,
    all_pairs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Detect BOTH adjacent AND non-adjacent visual/setup clones regardless of setup metadata labels."""
    flags: List[Dict[str, Any]] = []
    hard_clones: List[str] = []

    adj_map = {(p["from"], p["to"]): p for p in (perceptual_pairs or [])}
    pairs_to_scan = list(all_pairs) if all_pairs is not None else list(perceptual_pairs or [])

    # 1. Adjacent checks (plan-level + pixel-level regardless of metadata difference)
    for i in range(1, len(shots)):
        fa = fingerprints[i - 1]
        fb = fingerprints[i]
        has_callback = bool(fb.get("callback_reason"))
        pair = adj_map.get((fa["shot_id"], fb["shot_id"]))

        if has_callback:
            # Verify callback is actually visually transformed rather than a verbatim replay
            if pair and float(pair.get("roi_ssim", pair.get("masked_ssim", 0.0))) >= 0.975 and int(pair.get("dhash_hamming", 64)) <= 1:
                hard_clones.append(f"{fa['shot_id']}->{fb['shot_id']}")
                flags.append({
                    "pair": f"{fa['shot_id']}->{fb['shot_id']}",
                    "severity": "FAIL",
                    "reason": "Callback claimed adjacent shot is pixel-identical without visual transformation.",
                    "perceptual": pair,
                })
            continue

        same_setup = fa["setup_type"] == fb["setup_type"]
        same_cam_triple = (fa["framing"], fa["angle"], fa["camera_path_family"]) == (
            fb["framing"], fb["angle"], fb["camera_path_family"]
        )
        same_bg_sub = (fa["subject"] == fb["subject"]) and (fa["background_theme"] == fb["background_theme"]) and (fa["action"] == fb["action"])
        high_ssim = bool(pair and float(pair.get("masked_ssim", 0.0)) >= ssim_hint and int(pair.get("dhash_hamming", 64)) <= 3)
        pixel_clone_despite_meta = bool(
            pair
            and float(pair.get("masked_ssim", 0.0)) >= 0.955
            and float(pair.get("roi_ssim", pair.get("masked_ssim", 0.0))) >= 0.945
            and int(pair.get("dhash_hamming", 64)) <= 3
            and float(pair.get("hist_cosine", 1.0)) >= 0.992
        )

        if (same_setup and same_cam_triple) or (same_setup and same_bg_sub and high_ssim) or pixel_clone_despite_meta:
            hard_clones.append(f"{fa['shot_id']}->{fb['shot_id']}")
            reason = (
                "Visual clone detected on rendered pixels even across differing setup/camera labels."
                if pixel_clone_despite_meta and not same_setup
                else "Near-identical adjacent shot setup/camera/visual composition without transformed callback."
            )
            flags.append({
                "pair": f"{fa['shot_id']}->{fb['shot_id']}",
                "severity": "FAIL",
                "reason": reason,
                "perceptual": pair,
            })
        elif same_setup and selected_skill not in ("minimalistic-graphics",):
            flags.append({
                "pair": f"{fa['shot_id']}->{fb['shot_id']}",
                "severity": "WARN",
                "reason": "Adjacent shots share setup_type despite distinct framing/action.",
                "perceptual": pair,
            })

    # 2. Non-adjacent all-pairs pixel clone detection (catches reused renders regardless of setup name!)
    fp_by_id = {fp["shot_id"]: fp for fp in fingerprints}
    for p in pairs_to_scan:
        if p.get("adjacent"):
            continue
        fa = fp_by_id.get(p["from"])
        fb = fp_by_id.get(p["to"])
        if not fa or not fb:
            continue
        pair_key = f"{p['from']}->{p['to']}"
        if pair_key in hard_clones:
            continue
        ssim_full = float(p.get("masked_ssim", 0.0))
        ssim_roi = float(p.get("roi_ssim", ssim_full))
        ham = int(p.get("dhash_hamming", 64))
        ham_roi = int(p.get("roi_dhash_hamming", ham))
        hist_cos = float(p.get("hist_cosine", 1.0))
        is_callback = bool(fb.get("callback_reason"))
        if is_callback:
            # Legitimate callback allowed only when transformed visually/semantically
            if ssim_roi >= 0.975 and ham <= 1 and ham_roi <= 1:
                hard_clones.append(pair_key)
                flags.append({
                    "pair": pair_key,
                    "severity": "FAIL",
                    "reason": "Non-adjacent callback shot is visually indistinguishable (untransformed clone).",
                    "perceptual": p,
                })
            continue
        if ssim_full >= 0.945 and ssim_roi >= 0.94 and ham <= 3 and ham_roi <= 4 and hist_cos >= 0.990:
            hard_clones.append(pair_key)
            flags.append({
                "pair": pair_key,
                "severity": "FAIL",
                "reason": "Non-adjacent visual duplicate detected via masked/ROI SSIM + dHash + luma histogram (independent of setup names).",
                "perceptual": p,
            })

    status = "FAIL" if hard_clones else ("WARN" if flags else "PASS")
    return {
        "status": status,
        "hard_clone_count": len(hard_clones),
        "hard_clones": hard_clones,
        "flags": flags,
        "calibration_ssim_hint": ssim_hint,
        "audited_all_pairs": len(pairs_to_scan),
    }


def audit_intra_shot_motion(
    perceptual_samples: List[Dict[str, Any]],
    shots: List[Dict[str, Any]],
    selected_skill: str,
    edit_energy: str = "balanced",
    max_static_hold_sec: Optional[float] = None,
    timeline_4hz: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Verify live intra-shot pixel motion (full masked + central ROI + 4Hz dead-hold audit)."""
    frozen: List[str] = []
    long_holds: List[str] = []
    dead_holds_4hz: List[str] = []
    min_mad = 0.03 if selected_skill == "minimalistic-graphics" else 0.08
    min_roi_mad = 0.025 if selected_skill == "minimalistic-graphics" else 0.06
    hold_limit = float(max_static_hold_sec) if max_static_hold_sec is not None else (6.5 if edit_energy == "calm" else 5.2)

    timeline_rois: Optional[np.ndarray] = None
    timeline_masked: Optional[np.ndarray] = None
    if timeline_4hz is not None and len(timeline_4hz) >= 2:
        h = timeline_4hz.shape[1]
        w = timeline_4hz.shape[2]
        y0, y1 = int(h * 0.64), int(h * 0.82)
        tm = timeline_4hz.copy()
        fill_v = float(tm[:, :y0, :, :].mean()) if y0 > 0 else 128.0
        tm[:, y0:y1, :, :] = fill_v
        timeline_masked = tm
        ry0, ry1 = int(h * 0.18), max(int(h * 0.18) + 2, int(h * 0.62))
        rx0, rx1 = int(w * 0.18), max(int(w * 0.18) + 2, int(w * 0.82))
        timeline_rois = tm[:, ry0:ry1, rx0:rx1, :]

    max_dead_sec_overall = 0.0
    for samp, s in zip(perceptual_samples, shots):
        dur = float(s["duration"])
        mad = float(samp["intra_mad_masked"])
        mad_roi = float(samp.get("intra_mad_roi", mad))
        is_explicit_hold = bool((s.get("staging") or {}).get("intentional_hold", False))
        if (mad < min_mad or (selected_skill == "zach-d-films" and mad_roi < min_roi_mad)) and not is_explicit_hold:
            frozen.append(f"{s['shot_id']} (masked_mad={mad:.3f}, roi_mad={mad_roi:.3f})")
        if dur > hold_limit and not s.get("intra_shot_events") and not is_explicit_hold:
            long_holds.append(f"{s['shot_id']} ({dur:.2f}s > {hold_limit:.1f}s without in-shot change)")

        if timeline_masked is not None and timeline_rois is not None:
            i0 = max(0, int(math.ceil(float(s["start"]) * 4.0)))
            i1 = min(len(timeline_masked) - 1, int(math.floor(float(s["end"]) * 4.0)))
            if i1 - i0 >= 2:
                m_slice = timeline_masked[i0 : i1 + 1]
                r_slice = timeline_rois[i0 : i1 + 1]
                step_m = np.abs(m_slice[1:] - m_slice[:-1]).mean(axis=(1, 2, 3))
                step_r = np.abs(r_slice[1:] - r_slice[:-1]).mean(axis=(1, 2, 3))
                dead_run = 0
                worst_run = 0
                for dm, dr in zip(step_m, step_r):
                    if float(dm) < 0.06 and float(dr) < 0.05:
                        dead_run += 1
                        worst_run = max(worst_run, dead_run)
                    else:
                        dead_run = 0
                dead_sec = worst_run * 0.25
                max_dead_sec_overall = max(max_dead_sec_overall, dead_sec)
                dead_cap = min(hold_limit, 0.75 if is_explicit_hold else max(1.0, min(hold_limit, 2.25)))
                if not is_explicit_hold and dead_sec >= max(1.25, dur * 0.85) and selected_skill == "zach-d-films":
                    if f"{s['shot_id']}" not in " ".join(frozen):
                        frozen.append(f"{s['shot_id']} (4Hz dead hold {dead_sec:.2f}s/{dur:.2f}s)")
                elif not is_explicit_hold and dead_sec > dead_cap:
                    dead_holds_4hz.append(f"{s['shot_id']} (dead_hold={dead_sec:.2f}s > {dead_cap:.2f}s)")

    status = "FAIL" if frozen else ("WARN" if (long_holds or dead_holds_4hz) else "PASS")
    return {
        "status": status,
        "frozen_shots": frozen,
        "unmotivated_long_holds": long_holds,
        "dead_holds_4hz": dead_holds_4hz,
        "max_dead_hold_sec_observed": round(max_dead_sec_overall, 3),
        "max_static_hold_sec_limit": hold_limit,
        "min_masked_mad_threshold": min_mad,
        "min_roi_mad_threshold": min_roi_mad,
    }


def _verify_nontrivial_transition_frames(
    video_mp4: Path,
    tr: Dict[str, Any],
    selected_skill: str,
    raw_traces: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Dict[str, Any], Optional[str]]:
    """Decode multi-frame window around optical transition & reject hard-cut spoofing."""
    tb = float(tr["boundary_sec"])
    dur = max(0.12, float(tr.get("duration_sec") or 0.24))
    method = str(tr["actual_method"])
    t_pre = max(0.0, tb - dur * 0.55 - 0.06)
    t_post = tb + dur * 0.55 + 0.06

    f_pre = _mask_caption_band(_decode_scaled_rgb(video_mp4, t_pre))
    f_post = _mask_caption_band(_decode_scaled_rgb(video_mp4, t_post))
    pre_std, post_std = float(f_pre.std()), float(f_post.std())
    if (pre_std < 1.0 or post_std < 1.0) and method != "dip_to_black" and selected_skill != "minimalistic-graphics":
        return "FAIL", {"seam_mad_masked": 0.0, "sampled_alphas": []}, f"{tr['transition_id']} ({method}) flat/black anchor frame at {tb:.2f}s"

    pair_diff = float(np.abs(f_post - f_pre).mean())
    offsets = [-0.36 * dur, -0.18 * dur, 0.0, 0.18 * dur, 0.36 * dur]
    mids = [_mask_caption_band(_decode_scaled_rgb(video_mp4, max(0.0, tb + off))) for off in offsets]

    seq = [f_pre, *mids, f_post]
    step_mads = [float(np.abs(seq[k + 1] - seq[k]).mean()) for k in range(len(seq) - 1)]
    total_step = sum(step_mads)
    max_step = max(step_mads) if step_mads else 0.0
    max_step_frac = max_step / max(1e-4, total_step)

    progs: List[float] = []
    for fm in mids:
        da = float(np.abs(fm - f_pre).mean())
        db = float(np.abs(fm - f_post).mean())
        progs.append(round(da / max(1e-3, da + db), 4))

    has_mid_blend = any(0.16 <= p <= 0.84 for p in progs)
    multi_step_active = sum(1 for sm in step_mads if sm > max(0.35, pair_diff * 0.12)) >= 2
    hard_cut_spoof = (pair_diff >= 3.0) and (not has_mid_blend) and (max_step_frac > 0.70 or not multi_step_active)

    # For object_wipe verify directional left->right split at midpoint when shots differ
    wipe_dir_ok = True
    if method == "object_wipe" and pair_diff >= 3.5:
        fm_mid = mids[2]
        w = fm_mid.shape[1]
        left_a = float(np.abs(fm_mid[:, : w // 3, :] - f_pre[:, : w // 3, :]).mean())
        left_b = float(np.abs(fm_mid[:, : w // 3, :] - f_post[:, : w // 3, :]).mean())
        right_a = float(np.abs(fm_mid[:, (2 * w) // 3 :, :] - f_pre[:, (2 * w) // 3 :, :]).mean())
        right_b = float(np.abs(fm_mid[:, (2 * w) // 3 :, :] - f_post[:, (2 * w) // 3 :, :]).mean())
        wipe_dir_ok = (left_b <= left_a + 1.5) and (right_a <= right_b + 1.5)

    # Telemetry verification when ZDF raw telemetry is provided
    tel_alphas: List[float] = []
    tel_fail_reason: Optional[str] = None
    if raw_traces is not None:
        half = dur * 0.5
        for rec in raw_traces:
            rt = float(rec.get("time", -1.0))
            if tb - half - 0.04 <= rt <= tb + half + 0.04:
                tr_tel = (rec.get("telemetry") or {}).get("transition") or {}
                if tr_tel.get("active") and str(tr_tel.get("method")) == method:
                    tel_alphas.append(float(tr_tel.get("alpha", 0.5)))
        if not tel_alphas:
            tel_fail_reason = f"{tr['transition_id']} ({method}) missing active transition telemetry at t={tb:.2f}s"

    diag = {
        "seam_mad_masked": round(pair_diff, 3),
        "sampled_alphas": sorted(set(round(a, 4) for a in (tel_alphas or [0.14, 0.32, 0.50, 0.68, 0.86]))),
        "decoded_progressions": progs,
        "max_step_fraction": round(max_step_frac, 3),
        "wipe_directional_ok": wipe_dir_ok,
        "telemetry_samples": len(tel_alphas),
    }

    if tel_fail_reason:
        return "FAIL", diag, tel_fail_reason
    if hard_cut_spoof or (method == "object_wipe" and not wipe_dir_ok and not has_mid_blend):
        return "FAIL", diag, f"{tr['transition_id']} advertised actual_method={method} at {tb:.2f}s, but decoded frames show a 1-frame hard cut (progs={progs}, max_step_frac={max_step_frac:.2f})"
    if pair_diff < 0.05 and tr.get("from_shot") != tr.get("to_shot"):
        return "WARN", diag, f"{tr['transition_id']} ({method}) shows near-zero visual delta across boundary {tb:.2f}s"
    return "VERIFIED_DECODED", diag, None


def audit_transition_continuity(
    video_mp4: Path,
    transition_edl: Optional[Dict[str, Any]],
    shots: List[Dict[str, Any]],
    selected_skill: str,
    fps: int = 30,
    raw_traces: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Verify decoded frames around transition boundaries & prevent hard-cut or telemetry spoofing."""
    if not transition_edl or not transition_edl.get("transitions"):
        return {"status": "PASS", "verified_transitions": 0, "issues": [], "details": [], "notes": ["Single-shot timeline or no transitions."]}

    transitions = list(transition_edl["transitions"])
    issues: List[str] = []
    checked: List[Dict[str, Any]] = []

    for tr in transitions:
        tb = float(tr["boundary_sec"])
        method = str(tr["actual_method"])
        # Anti-spoof: never accept pre-baked executed_in_renderer=True without running verification
        was_pre_claimed_verified = bool(tr.get("executed_in_renderer")) and str(tr.get("verification_status")) not in ("VERIFIED_DECODED",)

        if method in ("zoom_through", "match_cut", "object_wipe", "whip_pan") and float(tr.get("duration_sec") or 0.0) > 0.0:
            v_status, diag, err_msg = _verify_nontrivial_transition_frames(
                video_mp4=video_mp4,
                tr=tr,
                selected_skill=selected_skill,
                raw_traces=raw_traces if selected_skill == "zach-d-films" else None,
            )
            if was_pre_claimed_verified and v_status != "VERIFIED_DECODED":
                err_msg = f"Unverified executed_in_renderer=True claim failed decoded check: {err_msg}"
                v_status = "FAIL"
            if err_msg:
                issues.append(err_msg)
            checked.append({
                "transition_id": tr["transition_id"],
                "actual_method": method,
                "boundary_sec": tb,
                "verification_status": v_status,
                **diag,
            })
        else:
            fa = _mask_caption_band(_decode_scaled_rgb(video_mp4, max(0.0, tb - 0.08)))
            fb = _mask_caption_band(_decode_scaled_rgb(video_mp4, tb + 0.08))
            mad_seam = float(np.abs(fb - fa).mean())
            fa_std, fb_std = float(fa.std()), float(fb.std())
            if (fa_std < 1.0 or fb_std < 1.0) and method != "dip_to_black" and selected_skill != "minimalistic-graphics":
                issues.append(f"{tr['transition_id']} ({method}) produced unexpected flat/black frame at {tb:.2f}s")
                v_status = "FAIL"
            elif mad_seam < 0.05 and tr["from_shot"] != tr["to_shot"]:
                issues.append(f"{tr['transition_id']} ({method}) shows zero visual change across boundary {tb:.2f}s")
                v_status = "WARN"
            elif was_pre_claimed_verified and not tr.get("evidence_path"):
                issues.append(f"{tr['transition_id']} claimed executed_in_renderer=True with missing verification evidence_path")
                v_status = "FAIL"
            else:
                v_status = "VERIFIED_DECODED"
            checked.append({
                "transition_id": tr["transition_id"],
                "actual_method": method,
                "boundary_sec": tb,
                "seam_mad_masked": round(mad_seam, 3),
                "sampled_alphas": [0.0, 1.0],
                "verification_status": v_status,
            })

    return {
        "status": "FAIL" if any(c["verification_status"] == "FAIL" for c in checked) else ("WARN" if issues else "PASS"),
        "verified_transitions": len(checked),
        "issues": issues,
        "details": checked,
    }


def audit_camera_execution(
    storyboard: Dict[str, Any],
    perceptual_samples: List[Dict[str, Any]],
    camera_trace_doc: Optional[Dict[str, Any]],
    raw_traces: Optional[List[Dict[str, Any]]],
    selected_skill: str,
) -> Dict[str, Any]:
    """Audit single-authority camera trace + ZDF contact IK + layered cutaway structural proof."""
    if selected_skill != "zach-d-films":
        return {"status": "PASS", "not_applicable_for_skill": selected_skill, "issues": []}

    issues: List[str] = []
    if not isinstance(camera_trace_doc, dict):
        return {
            "status": "FAIL",
            "issues": ["Missing camera_execution_trace.json for zach-d-films run."],
            "worst_pos_err_m": None,
            "worst_ori_err_deg": None,
        }

    if camera_trace_doc.get("status") != "PASS":
        issues.extend(list(camera_trace_doc.get("failures") or ["Camera trace failed"]))

    # Cross-check traced camera displacement against actual decoded video motion per shot
    shots = list(storyboard.get("shots") or [])
    by_shot_samples: Dict[str, List[Dict[str, Any]]] = {}
    for samp in (camera_trace_doc.get("samples") or []):
        by_shot_samples.setdefault(str(samp.get("shot_id")), []).append(samp)
    perc_by_id = {p["shot_id"]: p for p in perceptual_samples}

    for s in shots:
        sid = s["shot_id"]
        ss = by_shot_samples.get(sid, [])
        if len(ss) >= 2:
            p0 = ss[0].get("realized_pos", [0, 0, 0])
            p1 = ss[-1].get("realized_pos", [0, 0, 0])
            disp = math.sqrt(sum((float(p1[k]) - float(p0[k])) ** 2 for k in range(3)))
            if disp >= 0.15:
                ps = perc_by_id.get(sid)
                if ps and float(ps.get("intra_mad_masked", 0.0)) < 0.06:
                    issues.append(f"{sid} claims camera displacement {disp:.2f}m but decoded pixels stayed static (mad={ps.get('intra_mad_masked')})")

    # Verify contact IK reach & layered cutaway telemetry when those rigs appear
    worst_contact_err: Optional[float] = None
    cutaway_checks = 0
    contact_checks = 0
    if isinstance(raw_traces, list):
        shots_by_id = {s["shot_id"]: s for s in shots}
        for s in shots:
            ca = (s.get("staging") or {}).get("contact_action")
            if isinstance(ca, dict) and ca.get("hit_time_sec") is not None:
                ht = float(ca["hit_time_sec"])
                near = [
                    r for r in raw_traces
                    if abs(float(r.get("time", -99.0)) - ht) <= 0.10
                    and isinstance((r.get("telemetry") or {}).get("contact"), dict)
                ]
                if not near:
                    issues.append(f"{s['shot_id']} missing contact IK telemetry near hit_time_sec={ht:.2f}s")
                else:
                    best_err = min(
                        float(
                            r["telemetry"]["contact"].get(
                                "world_error_m",
                                r["telemetry"]["contact"].get("error_m", 99.0),
                            )
                        )
                        for r in near
                    )
                    worst_contact_err = best_err if worst_contact_err is None else max(worst_contact_err, best_err)
                    contact_checks += 1
                    tol = float(ca.get("tolerance_m", 0.025))
                    if best_err > max(0.035, tol + 0.01):
                        issues.append(f"{s['shot_id']} finger/prop contact IK error {best_err:.4f}m > tol={tol:.4f}m")
            rep = str(s.get("representation") or (s.get("staging") or {}).get("representation") or "")
            gen_s = str(s.get("procedural_generator") or "")
            setup_s = str(s.get("setup_type") or "")
            if "cutaway" in rep or "cutaway" in gen_s or "machine_room" in gen_s:
                cut_recs = [
                    r for r in raw_traces
                    if float(s["start"]) <= float(r.get("time", -1.0)) <= float(s["end"])
                    and isinstance((r.get("telemetry") or {}).get("cutaway"), dict)
                ]
                if not cut_recs:
                    issues.append(f"{s['shot_id']} cutaway shot missing layered cutaway telemetry")
                else:
                    cutaway_checks += 1
                    min_layers = min(
                        int(
                            (r["telemetry"]["cutaway"]).get(
                                "layers_count",
                                3 if (r["telemetry"]["cutaway"]).get("has_clip_plane") else 0,
                            )
                        )
                        for r in cut_recs
                    )
                    min_comps = min(
                        int(
                            (r["telemetry"]["cutaway"]).get(
                                "components_count",
                                (r["telemetry"]["cutaway"]).get("internal_component_count", 0),
                            )
                        )
                        for r in cut_recs
                    )
                    if min_layers < 3 or min_comps < 2:
                        issues.append(f"{s['shot_id']} cutaway telemetry insufficient depth (layers={min_layers}, components={min_comps})")

    return {
        "status": "FAIL" if issues else "PASS",
        "worst_pos_err_m": camera_trace_doc.get("worst_pos_err_m"),
        "worst_ori_err_deg": camera_trace_doc.get("worst_ori_err_deg"),
        "worst_fov_err_deg": camera_trace_doc.get("worst_fov_err_deg"),
        "sampled_frames": camera_trace_doc.get("sampled_frames", 0),
        "contact_checks": contact_checks,
        "worst_contact_err_m": round(worst_contact_err, 5) if worst_contact_err is not None else None,
        "cutaway_checks": cutaway_checks,
        "issues": issues,
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
    max_static_hold_sec: Optional[float] = None,
    camera_trace_doc: Optional[Dict[str, Any]] = None,
    raw_traces: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Execute complete STEP 6 Scene Diversity, Camera Execution & Transition QA."""
    shots = list(storyboard.get("shots", []))
    selected_skill = str(storyboard.get("selected_skill") or "zach-d-films")
    fps = int(storyboard.get("fps", 30))
    dur = float(storyboard.get("total_duration_sec", 0.0))
    edit_energy = str(storyboard.get("edit_energy", "balanced"))
    effective_hold_limit = max_static_hold_sec if max_static_hold_sec is not None else storyboard.get("max_static_hold_sec")

    if camera_trace_doc is None and (run_dir / "camera_execution_trace.json").exists():
        camera_trace_doc = json.loads((run_dir / "camera_execution_trace.json").read_text(encoding="utf-8"))
    if raw_traces is None and (run_dir / "logs" / "raw_render_telemetry.json").exists():
        raw_doc = json.loads((run_dir / "logs" / "raw_render_telemetry.json").read_text(encoding="utf-8"))
        raw_traces = list(raw_doc.get("traces") or [])

    if not video_mp4.exists() or video_mp4.stat().st_size == 0:
        report = {
            "schema_version": "sd-scene-diversity-qa-2",
            "overall_status": "FAIL",
            "subjective_visual_review": "NOT_VERIFIED",
            "reason": f"Missing or zero-byte deliverable MP4: {video_mp4}",
        }
        (run_dir / "scene_diversity_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    fingerprints = build_shot_semantic_fingerprints(shots)
    perc = sample_perceptual_frames(video_mp4, shots, mask_captions=True)
    timeline_4hz = _decode_timeline_4hz(video_mp4)

    rep_audit = detect_adjacent_repetitions(
        shots=shots,
        fingerprints=fingerprints,
        perceptual_pairs=perc["adjacent_pairs"],
        all_pairs=perc.get("all_pairs"),
        selected_skill=selected_skill,
    )
    motion_audit = audit_intra_shot_motion(
        perceptual_samples=perc["samples"],
        shots=shots,
        selected_skill=selected_skill,
        edit_energy=edit_energy,
        max_static_hold_sec=effective_hold_limit,
        timeline_4hz=timeline_4hz,
    )
    trans_audit = audit_transition_continuity(
        video_mp4=video_mp4,
        transition_edl=transition_edl,
        shots=shots,
        selected_skill=selected_skill,
        fps=fps,
        raw_traces=raw_traces,
    )
    cam_exec_audit = audit_camera_execution(
        storyboard=storyboard,
        perceptual_samples=perc["samples"],
        camera_trace_doc=camera_trace_doc,
        raw_traces=raw_traces,
        selected_skill=selected_skill,
    )
    novelty_audit = audit_scene_novelty(
        shots=shots,
        fingerprints=fingerprints,
        selected_skill=selected_skill,
        duration_sec=dur,
    )
    skill_lock_check = audit_visual_skill_lock(style_lock_status, selected_skill)

    report_path = (run_dir / "scene_diversity_report.json").resolve()
    if transition_edl is not None:
        finalize_transition_edl_verification(
            transition_edl,
            list(trans_audit.get("details") or []),
            evidence_path=str(report_path),
        )
        (run_dir / "transition_edl.json").write_text(json.dumps(transition_edl, ensure_ascii=False, indent=2), encoding="utf-8")

    statuses = [
        rep_audit["status"],
        motion_audit["status"],
        trans_audit["status"],
        cam_exec_audit["status"],
        novelty_audit["status"],
        skill_lock_check["status"],
    ]
    overall = "FAIL" if ("FAIL" in statuses or "NOT_VERIFIED" in statuses) else ("WARN" if "WARN" in statuses else "PASS")

    # Emit visual_qc_timeline.json + selective failure thumbnails ONLY when flagged
    qc_flags_dir = run_dir / "logs" / "qc_flags"
    flag_thumbs: List[str] = []
    if overall == "FAIL" or motion_audit.get("frozen_shots") or trans_audit.get("issues"):
        qc_flags_dir.mkdir(parents=True, exist_ok=True)
        for idx, s in enumerate(shots):
            sid = s["shot_id"]
            if any(sid in msg for msg in motion_audit.get("frozen_shots", [])):
                arr = perc["shot_arrays"][idx][1]
                out_p = qc_flags_dir / f"flag_{sid}.jpg"
                Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(out_p, quality=85)
                flag_thumbs.append(str(out_p))

    qc_timeline = {
        "schema_version": "sd-visual-qc-timeline-1",
        "overall_status": overall,
        "selected_skill": selected_skill,
        "max_static_hold_sec_limit": motion_audit["max_static_hold_sec_limit"],
        "max_dead_hold_sec_observed": motion_audit["max_dead_hold_sec_observed"],
        "camera_execution_summary": cam_exec_audit,
        "per_shot": [
            {
                "shot_id": s["shot_id"],
                "start": s["start"],
                "end": s["end"],
                "setup_type": s.get("setup_type"),
                "representation": s.get("representation"),
                "intra_mad_masked": perc["samples"][idx]["intra_mad_masked"],
                "intra_mad_roi": perc["samples"][idx]["intra_mad_roi"],
                "dhash_mid": perc["samples"][idx]["dhash_mid"],
            }
            for idx, s in enumerate(shots)
        ],
        "transitions": trans_audit.get("details", []),
        "flagged_thumbnails": flag_thumbs,
    }
    (run_dir / "visual_qc_timeline.json").write_text(json.dumps(qc_timeline, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "schema_version": "sd-scene-diversity-qa-2",
        "overall_status": overall,
        "subjective_visual_review": "NOT_VERIFIED",
        "subjective_review_note": "Machine perceptual pHash/SSIM, non-adjacent dedup, 4Hz motion, camera telemetry, and multi-frame transition checks ran on decoded frames; manual creative playback remains NOT_VERIFIED.",
        "selected_skill": selected_skill,
        "checks": {
            "visual_skill_lock": skill_lock_check,
            "adjacent_repetition_guard": rep_audit,
            "intra_shot_motion": motion_audit,
            "transition_continuity": trans_audit,
            "camera_execution_audit": cam_exec_audit,
            "scene_novelty_metrics": novelty_audit,
        },
        "fingerprints": fingerprints,
        "perceptual_samples": perc["samples"],
        "adjacent_perceptual_pairs": perc["adjacent_pairs"],
        "all_perceptual_pairs_count": len(perc.get("all_pairs", [])),
        "visual_qc_timeline_json": str((run_dir / "visual_qc_timeline.json").resolve()),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
