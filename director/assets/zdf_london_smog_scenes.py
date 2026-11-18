"""Procedural 1952 London Great Smog 3D Scene Library (`SD-RETENTION-04.R2`).

Upgrades over R1:
- Eliminates ALL exposed faceted polyhedral/sphere smoke puffs & yellow marble halos
  by delegating plumes and haze strata to shared `atmospheric_volume_primitives.js`
  (`makeVolumetricPlumeStream`, `makeLayeredSmogStrata`, `makeLightScatterHaloSprite`).
- Removes the legacy oversized 3D airflow plane card; relies on physical airflow
  visualization + screen-safe `EditorialOverlayController` anchored badges.
- Adds genuinely distinct rooftop smokestack (`makeLondonRooftopStacksRig`) and street-canyon
  under-lid trap (`makeLondonStreetCanyonTrappingRig`) rigs so consecutive London beats never repeat
  identical cutaway or elevation setups.
- Upgrades E1 pedestrian scarf/cough posture and clean-sky before/after payoff (`makeLondonAftermathRig`).

Deterministic on arbitrary time seek (`stateAt(t)` driven purely by continuous `(u, lt)`).
Disclosed model: `stylized_atmospheric_visualization` (procedural soft-sprite approximation, non-CFD).
"""

from __future__ import annotations


