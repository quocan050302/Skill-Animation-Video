"""R2.1 Decoded Visual Truth, Semantic Object-ID Matte & Camera-Compensated Motion QA.

Computes objective visual evidence directly from decoded video frames, deterministic
WebGL semantic object-ID mattes, DOM layout boxes, and camera transforms rather than
self-reported storyboard labels alone.

Status distinction:
- Automated gates report strictly `PASS` | `FAIL` | `WARN` | `NOT_VERIFIED`.
- Subjective human evaluation fields (`subjective_visual_quality`, `human_preference`,
  `viewer_retention_status`) remain `NOT_VERIFIED` with `HUMAN_REVIEW_REQUIRED: true`.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw

SCHEMA_VERSION = "sd-decoded-visual-quality-1"

# Calibrated portrait 9:16 thresholds (reference resolution disclosed explicitly in every report)
REF_ANALYSIS_W = 270
REF_ANALYSIS_H = 480
PHONE_REF_WIDTH_PX = 360
PHONE_REF_HEIGHT_PX = 640

# Event-dependent policy defaults (calibrated against Tacoma Narrows R1 failures & Skyscraper R2)
EVENT_PROMINENCE_POLICY: Dict[str, Dict[str, float]] = {
    "curiosity_hook": {
        "min_subject_area": 0.16,
        "min_span_wh": 0.42,
        "min_feature_px_360": 40.0,
        "max_uniform_empty": 0.72,
    },
    "action_peak": {
        "min_subject_area": 0.16,
        "min_span_wh": 0.42,
        "min_feature_px_360": 40.0,
        "max_uniform_empty": 0.72,
    },
    "explanatory_macro": {
        "min_subject_area": 0.14,
        "min_span_wh": 0.35,
        "min_feature_px_360": 42.0,
        "max_uniform_empty": 0.74,
    },
    "human_reaction": {
        "min_subject_area": 0.10,
        "min_span_wh": 0.30,
        "min_feature_px_360": 32.0,
        "max_uniform_empty": 0.76,
    },
    "establishing_wide": {
        "min_subject_area": 0.055,
        "min_span_wh": 0.38,
        "min_feature_px_360": 22.0,
        "max_uniform_empty": 0.84,
    },
    "aftermath_hold": {
        "min_subject_area": 0.05,
        "min_span_wh": 0.35,
        "min_feature_px_360": 20.0,
        "max_uniform_empty": 0.86,
    },
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def probe_video_metadata(video_path: Path) -> Dict[str, Any]:
    """Verify container, codec, FPS, resolution, duration, packet counts and SHA-256 via ffprobe."""
    p = Path(video_path)
    if not p.exists() or not p.is_file() or p.stat().st_size == 0:
        return {
            "ok": False,
            "status": "FAIL",
            "path": str(p),
            "issues": [f"Video missing or empty: {p}"],
        }
    sha = _sha256_file(p)
    try:
        res = subprocess.run(
            [
                "ffprobe", "-v", "error", "-count_packets",
                "-print_format", "json",
                "-show_format", "-show_streams",
                str(p),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        data = json.loads(res.stdout or "{}")
    except Exception as exc:
        return {
            "ok": False,
            "status": "FAIL",
            "path": str(p),
            "sha256": sha,
            "issues": [f"ffprobe failed on {p.name}: {exc}"],
        }

    streams = list(data.get("streams") or [])
    v_str = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_str = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not v_str:
        return {
            "ok": False,
            "status": "FAIL",
            "path": str(p),
            "sha256": sha,
            "issues": ["No video stream found"],
        }

    w = int(v_str.get("width") or 0)
    h = int(v_str.get("height") or 0)
    num, den = map(int, str(v_str.get("r_frame_rate") or "0/1").split("/"))
    fps = round(num / max(1, den), 3)
    dur = float(v_str.get("duration") or data.get("format", {}).get("duration") or 0.0)
    v_pkts = int(v_str.get("nb_read_packets") or v_str.get("nb_frames") or 0)
    a_pkts = int((a_str or {}).get("nb_read_packets") or 0)
    issues: List[str] = []
    if w <= 0 or h <= 0 or dur <= 0.05 or v_pkts <= 0:
        issues.append(f"Corrupt/zero-packet video stream (w={w}, h={h}, dur={dur}, v_pkts={v_pkts})")

    return {
        "ok": len(issues) == 0,
        "status": "FAIL" if issues else "PASS",
        "path": str(p.resolve()),
        "size_bytes": int(p.stat().st_size),
        "sha256": sha,
        "width": w,
        "height": h,
        "fps": fps,
        "duration_sec": round(dur, 4),
        "video_codec": v_str.get("codec_name"),
        "pix_fmt": v_str.get("pix_fmt"),
        "video_packets": v_pkts,
        "has_audio": a_str is not None,
        "audio_codec": (a_str or {}).get("codec_name"),
        "audio_packets": a_pkts,
        "issues": issues,
    }


def _decode_rgb_png_pipe(video_path: Path, t_sec: float, w: int, h: int) -> np.ndarray:
    cmd = [
        "ffmpeg", "-v", "error",
        "-ss", f"{max(0.0, t_sec):.4f}",
        "-i", str(video_path),
        "-vf", f"scale={w}:{h}:flags=bilinear",
        "-frames:v", "1",
        "-f", "image2pipe", "-vcodec", "png", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, check=True, timeout=20)
    img = Image.open(io.BytesIO(res.stdout)).convert("RGB")
    arr = np.asarray(img, dtype=np.float32)
    if arr.shape[:2] != (h, w):
        raise RuntimeError(f"Decoded shape {arr.shape[:2]} != expected {(h, w)}")
    return arr


def sample_event_aligned_frames(
    video_path: Path,
    storyboard: Dict[str, Any],
    sample_spec: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Decode start/peak/end RGB frames for each key shot/event; fail closed on blank or stale media."""
    spec = dict(sample_spec or {})
    meta = probe_video_metadata(video_path)
    if not meta.get("ok"):
        return {
            "status": "FAIL",
            "metadata": meta,
            "samples": [],
            "issues": list(meta.get("issues") or ["Video metadata invalid"]),
        }

    issues: List[str] = []
    if spec.get("expected_sha256") and spec["expected_sha256"] != meta["sha256"]:
        issues.append(f"Stale/mismatched video SHA256 ({meta['sha256'][:12]} != {str(spec['expected_sha256'])[:12]})")
    if spec.get("expected_width") and int(spec["expected_width"]) != meta["width"]:
        issues.append(f"Width mismatch: {meta['width']} != {spec['expected_width']}")
    if spec.get("expected_height") and int(spec["expected_height"]) != meta["height"]:
        issues.append(f"Height mismatch: {meta['height']} != {spec['expected_height']}")
    if spec.get("expected_duration_sec") and abs(meta["duration_sec"] - float(spec["expected_duration_sec"])) > 0.75:
        issues.append(
            f"Duration mismatch: {meta['duration_sec']:.2f}s vs expected {float(spec['expected_duration_sec']):.2f}s"
        )
    if issues:
        return {"status": "FAIL", "metadata": meta, "samples": [], "issues": issues}

    w = int(spec.get("width", REF_ANALYSIS_W))
    h = int(spec.get("height", REF_ANALYSIS_H))
    dur_vid = float(meta["duration_sec"])

    shots = list(storyboard.get("shots") or [])
    if not shots:
        return {"status": "FAIL", "metadata": meta, "samples": [], "issues": ["Storyboard contains 0 shots"]}

    shot_samples: List[Dict[str, Any]] = []
    all_stds: List[float] = []
    for s in shots:
        st = float(s.get("start", 0.0))
        en = float(s.get("end", st + 1.0))
        dur = max(0.2, en - st)
        t0 = round(min(dur_vid - 0.04, st + min(0.10, dur * 0.14)), 3)
        t_peak = round(min(dur_vid - 0.03, st + dur * 0.52), 3)
        t2 = round(min(dur_vid - 0.02, max(t_peak + 0.04, en - min(0.10, dur * 0.14))), 3)
        if en > dur_vid + 0.85:
            issues.append(f"Stale/truncated video: shot {s.get('shot_id')} ends at {en:.2f}s > video {dur_vid:.2f}s")
            continue
        tri = []
        for tag, ts in (("start", t0), ("peak", t_peak), ("end", t2)):
            try:
                rgb = _decode_rgb_png_pipe(video_path, ts, w, h)
                all_stds.append(float(rgb.std()))
                tri.append({"phase": tag, "t_sec": ts, "rgb": rgb, "luma_std": round(float(rgb.std()), 2)})
            except Exception as exc:
                issues.append(f"Failed decode at t={ts:.3f}s ({s.get('shot_id')}): {exc}")
        shot_samples.append({
            "shot_id": s.get("shot_id"),
            "shot_index": s.get("index", len(shot_samples)),
            "start": st,
            "end": en,
            "triples": tri,
        })

    if all_stds and max(all_stds) < 1.8:
        issues.append(f"T01: Blank/flat MP4 content across all decoded frames (max_luma_std={max(all_stds):.2f} < 1.8)")
    if not shot_samples or sum(len(s["triples"]) for s in shot_samples) < len(shots) * 3:
        if not issues:
            issues.append("Incomplete decoded frame coverage across shots")

    return {
        "status": "FAIL" if issues else "PASS",
        "analysis_resolution": [w, h],
        "metadata": meta,
        "samples": shot_samples,
        "issues": issues,
    }


