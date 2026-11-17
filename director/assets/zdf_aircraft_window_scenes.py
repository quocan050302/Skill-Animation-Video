"""Procedural 3D Multi-Pane Aircraft Cabin Window & Bleed-Hole Assembly (ZDF Only).

Constructs a physically structured three-pane pressurized cabin window assembly:
1. Fuselage curved trim wall + ovalized rounded-rectangle bezel (`Layer 0`)
2. Outer structural pressure-bearing pane (`Layer 1`, carries primary delta-P load)
3. Middle structural fail-safe pane with a TRUE pierced circular bleed/breather hole
   near its lower centerline + schematic pressure equalization particle stream (`Layer 2`)
4. Inner cabin scratch cover pane (`Layer 3`)

All aerodynamic pressure arrows / moisture vent particles represent illustrative schematic flow.
"""

from __future__ import annotations


AIRCRAFT_WINDOW_SCENES_JS = r"""import * as THREE from 'three';
import { materials } from './materials.js';
import { LayeredCutaway } from './layered_cutaway.js';
import { clamp, easeInOut, lerp } from './anim.js';

function shadow(o) {
  o.traverse(c => { if (c.isMesh) { c.castShadow = true; c.receiveShadow = true; } });
  return o;
}

function makeRoundedRectShape(w, h, r) {
  const s = new THREE.Shape();
  const hw = w * 0.5, hh = h * 0.5;
  s.moveTo(-hw + r, -hh);
  s.lineTo(hw - r, -hh);
  s.quadraticCurveTo(hw, -hh, hw, -hh + r);
  s.lineTo(hw, hh - r);
  s.quadraticCurveTo(hw, hh, hw - r, hh);
  s.lineTo(-hw + r, hh);
  s.quadraticCurveTo(-hw, hh, -hw, hh - r);
  s.lineTo(-hw, -hh + r);
  s.quadraticCurveTo(-hw, -hh, -hw + r, -hh);
  return s;
}

/**
 * Project a 3D world anchor to screen UV [0..1] and test occlusion against solid structural colliders.
 */
export function computeAnchorsTelemetry(camera, anchorMap, occluders = []) {
  camera.updateMatrixWorld(true);
  const ray = new THREE.Raycaster();
  const camPos = new THREE.Vector3();
  camera.getWorldPosition(camPos);
  const out = {};

  for (const [aid, obj] of Object.entries(anchorMap || {})) {
    const wp = new THREE.Vector3();
    if (obj && typeof obj.getWorldPosition === 'function') {
      obj.getWorldPosition(wp);
    } else if (Array.isArray(obj)) {
      wp.set(obj[0], obj[1], obj[2]);
    } else {
      continue;
    }

    const dirToAnchor = wp.clone().sub(camPos);
    const dist = dirToAnchor.length();
    const camFwd = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
    const inFront = dirToAnchor.dot(camFwd) > 0.05;

    const ndc = wp.clone().project(camera);
    const u = (ndc.x + 1.0) * 0.5;
    const v = (1.0 - ndc.y) * 0.5;

    let occluded = false;
    if (inFront && occluders.length > 0 && dist > 0.05) {
      ray.set(camPos, dirToAnchor.clone().normalize());
      ray.far = Math.max(0.02, dist - 0.03);
      const hits = ray.intersectObjects(occluders, true);
      if (hits.length > 0 && hits[0].distance < dist - 0.035) {
        occluded = true;
      }
    }

    out[aid] = {
      u: Number(u.toFixed(4)),
      v: Number(v.toFixed(4)),
      in_front: inFront && ndc.z >= -1.0 && ndc.z <= 1.05,
      occluded,
      world_pos: [Number(wp.x.toFixed(4)), Number(wp.y.toFixed(4)), Number(wp.z.toFixed(4))],
    };
  }
  return out;
}

function makeWindowDeckPlaque(title, subtitle) {
  const c = document.createElement('canvas');
  c.width = 512; c.height = 128;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#0b1322';
  ctx.fillRect(0, 0, 512, 128);
  ctx.strokeStyle = '#38bdf8';
  ctx.lineWidth = 4;
  ctx.strokeRect(6, 6, 500, 116);
  ctx.textAlign = 'center';
  ctx.fillStyle = '#e2e8f0';
  ctx.font = '800 32px sans-serif';
  ctx.fillText(title, 256, 54);
  ctx.fillStyle = '#fbbf24';
  ctx.font = '600 22px sans-serif';
  ctx.fillText(subtitle, 256, 94);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/**
 * Construct full 3-pane pressurized cabin window assembly + LayeredCutaway controller + schematic airflow.
 */
export function makeAircraftWindowAssemblyRig({
  mode = 'macro_hole',
  outerDamaged = false,
  moistureDemo = false,
} = {}) {
  const M = materials();
  const root = new THREE.Group();
  root.position.set(0, 1.24, 0);

  // Exterior high-altitude deep sapphire sky & bright cloud horizon seen through crystal panes
  const skyCanv = document.createElement('canvas');
  skyCanv.width = 256; skyCanv.height = 512;
  const sctx = skyCanv.getContext('2d');
  const grad = sctx.createLinearGradient(0, 0, 0, 512);
  grad.addColorStop(0.0, '#07224d');
  grad.addColorStop(0.45, '#0369a1');
  grad.addColorStop(0.80, '#38bdf8');
  grad.addColorStop(1.0, '#e0f2fe');
  sctx.fillStyle = grad;
  sctx.fillRect(0, 0, 256, 512);
  const skyTex = new THREE.CanvasTexture(skyCanv);
  skyTex.colorSpace = THREE.SRGBColorSpace;
  const skyViewMat = new THREE.MeshBasicMaterial({ map: skyTex });
  const skyPanel = new THREE.Mesh(new THREE.PlaneGeometry(0.95, 1.25), skyViewMat);
  skyPanel.position.set(0, 0.04, -0.58);
  root.add(skyPanel);

  // Crisp backlit high-altitude cloud bank far behind outer fuselage
  const cloudMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.85, emissive: 0xbae6fd, emissiveIntensity: 0.12 });
  const cloudGroup = new THREE.Group();
  for (let i = 0; i < 4; i++) {
    const puff = new THREE.Mesh(new THREE.SphereGeometry(0.11 + (i % 2) * 0.03, 18, 12), cloudMat);
    puff.scale.set(1.6, 0.50, 0.45);
    puff.position.set(-0.14 + i * 0.09, -0.18 + (i % 2) * 0.03, -0.50);
    cloudGroup.add(puff);
  }
  root.add(cloudGroup);

  // Aerospace slate-metallic fuselage bulkhead wall + crisp light-titanium trim surround collar
  const wallOuterShape = makeRoundedRectShape(1.56, 1.96, 0.14);
  const apertureHole = makeRoundedRectShape(0.40, 0.58, 0.16);
  wallOuterShape.holes.push(apertureHole);

  const bulkheadMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.58, metalness: 0.25 });
  const wallGeo = new THREE.ExtrudeGeometry(wallOuterShape, { depth: 0.12, bevelEnabled: true, bevelThickness: 0.015, bevelSize: 0.012, bevelSegments: 4 });
  wallGeo.center();
  const wallMesh = new THREE.Mesh(wallGeo, bulkheadMat);
  wallMesh.position.set(0, 0, -0.04);

  // Crisp satin aluminum bezel reveal collar contrasting sharply against dark fuselage wall
  const bezelOuter = makeRoundedRectShape(0.50, 0.68, 0.19);
  const bezelInner = makeRoundedRectShape(0.39, 0.57, 0.155);
  bezelOuter.holes.push(bezelInner);
  const bezelGeo = new THREE.ExtrudeGeometry(bezelOuter, { depth: 0.09, bevelEnabled: true, bevelThickness: 0.012, bevelSize: 0.01, bevelSegments: 4 });
  bezelGeo.center();
  const bezelMat = new THREE.MeshPhysicalMaterial({ color: 0xe2e8f0, roughness: 0.34, metalness: 0.22, clearcoat: 0.4 });
  const bezelMesh = new THREE.Mesh(bezelGeo, bezelMat);
  bezelMesh.position.set(0, 0, 0.04);

  // Anodized dark structural seal ring inside housing
  const sealOuter = makeRoundedRectShape(0.43, 0.61, 0.17);
  const sealInner = makeRoundedRectShape(0.38, 0.56, 0.15);
  sealOuter.holes.push(sealInner);
  const sealGeo = new THREE.ExtrudeGeometry(sealOuter, { depth: 0.06, bevelEnabled: false });
  sealGeo.center();
  const sealMesh = new THREE.Mesh(sealGeo, M.steelDark);
  sealMesh.position.set(0, 0, 0.0);

  // LayeredCutaway wraps fuselage shell (clipped during cutaway reveals) + 3 distinct structural panes
  const cutaway = new LayeredCutaway({
    id: 'airplane_window_cutaway',
    worldAnchor: [0, 1.24, 0.02],
    clipNormal: [-1, 0, 0],
    clipConstantStart: 1.5,
    clipConstantOpen: 0.02,
  });
  root.add(cutaway.root);

  const shellGroup = new THREE.Group();
  shellGroup.add(wallMesh, bezelMesh);
  cutaway.addOuterShell(shellGroup, { applyClip: true });
  root.add(sealMesh);

  // --- LAYER 1: OUTER STRUCTURAL PANE (primary cabin pressure barrier, -z, crystal-clear blue edge) ---
  const paneShape = makeRoundedRectShape(0.38, 0.56, 0.145);
  const outerGeo = new THREE.ExtrudeGeometry(paneShape, { depth: 0.020, bevelEnabled: true, bevelThickness: 0.004, bevelSize: 0.004, bevelSegments: 2 });
  outerGeo.center();
  const outerMat = new THREE.MeshPhysicalMaterial({
    color: outerDamaged ? 0xfca5a5 : 0x38bdf8,
    transparent: true,
    opacity: outerDamaged ? 0.34 : 0.18,
    roughness: 0.05,
    metalness: 0.05,
    clearcoat: 1.0,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  const outerPane = new THREE.Mesh(outerGeo, outerMat);
  outerPane.position.set(0, 0, -0.055);
  const outerRim = new THREE.Mesh(sealGeo, new THREE.MeshStandardMaterial({ color: 0x0284c7, emissive: 0x0284c7, emissiveIntensity: 0.25, metalness: 0.85, roughness: 0.22 }));
  outerRim.scale.set(0.99, 0.99, 0.34);
  outerPane.add(outerRim);
  cutaway.addInternalComponent('outer_pressure_pane', outerPane, { layerIndex: 1, materialId: 'mat_acrylic_outer' });

  // Fracture hairline visual on outer pane during fail-safe shot
  const crackGroup = new THREE.Group();
  if (outerDamaged) {
    const crackMat = new THREE.MeshStandardMaterial({ color: 0xef4444, emissive: 0xef4444, emissiveIntensity: 1.5 });
    for (let k = 0; k < 6; k++) {
      const seg = new THREE.Mesh(new THREE.BoxGeometry(0.13, 0.008, 0.028), crackMat);
      seg.position.set(-0.05 + (k % 2) * 0.08, 0.08 - k * 0.035, 0);
      seg.rotation.z = (k % 2 ? 0.52 : -0.45);
      crackGroup.add(seg);
    }
    outerPane.add(crackGroup);
  }

  // --- LAYER 2: MIDDLE FAIL-SAFE PANE WITH TRUE PIERCED BLEED HOLE NEAR BOTTOM ---
  const holeY = -0.175;
  const middleShape = makeRoundedRectShape(0.38, 0.56, 0.145);
  const bleedHolePath = new THREE.Path();
  bleedHolePath.absarc(0, holeY, 0.025, 0, Math.PI * 2, true);
  middleShape.holes.push(bleedHolePath);

  const midGeo = new THREE.ExtrudeGeometry(middleShape, {
    depth: 0.016, bevelEnabled: true, bevelThickness: 0.003, bevelSize: 0.003, bevelSegments: 2, curveSegments: 32,
  });
  midGeo.center();
  const midMat = new THREE.MeshPhysicalMaterial({
    color: 0xfef3c7,
    transparent: true,
    opacity: 0.19,
    roughness: 0.06,
    metalness: 0.06,
    clearcoat: 0.95,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  const middlePane = new THREE.Mesh(midGeo, midMat);
  middlePane.position.set(0, 0, 0.0);

  // High-contrast precision brass/amber chamfer collar circling the real drilled bleed hole
  const collarRing = new THREE.Mesh(
    new THREE.TorusGeometry(0.0265, 0.0052, 16, 40),
    new THREE.MeshStandardMaterial({ color: 0xf59e0b, emissive: 0xf59e0b, emissiveIntensity: 0.72, metalness: 0.80, roughness: 0.18 })
  );
  collarRing.position.set(0, holeY, 0.0);
  middlePane.add(collarRing);

  const holeAnchor = new THREE.Object3D();
  holeAnchor.position.set(0, holeY, 0.0);
  middlePane.add(holeAnchor);

  const midRim = new THREE.Mesh(sealGeo, new THREE.MeshStandardMaterial({ color: 0xf59e0b, emissive: 0xb45309, emissiveIntensity: 0.25, metalness: 0.76, roughness: 0.24 }));
  midRim.scale.set(0.985, 0.985, 0.30);
  middlePane.add(midRim);
  cutaway.addInternalComponent('middle_failsafe_pane', middlePane, { layerIndex: 2, materialId: 'mat_acrylic_middle' });

  // --- LAYER 3: INNER CABIN SCRATCH COVER PANE (+z interior side, crystal-clear emerald edge) ---
  const innerGeo = new THREE.ExtrudeGeometry(paneShape, { depth: 0.010, bevelEnabled: true, bevelThickness: 0.002, bevelSize: 0.002, bevelSegments: 2 });
  innerGeo.center();
  const innerMat = new THREE.MeshPhysicalMaterial({
    color: 0xd1fae5,
    transparent: true,
    opacity: 0.14,
    roughness: 0.08,
    clearcoat: 0.85,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  const innerPane = new THREE.Mesh(innerGeo, innerMat);
  innerPane.position.set(0, 0, 0.055);
  const innerRim = new THREE.Mesh(sealGeo, new THREE.MeshStandardMaterial({ color: 0x10b981, emissive: 0x059669, emissiveIntensity: 0.25, metalness: 0.60, roughness: 0.28 }));
  innerRim.scale.set(0.98, 0.98, 0.22);
  innerPane.add(innerRim);
  cutaway.addInternalComponent('inner_scratch_pane', innerPane, { layerIndex: 3, materialId: 'mat_acrylic_inner' });

  // Schematic cabin airflow path threading THROUGH the bleed hole between inner, middle & outer gap
  cutaway.addConnectionEdge('bleed_equalization_stream', [
    [0.08, -0.06, 0.085],
    [0.025, holeY + 0.03, 0.042],
    [0.0, holeY, 0.0],
    [0.0, holeY + 0.04, -0.032],
    [0.0, 0.08, -0.034],
  ], 0.0045, 0x38bdf8);
  cutaway.addConnectionEdge('moisture_vent_loop', [
    [-0.06, -0.08, -0.030],
    [-0.02, holeY - 0.01, -0.018],
    [0.0, holeY, 0.0],
    [0.03, holeY + 0.02, 0.035],
    [0.06, 0.02, 0.070],
  ], 0.0038, 0x34d399);

  for (let i = 0; i < 6; i++) {
    cutaway.addFlowPulseOnEdge(0, 0x38bdf8, 0.009, i / 6);
  }
  for (let i = 0; i < 4; i++) {
    cutaway.addFlowPulseOnEdge(1, 0x34d399, 0.0085, i / 4);
  }

  // Stylized pressure vectors pressing from cabin interior (+z -> -z)
  const pressureArrows = new THREE.Group();
  const arrowMat = new THREE.MeshStandardMaterial({ color: 0xef4444, emissive: 0xef4444, emissiveIntensity: 0.75, roughness: 0.35 });
  const arrowOffsets = [[-0.09, 0.11], [0.09, 0.11], [-0.09, -0.02], [0.09, -0.02]];
  arrowOffsets.forEach(([ax, ay]) => {
    const arr = new THREE.Group();
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.007, 0.007, 0.09, 10), arrowMat);
    shaft.rotation.x = Math.PI / 2;
    const tip = new THREE.Mesh(new THREE.ConeGeometry(0.018, 0.034, 12), arrowMat);
    tip.rotation.x = -Math.PI / 2;
    tip.position.z = -0.055;
    arr.add(shaft, tip);
    arr.position.set(ax, ay, 0.12);
    pressureArrows.add(arr);
  });
  pressureArrows.visible = false;
  root.add(pressureArrows);

  // Subtle condensation frost mist patches on outer-mid chamber when moistureDemo active
  const frostGroup = new THREE.Group();
  const frostDots = [];
  if (moistureDemo) {
    const frostMat = new THREE.MeshStandardMaterial({ color: 0xe0f2fe, transparent: true, opacity: 0.62, roughness: 0.85 });
    for (let i = 0; i < 14; i++) {
      const ang = (i / 14) * Math.PI * 2;
      const rad = 0.06 + (i % 3) * 0.035;
      const d = new THREE.Mesh(new THREE.SphereGeometry(0.015, 10, 8), frostMat);
      d.scale.set(1.2, 0.9, 0.25);
      d.position.set(Math.cos(ang) * rad, Math.sin(ang) * rad * 1.2 + 0.02, -0.028);
      frostGroup.add(d);
      frostDots.push(d);
    }
    root.add(frostGroup);
  }

  // Informational deck plinth below window assembly (transparently labeled schematic aircraft bay)
  const deck = new THREE.Mesh(new THREE.BoxGeometry(1.15, 0.14, 0.56), M.steelDark);
  deck.position.set(0, -1.02, 0.06);
  const plaque = new THREE.Mesh(
    new THREE.PlaneGeometry(0.62, 0.155),
    new THREE.MeshBasicMaterial({ map: makeWindowDeckPlaque('3-PANE CABIN WINDOW', '14 CFR § 25.775 • SCHEMATIC FLOW') })
  );
  plaque.position.set(0, -1.01, 0.345);
  root.add(deck, plaque);

  const stackAnchor = new THREE.Object3D();
  stackAnchor.position.set(0, 0.02, 0.0);
  root.add(stackAnchor);

  const outerAnchor = new THREE.Object3D();
  outerAnchor.position.set(0, 0.06, 0);
  outerPane.add(outerAnchor);

  const solidOccluders = [wallMesh, bezelMesh, deck];
  const anchorMap = {
    middle_bleed_hole: holeAnchor,
    bleed_vent_port: holeAnchor,
    window_pane_stack: stackAnchor,
    outer_pressure_pane: outerAnchor,
    middle_pane_core: middlePane,
    stage_center: stackAnchor,
  };

  shadow(root);

  return {
    root,
    cutaway,
    outerPane,
    middlePane,
    innerPane,
    collarRing,
    pressureArrows,
    updateAssembly(lt, dur, opts = {}) {
      const u = clamp(lt / Math.max(0.25, dur), 0, 1);
      const explodeAmt = Number(opts.explodeAmount ?? 0.0);
      const peelAmt = Number(opts.cutawayAmount ?? 0.0);
      const showPressure = Boolean(opts.showPressure ?? false);

      // Explode layers cleanly in staggered oblique staircase along X and Z for unmistakable 3-pane separation
      outerPane.position.set(-0.18 * explodeAmt, 0.04 * explodeAmt, -0.055 - 0.20 * explodeAmt);
      middlePane.position.set(0.0, 0.0, 0.0 + 0.02 * explodeAmt);
      innerPane.position.set(0.18 * explodeAmt, -0.04 * explodeAmt, 0.055 + 0.22 * explodeAmt);

      cutaway.setReveal(peelAmt, { slideOffset: [-0.26, 0.0, 0.04], hingeRotY: -0.18 });
      cutaway.updateFlow(lt, moistureDemo ? 0.95 : 1.25);

      collarRing.material.emissiveIntensity = 0.55 + 0.75 * (0.5 + 0.5 * Math.sin(lt * 5.2));
      pressureArrows.visible = showPressure;
      if (showPressure) {
        const pulse = (lt * 1.4) % 1.0;
        pressureArrows.position.z = 0.04 * (1.0 - pulse);
      }

      if (moistureDemo && frostDots.length > 0) {
        const clearU = easeInOut(u);
        frostDots.forEach((d, k) => {
          const s = Math.max(0.08, 1.0 - clearU * 0.85 + 0.1 * Math.sin(lt * 3.0 + k));
          d.scale.set(1.2 * s, 0.9 * s, 0.25);
        });
      }
    },
    getAnchorsTelemetry(camera) {
      return computeAnchorsTelemetry(camera, anchorMap, solidOccluders);
    },
    getTelemetry() {
      return cutaway.getTelemetry();
    },
  };
}
"""
