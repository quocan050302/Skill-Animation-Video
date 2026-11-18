"""Procedural 1940 Tacoma Narrows Bridge ("Galloping Gertie") 3D Scene Library (R2 Repaired).

Strict Engineering & Historical Integrity Guarantees:
- Illustrative 3D reconstruction calibrated visually (non-CFD, explicitly labeled `stylized_illustrative`).
- Pure deterministic `motionAtTime(lt, params)` curves built on `physical_motion_primitives.js`
  and `character_performance.js` (out-of-order frame seeks yield identical geometry & telemetry).
- R2 Structural Repair:
  * Continuous 66-subdivision deformable asphalt roadway + white edge curbs + yellow divider +
    8-ft solid plate stiffening girders with vertical web stiffeners (zero stair-stepping boxes).
  * 44 suspender rods coupled every frame to exact deformed deck-edge coordinates before collapse.
  * Hinged 3-section center-span failure sequence (`left seam tear -> hinged plunge -> water splash plume`
    synchronized at exact `water_impact_time_sec`) + non-resetting `aftermath` state.
  * Explicit `userData.semanticRole` tags (`subject`, `causal_feature`, `character`, `environment`)
    for independent decoded object-ID matte QA.
"""

from __future__ import annotations


TACOMA_BRIDGE_SCENES_JS = r"""import * as THREE from 'three';
import { clamp, easeInOut, easeOut, lerp } from './anim.js';
import { buildRegisteredCharacter } from './character_action_rig.js';
import { computeAnchorsTelemetry } from './aircraft_window_scenes.js';
import {
  evaluateTorsionSpan,
  evaluateCollapseTrajectory,
  getPhysicalTelemetry,
} from './physical_motion_primitives.js';
import {
  evaluateCharacterPose,
  applyGroundedCharacterPose,
  getCharacterPerformanceTelemetry,
} from './character_performance.js';

function shadow(o) {
  o.traverse(c => {
    if (c.isMesh || c.isInstancedMesh) {
      c.castShadow = true;
      c.receiveShadow = true;
    }
  });
  return o;
}

function tagSemantic(obj, role) {
  if (!obj) return obj;
  obj.userData = obj.userData || {};
  obj.userData.semanticRole = role;
  return obj;
}

function addFedora1940(human, hex = 0x4b4036) {
  const mat = new THREE.MeshStandardMaterial({ color: hex, roughness: 0.84, metalness: 0.04 });
  const bandMat = new THREE.MeshStandardMaterial({ color: 0x161413, roughness: 0.65 });
  const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.185, 0.19, 0.014, 24), mat);
  brim.position.set(0, 0.115, 0.01);
  const crown = new THREE.Mesh(new THREE.CylinderGeometry(0.095, 0.115, 0.095, 22), mat);
  crown.position.set(0, 0.165, 0.0);
  const ribbon = new THREE.Mesh(new THREE.CylinderGeometry(0.117, 0.117, 0.022, 22), bandMat);
  ribbon.position.set(0, 0.129, 0.0);
  human.j.head.add(brim, crown, ribbon);
}

/**
 * Period 1939/1940 Streamlined Coupe / Sedan (rounded fenders, chrome radiator grille, rubber tires).
 */
export function makePeriodCar1940(bodyHex = 0x993b32) {
  const g = new THREE.Group();
  const paint = new THREE.MeshStandardMaterial({ color: bodyHex, roughness: 0.34, metalness: 0.32 });
  const chrome = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, roughness: 0.20, metalness: 0.90 });
  const glass = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.16, metalness: 0.25 });
  const rubber = new THREE.MeshStandardMaterial({ color: 0x141619, roughness: 0.88 });

  const chassis = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.16, 1.05), paint);
  chassis.position.y = 0.18;
  const hood = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.15, 0.38), paint);
  hood.position.set(0, 0.24, 0.31);
  const cabin = new THREE.Mesh(new THREE.BoxGeometry(0.40, 0.18, 0.50), paint);
  cabin.position.set(0, 0.32, -0.08);
  const windshield = new THREE.Mesh(new THREE.BoxGeometry(0.36, 0.12, 0.04), glass);
  windshield.position.set(0, 0.33, 0.17);
  windshield.rotation.x = -0.35;
  const grille = new THREE.Mesh(new THREE.BoxGeometry(0.20, 0.13, 0.03), chrome);
  grille.position.set(0, 0.22, 0.51);
  const bumper = new THREE.Mesh(new THREE.BoxGeometry(0.48, 0.035, 0.04), chrome);
  bumper.position.set(0, 0.12, 0.55);
  g.add(chassis, hood, cabin, windshield, grille, bumper);

  for (const [wx, wz] of [[-0.24, -0.30], [0.24, -0.30], [-0.24, 0.32], [0.24, 0.32]]) {
    const tire = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.11, 0.06, 18), rubber);
    tire.rotation.z = Math.PI / 2;
    tire.position.set(wx, 0.11, wz);
    const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.07, 12), chrome);
    hub.rotation.z = Math.PI / 2;
    hub.position.set(wx, 0.11, wz);
    g.add(tire, hub);
  }
  return shadow(g);
}

/**
 * Animated Puget Sound Narrows Environment (textured strait water, coastal cliffs, pines & 3D collapse splash plume).
 */
export function makePugetSoundEnvironment({ includeShore = true } = {}) {
  const root = new THREE.Group();
  tagSemantic(root, 'environment');

  const waterGeom = new THREE.PlaneGeometry(42, 42, 48, 48);
  waterGeom.rotateX(-Math.PI / 2);
  const wPos = waterGeom.attributes.position;
  const wBaseY = new Float32Array(wPos.count);
  for (let i = 0; i < wPos.count; i++) wBaseY[i] = wPos.getY(i);

  const waterMat = new THREE.MeshStandardMaterial({
    color: 0x0f3b4d,
    emissive: 0x061e2b,
    emissiveIntensity: 0.28,
    roughness: 0.26,
    metalness: 0.24,
    side: THREE.DoubleSide,
  });
  const waterMesh = new THREE.Mesh(waterGeom, waterMat);
  waterMesh.position.y = 0.0;
  waterMesh.receiveShadow = true;
  tagSemantic(waterMesh, 'environment');
  root.add(waterMesh);

  if (includeShore) {
    const rockMat = new THREE.MeshStandardMaterial({ color: 0x5c6352, roughness: 0.90, metalness: 0.02 });
    const shoreSlopeMat = new THREE.MeshStandardMaterial({ color: 0x47523f, roughness: 0.92 });
    const pineMat = new THREE.MeshStandardMaterial({ color: 0x264b2e, roughness: 0.86 });

    const cliffL = new THREE.Mesh(new THREE.BoxGeometry(9.0, 3.3, 22), rockMat);
    cliffL.position.set(-12.0, 1.45, 0);
    const cliffR = new THREE.Mesh(new THREE.BoxGeometry(9.0, 3.3, 22), rockMat);
    cliffR.position.set(12.0, 1.45, 0);
    const bankL = new THREE.Mesh(new THREE.BoxGeometry(3.2, 1.5, 16), shoreSlopeMat);
    bankL.position.set(-7.6, 0.72, 0);
    const bankR = new THREE.Mesh(new THREE.BoxGeometry(3.2, 1.5, 16), shoreSlopeMat);
    bankR.position.set(7.6, 0.72, 0);
    root.add(cliffL, cliffR, bankL, bankR);

    for (const [tx, tz, sc] of [
      [-9.2, -2.5, 1.15], [-10.0, 2.2, 0.95], [-8.4, 0.2, 1.05],
      [9.2, -1.8, 1.05], [10.0, 3.1, 1.2], [8.5, 0.4, 1.0],
      [-8.8, 5.4, 0.95], [8.9, -4.6, 1.1],
    ]) {
      const cone = new THREE.Mesh(new THREE.ConeGeometry(0.60 * sc, 2.0 * sc, 8), pineMat);
      cone.position.set(tx, 3.25, tz);
      root.add(cone);
    }
  }

  // Multi-layered 3D water impact splash plumes + concentric shockwave rings + mist spray
  const splashGroup = new THREE.Group();
  tagSemantic(splashGroup, 'causal_feature');
  splashGroup.position.set(0, 0.04, 0);
  root.add(splashGroup);

  const splashRingMat = new THREE.MeshBasicMaterial({
    color: 0xdbeafe, transparent: true, opacity: 0.0, side: THREE.DoubleSide,
  });
  const splashRing1 = new THREE.Mesh(new THREE.RingGeometry(0.45, 0.85, 36), splashRingMat);
  splashRing1.rotation.x = -Math.PI / 2;
  const splashRing2 = new THREE.Mesh(new THREE.RingGeometry(0.25, 0.52, 36), splashRingMat.clone());
  splashRing2.rotation.x = -Math.PI / 2;
  splashGroup.add(splashRing1, splashRing2);

  const plumeMat = new THREE.MeshStandardMaterial({
    color: 0xe0f2fe, emissive: 0x7dd3fc, emissiveIntensity: 0.25,
    transparent: true, opacity: 0.0, roughness: 0.52,
  });
  const sprayDrops = [];
  const dropGeo = new THREE.SphereGeometry(0.11, 8, 6);
  const jetGeo = new THREE.CapsuleGeometry(0.08, 0.34, 4, 8);
  for (let i = 0; i < 22; i++) {
    const isJet = i % 3 === 0;
    const dm = new THREE.Mesh(isJet ? jetGeo : dropGeo, plumeMat);
    const ang = (i / 22) * Math.PI * 2 + (i % 2) * 0.14;
    const spread = 0.45 + (i % 5) * 0.26;
    dm.userData = {
      ang,
      rad: spread,
      hMax: isJet ? (0.85 + (i % 4) * 0.32) : (1.10 + (i % 5) * 0.34),
      tilt: 0.28 + (i % 3) * 0.16,
      isJet,
    };
    dm.visible = false;
    splashGroup.add(dm);
    sprayDrops.push(dm);
  }

  function updateEnv(t, splashProg = 0.0) {
    const arr = wPos.array;
    for (let i = 0; i < wPos.count; i++) {
      const x = arr[i * 3];
      const z = arr[i * 3 + 2];
      const radialDist = Math.hypot(x, z);
      const impactRipple = splashProg > 0.01
        ? Math.sin(radialDist * 2.4 - splashProg * 14.0) * 0.16 * (1.0 - splashProg) * Math.exp(-radialDist * 0.14)
        : 0.0;
      arr[i * 3 + 1] = wBaseY[i] + Math.sin(x * 0.68 + t * 2.0) * 0.065 + Math.cos(z * 0.85 - t * 1.7) * 0.055 + impactRipple;
    }
    wPos.needsUpdate = true;
    waterGeom.computeVertexNormals();

    if (splashProg > 0.005 && splashProg < 0.99) {
      const fade = Math.sin(clamp(splashProg, 0, 1) * Math.PI);
      const grow = 1.0 + splashProg * 4.2;
      splashRingMat.opacity = (1.0 - splashProg) * 0.62;
      splashRing1.scale.set(grow, grow, grow);
      splashRing2.material.opacity = (1.0 - splashProg) * 0.50;
      const grow2 = 0.7 + splashProg * 2.8;
      splashRing2.scale.set(grow2, grow2, grow2);

      plumeMat.opacity = fade * 0.78;
      sprayDrops.forEach((dm) => {
        const u = splashProg;
        const arcY = 4.0 * u * (1.0 - u) * dm.userData.hMax;
        const rNow = dm.userData.rad + u * (dm.userData.isJet ? 1.35 : 2.15);
        dm.visible = arcY > 0.04;
        dm.position.set(Math.cos(dm.userData.ang) * rNow, arcY, Math.sin(dm.userData.ang) * rNow);
        const sc = dm.userData.isJet ? (0.85 + fade * 0.45) : (0.65 + (1.0 - u) * 0.65);
        dm.scale.setScalar(sc);
        if (dm.userData.isJet) {
          dm.rotation.set(Math.sin(dm.userData.ang) * dm.userData.tilt, 0, -Math.cos(dm.userData.ang) * dm.userData.tilt);
        }
      });
    } else {
      splashRingMat.opacity = 0.0;
      splashRing2.material.opacity = 0.0;
      plumeMat.opacity = 0.0;
      sprayDrops.forEach(dm => { dm.visible = false; });
    }
  }

  return { root, waterMesh, splashGroup, update: updateEnv };
}

/**
 * Helper to create a deformable continuous bridge span strip (roadway + stripe + curbs + 8ft girders).
 */
function buildDeformableDeckStrip({
  uStart = 0.0,
  uEnd = 1.0,
  nSlices = 60,
  spanLength = 15.6,
  deckWidth = 1.24,
  girderDepth = 0.34,
  mats,
}) {
  const nVerts = (nSlices + 1) * 2;
  const mkRibbon = (mat) => {
    const geo = new THREE.BufferGeometry();
    const pos = new Float32Array(nVerts * 3);
    const idx = [];
    for (let i = 0; i < nSlices; i++) {
      const a = i * 2;
      const b = a + 1;
      const c = a + 2;
      const d = a + 3;
      idx.push(a, c, b, b, c, d);
    }
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setIndex(idx);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return { geo, pos, mesh };
  };

  const road = mkRibbon(mats.road);
  const stripe = mkRibbon(mats.stripe);
  const curbL = mkRibbon(mats.curb);
  const curbR = mkRibbon(mats.curb);
  const girderL = mkRibbon(mats.girder);
  const girderR = mkRibbon(mats.girder);

  const group = new THREE.Group();
  group.add(road.mesh, stripe.mesh, curbL.mesh, curbR.mesh, girderL.mesh, girderR.mesh);

  const halfSpan = spanLength * 0.5;
  const hw = deckWidth * 0.5;

  function setSlicePair(ribbon, i, x, y0, z0, y1, z1) {
    const arr = ribbon.pos;
    const o = i * 6;
    arr[o] = x; arr[o + 1] = y0; arr[o + 2] = z0;
    arr[o + 3] = x; arr[o + 4] = y1; arr[o + 5] = z1;
  }

  function updateStrip(evalFn) {
    for (let i = 0; i <= nSlices; i++) {
      const u = lerp(uStart, uEnd, i / nSlices);
      const x = -halfSpan + u * spanLength;
      const st = evalFn(u, x);
      const yC = st.yCenter;
      const r = st.rollRad;
      const cr = Math.cos(r);
      const sr = Math.sin(r);

      const pt = (ly, lz, dzOff = 0) => [
        yC + ly * cr + lz * sr,
        (st.dz || 0) + dzOff + lz * cr - ly * sr,
      ];

      const [ry0, rz0] = pt(0.05, hw);
      const [ry1, rz1] = pt(0.05, -hw);
      setSlicePair(road, i, x, ry0, rz0, ry1, rz1);

      const [sy0, sz0] = pt(0.062, 0.032);
      const [sy1, sz1] = pt(0.062, -0.032);
      setSlicePair(stripe, i, x, sy0, sz0, sy1, sz1);

      const [cl0, cz0] = pt(0.085, hw + 0.04);
      const [cl1, cz1] = pt(0.085, hw - 0.06);
      setSlicePair(curbL, i, x, cl0, cz0, cl1, cz1);

      const [cr0, crz0] = pt(0.085, -hw + 0.06);
      const [cr1, crz1] = pt(0.085, -hw - 0.04);
      setSlicePair(curbR, i, x, cr0, crz0, cr1, crz1);

      const [gl0, glz0] = pt(0.06, hw + 0.02);
      const [gl1, glz1] = pt(0.06 - girderDepth, hw + 0.02);
      setSlicePair(girderL, i, x, gl0, glz0, gl1, glz1);

      const [gr0, grz0] = pt(0.06, -hw - 0.02);
      const [gr1, grz1] = pt(0.06 - girderDepth, -hw - 0.02);
      setSlicePair(girderR, i, x, gr0, grz0, gr1, grz1);
    }
    for (const r of [road, stripe, curbL, curbR, girderL, girderR]) {
      r.geo.attributes.position.needsUpdate = true;
      r.geo.computeVertexNormals();
    }
  }

  return { group, update: updateStrip, uStart, uEnd };
}

/**
 * Full 1940 Tacoma Narrows Suspension Bridge Continuous Physical Rig (R2 Repaired).
 */
export function makeTacomaSuspensionBridgeRig({
  deckBaseY = 2.45,
  spanLength = 15.6,
  nSegments = 22,
  deckWidth = 1.24,
  showWindStreams = false,
  includeCar = true,
  semanticCenterFocus = true,
} = {}) {
  const root = new THREE.Group();
  tagSemantic(root, 'subject');

  const steelTower = new THREE.MeshStandardMaterial({ color: 0x9cb0bf, roughness: 0.44, metalness: 0.62 });
  const concreteMat = new THREE.MeshStandardMaterial({ color: 0xaab2b8, roughness: 0.86 });
  const deckRoadMat = new THREE.MeshStandardMaterial({ color: 0x252a32, roughness: 0.82, metalness: 0.08, side: THREE.DoubleSide });
  const curbMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, roughness: 0.72, metalness: 0.10, side: THREE.DoubleSide });
  const girderMat = new THREE.MeshStandardMaterial({ color: 0x627788, roughness: 0.44, metalness: 0.56, side: THREE.DoubleSide });
  const stripeMat = new THREE.MeshStandardMaterial({ color: 0xfacc15, emissive: 0x422006, emissiveIntensity: 0.18, roughness: 0.65, side: THREE.DoubleSide });
  const cableMat = new THREE.MeshStandardMaterial({ color: 0xcbd5e1, roughness: 0.36, metalness: 0.76 });
  const windMat = new THREE.MeshStandardMaterial({
    color: 0x38bdf8, emissive: 0x0ea5e9, emissiveIntensity: 0.85, transparent: true, opacity: 0.78, roughness: 0.25,
  });

  const stripMats = { road: deckRoadMat, stripe: stripeMat, curb: curbMat, girder: girderMat };

  // Two H-frame Art Deco steel towers anchored onto concrete caisson piers in the Narrows
  const towerXs = [-spanLength * 0.34, spanLength * 0.34];
  const towerTopY = deckBaseY + 2.55;
  for (const tx of towerXs) {
    const pier = new THREE.Mesh(new THREE.BoxGeometry(1.20, 0.74, 2.05), concreteMat);
    pier.position.set(tx, 0.18, 0);
    tagSemantic(pier, 'subject');
    root.add(pier);
    for (const sz of [-deckWidth * 0.54, deckWidth * 0.54]) {
      const leg = new THREE.Mesh(new THREE.BoxGeometry(0.25, towerTopY, 0.25), steelTower);
      leg.position.set(tx, towerTopY * 0.5 + 0.15, sz);
      tagSemantic(leg, 'subject');
      root.add(leg);
    }
    for (const cy of [deckBaseY + 0.68, deckBaseY + 1.54, towerTopY - 0.10]) {
      const strut = new THREE.Mesh(new THREE.BoxGeometry(0.21, 0.22, deckWidth * 1.26), steelTower);
      strut.position.set(tx, cy, 0);
      tagSemantic(strut, 'subject');
      root.add(strut);
    }
  }

  const halfSpan = spanLength * 0.5;
  const sagCenterY = deckBaseY + 0.44;
  function mainCableHeightAt(x) {
    const tPos = towerXs[1];
    if (Math.abs(x) <= tPos) {
      const rn = x / tPos;
      return lerp(sagCenterY, towerTopY, rn * rn);
    }
    const sideU = clamp((Math.abs(x) - tPos) / Math.max(0.5, halfSpan - tPos), 0, 1);
    return lerp(towerTopY, deckBaseY - 0.35, sideU);
  }

  // Main overhead catenary cable tubes (front + back Z rails)
  for (const sz of [-deckWidth * 0.54, deckWidth * 0.54]) {
    const pts = [];
    for (let k = 0; k <= 36; k++) {
      const x = -halfSpan + (k / 36) * spanLength;
      pts.push(new THREE.Vector3(x, mainCableHeightAt(x), sz));
    }
    const curve = new THREE.CatmullRomCurve3(pts);
    const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 0.048, 8, false), cableMat);
    tagSemantic(tube, 'subject');
    root.add(tube);
  }

  // 1. Continuous intact full-span ribbon (used pre-collapse)
  const intactRibbon = buildDeformableDeckStrip({
    uStart: 0.0, uEnd: 1.0, nSlices: 66, spanLength, deckWidth, girderDepth: 0.34, mats: stripMats,
  });
  tagSemantic(intactRibbon.group, semanticCenterFocus ? 'causal_feature' : 'subject');
  root.add(intactRibbon.group);

  // 2. Post-collapse split ribbons: Left stub [0..0.37], Right stub [0.63..1], plus 3 hinged falling center chunks!
  const uBreakL = 0.37;
  const uBreakR = 0.63;
  const leftStub = buildDeformableDeckStrip({
    uStart: 0.0, uEnd: uBreakL, nSlices: 24, spanLength, deckWidth, girderDepth: 0.34, mats: stripMats,
  });
  const rightStub = buildDeformableDeckStrip({
    uStart: uBreakR, uEnd: 1.0, nSlices: 24, spanLength, deckWidth, girderDepth: 0.34, mats: stripMats,
  });
  tagSemantic(leftStub.group, 'subject');
  tagSemantic(rightStub.group, 'subject');
  leftStub.group.visible = false;
  rightStub.group.visible = false;
  root.add(leftStub.group, rightStub.group);

  // Hinged 3-chunk falling center span (connected articulated steel deck + plate girders + center stripe)
  const fallingCenterGroup = new THREE.Group();
  tagSemantic(fallingCenterGroup, 'causal_feature');
  fallingCenterGroup.visible = false;
  root.add(fallingCenterGroup);

  const centerLen = (uBreakR - uBreakL) * spanLength;
  const chunkCount = 3;
  const chunkLen = centerLen / chunkCount;
  const fallingChunks = [];
  for (let k = 0; k < chunkCount; k++) {
    const cg = new THREE.Group();
    const roadM = new THREE.Mesh(new THREE.BoxGeometry(chunkLen * 0.99, 0.11, deckWidth), deckRoadMat);
    const stM = new THREE.Mesh(new THREE.BoxGeometry(chunkLen * 0.68, 0.125, 0.065), stripeMat);
    const cL = new THREE.Mesh(new THREE.BoxGeometry(chunkLen * 0.99, 0.14, 0.09), curbMat);
    cL.position.set(0, 0.02, deckWidth * 0.5);
    const cR = cL.clone();
    cR.position.z = -deckWidth * 0.5;
    const gL = new THREE.Mesh(new THREE.BoxGeometry(chunkLen * 0.99, 0.34, 0.06), girderMat);
    gL.position.set(0, -0.14, deckWidth * 0.52);
    const gR = gL.clone();
    gR.position.z = -deckWidth * 0.52;
    const truss = new THREE.Mesh(new THREE.BoxGeometry(chunkLen * 0.85, 0.12, deckWidth * 0.92), steelTower);
    truss.position.set(0, -0.22, 0);
    cg.add(roadM, stM, cL, cR, gL, gR, truss);
    fallingCenterGroup.add(cg);
    fallingChunks.push(cg);
  }

  // Fracture glow marker at break seam
  const sparkMat = new THREE.MeshBasicMaterial({ color: 0xfef08a, transparent: true, opacity: 0.0 });
  const breakSpark = new THREE.Mesh(new THREE.SphereGeometry(0.28, 14, 10), sparkMat);
  breakSpark.position.set(-halfSpan + uBreakL * spanLength, deckBaseY, 0);
  root.add(breakSpark);

  // 22 logical segment anchors + 44 frame-coupled suspender rods
  const segments = [];
  const segLen = spanLength / nSegments;
  const suspenders = [];
  for (let i = 0; i < nSegments; i++) {
    const uNorm = (i + 0.5) / nSegments;
    const xPos = -halfSpan + uNorm * spanLength;
    const segGroup = new THREE.Group();
    segGroup.position.set(xPos, deckBaseY, 0);

    for (const sz of [deckWidth * 0.525, -deckWidth * 0.525]) {
      const rib = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.32, 0.04), steelTower);
      rib.position.set(0, -0.10, sz);
      tagSemantic(rib, Math.abs(xPos) < spanLength * 0.20 ? 'causal_feature' : 'subject');
      segGroup.add(rib);
    }

    const edgeFront = new THREE.Object3D();
    edgeFront.position.set(0, 0.06, deckWidth * 0.52);
    const edgeBack = new THREE.Object3D();
    edgeBack.position.set(0, 0.06, -deckWidth * 0.52);
    segGroup.add(edgeFront, edgeBack);

    const isCenterSection = (uNorm > uBreakL && uNorm < uBreakR);
    segGroup.userData = {
      uNorm,
      xPos,
      isCenterSection,
      inMainSpan: Math.abs(xPos) <= towerXs[1] * 0.98,
      edgeFront,
      edgeBack,
    };
    root.add(segGroup);
    segments.push(segGroup);

    for (const [sideSign, edgeObj] of [[1, edgeFront], [-1, edgeBack]]) {
      const cY = mainCableHeightAt(xPos);
      const rodMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.017, 0.017, 1.0, 6), cableMat);
      tagSemantic(rodMesh, 'subject');
      root.add(rodMesh);
      suspenders.push({
        mesh: rodMesh,
        xPos,
        topZ: sideSign * deckWidth * 0.54,
        topY: cY,
        edgeObj,
        seg: segGroup,
        sideSign,
      });
    }
  }

  // Period 1940 sedan placed cleanly on a midspan roadway segment (vintage crimson-maroon for clear figure-ground pop)
  let car = null;
  if (includeCar) {
    car = makePeriodCar1940(0x993b32);
    tagSemantic(car, 'causal_feature');
    car.rotation.y = Math.PI * 0.5;
    car.position.set(0.0, 0.06, 0.25);
    const midIdx = Math.floor(nSegments * 0.45);
    segments[midIdx].add(car);
  }

  // Curling aerodynamic vortex streamlines hitting flat solid plate girder (visible when showWindStreams=true)
  const windRibbons = [];
  if (showWindStreams) {
    for (let w = 0; w < 7; w++) {
      const pts = [];
      for (let k = 0; k < 12; k++) {
        const zn = -1.95 + k * 0.36;
        const curlY = Math.sin(k * 0.72 + w * 0.8) * 0.22;
        pts.push(new THREE.Vector3(-1.8 + w * 0.58, deckBaseY - 0.14 + (w % 2 ? 0.26 : -0.22) + curlY, zn));
      }
      const wMesh = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 24, 0.028, 6, false), windMat);
      tagSemantic(wMesh, 'causal_feature');
      wMesh.userData.baseZ = -1.6 + w * 0.12;
      root.add(wMesh);
      windRibbons.push(wMesh);
    }
  }

  // Explicit 3D world anchors used by Attention Pointers & Telemetry
  const midSpanAnchor = new THREE.Object3D();
  const edgeFrontAnchor = new THREE.Object3D();
  const edgeBackAnchor = new THREE.Object3D();
  const girderAnchor = new THREE.Object3D();
  const breakSeamAnchor = new THREE.Object3D();
  const centerSeg = segments[Math.floor(nSegments * 0.5)];
  const seamSegIdx = Math.max(0, Math.floor(nSegments * uBreakL) - 1);
  const seamSeg = segments[seamSegIdx];
  midSpanAnchor.position.set(0, 0.14, 0.0);
  edgeFrontAnchor.position.set(0, 0.14, deckWidth * 0.52);
  edgeBackAnchor.position.set(0, 0.14, -deckWidth * 0.52);
  girderAnchor.position.set(0, -0.10, deckWidth * 0.54);
  centerSeg.add(midSpanAnchor, edgeFrontAnchor, edgeBackAnchor, girderAnchor);
  breakSeamAnchor.position.set(segLen * 0.64, 0.14, deckWidth * 0.30);
  seamSeg.add(breakSeamAnchor);

  const _wTop = new THREE.Vector3();
  const _wBot = new THREE.Vector3();
  const _wDelta = new THREE.Vector3();
  const _upY = new THREE.Vector3(0, 1, 0);

  let lastPhysTel = {
    vertex_disp_max_m: 0,
    deck_roll_span_rad: 0,
    collapse_active: false,
    cables_attached: true,
    collapse_drop_m: 0,
    water_contact_active: false,
    water_impact_time_sec: null,
    splash_progress: 0.0,
  };

  function updateBridge(lt, dur, {
    mode = 'torsion_heavy',
    verticalAmp = 0.24,
    torsionRad = 0.44,
    collapseOnsetSec = null,
    aftermathCollapsed = false,
  } = {}) {
    let maxDisp = 0.0;
    let maxRoll = 0.0;
    let maxDrop = 0.0;
    let collapseNow = false;
    let allAttached = true;
    let splashProg = 0.0;
    let waterHitT = null;

    const twGain = mode === 'wobble_hook' ? 0.48
      : (mode === 'vertical_wave' ? 0.22
      : (mode === 'aftermath' ? 0.06 : (1.0 + 0.20 * clamp(lt / Math.max(0.2, dur), 0, 1))));

    const evalDeckAtU = (u) => {
      const inMain = Math.abs(-halfSpan + u * spanLength) <= towerXs[1] * 0.98;
      const ev = evaluateTorsionSpan(lt, u, {
        verticalAmp: aftermathCollapsed ? 0.02 : verticalAmp,
        torsionRad: aftermathCollapsed ? 0.03 : torsionRad,
        omegaVert: 2.45,
        omegaTorsion: 3.25,
        twistGain: inMain ? twGain : twGain * 0.28,
        deckHalfWidth: deckWidth * 0.5,
      });
      return { yCenter: deckBaseY + ev.dyCenter, rollRad: ev.rollRad, dyCenter: ev.dyCenter };
    };

    collapseNow = Boolean(collapseOnsetSec != null && lt >= collapseOnsetSec);
    const showSplit = aftermathCollapsed || collapseNow;

    intactRibbon.group.visible = !showSplit;
    leftStub.group.visible = showSplit;
    rightStub.group.visible = showSplit;
    fallingCenterGroup.visible = collapseNow && !aftermathCollapsed;

    if (!showSplit) {
      intactRibbon.update(evalDeckAtU);
    } else {
      leftStub.update(evalDeckAtU);
      rightStub.update(evalDeckAtU);
    }

    if (collapseNow && !aftermathCollapsed) {
      const dtCol = Math.max(0.0, lt - collapseOnsetSec);
      const cTraj = evaluateCollapseTrajectory(lt, collapseOnsetSec, {
        baseY: deckBaseY,
        vx: 0.08,
        vz: 0.26,
        pitchRate: 1.45,
        rollRate: 0.95,
        floorY: -0.28,
      });
      waterHitT = Number((collapseOnsetSec + cTraj.hitWaterT).toFixed(3));
      splashProg = cTraj.splashProgress || 0.0;
      const hingeStage = clamp(dtCol / 0.36, 0, 1);

      fallingChunks.forEach((cg, k) => {
        const uC = lerp(uBreakL + 0.045, uBreakR - 0.045, k / Math.max(1, chunkCount - 1));
        const xBase = -halfSpan + uC * spanLength;
        const evC = evalDeckAtU(uC);
        const delayDrop = k * 0.07;
        const tChunk = Math.max(collapseOnsetSec, lt - delayDrop);
        const trC = evaluateCollapseTrajectory(tChunk, collapseOnsetSec, {
          baseY: deckBaseY,
          vx: (k - 1) * 0.14,
          vz: 0.24 + k * 0.04,
          pitchRate: 1.35 + k * 0.15,
          rollRate: 0.90,
          floorY: -0.28,
        });
        const hingeTiltZ = -hingeStage * (1.0 - k * 0.28) * 0.55;
        cg.position.set(xBase + trC.dx, evC.yCenter + trC.dy, trC.dz);
        cg.rotation.set(evC.rollRad + trC.rotX * 0.65, trC.rotZ * 0.2, hingeTiltZ + trC.rotZ * 0.4);
        maxDisp = Math.max(maxDisp, Math.abs(trC.dy));
        maxDrop = Math.max(maxDrop, Math.abs(trC.dy));
      });
      sparkMat.opacity = dtCol < 0.32 ? (1.0 - dtCol / 0.32) * 0.95 : 0.0;
      breakSpark.visible = sparkMat.opacity > 0.02;
    } else {
      breakSpark.visible = false;
      sparkMat.opacity = 0.0;
    }

    segments.forEach((seg) => {
      const { uNorm, isCenterSection } = seg.userData;
      const ev = evalDeckAtU(uNorm);
      if (aftermathCollapsed && isCenterSection) {
        seg.visible = false;
        return;
      }
      seg.visible = true;
      if (collapseNow && isCenterSection) {
        const trS = evaluateCollapseTrajectory(lt, collapseOnsetSec, {
          baseY: deckBaseY,
          vx: 0.05,
          vz: 0.24,
          pitchRate: 1.4,
          rollRate: 0.9,
          floorY: -0.28,
        });
        seg.position.set(seg.userData.xPos + trS.dx, ev.yCenter + trS.dy, trS.dz);
        seg.rotation.set(ev.rollRad + trS.rotX * 0.6, 0, trS.rotZ * 0.4);
      } else {
        const du = 0.015;
        const evNext = evalDeckAtU(clamp(uNorm + du, 0, 1));
        const evPrev = evalDeckAtU(clamp(uNorm - du, 0, 1));
        const slopePitch = Math.atan2(evNext.yCenter - evPrev.yCenter, Math.max(0.05, 2 * du * spanLength));
        seg.position.set(seg.userData.xPos, ev.yCenter, 0);
        seg.rotation.set(ev.rollRad, 0, slopePitch);
        maxDisp = Math.max(maxDisp, Math.abs(ev.dyCenter) + Math.abs(Math.sin(ev.rollRad) * deckWidth * 0.5));
        maxRoll = Math.max(maxRoll, Math.abs(ev.rollRad));
      }
    });

    root.updateMatrixWorld(true);
    suspenders.forEach((sp) => {
      if (!sp.seg.visible || (collapseNow && sp.seg.userData.isCenterSection)) {
        sp.mesh.position.set(sp.xPos, sp.topY - 0.58, sp.topZ);
        sp.mesh.scale.set(1, 1.16, 1);
        sp.mesh.rotation.set(Math.sin(lt * 3.1 + sp.xPos) * 0.18, 0, Math.cos(lt * 2.4) * 0.14);
        return;
      }
      _wTop.set(sp.xPos, sp.topY, sp.topZ);
      root.localToWorld(_wTop);
      sp.edgeObj.getWorldPosition(_wBot);
      _wDelta.subVectors(_wBot, _wTop);
      const dist = _wDelta.length();
      if (!Number.isFinite(dist) || dist < 0.01) allAttached = false;
      const mid = _wTop.clone().add(_wBot).multiplyScalar(0.5);
      root.worldToLocal(mid);
      sp.mesh.position.copy(mid);
      sp.mesh.scale.set(1, Math.max(0.05, dist), 1);
      const dir = _wDelta.normalize();
      sp.mesh.quaternion.setFromUnitVectors(_upY, dir);
    });

    windRibbons.forEach((wr, wi) => {
      wr.position.z = ((lt * 1.55 + wi * 0.35) % 1.4) - 0.7;
      wr.position.y = Math.sin(lt * 4.5 + wi) * 0.09;
    });

    lastPhysTel = {
      vertex_disp_max_m: Number(maxDisp.toFixed(4)),
      deck_roll_span_rad: Number(maxRoll.toFixed(4)),
      collapse_active: collapseNow,
      collapse_drop_m: Number(maxDrop.toFixed(4)),
      cables_attached: allAttached,
      water_contact_active: splashProg > 0.01,
      water_impact_time_sec: waterHitT,
      splash_progress: Number(splashProg.toFixed(3)),
    };
    return lastPhysTel;
  }

  return {
    root: shadow(root),
    segments,
    update: updateBridge,
    getPhysicalState: () => getPhysicalTelemetry({ motion_type: 'torsion_span' }, lastPhysTel),
    getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, {
      bridge_midspan_twist: midSpanAnchor,
      deck_twist_edge_l: edgeFrontAnchor,
      deck_twist_edge_r: edgeBackAnchor,
      plate_girder_windward: girderAnchor,
      suspender_cable_joint: edgeFrontAnchor,
      collapse_break_seam: breakSeamAnchor,
      aftermath_broken_gap: midSpanAnchor,
    }, []),
  };
}

/**
 * Shot S06: 1940 Shore Onlooker Grounded Reaction Rig (full 3/4 view toward twisting bridge, uncropped).
 */
export function makeTacomaShoreOnlookerRig(makeHumanFn, charSpec = {}) {
  const root = new THREE.Group();
  const rockLedge = new THREE.Mesh(
    new THREE.BoxGeometry(5.6, 0.42, 4.8),
    new THREE.MeshStandardMaterial({ color: 0x626b5c, roughness: 0.88 })
  );
  rockLedge.position.set(0, -0.21, 0);
  tagSemantic(rockLedge, 'environment');
  root.add(rockLedge);

  const actor = buildRegisteredCharacter(makeHumanFn, {
    character_id: charSpec.character_id || 'char_onlooker_1940_01',
    shirt_hex: charSpec.shirt_hex ?? 0x6e5c4a,
    pants_hex: charSpec.pants_hex ?? 0x26292e,
    collar_hex: 0xe5e7eb,
    shoe_hex: 0x161412,
  });
  addFedora1940(actor, 0x4b4036);
  tagSemantic(actor.root, 'character');
  root.add(actor.root);

  const headAnchor = new THREE.Object3D();
  headAnchor.position.set(0, 0.14, 0.05);
  actor.j.head.add(headAnchor);

  const guardRail = new THREE.Mesh(
    new THREE.BoxGeometry(4.4, 0.08, 0.12),
    new THREE.MeshStandardMaterial({ color: 0x7c5e40, roughness: 0.85 })
  );
  guardRail.position.set(0, 0.78, -1.75);
  tagSemantic(guardRail, 'environment');
  root.add(guardRail);

  const stanceTracker = { epoch: -1, foot: '', anchorXZ: null };
  let lastCharTel = null;

  function updateOnlooker(lt, dur, threatPos = [0, 2.5, -7.5]) {
    const res = evaluateCharacterPose(lt, {
      primary_intent: 'brace',
      duration_sec: dur,
      ground_y: 0.0,
      base_x: 0.22,
      base_z: 0.35,
      base_yaw: -0.45,
      reaction_onset_sec: Math.min(0.40, dur * 0.15),
      retreat_distance_m: 0.62,
      threat_world: threatPos,
    });
    applyGroundedCharacterPose(actor, res);
    lastCharTel = getCharacterPerformanceTelemetry(actor, res, stanceTracker, threatPos);
    return lastCharTel;
  }

  return {
    root: shadow(root),
    actor,
    update: updateOnlooker,
    getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, { shore_onlooker_head: headAnchor }, []),
    getCharTelemetry: () => lastCharTel,
  };
}
"""