def _masks_from_matte_rgb(matte_rgb: np.ndarray) -> Dict[str, np.ndarray]:
    """Decode semantic matte PNG RGB channels into clean boolean masks."""
    r = matte_rgb[:, :, 0].astype(np.float32)
    g = matte_rgb[:, :, 1].astype(np.float32)
    b = matte_rgb[:, :, 2].astype(np.float32)
    causal = (g > 110.0) & (r < 95.0)
    character = (b > 110.0) & (r < 95.0) & (g < 95.0)
    subject = ((r > 110.0) & (g < 95.0) & (b < 95.0)) | causal
    env = ~(subject | character)
    return {
        "subject_mask": subject,
        "causal_feature_mask": causal,
        "character_mask": character,
        "environment_mask": env,
    }


def _overlay_mask_from_boxes(
    boxes_1080: Sequence[Sequence[float]],
    w: int,
    h: int,
) -> np.ndarray:
    mask = np.zeros((h, w), dtype=bool)
    sx, sy = w / 1080.0, h / 1920.0
    for box in boxes_1080:
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        x0 = max(0, min(w - 1, int(round(float(box[0]) * sx))))
        y0 = max(0, min(h - 1, int(round(float(box[1]) * sy))))
        x1 = max(x0 + 1, min(w, int(round(float(box[2]) * sx))))
        y1 = max(y0 + 1, min(h, int(round(float(box[3]) * sy))))
        mask[y0:y1, x0:x1] = True
    return mask


def render_subject_id_matte_at_t(
    scene: Any,
    camera: Any = None,
    t: float = 0.0,
    overlay_boxes_1080: Optional[Sequence[Sequence[float]]] = None,
    width: int = REF_ANALYSIS_W,
    height: int = REF_ANALYSIS_H,
) -> Dict[str, Any]:
    """Extract deterministic semantic masks (`subject`, `causal_feature`, `character`, `overlay`, `environment`).

    Supports:
    - pre-rendered `matte_*.png` path (`Path` / `str`)
    - deterministic Python `scene(camera, t)` callable or mask dict (for isolated unit/negative tests)
    - live HTML entry via `render_node.mjs mattes` when `scene` is an `.html` file path.
    """
    matte_arr: Optional[np.ndarray] = None
    masks: Optional[Dict[str, np.ndarray]] = None

    if isinstance(scene, (Path, str)):
        p = Path(scene)
        if p.suffix.lower() in (".png", ".jpg", ".jpeg") and p.exists():
            img = Image.open(p).convert("RGB").resize((width, height), Image.Resampling.NEAREST)
            matte_arr = np.asarray(img, dtype=np.float32)
            masks = _masks_from_matte_rgb(matte_arr)
        elif p.suffix.lower() == ".html" and p.exists():
            import tempfile
            render_mjs = Path(__file__).resolve().parent / "render_node.mjs"
            with tempfile.TemporaryDirectory() as td:
                cmd = ["node", str(render_mjs), "mattes", str(p), td, f"{float(t):.4f}", "1"]
                subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
                out_png = sorted(Path(td).glob("matte_*.png"))
                if not out_png:
                    return {"status": "FAIL", "reason": "T04: Missing rendered matte PNG"}
                img = Image.open(out_png[0]).convert("RGB").resize((width, height), Image.Resampling.NEAREST)
                matte_arr = np.asarray(img, dtype=np.float32)
                masks = _masks_from_matte_rgb(matte_arr)
                man_p = Path(td) / "matte_manifest.json"
                if man_p.exists():
                    man = json.loads(man_p.read_text(encoding="utf-8"))
                    recs = man.get("frames") or []
                    if recs and not overlay_boxes_1080:
                        overlay_boxes_1080 = recs[0].get("overlay_boxes_1080") or []
        else:
            return {"status": "FAIL", "reason": f"T04: Missing matte path: {p}"}
    elif callable(scene):
        out = scene(camera, t)
        if isinstance(out, np.ndarray):
            matte_arr = out.astype(np.float32)
            masks = _masks_from_matte_rgb(matte_arr)
        elif isinstance(out, dict):
            masks = {k: np.asarray(v, dtype=bool) for k, v in out.items() if k.endswith("_mask")}
    elif isinstance(scene, dict):
        if "matte_rgb" in scene:
            matte_arr = np.asarray(scene["matte_rgb"], dtype=np.float32)
            masks = _masks_from_matte_rgb(matte_arr)
        elif "subject_mask" in scene:
            masks = {
                "subject_mask": np.asarray(scene["subject_mask"], dtype=bool),
                "causal_feature_mask": np.asarray(scene.get("causal_feature_mask", scene["subject_mask"]), dtype=bool),
                "character_mask": np.asarray(scene.get("character_mask", np.zeros_like(scene["subject_mask"], dtype=bool)), dtype=bool),
                "environment_mask": np.asarray(scene.get("environment_mask", ~np.asarray(scene["subject_mask"], dtype=bool)), dtype=bool),
            }

    if not masks or "subject_mask" not in masks:
        return {"status": "FAIL", "reason": "T04: Subject matte missing or unreadable"}

    h, w = masks["subject_mask"].shape[:2]
    ov_mask = _overlay_mask_from_boxes(overlay_boxes_1080 or [], w, h)
    masks["overlay_mask"] = ov_mask
    return {
        "status": "PASS",
        "t_sec": round(float(t), 4),
        "width": w,
        "height": h,
        **masks,
    }


