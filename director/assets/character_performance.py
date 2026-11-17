"""Deterministic Grounded Three.js Character Performance & Foot-Lock Runtime (`SD-RETENTION-03` Workstream 4).

Matches `vendor/.../human.js` skeleton geometry (`hip=-0.06`, `thigh=0.44`, `shin=0.45`,
`soleOffset=0.0735`, default pelvis y=`0.95` before `drop` correction, Three.js right-handed +X rot
swings -Y leg forward when theta < 0 and backward when theta > 0) so stance feet stay planted
on `groundY = 0` without floor penetration or sliding.
"""

from __future__ import annotations


CHARACTER_PERFORMANCE_JS = r"""import * as THREE from 'three';

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function easeOut(u) { const c = clamp(u, 0, 1); return 1 - Math.pow(1 - c, 3); }
function smooth(u) { const c = clamp(u, 0, 1); return c * c * (3 - 2 * c); }
function lerp(a, b, u) { return a + (b - a) * u; }

const L_THIGH = 0.44;
const L_SHIN = 0.45;
const SOLE_DROP = 0.0735;
const HIP_OFFSET_Y = 0.06;
const PELVIS_DEFAULT_Y = 0.95;

function legSpanY(hipX, knX) {
  return L_THIGH * Math.cos(hipX) + L_SHIN * Math.cos(hipX + knX) + SOLE_DROP;
}

function legLocalZ(hipX, knX) {
  // Exact forward (+Z) projection of foot relative to hip in Three.js (+X rot moves -Y toward -Z)
  return -L_THIGH * Math.sin(hipX) - L_SHIN * Math.sin(hipX + knX);
}

/**
 * Pure deterministic pose & foot-grounded locomotion evaluator `pose(t, plan)`.
 * Matches stance stride translation mathematically to stance leg arc so world foot remains anchored.
 */
export function evaluateCharacterPose(t, actionPlan = {}) {
  const dur = Math.max(0.4, Number(actionPlan.duration_sec || 3.5));
  const intent = String(actionPlan.primary_intent || 'brace');
  const groundY = Number(actionPlan.ground_y || 0.0);
  const baseX = Number(actionPlan.base_x || 0.0);
  const baseZ = Number(actionPlan.base_z || 0.0);
  const baseYaw = Number(actionPlan.base_yaw || 0.0);
  const onset = Number(actionPlan.reaction_onset_sec ?? Math.min(0.42, dur * 0.15));
  const retreatDist = Number(actionPlan.retreat_distance_m ?? 1.8);
  const threat = actionPlan.threat_world || [0, 1.4, -4.5];

  const u = clamp(t / dur, 0, 1);
  const uReact = smooth((t - onset) / Math.max(0.25, dur * 0.25));

  const dxT = baseX - Number(threat[0] || 0);
  const dzT = baseZ - Number(threat[2] || -4.5);
  const tLen = Math.max(0.001, Math.hypot(dxT, dzT));
  const awayX = dxT / tLen;
  const awayZ = dzT / tLen;
  const towardYaw = Math.atan2(-awayX, -awayZ);

  let rootX = baseX;
  let rootZ = baseZ;
  let rootYaw = baseYaw;
  let lHipX = -0.04, rHipX = 0.04;
  let lKnX = 0.08, rKnX = 0.08;
  let lAnX = -(lHipX + lKnX), rAnX = -(rHipX + rKnX);
  let spineX = 0.04, spineY = 0.0, chestY = 0.0;
  let headX = 0.0, headY = 0.0;
  let lShX = 0.05, rShX = 0.05, lShZ = 0.16, rShZ = -0.16;
  let lElX = -0.25, rElX = -0.25;
  let stanceFoot = 'both';
  let phaseLabel = 'idle_stance';
  let stanceEpoch = 0;

  if (intent === 'retreat' || intent === 'run') {
    const moveT = Math.max(0.0, t - onset);
    const stepPeriod = 0.56;
    const nHalfSteps = moveT / stepPeriod;
    const stepIdx = Math.floor(nHalfSteps);
    const frac = clamp(nHalfSteps - stepIdx, 0, 1);
    const sFrac = smooth(frac);
    stanceEpoch = stepIdx + 1;

    // Stance foot swings hipX from -0.26 (front +Z) -> +0.26 (rear -Z) with fixed knee 0.10.
    // Exact leg arc change in root-local Z = (-L_t sin(-0.26) - L_s sin(-0.16)) - (-L_t sin(0.26) - L_s sin(0.36))
    const stanceHipStart = -0.26;
    const stanceHipEnd = 0.26;
    const stanceKnee = 0.10;
    const zStanceStart = legLocalZ(stanceHipStart, stanceKnee);
    const zStanceEnd = legLocalZ(stanceHipEnd, stanceKnee);
    const arcStride = zStanceStart - zStanceEnd; // ~0.44m natural step matching foot arc

    const curStanceHip = lerp(stanceHipStart, stanceHipEnd, sFrac);
    const curStepDelta = zStanceStart - legLocalZ(curStanceHip, stanceKnee);
    const totalStepsPossible = Math.max(1.0, (dur - onset) / stepPeriod);
    const scaleMove = Math.min(1.0, retreatDist / Math.max(0.1, arcStride * totalStepsPossible));

    const prevDist = stepIdx * arcStride * scaleMove;
    const stepAdvance = curStepDelta * scaleMove;
    const actualDist = Math.min(retreatDist, prevDist + stepAdvance);

    rootX = baseX + awayX * actualDist;
    rootZ = baseZ + awayZ * actualDist;
    rootYaw = lerp(baseYaw, Math.atan2(awayX, awayZ), easeOut(uReact * 1.5));

    const leftIsSwing = (stepIdx % 2 === 0);
    stanceFoot = moveT <= 0.01 ? 'both' : (leftIsSwing ? 'right' : 'left');
    phaseLabel = moveT < 0.18 ? 'notice_anticipation' : 'retreat_stride';

    // Swing foot moves from rear (+hipX) to front (-hipX) with mid-swing knee lift
    const swingHip = lerp(stanceHipEnd * scaleMove, stanceHipStart * scaleMove, sFrac);
    const swingKnee = stanceKnee + Math.sin(frac * Math.PI) * 0.72;
    const stanceHipScaled = lerp(stanceHipStart * scaleMove, stanceHipEnd * scaleMove, sFrac);

    if (leftIsSwing) {
      lHipX = swingHip; lKnX = swingKnee; lAnX = -(lHipX + lKnX) * 0.65;
      rHipX = stanceHipScaled; rKnX = stanceKnee; rAnX = -(rHipX + rKnX);
      lShX = 0.44 * (frac - 0.5); rShX = -0.44 * (frac - 0.5);
    } else {
      rHipX = swingHip; rKnX = swingKnee; rAnX = -(rHipX + rKnX) * 0.65;
      lHipX = stanceHipScaled; lKnX = stanceKnee; lAnX = -(lHipX + lKnX);
      rShX = 0.44 * (frac - 0.5); lShX = -0.44 * (frac - 0.5);
    }
    lElX = -0.88; rElX = -0.88;
    spineX = 0.14 * uReact;
    headY = lerp(0.0, -0.42, Math.sin(u * Math.PI) * 0.75);
    headX = 0.06;
  } else if (intent === 'brace' || intent === 'take_step') {
    // Grounded 4-phase reaction: look -> startle weight shift -> exact step back (left foot) -> braced hold
    const uLook = smooth(clamp((t - onset * 0.45) / 0.35, 0, 1));
    const uStep = smooth(clamp((t - onset) / 0.62, 0, 1));
    phaseLabel = uStep < 0.02 ? 'notice_gaze' : (uStep < 0.96 ? 'step_back_brace' : 'braced_hold');
    stanceFoot = (uStep > 0.04 && uStep < 0.96) ? 'right' : 'both';
    stanceEpoch = uStep > 0.04 ? (uStep >= 0.96 ? 2 : 1) : 0;

    // Right foot stays pinned! As root shifts backward away from threat, right leg hip leans forward slightly
    const rHipEnd = -0.22;
    const rHipStart = 0.02;
    rHipX = lerp(rHipStart, rHipEnd, uStep);
    rKnX = lerp(0.10, 0.24, uStep);
    rAnX = -(rHipX + rKnX);

    // Match root step-back distance EXACTLY to right stance leg local Z travel along toward-threat/away axis!
    const exactStepDist = Math.min(retreatDist, Math.abs(legLocalZ(rHipX, rKnX) - legLocalZ(rHipStart, 0.10)));
    rootX = baseX + awayX * exactStepDist;
    rootZ = baseZ + awayZ * exactStepDist;
    rootYaw = lerp(baseYaw, towardYaw, uLook * 0.92);

    const swingArc = Math.sin(uStep * Math.PI);
    lHipX = lerp(0.02, -0.26, uStep);
    lKnX = lerp(0.10, 0.24, uStep) + swingArc * 0.48;
    lAnX = -(lHipX + lKnX) * 0.85;

    spineX = 0.08 * uStep - 0.06 * Math.sin(uLook * Math.PI);
    chestY = 0.14 * uLook;
    headY = 0.22 * uLook;
    headX = -0.06 * uLook;
    lShX = lerp(0.05, -0.52, uStep);
    rShX = lerp(0.05, -0.44, uStep);
    lShZ = lerp(0.16, 0.34, uStep);
    rShZ = lerp(-0.16, -0.30, uStep);
    lElX = lerp(-0.25, -0.90, uStep);
    rElX = lerp(-0.25, -0.82, uStep);
  } else if (intent === 'inspect') {
    const stepBack = smooth(clamp((u - 0.55) / 0.38, 0, 1));
    phaseLabel = stepBack < 0.05 ? 'inspect_seam' : 'step_back';
    rHipX = lerp(0.02, -0.20, stepBack);
    rKnX = lerp(0.10, 0.22, stepBack);
    rAnX = -(rHipX + rKnX);
    lHipX = lerp(-0.02, -0.22, stepBack);
    lKnX = lerp(0.10, 0.22, stepBack) + Math.sin(stepBack * Math.PI) * 0.36;
    lAnX = -(lHipX + lKnX) * 0.85;
    stanceFoot = stepBack > 0.05 && stepBack < 0.95 ? 'right' : 'both';
    stanceEpoch = stepBack > 0.05 ? 1 : 0;

    const exactStep = Math.min(retreatDist, Math.abs(legLocalZ(rHipX, rKnX) - legLocalZ(0.02, 0.10)));
    rootX = baseX + awayX * exactStep;
    rootZ = baseZ + awayZ * exactStep;
    rShX = -0.82 - Math.sin(t * 2.1) * 0.05;
    rElX = -0.60;
    headX = 0.22; headY = -0.16 + Math.sin(t * 1.4) * 0.10;
    chestY = 0.10;
  } else {
    const sway = Math.sin(t * 1.25);
    phaseLabel = 'sober_scan';
    stanceFoot = 'both';
    lHipX = 0.0; rHipX = 0.0;
    lKnX = 0.10; rKnX = 0.10;
    lAnX = -0.10; rAnX = -0.10;
    rShX = -0.60 + sway * 0.07;
    rElX = -0.52;
    headX = -0.10;
    headY = sway * 0.20;
    spineX = 0.10;
  }

  const spanL = legSpanY(lHipX, lKnX);
  const spanR = legSpanY(rHipX, rKnX);
  const stanceSpan = stanceFoot === 'left' ? spanL : (stanceFoot === 'right' ? spanR : Math.max(spanL, spanR));
  const reqPelvisY = HIP_OFFSET_Y + stanceSpan;
  const drop = reqPelvisY - PELVIS_DEFAULT_Y;

  return {
    t: Number(Number(t || 0).toFixed(4)),
    root_pos: [rootX, groundY, rootZ],
    root_yaw: rootYaw,
    stance_foot: stanceFoot,
    stance_epoch: stanceEpoch,
    phase_label: phaseLabel,
    action_intent: intent,
    away_vec: [awayX, awayZ],
    pose: {
      drop,
      spine: [spineX, spineY, 0],
      chest: [0, chestY, 0],
      head: [headX, headY, 0],
      lSh: [lShX, 0, lShZ], rSh: [rShX, 0, rShZ],
      lEl: [lElX, 0, 0], rEl: [rElX, 0, 0],
      lHip: [lHipX, 0, 0.06], rHip: [rHipX, 0, -0.06],
      lKn: [lKnX, 0, 0], rKn: [rKnX, 0, 0],
      lAn: [lAnX, 0, -0.06], rAn: [rAnX, 0, 0.06],
    },
  };
}

const _tmpPelvis = new THREE.Vector3();
const _tmpLFoot = new THREE.Vector3();
const _tmpRFoot = new THREE.Vector3();

export function applyGroundedCharacterPose(human, evalRes) {
  if (!human || !evalRes) return;
  human.root.position.set(...evalRes.root_pos);
  human.root.rotation.y = evalRes.root_yaw;
  human.setPose(evalRes.pose);
  human.root.updateMatrixWorld(true);
}

export function getCharacterPerformanceTelemetry(human, evalRes, stanceTracker = null, threatWorld = [0, 1.4, -4.5]) {
  if (!human || !human.j) return null;
  human.root.updateMatrixWorld(true);
  human.j.pelvis.getWorldPosition(_tmpPelvis);
  _tmpLFoot.set(0, -SOLE_DROP, 0.05);
  _tmpRFoot.set(0, -SOLE_DROP, 0.05);
  human.j.lAn.localToWorld(_tmpLFoot);
  human.j.rAn.localToWorld(_tmpRFoot);

  const groundY = Number(evalRes?.root_pos?.[1] || 0.0);
  const lErr = _tmpLFoot.y - groundY;
  const rErr = _tmpRFoot.y - groundY;
  const stFoot = evalRes?.stance_foot || 'both';
  const stEpoch = Number(evalRes?.stance_epoch || 0);
  const curT = Number(evalRes?.t ?? 0);
  if (stanceTracker && stanceTracker.lastT != null && curT < stanceTracker.lastT - 1e-4) {
    stanceTracker.epoch = -1;
    stanceTracker.foot = '';
    stanceTracker.anchorXZ = null;
    stanceTracker.originXZ = null;
  }
  if (stanceTracker) {
    stanceTracker.lastT = curT;
    if (!stanceTracker.originXZ || curT <= 0.05) {
      stanceTracker.originXZ = [_tmpPelvis.x, _tmpPelvis.z];
    }
  }
  let slideM = 0.0;
  if (stanceTracker && stFoot !== 'both') {
    const activeVec = stFoot === 'left' ? [_tmpLFoot.x, _tmpLFoot.z] : [_tmpRFoot.x, _tmpRFoot.z];
    if (stanceTracker.epoch !== stEpoch || stanceTracker.foot !== stFoot) {
      stanceTracker.epoch = stEpoch;
      stanceTracker.foot = stFoot;
      stanceTracker.anchorXZ = activeVec;
    } else if (stanceTracker.anchorXZ) {
      slideM = Math.hypot(activeVec[0] - stanceTracker.anchorXZ[0], activeVec[1] - stanceTracker.anchorXZ[1]);
    }
  } else if (stanceTracker) {
    stanceTracker.epoch = stEpoch;
    stanceTracker.foot = stFoot;
    stanceTracker.anchorXZ = null;
  }

  let moveDot = 0.0;
  if (stanceTracker && stanceTracker.originXZ) {
    const dx = _tmpPelvis.x - stanceTracker.originXZ[0];
    const dz = _tmpPelvis.z - stanceTracker.originXZ[1];
    const disp = Math.hypot(dx, dz);
    const tx = Number(threatWorld[0] || 0) - stanceTracker.originXZ[0];
    const tz = Number(threatWorld[2] || 0) - stanceTracker.originXZ[1];
    const tLen = Math.hypot(tx, tz);
    if (disp > 0.03 && tLen > 0.05) {
      moveDot = (dx * tx + dz * tz) / (disp * tLen);
    }
  }

  return {
    action_intent: evalRes?.action_intent || 'brace',
    action_phase: evalRes?.phase_label || 'idle_stance',
    stance_foot: stFoot,
    world_pelvis: [Number(_tmpPelvis.x.toFixed(4)), Number(_tmpPelvis.y.toFixed(4)), Number(_tmpPelvis.z.toFixed(4))],
    left_foot_world: [Number(_tmpLFoot.x.toFixed(4)), Number(_tmpLFoot.y.toFixed(4)), Number(_tmpLFoot.z.toFixed(4))],
    right_foot_world: [Number(_tmpRFoot.x.toFixed(4)), Number(_tmpRFoot.y.toFixed(4)), Number(_tmpRFoot.z.toFixed(4))],
    left_foot_ground_err_m: Number(lErr.toFixed(4)),
    right_foot_ground_err_m: Number(rErr.toFixed(4)),
    stance_slide_m: Number(slideM.toFixed(4)),
    move_toward_threat_dot: Number(moveDot.toFixed(4)),
    threat_distance_m: Number(Math.hypot(_tmpPelvis.x - threatWorld[0], _tmpPelvis.z - threatWorld[2]).toFixed(3)),
  };
}
"""
