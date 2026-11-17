"""Modular 3D Character Identity Rig, Two-Bone Reach/Contact IK, and Layered Cutaway Runtime (ZDF Only)."""

from __future__ import annotations


CHARACTER_ACTION_RIG_JS = r"""import * as THREE from 'three';
import { torsoShell } from './human.js';
import { materials } from './materials.js';
import { aimNegY, clamp, easeInOut, easeOut, lerp, smooth, range } from './anim.js';

function shadow(o) {
  o.traverse(c => { if (c.isMesh) { c.castShadow = true; c.receiveShadow = true; } });
  return o;
}

/**
 * Build a modern human character with immutable `character_registry` appearance,
 * matching jacket sleeves, dark trousers, clean shoes, and articulated pointing index finger.
 */
export function buildRegisteredCharacter(makeHumanFn, charSpec = {}) {
  const M = materials();
  const h = makeHumanFn('plain');
  const shirtHex = Number(charSpec.shirt_hex ?? 0x2563eb);
  const pantsHex = Number(charSpec.pants_hex ?? 0x1e293b);
  const collarHex = Number(charSpec.collar_hex ?? 0xe2e8f0);
  const shoeHex = Number(charSpec.shoe_hex ?? 0x0f172a);

  const shirtMat = new THREE.MeshStandardMaterial({ color: shirtHex, roughness: 0.72, metalness: 0.05 });
  const pantsMat = new THREE.MeshStandardMaterial({ color: pantsHex, roughness: 0.85, metalness: 0.04 });
  const collarMat = new THREE.MeshStandardMaterial({ color: collarHex, roughness: 0.55 });
  const shoeMat = new THREE.MeshStandardMaterial({ color: shoeHex, roughness: 0.60, metalness: 0.10 });

  // Torso jacket shell (offset >= 0.016 prevents z-fighting with base torsoShell)
  const chestG = torsoShell(0.18, 0.54, 0.018);
  chestG.translate(0, -0.2, 0);
  const chestShirt = new THREE.Mesh(chestG, shirtMat);
  h.j.chest.add(chestShirt);

  const spineShirt = new THREE.Mesh(torsoShell(-0.14, 0.20, 0.016), shirtMat);
  h.j.spine.add(spineShirt);

  const collar = new THREE.Mesh(new THREE.TorusGeometry(0.105, 0.018, 8, 24), collarMat);
  collar.rotation.x = Math.PI / 2;
  collar.position.set(0, 0.34, 0.01);
  h.j.chest.add(collar);

  // Matching jacket sleeves + shoulder/elbow caps (no exposed black joint hinges or wrist gaps)
  for (const side of ['l', 'r']) {
    const shCap = new THREE.Mesh(new THREE.SphereGeometry(0.062, 18, 14), shirtMat);
    h.j[side + 'Sh'].add(shCap);

    const shSleeve = new THREE.Mesh(new THREE.CylinderGeometry(0.058, 0.054, 0.27, 20), shirtMat);
    shSleeve.position.y = -0.14;
    h.j[side + 'Sh'].add(shSleeve);

    const elCap = new THREE.Mesh(new THREE.SphereGeometry(0.052, 18, 14), shirtMat);
    h.j[side + 'El'].add(elCap);

    const elSleeve = new THREE.Mesh(new THREE.CylinderGeometry(0.051, 0.043, 0.262, 20), shirtMat);
    elSleeve.position.y = -0.132;
    h.j[side + 'El'].add(elSleeve);

    const thigh = new THREE.Mesh(new THREE.CylinderGeometry(0.084, 0.070, 0.36, 20), pantsMat);
    thigh.position.y = -0.19;
    h.j[side + 'Hip'].add(thigh);

    const shin = new THREE.Mesh(new THREE.CylinderGeometry(0.062, 0.052, 0.38, 20), pantsMat);
    shin.position.y = -0.19;
    h.j[side + 'Kn'].add(shin);

    const shoe = new THREE.Mesh(new THREE.BoxGeometry(0.10, 0.075, 0.24), shoeMat);
    shoe.position.set(0, -0.036, 0.068);
    h.j[side + 'An'].add(shoe);
  }

  // Extended index finger protruding cleanly past fist knuckles + fingertip marker
  const fingerGroup = new THREE.Group();
  const idxFinger = new THREE.Mesh(new THREE.CapsuleGeometry(0.011, 0.058, 6, 12), M.skin);
  idxFinger.position.set(0.0, -0.118, 0.0);
  fingerGroup.add(idxFinger);

  const fingerTip = new THREE.Object3D();
  fingerTip.position.set(0.0, -0.156, 0.0);
  fingerGroup.add(fingerTip);
  h.j.rWr.add(fingerGroup);

  h.characterId = charSpec.character_id || 'char_protagonist_01';
  h.shirtMaterialId = charSpec.shirt_material_id || ('mat_shirt_' + shirtHex.toString(16).padStart(6, '0'));
  h.fingerGroup = fingerGroup;
  h.fingerTip = fingerTip;
  shadow(h.root);
  return h;
}

const _pq = new THREE.Quaternion();
const _vA = new THREE.Vector3();
const _vB = new THREE.Vector3();

/**
 * Solve true two-bone arm IK (`a=0.30, b=0.27`) with fingertip offset compensation so
 * `human.fingerTip` reaches exact world `targetTipWorld` along `approachDir`.
 */
export function solveFingerContactIK(human, side, targetTipWorld, poleWorld, approachDirWorld) {
  const sh = human.j[side + 'Sh'];
  const el = human.j[side + 'El'];
  const wr = human.j[side + 'Wr'];
  const a = 0.30;
  const b = 0.27;
  const tipLocalOffset = 0.156;

  human.root.updateMatrixWorld(true);
  const S = sh.getWorldPosition(new THREE.Vector3());
  const approachDir = approachDirWorld.clone().normalize();
  // Wrist target sits back from fingertip target by finger length along approachDir
  const wristTarget = targetTipWorld.clone().addScaledVector(approachDir, -tipLocalOffset);

  const D = wristTarget.clone().sub(S);
  const maxReach = a + b - 0.004;
  const d = Math.max(0.12, Math.min(D.length(), maxReach));
  const dir = D.normalize();
  const cosA = clamp((a * a + d * d - b * b) / (2 * a * d), -1, 1);
  const sinA = Math.sqrt(Math.max(0, 1 - cosA * cosA));
  const p = poleWorld.clone().sub(S);
  p.addScaledVector(dir, -p.dot(dir));
  if (p.lengthSq() < 1e-6) p.set(0, -1, 0.3);
  p.normalize();

  const E = S.clone().addScaledVector(dir, a * cosA).addScaledVector(p, a * sinA);
  const hint = new THREE.Vector3(0, 0, 1);
  aimNegY(sh, E.clone().sub(S), hint);
  const T = S.clone().addScaledVector(dir, d);
  aimNegY(el, T.clone().sub(E), hint);

  // Align wrist so local -Y points directly into button surface normal
  aimNegY(wr, approachDir, new THREE.Vector3(0, 1, 0));
  human.root.updateMatrixWorld(true);

  const realizedTip = human.fingerTip ? human.fingerTip.getWorldPosition(_vA) : wr.getWorldPosition(_vA);
  return {
    realized_tip: [realizedTip.x, realizedTip.y, realizedTip.z],
    target_tip: [targetTipWorld.x, targetTipWorld.y, targetTipWorld.z],
    error_m: realizedTip.distanceTo(targetTipWorld),
  };
}

/**
 * Execute 4-phase natural contact animation (anticipation -> physical touch/depress -> hold -> release).
 */
export function updateButtonPressAction(human, contactSpec, lt, standPose) {
  const hitT = Number(contactSpec?.hit_time_rel_sec ?? 0.9);
  const holdDur = Number(contactSpec?.hold_duration_sec ?? 0.16);
  const appStart = Math.max(0.0, hitT - 0.48);
  const relEnd = hitT + holdDur + 0.42;

  const tVec = new THREE.Vector3(...(contactSpec?.target_world || [0.24, 1.16, 0.24]));
  const nVec = new THREE.Vector3(...(contactSpec?.target_normal || [-1, 0, 0])).normalize();
  const pressDepth = Number(contactSpec?.button_depress_m ?? 0.008);
  const targetRadius = Number(contactSpec?.target_radius_m ?? 0.028);

  let reachWeight = 0.0;
  let depress = 0.0;
  let phase = 'idle_ready';

  if (lt < appStart) {
    phase = 'anticipation_ready';
    reachWeight = 0.25 * smooth(range(lt, 0, Math.max(0.05, appStart)));
  } else if (lt < hitT) {
    phase = 'approach';
    const u = smooth(range(lt, appStart, hitT));
    reachWeight = lerp(0.25, 1.0, u);
  } else if (lt <= hitT + holdDur) {
    phase = 'contact_press';
    reachWeight = 1.0;
    const pressU = Math.sin(clamp((lt - hitT) / Math.max(0.05, holdDur), 0, 1) * Math.PI);
    depress = pressDepth * Math.max(0.65, pressU);
  } else if (lt < relEnd) {
    phase = 'release';
    const u = smooth(range(lt, hitT + holdDur, relEnd));
    reachWeight = lerp(1.0, 0.18, u);
    depress = pressDepth * (1.0 - u) * 0.4;
  } else {
    phase = 'follow_through';
    reachWeight = 0.18;
  }

  // Anticipatory torso lean + head gaze toward button
  const breath = Math.sin(lt * 2.2) * 0.015;
  human.setPose({
    ...standPose,
    drop: -0.02 * reachWeight + breath * 0.2,
    spine: [0.05 * reachWeight, 0.16 * reachWeight, 0],
    chest: [0.04 * reachWeight, 0.18 * reachWeight, 0],
    neck: [0.04, 0.18 * reachWeight, 0],
    head: [0.06 * reachWeight, 0.22 * reachWeight, 0],
    lSh: [0.08, 0, 0.18],
    lEl: [-0.32, 0, 0],
  });

  // Compute fingertip target along normal: hover 14cm away at weight=0, depressed surface at contact
  const hoverDist = lerp(0.16, -depress, reachWeight);
  const desiredTipWorld = tVec.clone().addScaledVector(nVec, hoverDist);
  const approachDir = nVec.clone().negate();
  human.root.updateMatrixWorld(true);
  const poleWorld = human.root.localToWorld(new THREE.Vector3(-0.36, 1.12, -0.18));

  const ikRes = solveFingerContactIK(human, 'r', desiredTipWorld, poleWorld, approachDir);
  const activeButtonSurface = tVec.clone().addScaledVector(nVec, -depress);
  const surfaceErr = _vB.set(...ikRes.realized_tip).distanceTo(activeButtonSurface);

  return {
    performer_id: human.characterId,
    target_id: contactSpec?.target_id || 'call_button_01',
    phase,
    reach_weight: Number(reachWeight.toFixed(4)),
    button_depress_m: Number(depress.toFixed(5)),
    button_lit: lt >= hitT,
    fingertip_world: ikRes.realized_tip.map(v => Number(v.toFixed(5))),
    target_surface_world: [
      Number(activeButtonSurface.x.toFixed(5)),
      Number(activeButtonSurface.y.toFixed(5)),
      Number(activeButtonSurface.z.toFixed(5)),
    ],
    world_error_m: Number(surfaceErr.toFixed(5)),
    target_radius_m: targetRadius,
  };
}
"""

