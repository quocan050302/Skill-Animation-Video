"""Procedural 1919 Boston North End Molasses Flood 3D Scene Library (ZDF Only — R2.2).

Composable pure Three.js scene modules strictly representing 1919 period structures,
riveted steel tank geometry, viscous molasses gravity-current waves, period characters,
elevated railway trestle impact, engineering lap-joint cutaway, rescue aftermath, and harbor
context overview.

Strict Engineering Guarantees:
- Zero modern props (no smartphones, modern SUVs, glass skyscrapers, or LED towers).
- Pure deterministic `update(lt, dur)` curves (identical across seek order and worker count).
- InstancedMesh used for repeated rivets, bricks, and trestle lattice bracing.
- Exposes real world-space focal anchors (`computeAnchorsTelemetry`) and live action state
  (`getNarrativeActionTelemetry`) per frame.
"""

from __future__ import annotations


BOSTON_MOLASSES_SCENES_JS = r"""import * as THREE from 'three';
import { materials } from './materials.js';
import { clamp, easeInOut, easeOut, lerp, range, smooth } from './anim.js';
import { buildRegisteredCharacter } from './character_action_rig.js';
import { LayeredCutaway } from './layered_cutaway.js';
import { computeAnchorsTelemetry } from './aircraft_window_scenes.js';
import { makeContinuousViscousSurface, evaluateSurfaceWave } from './physical_motion_primitives.js';
import { evaluateCharacterPose, applyGroundedCharacterPose, getCharacterPerformanceTelemetry } from './character_performance.js';

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

function addFlatCap1919(human, hex = 0x3a322c) {
  const capMat = new THREE.MeshStandardMaterial({ color: hex, roughness: 0.88, metalness: 0.04 });
  const crown = new THREE.Mesh(new THREE.CylinderGeometry(0.115, 0.125, 0.068, 18), capMat);
  crown.position.set(0, 0.118, -0.012);
  crown.rotation.x = -0.08;
  const brim = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.016, 0.11), capMat);
  brim.position.set(0, 0.088, 0.105);
  brim.rotation.x = 0.12;
  human.j.head.add(crown, brim);
}

function addWorkerApron1919(human, hex = 0x7b6a56) {
  const mat = new THREE.MeshStandardMaterial({ color: hex, roughness: 0.92, metalness: 0.02 });
  const bib = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.42, 0.03), mat);
  bib.position.set(0, -0.04, 0.135);
  human.j.chest.add(bib);
  const skirt = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.19, 0.34, 16, 1, false, -0.95, 1.9), mat);
  skirt.position.set(0, -0.14, 0.02);
  human.j.pelvis.add(skirt);
}

function makeOilLantern1919() {
  const g = new THREE.Group();
  const brass = new THREE.MeshStandardMaterial({ color: 0x6b5632, roughness: 0.42, metalness: 0.72 });
  const flame = new THREE.MeshStandardMaterial({
    color: 0xffd27a,
    emissive: 0xff9d2e,
    emissiveIntensity: 1.85,
    roughness: 0.25,
  });
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.065, 0.045, 14), brass);
  base.position.y = 0.022;
  const glass = new THREE.Mesh(new THREE.CylinderGeometry(0.042, 0.045, 0.095, 14), flame);
  glass.position.y = 0.092;
  const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.058, 0.04, 14), brass);
  cap.position.y = 0.155;
  const bail = new THREE.Mesh(new THREE.TorusGeometry(0.055, 0.008, 8, 20, Math.PI), brass);
  bail.position.y = 0.165;
  g.add(base, glass, cap, bail);
  const light = new THREE.PointLight(0xffad42, 0.85, 2.8, 1.6);
  light.position.y = 0.10;
  g.add(light);
  g.flameMat = flame;
  g.pointLight = light;
  return shadow(g);
}

function makeWoodenCrate1919(w = 0.48, h = 0.42, d = 0.48, hex = 0x7c5c3e) {
  const g = new THREE.Group();
  const wood = new THREE.MeshStandardMaterial({ color: hex, roughness: 0.88, metalness: 0.02 });
  const trim = new THREE.MeshStandardMaterial({ color: 0x5c422a, roughness: 0.90 });
  const box = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), wood);
  box.position.y = h * 0.5;
  g.add(box);
  for (const sx of [-w * 0.46, w * 0.46]) {
    const slat = new THREE.Mesh(new THREE.BoxGeometry(0.04, h * 1.01, d * 1.01), trim);
    slat.position.set(sx, h * 0.5, 0);
    g.add(slat);
  }
  return shadow(g);
}

function makeWoodenBarrel1919(r = 0.24, h = 0.66) {
  const g = new THREE.Group();
  const oak = new THREE.MeshStandardMaterial({ color: 0x7a5638, roughness: 0.86, metalness: 0.03 });
  const iron = new THREE.MeshStandardMaterial({ color: 0x2a2e33, roughness: 0.52, metalness: 0.78 });
  const body = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.86, r * 0.84, h, 18), oak);
  body.position.y = h * 0.5;
  const bulge = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h * 0.56, 18), oak);
  bulge.position.y = h * 0.5;
  g.add(body, bulge);
  for (const hy of [0.12, 0.34, 0.56]) {
    const hoop = new THREE.Mesh(new THREE.TorusGeometry(r * (hy === 0.34 ? 1.01 : 0.93), 0.012, 8, 22), iron);
    hoop.rotation.x = Math.PI / 2;
    hoop.position.y = h * (hy / 0.66);
    g.add(hoop);
  }
  return shadow(g);
}

function makeMolassesMaterial() {
  return new THREE.MeshStandardMaterial({
    color: 0x5c2708,
    emissive: 0x260d02,
    emissiveIntensity: 0.40,
    roughness: 0.22,
    metalness: 0.05,
  });
}

/**
 * 1. Composable 1919 North End Commercial Street Corridor
 */
export function makeNorthEndStreet1919({ streetLength = 14.0, streetWidth = 4.6, includeCart = true } = {}) {
  const root = new THREE.Group();
  tagSemantic(root, 'environment');

  const cobbleBaseMat = new THREE.MeshStandardMaterial({ color: 0x45494e, roughness: 0.86, metalness: 0.06 });
  const road = new THREE.Mesh(new THREE.BoxGeometry(streetWidth, 0.12, streetLength), cobbleBaseMat);
  road.position.set(0, -0.06, 0);
  root.add(road);

  // Instanced cobblestones for authentic 1919 street texture
  const cols = 10;
  const rows = 28;
  const stoneGeo = new THREE.BoxGeometry(0.32, 0.035, 0.38);
  const stoneMat = new THREE.MeshStandardMaterial({ color: 0x575c63, roughness: 0.82, metalness: 0.06 });
  const stones = new THREE.InstancedMesh(stoneGeo, stoneMat, cols * rows);
  const dummy = new THREE.Object3D();
  let sIdx = 0;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const stagger = (r % 2) * 0.16;
      const sx = -streetWidth * 0.42 + c * (streetWidth * 0.84 / (cols - 1)) + (stagger - 0.08);
      const sz = -streetLength * 0.46 + r * (streetLength * 0.92 / (rows - 1));
      dummy.position.set(sx, 0.008 + ((r * 7 + c * 3) % 3) * 0.004, sz);
      dummy.rotation.set(0, ((r + c) % 5 - 2) * 0.03, 0);
      dummy.updateMatrix();
      stones.setMatrixAt(sIdx++, dummy.matrix);
    }
  }
  stones.instanceMatrix.needsUpdate = true;
  root.add(stones);

  const curbMat = new THREE.MeshStandardMaterial({ color: 0x6b7075, roughness: 0.85 });
  for (const sx of [-streetWidth * 0.5 - 0.35, streetWidth * 0.5 + 0.35]) {
    const sidewalk = new THREE.Mesh(new THREE.BoxGeometry(0.95, 0.14, streetLength), curbMat);
    sidewalk.position.set(sx, 0.05, 0);
    root.add(sidewalk);
  }

  // 1919 Red-Brick Warehouses & Storefronts with instanced timber-sash windows
  const brickMatA = new THREE.MeshStandardMaterial({ color: 0x733a2c, roughness: 0.92, metalness: 0.03 });
  const brickMatB = new THREE.MeshStandardMaterial({ color: 0x5f3227, roughness: 0.92, metalness: 0.03 });
  const trimMat = new THREE.MeshStandardMaterial({ color: 0x3b2e26, roughness: 0.84 });
  const winPaneMat = new THREE.MeshStandardMaterial({ color: 0x262f3b, roughness: 0.35, metalness: 0.25 });

  const bldgConfigs = [
    [-3.65, -3.6, 2.2, 4.2, 3.8, brickMatA],
    [-3.65, 0.6, 2.2, 4.6, 3.8, brickMatB],
    [-3.65, 4.5, 2.2, 3.9, 3.4, brickMatA],
    [3.65, -3.2, 2.2, 4.4, 3.6, brickMatB],
    [3.65, 1.1, 2.2, 4.1, 4.0, brickMatA],
  ];
  const winGeo = new THREE.BoxGeometry(0.08, 0.72, 0.52);
  const winFrames = new THREE.InstancedMesh(winGeo, winPaneMat, bldgConfigs.length * 6);
  let wIdx = 0;

  for (const [bx, bz, bw, bh, bd, bmat] of bldgConfigs) {
    const bldg = new THREE.Mesh(new THREE.BoxGeometry(bw, bh, bd), bmat);
    bldg.position.set(bx, bh * 0.5, bz);
    const cornice = new THREE.Mesh(new THREE.BoxGeometry(bw + 0.18, 0.22, bd + 0.14), trimMat);
    cornice.position.set(bx, bh + 0.10, bz);
    root.add(bldg, cornice);

    const sideFaceX = bx < 0 ? bx + bw * 0.5 + 0.02 : bx - bw * 0.5 - 0.02;
    for (let fl = 0; fl < 2; fl++) {
      for (let wi = -1; wi <= 1; wi++) {
        dummy.position.set(sideFaceX, 1.35 + fl * 1.45, bz + wi * 1.02);
        dummy.rotation.set(0, 0, 0);
        dummy.updateMatrix();
        winFrames.setMatrixAt(wIdx++, dummy.matrix);
      }
    }
  }
  winFrames.instanceMatrix.needsUpdate = true;
  root.add(winFrames);

  // Period iron gas streetlamps
  const ironMat = new THREE.MeshStandardMaterial({ color: 0x1e2226, roughness: 0.48, metalness: 0.76 });
  const lampGlow = new THREE.MeshStandardMaterial({
    color: 0xffdca8, emissive: 0xffa73d, emissiveIntensity: 1.2, roughness: 0.25,
  });
  for (const [lx, lz] of [[-2.35, -1.8], [2.35, 1.8]]) {
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.065, 2.45, 10), ironMat);
    post.position.set(lx, 1.22, lz);
    const head = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.09, 0.28, 6), lampGlow);
    head.position.set(lx, 2.55, lz);
    root.add(post, head);
  }

  // Barrel & crate street staging
  const b1 = makeWoodenBarrel1919(); b1.position.set(-2.1, 0, 1.35);
  const b2 = makeWoodenBarrel1919(); b2.position.set(-1.95, 0, 2.02);
  const c1 = makeWoodenCrate1919(); c1.position.set(2.05, 0, -0.95);
  root.add(b1, b2, c1);

  // Period 1919 horse-drawn freight cart (wooden spoked wheels, leaf springs, shafts)
  let cartGroup = null;
  const wheelMeshes = [];
  if (includeCart) {
    cartGroup = new THREE.Group();
    const oak = new THREE.MeshStandardMaterial({ color: 0x6f4d31, roughness: 0.86 });
    const bed = new THREE.Mesh(new THREE.BoxGeometry(1.05, 0.28, 1.72), oak);
    bed.position.y = 0.64;
    const rail = new THREE.Mesh(new THREE.BoxGeometry(1.09, 0.22, 1.74), trimMat);
    rail.position.y = 0.86;
    const shaftL = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.028, 1.15, 8), oak);
    shaftL.rotation.x = Math.PI / 2; shaftL.position.set(-0.32, 0.56, 1.32);
    const shaftR = shaftL.clone(); shaftR.position.x = 0.32;
    cartGroup.add(bed, rail, shaftL, shaftR);

    for (const [wx, wz] of [[-0.62, -0.52], [0.62, -0.52], [-0.62, 0.55], [0.62, 0.55]]) {
      const wg = new THREE.Group();
      const rim = new THREE.Mesh(new THREE.TorusGeometry(0.32, 0.036, 10, 24), oak);
      rim.rotation.y = Math.PI / 2;
      const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.09, 12), ironMat);
      hub.rotation.z = Math.PI / 2;
      wg.add(rim, hub);
      for (let sp = 0; sp < 6; sp++) {
        const spoke = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.60, 6), oak);
        spoke.rotation.x = (sp * Math.PI) / 6;
        wg.add(spoke);
      }
      wg.position.set(wx, 0.36, wz);
      cartGroup.add(wg);
      wheelMeshes.push(wg);
    }
    cartGroup.position.set(0.85, 0, -1.35);
    cartGroup.rotation.y = -0.14;
    root.add(cartGroup);
  }

  return {
    root: shadow(root),
    cartGroup,
    wheelMeshes,
    heroLook: new THREE.Object3D(),
  };
}

/**
 * 2. Iconic 1915 USIA Riveted Molasses Tank
 */
export function makeMolassesStorageTank1919({ radius = 1.65, height = 3.25 } = {}) {
  const root = new THREE.Group();
  tagSemantic(root, 'subject');
  const steelMat = new THREE.MeshStandardMaterial({ color: 0x4f433b, roughness: 0.62, metalness: 0.48 });
  const darkBandMat = new THREE.MeshStandardMaterial({ color: 0x3b322c, roughness: 0.55, metalness: 0.58 });
  const concreteMat = new THREE.MeshStandardMaterial({ color: 0x707274, roughness: 0.90 });

  const plinth = new THREE.Mesh(new THREE.CylinderGeometry(radius + 0.14, radius + 0.22, 0.24, 36), concreteMat);
  plinth.position.y = 0.12;
  root.add(plinth);

  const shell = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, height, 40, 1, false), steelMat);
  shell.position.y = 0.24 + height * 0.5;
  root.add(shell);

  // Horizontal lap rings
  for (let t = 0; t <= 4; t++) {
    const band = new THREE.Mesh(
      new THREE.CylinderGeometry(radius + 0.022, radius + 0.022, 0.08, 40, 1, true),
      darkBandMat
    );
    band.position.y = 0.30 + (height * 0.92 * t) / 4;
    root.add(band);
  }

  // Dome rivets via InstancedMesh
  const rivGeo = new THREE.SphereGeometry(0.024, 8, 6);
  const rivMat = new THREE.MeshStandardMaterial({ color: 0x69594d, roughness: 0.48, metalness: 0.66 });
  const ringsCount = 4;
  const rivetsPerRing = 28;
  const rivMesh = new THREE.InstancedMesh(rivGeo, rivMat, ringsCount * rivetsPerRing);
  const dummy = new THREE.Object3D();
  let rIdx = 0;
  for (let ri = 0; ri < ringsCount; ri++) {
    const yPos = 0.32 + (height * 0.85 * ri) / (ringsCount - 1);
    for (let k = 0; k < rivetsPerRing; k++) {
      const ang = (k / rivetsPerRing) * Math.PI * 2;
      dummy.position.set(Math.sin(ang) * (radius + 0.026), yPos, Math.cos(ang) * (radius + 0.026));
      dummy.updateMatrix();
      rivMesh.setMatrixAt(rIdx++, dummy.matrix);
    }
  }
  rivMesh.instanceMatrix.needsUpdate = true;
  root.add(rivMesh);

  const roof = new THREE.Mesh(new THREE.ConeGeometry(radius + 0.06, 0.42, 40), darkBandMat);
  roof.position.y = 0.24 + height + 0.21;
  root.add(roof);

  // Access ladder on side
  const ladder = new THREE.Group();
  for (const lx of [-0.14, 0.14]) {
    const rail = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.016, height, 8), darkBandMat);
    rail.position.set(lx, 0.24 + height * 0.5, radius + 0.12);
    ladder.add(rail);
  }
  for (let ry = 0; ry < 9; ry++) {
    const rung = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.28, 8), darkBandMat);
    rung.rotation.z = Math.PI / 2;
    rung.position.set(0, 0.45 + ry * (height / 9.2), radius + 0.12);
    ladder.add(rung);
  }
  ladder.rotation.y = -0.62;
  root.add(ladder);

  return shadow(root);
}

/**
 * 3. Seam Leak & Rivet Rupture Assembly Rig
 */
export function makeSeamLeakAndRivetFailureRig({ mode = 'rupture' } = {}) {
  const root = new THREE.Group();
  tagSemantic(root, 'subject');
  const M = materials();
  const molMat = makeMolassesMaterial();
  const plateMat = new THREE.MeshStandardMaterial({ color: 0x4e423a, roughness: 0.58, metalness: 0.50 });
  const stressedMat = new THREE.MeshStandardMaterial({
    color: 0x61483c, emissive: 0x421406, emissiveIntensity: 0.25, roughness: 0.50, metalness: 0.55,
  });

  // Left & Right riveted tank curved panels meeting along central seam x = 0, z = 0.45
  const leftPlate = new THREE.Mesh(new THREE.BoxGeometry(1.15, 2.35, 0.08), plateMat);
  leftPlate.position.set(-0.57, 1.32, 0.36);
  leftPlate.rotation.y = -0.16;
  tagSemantic(leftPlate, 'causal_feature');

  const rightPlate = new THREE.Mesh(new THREE.BoxGeometry(1.15, 2.35, 0.08), stressedMat);
  rightPlate.position.set(0.57, 1.32, 0.36);
  rightPlate.rotation.y = 0.16;
  tagSemantic(rightPlate, 'causal_feature');

  const backFill = new THREE.Mesh(new THREE.CylinderGeometry(1.1, 1.1, 2.28, 24), molMat);
  backFill.position.set(0, 1.28, -0.78);
  tagSemantic(backFill, 'causal_feature');

  const plinth = new THREE.Mesh(new THREE.BoxGeometry(2.55, 0.26, 0.92), M.concrete || new THREE.MeshStandardMaterial({ color: 0x6f7275, roughness: 0.9 }));
  plinth.position.set(0, 0.13, 0.12);
  tagSemantic(plinth, 'reference_fixed');
  root.add(backFill, leftPlate, rightPlate, plinth);

  // Seam rivets arrayed along central vertical seam
  const rivets = [];
  const rivMat = new THREE.MeshStandardMaterial({ color: 0x8b6e5b, roughness: 0.42, metalness: 0.72 });
  for (let k = 0; k < 7; k++) {
    const r = new THREE.Mesh(new THREE.SphereGeometry(0.038, 12, 10), rivMat);
    const baseY = 0.52 + k * 0.26;
    r.position.set(0.0, baseY, 0.47);
    r.userData = {
      baseY,
      vx: ((k % 2 === 0 ? -1 : 1) * (0.65 + k * 0.18)),
      vy: 0.85 + (k % 3) * 0.42,
      vz: 1.55 + k * 0.22,
    };
    root.add(r);
    rivets.push(r);
  }

  // Slow leak drip drops + wooden catch barrel for chronic seepage scene
  const drips = [];
  for (let d = 0; d < 4; d++) {
    const drop = new THREE.Mesh(new THREE.SphereGeometry(0.032, 12, 10), molMat);
    drop.scale.set(0.75, 1.55, 0.75);
    drop.position.set(-0.02 + (d % 2) * 0.05, 1.65 - d * 0.36, 0.49);
    root.add(drop);
    drips.push(drop);
  }
  const streak = new THREE.Mesh(new THREE.CylinderGeometry(0.026, 0.042, 1.35, 12), molMat);
  streak.position.set(0.0, 0.92, 0.475);
  root.add(streak);

  // Burst surge jet + lower pool when rupture occurs
  const jet = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.55, 2.4, 20), molMat);
  jet.rotation.x = Math.PI * 0.46;
  jet.position.set(0, 0.95, 1.15);
  jet.visible = false;
  tagSemantic(jet, 'causal_feature');
  const pool = new THREE.Mesh(new THREE.CylinderGeometry(1.6, 1.75, 0.22, 28), molMat);
  pool.position.set(0, 0.11, 1.15);
  pool.scale.setScalar(0.01);
  tagSemantic(pool, 'effect_result');
  root.add(jet, pool);

  const seamAnchor = new THREE.Object3D();
  seamAnchor.position.set(0.0, 1.32, 0.52);
  root.add(seamAnchor);

  let lastState = { bulge: 0, ruptureProgress: 0, world_error_m: 0.005 };
  const _leftLipW = new THREE.Vector3();
  const _rightLipW = new THREE.Vector3();

  function updateSeepAndRupture(lt, dur, hitTimeRel = null) {
    const u = clamp(lt / Math.max(0.2, dur), 0, 1);
    if (mode === 'seep') {
      drips.forEach((d, idx) => {
        const cy = (lt * 0.55 + idx * 0.25) % 1.0;
        d.position.y = lerp(1.62, 0.24, cy);
        d.scale.set(0.72, 1.35 + cy * 0.45, 0.72);
      });
      streak.scale.set(1.0, 0.65 + 0.35 * Math.sin(lt * 1.4), 1.0);
      lastState = { bulge: 0.05, ruptureProgress: 0, world_error_m: 0.005 };
      return lastState;
    }

    const hitT = hitTimeRel != null ? hitTimeRel : dur * 0.44;
    const preRatio = clamp(lt / Math.max(0.1, hitT), 0, 1);
    const bulge = easeInOut(preRatio);
    const post = lt > hitT ? clamp((lt - hitT) / Math.max(0.25, dur - hitT), 0, 1) : 0.0;
    const open = easeOut(clamp(post * 1.65, 0, 1));

    // Strain bulge before rupture, then violent outward hinge split at hitT
    leftPlate.position.set(-0.57 - open * 0.48, 1.32, 0.36 + bulge * 0.06 + open * 0.16);
    leftPlate.rotation.y = -0.16 - open * 0.44;
    rightPlate.position.set(0.57 + open * 0.48, 1.32, 0.36 + bulge * 0.06 + open * 0.16);
    rightPlate.rotation.y = 0.16 + open * 0.44;
    stressedMat.emissiveIntensity = 0.2 + 0.85 * bulge * (1.0 - post * 0.4);

    rivets.forEach((r, k) => {
      if (lt <= hitT) {
        const vib = preRatio > 0.55 ? Math.sin(lt * 44 + k) * 0.008 * preRatio : 0;
        r.position.set(vib, r.userData.baseY, 0.47 + bulge * 0.05);
      } else {
        const dt = lt - hitT;
        r.position.set(
          r.userData.vx * dt,
          Math.max(0.06, r.userData.baseY + r.userData.vy * dt - 4.4 * dt * dt),
          0.52 + r.userData.vz * dt
        );
      }
    });

    if (post > 0.01) {
      jet.visible = true;
      jet.scale.set(0.5 + open * 0.9, 0.45 + open * 1.15, 0.5 + open * 0.9);
      jet.position.set(0, 0.98 - open * 0.18, 0.72 + open * 0.85);
      pool.scale.set(0.2 + open * 0.95, 1.0, 0.2 + open * 1.05);
    } else {
      jet.visible = false;
      pool.scale.setScalar(0.01);
    }
    root.updateMatrixWorld(true);
    _leftLipW.set(0.575, 0, 0);
    _rightLipW.set(-0.575, 0, 0);
    leftPlate.localToWorld(_leftLipW);
    rightPlate.localToWorld(_rightLipW);
    const seamGapM = _leftLipW.distanceTo(_rightLipW);
    lastState = {
      bulge: Number(bulge.toFixed(3)),
      ruptureProgress: Number(open.toFixed(3)),
      world_error_m: Number(seamGapM.toFixed(4)),
    };
    return lastState;
  }

  return {
    root: shadow(root),
    seamAnchor,
    occluders: [leftPlate, rightPlate],
    update: updateSeepAndRupture,
    getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, { tank_seam_drip: seamAnchor, tank_rivet_seam: seamAnchor }, []),
    getTelemetry: () => lastState,
  };
}

/**
 * 4. Viscous Moving 3D Molasses Gravity Current Wave Rig
 */
export function makeMolassesGravityCurrentRig({ width = 4.2, height = 1.65 } = {}) {
  const root = new THREE.Group();
  tagSemantic(root, 'causal_feature');
  const waveGroup = new THREE.Group();
  tagSemantic(waveGroup, 'causal_feature');

  // Continuous deformable 3D viscous surface (replaces disconnected spheres/bars cleanly)
  const viscousWave = makeContinuousViscousSurface({
    width,
    length: 5.8,
    height,
    nx: 40,
    nz: 22,
    colorHex: 0x5c2708,
    emissiveHex: 0x260d02,
  });
  waveGroup.add(viscousWave.mesh);

  // Floating timber planks & barrels riding the live crest height profile
  const plankMat = new THREE.MeshStandardMaterial({ color: 0x704d30, roughness: 0.86 });
  const barrel1 = makeWoodenBarrel1919(0.22, 0.58);
  barrel1.position.set(-0.95, height * 0.78, -0.25);
  barrel1.rotation.set(0.35, 0.4, 0.9);
  const crate1 = makeWoodenCrate1919(0.45, 0.38, 0.45);
  crate1.position.set(0.88, height * 0.72, -0.35);
  crate1.rotation.set(-0.22, 0.6, 0.28);
  const plank1 = new THREE.Mesh(new THREE.BoxGeometry(1.15, 0.08, 0.24), plankMat);
  plank1.position.set(0.05, height * 0.88, -0.08);
  plank1.rotation.set(0.18, -0.32, 0.15);
  waveGroup.add(barrel1, crate1, plank1);

  root.add(waveGroup);

  const crestAnchor = new THREE.Object3D();
  crestAnchor.position.set(0.0, height * 0.72, 0.45);
  waveGroup.add(crestAnchor);

  let waveFrontZ = -2.2;
  let lastSurfTel = { vertex_disp_max_m: 0.0, crest_y_max_m: height, nose_z_local: 0.72 };

  function updateWave(lt, dur, { zStart = -2.4, zEnd = 2.6, hitTimeRel = null, impactZ = -0.86 } = {}) {
    const u = clamp(lt / Math.max(0.2, dur), 0, 1);
    if (hitTimeRel != null && hitTimeRel > 0.05 && hitTimeRel < dur - 0.05) {
      if (lt <= hitTimeRel) {
        waveFrontZ = lerp(zStart, impactZ, easeOut(clamp(lt / hitTimeRel, 0, 1)));
      } else {
        waveFrontZ = lerp(impactZ, zEnd, easeInOut(clamp((lt - hitTimeRel) / Math.max(0.15, dur - hitTimeRel), 0, 1)));
      }
    } else {
      const adv = easeInOut(u);
      waveFrontZ = lerp(zStart, zEnd, adv);
    }
    waveGroup.position.z = waveFrontZ;
    lastSurfTel = viscousWave.update(lt);
    const surfA = evaluateSurfaceWave(lt, -0.44, 0.84, { baseHeight: height });
    const surfB = evaluateSurfaceWave(lt, 0.40, 0.82, { baseHeight: height });
    const surfMid = evaluateSurfaceWave(lt, 0.02, 0.87, { baseHeight: height });
    barrel1.position.y = Math.max(0.25, surfA.y - 0.05);
    barrel1.rotation.z = 0.9 + Math.sin(lt * 2.8) * 0.25;
    crate1.position.y = Math.max(0.22, surfB.y - 0.06);
    crate1.rotation.x = -0.22 + Math.cos(lt * 2.5) * 0.22;
    plank1.position.y = Math.max(0.28, surfMid.y + 0.02);
    plank1.position.z = -0.05 + surfMid.dz * 0.45;
    crestAnchor.position.set(0.0, surfMid.y * 0.85, 0.35 + surfMid.dz * 0.65);
    return {
      wave_front_z: Number(waveFrontZ.toFixed(3)),
      progress: Number(u.toFixed(3)),
      vertex_disp_max_m: lastSurfTel.vertex_disp_max_m,
      crest_y_max_m: lastSurfTel.crest_y_max_m,
      surface_mode: 'continuous_viscous_heightfield',
    };
  }

  return {
    root: shadow(root),
    waveGroup,
    crestAnchor,
    waveMesh: viscousWave.mesh,
    update: updateWave,
    getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, {
      molasses_reveal_crest: crestAnchor,
      wave_front_crest: crestAnchor,
    }, []),
    getTelemetry: () => ({ wave_front_z: Number(waveFrontZ.toFixed(3)), ...lastSurfTel, surface_mode: 'continuous_viscous_heightfield' }),
  };
}

/**
 * 5. Elevated Railway Steel Trestle & Street Impact Rig
 */
export function makeElevatedRailAndStreetImpactRig() {
  const root = new THREE.Group();
  tagSemantic(root, 'subject');
  const ironMat = new THREE.MeshStandardMaterial({ color: 0x262d35, roughness: 0.48, metalness: 0.76 });
  const trackMat = new THREE.MeshStandardMaterial({ color: 0x565e68, roughness: 0.38, metalness: 0.85 });
  const coachWood = new THREE.MeshStandardMaterial({ color: 0x5c3c28, roughness: 0.78 });
  const brass = new THREE.MeshStandardMaterial({ color: 0x9b7a42, roughness: 0.45, metalness: 0.65 });

  // Pivoting steel trestle bent near z = 0
  const bentGroup = new THREE.Group();
  const colL = new THREE.Mesh(new THREE.BoxGeometry(0.24, 3.25, 0.24), ironMat);
  colL.position.set(-1.35, 1.62, 0);
  const colR = new THREE.Mesh(new THREE.BoxGeometry(0.24, 3.25, 0.24), ironMat);
  colR.position.set(0.18, 1.62, 0);
  const crossGirder = new THREE.Mesh(new THREE.BoxGeometry(3.4, 0.34, 0.42), ironMat);
  crossGirder.position.set(-0.35, 3.12, 0);
  bentGroup.add(colL, colR, crossGirder);

  // Diagonal lattice bracing
  const braceGeo = new THREE.BoxGeometry(0.06, 1.38, 0.05);
  const braces = new THREE.InstancedMesh(braceGeo, ironMat, 4);
  const dummy = new THREE.Object3D();
  for (let b = 0; b < 4; b++) {
    dummy.position.set(-0.58 + (b % 2) * 0.0, 2.35 - Math.floor(b / 2) * 1.15, 0.08);
    dummy.rotation.set(0, 0, (b % 2 === 0 ? 1 : -1) * 0.62);
    dummy.updateMatrix();
    braces.setMatrixAt(b, dummy.matrix);
  }
  braces.instanceMatrix.needsUpdate = true;
  bentGroup.add(braces);

  // Longitudinal elevated rail deck & 1919 elevated railcar silhouette on top
  const viaduct = new THREE.Mesh(new THREE.BoxGeometry(2.15, 0.24, 8.5), ironMat);
  viaduct.position.set(-0.55, 3.38, 0);
  const railL = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.10, 8.5), trackMat);
  railL.position.set(-1.05, 3.55, 0);
  const railR = railL.clone(); railR.position.x = -0.05;
  const coach = new THREE.Group();
  const coachBody = new THREE.Mesh(new THREE.BoxGeometry(1.18, 0.92, 3.4), coachWood);
  coachBody.position.set(-0.55, 4.10, -0.4);
  const coachRoof = new THREE.Mesh(new THREE.BoxGeometry(1.24, 0.18, 3.5), ironMat);
  coachRoof.position.set(-0.55, 4.62, -0.4);
  const headlamp = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.10, 0.08, 12), brass);
  headlamp.rotation.x = Math.PI / 2; headlamp.position.set(-0.55, 3.92, 1.32);
  coach.add(coachBody, coachRoof, headlamp);
  bentGroup.add(viaduct, railL, railR, coach);
  root.add(bentGroup);

  const colAnchor = new THREE.Object3D();
  colAnchor.position.set(0.18, 1.48, 0.10);
  bentGroup.add(colAnchor);

  const waveRig = makeMolassesGravityCurrentRig({ width: 3.6, height: 1.55 });
  root.add(waveRig.root);

  let railDeflectionRad = 0;
  let lastWorldErrM = 2.0;
  const _colWorld = new THREE.Vector3();
  const _crestWorld = new THREE.Vector3();

  function updateRailImpact(lt, dur, hitTimeRel = null) {
    const hitT = hitTimeRel != null ? hitTimeRel : dur * 0.44;
    // Align oncoming fluid surge front (crestAnchor + 0.29 = group.z + 0.74) with column front face at hitT
    waveRig.update(lt, dur, { zStart: -2.6, zEnd: 1.65, hitTimeRel: hitT, impactZ: -0.86 });
    const post = lt > hitT ? clamp((lt - hitT) / Math.max(0.2, dur - hitT), 0, 1) : 0.0;
    const slam = easeOut(clamp(post * 1.85, 0, 1));
    const ring = post > 0 ? Math.exp(-(lt - hitT) * 3.8) * Math.sin((lt - hitT) * 20) * 0.015 : 0;
    railDeflectionRad = slam * 0.068 + ring;
    bentGroup.rotation.x = railDeflectionRad;
    bentGroup.rotation.z = -railDeflectionRad * 0.45;
    root.updateMatrixWorld(true);
    colAnchor.getWorldPosition(_colWorld);
    waveRig.crestAnchor.getWorldPosition(_crestWorld);
    const waveNoseZ = _crestWorld.z + 0.29;
    const waveBackZ = _crestWorld.z - 0.85;
    const colFrontZ = _colWorld.z - 0.22;
    const colBackZ = _colWorld.z + 0.02;
    if (waveNoseZ < colFrontZ) {
      lastWorldErrM = colFrontZ - waveNoseZ;
    } else if (waveBackZ > colBackZ) {
      lastWorldErrM = waveBackZ - colBackZ;
    } else {
      lastWorldErrM = 0.0;
    }
    return {
      rail_deflection_rad: Number(railDeflectionRad.toFixed(4)),
      hit_active: post > 0,
      world_error_m: Number(lastWorldErrM.toFixed(4)),
    };
  }

  return {
    root: shadow(root),
    colAnchor,
    update: updateRailImpact,
    getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, { elevated_rail_column: colAnchor }, []),
    getTelemetry: () => ({
      rail_deflection_rad: Number(railDeflectionRad.toFixed(4)),
      world_error_m: Number(lastWorldErrM.toFixed(4)),
    }),
  };
}

/**
 * 6. Composable 1919 Period Crowd & Worker Action Rig
 */
export function makePeriodCrowdActionRig(makeHumanFn, charSpec = {}, roleMode = 'pedestrians') {
  const root = new THREE.Group();
  tagSemantic(root, 'character');
  const actors = [];

  if (roleMode === 'dock_worker') {
    const w = buildRegisteredCharacter(makeHumanFn, {
      shirt_hex: charSpec.shirt_hex ?? 0x5a493a,
      pants_hex: charSpec.pants_hex ?? 0x35322f,
      collar_hex: 0xcbd5e1,
    });
    addFlatCap1919(w, 0x3f362f);
    addWorkerApron1919(w, 0x7c6b57);
    const lantern = makeOilLantern1919();
    lantern.position.set(0.0, -0.24, 0.08);
    w.j.rEl.add(lantern);
    w.root.position.set(-0.68, 0, 0.95);
    w.root.rotation.y = 0.72;
    root.add(w.root);
    actors.push(w);
  } else if (roleMode === 'rescuer_crew') {
    const specs = [
      { pos: [-0.62, 0, 0.25], rot: 0.42, coat: 0x26323e, hasLantern: true },
      { pos: [0.68, 0, 0.48], rot: -0.58, coat: 0x3b3530, hasLantern: true },
    ];
    for (const sp of specs) {
      const a = buildRegisteredCharacter(makeHumanFn, {
        shirt_hex: sp.coat,
        pants_hex: 0x1e242b,
        collar_hex: 0x9ca3af,
      });
      addFlatCap1919(a, 0x25282c);
      if (sp.hasLantern) {
        const lan = makeOilLantern1919();
        lan.position.set(0, -0.25, 0.08);
        a.j.rEl.add(lan);
      }
      a.root.position.set(...sp.pos);
      a.root.rotation.y = sp.rot;
      root.add(a.root);
      actors.push(a);
    }
  } else {
    const crowdSpecs = [
      { pos: [-0.72, 0, 0.65], rot: 0.22, coat: 0x4a3f35 },
      { pos: [0.22, 0, 1.35], rot: -0.15, coat: 0x39404a },
      { pos: [0.95, 0, 0.35], rot: -0.35, coat: 0x5c4636 },
    ];
    for (const sp of crowdSpecs) {
      const a = buildRegisteredCharacter(makeHumanFn, {
        shirt_hex: charSpec.shirt_hex ?? sp.coat,
        pants_hex: charSpec.pants_hex ?? 0x2b2824,
        collar_hex: 0xd6d3d1,
      });
      addFlatCap1919(a, 0x332d28);
      a.root.position.set(...sp.pos);
      a.root.rotation.y = sp.rot;
      a.userBasePos = sp.pos;
      a.userBaseRot = sp.rot;
      root.add(a.root);
      actors.push(a);
    }
  }

  let leadPos = [0, 0, 0];
  let leadCharTel = null;
  const stanceTrackers = actors.map(() => ({ epoch: -1, foot: '', anchorXZ: null }));

  function updateCrowd(lt, dur, actionMode = 'street_turn') {
    const u = clamp(lt / Math.max(0.2, dur), 0, 1);
    if (actionMode === 'inspect_leak' && actors[0]) {
      const evalRes = evaluateCharacterPose(lt, {
        primary_intent: 'inspect',
        duration_sec: dur,
        base_x: -0.68,
        base_z: 0.95,
        base_yaw: 0.72,
        reaction_onset_sec: Math.min(0.45, dur * 0.5),
        retreat_distance_m: 0.34,
        threat_world: [0.0, 1.3, -1.2],
      });
      applyGroundedCharacterPose(actors[0], evalRes);
      leadCharTel = getCharacterPerformanceTelemetry(actors[0], evalRes, stanceTrackers[0], [0.0, 1.3, -1.2]);
      leadPos = [actors[0].root.position.x, actors[0].root.position.y, actors[0].root.position.z];
    } else if (actionMode === 'retreat_run') {
      actors.forEach((a, idx) => {
        const bPos = a.userBasePos || [0, 0, 0.5];
        const evalRes = evaluateCharacterPose(lt, {
          primary_intent: 'retreat',
          duration_sec: dur,
          base_x: bPos[0],
          base_z: bPos[2],
          base_yaw: a.userBaseRot || 0.0,
          reaction_onset_sec: 0.14 + idx * 0.08,
          retreat_distance_m: 2.35 + idx * 0.18,
          threat_world: [bPos[0], 1.2, bPos[2] - 4.0],
        });
        applyGroundedCharacterPose(a, evalRes);
        const tel = getCharacterPerformanceTelemetry(a, evalRes, stanceTrackers[idx], [bPos[0], 1.2, bPos[2] - 4.0]);
        if (idx === 0) leadCharTel = tel;
      });
      if (actors[0]) leadPos = [actors[0].root.position.x, 0, actors[0].root.position.z];
    } else if (actionMode === 'rescuer_lantern') {
      actors.forEach((a, idx) => {
        const baseRot = idx === 0 ? 0.42 : -0.58;
        const evalRes = evaluateCharacterPose(lt + idx * 0.8, {
          primary_intent: 'help',
          duration_sec: dur,
          base_x: a.root.position.x,
          base_z: a.root.position.z,
          base_yaw: baseRot,
          retreat_distance_m: 0.0,
        });
        applyGroundedCharacterPose(a, evalRes);
        const tel = getCharacterPerformanceTelemetry(a, evalRes, stanceTrackers[idx]);
        if (idx === 0) leadCharTel = tel;
      });
      if (actors[0]) leadPos = [actors[0].root.position.x, 0, actors[0].root.position.z];
    } else {
      // street_turn: grounded turn & wary step back toward harbor rumble
      actors.forEach((a, idx) => {
        const bPos = a.userBasePos || [0, 0, 0.5];
        const evalRes = evaluateCharacterPose(lt, {
          primary_intent: 'brace',
          duration_sec: dur,
          base_x: bPos[0],
          base_z: bPos[2],
          base_yaw: a.userBaseRot || 0.0,
          reaction_onset_sec: 0.45 + idx * 0.12,
          retreat_distance_m: 0.42,
          threat_world: [0.0, 1.8, -4.8],
        });
        applyGroundedCharacterPose(a, evalRes);
        const tel = getCharacterPerformanceTelemetry(a, evalRes, stanceTrackers[idx], [0.0, 1.8, -4.8]);
        if (idx === 0) leadCharTel = tel;
      });
      if (actors[0]) leadPos = [actors[0].root.position.x, 0, actors[0].root.position.z];
    }
    return { lead_actor_pos: leadPos.map(v => Number(v.toFixed(3))), character_performance: leadCharTel };
  }

  return { root, actors, update: updateCrowd, getTelemetry: () => ({ lead_actor_pos: leadPos, character_performance: leadCharTel }) };
}

/**
 * 7. Respectful 1919 Rescue & Settled Aftermath Stage
 */
export function makeRescueAndAftermathRig(makeHumanFn) {
  const root = new THREE.Group();
  const molMat = makeMolassesMaterial();
  const woodMat = new THREE.MeshStandardMaterial({ color: 0x624732, roughness: 0.90 });

  const pool = new THREE.Mesh(new THREE.CylinderGeometry(2.65, 2.85, 0.16, 36), molMat);
  pool.position.set(0, 0.08, 0.15);
  root.add(pool);

  // Settled wooden beams and a half-submerged cart wheel (sober, dignified scale)
  for (const [bx, by, bz, rx, ry, rz] of [
    [-0.95, 0.24, -0.25, 0.18, 0.55, 0.24],
    [0.85, 0.22, -0.45, -0.14, -0.48, -0.28],
    [0.12, 0.18, 0.92, 0.06, 0.92, 0.08],
  ]) {
    const beam = new THREE.Mesh(new THREE.BoxGeometry(1.65, 0.14, 0.18), woodMat);
    beam.position.set(bx, by, bz);
    beam.rotation.set(rx, ry, rz);
    root.add(beam);
  }
  const wheel = new THREE.Mesh(new THREE.TorusGeometry(0.36, 0.045, 10, 22), woodMat);
  wheel.position.set(-0.22, 0.24, 0.18);
  wheel.rotation.set(1.12, 0.3, -0.25);
  root.add(wheel);

  const crowd = makePeriodCrowdActionRig(makeHumanFn, {}, 'rescuer_crew');
  root.add(crowd.root);

  const centerAnchor = new THREE.Object3D();
  centerAnchor.position.set(0.0, 0.92, 0.20);
  root.add(centerAnchor);

  return {
    root: shadow(root),
    centerAnchor,
    update(lt, dur) {
      return crowd.update(lt, dur, 'rescuer_lantern');
    },
    getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, { rescue_aftermath_center: centerAnchor }, []),
  };
}

/**
 * 8. True Layered Cutaway: 1915 Thin Lap-Joint Steel Tank Section
 */
export function makeBostonSteelSectionCutawayRig() {
  const root = new THREE.Group();
  tagSemantic(root, 'subject');
  const cutaway = new LayeredCutaway({
    id: 'tank_lap_joint_cutaway',
    worldAnchor: [0, 1.24, 0.08],
    clipNormal: [0, 0, -1],
    clipConstantStart: 0.34,
    clipConstantOpen: -0.05,
  });

  const outerPlateMat = new THREE.MeshStandardMaterial({ color: 0x4f4239, roughness: 0.56, metalness: 0.55 });
  const stressedLapMat = new THREE.MeshStandardMaterial({
    color: 0xb45309, emissive: 0x7c2d12, emissiveIntensity: 0.48, roughness: 0.42, metalness: 0.62,
  });
  const molMat = makeMolassesMaterial();
  const specRimMat = new THREE.MeshStandardMaterial({
    color: 0xf59e0b, emissive: 0xd97706, emissiveIntensity: 0.55, roughness: 0.35, metalness: 0.4,
  });

  // Layer 0: Outer riveted painted shell (slices open diagonally to reveal interior layers)
  const l0 = new THREE.Mesh(new THREE.BoxGeometry(1.42, 1.55, 0.08), outerPlateMat);
  l0.position.set(0, 1.24, 0.24);
  cutaway.addOuterShell(l0, { applyClip: true });

  // Layer 1: Thin under-spec 1915 lap joint + stressed rivet line (stepped width so core peeks clearly)
  const l1 = new THREE.Group();
  l1.position.set(-0.08, 1.24, 0.10);
  const thinLower = new THREE.Mesh(new THREE.BoxGeometry(1.06, 0.66, 0.04), stressedLapMat);
  thinLower.position.y = -0.32;
  const thinUpper = new THREE.Mesh(new THREE.BoxGeometry(1.06, 0.66, 0.04), outerPlateMat);
  thinUpper.position.set(0, 0.32, 0.042);
  l1.add(thinLower, thinUpper);
  const rivetHeads = [];
  for (let i = -2; i <= 2; i++) {
    const rh = new THREE.Mesh(new THREE.SphereGeometry(0.034, 12, 10), specRimMat);
    rh.position.set(i * 0.20, 0.0, 0.075);
    l1.add(rh);
    rivetHeads.push(rh);
  }
  cutaway.addInternalComponent('lap_joint_seam', l1, { layerIndex: 1, materialId: 'mat_1915_lap_steel' });

  // Layer 2: Interior hydrostatic molasses load column visible to the right & rear of lap step
  const l2 = new THREE.Group();
  l2.position.set(0.16, 1.24, -0.14);
  const molWall = new THREE.Mesh(new THREE.BoxGeometry(1.24, 1.48, 0.28), molMat);
  const molCutSide = new THREE.Mesh(
    new THREE.BoxGeometry(0.28, 1.38, 0.30),
    new THREE.MeshStandardMaterial({ color: 0x853b0e, emissive: 0x3b1504, emissiveIntensity: 0.45, roughness: 0.18 })
  );
  molCutSide.position.set(0.56, 0, 0.05);
  l2.add(molWall, molCutSide);
  cutaway.addInternalComponent('molasses_hydrostatic_core', l2, { layerIndex: 2, materialId: 'mat_molasses_core' });
  tagSemantic(l2, 'causal_feature');

  // Clearly visible horizontal-to-outward hydrostatic stress path pressing onto the strained rivet row
  cutaway.addConnectionEdge('hydro_load_center', [[0.56, 1.24, 0.12], [0.18, 1.24, 0.18], [-0.14, 1.24, 0.18]], 0.016, 0xfbbf24);
  cutaway.addFlowPulseOnEdge(0, 0xfde047, 0.030, 0.0);

  root.add(cutaway.root);
  const defectAnchor = new THREE.Object3D();
  defectAnchor.position.set(0, 1.24, 0.10);
  root.add(defectAnchor);

  return {
    root: shadow(root),
    cutaway,
    defectAnchor,
    update(lt, dur) {
      const u = clamp(lt / Math.max(0.2, dur), 0, 1);
      cutaway.setReveal(easeInOut(clamp(u * 1.45, 0, 1)), { slideOffset: [0.22, 0.0, 0.18] });
      cutaway.updateFlow(lt, 1.0);
      const pulse = 0.45 + 0.55 * Math.abs(Math.sin(lt * 4.2));
      rivetHeads.forEach((rh, idx) => {
        const sc = 1.0 + 0.14 * pulse * (idx % 2 === 0 ? 1 : 0.7);
        rh.scale.setScalar(sc);
      });
      return {
        cutaway_separation: Number(cutaway.getTelemetry().reveal_u.toFixed(3)),
        stress_pulse: Number(pulse.toFixed(3)),
      };
    },
    getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, { lap_joint_defect: defectAnchor }, []),
    getTelemetry: () => cutaway.getTelemetry(),
  };
}

/**
 * 9. Closing Contextual Harbor & North End Waterfront Overview
 */
export function makeBostonLocationOverview() {
  const root = new THREE.Group();
  tagSemantic(root, 'environment');
  const brickMat = new THREE.MeshStandardMaterial({ color: 0x763e30, roughness: 0.90 });
  const graniteMat = new THREE.MeshStandardMaterial({ color: 0x676b70, roughness: 0.88 });
  const harborMat = new THREE.MeshStandardMaterial({ color: 0x1c3a4f, roughness: 0.28, metalness: 0.15 });
  const wharfMat = new THREE.MeshStandardMaterial({ color: 0x5c4634, roughness: 0.88 });
  const railMat = new THREE.MeshStandardMaterial({ color: 0x262c33, roughness: 0.52, metalness: 0.74 });

  // Boston Harbor basin & North End masonry wharf
  const harbor = new THREE.Mesh(new THREE.BoxGeometry(16, 0.18, 8.5), harborMat);
  harbor.position.set(0, -0.10, -4.6);
  const land = new THREE.Mesh(new THREE.BoxGeometry(16, 0.24, 9.5), graniteMat);
  land.position.set(0, -0.02, 1.8);
  const pier = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.26, 2.8), wharfMat);
  pier.position.set(-2.2, 0.04, -2.5);
  root.add(harbor, land, pier);

  // Historic ruined tank plinth footprint pad near waterfront corner
  const memorialPad = new THREE.Mesh(
    new THREE.CylinderGeometry(1.18, 1.24, 0.14, 32),
    new THREE.MeshStandardMaterial({ color: 0x4b423b, roughness: 0.72, metalness: 0.35 })
  );
  memorialPad.position.set(0.0, 0.14, -0.45);
  tagSemantic(memorialPad, 'causal_feature');
  root.add(memorialPad);

  // North End multi-block tenement silhouette + inner harbor landmarks inside 9:16 portrait cone
  const blkGeo = new THREE.BoxGeometry(1.15, 1.35, 1.15);
  const blocks = new THREE.InstancedMesh(blkGeo, brickMat, 10);
  const dummy = new THREE.Object3D();
  const blockCoords = [
    [-2.1, 0.72, 1.2], [-1.35, 0.80, 1.85], [1.40, 0.78, 1.65], [2.25, 0.68, 1.05],
    [-1.85, 0.68, -0.55], [1.85, 0.84, -0.75], [-0.95, 0.62, 2.75], [1.05, 0.74, 2.65],
    [-3.1, 0.70, 0.45], [3.1, 0.72, 0.35],
  ];
  blockCoords.forEach(([x, y, z], idx) => {
    dummy.position.set(x, y, z);
    dummy.scale.set(1.0, 0.78 + (idx % 3) * 0.24, 1.0);
    dummy.updateMatrix();
    blocks.setMatrixAt(idx, dummy.matrix);
  });
  blocks.instanceMatrix.needsUpdate = true;
  tagSemantic(blocks, 'subject');
  root.add(blocks);

  // Harbor tugboat silhouette near pier for unmistakable coastal context
  const hull = new THREE.Mesh(new THREE.BoxGeometry(0.75, 0.24, 1.45), brickMat);
  hull.position.set(-0.65, 0.12, -2.55);
  const cabin = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.32, 0.56), wharfMat);
  cabin.position.set(-0.65, 0.38, -2.55);
  const funnel = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.09, 0.38, 10), railMat);
  funnel.position.set(-0.65, 0.64, -2.42);
  tagSemantic(hull, 'subject');
  tagSemantic(cabin, 'subject');
  tagSemantic(funnel, 'subject');
  root.add(hull, cabin, funnel);

  // Atlantic Ave Elevated Railway ribbon behind memorial plinth along waterfront edge
  const railSpan = new THREE.Mesh(new THREE.BoxGeometry(11.5, 0.18, 0.44), railMat);
  railSpan.position.set(0, 1.15, -1.65);
  tagSemantic(railSpan, 'subject');
  root.add(railSpan);

  const overviewAnchor = new THREE.Object3D();
  overviewAnchor.position.set(0, 1.05, -0.35);
  root.add(overviewAnchor);

  return {
    root: shadow(root),
    overviewAnchor,
    getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, { boston_overview_center: overviewAnchor }, []),
  };
}

export { computeAnchorsTelemetry };

export function getNarrativeActionTelemetry({
  locationId,
  physicalAction,
  actorCount = 0,
  fluidFrontPos = null,
  cutawayState = null,
  structuralState = null,
} = {}) {
  return {
    location_id: locationId || 'boston_north_end_1919',
    physical_action: physicalAction || 'scene_action',
    actor_count: Number(actorCount || 0),
    fluid_front_pos: fluidFrontPos,
    cutaway_state: cutawayState,
    structural_state: structuralState,
  };
}
"""
