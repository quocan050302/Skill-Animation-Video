"""Deterministic Pure Three.js Physical Motion Primitives (`SD-RETENTION-03` Workstream 3).

All evaluators are strict mathematical functions `pose(t, params)` with ZERO global delta-t
accumulation so out-of-order seeking to any timestamp `t` returns bit-identical vertex coordinates,
rotations, and telemetry.
"""

from __future__ import annotations


PHYSICAL_MOTION_PRIMITIVES_JS = r"""import * as THREE from 'three';

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function smooth01(u) { const c = clamp(u, 0, 1); return c * c * (3 - 2 * c); }

export function evaluateSpringDampedMotion(t, { amplitude = 0.25, omega = 6.2, damping = 1.6, onsetT = 0.0 } = {}) {
  const dt = Math.max(0, t - onsetT);
  if (dt <= 0) return { offset: 0, velocity: 0 };
  const env = Math.exp(-damping * dt);
  const w = Math.max(0.5, omega);
  const off = amplitude * env * Math.sin(w * dt);
  const vel = amplitude * env * (w * Math.cos(w * dt) - damping * Math.sin(w * dt));
  return { offset: off, velocity: vel };
}

export function evaluateBendingBeam(t, xNorm, { amp = 0.16, omega = 2.8, phase = 0.0 } = {}) {
  const s = clamp(xNorm, 0, 1);
  // Clamped-clamped bending mode shape vanishing smoothly at bridge towers (0 and 1)
  const mode = Math.sin(Math.PI * s) * Math.sin(Math.PI * s);
  const dy = amp * mode * Math.sin(t * omega + phase);
  const slope = amp * 2 * Math.PI * Math.sin(Math.PI * s) * Math.cos(Math.PI * s) * Math.sin(t * omega + phase);
  return { dy, slope };
}

export function evaluateTorsionSpan(t, uSpan, {
  verticalAmp = 0.18,
  torsionRad = 0.32,
  omegaVert = 2.2,
  omegaTorsion = 3.4,
  twistGain = 1.0,
  deckHalfWidth = 0.56,
} = {}) {
  const s = clamp(uSpan, 0, 1);
  // Two-loop vertical wave + fundamental antisymmetric center-span torsional flutter
  const envEnd = Math.sin(Math.PI * s);
  const vShape = Math.sin(2.0 * Math.PI * s) * 0.72 + envEnd * 0.28;
  const dyCenter = verticalAmp * vShape * Math.sin(t * omegaVert + s * 1.4);

  const twistMode = Math.sin(Math.PI * s) * (0.85 + 0.15 * Math.cos(2.0 * Math.PI * s));
  const twistEnv = twistGain * (0.82 + 0.18 * Math.sin(t * 0.65));
  const rollRad = torsionRad * twistMode * twistEnv * Math.sin(t * omegaTorsion + s * 0.45);
  const leftEdgeY = dyCenter + Math.sin(rollRad) * deckHalfWidth;
  const rightEdgeY = dyCenter - Math.sin(rollRad) * deckHalfWidth;
  return { dyCenter, rollRad, leftEdgeY, rightEdgeY };
}

export function evaluateCollapseTrajectory(t, onsetT, {
  baseY = 2.2,
  vx = 0.0,
  vz = 0.22,
  pitchRate = 1.6,
  rollRate = 1.1,
  gravity = 9.81,
  floorY = -1.65,
} = {}) {
  const dt = Math.max(0, t - onsetT);
  if (dt <= 0) {
    return { active: false, dy: 0, dx: 0, dz: 0, rotX: 0, rotZ: 0, splashProgress: 0 };
  }
  const rawY = -0.5 * gravity * dt * dt * 0.62;
  const minDrop = floorY - baseY;
  const clampedDrop = Math.max(minDrop, rawY);
  const hitWaterT = Math.sqrt(Math.max(0, (2 * Math.abs(minDrop)) / Math.max(0.1, gravity * 0.62)));
  const splashProgress = dt > hitWaterT ? smooth01((dt - hitWaterT) / 0.45) : 0.0;
  return {
    active: true,
    dy: clampedDrop,
    dx: vx * dt,
    dz: vz * dt,
    rotX: Math.min(0.95, dt * pitchRate),
    rotZ: clamp(Math.sin(onsetT * 13.7 + 0.5) * rollRate * dt, -0.85, 0.85),
    splashProgress,
  };
}

export function evaluateSurfaceWave(t, xNorm, zNorm, {
  baseHeight = 1.65,
  frontCurvature = 0.42,
  viscousRipples = 0.16,
} = {}) {
  // zNorm in [0 (tail), 1 (leading advancing nose)]
  const zn = clamp(zNorm, 0, 1);
  const xn = clamp(xNorm, -1, 1);
  const edgeTaper = Math.max(0.05, 1.0 - Math.pow(Math.abs(xn), 3.6) * 0.82);
  // Thick bulbous hydraulic bore nose rising near zNorm = 0.82 and sloping back cleanly
  const frontSlope = zn > 0.84 ? Math.sqrt(Math.max(0.0, 1.0 - Math.pow((zn - 0.84) / 0.16, 2))) : 1.0;
  const crestHum = 0.42 + 0.58 * Math.pow(zn, 0.65);
  const surgeFold = Math.sin(xn * 5.2 + t * 2.8) * 0.12 * Math.sin(zn * Math.PI)
                  + Math.cos(xn * 8.4 - t * 3.9 + zn * 5.0) * 0.07 * zn;
  const boreH = baseHeight * edgeTaper * frontSlope * (crestHum + viscousRipples * (0.5 + 0.5 * Math.sin(zn * 6.5 - t * 3.1)) + surgeFold);
  // Forward bulging nose curve across street width so front isn't a flat wall
  const nosePushZ = frontCurvature * (1.0 - xn * xn) * Math.pow(zn, 2.2)
                  + 0.11 * Math.sin(xn * 4.5 + t * 2.4) * Math.pow(zn, 1.8);
  return { y: Math.max(0.02, boreH), dz: nosePushZ };
}

export function evaluateCollisionResponse(t, impactT, { maxDeflection = 0.08, freq = 18.0, decay = 4.0 } = {}) {
  if (t < impactT) return { deflection: 0, ringing: 0, impactActive: false };
  const dt = t - impactT;
  const step = smooth01(dt / 0.18);
  const ring = Math.exp(-dt * decay) * Math.sin(dt * freq) * 0.25 * maxDeflection;
  return { deflection: maxDeflection * step + ring, ringing: ring, impactActive: true };
}

/**
 * Continuous deformable 3D viscous fluid bore / surge mesh (zero detached sphere clusters).
 * Updates vertices analytically at any absolute `t` with exact normals and deformation metrics.
 */
export function makeContinuousViscousSurface({
  width = 4.3,
  length = 5.6,
  height = 1.68,
  nx = 40,
  nz = 22,
  colorHex = 0x5c2708,
  emissiveHex = 0x260d02,
} = {}) {
  const geom = new THREE.PlaneGeometry(width, length, nx, nz);
  geom.rotateX(-Math.PI / 2);
  // Shift geometry so local z spans [-length, 0.72] where +0.72 is leading street surge nose
  geom.translate(0, 0, -length * 0.5 + 0.72);
  const posAttr = geom.attributes.position;
  const baseCoords = new Float32Array(posAttr.array.length);
  baseCoords.set(posAttr.array);

  const mat = new THREE.MeshStandardMaterial({
    color: colorHex,
    emissive: emissiveHex,
    emissiveIntensity: 0.40,
    roughness: 0.22,
    metalness: 0.05,
    side: THREE.DoubleSide,
  });
  const mesh = new THREE.Mesh(geom, mat);
  mesh.castShadow = true;
  mesh.receiveShadow = true;

  let lastTelemetry = { vertex_disp_max_m: 0.0, crest_y_max_m: height, nose_z_local: 0.72 };

  function updateSurface(t) {
    const arr = posAttr.array;
    let maxDisp = 0.0;
    let maxY = 0.0;
    let maxNoseZ = -99.0;
    const halfW = width * 0.5;
    const zMin = -length + 0.72;
    const zSpan = Math.max(0.2, length);

    for (let i = 0; i < posAttr.count; i++) {
      const ix = i * 3;
      const bx = baseCoords[ix];
      const bz = baseCoords[ix + 2];
      const xn = bx / Math.max(0.01, halfW);
      const zn = clamp((bz - zMin) / zSpan, 0, 1);

      const ev = evaluateSurfaceWave(t, xn, zn, { baseHeight: height });
      // Taper sides & extreme back edge tightly down onto street cobbles (zero floating edge slab)
      const rimMask = Math.min(1.0, Math.min((1.0 - Math.abs(xn)) * 7.5, zn * 9.0, (1.0 - zn) * 14.0 + 0.04));
      const newY = 0.015 + ev.y * clamp(rimMask, 0, 1);
      const newZ = bz + ev.dz;

      arr[ix] = bx;
      arr[ix + 1] = newY;
      arr[ix + 2] = newZ;

      maxDisp = Math.max(maxDisp, Math.hypot(newZ - bz, newY - baseCoords[ix + 1]));
      maxY = Math.max(maxY, newY);
      maxNoseZ = Math.max(maxNoseZ, newZ);
    }
    posAttr.needsUpdate = true;
    geom.computeVertexNormals();
    lastTelemetry = {
      vertex_disp_max_m: Number(maxDisp.toFixed(4)),
      crest_y_max_m: Number(maxY.toFixed(3)),
      nose_z_local: Number(maxNoseZ.toFixed(3)),
    };
    return lastTelemetry;
  }

  updateSurface(0.0);
  return {
    mesh,
    geometry: geom,
    update: updateSurface,
    getTelemetry: () => lastTelemetry,
  };
}

export function getPhysicalTelemetry(motionSpec = {}, extra = {}) {
  return {
    motion_type: motionSpec.motion_type || 'procedural_continuous',
    fidelity_disclosure: motionSpec.fidelity_disclosure || 'stylized_illustrative',
    ...extra,
  };
}
"""
