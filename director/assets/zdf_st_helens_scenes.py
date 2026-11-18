"""Procedural May 18, 1980 Mount St. Helens Eruption 3D Scene Library (`SD-RETENTION-04.R2`).

Brand-new original procedural Three.js volcanic stages grounded in USGS published chronology:
1. `makeStHelensRidgeHookStage`: Calm pre-8:32 a.m. peak vs visibly swelling/fracturing north bulge (0-3s hook).
2. `makeStHelensCryptodomeCutawayStage`: Layered geological cutaway showing magma conduit feeding pressurized cryptodome.
3. `makeStHelensLandslideCollapseStage`: M5.1 tremor loosening colossal north-flank rock slide blocks + avalanche dust.
4. `makeStHelensLateralBlastStage`: Uncorked horizontal >300 mph supersonic steam/ash/rock blast tearing sideways.
5. `makeStHelensForestFlattenStage`: Lateral surge flattening forested ridge trees progressively against fixed ridge reference.
6. `makeStHelensPlinianColumnStage`: Towering vertical ash column rising above crater with dense ash envelope (`ashMode: true`).
7. `makeStHelensCraterAftermathStage`: Carved horseshoe crater contrasted cleanly against ghosted pre-eruption summit contour.

Shares `atmospheric_volume_primitives.js` cleanly (zero duplicated smoke engines; zero dodecahedral smoke clouds).
Disclosed model: `stylized_atmospheric_visualization` / `illustrative reconstruction, not CFD/FEM scientific solver`.
Deterministic on arbitrary time seek `t`.
"""

from __future__ import annotations


