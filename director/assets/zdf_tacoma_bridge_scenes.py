"""Procedural 1940 Tacoma Narrows Bridge ("Galloping Gertie") 3D Scene Library (`SD-RETENTION-03` Workstream 3+4+5).

Strict Engineering & Historical Integrity Guarantees:
- Illustrative 3D reconstruction calibrated visually (non-CFD, explicitly labeled `stylized_illustrative`).
- Pure deterministic `update(lt, dur)` curves built on `physical_motion_primitives.js` and `character_performance.js`.
- Continuous segmented roadway deck with 8-ft solid plate stiffening girders, catenary main cables,
  and suspender cables coupled directly every frame to exact deformed deck-edge world coordinates
  (`cables_attached: true`, zero dangling detached struts before collapse onset).
- Authentic 1940 period coupe/sedan vehicles and 1940 fedora/wool-coat shore onlooker (zero modern items).
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

function addFedora1940(human, hex = 0x3f3730) {
  const mat = new THREE.MeshStandardMaterial({ color: hex, roughness: 0.86, metalness: 0.04 });
  const bandMat = new THREE.MeshStandardMaterial({ color: 0x1b1918, roughness: 0.65 });
  const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.185, 0.19, 0.014, 24), mat);
  brim.position.set(0, 0.115, 0.01);
  const crown = new THREE.Mesh(new THREE.CylinderGeometry(0.095, 0.115, 0.095, 22), mat);
  crown.position.set(0, 0.165, 0.0);
  const ribbon = new THREE.Mesh(new THREE.CylinderGeometry(0.117, 0.117, 0.022, 22), bandMat);
  ribbon.position.set(0, 0.129, 0.0);
  human.j.head.add(brim, crown, ribbon);
}

/**
 * Period 1939/1940 Streamlined Coupe / Sedan (rounded fenders, chrome radiator grille, rubber spoked tires).
 */
export function makePeriodCar1940(bodyHex = 0x263544) {
  const g = new THREE.Group();
  const paint = new THREE.MeshStandardMaterial({ color: bodyHex, roughness: 0.34, metalness: 0.35 });
  const chrome = new THREE.MeshStandardMaterial({ color: 0xd8dee6, roughness: 0.22, metalness: 0.88 });
  const glass = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.18, metalness: 0.25 });
  const rubber = new THREE.MeshStandardMaterial({ color: 0x17191c, roughness: 0.88 });

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
 * Animated Puget Sound Narrows Environment (choppy strait water, 1940 rocky cliffs, timber pilings, far shore).
 */
export function makePugetSoundEnvironment({ includeShore = true } = {}) {
  const root = new THREE.Group();
  const waterGeom = new THREE.PlaneGeometry(36, 36, 44, 44);
  waterGeom.rotateX(-Math.PI / 2);
  const wPos = waterGeom.attributes.position;
  const wBaseY = new Float32Array(wPos.count);
  for (let i = 0; i < wPos.count; i++) wBaseY[i] = wPos.getY(i);

  const waterMat = new THREE.MeshStandardMaterial({
    color: 0x16384a, emissive: 0x091a26, emissiveIntensity: 0.32,
    roughness: 0.24, metalness: 0.22, side: THREE.DoubleSide,
  });
  const waterMesh = new THREE.Mesh(waterGeom, waterMat);
  waterMesh.position.y = 0.0;
  waterMesh.receiveShadow = true;
  root.add(waterMesh);

  if (includeShore) {
    const rockMat = new THREE.MeshStandardMaterial({ color: 0x4b5349, roughness: 0.92, metalness: 0.02 });
    const pineMat = new THREE.MeshStandardMaterial({ color: 0x263f2c, roughness: 0.88 });
    const cliffL = new THREE.Mesh(new THREE.BoxGeometry(8.5, 3.2, 22), rockMat);
    cliffL.position.set(-12.2, 1.35, 0);
    const cliffR = new THREE.Mesh(new THREE.BoxGeometry(8.5, 3.2, 22), rockMat);
    cliffR.position.set(12.2, 1.35, 0);
    root.add(cliffL, cliffR);

    for (const [tx, tz, sc] of [[-9.6, -2.5, 1.1], [-10.4, 2.2, 0.9], [9.8, -1.8, 1.0], [10.6, 3.1, 1.2], [-9.2, 5.4, 0.95]]) {
      const cone = new THREE.Mesh(new THREE.ConeGeometry(0.55 * sc, 1.85 * sc, 8), pineMat);
      cone.position.set(tx, 3.35, tz);
      root.add(cone);
    }
  }

  // Water splash rings anchored under midspan (x=0, z=0) when collapse impacts water
  const splashMat = new THREE.MeshBasicMaterial({
    color: 0xdbeafe, transparent: true, opacity: 0.0, side: THREE.DoubleSide,
  });
  const splashRing = new THREE.Mesh(new THREE.RingGeometry(0.45, 0.95, 36), splashMat);
  splashRing.rotation.x = -Math.PI / 2;
  splashRing.position.set(0, 0.06, 0);
  root.add(splashRing);

  function updateEnv(t, splashProg = 0.0) {
    const arr = wPos.array;
    for (let i = 0; i < wPos.count; i++) {
      const x = arr[i * 3];
      const z = arr[i * 3 + 2];
      arr[i * 3 + 1] = wBaseY[i] + Math.sin(x * 0.65 + t * 1.9) * 0.055 + Math.cos(z * 0.82 - t * 1.6) * 0.045;
    }
    wPos.needsUpdate = true;
    waterGeom.computeVertexNormals();
    if (splashProg > 0.01) {
      splashMat.opacity = (1.0 - splashProg) * 0.72;
      const sc = 1.0 + splashProg * 4.5;
      splashRing.scale.set(sc, sc, sc);
    } else {
      splashMat.opacity = 0.0;
    }
  }

  return { root, waterMesh, update: updateEnv };
}

/**
 * Full 1940 Tacoma Narrows Suspension Bridge Multi-Segment Physical Rig.
 * Supports: vertical wave, asymmetric torsional flutter, wind flow streamlines,
 * coupled suspender cables matching deformed girder edges at every frame, and staged center-span collapse.
 */
export function makeTacomaSuspensionBridgeRig({
  deckBaseY = 2.45,
  spanLength = 15.6,
  nSegments = 22,
  deckWidth = 1.18,
  showWindStreams = false,
  includeCar = true,
} = {}) {
  const root = new THREE.Group();
  const steelTower = new THREE.MeshStandardMaterial({ color: 0x6b7b84, roughness: 0.54, metalness: 0.62 });
  const concreteMat = new THREE.MeshStandardMaterial({ color: 0x808588, roughness: 0.90 });
  const deckRoadMat = new THREE.MeshStandardMaterial({ color: 0x393d42, roughness: 0.86, metalness: 0.08 });
  const girderMat = new THREE.MeshStandardMaterial({ color: 0x54646e, roughness: 0.50, metalness: 0.58 });
  const stripeMat = new THREE.MeshStandardMaterial({ color: 0xeab308, roughness: 0.75 });
  const cableMat = new THREE.MeshStandardMaterial({ color: 0x9aa6b0, roughness: 0.44, metalness: 0.72 });
  const windMat = new THREE.MeshStandardMaterial({
    color: 0x38bdf8, emissive: 0x0284c7, emissiveIntensity: 0.55, transparent: true, opacity: 0.68, roughness: 0.3,
  });

  // Two H-frame Art Deco steel towers anchored onto concrete caisson piers in the Narrows
  const towerXs = [-spanLength * 0.34, spanLength * 0.34];
  const towerTopY = deckBaseY + 2.45;
  for (const tx of towerXs) {
    const pier = new THREE.Mesh(new THREE.BoxGeometry(1.15, 0.68, 1.95), concreteMat);
    pier.position.set(tx, 0.16, 0);
    root.add(pier);
    for (const sz of [-deckWidth * 0.54, deckWidth * 0.54]) {
      const leg = new THREE.Mesh(new THREE.BoxGeometry(0.24, towerTopY, 0.24), steelTower);
      leg.position.set(tx, towerTopY * 0.5 + 0.15, sz);
      root.add(leg);
    }
    for (const cy of [deckBaseY + 0.65, deckBaseY + 1.48, towerTopY - 0.10]) {
      const strut = new THREE.Mesh(new THREE.BoxGeometry(0.20, 0.20, deckWidth * 1.24), steelTower);
      strut.position.set(tx, cy, 0);
      root.add(strut);
    }
  }

  // Segmented continuous deck + 8-ft solid plate girders + road divider line + dynamic suspender cables
  const segments = [];
  const segLen = spanLength / nSegments;
  const suspenders = []; // each entry tracks { mesh, sideSign (-1/+1), xPos, cableAnchorY, seg }
  const halfSpan = spanLength * 0.5;
  const sagCenterY = deckBaseY + 0.42;

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
    const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 0.045, 8, false), cableMat);
    root.add(tube);
  }

  for (let i = 0; i < nSegments; i++) {
    const uNorm = (i + 0.5) / nSegments;
    const xPos = -halfSpan + uNorm * spanLength;
    const segGroup = new THREE.Group();
    segGroup.position.set(xPos, deckBaseY, 0);

    const road = new THREE.Mesh(new THREE.BoxGeometry(segLen * 1.03, 0.09, deckWidth), deckRoadMat);
    const stripe = new THREE.Mesh(new THREE.BoxGeometry(segLen * 0.62, 0.098, 0.035), stripeMat);
    // Deep solid 8-ft plate stiffening girders on both windward & leeward deck sides
    const gFront = new THREE.Mesh(new THREE.BoxGeometry(segLen * 1.04, 0.30, 0.065), girderMat);
    gFront.position.set(0, -0.05, deckWidth * 0.51);
    const gBack = gFront.clone();
    gBack.position.z = -deckWidth * 0.51;

    // Left/right edge anchors attached firmly onto segment geometry
    const edgeFront = new THREE.Object3D();
    edgeFront.position.set(0, 0.06, deckWidth * 0.52);
    const edgeBack = new THREE.Object3D();
    edgeBack.position.set(0, 0.06, -deckWidth * 0.52);
    segGroup.add(road, stripe, gFront, gBack, edgeFront, edgeBack);

    const isCenterSection = Math.abs(xPos) < spanLength * 0.092;
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

    // Paired vertical suspender rods connecting main catenary directly to segment edges every frame!
    for (const [sideSign, edgeObj] of [[1, edgeFront], [-1, edgeBack]]) {
      const cY = mainCableHeightAt(xPos);
      const rodMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 1.0, 6), cableMat);
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

  // Period 1940 sedan placed cleanly on a midspan roadway segment so it rides realistic tilt
  let car = null;
  if (includeCar) {
    car = makePeriodCar1940(0x2d3f4e);
    car.rotation.y = Math.PI * 0.5;
    car.position.set(0.0, 0.05, 0.24);
    const midIdx = Math.floor(nSegments * 0.44);
    segments[midIdx].add(car);
  }

  // Illustrative wind flow streamlines hitting flat solid plate girder (only visible when showWindStreams=true)
  const windRibbons = [];
  if (showWindStreams) {
    for (let w = 0; w < 6; w++) {
      const pts = [];
      for (let k = 0; k < 10; k++) {
        pts.push(new THREE.Vector3(-1.2 + w * 0.48, deckBaseY - 0.18 + (w % 2) * 0.24, -1.6 + k * 0.34));
      }
      const wMesh = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 20, 0.022, 6, false), windMat);
      wMesh.userData.baseZ = -1.6 + w * 0.12;
      root.add(wMesh);
      windRibbons.push(wMesh);
    }
  }

  // Explicit 3D world anchors used by Attention Pointers & Telemetry
  const midSpanAnchor = new THREE.Object3D();
  const edgeFrontAnchor = new THREE.Object3D();
  const girderAnchor = new THREE.Object3D();
  const breakSeamAnchor = new THREE.Object3D();
  const centerSeg = segments[Math.floor(nSegments * 0.5)];
  const seamSeg = segments[13];
  midSpanAnchor.position.set(0, 0.10, 0.0);
  edgeFrontAnchor.position.set(0, 0.14, deckWidth * 0.52);
  girderAnchor.position.set(0, -0.06, deckWidth * 0.53);
  centerSeg.add(midSpanAnchor, edgeFrontAnchor, girderAnchor);
  breakSeamAnchor.position.set(-segLen * 0.42, 0.14, deckWidth * 0.38);
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
  };

  function updateBridge(lt, dur, {
    mode = 'torsion_heavy',
    verticalAmp = 0.22,
    torsionRad = 0.36,
    collapseOnsetSec = null,
    aftermathCollapsed = false,
  } = {}) {
    let maxDisp = 0.0;
    let maxRoll = 0.0;
    let maxDrop = 0.0;
    let collapseNow = false;
    let allAttached = true;

    const twGain = mode === 'wobble_hook' ? 0.42
      : (mode === 'vertical_wave' ? 0.18
      : (mode === 'aftermath' ? 0.06 : (1.0 + 0.18 * clamp(lt / Math.max(0.2, dur), 0, 1))));

    segments.forEach((seg, idx) => {
      const { uNorm, isCenterSection, inMainSpan } = seg.userData;
      const ev = evaluateTorsionSpan(lt, uNorm, {
        verticalAmp: aftermathCollapsed ? 0.02 : verticalAmp,
        torsionRad: aftermathCollapsed ? 0.03 : torsionRad,
        omegaVert: 2.35,
        omegaTorsion: 3.15,
        twistGain: inMainSpan ? twGain : twGain * 0.28,
        deckHalfWidth: deckWidth * 0.5,
      });

      if ((aftermathCollapsed && isCenterSection)) {
        seg.visible = false;
        return;
      }

      seg.visible = true;
      if (collapseOnsetSec != null && isCenterSection && lt >= collapseOnsetSec) {
        collapseNow = true;
        const cTraj = evaluateCollapseTrajectory(lt, collapseOnsetSec, {
          baseY: deckBaseY,
          vx: (idx % 2 ? 0.18 : -0.18),
          vz: 0.24,
          pitchRate: 1.55,
          rollRate: 1.05,
          floorY: -0.25,
        });
        seg.position.set(seg.userData.xPos + cTraj.dx, deckBaseY + ev.dyCenter + cTraj.dy, cTraj.dz);
        seg.rotation.set(ev.rollRad + cTraj.rotX, cTraj.rotZ * 0.3, cTraj.rotZ);
        maxDisp = Math.max(maxDisp, Math.abs(cTraj.dy));
        maxDrop = Math.max(maxDrop, Math.abs(cTraj.dy));
      } else {
        const slopePitch = Math.cos(Math.PI * uNorm) * 0.05;
        seg.position.set(seg.userData.xPos, deckBaseY + ev.dyCenter, 0);
        // Roll about bridge span X axis!
        seg.rotation.set(ev.rollRad, 0, slopePitch * verticalAmp);
        maxDisp = Math.max(maxDisp, Math.abs(ev.dyCenter) + Math.abs(Math.sin(ev.rollRad) * deckWidth * 0.5));
        maxRoll = Math.max(maxRoll, Math.abs(ev.rollRad));
      }
    });

    root.updateMatrixWorld(true);
    suspenders.forEach((sp) => {
      if (!sp.seg.visible || (collapseNow && sp.seg.userData.isCenterSection)) {
        // After collapse onset, center-section suspenders dangle cleanly from main cable
        sp.mesh.position.set(sp.xPos, sp.topY - 0.55, sp.topZ);
        sp.mesh.scale.set(1, 1.1, 1);
        sp.mesh.rotation.set(Math.sin(lt * 2.5 + sp.xPos) * 0.14, 0, Math.cos(lt * 2.1) * 0.10);
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
      wr.position.z = ((lt * 1.45 + wi * 0.35) % 1.4) - 0.7;
      wr.position.y = Math.sin(lt * 4.2 + wi) * 0.08;
    });

    lastPhysTel = {
      vertex_disp_max_m: Number(maxDisp.toFixed(4)),
      deck_roll_span_rad: Number(maxRoll.toFixed(4)),
      collapse_active: collapseNow,
      collapse_drop_m: Number(maxDrop.toFixed(4)),
      cables_attached: allAttached,
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
      plate_girder_windward: girderAnchor,
      suspender_cable_joint: edgeFrontAnchor,
      collapse_break_seam: breakSeamAnchor,
      aftermath_broken_gap: midSpanAnchor,
    }, []),
  };
}

/**
 * Shot S06: 1940 Shore Onlooker Grounded Reaction Rig (no modern clothing/items).
 */
export function makeTacomaShoreOnlookerRig(makeHumanFn, charSpec = {}) {
  const root = new THREE.Group();
  const rockLedge = new THREE.Mesh(
    new THREE.BoxGeometry(5.2, 0.40, 4.6),
    new THREE.MeshStandardMaterial({ color: 0x565c54, roughness: 0.90 })
  );
  rockLedge.position.set(0, -0.20, 0);
  root.add(rockLedge);

  const actor = buildRegisteredCharacter(makeHumanFn, {
    character_id: charSpec.character_id || 'char_onlooker_1940_01',
    shirt_hex: charSpec.shirt_hex ?? 0x463d34,
    pants_hex: charSpec.pants_hex ?? 0x26292e,
    collar_hex: 0xd6d3d1,
    shoe_hex: 0x161412,
  });
  addFedora1940(actor, 0x3b332c);
  root.add(actor.root);

  const headAnchor = new THREE.Object3D();
  headAnchor.position.set(0, 0.14, 0.05);
  actor.j.head.add(headAnchor);

  const guardRail = new THREE.Mesh(
    new THREE.BoxGeometry(4.2, 0.08, 0.12),
    new THREE.MeshStandardMaterial({ color: 0x6f5438, roughness: 0.85 })
  );
  guardRail.position.set(0, 0.78, -1.65);
  root.add(guardRail);

  const stanceTracker = { epoch: -1, foot: '', anchorXZ: null };
  let lastCharTel = null;

  function updateOnlooker(lt, dur, threatPos = [0, 2.5, -9.0]) {
    const res = evaluateCharacterPose(lt, {
      primary_intent: 'brace',
      duration_sec: dur,
      ground_y: 0.0,
      base_x: 0.35,
      base_z: 0.65,
      base_yaw: -0.35,
      reaction_onset_sec: Math.min(0.42, dur * 0.15),
      retreat_distance_m: 0.55,
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
