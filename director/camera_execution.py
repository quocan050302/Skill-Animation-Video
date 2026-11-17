"""Single-Authority Camera Choreography Contract, Python/JS Spline Evaluator & Trace Verifier.

Guarantees that what `camera_choreographer.py` plans (`camera_paths.json`) is the EXACT
3D camera world position, look orientation, roll, and FOV executed by Three.js (`camera_executor.js`)
and verified post-render (`camera_execution_trace.json`).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = "sd-camera-exec-1"

CAMERA_EXECUTOR_JS = r"""import * as THREE from 'three';

function clamp01(x) {
  return Math.min(1, Math.max(0, Number(x) || 0));
}

function quintic(t) {
  const x = clamp01(t);
  return x * x * x * (x * (x * 6 - 15) + 10);
}

function cubicEaseInOut(t) {
  const x = clamp01(t);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

/**
 * Deterministic keyframe path evaluator matching Python `evaluate_camera_path_py`.
 * Evaluates pos[3], look[3], fov, roll from immutable keyframes.
 */
export function evalCameraPath(kfs, tNorm) {
  if (!Array.isArray(kfs) || kfs.length === 0) {
    return { pos: [0.3, 1.38, 2.0], look: [0, 1.18, 0], fov: 34, roll: 0, segIndex: 0 };
  }
  const u = clamp01(tNorm);
  if (kfs.length === 1 || u <= (kfs[0].t_norm || 0)) {
    const k0 = kfs[0];
    return {
      pos: [...k0.pos],
      look: [...k0.look],
      fov: Number(k0.fov ?? 34),
      roll: Number(k0.roll ?? 0),
      segIndex: 0,
    };
  }
  for (let i = 0; i < kfs.length - 1; i++) {
    const a = kfs[i];
    const b = kfs[i + 1];
    const ta = Number(a.t_norm ?? 0);
    const tb = Number(b.t_norm ?? 1);
    if (u <= tb + 1e-6) {
      const span = Math.max(1e-5, tb - ta);
      const raw = clamp01((u - ta) / span);
      const easeMode = b.ease || a.ease || 'quintic';
      const segU = a.hold ? 0.0 : (easeMode === 'linear' ? raw : (easeMode === 'cubic' ? cubicEaseInOut(raw) : quintic(raw)));
      return {
        pos: [lerp(a.pos[0], b.pos[0], segU), lerp(a.pos[1], b.pos[1], segU), lerp(a.pos[2], b.pos[2], segU)],
        look: [lerp(a.look[0], b.look[0], segU), lerp(a.look[1], b.look[1], segU), lerp(a.look[2], b.look[2], segU)],
        fov: lerp(Number(a.fov ?? 34), Number(b.fov ?? 34), segU),
        roll: lerp(Number(a.roll ?? 0), Number(b.roll ?? 0), segU),
        segIndex: i,
      };
    }
  }
  const last = kfs[kfs.length - 1];
  return {
    pos: [...last.pos],
    look: [...last.look],
    fov: Number(last.fov ?? 34),
    roll: Number(last.roll ?? 0),
    segIndex: kfs.length - 1,
  };
}

/**
 * Authoritative camera application: drives position, lookAt, up/roll, FOV, and emits
 * world-space telemetry for `camera_execution_trace.json`.
 */
export function applyCameraPath(camera, poseCam, opts = {}) {
  const pos = poseCam.pos || [0.3, 1.38, 2.0];
  const look = poseCam.look || [0, 1.18, 0];
  const roll = Number(poseCam.roll ?? 0);
  const baseFov = Number(poseCam.fov ?? 34);
  const trFovScale = Number(opts.transitionFovScale ?? 1.0);
  const trYawDelta = Number(opts.transitionYawDelta ?? 0.0);
  const trPosDelta = opts.transitionPosDelta || [0, 0, 0];

  camera.position.set(
    pos[0] + trPosDelta[0],
    pos[1] + trPosDelta[1],
    pos[2] + trPosDelta[2]
  );
  camera.up.set(Math.sin(roll), Math.cos(roll), 0);
  camera.lookAt(look[0], look[1], look[2]);
  if (Math.abs(trYawDelta) > 1e-6) {
    camera.rotation.y += trYawDelta;
  }
  camera.fov = Math.max(12, Math.min(85, baseFov * trFovScale));
  if (opts.aspect) camera.aspect = opts.aspect;
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);

  const wPos = new THREE.Vector3();
  const wQuat = new THREE.Quaternion();
  const wDir = new THREE.Vector3();
  camera.getWorldPosition(wPos);
  camera.getWorldQuaternion(wQuat);
  camera.getWorldDirection(wDir);

  let focalAnchorUv = null;
  if (opts.focalAnchor && Array.isArray(opts.focalAnchor.world_pos)) {
    const p = new THREE.Vector3(...opts.focalAnchor.world_pos);
    const pNdc = p.clone().project(camera);
    focalAnchorUv = {
      u: Number(((pNdc.x + 1) * 0.5).toFixed(4)),
      v: Number(((1 - pNdc.y) * 0.5).toFixed(4)),
      in_front: pNdc.z >= -1 && pNdc.z <= 1,
    };
  }

  return {
    planned_pos: [Number(pos[0].toFixed(5)), Number(pos[1].toFixed(5)), Number(pos[2].toFixed(5))],
    planned_look: [Number(look[0].toFixed(5)), Number(look[1].toFixed(5)), Number(look[2].toFixed(5))],
    planned_fov: Number(baseFov.toFixed(4)),
    planned_roll: Number(roll.toFixed(5)),
    realized_pos: [Number(wPos.x.toFixed(5)), Number(wPos.y.toFixed(5)), Number(wPos.z.toFixed(5))],
    realized_quat: [
      Number(wQuat.x.toFixed(6)),
      Number(wQuat.y.toFixed(6)),
      Number(wQuat.z.toFixed(6)),
      Number(wQuat.w.toFixed(6)),
    ],
    realized_forward: [Number(wDir.x.toFixed(5)), Number(wDir.y.toFixed(5)), Number(wDir.z.toFixed(5))],
    realized_fov: Number(camera.fov.toFixed(4)),
    transition_offset_active: (Math.abs(trFovScale - 1.0) > 1e-4) || (Math.abs(trYawDelta) > 1e-4) ||
      (Math.abs(trPosDelta[0]) + Math.abs(trPosDelta[1]) + Math.abs(trPosDelta[2]) > 1e-4),
    focal_anchor_uv: focalAnchorUv,
  };
}
"""


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _quintic(t: float) -> float:
    x = _clamp01(t)
    return x * x * x * (x * (x * 6.0 - 15.0) + 10.0)


def _cubic_ease_in_out(t: float) -> float:
    x = _clamp01(t)
    return 4.0 * x * x * x if x < 0.5 else 1.0 - ((-2.0 * x + 2.0) ** 3) / 2.0


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _normalize(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if n < 1e-9:
        return (0.0, 0.0, 1.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def look_at_quaternion(
    pos: List[float],
    look: List[float],
    roll: float = 0.0,
) -> Tuple[float, float, float, float]:
    """Compute Three.js-compatible camera quaternion `[x, y, z, w]` from pos, look, and roll."""
    zx, zy, zz = _normalize((pos[0] - look[0], pos[1] - look[1], pos[2] - look[2]))
    ux, uy, uz = _normalize((math.sin(roll), math.cos(roll), 0.0))
    xx, xy, xz = _cross((ux, uy, uz), (zx, zy, zz))
    if math.sqrt(xx * xx + xy * xy + xz * xz) < 1e-7:
        # Degenerate up collinear with view axis; pick fallback
        xx, xy, xz = (1.0, 0.0, 0.0)
    else:
        xx, xy, xz = _normalize((xx, xy, xz))
    yx, yy, yz = _cross((zx, zy, zz), (xx, xy, xz))

    # Matrix columns are X, Y, Z axes -> convert 3x3 rotation matrix to quaternion [x, y, z, w]
    m00, m01, m02 = xx, yx, zx
    m10, m11, m12 = xy, yy, zy
    m20, m21, m22 = xz, yz, zz
    tr = m00 + m11 + m22
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        qw = 0.25 * s
        qx = (m21 - m12) / s
        qy = (m02 - m20) / s
        qz = (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        qw = (m21 - m12) / s
        qx = 0.25 * s
        qy = (m01 + m10) / s
        qz = (m02 + m20) / s
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        qw = (m02 - m20) / s
        qx = (m01 + m10) / s
        qy = 0.25 * s
        qz = (m12 + m21) / s
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        qw = (m10 - m01) / s
        qx = (m02 + m20) / s
        qy = (m12 + m21) / s
        qz = 0.25 * s
    norm = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw) or 1.0
    return (qx / norm, qy / norm, qz / norm, qw / norm)


def quaternion_angle_deg(q1: Tuple[float, float, float, float], q2: Tuple[float, float, float, float]) -> float:
    dot = abs(q1[0] * q2[0] + q1[1] * q2[1] + q1[2] * q2[2] + q1[3] * q2[3])
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(2.0 * math.acos(dot))


def evaluate_camera_path_py(camera_path: Dict[str, Any], t_norm: float) -> Dict[str, Any]:
    """Python equivalent of `evalCameraPath(kfs, tNorm)`."""
    kfs = list(camera_path.get("keyframes") or [])
    if not kfs:
        pos = [0.3, 1.38, 2.0]
        look = [0.0, 1.18, 0.0]
        fov, roll = 34.0, 0.0
    else:
        u = _clamp01(t_norm)
        if len(kfs) == 1 or u <= float(kfs[0].get("t_norm", 0.0)):
            k0 = kfs[0]
            pos = [float(v) for v in k0["pos"]]
            look = [float(v) for v in k0["look"]]
            fov = float(k0.get("fov", 34.0))
            roll = float(k0.get("roll", 0.0))
        else:
            chosen = None
            for i in range(len(kfs) - 1):
                a, b = kfs[i], kfs[i + 1]
                ta = float(a.get("t_norm", 0.0))
                tb = float(b.get("t_norm", 1.0))
                if u <= tb + 1e-6:
                    raw = _clamp01((u - ta) / max(1e-5, tb - ta))
                    ease_mode = str(b.get("ease") or a.get("ease") or "quintic")
                    if a.get("hold"):
                        seg_u = 0.0
                    elif ease_mode == "linear":
                        seg_u = raw
                    elif ease_mode == "cubic":
                        seg_u = _cubic_ease_in_out(raw)
                    else:
                        seg_u = _quintic(raw)
                    pos = [_lerp(float(a["pos"][k]), float(b["pos"][k]), seg_u) for k in range(3)]
                    look = [_lerp(float(a["look"][k]), float(b["look"][k]), seg_u) for k in range(3)]
                    fov = _lerp(float(a.get("fov", 34.0)), float(b.get("fov", 34.0)), seg_u)
                    roll = _lerp(float(a.get("roll", 0.0)), float(b.get("roll", 0.0)), seg_u)
                    chosen = True
                    break
            if not chosen:
                last = kfs[-1]
                pos = [float(v) for v in last["pos"]]
                look = [float(v) for v in last["look"]]
                fov = float(last.get("fov", 34.0))
                roll = float(last.get("roll", 0.0))
    quat = look_at_quaternion(pos, look, roll)
    return {
        "pos": [round(v, 5) for v in pos],
        "look": [round(v, 5) for v in look],
        "fov": round(fov, 4),
        "roll": round(roll, 5),
        "quat": [round(v, 6) for v in quat],
    }


def collect_camera_trace_samples(storyboard: Dict[str, Any], fps: int = 30) -> List[float]:
    """Select bounded keyframe + seam-neighbor + action timestamps for telemetry verification."""
    shots = list(storyboard.get("shots") or [])
    dur = float(storyboard.get("total_duration_sec") or 1.0)
    dt = 1.0 / max(1, fps)
    times: set[float] = set()
    for i, s in enumerate(shots):
        st = float(s["start"])
        en = float(s["end"])
        s_dur = max(0.1, en - st)
        times.add(round(min(dur - 0.002, st + min(dt, s_dur * 0.1)), 4))
        times.add(round(st + s_dur * 0.25, 4))
        times.add(round(st + s_dur * 0.50, 4))
        times.add(round(st + s_dur * 0.75, 4))
        times.add(round(max(st + dt, en - min(2.0 * dt, s_dur * 0.15)), 4))
        # Action contacts
        ca = (s.get("staging") or {}).get("contact_action")
        if isinstance(ca, dict) and ca.get("hit_time_sec") is not None:
            ht = float(ca["hit_time_sec"])
            times.add(round(max(0.0, ht - 0.12), 4))
            times.add(round(min(dur - 0.002, ht), 4))
            times.add(round(min(dur - 0.002, ht + 0.12), 4))
        # Seam neighbors
        if i < len(shots) - 1:
            for k in (-2, -1, 0, 1, 2):
                tk = en + k * dt
                if 0.0 <= tk < dur - 1e-4:
                    times.add(round(tk, 4))
    return sorted(times)


def evaluate_camera_trace_accuracy(
    storyboard: Dict[str, Any],
    camera_plan: Dict[str, Any],
    trace_records: List[Dict[str, Any]],
    transition_edl: Optional[Dict[str, Any]] = None,
    pos_tol_rel_diag: float = 0.015,
    ori_tol_deg: float = 0.65,
    fov_tol_deg: float = 0.65,
) -> Dict[str, Any]:
    """Compare planned world camera poses against realized Three.js world poses across sampled frames."""
    shots = list(storyboard.get("shots") or [])
    paths_by_id = {p["shot_id"]: p for p in (camera_plan.get("paths") or [])}
    fps = int(storyboard.get("fps", 30))

    # Build transition overlap exclusion windows where optical camera whip/zoom is intentionally applied
    tr_windows: List[Tuple[float, float, str]] = []
    for tr in (transition_edl or {}).get("transitions", []):
        m = str(tr.get("actual_method") or "cut")
        d = float(tr.get("duration_sec") or 0.0)
        b = float(tr.get("boundary_sec") or 0.0)
        if d > 0.0 and m not in ("cut", "cut_on_action"):
            tr_windows.append((b - d * 0.55 - 1.0 / fps, b + d * 0.55 + 1.0 / fps, m))

    worst_pos_err = 0.0
    worst_ori_err = 0.0
    worst_fov_err = 0.0
    failures: List[str] = []
    samples_out: List[Dict[str, Any]] = []
    collision_violations: List[str] = []
    offscreen_focal: List[str] = []

    for rec in trace_records:
        t = float(rec.get("time", 0.0))
        tel = rec.get("telemetry")
        if not isinstance(tel, dict) or not isinstance(tel.get("camera"), dict):
            failures.append(f"Missing camera telemetry at t={t:.3f}s")
            continue
        cam_tel = tel["camera"]
        shot_idx = int(rec.get("shot_index", 0))
        if shot_idx < 0 or shot_idx >= len(shots):
            failures.append(f"Invalid shot_index {shot_idx} at t={t:.3f}s")
            continue
        shot = shots[shot_idx]
        cpath = paths_by_id.get(shot["shot_id"])
        if not cpath or cpath.get("space") != "world_3d":
            continue

        st = float(shot["start"])
        en = float(shot["end"])
        dur = max(0.2, en - st)
        u = _clamp01((t - st) / dur)
        expected = evaluate_camera_path_py(cpath, u)

        r_pos = [float(v) for v in cam_tel.get("realized_pos", [0, 0, 0])]
        r_quat = tuple(float(v) for v in cam_tel.get("realized_quat", [0, 0, 0, 1]))
        r_fov = float(cam_tel.get("realized_fov", 34.0))

        bounds = cpath.get("bounds") or {"x_min": -3.5, "x_max": 3.5, "y_min": 0.12, "y_max": 4.2, "z_min": -4.0, "z_max": 5.2}
        diag = math.sqrt(
            (float(bounds["x_max"]) - float(bounds["x_min"])) ** 2
            + (float(bounds["y_max"]) - float(bounds["y_min"])) ** 2
            + (float(bounds["z_max"]) - float(bounds["z_min"])) ** 2
        )
        pos_tol = max(0.03, pos_tol_rel_diag * diag)

        in_tr_win = any(w0 <= t <= w1 for w0, w1, _ in tr_windows) or bool(cam_tel.get("transition_offset_active"))

        pos_err = math.sqrt(sum((r_pos[k] - expected["pos"][k]) ** 2 for k in range(3)))
        ori_err = quaternion_angle_deg(tuple(expected["quat"]), r_quat)  # type: ignore[arg-type]
        fov_err = abs(r_fov - expected["fov"])

        # Camera floor & collider safety check
        if r_pos[1] < 0.08:
            collision_violations.append(f"{shot['shot_id']}@t={t:.3f}s camera below floor y={r_pos[1]:.3f}")
        dist_look = math.sqrt(sum((r_pos[k] - expected["look"][k]) ** 2 for k in range(3)))
        if dist_look < 0.20:
            collision_violations.append(f"{shot['shot_id']}@t={t:.3f}s camera inside target dist={dist_look:.3f}")
        for box in (cpath.get("collision_constraints") or {}).get("collider_boxes", []):
            mn, mx = box.get("min", [0, 0, 0]), box.get("max", [0, 0, 0])
            pad = 0.04
            if (mn[0] - pad <= r_pos[0] <= mx[0] + pad) and (mn[1] - pad <= r_pos[1] <= mx[1] + pad) and (mn[2] - pad <= r_pos[2] <= mx[2] + pad):
                collision_violations.append(f"{shot['shot_id']}@t={t:.3f}s camera penetrates collider {box.get('id')}")

        fuv = cam_tel.get("focal_anchor_uv")
        if isinstance(fuv, dict) and not in_tr_win:
            if not fuv.get("in_front", True) or not (-0.05 <= float(fuv["u"]) <= 1.05 and 0.02 <= float(fuv["v"]) <= 0.95):
                offscreen_focal.append(f"{shot['shot_id']}@t={t:.3f}s focal_uv=({fuv['u']},{fuv['v']})")

        if not in_tr_win:
            worst_pos_err = max(worst_pos_err, pos_err)
            worst_ori_err = max(worst_ori_err, ori_err)
            worst_fov_err = max(worst_fov_err, fov_err)
            if pos_err > pos_tol:
                failures.append(f"{shot['shot_id']}@t={t:.3f}s pos_err={pos_err:.4f}m > tol={pos_tol:.4f}m")
            if ori_err > ori_tol_deg:
                failures.append(f"{shot['shot_id']}@t={t:.3f}s ori_err={ori_err:.2f}deg > tol={ori_tol_deg:.2f}deg")
            if fov_err > fov_tol_deg:
                failures.append(f"{shot['shot_id']}@t={t:.3f}s fov_err={fov_err:.2f}deg > tol={fov_tol_deg:.2f}deg")

        samples_out.append({
            "shot_id": shot["shot_id"],
            "time_sec": round(t, 4),
            "frame": int(round(t * fps)),
            "in_transition_window": in_tr_win,
            "planned_pos": expected["pos"],
            "realized_pos": [round(v, 5) for v in r_pos],
            "planned_quat": expected["quat"],
            "realized_quat": [round(v, 6) for v in r_quat],
            "planned_fov": expected["fov"],
            "realized_fov": round(r_fov, 4),
            "pos_err_m": round(pos_err, 5),
            "ori_err_deg": round(ori_err, 3),
            "fov_err_deg": round(fov_err, 3),
            "focal_anchor_uv": fuv,
        })

    if collision_violations:
        failures.extend(collision_violations)
    if offscreen_focal:
        failures.extend(offscreen_focal)

    status = "FAIL" if failures or not samples_out else "PASS"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "sampled_frames": len(samples_out),
        "worst_pos_err_m": round(worst_pos_err, 5),
        "worst_ori_err_deg": round(worst_ori_err, 3),
        "worst_fov_err_deg": round(worst_fov_err, 3),
        "collision_violations": collision_violations,
        "offscreen_focal_frames": offscreen_focal,
        "failures": failures,
        "samples": samples_out,
    }