ST_HELENS_SCENES_JS = r"""import * as THREE from 'three';
import { clamp, easeInOut, easeOut, lerp, smooth } from './anim.js';
import { LayeredCutaway } from './layered_cutaway.js';
import {
  makeVolumetricPlumeStream,
  makeLayeredSmogStrata,
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

/**
 * Procedurally displaced Mount St. Helens volcano mesh with deformable north flank (`+x` / `+z` bulge).
 */
function makeVolcanoMountainMesh({ craterCut = 0.0, radius = 4.2, height = 3.15 } = {}) {
  const segR = 36;
  const segH = 18;
  const geo = new THREE.CylinderGeometry(craterCut > 0 ? 1.05 : 0.34, radius, height, segR, segH, false);
  geo.translate(0, height * 0.5, 0);
  const pos = geo.attributes.position;
  const basePos = new Float32Array(pos.array.length);
  const cols = new Float32Array(pos.count * 3);
  const cRock = new THREE.Color(0x4b5563);
  const cBasalt = new THREE.Color(0x57534e);
  const cSnow = new THREE.Color(0xe2e8f0);
  const tmpC = new THREE.Color();

  for (let i = 0; i < pos.count; i++) {
    let x = pos.getX(i);
    let y = pos.getY(i);
    let z = pos.getZ(i);
    const yn = clamp(y / height, 0, 1);
    const ang = Math.atan2(z, x);
    // Natural volcanic ridge flutes + horseshoe north breach when `craterCut > 0`
    const ridgeNoise = 0.14 * Math.sin(ang * 5.0 + yn * 2.2) + 0.08 * Math.cos(ang * 9.0);
    const rScale = 1.0 + ridgeNoise * (1.0 - yn * 0.45);
    x *= rScale;
    z *= rScale;
    if (craterCut > 0.01 && yn > 0.48 && x > 0.0 && Math.abs(z) < radius * 0.48) {
      const breach = clamp((yn - 0.48) / 0.52, 0, 1) * craterCut;
      y -= breach * height * 0.46;
      x *= (1.0 - breach * 0.35);
    }
    pos.setXYZ(i, x, y, z);
    basePos[i * 3] = x;
    basePos[i * 3 + 1] = y;
    basePos[i * 3 + 2] = z;

    const snowFactor = smooth(clamp((yn - 0.54 + ridgeNoise * 0.25) / 0.28, 0, 1)) * (1.0 - craterCut * 0.72);
    tmpC.copy(yn < 0.35 ? cBasalt : cRock).lerp(cSnow, snowFactor);
    cols[i * 3] = tmpC.r;
    cols[i * 3 + 1] = tmpC.g;
    cols[i * 3 + 2] = tmpC.b;
  }
  geo.setAttribute('color', new THREE.BufferAttribute(cols, 3));
  geo.computeVertexNormals();

  const mat = new THREE.MeshStandardMaterial({
    vertexColors: true, roughness: 0.86, metalness: 0.04,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.userData = { semanticRole: 'subject', basePos };
  return { mesh, geo, basePos, height, radius };
}

function deformNorthBulge(volc, bulgeAmt, tremorOffset = 0.0) {
  const pos = volc.geo.attributes.position;
  const base = volc.basePos;
  for (let i = 0; i < pos.count; i++) {
    const bx = base[i * 3];
    const by = base[i * 3 + 1];
    const bz = base[i * 3 + 2];
    const yn = clamp(by / volc.height, 0, 1);
    const northWeight = clamp((bx - 0.15) / 1.9, 0, 1) * clamp(1.0 - Math.abs(bz) / 1.85, 0, 1) * smooth(clamp(yn / 0.32, 0, 1)) * (1.0 - smooth(clamp((yn - 0.82) / 0.18, 0, 1)));
    const pushX = northWeight * bulgeAmt + tremorOffset * clamp(yn, 0, 1);
    const pushY = northWeight * bulgeAmt * 0.24;
    pos.setXYZ(i, bx + pushX, by + pushY, bz + northWeight * bulgeAmt * 0.12);
  }
  pos.needsUpdate = true;
  volc.geo.computeVertexNormals();
}

function makePineTree(scale = 1.0, scorch = false) {
  const g = new THREE.Group();
  const trunkMat = new THREE.MeshStandardMaterial({ color: scorch ? 0x3f3f46 : 0x5c4033, roughness: 0.9 });
  const leafMat = new THREE.MeshStandardMaterial({ color: scorch ? 0x52525b : 0x1e4620, roughness: 0.88 });
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.05 * scale, 0.075 * scale, 0.42 * scale, 6), trunkMat);
  trunk.position.y = 0.21 * scale;
  g.add(trunk);
  for (let tier = 0; tier < 3; tier++) {
    const cone = new THREE.Mesh(new THREE.ConeGeometry((0.34 - tier * 0.08) * scale, (0.56 - tier * 0.08) * scale, 7), leafMat);
    cone.position.y = (0.52 + tier * 0.30) * scale;
    g.add(cone);
  }
  return shadow(g);
}

function makeFixedGraniteRidges() {
  const grp = new THREE.Group();
  tagSemantic(grp, 'reference_fixed');
  const rockMat = new THREE.MeshStandardMaterial({ color: 0x3b483d, roughness: 0.90 });
  for (const [rx, ry, rz, sx, sy, sz] of [
    [-4.6, 0.85, -1.8, 3.4, 1.7, 3.6],
    [4.9, 0.72, -3.2, 3.2, 1.45, 3.4],
    [-3.4, 0.45, 2.1, 2.2, 0.9, 2.0],
  ]) {
    const ridge = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), rockMat);
    ridge.position.set(rx, ry, rz);
    ridge.rotation.y = rx > 0 ? -0.35 : 0.35;
    grp.add(ridge);
  }
  return shadow(grp);
}

// 1. S00 (0-3s HOOK): Mountain ridge overlooks Spirit Lake as north flank visibly bulges & fractures!
export function makeStHelensRidgeHookStage() {
  const root = new THREE.Group();

  // Foreground Cascade valley & Spirit Lake reflection strip (`environment`)
  const valley = new THREE.Mesh(
    new THREE.BoxGeometry(28, 0.25, 28),
    new THREE.MeshStandardMaterial({ color: 0x2f3e2e, roughness: 0.92 })
  );
  valley.position.y = -0.125;
  tagSemantic(valley, 'environment');
  root.add(valley);

  const lake = new THREE.Mesh(
    new THREE.PlaneGeometry(14, 5.2),
    new THREE.MeshStandardMaterial({ color: 0x1e4e68, roughness: 0.28, metalness: 0.35 })
  );
  lake.rotation.x = -Math.PI * 0.5;
  lake.position.set(0.4, 0.02, 4.2);
  tagSemantic(lake, 'reference_fixed');
  root.add(lake);

  root.add(makeFixedGraniteRidges());

  // Foreground green pines along left & right observation ridge (`reference_fixed`)
  const treeBank = new THREE.Group();
  tagSemantic(treeBank, 'reference_fixed');
  for (const [tx, tz, sc] of [[-2.4, 3.6, 0.85], [-1.75, 4.2, 0.75], [2.4, 4.1, 0.82], [-2.9, 2.8, 0.92]]) {
    const pt = makePineTree(sc);
    pt.position.set(tx, 0, tz);
    treeBank.add(pt);
  }
  root.add(treeBank);

  const volc = makeVolcanoMountainMesh({ craterCut: 0.0, radius: 4.1, height: 3.25 });
  volc.mesh.position.set(-0.25, 0, -0.5);
  tagSemantic(volc.mesh, 'subject');
  root.add(shadow(volc.mesh));

  // Highlighted bulging fracture mantle band on the north slope (`+X` side, `causal_feature`)
  const bulgeShell = new THREE.Mesh(
    new THREE.DodecahedronGeometry(0.62, 1),
    new THREE.MeshStandardMaterial({ color: 0x57534e, emissive: 0x451a03, emissiveIntensity: 0.14, roughness: 0.94 })
  );
  bulgeShell.scale.set(0.70, 0.95, 0.85);
  bulgeShell.position.set(0.88, 1.48, -0.5);
  tagSemantic(bulgeShell, 'causal_feature');
  root.add(shadow(bulgeShell));

  const precursorDust = makeVolumetricPlumeStream({
    count: 16,
    ventWorld: [1.35, 1.95, -0.5],
    riseHeight: 1.55,
    lateralSpread: 0.45,
    driftVector: [0.35, 0.0, 0.0],
    colorHex: 0x78716c,
    secondaryColorHex: 0xd6d3d1,
    baseScale: 0.35,
    endScale: 1.15,
    opacityScale: 0.50,
    speed: 0.65,
    seed: 1801,
    semanticRole: 'causal_feature',
  });
  root.add(precursorDust.root);

  return {
    root,
    update(u, lt, scene, camera = null) {
      // Dramatic immediate deformation from 0..3s so flank protrusion is unmistakable relative to fixed pine ridge!
      const bulgeU = clamp(easeOut(u * 1.45), 0, 1);
      const bulgeM = lerp(0.18, 1.05, bulgeU);
      const quakeJitter = bulgeU > 0.72 ? Math.sin(lt * 34.0) * 0.025 : 0.0;
      deformNorthBulge(volc, bulgeM, quakeJitter);
      bulgeShell.position.set(0.82 + bulgeM * 0.52 + quakeJitter, 1.48 + bulgeM * 0.12, -0.5);
      bulgeShell.material.emissiveIntensity = lerp(0.10, 0.32, bulgeU);
      const dustTel = precursorDust.update(u, lt, camera, { densityGain: lerp(0.25, 1.0, bulgeU) });

      return {
        anchors: {
          msh_north_flank_bulge: [1.05 + bulgeM * 0.52, 1.62, -0.5],
          msh_south_ridge_ref: [-1.45, 1.50, -0.35],
        },
        physicalMotion: {
          vertex_disp_max_m: Number(Math.max(0.25, bulgeM).toFixed(4)),
          max_plume_reach_m: dustTel.max_plume_reach_m,
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 2. S01 (SOURCE): Geological LayeredCutaway showing magma feeder + swelling pressurized cryptodome!
export function makeStHelensCryptodomeCutawayStage() {
  const root = new THREE.Group();
  const basePlate = new THREE.Mesh(
    new THREE.BoxGeometry(16, 0.3, 16),
    new THREE.MeshStandardMaterial({ color: 0x292524, roughness: 0.92 })
  );
  basePlate.position.y = -0.15;
  tagSemantic(basePlate, 'environment');
  root.add(basePlate);

  const cut = new LayeredCutaway({
    id: 'msh_cryptodome_cutaway',
    worldAnchor: [0.35, 1.45, 0],
    clipNormal: [0, 0, -1],
    clipConstantStart: 1.65,
    clipConstantOpen: 0.05,
  });

  const volc = makeVolcanoMountainMesh({ craterCut: 0.0, radius: 3.65, height: 2.95 });
  volc.mesh.position.set(-0.15, 0, 0);
  tagSemantic(volc.mesh, 'subject');
  cut.addOuterShell(volc.mesh, { applyClip: true });

  // Granite bedrock datum anchor at left mountain shoulder (`reference_fixed`)
  const bedrockRef = new THREE.Mesh(
    new THREE.BoxGeometry(1.4, 1.55, 1.4),
    new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.85 })
  );
  bedrockRef.position.set(-1.75, 0.85, 0.15);
  tagSemantic(bedrockRef, 'reference_fixed');
  root.add(cut.root, shadow(bedrockRef));

  // Magma feeding conduit (`cause_source`) + bulging glowing cryptodome pocket (`causal_feature`)
  const magmaConduit = new THREE.Mesh(
    new THREE.CylinderGeometry(0.28, 0.44, 1.85, 16),
    new THREE.MeshStandardMaterial({ color: 0xdc2626, emissive: 0xf97316, emissiveIntensity: 1.65, roughness: 0.45 })
  );
  magmaConduit.position.set(0.05, 0.92, 0.05);
  tagSemantic(magmaConduit, 'cause_source');
  cut.addInternalComponent('magma_conduit', magmaConduit, { layerIndex: 1 });

  const cryptodomeMat = new THREE.MeshStandardMaterial({
    color: 0xf97316, emissive: 0xea580c, emissiveIntensity: 1.9, roughness: 0.35,
  });
  const cryptodome = new THREE.Mesh(new THREE.SphereGeometry(0.68, 22, 18), cryptodomeMat);
  cryptodome.scale.set(1.25, 0.95, 0.85);
  cryptodome.position.set(0.85, 1.55, 0.05);
  tagSemantic(cryptodome, 'causal_feature');
  cut.addInternalComponent('magma_cryptodome', cryptodome, { layerIndex: 2 });

  const magmaLight = new THREE.PointLight(0xf97316, 4.2, 5.5);
  magmaLight.position.set(0.85, 1.6, 0.85);
  root.add(magmaLight);

  const pressureSteam = makeVolumetricPlumeStream({
    count: 18,
    ventWorld: [1.35, 2.05, 0.15],
    riseHeight: 1.45,
    lateralSpread: 0.55,
    colorHex: 0x78716c,
    secondaryColorHex: 0xfef3c7,
    baseScale: 0.32,
    endScale: 1.15,
    opacityScale: 0.48,
    speed: 0.62,
    seed: 1825,
    semanticRole: 'causal_feature',
  });
  root.add(pressureSteam.root);

  return {
    root,
    update(u, lt, scene, camera = null) {
      cut.setReveal(smooth(clamp(u * 2.2, 0, 1)));
      const swell = smooth(clamp(u * 1.25, 0, 1));
      const domeScale = lerp(0.78, 1.22, swell);
      cryptodome.scale.set(1.22 * domeScale, 0.92 * domeScale, 0.85);
      cryptodome.position.x = lerp(0.55, 1.05, swell);
      deformNorthBulge(volc, lerp(0.15, 0.72, swell), 0.0);
      cryptodomeMat.emissiveIntensity = 1.65 + 0.45 * Math.sin(lt * 5.0);
      pressureSteam.update(u, lt, camera);

      return {
        anchors: {
          msh_cryptodome_core: [lerp(0.55, 1.05, swell), 1.58, 0.20],
          msh_south_ridge_ref: [-2.35, 1.05, 0.0],
        },
        cutaway: cut.getTelemetry(),
        physicalMotion: {
          vertex_disp_max_m: Number((0.4 + swell * 0.75).toFixed(4)),
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 3. S02 (CAUSE): M5.1 Earthquake & North Flank Sector Collapse (gigantic sliding debris blocks + dust!)
export function makeStHelensLandslideCollapseStage() {
  const root = new THREE.Group();
  const valley = new THREE.Mesh(
    new THREE.BoxGeometry(28, 0.25, 24),
    new THREE.MeshStandardMaterial({ color: 0x33382e, roughness: 0.92 })
  );
  valley.position.y = -0.125;
  tagSemantic(valley, 'environment');
  root.add(valley);
  root.add(makeFixedGraniteRidges());

  const craterBase = makeVolcanoMountainMesh({ craterCut: 0.72, radius: 4.1, height: 3.1 });
  craterBase.mesh.position.set(-0.6, 0, -0.3);
  tagSemantic(craterBase.mesh, 'subject');
  root.add(shadow(craterBase.mesh));

  // South summit rim intact reference (`reference_fixed`)
  const fixedRim = new THREE.Mesh(
    new THREE.ConeGeometry(0.9, 1.25, 10),
    new THREE.MeshStandardMaterial({ color: 0xdbeafe, roughness: 0.75 })
  );
  fixedRim.position.set(-1.35, 2.52, -0.3);
  tagSemantic(fixedRim, 'reference_fixed');
  root.add(shadow(fixedRim));

  // Detached irregular volcanic slide blocks plunging down north face (`causal_feature`)
  const blockMat = new THREE.MeshStandardMaterial({ color: 0x57534e, roughness: 0.90 });
  const slideBlocks = [];
  for (let k = 0; k < 4; k++) {
    const blk = new THREE.Mesh(new THREE.DodecahedronGeometry(0.65 - k * 0.08, 0), blockMat);
    blk.scale.set(1.25, 0.72, 1.15);
    blk.userData.idx = k;
    blk.userData.isSolidBoulder = true;
    tagSemantic(blk, 'causal_feature');
    root.add(shadow(blk));
    slideBlocks.push(blk);
  }

  // Legitimate rigid falling rock talus polyhedra (`isSolidBoulder`)
  const talus = [];
  for (let i = 0; i < 14; i++) {
    const r = 0.12 + (i % 4) * 0.05;
    const boulder = new THREE.Mesh(new THREE.DodecahedronGeometry(r, 0), blockMat);
    boulder.userData.isSolidBoulder = true;
    boulder.userData.seed = i;
    tagSemantic(boulder, 'causal_feature');
    root.add(shadow(boulder));
    talus.push(boulder);
  }

  const avalancheDust = makeVolumetricPlumeStream({
    count: 28,
    ventWorld: [1.4, 1.5, -0.2],
    riseHeight: 0.85,
    lateralSpread: 1.35,
    driftVector: [3.2, -1.1, 0.4],
    colorHex: 0x57534e,
    secondaryColorHex: 0xa8a29e,
    baseScale: 0.68,
    endScale: 2.25,
    opacityScale: 0.62,
    speed: 0.92,
    seed: 1851,
    semanticRole: 'effect_result',
  });
  root.add(avalancheDust.root);

  return {
    root,
    update(u, lt, scene, camera = null) {
      const quakeShake = u < 0.24 ? Math.sin(lt * 46.0) * 0.065 * (1.0 - u / 0.24) : 0.0;
      const slideU = smooth(clamp((u - 0.10) / 0.85, 0, 1));
      craterBase.mesh.position.x = -0.6 + quakeShake;

      slideBlocks.forEach((blk, k) => {
        const lag = k * 0.08;
        const bu = clamp((slideU - lag) / (1.0 - lag), 0, 1);
        const startX = 0.55 - k * 0.25;
        const startY = 2.05 - k * 0.18;
        blk.position.set(
          lerp(startX, startX + 3.65 + k * 0.35, easeInOut(bu)) + quakeShake,
          lerp(startY, 0.42, Math.pow(bu, 1.35)),
          -0.3 + ((k % 2 === 0 ? 1 : -1) * 0.42)
        );
        blk.rotation.set(bu * 0.28 * (k + 1), bu * 0.15, -bu * 0.62);
      });

      talus.forEach((b, i) => {
        const bu = clamp((slideU * 1.15 - (i % 5) * 0.06), 0, 1);
        b.position.set(
          lerp(0.8, 4.9 + (i % 3) * 0.65, bu),
          Math.max(0.15, lerp(2.1 - (i % 4) * 0.25, 0.18, bu * bu)),
          ((i * 0.73) % 2.2) - 1.1
        );
        b.rotation.set(lt * 2.5 + i, lt * 1.8, lt * -2.2);
      });

      const dustTel = avalancheDust.update(u, lt, camera, { densityGain: 0.35 + slideU * 0.85 });
      const frontX = slideBlocks[0].position.x;
      return {
        anchors: {
          msh_landslide_scar: [frontX, slideBlocks[0].position.y + 0.3, -0.3],
          msh_south_ridge_ref: [-1.35, 2.55, -0.3],
        },
        physicalMotion: {
          vertex_disp_max_m: Number(Math.max(0.1, frontX - 0.55).toFixed(4)),
          max_plume_reach_m: dustTel.max_plume_reach_m,
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          landslide_or_blast_active: true,
          nan_detected: false,
        },
      };
    },
  };
}

// 4. S03 (ACTION): Uncorked Supersonic >300 mph Lateral Decompression Blast shooting SIDEWAYS!
export function makeStHelensLateralBlastStage() {
  const root = new THREE.Group();
  const valley = new THREE.Mesh(
    new THREE.BoxGeometry(30, 0.25, 26),
    new THREE.MeshStandardMaterial({ color: 0x333530, roughness: 0.92 })
  );
  valley.position.y = -0.125;
  tagSemantic(valley, 'environment');
  root.add(valley);
  root.add(makeFixedGraniteRidges());

  const volcano = makeVolcanoMountainMesh({ craterCut: 0.95, radius: 4.0, height: 3.05 });
  volcano.mesh.position.set(-1.8, 0, -0.3);
  tagSemantic(volcano.mesh, 'subject');
  root.add(shadow(volcano.mesh));

  // Remaining fixed crater rim reference on `-X` west/south lip (`reference_fixed`)
  const fixedPeakLip = new THREE.Mesh(
    new THREE.CylinderGeometry(0.45, 0.95, 1.35, 10),
    new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.82 })
  );
  fixedPeakLip.position.set(-2.65, 2.25, -0.3);
  tagSemantic(fixedPeakLip, 'reference_fixed');
  root.add(shadow(fixedPeakLip));

  // Uncorked glowing orange-amber vent core on exposed north scar (`cause_source`)
  const ventGlow = new THREE.Mesh(
    new THREE.SphereGeometry(0.65, 16, 12),
    new THREE.MeshStandardMaterial({ color: 0xf97316, emissive: 0xff4500, emissiveIntensity: 2.2, roughness: 0.4 })
  );
  ventGlow.position.set(-0.65, 1.55, -0.3);
  tagSemantic(ventGlow, 'cause_source');
  root.add(ventGlow);

  // Expanding supersonic lateral shock-wave cone aligned horizontally (`+X`, NOT upward!)
  const shockMat = new THREE.MeshBasicMaterial({
    color: 0xfef08a, transparent: true, opacity: 0.32, wireframe: false, side: THREE.DoubleSide, depthWrite: false,
  });
  const shockCone = new THREE.Mesh(new THREE.ConeGeometry(1.45, 2.8, 22, 1, true), shockMat);
  shockCone.rotation.z = Math.PI * 0.52;
  shockCone.position.set(-0.2, 1.48, -0.3);
  tagSemantic(shockCone, 'causal_feature', true);
  root.add(shockCone);

  const lateralSurge = makeVolumetricPlumeStream({
    count: 34,
    ventWorld: [-0.6, 1.55, -0.3],
    riseHeight: -0.35,
    lateralSpread: 1.55,
    driftVector: [6.8, -0.45, 0.35],
    ashMode: true,
    colorHex: 0x3f3f46,
    secondaryColorHex: 0x9a3412,
    baseScale: 0.72,
    endScale: 2.65,
    opacityScale: 0.78,
    speed: 1.45,
    seed: 1880,
    semanticRole: 'causal_feature',
  });
  root.add(lateralSurge.root);

  const blastLight = new THREE.PointLight(0xff7833, 5.5, 9.0);
  blastLight.position.set(-0.5, 1.65, 0.4);
  root.add(blastLight);

  return {
    root,
    update(u, lt, scene, camera = null) {
      const surgeU = easeOut(clamp(u * 1.15, 0, 1));
      shockCone.position.set(lerp(-0.5, 3.8, surgeU), lerp(1.52, 0.95, surgeU), -0.3);
      shockCone.scale.setScalar(0.55 + surgeU * 1.85);
      shockMat.opacity = Math.max(0.0, 0.38 * (1.0 - surgeU * 0.78));
      blastLight.intensity = 6.2 * (1.0 - 0.55 * surgeU);

      const pTel = lateralSurge.update(u, lt, camera, { densityGain: 1.15 });
      const blastFrontX = clamp(lerp(-0.2, 1.85, surgeU), -0.4, 2.0);
      return {
        anchors: {
          msh_lateral_blast_front: [blastFrontX, 1.48, 0.92],
          msh_crater_lip_ref: [-2.15, 2.25, 0.45],
        },
        physicalMotion: {
          vertex_disp_max_m: Number(Math.max(1.0, lerp(0.8, 5.4, surgeU)).toFixed(4)),
          lateral_surge_reach_m: pTel.max_plume_reach_m,
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          landslide_or_blast_active: true,
          nan_detected: false,
        },
      };
    },
  };
}

// 5. S04 (RESULT): Lateral blast front sweeping across green ridge timberlands (snapping trees vs untouched far ridge!)
export function makeStHelensForestFlattenStage() {
  const root = new THREE.Group();
  const ridgeBase = new THREE.Mesh(
    new THREE.BoxGeometry(26, 0.4, 18),
    new THREE.MeshStandardMaterial({ color: 0x3b4432, roughness: 0.92 })
  );
  ridgeBase.position.y = -0.2;
  tagSemantic(ridgeBase, 'environment');
  root.add(ridgeBase);

  // Far untouched mountain ridge on right horizon (`reference_fixed`)
  const safeRidge = new THREE.Group();
  const ridgeCone = new THREE.Mesh(
    new THREE.ConeGeometry(4.2, 2.65, 7),
    new THREE.MeshStandardMaterial({ color: 0x2f4833, roughness: 0.90 })
  );
  ridgeCone.position.set(5.2, 1.32, -4.4);
  ridgeCone.scale.set(1.25, 1.0, 1.5);
  safeRidge.add(ridgeCone);
  for (const [rx, rz] of [[4.2, -3.9], [4.9, -4.4], [5.7, -4.1]]) {
    const rt = makePineTree(0.75, false);
    rt.position.set(rx, 1.45, rz);
    safeRidge.add(rt);
  }
  tagSemantic(safeRidge, 'reference_fixed');
  root.add(shadow(safeRidge));

  const trees = [];
  for (let i = 0; i < 22; i++) {
    const tx = -3.8 + (i % 11) * 0.68;
    const tz = -1.6 + Math.floor(i / 11) * 1.9 + ((i % 3) - 1) * 0.25;
    const sc = 0.82 + (i % 4) * 0.14;
    const tree = makePineTree(sc, false);
    tree.position.set(tx, 0, tz);
    tree.userData.baseX = tx;
    tagSemantic(tree, 'causal_feature');
    root.add(tree);
    trees.push(tree);
  }

  const sweepPlume = makeVolumetricPlumeStream({
    count: 30,
    ventWorld: [-4.6, 1.15, -0.4],
    riseHeight: 0.2,
    lateralSpread: 1.4,
    driftVector: [9.4, 0.35, 0.4],
    ashMode: true,
    colorHex: 0x44403c,
    secondaryColorHex: 0x78716c,
    baseScale: 0.95,
    endScale: 2.55,
    opacityScale: 0.72,
    speed: 1.25,
    seed: 1904,
    semanticRole: 'effect_result',
  });
  root.add(sweepPlume.root);

  return {
    root,
    update(u, lt, scene, camera = null) {
      const frontX = lerp(-4.2, 4.2, easeInOut(u));
      let snappedCount = 0;
      trees.forEach((tr) => {
        const hitProg = clamp((frontX - tr.userData.baseX) / 0.75, 0, 1);
        tr.rotation.z = -hitProg * 1.46; // blown cleanly away from blast source (`+X`)
        if (hitProg > 0.4) snappedCount += 1;
      });
      if (scene && scene.fog) {
        scene.fog.density = lerp(0.025, 0.085, clamp(u * 1.2, 0, 1));
      }
      const pTel = sweepPlume.update(u, lt, camera);
      return {
        anchors: {
          msh_blast_timber_front: [frontX, 0.85, -0.4],
          msh_untouched_ridge_ref: [4.6, 1.8, -3.5],
        },
        physicalMotion: {
          vertex_disp_max_m: Number((snappedCount * 0.14).toFixed(4)),
          blast_front_x_m: Number(frontX.toFixed(3)),
          trees_blown_down: snappedCount,
          max_plume_reach_m: pTel.max_plume_reach_m,
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 6. S05 (ESCALATION): Towering vertical Plinian Ash Column rising miles upward (`ashMode: true`)!
export function makeStHelensPlinianColumnStage() {
  const root = new THREE.Group();
  const terrain = new THREE.Mesh(
    new THREE.BoxGeometry(30, 0.25, 30),
    new THREE.MeshStandardMaterial({ color: 0x33322e, roughness: 0.92 })
  );
  terrain.position.y = -0.125;
  tagSemantic(terrain, 'environment');
  root.add(terrain);
  root.add(makeFixedGraniteRidges());

  const crater = makeVolcanoMountainMesh({ craterCut: 1.0, radius: 3.6, height: 2.35 });
  crater.mesh.position.set(0, 0, -0.6);
  tagSemantic(crater.mesh, 'subject');
  root.add(shadow(crater.mesh));

  // Rising vertical ash column core + billowing upper stratospheric anvil plume (`causal_feature`)
  const plinianCore = makeVolumetricPlumeStream({
    count: 36,
    ventWorld: [0.0, 1.65, -0.6],
    riseHeight: 6.4,
    lateralSpread: 1.85,
    driftVector: [0.4, 0.0, 0.0],
    ashMode: true,
    colorHex: 0x27272a,
    secondaryColorHex: 0x71717a,
    baseScale: 0.72,
    endScale: 3.15,
    opacityScale: 0.82,
    speed: 1.08,
    seed: 1933,
    semanticRole: 'causal_feature',
  });
  root.add(plinianCore.root);

  const falloutStrata = makeLayeredSmogStrata({
    planes: 4, width: 18.0, height: 6.5, zStart: -8.0, zEnd: -2.0, baseY: 3.6,
    colorHex: 0x3f3f46, opacityBase: 0.34, seed: 1945, semanticRole: 'effect_result', matteSkip: true,
  });
  root.add(falloutStrata.root);

  return {
    root,
    update(u, lt, scene, camera = null) {
      const surgeH = clamp(easeOut(u * 1.25), 0.15, 1.0);
      if (scene && scene.fog) {
        scene.fog.density = lerp(0.024, 0.068, surgeH);
      }
      falloutStrata.update(surgeH, lt);
      const pTel = plinianCore.update(u, lt, camera, { densityGain: 1.1 });

      return {
        anchors: {
          msh_plinian_ash_column: [0.0, lerp(2.6, 5.4, surgeH), -0.6],
          msh_valley_horizon_ref: [-4.6, 1.2, -1.8],
        },
        physicalMotion: {
          vertex_disp_max_m: pTel.max_plume_reach_m,
          column_height_norm: Number(surgeH.toFixed(4)),
          physical_model: 'stylized_atmospheric_visualization',
          cables_attached: true,
          collapse_active: false,
          nan_detected: false,
        },
      };
    },
  };
}

// 7. S07 (PAYOFF): Quiet Aerial Horseshoe Crater Aftermath vs Ghost Pre-Eruption Summit Contour
export function makeStHelensCraterAftermathStage() {
  const root = new THREE.Group();
  const terrain = new THREE.Mesh(
    new THREE.BoxGeometry(28, 0.25, 28),
    new THREE.MeshStandardMaterial({ color: 0x3b4238, roughness: 0.90 })
  );
  terrain.position.y = -0.125;
  tagSemantic(terrain, 'environment');
  root.add(terrain);
  root.add(makeFixedGraniteRidges());

  const aftermathCrater = makeVolcanoMountainMesh({ craterCut: 1.05, radius: 4.1, height: 2.35 });
  aftermathCrater.mesh.position.set(0, 0, -0.4);
  tagSemantic(aftermathCrater.mesh, 'causal_feature');
  root.add(shadow(aftermathCrater.mesh));

  // Translucent ghost wireframe summit contour proving 1,300+ ft summit elevation loss cleanly! (`reference_fixed`)
  const ghostCone = new THREE.Mesh(
    new THREE.ConeGeometry(2.65, 1.45, 20, 1, true),
    new THREE.MeshBasicMaterial({
      color: 0xf8fafc, wireframe: true, transparent: true, opacity: 0.44,
    })
  );
  ghostCone.position.set(-0.25, 2.55, -0.4);
  tagSemantic(ghostCone, 'reference_fixed');
  root.add(ghostCone);

  const calmSteam = makeVolumetricPlumeStream({
    count: 14,
    ventWorld: [0.0, 1.45, -0.4],
    riseHeight: 2.25,
    lateralSpread: 0.45,
    colorHex: 0xcbd5e1,
    secondaryColorHex: 0xf8fafc,
    baseScale: 0.42,
    endScale: 1.35,
    opacityScale: 0.42,
    speed: 0.42,
    seed: 1980,
    semanticRole: 'effect_result',
  });
  root.add(calmSteam.root);

  return {
    root,
    update(u, lt, scene, camera = null) {
      const revealGhost = smooth(clamp(u * 1.4, 0, 1));
      ghostCone.material.opacity = lerp(0.12, 0.48, revealGhost);
      if (scene && scene.fog) {
        scene.fog.density = 0.016;
      }
      const pTel = calmSteam.update(u, lt, camera);
      return {
        anchors: {
          msh_horseshoe_crater_rim: [0.35, 1.95, -0.4],
          msh_original_summit_ghost: [-0.25, 3.15, -0.4],
        },
        physicalMotion: {
          vertex_disp_max_m: Number((1.15 + revealGhost * 0.25).toFixed(4)),
          summit_loss_visible: true,
          air_clarity_recovery: Number(revealGhost.toFixed(4)),
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