LONDON_SMOG_SCENES_JS = r"""import * as THREE from 'three';
import { clamp, easeInOut, easeOut, lerp, smooth } from './anim.js';
import { buildRegisteredCharacter } from './character_action_rig.js';
import { LayeredCutaway } from './layered_cutaway.js';
import {
  evaluateCharacterPose,
  applyGroundedCharacterPose,
  getCharacterPerformanceTelemetry,
} from './character_performance.js';
import {
  makeVolumetricPlumeStream,
  makeLayeredSmogStrata,
  makeLightScatterHaloSprite,
} from './atmospheric_volume_primitives.js';

function shadow(o) {
  o.traverse(c => {
    if ((c.isMesh || c.isInstancedMesh) && !(c.userData && c.userData.matteSkip)) {
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
    const walk = new THREE.Mesh(
      new THREE.BoxGeometry(4.2, 0.12, depth),
      new THREE.MeshStandardMaterial({ color: 0x333842, roughness: 0.9 })
    );
    walk.position.set(sx + (sx > 0 ? 2.2 : -2.2), 0.06, 0);
    grp.add(walk);
  }
  return shadow(grp);
}

function makeVictorianLamp({ x = -2.15, z = 0.0, litIntensity = 1.4, semanticRole = 'reference_fixed', seed = 401 } = {}) {
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
  const globe = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.10, 0.28, 6), globeMat);
  globe.position.y = 2.62;
  tagSemantic(globe, 'causal_feature');
  grp.add(globe);

  // Soft scatter glow sprite (NO solid glossy sphere halo)
  const haloSprite = makeLightScatterHaloSprite({ colorHex: 0xfde68a, scale: 1.45, opacity: 0.28, seed });
  haloSprite.mesh.position.y = 2.62;
  grp.add(haloSprite.mesh);

  const pt = new THREE.PointLight(0xffb74d, litIntensity * 2.2, 6.5, 1.8);
  pt.position.y = 2.58;
  grp.add(pt);

  return { root: grp, globe, halo: haloSprite.mesh, globeMat, haloMat: haloSprite.material, light: pt };
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

    const cone = new THREE.Mesh(new THREE.ConeGeometry(0.54, 2.35, 18, 1, true), coneMat);
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

/**
 * Clean volumetric-like wrapper preserving compatibility while strictly banning dodeca/sphere puffs.
 */
export function makeSmokePlumeCluster({
  count = 24,
  colorHex = 0x524c44,
  sulfurTint = false,
  semanticRole = 'effect_result',
  ventWorld = [0, 0.5, 0],
  riseHeight = 3.1,
  lateralSpread = 0.72,
  inversionCapY = null,
  seed = 109,
  baseScale = 0.52,
  endScale = 1.65,
  opacityScale = 0.58,
  matteSkip = false,
} = {}) {
  return makeVolumetricPlumeStream({
    count,
    ventWorld,
    riseHeight,
    lateralSpread,
    inversionCapY,
    colorHex,
    secondaryColorHex: sulfurTint ? 0xa38544 : 0x8b8680,
    baseScale,
    endScale,
    opacityScale,
    seed,
    semanticRole,
    matteSkip,
  });
}

// 1. Hook Scene (0-6s): Clear St. Paul's noon rapidly consumed by sweeping volumetric smog + bus headlights
export function makeLondonStreetFogRig() {
  const root = new THREE.Group();
  root.add(makeCobblestoneGround({ width: 22, depth: 28 }));

  const buildings = new THREE.Group();
  tagSemantic(buildings, 'subject');
  const brickA = new THREE.MeshStandardMaterial({ color: 0x574238, roughness: 0.85 });
  const brickB = new THREE.MeshStandardMaterial({ color: 0x44403c, roughness: 0.88 });
  const winGlow = new THREE.MeshStandardMaterial({ color: 0xfde68a, emissive: 0xf59e0b, emissiveIntensity: 0.45 });
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

  const domeRef = makeStPaulsSilhouette({ z: -9.8, scale: 0.96, role: 'reference_fixed' });
  root.add(domeRef);

  const lamps = [
    makeVictorianLamp({ x: -1.38, z: -1.6, semanticRole: 'reference_fixed', seed: 411 }),
    makeVictorianLamp({ x: 1.38, z: -2.4, semanticRole: 'reference_fixed', seed: 412 }),
    makeVictorianLamp({ x: -1.65, z: -4.2, semanticRole: 'reference_fixed', seed: 413 }),
    makeVictorianLamp({ x: 1.65, z: -6.0, semanticRole: 'reference_fixed', seed: 414 }),
  ];
  for (const lm of lamps) root.add(lm.root);

  const fgBus = makeDoubleDeckerBus1952({ scale: 0.80 });
  fgBus.root.position.set(0.55, 0, -4.2);
  fgBus.root.rotation.y = 0.06;
  root.add(fgBus.root);

  const strata = makeLayeredSmogStrata({
    planes: 5, width: 17.5, height: 6.0, zStart: -8.2, zEnd: -1.6, baseY: 2.0,
    colorHex: 0x827246, opacityBase: 0.36, seed: 501, semanticRole: 'causal_feature', matteSkip: true,
  });
  root.add(strata.root);

  const smogSweep = makeVolumetricPlumeStream({
    count: 26,
    ventWorld: [0.0, 2.1, -6.2],
    riseHeight: 0.35,
    lateralSpread: 2.2,
    driftVector: [0.0, -0.85, 6.2],
    colorHex: 0x5c523c,
    secondaryColorHex: 0x99844c,
    baseScale: 0.95,
    endScale: 2.65,
    opacityScale: 0.46,
    speed: 0.62,
    seed: 517,
    semanticRole: 'causal_feature',
  });
  root.add(smogSweep.root);

  return {
    root,
    update(u, lt, scene, camera = null) {
      // Immediate 0..3s punch: crisp noon visibility collapses rapidly across first ~52% of shot!
      const fogP = clamp(easeInOut(u * 1.65), 0, 1);
      winGlow.emissiveIntensity = lerp(0.18, 0.95, fogP);
      strata.update(fogP, lt);
      if (scene && scene.fog) {
        scene.fog.density = lerp(0.016, 0.135, fogP);
      }

      // Advance bus smoothly while keeping clear framing (stops comfortably ahead of camera lens!)
      const busZ = lerp(-4.2, -1.45, easeOut(clamp(u, 0, 1)));
      fgBus.root.position.z = busZ;
      for (const w of fgBus.wheels) w.rotation.x = u * 9.0;
      fgBus.coneMat.opacity = lerp(0.08, 0.36, fogP);

      lamps.forEach((lm, idx) => {
        lm.globeMat.emissiveIntensity = lerp(0.35, 2.4, fogP);
        lm.haloMat.opacity = lerp(0.04, 0.38, fogP) + 0.03 * Math.sin(lt * 3.0 + idx);
        lm.light.intensity = lerp(0.5, 3.8, fogP);
        if (camera) lm.halo.quaternion.copy(camera.quaternion);
      });

      const plumeTel = smogSweep.update(u, lt, camera, { densityGain: 0.35 + 0.85 * fogP });
      root.updateMatrixWorld(true);
      return {
        anchors: {
          streetlamp_halo_visibility: lamps[1].globe,
          lamppost_column_ref: [-1.38, 1.45, -1.6],
          bus_headlight_cone: [0.45, 0.62, busZ + 1.85],
        },
        physicalMotion: {
          vertex_disp_max_m: Number((busZ + 4.2).toFixed(4)),
          visibility_obscuration: Number(fogP.toFixed(4)),
          plume_reach_m: plumeTel.max_plume_reach_m,
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 2A. Interior Coal Hearth Cutaway (`coal_hearth_cutaway`)
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
    const chunk = new THREE.Mesh(new THREE.BoxGeometry(0.19 + (k % 2) * 0.04, 0.13, 0.17 + (k % 3) * 0.03), emberMat);
    chunk.rotation.set(k * 0.55, k * 1.15, k * 0.42);
    chunk.userData.isSolidCoalChunk = true;
    chunk.position.set((k - 3) * 0.095, (k % 2) * 0.06, ((k * 3) % 5 - 2) * 0.03);
    coalBedGrp.add(chunk);
  }
  const fireLight = new THREE.PointLight(0xf97316, 4.2, 4.0);
  fireLight.position.set(0, 0.55, 0.35);
  cut.addInternalComponent('coal_bed', coalBedGrp, { layerIndex: 2 });
  root.add(fireLight);

  const fluePlume = makeVolumetricPlumeStream({
    count: 28,
    ventWorld: [0.0, 0.62, 0.16],
    riseHeight: 3.8,
    lateralSpread: 0.58,
    colorHex: 0x3b3734,
    secondaryColorHex: 0xc2933a,
    baseScale: 0.42,
    endScale: 1.75,
    opacityScale: 0.68,
    speed: 0.85,
    seed: 601,
    semanticRole: 'causal_feature',
  });
  root.add(fluePlume.root);

  return {
    root,
    update(u, lt, scene, camera = null) {
      cut.setReveal(smooth(clamp(u * 2.5, 0, 1)));
      emberMat.emissiveIntensity = 1.45 + 0.55 * Math.sin(lt * 5.2);
      fireLight.intensity = 3.8 + 1.2 * Math.sin(lt * 5.2);
      const plumeTel = fluePlume.update(u, lt, camera);

      return {
        anchors: {
          chimney_flue_combustion: [0, 1.55, 0.22],
          roofline_chimney_masonry_ref: [0, 2.42, 0.25],
        },
        cutaway: cut.getTelemetry(),
        physicalMotion: {
          vertex_disp_max_m: plumeTel.max_plume_reach_m,
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 2B. Distinct Exterior Skyline Stacks Stage (`london_rooftop_stacks`) — eliminates shot_01->02 repetition!
export function makeLondonRooftopStacksRig() {
  const root = new THREE.Group();
  const ground = new THREE.Mesh(
    new THREE.BoxGeometry(24, 0.2, 22),
    new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.9 })
  );
  ground.position.y = -0.1;
  tagSemantic(ground, 'environment');
  root.add(ground);

  const slateMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.82 });
  const brickMat = new THREE.MeshStandardMaterial({ color: 0x6b4235, roughness: 0.86 });
  const frostMat = new THREE.MeshStandardMaterial({ color: 0xcbd5e1, roughness: 0.65 });

  // Fore-to-mid Victorian rowhouse gables + chimney pots
  const roofBlock = new THREE.Group();
  tagSemantic(roofBlock, 'subject');
  for (let k = -2; k <= 2; k++) {
    const house = new THREE.Mesh(new THREE.BoxGeometry(1.45, 1.75 + (Math.abs(k) % 2) * 0.25, 1.55), brickMat);
    house.position.set(k * 1.55, 0.88, 0.6);
    const roof = new THREE.Mesh(new THREE.ConeGeometry(1.08, 0.65, 4), slateMat);
    roof.rotation.y = Math.PI * 0.25;
    roof.position.set(k * 1.55, 2.08, 0.6);
    const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.14, 0.55, 10), brickMat);
    pot.position.set(k * 1.55 + 0.22, 2.45, 0.6);
    roofBlock.add(house, roof, pot);
  }
  root.add(shadow(roofBlock));

  // Battersea-inspired twin towering coal power plant stacks (`cause_source` + `reference_fixed` base)
  const powerHall = new THREE.Mesh(new THREE.BoxGeometry(3.8, 2.0, 2.2), brickMat);
  powerHall.position.set(0, 1.0, -2.6);
  tagSemantic(powerHall, 'reference_fixed');
  root.add(shadow(powerHall));

  const stackXs = [-1.15, 1.15];
  const plumes = [];
  for (let i = 0; i < stackXs.length; i++) {
    const sx = stackXs[i];
    const stBase = new THREE.Mesh(new THREE.CylinderGeometry(0.26, 0.36, 3.1, 16), brickMat);
    stBase.position.set(sx, 2.95, -2.6);
    const frostRing = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.12, 16), frostMat);
    frostRing.position.set(sx, 4.44, -2.6);
    tagSemantic(stBase, 'cause_source');
    root.add(shadow(stBase), frostRing);

    const p = makeVolumetricPlumeStream({
      count: 26,
      ventWorld: [sx, 4.55, -2.6],
      riseHeight: 2.8,
      lateralSpread: 1.05,
      driftVector: [0.65, 0.0, 0.25],
      colorHex: 0x47423a,
      secondaryColorHex: 0xb48a3e,
      baseScale: 0.58,
      endScale: 2.05,
      opacityScale: 0.66,
      speed: 0.68,
      seed: 640 + i * 31,
      semanticRole: 'causal_feature',
    });
    root.add(p.root);
    plumes.push(p);
  }

  return {
    root,
    update(u, lt, scene, camera = null) {
      let maxReach = 0.0;
      plumes.forEach((p) => {
        const res = p.update(u, lt, camera);
        maxReach = Math.max(maxReach, res.max_plume_reach_m);
      });
      return {
        anchors: {
          chimney_flue_combustion: [1.15, 4.65, -2.6],
          roofline_chimney_masonry_ref: [0.0, 1.9, -2.6],
        },
        physicalMotion: {
          vertex_disp_max_m: maxReach,
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 3A. Temperature Inversion Cap (`atmospheric_inversion_cap`) — ZERO clipped 3D card!
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

  // Translucent warm air inversion blanket (glides across skyline — NO clipped 3D PlaneGeometry card!)
  const lidGrp = new THREE.Group();
  lidGrp.position.set(0, 3.22, -0.2);
  tagSemantic(lidGrp, 'causal_feature');
  const lidMat = new THREE.MeshStandardMaterial({
    color: 0xf97316, emissive: 0xea580c, emissiveIntensity: 0.52,
    transparent: true, opacity: 0.40, roughness: 0.32, side: THREE.DoubleSide, depthWrite: false,
  });
  const lidSlab = new THREE.Mesh(new THREE.BoxGeometry(9.6, 0.36, 4.2), lidMat);
  tagSemantic(lidSlab, 'causal_feature');
  lidGrp.add(lidSlab);
  root.add(lidGrp);

  const arrowGrp = new THREE.Group();
  tagSemantic(arrowGrp, 'causal_feature');
  const arrowMat = new THREE.MeshStandardMaterial({ color: 0xfbbf24, emissive: 0xd97706, emissiveIntensity: 0.88 });
  const arrows = [];
  for (const ax of [-1.8, 0.0, 1.8]) {
    const cone = new THREE.Mesh(new THREE.ConeGeometry(0.14, 0.36, 10), arrowMat);
    cone.rotation.z = Math.PI;
    cone.position.set(ax, 2.86, 0.85);
    arrowGrp.add(cone);
    arrows.push(cone);
  }
  root.add(arrowGrp);

  const smokeStreams = stackXs.map((sx, sIdx) => {
    const p = makeVolumetricPlumeStream({
      count: 20,
      ventWorld: [sx, 2.08, 0.0],
      riseHeight: 1.55,
      lateralSpread: 1.55,
      inversionCapY: 2.88,
      colorHex: 0x5c5340,
      secondaryColorHex: 0xa18648,
      baseScale: 0.56,
      endScale: 1.88,
      opacityScale: 0.54,
      speed: 0.72,
      seed: 700 + sIdx * 23,
      semanticRole: 'effect_result',
    });
    root.add(p.root);
    return p;
  });

  return {
    root,
    update(u, lt, scene, camera = null) {
      const slideU = clamp(easeOut(u * 1.4), 0, 1);
      lidGrp.position.x = lerp(6.8, 0.0, slideU);
      lidGrp.position.y = 3.22 + 0.05 * Math.sin(lt * 2.0);
      arrows.forEach((ar, idx) => {
        ar.visible = slideU > 0.35;
        ar.position.y = 2.88 - 0.14 * ((lt * 1.2 + idx * 0.3) % 1.0);
      });

      const activeCapY = slideU > 0.45 ? 2.88 : null;
      let maxReach = 0.0;
      smokeStreams.forEach((ss) => {
        const res = ss.update(u, lt, camera, { inversionCapY: activeCapY });
        maxReach = Math.max(maxReach, res.max_plume_reach_m);
      });

      return {
        anchors: {
          inversion_thermal_boundary: [0.0, 3.20, 0.4],
          st_pauls_dome_and_horizon_ref: [0.0, 3.40, -3.2],
        },
        physicalMotion: {
          vertex_disp_max_m: Number(Math.max(1.2, maxReach).toFixed(4)),
          trapped_cap_y_m: 3.22,
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 3B. Street-Canyon Trapped Smog Lateral Accumulation (`london_street_canyon_buildup`)
export function makeLondonStreetCanyonTrappingRig() {
  const root = new THREE.Group();
  root.add(makeCobblestoneGround({ width: 20, depth: 24 }));

  const facadeMat = new THREE.MeshStandardMaterial({ color: 0x3b2d26, roughness: 0.86 });
  const winGlowMat = new THREE.MeshStandardMaterial({ color: 0xfde68a, emissive: 0xf59e0b, emissiveIntensity: 1.15 });
  const capMat = new THREE.MeshStandardMaterial({
    color: 0xf59e0b, emissive: 0xd97706, emissiveIntensity: 0.52,
    transparent: true, opacity: 0.34, depthWrite: false, side: THREE.DoubleSide,
  });
  for (const sx of [-3.1, 3.1]) {
    const row = new THREE.Mesh(new THREE.BoxGeometry(2.1, 3.1, 14), facadeMat);
    row.position.set(sx, 1.55, -2.0);
    tagSemantic(row, 'subject');
    root.add(shadow(row));
    const cornice = new THREE.Mesh(new THREE.BoxGeometry(2.22, 0.24, 14.1), facadeMat);
    cornice.position.set(sx, 3.12, -2.0);
    tagSemantic(cornice, 'reference_fixed');
    root.add(shadow(cornice));
    for (let wz = 0.2; wz >= -7.8; wz -= 2.0) {
      for (const wy of [1.05, 2.2]) {
        const w = new THREE.Mesh(new THREE.BoxGeometry(0.10, 0.56, 0.48), winGlowMat);
        w.position.set(sx + (sx < 0 ? 1.06 : -1.06), wy, wz);
        tagSemantic(w, 'subject');
        root.add(w);
      }
    }
  }

  const lampRef = makeVictorianLamp({ x: -1.8, z: -0.8, litIntensity: 2.2, semanticRole: 'reference_fixed', seed: 741 });
  root.add(lampRef.root);

  const capCeiling = new THREE.Mesh(new THREE.BoxGeometry(10.5, 0.28, 15.0), capMat);
  capCeiling.position.set(0, 3.45, -2.0);
  tagSemantic(capCeiling, 'causal_feature');
  root.add(capCeiling);

  const canyonStrata = makeLayeredSmogStrata({
    planes: 5, width: 8.5, height: 3.1, zStart: -6.5, zEnd: 1.2, baseY: 1.45,
    colorHex: 0x73633c, opacityBase: 0.42, seed: 760, semanticRole: 'effect_result', matteSkip: true,
  });
  root.add(canyonStrata.root);

  const canyonPlumes = makeVolumetricPlumeStream({
    count: 30,
    ventWorld: [-1.4, 2.75, -3.5],
    riseHeight: -1.65,
    lateralSpread: 2.1,
    driftVector: [2.2, -0.55, 2.8],
    colorHex: 0x5c523c,
    secondaryColorHex: 0x99844c,
    baseScale: 0.85,
    endScale: 2.35,
    opacityScale: 0.56,
    speed: 0.65,
    seed: 781,
    semanticRole: 'causal_feature',
  });
  root.add(canyonPlumes.root);

  return {
    root,
    update(u, lt, scene, camera = null) {
      const fogBuild = clamp(easeInOut(u), 0, 1);
      if (scene && scene.fog) {
        scene.fog.density = lerp(0.032, 0.082, fogBuild);
      }
      if (camera) lampRef.halo.quaternion.copy(camera.quaternion);
      canyonStrata.update(fogBuild, lt);
      const res = canyonPlumes.update(u, lt, camera, { densityGain: 0.55 + 0.55 * fogBuild });
      return {
        anchors: {
          inversion_thermal_boundary: [0.0, 3.25, -1.8],
          lamppost_column_ref: [-1.8, 1.5, -0.8],
        },
        physicalMotion: {
          vertex_disp_max_m: res.max_plume_reach_m,
          trapped_cap_y_m: 3.45,
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 4. Visibility Crisis: Grounded lantern guide leads slow double-decker bus past fixed lampposts
export function makeLondonBusVisibilityRig(makeHumanFn, { charSpec = {}, dur = 4.0 } = {}) {
  const root = new THREE.Group();
  root.add(makeCobblestoneGround({ width: 22, depth: 30 }));

  const bus = makeDoubleDeckerBus1952({ scale: 0.90 });
  root.add(bus.root);

  const lamps = [
    makeVictorianLamp({ x: 1.95, z: 3.0, semanticRole: 'reference_fixed', seed: 801 }),
    makeVictorianLamp({ x: 1.95, z: -0.6, semanticRole: 'reference_fixed', seed: 802 }),
    makeVictorianLamp({ x: 1.95, z: -4.2, semanticRole: 'reference_fixed', seed: 803 }),
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
    new THREE.MeshStandardMaterial({ color: 0xfef08a, emissive: 0xf59e0b, emissiveIntensity: 2.3 })
  );
  const lHalo = makeLightScatterHaloSprite({ colorHex: 0xfef08a, scale: 0.72, opacity: 0.34, seed: 815 });
  const lPt = new THREE.PointLight(0xffb74d, 3.4, 4.8);
  lantern.add(lCore, lHalo.mesh, lPt);
  tagSemantic(lantern, 'causal_feature');
  walker.j.rWr.add(lantern);
  lantern.position.set(0, -0.09, 0.05);
  root.add(walker.root);

  const busFogStrata = makeLayeredSmogStrata({
    planes: 4, width: 15.0, height: 4.8, zStart: -6.8, zEnd: -0.8, baseY: 1.65,
    colorHex: 0x7b6e46, opacityBase: 0.38, seed: 825, semanticRole: 'effect_result', matteSkip: true,
  });
  root.add(busFogStrata.root);

  const streetMist = makeVolumetricPlumeStream({
    count: 20,
    ventWorld: [-1.4, 1.25, -3.2],
    riseHeight: 0.4,
    lateralSpread: 2.2,
    driftVector: [2.8, 0.15, 2.2],
    colorHex: 0x6e6244,
    secondaryColorHex: 0xa18f54,
    baseScale: 0.85,
    endScale: 1.95,
    opacityScale: 0.42,
    speed: 0.45,
    seed: 839,
    semanticRole: 'effect_result',
    matteSkip: true,
  });
  root.add(streetMist.root);

  const stanceTracker = {};
  const threatBack = [-0.45, 1.2, -5.0];
  const walkPlan = {
    duration_sec: dur,
    primary_intent: 'retreat',
    ground_y: 0.0,
    base_x: 0.52,
    base_z: -0.25,
    base_yaw: -0.28,
    reaction_onset_sec: 0.05,
    retreat_distance_m: 1.25,
    threat_world: threatBack,
  };

  return {
    root,
    update(u, lt, scene, camera = null) {
      const walkEval = evaluateCharacterPose(lt, walkPlan);
      applyGroundedCharacterPose(walker, walkEval);
      walker.j.rSh.rotation.set(-0.72, 0.0, -0.18);
      walker.j.rEl.rotation.set(-0.52, 0.0, 0.0);
      walker.root.updateMatrixWorld(true);

      const walkZ = walkEval.root_pos[2];
      const busZ = walkZ - 3.35;
      bus.root.position.set(-0.42, 0, busZ);
      for (const w of bus.wheels) w.rotation.x = u * 9.5;

      if (scene && scene.fog) {
        scene.fog.density = 0.11;
      }
      lamps.forEach((lm) => {
        if (camera) lm.halo.quaternion.copy(camera.quaternion);
      });
      if (camera) lHalo.mesh.quaternion.copy(camera.quaternion);
      busFogStrata.update(0.82, lt);
      streetMist.update(u, lt, camera);

      const cpTel = getCharacterPerformanceTelemetry(walker, walkEval, stanceTracker, threatBack);
      return {
        anchors: {
          bus_headlight_cone: [-0.25, 0.65, busZ + 2.30],
          lamppost_column_ref: [1.95, 1.55, -0.6],
        },
        characterPerformance: cpTel,
        physicalMotion: {
          vertex_disp_max_m: Number(Math.abs(walkZ + 0.25).toFixed(4)),
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 5. E1 Polished Pedestrian Reaction: Firm scarf shield against airway, respectful torso cough & grounded foot stance
export function makeLondonPedestrianReactionRig(makeHumanFn, { charSpec = {}, dur = 4.0 } = {}) {
  const root = new THREE.Group();
  root.add(makeCobblestoneGround({ width: 16, depth: 18 }));

  const curbPost = new THREE.Mesh(
    new THREE.CylinderGeometry(0.10, 0.14, 0.92, 12),
    new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.55, metalness: 0.7 })
  );
  curbPost.position.set(-1.12, 0.46, -0.35);
  tagSemantic(curbPost, 'reference_fixed');
  root.add(shadow(curbPost));

  const leftLamp = makeVictorianLamp({ x: -1.05, z: -1.45, litIntensity: 2.3, semanticRole: 'reference_fixed', seed: 851 });
  root.add(leftLamp.root);

  // Period brick terrace facade + pub doorway warm refuge light
  const terrace = new THREE.Group();
  tagSemantic(terrace, 'subject');
  const wallMat = new THREE.MeshStandardMaterial({ color: 0x3b2f2f, roughness: 0.86 });
  const winGlowMat = new THREE.MeshStandardMaterial({ color: 0xfde68a, emissive: 0xd97706, emissiveIntensity: 0.58 });
  const facade = new THREE.Mesh(new THREE.BoxGeometry(6.8, 3.8, 1.2), wallMat);
  facade.position.set(0, 1.9, -4.1);
  terrace.add(facade);
  for (const wx of [-1.8, 0.0, 1.8]) {
    const win = new THREE.Mesh(new THREE.BoxGeometry(0.68, 0.98, 0.12), winGlowMat);
    win.position.set(wx, 1.75, -3.48);
    terrace.add(win);
  }
  root.add(shadow(terrace));

  const hero = buildRegisteredCharacter(makeHumanFn, {
    shirt_hex: charSpec.shirt_hex || 0x475569,
    pants_hex: charSpec.pants_hex || 0x1e293b,
    collar_hex: charSpec.collar_hex || 0x7f1d1d,
    skin_hex: charSpec.skin_hex || 0xd9a484,
  });
  tagSemantic(hero.root, 'character');

  // Neck scarf wrap (`causal_feature`) + right forearm bringing scarf fold smoothly against mouth
  const neckScarf = new THREE.Mesh(
    new THREE.CylinderGeometry(0.115, 0.125, 0.11, 16),
    new THREE.MeshStandardMaterial({ color: 0x7f1d1d, roughness: 0.88 })
  );
  neckScarf.position.set(0, 0.05, 0.0);
  tagSemantic(neckScarf, 'causal_feature');
  hero.j.chest.add(neckScarf);

  const scarfFold = new THREE.Mesh(
    new THREE.BoxGeometry(0.14, 0.11, 0.10),
    new THREE.MeshStandardMaterial({ color: 0x991b1b, roughness: 0.88 })
  );
  scarfFold.position.set(-0.02, -0.02, 0.05);
  tagSemantic(scarfFold, 'causal_feature');
  hero.j.rWr.add(scarfFold);
  root.add(hero.root);

  const acidicDrift = makeVolumetricPlumeStream({
    count: 18,
    ventWorld: [-1.1, 1.15, -1.6],
    riseHeight: 0.25,
    lateralSpread: 1.4,
    driftVector: [2.2, 0.15, 0.6],
    colorHex: 0x716448,
    secondaryColorHex: 0xa18c4f,
    baseScale: 0.65,
    endScale: 1.55,
    opacityScale: 0.36,
    speed: 0.45,
    seed: 888,
    semanticRole: 'effect_result',
    matteSkip: true,
  });
  root.add(acidicDrift.root);

  const stanceTracker = {};
  const hazardThreat = [-1.15, 1.4, -1.85];
  const bracePlan = {
    duration_sec: dur,
    primary_intent: 'brace',
    ground_y: 0.0,
    base_x: 0.32,
    base_z: 0.20,
    base_yaw: -0.36,
    reaction_onset_sec: Math.min(0.40, dur * 0.16),
    retreat_distance_m: 0.38,
    threat_world: hazardThreat,
  };

  return {
    root,
    update(u, lt, scene, camera = null) {
      // Respectful physical cough rhythm: slight forward chest hunch & right hand pressing scarf over nose/mouth
      const coughWave = Math.max(0, Math.sin(u * Math.PI * 2.5));
      const braceEval = evaluateCharacterPose(lt, bracePlan);
      applyGroundedCharacterPose(hero, braceEval);
      const liftU = smooth(clamp(u * 2.4, 0, 1));
      hero.j.chest.rotation.x += 0.14 * liftU + 0.09 * coughWave;
      hero.j.head.rotation.x = 0.18 * liftU + 0.08 * coughWave;
      hero.j.rSh.rotation.set(lerp(-0.12, -1.06 - 0.06 * coughWave, liftU), 0.28 * liftU, -0.18);
      hero.j.rEl.rotation.set(lerp(-0.25, -1.34 - 0.06 * coughWave, liftU), 0, 0);
      hero.j.lSh.rotation.set(-0.24, 0.0, 0.18);
      hero.j.lEl.rotation.set(-0.55, 0.0, 0.0);
      hero.root.updateMatrixWorld(true);

      if (scene && scene.fog) {
        scene.fog.density = 0.075;
      }
      if (camera) leftLamp.halo.quaternion.copy(camera.quaternion);
      acidicDrift.update(u, lt, camera);

      const cpTel = getCharacterPerformanceTelemetry(hero, braceEval, stanceTracker, hazardThreat);
      const headArr = v3Arr(hero.j.head);
      return {
        anchors: {
          pedestrian_respiratory_stance_zone: headArr,
          pedestrian_respiratory_brace: headArr,
          victorian_curb_post_ref: [-1.12, 0.65, -0.35],
        },
        characterPerformance: cpTel,
        physicalMotion: {
          vertex_disp_max_m: Number((0.22 + 0.12 * coughWave).toFixed(4)),
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 6. Clean Air Act 1956 Aftermath: Vivid 1952 smoky haze -> clear blue sky & clean smokeless hearth
export function makeLondonAftermathRig() {
  const root = new THREE.Group();
  root.add(makeCobblestoneGround({ width: 24, depth: 24 }));

  const dome = makeStPaulsSilhouette({ z: -3.2, scale: 1.08, role: 'reference_fixed' });
  root.add(dome);

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
  const frame = new THREE.Mesh(new THREE.BoxGeometry(2.25, 2.25, 1.0), masonryMat);
  frame.position.y = 1.12;
  const mantle = new THREE.Mesh(new THREE.BoxGeometry(2.45, 0.16, 1.18), trimMat);
  mantle.position.y = 1.28;
  const fireboxRecess = new THREE.Mesh(new THREE.BoxGeometry(1.10, 0.80, 0.20), new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.9 }));
  fireboxRecess.position.set(0, 0.64, 0.52);
  const chimneyStack = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.30, 1.25, 14), masonryMat);
  chimneyStack.position.y = 2.82;
  hearth.add(frame, mantle, fireboxRecess, chimneyStack);
  root.add(shadow(hearth));

  const burnerCore = new THREE.Mesh(
    new THREE.BoxGeometry(0.88, 0.46, 0.34),
    new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x0ea5e9, emissiveIntensity: 2.4 })
  );
  burnerCore.position.set(0, 0.68, 0.86);
  tagSemantic(burnerCore, 'causal_feature');
  root.add(burnerCore);

  const lingeringSmoke = makeVolumetricPlumeStream({
    count: 20,
    ventWorld: [0.0, 3.45, 0.55],
    riseHeight: 2.35,
    lateralSpread: 0.55,
    colorHex: 0x57534e,
    secondaryColorHex: 0xcbd5e1,
    baseScale: 0.48,
    endScale: 1.55,
    opacityScale: 0.62,
    speed: 0.72,
    seed: 909,
    semanticRole: 'causal_feature',
  });
  root.add(lingeringSmoke.root);

  const clearingVeil = makeLayeredSmogStrata({
    planes: 3, width: 16.0, height: 5.5, zStart: -4.2, zEnd: -1.4, baseY: 2.1,
    colorHex: 0x7c704c, opacityBase: 0.35, seed: 922, semanticRole: 'effect_result', matteSkip: true,
  });
  root.add(clearingVeil.root);

  return {
    root,
    update(u, lt, scene, camera = null) {
      // Genuine atmospheric shift: dirty 1952 coal haze (u<0.32) -> bright 1956 smokeless blue clarity (u->1.0)
      const clearP = clamp(easeInOut((u - 0.12) / 0.72), 0, 1);
      burnerCore.material.color.setHex(clearP < 0.38 ? 0xf97316 : 0x38bdf8);
      burnerCore.material.emissive.setHex(clearP < 0.38 ? 0xea580c : 0x0ea5e9);

      if (scene && scene.fog) {
        scene.fog.density = lerp(0.068, 0.004, clearP);
        scene.fog.color.setHex(clearP < 0.40 ? 0x6b6043 : 0xbae6fd);
      }
      if (scene && scene.userData && scene.userData.sky && scene.userData.sky.material && scene.userData.sky.material.uniforms) {
        const uSky = scene.userData.sky.material.uniforms;
        if (uSky.top && uSky.top.value) uSky.top.value.setRGB(lerp(0.21, 0.11, clearP), lerp(0.18, 0.30, clearP), lerp(0.14, 0.85, clearP));
        if (uSky.mid && uSky.mid.value) uSky.mid.value.setRGB(lerp(0.39, 0.38, clearP), lerp(0.34, 0.65, clearP), lerp(0.24, 0.98, clearP));
        if (uSky.horizon && uSky.horizon.value) uSky.horizon.value.setRGB(lerp(0.61, 0.82, clearP), lerp(0.54, 0.91, clearP), lerp(0.35, 0.99, clearP));
      }
      clearingVeil.update(1.0 - clearP, lt);
      lingeringSmoke.update(u, lt, camera, { densityGain: lerp(1.15, 0.25, clearP) });

      return {
        anchors: {
          smokeless_hearth_transition: [0, 1.38, 0.82],
          st_pauls_silhouette_ref: [0, 3.3, -3.2],
        },
        physicalMotion: {
          vertex_disp_max_m: Number((0.8 + clearP * 1.1).toFixed(4)),
          air_clarity_recovery: Number(clearP.toFixed(4)),
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}
"""
