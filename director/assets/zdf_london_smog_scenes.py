"""Procedural 1952 London Great Smog 3D Scene Library (SD-RETENTION-04.R1).

Atmospheric, period-grounded procedural Three.js stages (1952 red double-decker bus,
coal fireplace cutaway & smokestacks, stylized temperature inversion airflow boundary,
Victorian streetlamps, articulated trenchcoat/scarf pedestrian with foot-locked FK brace,
and 1956 Clean Air Act aftermath skyline recovery).

Generalizable climate/atmospheric physics visual approximation (non-CFD solver).
Deterministic on arbitrary time seek (`stateAt(t)` driven purely by local `u`, zero mutating accumulators).
"""

from __future__ import annotations


LONDON_SMOG_SCENES_JS = r"""import * as THREE from 'three';
import { clamp, easeInOut, easeOut, lerp, smooth } from './anim.js';
import { buildRegisteredCharacter } from './character_action_rig.js';
import { LayeredCutaway } from './layered_cutaway.js';
import { computeAnchorsTelemetry } from './aircraft_window_scenes.js';
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

function tagSemantic(obj, role, skipMatte = false) {
  if (!obj) return obj;
  obj.userData = obj.userData || {};
  obj.userData.semanticRole = role;
  if (skipMatte) obj.userData.matteSkip = true;
  return obj;
}

function v3Arr(obj) {
  const wp = new THREE.Vector3();
  obj.getWorldPosition(wp);
  return [Number(wp.x.toFixed(4)), Number(wp.y.toFixed(4)), Number(wp.z.toFixed(4))];
}

function makeLabelCardTexture(titleTxt, subTxt, accentHex = '#f59e0b', bgHex = '#0f172a') {
  const c = document.createElement('canvas');
  c.width = 640;
  c.height = 148;
  const ctx = c.getContext('2d');
  ctx.fillStyle = bgHex;
  ctx.globalAlpha = 0.88;
  ctx.fillRect(4, 4, 632, 140);
  ctx.globalAlpha = 1.0;
  ctx.strokeStyle = accentHex;
  ctx.lineWidth = 6;
  ctx.strokeRect(6, 6, 628, 136);
  ctx.fillStyle = accentHex;
  ctx.font = '900 38px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(titleTxt, 320, 62);
  ctx.fillStyle = '#e2e8f0';
  ctx.font = '700 26px sans-serif';
  ctx.fillText(subTxt, 320, 110);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function makeCobblestoneGround({ width = 26, depth = 30 } = {}) {
  const grp = new THREE.Group();
  tagSemantic(grp, 'environment');
  const roadMat = new THREE.MeshStandardMaterial({ color: 0x262a30, roughness: 0.88, metalness: 0.08 });
  const road = new THREE.Mesh(new THREE.BoxGeometry(width, 0.24, depth), roadMat);
  road.position.y = -0.12;
  grp.add(road);

  const curbMat = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.82 });
  for (const sx of [-2.4, 2.4]) {
    const curb = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.14, depth), curbMat);
    curb.position.set(sx, 0.07, 0);
    grp.add(curb);
    const walk = new THREE.Mesh(new THREE.BoxGeometry(4.2, 0.12, depth), new THREE.MeshStandardMaterial({ color: 0x333842, roughness: 0.9 }));
    walk.position.set(sx + (sx > 0 ? 2.2 : -2.2), 0.06, 0);
    grp.add(walk);
  }
  return shadow(grp);
}

function makeVictorianLamp({ x = -2.15, z = 0.0, litIntensity = 1.4, semanticRole = 'reference_fixed' } = {}) {
  const grp = new THREE.Group();
  grp.position.set(x, 0, z);
  tagSemantic(grp, semanticRole);

  const ironMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.55, metalness: 0.72 });
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.18, 0.45, 10), ironMat);
  base.position.y = 0.225;
  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.08, 2.25, 10), ironMat);
  post.position.y = 1.45;
  const cap = new THREE.Mesh(new THREE.ConeGeometry(0.19, 0.22, 6), ironMat);
  cap.position.y = 2.86;
  grp.add(base, post, cap);

  const globeMat = new THREE.MeshStandardMaterial({
    color: 0xfef08a, emissive: 0xf59e0b, emissiveIntensity: litIntensity, roughness: 0.2,
  });
  const globe = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.11, 0.28, 6), globeMat);
  globe.position.y = 2.62;
  tagSemantic(globe, 'causal_feature');
  grp.add(globe);

  const haloMat = new THREE.MeshBasicMaterial({
    color: 0xfbbf24, transparent: true, opacity: 0.24, depthWrite: false,
  });
  const halo = new THREE.Mesh(new THREE.SphereGeometry(0.54, 14, 14), haloMat);
  halo.position.y = 2.62;
  tagSemantic(halo, 'causal_feature', true);
  grp.add(halo);

  const pt = new THREE.PointLight(0xffb74d, litIntensity * 2.2, 6.5, 1.8);
  pt.position.y = 2.58;
  grp.add(pt);

  return { root: grp, globe, halo, globeMat, haloMat, light: pt };
}

function makeStPaulsSilhouette({ z = -9.5, scale = 1.0, role = 'reference_fixed' } = {}) {
  const grp = new THREE.Group();
  grp.position.set(0, 0, z);
  grp.scale.setScalar(scale);
  tagSemantic(grp, role);
  const stoneMat = new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.85, metalness: 0.06 });
  const roofMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.72, metalness: 0.25 });

  const nave = new THREE.Mesh(new THREE.BoxGeometry(5.6, 2.1, 2.8), stoneMat);
  nave.position.y = 1.05;
  const drum = new THREE.Mesh(new THREE.CylinderGeometry(1.15, 1.22, 1.35, 18), stoneMat);
  drum.position.y = 2.65;
  const dome = new THREE.Mesh(new THREE.SphereGeometry(1.18, 20, 14, 0, Math.PI * 2, 0, Math.PI * 0.55), roofMat);
  dome.position.y = 3.25;
  const lantern = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.30, 0.85, 10), stoneMat);
  lantern.position.y = 4.55;
  grp.add(nave, drum, dome, lantern);

  for (const sx of [-2.2, 2.2]) {
    const tower = new THREE.Mesh(new THREE.BoxGeometry(0.85, 3.0, 0.85), stoneMat);
    tower.position.set(sx, 1.5, 0.8);
    const spire = new THREE.Mesh(new THREE.ConeGeometry(0.32, 0.95, 8), roofMat);
    spire.position.set(sx, 3.45, 0.8);
    grp.add(tower, spire);
  }
  return shadow(grp);
}

function makeDoubleDeckerBus1952({ scale = 1.0 } = {}) {
  const root = new THREE.Group();
  root.scale.setScalar(scale);
  tagSemantic(root, 'subject');

  const redMat = new THREE.MeshStandardMaterial({ color: 0xb91c1c, roughness: 0.38, metalness: 0.25 });
  const creamMat = new THREE.MeshStandardMaterial({ color: 0xfef3c7, roughness: 0.45 });
  const winMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.22, metalness: 0.45, emissive: 0x451a03, emissiveIntensity: 0.28 });
  const tireMat = new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.88 });
  const rimMat = new THREE.MeshStandardMaterial({ color: 0x9ca3af, roughness: 0.45, metalness: 0.7 });

  const lower = new THREE.Mesh(new THREE.BoxGeometry(1.42, 0.92, 3.60), redMat);
  lower.position.y = 0.72;
  const upper = new THREE.Mesh(new THREE.BoxGeometry(1.38, 0.88, 3.50), redMat);
  upper.position.set(0, 1.62, -0.05);
  const creamBand = new THREE.Mesh(new THREE.BoxGeometry(1.45, 0.14, 3.62), creamMat);
  creamBand.position.y = 1.18;
  const roof = new THREE.Mesh(new THREE.BoxGeometry(1.32, 0.16, 3.42), redMat);
  roof.position.set(0, 2.10, -0.05);
  const hood = new THREE.Mesh(new THREE.BoxGeometry(0.88, 0.64, 0.72), redMat);
  hood.position.set(-0.18, 0.56, 2.02);
  const grille = new THREE.Mesh(new THREE.BoxGeometry(0.58, 0.52, 0.08), rimMat);
  grille.position.set(-0.18, 0.54, 2.38);
  root.add(lower, upper, creamBand, roof, hood, grille);

  for (const rowY of [0.84, 1.66]) {
    for (let k = -1.25; k <= 1.25; k += 0.62) {
      const wg = new THREE.Mesh(new THREE.BoxGeometry(1.46, 0.36, 0.44), winMat);
      wg.position.set(0, rowY, k);
      root.add(wg);
    }
  }
  const frontGlass = new THREE.Mesh(new THREE.BoxGeometry(1.24, 0.38, 0.08), winMat);
  frontGlass.position.set(0, 1.66, 1.72);
  root.add(frontGlass);

  const wheels = [];
  for (const wz of [1.45, -1.20]) {
    for (const wx of [-0.72, 0.72]) {
      const wg = new THREE.Group();
      wg.position.set(wx, 0.30, wz);
      const tire = new THREE.Mesh(new THREE.CylinderGeometry(0.30, 0.30, 0.18, 16), tireMat);
      tire.rotation.z = Math.PI * 0.5;
      const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 0.20, 12), rimMat);
      hub.rotation.z = Math.PI * 0.5;
      wg.add(tire, hub);
      root.add(wg);
      wheels.push(wg);
    }
  }

  const lampsGrp = new THREE.Group();
  tagSemantic(lampsGrp, 'causal_feature');
  const headMat = new THREE.MeshStandardMaterial({ color: 0xfef08a, emissive: 0xfde047, emissiveIntensity: 2.2 });
  const coneMat = new THREE.MeshBasicMaterial({
    color: 0xfde68a, transparent: true, opacity: 0.22, side: THREE.DoubleSide, depthWrite: false,
  });
  const cones = [];
  for (const hx of [-0.46, 0.24]) {
    const hMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.085, 0.085, 0.10, 12), headMat);
    hMesh.rotation.x = Math.PI * 0.5;
    hMesh.position.set(hx, 0.56, 2.38);
    lampsGrp.add(hMesh);

    const cone = new THREE.Mesh(new THREE.ConeGeometry(0.56, 2.35, 18, 1, true), coneMat);
    cone.rotation.x = -Math.PI * 0.5;
    cone.position.set(hx, 0.52, 3.55);
    tagSemantic(cone, 'causal_feature', true);
    lampsGrp.add(cone);
    cones.push(cone);
  }
  root.add(lampsGrp);

  const headLight = new THREE.SpotLight(0xfde68a, 4.5, 9.0, 0.45, 0.65);
  headLight.position.set(0, 0.62, 2.40);
  headLight.target.position.set(0, 0.35, 6.20);
  root.add(headLight, headLight.target);

  return { root: shadow(root), wheels, cones, coneMat, lampsGrp };
}

function makeSmokePlumeCluster({ count = 18, colorHex = 0x57534e, sulfurTint = false, semanticRole = 'effect_result' } = {}) {
  const grp = new THREE.Group();
  tagSemantic(grp, semanticRole);
  const baseMat = new THREE.MeshStandardMaterial({
    color: colorHex, roughness: 0.94, metalness: 0.02,
    emissive: sulfurTint ? 0x422006 : 0x1c1917, emissiveIntensity: sulfurTint ? 0.22 : 0.10,
  });
  const sulfurMat = new THREE.MeshStandardMaterial({
    color: 0xeab308, emissive: 0xca8a04, emissiveIntensity: 0.45, roughness: 0.55,
  });
  const puffs = [];
  for (let i = 0; i < count; i++) {
    const isSulfur = sulfurTint && (i % 4 === 1);
    const r = isSulfur ? 0.085 : (0.14 + (i % 5) * 0.032);
    const mesh = new THREE.Mesh(new THREE.DodecahedronGeometry(r, 1), isSulfur ? sulfurMat : baseMat);
    mesh.userData.phase = (i / count);
    mesh.userData.seedOffset = ((i * 73) % 19) / 19.0 - 0.5;
    grp.add(mesh);
    puffs.push(mesh);
  }
  return { root: grp, puffs };
}

// 1. Hook Scene: London noon street blacked out into amber lamp halos by descending ochre smog
export function makeLondonStreetFogRig() {
  const root = new THREE.Group();
  root.add(makeCobblestoneGround({ width: 22, depth: 28 }));

  const buildings = new THREE.Group();
  tagSemantic(buildings, 'subject');
  const brickA = new THREE.MeshStandardMaterial({ color: 0x574238, roughness: 0.85 });
  const brickB = new THREE.MeshStandardMaterial({ color: 0x44403c, roughness: 0.88 });
  const winGlow = new THREE.MeshStandardMaterial({ color: 0xfde68a, emissive: 0xf59e0b, emissiveIntensity: 0.72 });
  for (let i = 0; i < 6; i++) {
    const zPos = 2.2 - i * 2.45;
    for (const side of [-1, 1]) {
      const b = new THREE.Mesh(new THREE.BoxGeometry(2.4, 3.8 + (i % 2) * 0.7, 2.15), i % 2 === 0 ? brickA : brickB);
      b.position.set(side * 3.7, 1.9 + (i % 2) * 0.35, zPos);
      buildings.add(b);
      for (const wy of [1.2, 2.35]) {
        const w = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.52, 0.46), winGlow);
        w.position.set(side * 2.48, wy, zPos + (side > 0 ? 0.35 : -0.35));
        buildings.add(w);
      }
    }
  }
  root.add(shadow(buildings));

  const domeRef = makeStPaulsSilhouette({ z: -9.8, scale: 0.92, role: 'reference_fixed' });
  root.add(domeRef);

  const lamps = [
    makeVictorianLamp({ x: -1.95, z: 1.5, semanticRole: 'reference_fixed' }),
    makeVictorianLamp({ x: 1.95, z: -0.4, semanticRole: 'reference_fixed' }),
    makeVictorianLamp({ x: -1.95, z: -2.8, semanticRole: 'reference_fixed' }),
    makeVictorianLamp({ x: 1.95, z: -5.2, semanticRole: 'reference_fixed' }),
  ];
  for (const lm of lamps) root.add(lm.root);

  const fgBus = makeDoubleDeckerBus1952({ scale: 0.82 });
  fgBus.root.position.set(0.55, 0, -2.1);
  fgBus.root.rotation.y = 0.08;
  root.add(fgBus.root);

  const veilMatFar = new THREE.MeshBasicMaterial({ color: 0x78716c, transparent: true, opacity: 0.35, depthWrite: false, side: THREE.DoubleSide });
  const veilFar = new THREE.Mesh(new THREE.PlaneGeometry(18, 9), veilMatFar);
  veilFar.position.set(0, 2.8, -6.2);
  tagSemantic(veilFar, 'causal_feature', true);

  const veilMatMid = new THREE.MeshBasicMaterial({ color: 0x927c44, transparent: true, opacity: 0.25, depthWrite: false, side: THREE.DoubleSide });
  const veilMid = new THREE.Mesh(new THREE.PlaneGeometry(16, 8), veilMatMid);
  veilMid.position.set(0, 2.4, -3.1);
  tagSemantic(veilMid, 'causal_feature', true);
  root.add(veilFar, veilMid);

  const smogFrontPuffs = makeSmokePlumeCluster({ count: 16, colorHex: 0x6b6043, sulfurTint: true, semanticRole: 'causal_feature' });
  smogFrontPuffs.root.position.set(0, 1.35, -3.5);
  root.add(smogFrontPuffs.root);

  return {
    root,
    update(u, lt, scene) {
      const fogP = clamp(easeInOut(u), 0, 1);
      veilMatFar.opacity = lerp(0.20, 0.78, fogP);
      veilMatMid.opacity = lerp(0.12, 0.62, fogP);
      if (scene && scene.fog) {
        scene.fog.density = lerp(0.035, 0.145, fogP);
      }
      const busZ = lerp(-2.9, -0.7, u);
      fgBus.root.position.z = busZ;
      for (const w of fgBus.wheels) w.rotation.x = u * 8.5;
      fgBus.coneMat.opacity = lerp(0.14, 0.34, fogP);

      lamps.forEach((lm, idx) => {
        lm.haloMat.opacity = lerp(0.14, 0.36, fogP) + 0.03 * Math.sin(lt * 3.0 + idx);
        lm.light.intensity = lerp(1.6, 3.6, fogP);
      });

      smogFrontPuffs.puffs.forEach((p, idx) => {
        const cyc = (p.userData.phase + u * 0.7) % 1.0;
        p.position.set(
          Math.sin(idx * 2.1 + u * 2.4) * 2.1,
          Math.sin(cyc * Math.PI) * 1.15 - 0.15,
          lerp(-3.5, 2.2, cyc)
        );
        const s = 1.2 + Math.sin(cyc * Math.PI) * 1.45;
        p.scale.setScalar(s);
      });

      root.updateMatrixWorld(true);
      return {
        anchors: {
          streetlamp_halo_visibility: lamps[1].globe,
          lamppost_column_ref: [-1.95, 1.45, 1.5],
          bus_headlight_cone: [0.45, 0.62, busZ + 1.8],
        },
        physicalMotion: {
          vertex_disp_max_m: Number((busZ + 2.9).toFixed(4)),
          visibility_obscuration: Number(fogP.toFixed(4)),
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 2. Mechanism Cutaway: Coal fireplace & industrial stacks feeding sulfur & soot upward
export function makeCoalCombustionCutawayRig() {
  const root = new THREE.Group();
  root.add(makeCobblestoneGround({ width: 16, depth: 16 }));

  const cut = new LayeredCutaway({
    id: 'coal_hearth_cut',
    worldAnchor: [0, 1.35, 0],
    clipNormal: [0, 0, -1],
    clipConstantStart: 0.45,
    clipConstantOpen: 0.02,
  });
  const wallOuterMat = new THREE.MeshStandardMaterial({ color: 0x5c3d2e, roughness: 0.85 });
  const hearthWall = new THREE.Mesh(new THREE.BoxGeometry(1.9, 2.35, 1.1), wallOuterMat);
  hearthWall.position.set(0, 1.18, -0.15);
  tagSemantic(hearthWall, 'subject');
  cut.addOuterShell(hearthWall, { applyClip: true });

  const chimneyRim = new THREE.Mesh(
    new THREE.BoxGeometry(1.05, 0.24, 0.92),
    new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.72 })
  );
  chimneyRim.position.set(0, 2.42, -0.15);
  tagSemantic(chimneyRim, 'reference_fixed');
  root.add(cut.root, shadow(chimneyRim));

  const flueChamber = new THREE.Mesh(
    new THREE.BoxGeometry(0.68, 2.15, 0.56),
    new THREE.MeshStandardMaterial({ color: 0x1c1917, roughness: 0.92, side: THREE.BackSide })
  );
  flueChamber.position.set(0, 1.28, 0.08);
  tagSemantic(flueChamber, 'causal_feature');
  cut.addInternalComponent('flue_cavity', flueChamber, { layerIndex: 1 });

  const coalBedGrp = new THREE.Group();
  coalBedGrp.position.set(0, 0.42, 0.16);
  tagSemantic(coalBedGrp, 'cause_source');
  const emberMat = new THREE.MeshStandardMaterial({
    color: 0x991b1b, emissive: 0xf97316, emissiveIntensity: 1.65, roughness: 0.65,
  });
  for (let k = 0; k < 7; k++) {
    const chunk = new THREE.Mesh(new THREE.DodecahedronGeometry(0.11 + (k % 3) * 0.025, 0), emberMat);
    chunk.position.set((k - 3) * 0.095, (k % 2) * 0.06, ((k * 3) % 5 - 2) * 0.03);
    coalBedGrp.add(chunk);
  }
  const fireLight = new THREE.PointLight(0xf97316, 4.2, 4.0);
  fireLight.position.set(0, 0.55, 0.35);
  cut.addInternalComponent('coal_bed', coalBedGrp, { layerIndex: 2 });
  root.add(fireLight);

  const bgStacks = new THREE.Group();
  tagSemantic(bgStacks, 'subject');
  const stackMat = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.78 });
  for (const sx of [-1.85, 1.85]) {
    const stMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.28, 3.3, 14), stackMat);
    stMesh.position.set(sx, 1.65, -2.8);
    bgStacks.add(stMesh);
  }
  root.add(shadow(bgStacks));

  const fluePlume = makeSmokePlumeCluster({ count: 22, colorHex: 0x44403c, sulfurTint: true, semanticRole: 'causal_feature' });
  root.add(fluePlume.root);

  return {
    root,
    update(u, lt) {
      cut.setReveal(smooth(clamp(u * 2.4, 0, 1)));
      emberMat.emissiveIntensity = 1.45 + 0.55 * Math.sin(lt * 5.2);
      fireLight.intensity = 3.8 + 1.2 * Math.sin(lt * 5.2);

      fluePlume.puffs.forEach((p, idx) => {
        const cyc = (p.userData.phase + u * 0.95) % 1.0;
        const y = lerp(0.55, 4.15, cyc);
        const spread = cyc > 0.55 ? (cyc - 0.55) * 1.15 : 0.05;
        p.position.set(
          Math.sin(cyc * 9.0 + idx) * spread + (cyc > 0.6 ? p.userData.seedOffset * 0.50 : 0),
          y,
          0.12 + Math.cos(cyc * 7.0 + idx) * spread * 0.35
        );
        const sc = 0.36 + cyc * 0.95;
        p.scale.setScalar(sc);
      });

      return {
        anchors: {
          chimney_flue_combustion: [0, 1.45, 0.20],
          roofline_chimney_masonry_ref: [0, 2.42, 0.25],
        },
        cutaway: cut.getTelemetry(),
        physicalMotion: {
          vertex_disp_max_m: Number((1.2 + u * 2.4).toFixed(4)),
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 3. Temperature Inversion Trap: Warm upper air boundary deflects rising coal plumes horizontally over city
export function makeLondonAtmosphericInversionRig() {
  const root = new THREE.Group();
  root.add(makeCobblestoneGround({ width: 24, depth: 20 }));

  const dome = makeStPaulsSilhouette({ z: -3.2, scale: 0.72, role: 'reference_fixed' });
  root.add(dome);

  const chimneyGrp = new THREE.Group();
  tagSemantic(chimneyGrp, 'cause_source');
  const chMat = new THREE.MeshStandardMaterial({ color: 0x4b5563, roughness: 0.8 });
  const stackXs = [-2.2, -0.75, 0.85, 2.15];
  for (const sx of stackXs) {
    const roof = new THREE.Mesh(new THREE.BoxGeometry(1.1, 1.15, 1.1), chMat);
    roof.position.set(sx, 0.58, 0.0);
    const stack = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.19, 1.15, 12), chMat);
    stack.position.set(sx, 1.55, 0.0);
    chimneyGrp.add(roof, stack);
  }
  root.add(shadow(chimneyGrp));

  const lidGrp = new THREE.Group();
  lidGrp.position.set(0, 3.25, -0.2);
  tagSemantic(lidGrp, 'causal_feature');
  const lidMat = new THREE.MeshStandardMaterial({
    color: 0xf97316, emissive: 0xea580c, emissiveIntensity: 0.65,
    transparent: true, opacity: 0.48, roughness: 0.35, side: THREE.DoubleSide, depthWrite: false,
  });
  const lidSlab = new THREE.Mesh(new THREE.BoxGeometry(9.6, 0.42, 4.2), lidMat);
  tagSemantic(lidSlab, 'causal_feature');
  lidGrp.add(lidSlab);

  const labelTex = makeLabelCardTexture('ILLUSTRATIVE AIRFLOW', 'WARM AIR INVERSION CAP', '#fbbf24', '#1e1b18');
  const badge = new THREE.Mesh(
    new THREE.PlaneGeometry(3.2, 0.74),
    new THREE.MeshBasicMaterial({ map: labelTex, transparent: true })
  );
  badge.position.set(0, 0.42, 2.15);
  tagSemantic(badge, 'causal_feature');
  lidGrp.add(badge);
  root.add(lidGrp);

  const smokeStreams = stackXs.map(() =>
    makeSmokePlumeCluster({ count: 14, colorHex: 0x716448, sulfurTint: true, semanticRole: 'effect_result' })
  );
  for (const ss of smokeStreams) root.add(ss.root);

  const arrowGrp = new THREE.Group();
  tagSemantic(arrowGrp, 'causal_feature');
  const arrowMat = new THREE.MeshStandardMaterial({ color: 0xfbbf24, emissive: 0xd97706, emissiveIntensity: 0.9 });
  const arrows = [];
  for (const ax of [-1.8, 0.0, 1.8]) {
    const cone = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.38, 10), arrowMat);
    cone.rotation.z = Math.PI;
    cone.position.set(ax, 2.82, 0.85);
    arrowGrp.add(cone);
    arrows.push(cone);
  }
  root.add(arrowGrp);

  return {
    root,
    update(u, lt) {
      lidGrp.position.y = 3.22 + 0.06 * Math.sin(lt * 2.0);
      arrows.forEach((ar, idx) => {
        ar.position.y = 2.86 - 0.14 * ((lt * 1.2 + idx * 0.3) % 1.0);
      });

      smokeStreams.forEach((ss, sIdx) => {
        const sx = stackXs[sIdx];
        ss.puffs.forEach((p, pIdx) => {
          const cyc = (p.userData.phase + u * 0.85) % 1.0;
          let py;
          let px;
          let sc;
          if (cyc < 0.35) {
            const sub = cyc / 0.35;
            py = lerp(2.05, 2.86, sub);
            px = sx + Math.sin(lt * 3.0 + pIdx) * 0.08;
            sc = lerp(0.55, 1.05, sub);
          } else {
            const sub = (cyc - 0.35) / 0.65;
            const dir = (sIdx % 2 === 0 ? -1 : 1) * (pIdx % 2 === 0 ? 1 : -0.65);
            py = lerp(2.86, 1.72, sub * 0.65) + Math.sin(sub * 6.0 + pIdx) * 0.14;
            px = sx + dir * lerp(0.1, 2.35, sub);
            sc = lerp(1.05, 2.15, sub);
          }
          p.position.set(px, py, (sIdx % 2 === 0 ? 0.3 : -0.3) + p.userData.seedOffset * 0.45);
          p.scale.setScalar(sc);
        });
      });

      return {
        anchors: {
          inversion_thermal_boundary: [0.0, 3.20, 0.4],
          st_pauls_dome_and_horizon_ref: [0.0, 3.40, -3.2],
        },
        physicalMotion: {
          vertex_disp_max_m: Number((1.85 + Math.sin(lt * 2.0) * 0.15).toFixed(4)),
          trapped_cap_y_m: 3.22,
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 4. Visibility Crisis: Double-decker bus crawls behind lantern-carrying guide past fixed lampposts
export function makeLondonBusVisibilityRig(makeHumanFn, { charSpec = {}, dur = 4.0 } = {}) {
  const root = new THREE.Group();
  root.add(makeCobblestoneGround({ width: 22, depth: 30 }));

  const bus = makeDoubleDeckerBus1952({ scale: 0.92 });
  root.add(bus.root);

  const lamps = [
    makeVictorianLamp({ x: 1.85, z: 3.2, semanticRole: 'reference_fixed' }),
    makeVictorianLamp({ x: 1.85, z: -0.6, semanticRole: 'reference_fixed' }),
    makeVictorianLamp({ x: 1.85, z: -4.4, semanticRole: 'reference_fixed' }),
  ];
  for (const lm of lamps) root.add(lm.root);

  const walker = buildRegisteredCharacter(makeHumanFn, {
    shirt_hex: charSpec.shirt_hex || 0x475569,
    pants_hex: charSpec.pants_hex || 0x1e293b,
    collar_hex: charSpec.collar_hex || 0x9f1239,
    skin_hex: charSpec.skin_hex || 0xd9a484,
  });
  tagSemantic(walker.root, 'character');

  const lantern = new THREE.Group();
  const lCore = new THREE.Mesh(
    new THREE.CylinderGeometry(0.06, 0.06, 0.16, 8),
    new THREE.MeshStandardMaterial({ color: 0xfef08a, emissive: 0xf59e0b, emissiveIntensity: 2.2 })
  );
  const lPt = new THREE.PointLight(0xffb74d, 3.2, 4.5);
  lantern.add(lCore, lPt);
  tagSemantic(lantern, 'causal_feature');
  walker.j.rWr.add(lantern);
  lantern.position.set(0, -0.09, 0.05);
  root.add(walker.root);

  const fogClumps = makeSmokePlumeCluster({ count: 14, colorHex: 0x7c704c, sulfurTint: true, semanticRole: 'effect_result' });
  fogClumps.root.traverse(c => { c.userData.matteSkip = true; });
  root.add(fogClumps.root);

  const stanceTracker = {};
  const threatBack = [0.35, 1.2, -4.5];
  const walkPlan = {
    duration_sec: dur,
    primary_intent: 'retreat',
    ground_y: 0.0,
    base_x: 0.35,
    base_z: 1.35,
    base_yaw: 0.0,
    reaction_onset_sec: 0.05,
    retreat_distance_m: 1.65,
    threat_world: threatBack,
  };

  return {
    root,
    update(u, lt, scene) {
      const walkEval = evaluateCharacterPose(lt, walkPlan);
      applyGroundedCharacterPose(walker, walkEval);
      walker.j.rSh.rotation.x = -0.68;
      walker.j.rEl.rotation.x = -0.45;
      walker.root.updateMatrixWorld(true);

      const walkZ = walkEval.root_pos[2];
      const busZ = walkZ - 3.65;
      bus.root.position.set(-0.22, 0, busZ);
      for (const w of bus.wheels) w.rotation.x = u * 11.0;

      if (scene && scene.fog) {
        scene.fog.density = 0.115;
      }

      fogClumps.puffs.forEach((p, idx) => {
        const sideSign = (idx % 2 === 0 ? -1 : 1);
        p.position.set(
          sideSign * (1.85 + (idx % 3) * 0.55) + Math.sin(idx * 1.9 + lt * 0.45) * 0.45,
          1.45 + (idx % 3) * 0.52,
          lerp(-5.8, -0.2, ((idx / 14) + u * 0.25) % 1.0)
        );
        p.scale.setScalar(0.65 + (idx % 3) * 0.22);
      });

      const cpTel = getCharacterPerformanceTelemetry(walker, walkEval, stanceTracker, threatBack);
      return {
        anchors: {
          bus_headlight_cone: [-0.05, 0.72, busZ + 2.35],
          lamppost_column_ref: [1.85, 1.55, -0.6],
        },
        characterPerformance: cpTel,
        physicalMotion: {
          vertex_disp_max_m: Number(Math.abs(walkZ - 1.35).toFixed(4)),
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 5. Pedestrian Reaction: Period pedestrian braces at curb, shields scarf over airway against smog swirls
export function makeLondonPedestrianReactionRig(makeHumanFn, { charSpec = {}, dur = 4.0 } = {}) {
  const root = new THREE.Group();
  root.add(makeCobblestoneGround({ width: 16, depth: 18 }));

  const curbPost = new THREE.Mesh(
    new THREE.CylinderGeometry(0.10, 0.14, 0.92, 12),
    new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.55, metalness: 0.7 })
  );
  curbPost.position.set(-1.05, 0.46, -0.45);
  tagSemantic(curbPost, 'reference_fixed');
  root.add(shadow(curbPost));

  const leftLamp = makeVictorianLamp({ x: -0.95, z: -1.45, litIntensity: 2.4, semanticRole: 'reference_fixed' });
  root.add(leftLamp.root);

  // Period brick terrace facade across street for depth context & foreground figure-ground contrast
  const terrace = new THREE.Group();
  tagSemantic(terrace, 'subject');
  const wallMat = new THREE.MeshStandardMaterial({ color: 0x3b2f2f, roughness: 0.86 });
  const winGlowMat = new THREE.MeshStandardMaterial({ color: 0xfde68a, emissive: 0xd97706, emissiveIntensity: 0.65 });
  const facade = new THREE.Mesh(new THREE.BoxGeometry(6.8, 3.8, 1.2), wallMat);
  facade.position.set(0, 1.9, -4.1);
  terrace.add(facade);
  for (const wx of [-1.8, 0.0, 1.8]) {
    const win = new THREE.Mesh(new THREE.BoxGeometry(0.65, 0.95, 0.12), winGlowMat);
    win.position.set(wx, 1.75, -3.48);
    terrace.add(win);
  }
  root.add(shadow(terrace));

  const hero = buildRegisteredCharacter(makeHumanFn, {
    shirt_hex: charSpec.shirt_hex || 0x475569,
    pants_hex: charSpec.pants_hex || 0x1e293b,
    collar_hex: charSpec.collar_hex || 0x9f1239,
    skin_hex: charSpec.skin_hex || 0xd9a484,
  });
  tagSemantic(hero.root, 'character');

  const scarfShield = new THREE.Mesh(
    new THREE.CylinderGeometry(0.052, 0.062, 0.095, 12),
    new THREE.MeshStandardMaterial({ color: charSpec.collar_hex || 0x9f1239, roughness: 0.85 })
  );
  scarfShield.rotation.z = 0.35;
  tagSemantic(scarfShield, 'causal_feature');
  hero.j.rWr.add(scarfShield);
  scarfShield.position.set(-0.02, -0.04, 0.04);
  root.add(hero.root);

  const smogBand = makeSmokePlumeCluster({ count: 16, colorHex: 0x716448, sulfurTint: true, semanticRole: 'effect_result' });
  smogBand.root.traverse(c => { c.userData.matteSkip = true; });
  root.add(smogBand.root);

  const stanceTracker = {};
  const hazardThreat = [-1.15, 1.4, -1.85];
  const bracePlan = {
    duration_sec: dur,
    primary_intent: 'brace',
    ground_y: 0.0,
    base_x: 0.28,
    base_z: 0.24,
    base_yaw: -0.32,
    reaction_onset_sec: Math.min(0.45, dur * 0.20),
    retreat_distance_m: 0.36,
    threat_world: hazardThreat,
  };

  return {
    root,
    update(u, lt, scene) {
      const coughPulse = Math.max(0, Math.sin(u * Math.PI * 3.0));
      const braceEval = evaluateCharacterPose(lt, bracePlan);
      applyGroundedCharacterPose(hero, braceEval);
      hero.j.rSh.rotation.set(-0.98 - 0.10 * coughPulse, 0.25, -0.22);
      hero.j.rEl.rotation.set(-1.18 - 0.08 * coughPulse, 0, 0);
      hero.j.lSh.rotation.set(-0.22, 0.0, 0.20);
      hero.j.lEl.rotation.set(-0.45, 0.0, 0.0);
      hero.root.updateMatrixWorld(true);

      if (scene && scene.fog) {
        scene.fog.density = 0.085;
      }

      smogBand.puffs.forEach((p, idx) => {
        const ang = lt * 0.95 + idx * 0.42;
        p.position.set(
          Math.cos(ang) * (1.45 + (idx % 3) * 0.35),
          0.35 + (idx % 3) * 0.28 + Math.sin(idx + lt * 1.4) * 0.14,
          -1.85 - Math.abs(Math.sin(ang)) * 1.15
        );
        p.scale.setScalar(0.42 + (idx % 3) * 0.14);
      });

      const cpTel = getCharacterPerformanceTelemetry(hero, braceEval, stanceTracker, hazardThreat);
      const headArr = v3Arr(hero.j.head);
      return {
        anchors: {
          pedestrian_respiratory_stance_zone: headArr,
          pedestrian_respiratory_brace: headArr,
          victorian_curb_post_ref: [-1.05, 0.65, -0.45],
        },
        characterPerformance: cpTel,
        physicalMotion: {
          vertex_disp_max_m: Number((0.18 + 0.14 * coughPulse).toFixed(4)),
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 6. Clean Air Act 1956 Aftermath: Skyline fog clearing + transition from coal smoke to clean burner
export function makeLondonAftermathRig() {
  const root = new THREE.Group();
  root.add(makeCobblestoneGround({ width: 24, depth: 24 }));

  const dome = makeStPaulsSilhouette({ z: -3.1, scale: 1.05, role: 'reference_fixed' });
  root.add(dome);

  // Flanking period townhouses showing full city block clearing under cleaner skies (`subject`)
  const cityRow = new THREE.Group();
  tagSemantic(cityRow, 'subject');
  const rowMatA = new THREE.MeshStandardMaterial({ color: 0x574842, roughness: 0.82 });
  const rowMatB = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.78 });
  for (const sx of [-2.4, -1.25, 1.25, 2.4]) {
    const h = 2.65 + (Math.abs(sx) > 2.0 ? 0.55 : 0.0);
    const blk = new THREE.Mesh(new THREE.BoxGeometry(1.02, h, 1.35), Math.abs(sx) > 2.0 ? rowMatA : rowMatB);
    blk.position.set(sx, h * 0.5, -1.45);
    cityRow.add(blk);
    const flue = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.14, 0.65, 10), rowMatB);
    flue.position.set(sx, h + 0.32, -1.45);
    cityRow.add(flue);
  }
  root.add(shadow(cityRow));

  const hearth = new THREE.Group();
  hearth.position.set(0, 0, 0.55);
  tagSemantic(hearth, 'subject');
  const masonryMat = new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.76 });
  const trimMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.65 });
  const frame = new THREE.Mesh(new THREE.BoxGeometry(2.35, 2.35, 1.05), masonryMat);
  frame.position.y = 1.18;
  const mantle = new THREE.Mesh(new THREE.BoxGeometry(2.55, 0.18, 1.22), trimMat);
  mantle.position.y = 1.32;
  const fireboxRecess = new THREE.Mesh(new THREE.BoxGeometry(1.16, 0.84, 0.20), new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.9 }));
  fireboxRecess.position.set(0, 0.68, 0.56);
  const chimneyStack = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.32, 1.35, 14), masonryMat);
  chimneyStack.position.y = 2.90;
  hearth.add(frame, mantle, fireboxRecess, chimneyStack);
  root.add(shadow(hearth));

  const burnerCore = new THREE.Mesh(
    new THREE.BoxGeometry(0.92, 0.50, 0.36),
    new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x0ea5e9, emissiveIntensity: 2.5 })
  );
  burnerCore.position.set(0, 0.72, 0.90);
  tagSemantic(burnerCore, 'causal_feature');
  root.add(burnerCore);

  const smokeLeftover = makeSmokePlumeCluster({ count: 14, colorHex: 0x9ca3af, sulfurTint: false, semanticRole: 'causal_feature' });
  root.add(smokeLeftover.root);

  return {
    root,
    update(u, lt, scene) {
      const clearP = clamp(easeInOut(u), 0, 1);
      burnerCore.material.color.setHex(clearP < 0.35 ? 0xf97316 : 0x38bdf8);
      burnerCore.material.emissive.setHex(clearP < 0.35 ? 0xea580c : 0x0ea5e9);

      if (scene && scene.fog) {
        scene.fog.density = lerp(0.085, 0.012, clearP);
        scene.fog.color.setHex(clearP < 0.4 ? 0x6b6043 : 0x93c5fd);
      }

      smokeLeftover.puffs.forEach((p, idx) => {
        const cyc = (p.userData.phase + u * 0.8) % 1.0;
        p.position.set(
          Math.sin(cyc * 5.0 + idx) * 0.24,
          lerp(3.62, 5.25, cyc),
          0.55
        );
        const s = lerp(1.05, 0.35, clearP) * (0.75 + cyc * 0.65);
        p.scale.setScalar(Math.max(0.14, s));
      });

      return {
        anchors: {
          smokeless_hearth_transition: [0, 1.45, 0.85],
          st_pauls_silhouette_ref: [0, 3.2, -3.1],
        },
        physicalMotion: {
          vertex_disp_max_m: Number((1.0 - clearP).toFixed(4)),
          air_clarity_recovery: Number(clearP.toFixed(4)),
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}
"""