LAYERED_CUTAWAY_JS = r"""import * as THREE from 'three';

/**
 * Reusable LayeredCutaway component with real Three.js Plane clipping,
 * physical outer shell reveal, typed internal components, and edge-bound signal flow.
 */
export class LayeredCutaway {
  constructor({
    id,
    worldAnchor = [0, 1.2, 0],
    clipNormal = [0, 0, -1],
    clipConstantStart = 0.26,
    clipConstantOpen = -0.02,
  } = {}) {
    this.id = id || 'cutaway_01';
    this.root = new THREE.Group();
    this.outerShell = new THREE.Group();
    this.internalGroup = new THREE.Group();
    this.connectionsGroup = new THREE.Group();
    this.flowGroup = new THREE.Group();
    this.root.add(this.outerShell, this.internalGroup, this.connectionsGroup, this.flowGroup);

    this.worldAnchor = [...worldAnchor];
    this.clipNormal = new THREE.Vector3(...clipNormal).normalize();
    this.clipPlane = new THREE.Plane(this.clipNormal.clone(), clipConstantStart);
    this.clipConstantStart = clipConstantStart;
    this.clipConstantOpen = clipConstantOpen;
    this.internalComponents = [];
    this.connectionEdges = [];
    this.flowParticles = [];
    this.revealU = 0.0;
  }

  addOuterShell(meshOrGroup, { applyClip = true } = {}) {
    if (applyClip) {
      meshOrGroup.traverse(c => {
        if (c.isMesh && c.material) {
          c.material = c.material.clone();
          c.material.clippingPlanes = [this.clipPlane];
          c.material.clipShadows = true;
          c.material.side = THREE.DoubleSide;
        }
      });
    }
    this.outerShell.add(meshOrGroup);
    return meshOrGroup;
  }

  addInternalComponent(name, meshOrGroup, { layerIndex = 1, materialId = 'mat_internal' } = {}) {
    this.internalGroup.add(meshOrGroup);
    this.internalComponents.push({ name, mesh: meshOrGroup, layer_index: layerIndex, material_id: materialId });
    return meshOrGroup;
  }

  addConnectionEdge(name, points, radius = 0.008, colorHex = 0xd97706) {
    const vecs = points.map(p => new THREE.Vector3(...p));
    const curve = new THREE.CatmullRomCurve3(vecs);
    const geo = new THREE.TubeGeometry(curve, 24, radius, 8, false);
    const mat = new THREE.MeshStandardMaterial({ color: colorHex, metalness: 0.75, roughness: 0.30 });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.castShadow = true;
    this.connectionsGroup.add(mesh);
    const edge = { name, curve, mesh };
    this.connectionEdges.push(edge);
    return edge;
  }

  addFlowPulseOnEdge(edgeIndex, colorHex = 0x38bdf8, radius = 0.015, phaseOffset = 0) {
    const mat = new THREE.MeshStandardMaterial({
      color: colorHex,
      emissive: colorHex,
      emissiveIntensity: 1.6,
      roughness: 0.2,
    });
    const bead = new THREE.Mesh(new THREE.SphereGeometry(radius, 14, 10), mat);
    this.flowGroup.add(bead);
    this.flowParticles.push({ bead, edgeIndex, phaseOffset });
    return bead;
  }

  setReveal(u, { slideOffset = [0, 0, 0], hingeRotY = 0 } = {}) {
    const c = Math.max(0, Math.min(1, u));
    this.revealU = c;
    this.clipPlane.constant = this.clipConstantStart + (this.clipConstantOpen - this.clipConstantStart) * c;
    this.outerShell.position.set(slideOffset[0] * c, slideOffset[1] * c, slideOffset[2] * c);
    this.outerShell.rotation.y = hingeRotY * c;
  }

  updateFlow(lt, speed = 1.1) {
    for (const item of this.flowParticles) {
      const edge = this.connectionEdges[item.edgeIndex];
      if (!edge) continue;
      const t = (lt * speed + item.phaseOffset) % 1.0;
      const pt = edge.curve.getPointAt(t);
      item.bead.position.copy(pt);
    }
  }

  getTelemetry() {
    const distinctInternalLayers = new Set(this.internalComponents.map(c => Number(c.layer_index ?? 1))).size;
    const layers =
      (this.outerShell.children.length > 0 ? 1 : 0) +
      distinctInternalLayers +
      (this.connectionEdges.length > 0 ? 1 : 0) +
      (this.flowParticles.length > 0 ? 1 : 0);
    return {
      cutaway_id: this.id,
      world_anchor: this.worldAnchor,
      has_clip_plane: true,
      reveal_u: Number(this.revealU.toFixed(4)),
      layers_count: layers,
      components_count: this.internalComponents.length,
      internal_component_count: this.internalComponents.length,
      internal_component_names: this.internalComponents.map(c => c.name),
      connection_edge_count: this.connectionEdges.length,
      flow_particle_count: this.flowParticles.length,
    };
  }
}
"""