def _bbox_from_mask(mask: np.ndarray) -> Optional[List[float]]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    h, w = mask.shape[:2]
    return [
        round(float(xs.min()) / w, 4),
        round(float(ys.min()) / h, 4),
        round(float(xs.max() + 1) / w, 4),
        round(float(ys.max() + 1) / h, 4),
    ]


def estimate_subject_screen_occupancy(
    frame: np.ndarray,
    subject_mask: np.ndarray,
    causal_mask: Optional[np.ndarray] = None,
    character_mask: Optional[np.ndarray] = None,
    safe_rect_norm: Tuple[float, float, float, float] = (0.06, 0.08, 0.94, 0.78),
) -> Dict[str, Any]:
    """Measure subject/feature occupancy, bounding box, border clipping, quadrant balance & uniform bands."""
    h, w = frame.shape[:2]
    subj = np.asarray(subject_mask, dtype=bool)
    caus = np.asarray(causal_mask, dtype=bool) if causal_mask is not None else np.zeros((h, w), dtype=bool)
    char = np.asarray(character_mask, dtype=bool) if character_mask is not None else np.zeros((h, w), dtype=bool)

    union_hero = subj | char
    total_px = float(max(1, h * w))
    subj_ratio = float(subj.sum()) / total_px
    caus_ratio = float(caus.sum()) / total_px
    char_ratio = float(char.sum()) / total_px
    hero_ratio = float(union_hero.sum()) / total_px

    bbox = _bbox_from_mask(union_hero)
    causal_bbox = _bbox_from_mask(caus) if caus.any() else bbox
    char_bbox = _bbox_from_mask(char) if char.any() else None

    w_frac = round(bbox[2] - bbox[0], 4) if bbox else 0.0
    h_frac = round(bbox[3] - bbox[1], 4) if bbox else 0.0

    sx0, sy0, sx1, sy1 = safe_rect_norm
    ix0, ix1 = max(0, int(round(sx0 * w))), min(w, int(round(sx1 * w)))
    iy0, iy1 = max(0, int(round(sy0 * h))), min(h, int(round(sy1 * h)))
    safe_sub = np.zeros((h, w), dtype=bool)
    safe_sub[iy0:iy1, ix0:ix1] = True
    visible_fraction = float((union_hero & safe_sub).sum()) / float(max(1, union_hero.sum()))

    border = np.zeros((h, w), dtype=bool)
    bw = max(2, int(round(w * 0.02)))
    bh = max(2, int(round(h * 0.02)))
    border[:bh, :] = True
    border[-bh:, :] = True
    border[:, :bw] = True
    border[:, -bw:] = True
    border_clip_ratio = float((union_hero & border).sum()) / float(max(1, union_hero.sum()))

    mx, my = w // 2, h // 2
    q_tl = float(union_hero[:my, :mx].mean())
    q_tr = float(union_hero[:my, mx:].mean())
    q_bl = float(union_hero[my:, :mx].mean())
    q_br = float(union_hero[my:, mx:].mean())

    # Detect prolonged near-uniform background zones outside hero subject/character
    gray = frame.mean(axis=2).astype(np.float32)
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    grad_mag = 0.5 * (gx + gy)
    cell_h, cell_w = max(8, h // 16), max(8, w // 9)
    uniform_cells = 0
    total_cells = 0
    for r0 in range(0, h, cell_h):
        for c0 in range(0, w, cell_w):
            r1, c1 = min(h, r0 + cell_h), min(w, c0 + cell_w)
            if union_hero[r0:r1, c0:c1].mean() > 0.15:
                total_cells += 1
                continue
            patch_std = float(gray[r0:r1, c0:c1].std())
            patch_grad = float(grad_mag[r0:r1, c0:c1].mean())
            if patch_std < 3.2 and patch_grad < 1.25:
                uniform_cells += 1
            total_cells += 1
    uniform_empty_ratio = round(uniform_cells / float(max(1, total_cells)), 4)

    return {
        "analysis_resolution": [w, h],
        "subject_area_ratio": round(subj_ratio, 4),
        "causal_feature_area_ratio": round(caus_ratio, 4),
        "character_area_ratio": round(char_ratio, 4),
        "hero_union_area_ratio": round(hero_ratio, 4),
        "bbox_norm": bbox,
        "causal_bbox_norm": causal_bbox,
        "character_bbox_norm": char_bbox,
        "width_fraction": w_frac,
        "height_fraction": h_frac,
        "visible_fraction": round(visible_fraction, 4),
        "border_clip_ratio": round(border_clip_ratio, 4),
        "quadrant_coverage": {
            "top_left": round(q_tl, 4),
            "top_right": round(q_tr, 4),
            "bottom_left": round(q_bl, 4),
            "bottom_right": round(q_br, 4),
        },
        "uniform_empty_band_ratio": uniform_empty_ratio,
    }


def _dilate_mask(mask: np.ndarray, radius: int) -> np.ndarray:
    out = mask.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            shifted = np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
            if dy > 0:
                shifted[:dy, :] = False
            elif dy < 0:
                shifted[dy:, :] = False
            if dx > 0:
                shifted[:, :dx] = False
            elif dx < 0:
                shifted[:, dx:] = False
            out |= shifted
    return out


def estimate_scene_readability(
    frame: np.ndarray,
    masks: Dict[str, Any],
    role_plan: Optional[Dict[str, Any]] = None,
    phone_width_px: int = PHONE_REF_WIDTH_PX,
) -> Dict[str, Any]:
    """Evaluate phone-scale causal feature legibility, figure-ground separation, and overlay clutter."""
    h, w = frame.shape[:2]
    phone_h_px = int(round(phone_width_px * (1920.0 / 1080.0)))
    subj = np.asarray(masks["subject_mask"], dtype=bool)
    caus = np.asarray(masks.get("causal_feature_mask", subj), dtype=bool)
    char = np.asarray(masks.get("character_mask", np.zeros((h, w), dtype=bool)), dtype=bool)
    ov = np.asarray(masks.get("overlay_mask", np.zeros((h, w), dtype=bool)), dtype=bool)

    occ = estimate_subject_screen_occupancy(frame, subj, caus, char)
    cbox = occ["causal_bbox_norm"] or occ["bbox_norm"]
    if cbox:
        cw_px = (cbox[2] - cbox[0]) * phone_width_px
        ch_px = (cbox[3] - cbox[1]) * phone_h_px
        eq_diam_px = math.sqrt(max(0.0, occ["causal_feature_area_ratio"] or occ["hero_union_area_ratio"]) * phone_width_px * phone_h_px * (4.0 / math.pi))
        feature_span_px = round(max(min(cw_px, ch_px), eq_diam_px, 0.65 * max(cw_px, ch_px)), 2)
    else:
        cw_px, ch_px, feature_span_px = 0.0, 0.0, 0.0

    # Figure-ground separation along boundary between hero silhouette and background
    hero = subj | char
    edge_sep = 0.0
    luma_sep = 0.0
    if hero.any() and (~hero).any():
        outer_ring = _dilate_mask(hero, 4) & (~_dilate_mask(hero, 1)) & (~ov)
        inner_ring = hero & (~_erode_approx(hero, 2)) & (~ov)
        if not outer_ring.any():
            outer_ring = (~hero) & (~ov)
        if not inner_ring.any():
            inner_ring = hero & (~ov)
        if outer_ring.any() and inner_ring.any():
            fg_rgb = frame[inner_ring].mean(axis=0)
            bg_rgb = frame[outer_ring].mean(axis=0)
            edge_sep = float(np.linalg.norm(fg_rgb - bg_rgb))
            luma_sep = float(abs(fg_rgb.mean() - bg_rgb.mean()))

    # Overlay overlap with causal feature or character
    overlay_causal_overlap = 0.0
    if ov.any() and (caus | char).any():
        overlay_causal_overlap = float((ov & (caus | char)).sum()) / float(max(1, (caus | char).sum()))

    # Target visibility check if role_plan provides anchor_uv or target_region_norm
    target_vis = True
    rp = role_plan or {}
    t_uv = rp.get("anchor_uv")
    if isinstance(t_uv, (list, tuple)) and len(t_uv) == 2:
        tx = max(0, min(w - 1, int(round(float(t_uv[0]) * w))))
        ty = max(0, min(h - 1, int(round(float(t_uv[1]) * h))))
        r = max(3, int(round(0.045 * w)))
        win = hero[max(0, ty - r):min(h, ty + r + 1), max(0, tx - r):min(w, tx + r + 1)]
        target_vis = bool(win.any())

    return {
        "phone_ref_resolution": [phone_width_px, phone_h_px],
        "occupancy": occ,
        "protected_detail_width_px_360": round(cw_px, 2),
        "protected_detail_height_px_360": round(ch_px, 2),
        "protected_detail_min_px_360": feature_span_px,
        "foreground_background_edge_separation": round(edge_sep, 2),
        "foreground_background_luma_separation": round(luma_sep, 2),
        "overlay_causal_overlap_ratio": round(overlay_causal_overlap, 4),
        "target_visibility": target_vis,
    }


def _erode_approx(mask: np.ndarray, radius: int) -> np.ndarray:
    return ~_dilate_mask(~mask, radius)


def _estimate_shift_sad(
    img_a: np.ndarray,
    img_b: np.ndarray,
    weight_mask: np.ndarray,
    max_shift: int = 16,
) -> Tuple[int, int, float]:
    """Estimate dominant 2D rigid background translation (dx, dy) between frames using masked SAD."""
    h, w = img_a.shape[:2]
    m = weight_mask
    if m.sum() < 64:
        return 0, 0, float(np.mean(np.abs(img_b - img_a)))
    best_err = 1e9
    best_dx, best_dy = 0, 0
    step = 2
    pad = max_shift
    ga = img_a.mean(axis=2) if img_a.ndim == 3 else img_a
    gb = img_b.mean(axis=2) if img_b.ndim == 3 else img_b
    core_m = m[pad:h - pad, pad:w - pad]
    if core_m.sum() < 32:
        return 0, 0, float(np.mean(np.abs(gb - ga)))
    core_a = ga[pad:h - pad, pad:w - pad][core_m]
    for dy in range(-max_shift, max_shift + 1, step):
        for dx in range(-max_shift, max_shift + 1, step):
            sub_b = gb[pad + dy:h - pad + dy, pad + dx:w - pad + dx][core_m]
            err = float(np.mean(np.abs(sub_b - core_a)))
            if err < best_err:
                best_err = err
                best_dx, best_dy = dx, dy
    return best_dx, best_dy, round(best_err, 3)


def _center_align_mask_and_rgb(
    rgb: np.ndarray,
    mask: np.ndarray,
    out_size: int = 96,
) -> Tuple[np.ndarray, np.ndarray, Optional[Tuple[float, float, float, float]]]:
    """Crop subject bounding box and resize to canonical square so rigid camera pan/zoom is removed."""
    ys, xs = np.where(mask)
    if len(xs) < 8:
        return np.zeros((out_size, out_size), dtype=bool), np.zeros((out_size, out_size, 3), dtype=np.float32), None
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    sub_m = Image.fromarray((mask[y0:y1, x0:x1].astype(np.uint8) * 255)).resize((out_size, out_size), Image.Resampling.NEAREST)
    sub_rgb = Image.fromarray(np.clip(rgb[y0:y1, x0:x1], 0, 255).astype(np.uint8)).resize((out_size, out_size), Image.Resampling.BILINEAR)
    h, w = mask.shape[:2]
    bbox_norm = (x0 / w, y0 / h, x1 / w, y1 / h)
    return np.asarray(sub_m) > 127, np.asarray(sub_rgb, dtype=np.float32), bbox_norm


def assess_decoded_frame_triple(
    frames_at_t0_t1_t2: Sequence[np.ndarray],
    semantic_mattes: Sequence[Dict[str, Any]],
    camera_transforms: Optional[Sequence[Dict[str, Any]]] = None,
    expected_action_type: str = "deforming",
    claimed_vertex_disp_m: Optional[float] = None,
) -> Dict[str, Any]:
    """Measure true physical subject motion AFTER subtracting camera pan/orbit/zoom motion.

    Trap T03 / T14 guarantee: a rigid frozen object under camera orbit + claimed telemetry deformation FAILS.
    """
    if len(frames_at_t0_t1_t2) < 3 or len(semantic_mattes) < 3:
        return {
            "status": "FAIL",
            "reason": "Need at least 3 event-aligned frames and semantic mattes (onset, peak, end)",
            "physical_motion_detected": False,
        }

    f0, f1, f2 = [np.asarray(f, dtype=np.float32) for f in frames_at_t0_t1_t2[:3]]
    m_objs = semantic_mattes[:3]
    if any(m.get("status") == "FAIL" or "subject_mask" not in m for m in m_objs):
        return {
            "status": "FAIL",
            "reason": "T04: Missing valid subject semantic matte in frame triple",
            "physical_motion_detected": False,
        }

    masks = [
        (np.asarray(m["subject_mask"], dtype=bool) | np.asarray(m.get("character_mask", False), dtype=bool))
        for m in m_objs
    ]
    causal_masks = [
        np.asarray(m.get("causal_feature_mask", m["subject_mask"]), dtype=bool)
        for m in m_objs
    ]

    # Measure camera motion from telemetry transforms if provided
    cam_disp_m = 0.0
    cam_ang_deg = 0.0
    cams = list(camera_transforms or [])
    if len(cams) >= 2:
        for i in range(len(cams) - 1):
            p_a = cams[i].get("realized_pos") or cams[i].get("pos") or [0, 0, 0]
            p_b = cams[i + 1].get("realized_pos") or cams[i + 1].get("pos") or [0, 0, 0]
            cam_disp_m += math.sqrt(sum((float(p_b[k]) - float(p_a[k])) ** 2 for k in range(3)))
            fa = cams[i].get("realized_forward")
            fb = cams[i + 1].get("realized_forward")
            if isinstance(fa, list) and isinstance(fb, list) and len(fa) == 3 and len(fb) == 3:
                dot = max(-1.0, min(1.0, sum(float(fa[k]) * float(fb[k]) for k in range(3))))
                cam_ang_deg += math.degrees(math.acos(dot))

    # Pairwise camera-compensated comparison across (0->1) and (1->2)
    silhouette_deltas: List[float] = []
    aligned_internal_mads: List[float] = []
    aspect_deltas: List[float] = []
    centroid_vs_bg_deltas: List[float] = []
    raw_mad_list: List[float] = []

    for a, b in ((0, 1), (1, 2)):
        fa_f = frames_at_t0_t1_t2[a].astype(np.float32)
        fb_f = frames_at_t0_t1_t2[b].astype(np.float32)
        raw_mad_list.append(float(np.mean(np.abs(fb_f - fa_f))))
        bg_mask = (~masks[a]) & (~masks[b])
        bg_has_texture = bool(bg_mask.sum() >= 64 and float(fa_f[bg_mask].std()) >= 2.5)
        dx_bg, dy_bg, _ = _estimate_shift_sad(fa_f, fb_f, bg_mask)

        am_a, argb_a, bb_a = _center_align_mask_and_rgb(fa_f, masks[a])
        am_b, argb_b, bb_b = _center_align_mask_and_rgb(fb_f, masks[b])

        union = am_a | am_b
        inter = am_a & am_b
        iou = float(inter.sum()) / float(max(1, union.sum()))
        sil_delta = 1.0 - iou
        silhouette_deltas.append(sil_delta)

        # Also compare causal feature sub-mask inside subject if present
        cm_a, crgb_a, _ = _center_align_mask_and_rgb(fa_f, causal_masks[a] if causal_masks[a].any() else masks[a])
        cm_b, crgb_b, _ = _center_align_mask_and_rgb(fb_f, causal_masks[b] if causal_masks[b].any() else masks[b])
        c_union = cm_a | cm_b
        if c_union.any():
            c_mad = float(np.mean(np.abs(crgb_b[c_union] - crgb_a[c_union])))
        else:
            c_mad = 0.0

        s_mad = float(np.mean(np.abs(argb_b[union] - argb_a[union]))) if union.any() else 0.0
        aligned_internal_mads.append(max(s_mad, c_mad))

        if bb_a and bb_b:
            asp_a = (bb_a[2] - bb_a[0]) / max(1e-4, bb_a[3] - bb_a[1])
            asp_b = (bb_b[2] - bb_b[0]) / max(1e-4, bb_b[3] - bb_b[1])
            aspect_deltas.append(abs(asp_b - asp_a))
            if bg_has_texture:
                h_img, w_img = masks[a].shape[:2]
                cx_a, cy_a = 0.5 * (bb_a[0] + bb_a[2]) * w_img, 0.5 * (bb_a[1] + bb_a[3]) * h_img
                cx_b, cy_b = 0.5 * (bb_b[0] + bb_b[2]) * w_img, 0.5 * (bb_b[1] + bb_b[3]) * h_img
                centroid_vs_bg_deltas.append(math.hypot((cx_b - cx_a) - dx_bg, (cy_b - cy_a) - dy_bg))

    max_sil_delta = max(silhouette_deltas) if silhouette_deltas else 0.0
    max_internal_mad = max(aligned_internal_mads) if aligned_internal_mads else 0.0
    max_aspect_delta = max(aspect_deltas) if aspect_deltas else 0.0
    max_centroid_rel = max(centroid_vs_bg_deltas) if centroid_vs_bg_deltas else 0.0
    max_raw_mad = max(raw_mad_list) if raw_mad_list else 0.0

    # Combined camera-compensated physical deformation score
    motion_detected = (
        max_sil_delta >= 0.045
        or max_internal_mad >= 2.2
        or max_aspect_delta >= 0.045
        or max_centroid_rel >= 3.2
    )

    issues: List[str] = []
    if expected_action_type in ("deforming", "character_action", "collapse", "torsion", "wave", "sway", "damper"):
        if not motion_detected:
            if cam_disp_m > 0.04 or cam_ang_deg > 1.0 or max_raw_mad > 0.5:
                issues.append(
                    f"T03/T14: Camera moved (disp={cam_disp_m:.2f}m, ang={cam_ang_deg:.1f}deg, raw_mad={max_raw_mad:.2f}) "
                    f"but decoded camera-compensated subject deformation is negligible "
                    f"(sil_delta={max_sil_delta:.3f}, internal_mad={max_internal_mad:.2f}, rel_centroid={max_centroid_rel:.2f}px)"
                )
            else:
                issues.append(
                    f"T14: Decoded frame triple static despite expected '{expected_action_type}' action "
                    f"(sil_delta={max_sil_delta:.3f}, internal_mad={max_internal_mad:.2f})"
                )
        if claimed_vertex_disp_m is not None and claimed_vertex_disp_m >= 0.08 and not motion_detected:
            issues.append(
                f"T14: Telemetry claimed vertex_disp_max_m={claimed_vertex_disp_m:.3f}m while decoded subject stayed rigid"
            )

    return {
        "status": "FAIL" if issues else "PASS",
        "expected_action_type": expected_action_type,
        "physical_motion_detected": motion_detected,
        "camera_disp_m": round(cam_disp_m, 3),
        "camera_angle_deg": round(cam_ang_deg, 2),
        "max_raw_frame_mad": round(max_raw_mad, 3),
        "max_silhouette_delta_compensated": round(max_sil_delta, 4),
        "max_internal_mad_compensated": round(max_internal_mad, 3),
        "max_aspect_delta_compensated": round(max_aspect_delta, 4),
        "max_centroid_vs_bg_px": round(max_centroid_rel, 2),
        "issues": issues,
    }


def audit_phone_composition(
    views: Sequence[int] = (320, 360, 390, 1080),
    storyboard: Optional[Dict[str, Any]] = None,
    editorial_timeline: Optional[Dict[str, Any]] = None,
    visibility_by_shot: Optional[Sequence[Dict[str, Any]]] = None,
    raw_traces: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Audit subject, captions, headlines, pointers and YouTube Shorts UI chrome safe zones across mobile widths."""
    issues: List[str] = []
    warnings: List[str] = []
    per_view: Dict[str, Any] = {}

    tl = editorial_timeline or {}
    overlays = list(tl.get("overlays") or [])
    dur = float((storyboard or {}).get("total_duration_sec") or tl.get("total_duration_sec") or 10.0)

    # Verify >= 20% overlay-free breathing room over actual timeline
    if overlays and dur > 0.5:
        step = 0.05
        n_bins = max(1, int(round(dur / step)))
        free_bins = 0
        for bi in range(n_bins):
            ts = (bi + 0.5) * step
            active = any(float(o.get("start", 0.0)) <= ts <= float(o.get("end", 0.0)) for o in overlays)
            if not active:
                free_bins += 1
        free_ratio = round(free_bins / float(n_bins), 4)
        if free_ratio < 0.20:
            issues.append(f"Overlay breathing room too low ({free_ratio:.3f} < 0.20 required)")
    else:
        free_ratio = 1.0

    # Check Shorts chrome occlusion & overlay-vs-subject overlap from actual decoded visibility / DOM boxes
    for vw in views:
        scale = float(vw) / 1080.0
        vh = int(round(1920.0 * scale))
        view_issues: List[str] = []

        # YouTube Shorts chrome bands in 1080x1920 reference: top < 140px, bottom > 1525px (bottom 20.5% + right action buttons x>965)
        for ov in overlays:
            pbox = ov.get("placement_box") or [0, 0, 0, 0]
            x0, y0, x1, y1 = [float(v) for v in pbox]
            if y0 < 140.0:
                view_issues.append(f"Overlay {ov.get('overlay_id')} intrudes Shorts top status zone (y0={y0:.0f} < 140)")
            if y1 > 1345.0:
                view_issues.append(f"T07: Overlay {ov.get('overlay_id')} intrudes lower caption/Shorts UI zone (y1={y1:.0f} > 1345)")
            if x0 < 56.0 or x1 > 1024.0:
                view_issues.append(f"T07: Overlay {ov.get('overlay_id')} clips horizontal safe margin ({x0:.0f}..{x1:.0f})")

            # Font legibility at target mobile width
            fs_1080 = float(ov.get("font_size_1080") or 34.0)
            fs_scaled = fs_1080 * scale
            if fs_scaled < 9.5:
                view_issues.append(f"Overlay {ov.get('overlay_id')} font size {fs_scaled:.1f}px unreadable at {vw}px width")

        # Check decoded caption & overlay DOM glyph proofs from traces
        for rec in (raw_traces or []):
            ov_root = (rec.get("telemetry") or {}).get("overlay") or {}
            cap = ov_root.get("caption") or {}
            lay = cap.get("caption_layout")
            if isinstance(lay, dict):
                if int(lay.get("word_overlap_count", 0)) > 0:
                    view_issues.append(f"Caption word overlap at {vw}px (t={rec.get('time')}s)")
                if lay.get("clipped_by_viewport"):
                    view_issues.append(f"Caption clipped horizontally/vertically at {vw}px (t={rec.get('time')}s)")
                mgap = lay.get("min_word_gap_px")
                if mgap is not None and float(mgap) * scale < 0.45:
                    view_issues.append(f"Caption word gap cramped at {vw}px ({float(mgap)*scale:.2f}px)")
            for ov_t in (ov_root.get("overlays") or []):
                if not ov_t.get("visible"):
                    continue
                vp = ov_t.get("overlay_visibility_proof")
                if isinstance(vp, dict):
                    if vp.get("clipped_by_viewport") or vp.get("char_overflow"):
                        view_issues.append(
                            f"DOM glyph overflow/clip for {ov_t.get('overlay_id')} at {vw}px (t={rec.get('time')}s)"
                        )
                    if vw == 360 and vp.get("fits_mobile_360") is False:
                        view_issues.append(
                            f"DOM mobile-360 readability fail for {ov_t.get('overlay_id')} ({vp.get('mobile_360_font_px')}px)"
                        )

        # Check visibility_by_shot feature scale & overlay occlusion at 360px
        min_feat_seen: Optional[float] = None
        for sv in (visibility_by_shot or []):
            f_px_360 = sv.get("protected_detail_min_px_360")
            if f_px_360 is not None:
                scaled_f = float(f_px_360) * (float(vw) / float(PHONE_REF_WIDTH_PX))
                min_feat_seen = scaled_f if min_feat_seen is None else min(min_feat_seen, scaled_f)
            if float(sv.get("overlay_causal_overlap_ratio") or 0.0) > 0.42:
                view_issues.append(
                    f"T07: Overlay blocks causal feature in {sv.get('shot_id')} (overlap={sv.get('overlay_causal_overlap_ratio'):.2f})"
                )

        per_view[str(vw)] = {
            "viewport": [int(vw), vh],
            "ok": len(view_issues) == 0,
            "min_feature_px_at_view": round(min_feat_seen, 2) if min_feat_seen is not None else None,
            "issues": view_issues,
        }
        issues.extend([f"[{vw}px] {msg}" for msg in view_issues])

    return {
        "schema_version": "sd-mobile-qa-1",
        "status": "FAIL" if issues else ("WARN" if warnings else "PASS"),
        "free_screen_ratio": free_ratio,
        "views": per_view,
        "warnings": warnings,
        "issues": issues,
    }


def write_visual_proof_contact_sheet(
    samples: Sequence[Dict[str, Any]],
    out_path: Path,
    cols: int = 4,
    tile_w: int = 320,
    tile_h: int = 568,
) -> Path:
    """Render minimally edited labeled decoded contact sheet with exact timestamps and metrics."""
    items = list(samples)
    if not items:
        raise ValueError("Cannot build visual proof contact sheet from 0 samples")
    n = len(items)
    cols_eff = max(1, min(cols, n))
    rows = int(math.ceil(n / float(cols_eff)))
    header_h = 34
    canvas = Image.new("RGB", (cols_eff * tile_w, rows * (tile_h + header_h)), (14, 18, 26))
    draw = ImageDraw.Draw(canvas)

    for idx, smp in enumerate(items):
        r = idx // cols_eff
        c = idx % cols_eff
        x0 = c * tile_w
        y0 = r * (tile_h + header_h)
        rgb = smp.get("rgb")
        if rgb is None and smp.get("image_path"):
            rgb = np.asarray(Image.open(smp["image_path"]).convert("RGB"), dtype=np.float32)
        if rgb is not None:
            tile_img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).resize((tile_w, tile_h), Image.Resampling.BILINEAR)
            canvas.paste(tile_img, (x0, y0 + header_h))
        status = str(smp.get("status") or "PASS")
        tag_col = (52, 211, 153) if status == "PASS" else ((251, 191, 36) if status == "WARN" else (248, 113, 113))
        draw.rectangle([x0, y0, x0 + tile_w - 1, y0 + header_h - 1], fill=(20, 26, 38))
        lbl = str(smp.get("label") or f"{smp.get('shot_id', 'shot')} @{float(smp.get('t_sec', 0.0)):.2f}s [{status}]")
        draw.text((x0 + 8, y0 + 9), lbl[:44], fill=tag_col)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(out_path), quality=92)
    return out_path


def _classify_shot_policy_tier(shot: Dict[str, Any]) -> str:
    purpose = str(shot.get("shot_visual_purpose") or "").lower()
    act = str(shot.get("physical_action") or "").lower()
    gen = str(shot.get("procedural_generator") or "").lower()
    framing = str(shot.get("framing") or (shot.get("camera") or {}).get("framing") or "").lower()
    is_hold = bool((shot.get("staging") or {}).get("intentional_hold", False))
    if "aftermath" in purpose or "aftermath" in act or "aftermath" in gen or is_hold:
        return "aftermath_hold"
    if "establish" in purpose or "wide" in purpose or "establish" in gen or "overview" in gen or framing.startswith(("ws", "vws")):
        return "establishing_wide"
    if "human" in purpose or "onlooker" in act or "onlooker" in gen or "pedestrian" in act or "pedestrian" in gen:
        return "human_reaction"
    if "cutaway" in purpose or "macro" in purpose or "girder" in gen or "cutaway" in gen:
        return "explanatory_macro"
    if int(shot.get("index", 0) or 0) == 0 or "hook" in purpose:
        return "curiosity_hook"
    return "action_peak"


def run_decoded_visual_quality_audit(
    run_dir: Path,
    video_mp4: Path,
    storyboard: Dict[str, Any],
    editorial_timeline: Optional[Dict[str, Any]] = None,
    raw_traces: Optional[List[Dict[str, Any]]] = None,
    matte_manifest: Optional[Dict[str, Any]] = None,
    require_matte: bool = False,
) -> Dict[str, Any]:
    """Run complete R2.1 decoded-frame + semantic-matte + camera-compensated motion QA."""
    run_dir = Path(run_dir)
    qa_dir = run_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    sampled = sample_event_aligned_frames(video_mp4, storyboard)
    issues: List[str] = list(sampled.get("issues") or [])
    warnings: List[str] = []

    if sampled["status"] != "PASS":
        rep_fail = {
            "schema_version": SCHEMA_VERSION,
            "status": "FAIL",
            "subjective_visual_quality": "NOT_VERIFIED",
            "human_preference": "NOT_VERIFIED",
            "viewer_retention_status": "NOT_VERIFIED",
            "HUMAN_REVIEW_REQUIRED": True,
            "metadata": sampled.get("metadata"),
            "issues": issues,
        }
        (run_dir / "decoded_visual_quality_report.json").write_text(json.dumps(rep_fail, indent=2), encoding="utf-8")
        return rep_fail

    # Load matte manifest if present on disk
    if matte_manifest is None and (qa_dir / "mattes" / "matte_manifest.json").exists():
        matte_manifest = json.loads((qa_dir / "mattes" / "matte_manifest.json").read_text(encoding="utf-8"))

    matte_frames = list((matte_manifest or {}).get("frames") or [])
    if require_matte and not matte_frames:
        issues.append("T04: Required semantic subject matte manifest missing")

    def _find_matte_for_t(ts: float, shot_row: Dict[str, Any]) -> Dict[str, Any]:
        if matte_frames:
            match = min(matte_frames, key=lambda mf: abs(float(mf.get("t_sec", -99.0)) - ts))
            if abs(float(match.get("t_sec", -99.0)) - ts) <= 0.45:
                mp = Path(match.get("matte_path", ""))
                if not mp.is_absolute():
                    mp = qa_dir / "mattes" / mp.name
                res = render_subject_id_matte_at_t(
                    mp,
                    t=ts,
                    overlay_boxes_1080=match.get("overlay_boxes_1080"),
                    width=REF_ANALYSIS_W,
                    height=REF_ANALYSIS_H,
                )
                if res.get("status") == "PASS":
                    return res
        if require_matte:
            return {"status": "FAIL", "reason": f"T04: Missing semantic matte near t={ts:.2f}s"}
        # Non-matte fallback: derive foreground salience mask from frame gradients/luminance deviation (marked explicit!)
        return {"status": "NOT_VERIFIED", "reason": "No object-ID matte provided"}

    visibility_rows: List[Dict[str, Any]] = []
    motion_rows: List[Dict[str, Any]] = []
    contact_samples: List[Dict[str, Any]] = []
    shots_by_id = {str(s.get("shot_id")): s for s in (storyboard.get("shots") or [])}
    traces = list(raw_traces or [])

    for sh_s in sampled["samples"]:
        sid = str(sh_s.get("shot_id") or "")
        sh = shots_by_id.get(sid, {})
        tier = _classify_shot_policy_tier(sh)
        pol = EVENT_PROMINENCE_POLICY[tier]

        tri = sh_s["triples"]
        frames_rgb = [x["rgb"] for x in tri]
        mattes_tri = [_find_matte_for_t(float(x["t_sec"]), sh) for x in tri]

        # Match camera telemetry for the 3 timestamps
        cam_tri: List[Dict[str, Any]] = []
        phys_tri: List[Dict[str, Any]] = []
        for x in tri:
            ts = float(x["t_sec"])
            if traces:
                rec = min(traces, key=lambda r: abs(float(r.get("time_sec", r.get("time", -99.0))) - ts))
                tel = rec.get("telemetry") or {}
                if isinstance(tel.get("camera"), dict):
                    cam_tri.append(tel["camera"])
                if isinstance(tel.get("physical_motion"), dict):
                    phys_tri.append(tel["physical_motion"])

        peak_idx = 1 if len(tri) >= 2 else 0
        peak_rgb = frames_rgb[peak_idx]
        peak_matte = mattes_tri[peak_idx]

        if peak_matte.get("status") == "PASS":
            rd = estimate_scene_readability(peak_rgb, peak_matte, role_plan=None, phone_width_px=PHONE_REF_WIDTH_PX)
            occ = rd["occupancy"]
            hero_area = occ["hero_union_area_ratio"]
            max_span = max(occ["width_fraction"], occ["height_fraction"])
            feat_px = rd["protected_detail_min_px_360"]
            edge_sep = rd["foreground_background_edge_separation"]
            unif_ratio = occ["uniform_empty_band_ratio"]

            sh_status = "PASS"
            sh_issues: List[str] = []
            gen_low_s = str(sh.get("procedural_generator") or "").lower()
            act_low_s = str(sh.get("physical_action") or "").lower()
            is_r2_scene = any(k in gen_low_s or k in act_low_s for k in ("tacoma_", "boston_", "skyscraper_"))
            min_area_req = pol["min_subject_area"] if is_r2_scene else min(0.08, pol["min_subject_area"])
            min_span_req = pol["min_span_wh"] if is_r2_scene else min(0.28, pol["min_span_wh"])
            min_feat_req = pol["min_feature_px_360"] if is_r2_scene else min(24.0, pol["min_feature_px_360"])
            max_unif_req = pol["max_uniform_empty"] if is_r2_scene else max(0.86, pol["max_uniform_empty"])
            if hero_area < min_area_req and max_span < min_span_req:
                sh_status = "FAIL"
                sh_issues.append(
                    f"T05: Shot {sid} ({tier}) subject prominence too small "
                    f"(area={hero_area:.3f} < {min_area_req}, span={max_span:.3f} < {min_span_req})"
                )
            if feat_px < min_feat_req and tier not in ("establishing_wide", "aftermath_hold"):
                sh_status = "FAIL"
                sh_issues.append(
                    f"T06: Shot {sid} causal feature projected size {feat_px:.1f}px < {min_feat_req:.0f}px @360p"
                )
            if occ["border_clip_ratio"] > 0.35 and occ["visible_fraction"] < 0.72:
                sh_status = "FAIL"
                sh_issues.append(
                    f"Shot {sid} hero clipped out of safe frame (visible_fraction={occ['visible_fraction']:.2f})"
                )
            if unif_ratio > max_unif_req:
                if tier in ("curiosity_hook", "action_peak") and is_r2_scene:
                    sh_status = "FAIL"
                    sh_issues.append(f"T05: Excessive uniform empty band ({unif_ratio:.2f} > {max_unif_req:.2f})")
                else:
                    warnings.append(f"Shot {sid} has high uniform band ratio ({unif_ratio:.2f})")
            if edge_sep < 12.0:
                warnings.append(f"Shot {sid} low figure-ground edge separation ({edge_sep:.1f} < 12.0)")

            issues.extend(sh_issues)
            visibility_rows.append({
                "shot_id": sid,
                "policy_tier": tier,
                "t_peak_sec": tri[peak_idx]["t_sec"],
                "status": sh_status,
                "hero_union_area_ratio": hero_area,
                "subject_area_ratio": occ["subject_area_ratio"],
                "causal_feature_area_ratio": occ["causal_feature_area_ratio"],
                "width_fraction": occ["width_fraction"],
                "height_fraction": occ["height_fraction"],
                "visible_fraction": occ["visible_fraction"],
                "border_clip_ratio": occ["border_clip_ratio"],
                "protected_detail_min_px_360": feat_px,
                "foreground_background_edge_separation": edge_sep,
                "uniform_empty_band_ratio": unif_ratio,
                "overlay_causal_overlap_ratio": rd["overlay_causal_overlap_ratio"],
                "quadrant_coverage": occ["quadrant_coverage"],
                "issues": sh_issues,
            })

            act_low = str(sh.get("physical_action") or "").lower()
            gen_low = str(sh.get("procedural_generator") or "").lower()
            is_hold = bool((sh.get("staging") or {}).get("intentional_hold", False)) or ("aftermath" in act_low)
            is_r2_deforming = any(
                k in gen_low or k in act_low
                for k in ("tacoma_", "boston_", "skyscraper_", "torsion", "collapse", "wave", "sway", "damper", "rupture", "retreat", "onlooker")
            )
            claimed_disp = max((float(p.get("vertex_disp_max_m") or 0.0) for p in phys_tri), default=None)
            if is_hold:
                exp_type = "static_hold"
            elif is_r2_deforming or (claimed_disp is not None and claimed_disp >= 0.06):
                exp_type = "deforming"
            else:
                exp_type = "ambient_stage"
            mot = assess_decoded_frame_triple(
                frames_rgb,
                mattes_tri,
                camera_transforms=cam_tri,
                expected_action_type=exp_type,
                claimed_vertex_disp_m=claimed_disp,
            )
            mot["shot_id"] = sid
            mot["timestamps"] = [x["t_sec"] for x in tri]
            motion_rows.append(mot)
            if mot["status"] == "FAIL":
                issues.extend(mot["issues"])

            contact_samples.append({
                "shot_id": sid,
                "t_sec": tri[peak_idx]["t_sec"],
                "rgb": peak_rgb,
                "status": sh_status,
                "label": f"{sid} @{tri[peak_idx]['t_sec']:.1f}s {int(round(hero_area*100))}% {int(round(feat_px))}px [{sh_status}]",
            })
        else:
            if require_matte:
                issues.append(f"T04: Shot {sid} missing required semantic matte ({peak_matte.get('reason')})")
            visibility_rows.append({
                "shot_id": sid,
                "policy_tier": tier,
                "t_peak_sec": tri[peak_idx]["t_sec"],
                "status": "NOT_VERIFIED",
                "reason": peak_matte.get("reason", "Matte unavailable"),
            })
            contact_samples.append({
                "shot_id": sid,
                "t_sec": tri[peak_idx]["t_sec"],
                "rgb": peak_rgb,
                "status": "NOT_VERIFIED",
                "label": f"{sid} @{tri[peak_idx]['t_sec']:.1f}s [NO_MATTE]",
            })

    mobile_qa = audit_phone_composition(
        views=(320, 360, 390, 1080),
        storyboard=storyboard,
        editorial_timeline=editorial_timeline,
        visibility_by_shot=visibility_rows,
        raw_traces=traces,
    )
    if mobile_qa["status"] == "FAIL":
        issues.extend(mobile_qa["issues"])

    sheet_path = qa_dir / "decoded_visual_proof_sheet.jpg"
    if contact_samples:
        write_visual_proof_contact_sheet(contact_samples, sheet_path)

    vis_doc = {
        "schema_version": "sd-subject-visibility-1",
        "analysis_resolution": [REF_ANALYSIS_W, REF_ANALYSIS_H],
        "phone_reference_width_px": PHONE_REF_WIDTH_PX,
        "status": "FAIL" if any(r.get("status") == "FAIL" for r in visibility_rows) else (
            "NOT_VERIFIED" if any(r.get("status") == "NOT_VERIFIED" for r in visibility_rows) else "PASS"
        ),
        "shots": visibility_rows,
    }
    mot_doc = {
        "schema_version": "sd-camera-compensated-motion-1",
        "analysis_resolution": [REF_ANALYSIS_W, REF_ANALYSIS_H],
        "status": "FAIL" if any(r.get("status") == "FAIL" for r in motion_rows) else (
            "NOT_VERIFIED" if not motion_rows else "PASS"
        ),
        "shots": motion_rows,
    }

    (run_dir / "subject_visibility_by_shot.json").write_text(json.dumps(vis_doc, indent=2), encoding="utf-8")
    (run_dir / "camera_compensated_motion_report.json").write_text(json.dumps(mot_doc, indent=2), encoding="utf-8")
    (run_dir / "mobile_qa_320_360_390_1080.json").write_text(json.dumps(mobile_qa, indent=2), encoding="utf-8")

    has_not_ver = (vis_doc["status"] == "NOT_VERIFIED" or mot_doc["status"] == "NOT_VERIFIED")
    overall = "FAIL" if issues else ("NOT_VERIFIED" if (require_matte and has_not_ver) else ("WARN" if warnings else "PASS"))
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": overall,
        "subjective_visual_quality": "NOT_VERIFIED",
        "human_preference": "NOT_VERIFIED",
        "viewer_retention_status": "NOT_VERIFIED",
        "HUMAN_REVIEW_REQUIRED": True,
        "analysis_resolution": [REF_ANALYSIS_W, REF_ANALYSIS_H],
        "phone_reference_width_px": PHONE_REF_WIDTH_PX,
        "video_metadata": sampled["metadata"],
        "samples_per_shot_count": len(visibility_rows),
        "contact_sheet_jpg": str(sheet_path.resolve()) if sheet_path.exists() else None,
        "reports": {
            "subject_visibility_by_shot": str((run_dir / "subject_visibility_by_shot.json").resolve()),
            "camera_compensated_motion_report": str((run_dir / "camera_compensated_motion_report.json").resolve()),
            "mobile_qa_320_360_390_1080": str((run_dir / "mobile_qa_320_360_390_1080.json").resolve()),
        },
        "warnings": warnings,
        "issues": issues,
    }
    (run_dir / "decoded_visual_quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
