"""Procedural Modern Skyscraper Wind Sway & Tuned Mass Damper 3D Scene Library (R2.8 Showcase).

General engineering visualization (illustrative fictional modern tower; non-CFD/non-FEM).
Supports 6 distinct procedural camera spaces across 9+ story beats:
  1. Street-level upward hook with flexing tall tower vs static reference skyline + street observer
  2. Aerial city skyline establish showing slender tower rising over city blocks & traffic
  3. Mid-upper windward facade with alternating Karman wind-vortex streamlines
  4. Upper structural frame flex paired with rigid vertical plumb-line reference mast & drift gauge
  5. Upper-floor interior office with swinging pendant lamp, sloshing cup & grounded office worker
  6. LayeredCutaway penthouse Tuned Mass Damper (TMD) sphere + counter-phase vectors + damped/undamped split
"""

from __future__ import annotations


SKYSCRAPER_SCENES_JS = r"""import * as THREE from 'three';
import { clamp, easeInOut, easeOut, lerp } from './anim.js';
import { buildRegisteredCharacter } from './character_action_rig.js';
import { LayeredCutaway } from './layered_cutaway.js';
import { computeAnchorsTelemetry } from './aircraft_window_scenes.js';
import {
  evaluateFlexuralTowerSway,
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

function makeFlexingTower({
  width = 1.45,
  depth = 1.45,
  height = 8.4,
  nTiers = 18,
  accentHex = 0x38bdf8,
  glassHex = 0x1e3a5f,
  hasDamperBeacon = false,
  semanticRole = 'subject',
} = {}) {
  const group = new THREE.Group();
  tagSemantic(group, semanticRole);

  const frameMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.36, metalness: 0.72 });
  const glassMat = new THREE.MeshStandardMaterial({
    color: glassHex, emissive: 0x0f172a, emissiveIntensity: 0.35, roughness: 0.18, metalness: 0.55,
  });
  const mullionMat = new THREE.MeshStandardMaterial({ color: accentHex, emissive: accentHex, emissiveIntensity: 0.25, roughness: 0.35, metalness: 0.5 });

  const tierH = height / nTiers;
  const tiers = [];
  for (let i = 0; i < nTiers; i++) {
    const tNorm = (i + 0.5) / nTiers;
    const taper = 1.0 - tNorm * 0.14;
    const tg = new THREE.Group();
    tg.position.set(0, (i + 0.5) * tierH, 0);

    const core = new THREE.Mesh(new THREE.BoxGeometry(width * taper, tierH * 0.96, depth * taper), glassMat);
    const slab = new THREE.Mesh(new THREE.BoxGeometry(width * taper * 1.04, tierH * 0.16, depth * taper * 1.04), frameMat);
    slab.position.y = tierH * 0.44;
    tg.add(core, slab);

    // Bright vertical corner mullions so lateral bend & roof displacement read unmistakably against sky
    for (const sx of [-1, 1]) {
      for (const sz of [-1, 1]) {
        const col = new THREE.Mesh(new THREE.BoxGeometry(0.085, tierH * 1.02, 0.085), mullionMat);
        col.position.set(sx * width * taper * 0.5, 0, sz * depth * taper * 0.5);
        tg.add(col);
      }
    }
    tagSemantic(tg, tNorm >= 0.45 ? 'causal_feature' : semanticRole);
    tg.userData.yNorm = tNorm;
    tg.userData.baseY = (i + 0.5) * tierH;
    group.add(tg);
    tiers.push(tg);
  }

  // Crown & mast spire attached to top tier
  const topTier = tiers[tiers.length - 1];
  const crown = new THREE.Mesh(new THREE.BoxGeometry(width * 0.72, 0.45, depth * 0.72), frameMat);
  crown.position.y = tierH * 0.65;
  const spire = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.09, 1.35, 10), mullionMat);
  spire.position.y = tierH * 0.65 + 0.85;
  const beaconMat = new THREE.MeshStandardMaterial({
    color: hasDamperBeacon ? 0x22c55e : 0xfacc15,
    emissive: hasDamperBeacon ? 0x16a34a : 0xeab308,
    emissiveIntensity: 1.4,
  });
  const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.11, 14, 10), beaconMat);
  beacon.position.y = tierH * 0.65 + 1.55;
  tagSemantic(crown, 'causal_feature');
  tagSemantic(spire, 'causal_feature');
  tagSemantic(beacon, 'causal_feature');
  topTier.add(crown, spire, beacon);

  const roofAnchor = new THREE.Object3D();
  roofAnchor.position.set(0, tierH * 0.65 + 0.45, 0);
  topTier.add(roofAnchor);

  const midAnchor = new THREE.Object3D();
  midAnchor.position.set(0, 0, depth * 0.5);
  tiers[Math.floor(nTiers * 0.65)].add(midAnchor);

  function updateTower(t, opts = {}) {
    let maxDx = 0.0;
    tiers.forEach((tg) => {
      const ev = evaluateFlexuralTowerSway(t, tg.userData.yNorm, opts);
      tg.position.x = ev.dx;
      tg.rotation.z = ev.rotZ;
      maxDx = Math.max(maxDx, Math.abs(ev.dx));
    });
    return { roof_dx_m: Number(maxDx.toFixed(4)) };
  }

  return { group, tiers, topTier, roofAnchor, midAnchor, update: updateTower };
}

function makeCityBlocksEnvironment() {
  const root = new THREE.Group();
  tagSemantic(root, 'environment');

  const asphalt = new THREE.Mesh(
    new THREE.PlaneGeometry(34, 34),
    new THREE.MeshStandardMaterial({ color: 0x232934, roughness: 0.88 })
  );
  asphalt.rotation.x = -Math.PI / 2;
  asphalt.receiveShadow = true;
  tagSemantic(asphalt, 'environment');
  root.add(asphalt);

  const roadStripeMat = new THREE.MeshStandardMaterial({ color: 0xfacc15, roughness: 0.72 });
  for (let k = -5; k <= 5; k++) {
    const dash = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.02, 0.75), roadStripeMat);
    dash.position.set(0, 0.01, k * 1.65);
    tagSemantic(dash, 'environment');
    root.add(dash);
  }

  const blockMats = [
    new THREE.MeshStandardMaterial({ color: 0x3b4859, roughness: 0.76 }),
    new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.72 }),
    new THREE.MeshStandardMaterial({ color: 0x2e3b4e, roughness: 0.68 }),
  ];
  const coords = [
    [-3.8, 3.6, -2.2, 2.0, 2.2], [-3.6, 2.8, 2.4, 1.8, 2.0],
    [3.8, 4.1, -2.0, 2.1, 2.1], [3.7, 2.5, 2.6, 1.9, 2.0],
    [-4.2, 5.2, -6.5, 2.4, 2.4], [4.2, 4.8, -6.2, 2.2, 2.2],
  ];
  coords.forEach(([bx, bh, bz, bw, bd], idx) => {
    const b = new THREE.Mesh(new THREE.BoxGeometry(bw, bh, bd), blockMats[idx % blockMats.length]);
    b.position.set(bx, bh * 0.5, bz);
    tagSemantic(b, 'environment');
    root.add(b);
  });

  return root;
}

/**
 * 1. Street-Level Hook: Pedestrian looks up as hero skyscraper sways visibly relative to static skyline tower.
 */
export function makeSkyscraperStreetHookRig(makeHumanFn, charSpec = {}) {
  const root = new THREE.Group();
  root.add(makeCityBlocksEnvironment());

  // Static rigid neighboring reference tower at back-right so roof lateral motion is unmistakable
  const refTower = new THREE.Mesh(
    new THREE.BoxGeometry(1.35, 7.6, 1.35),
    new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.74, metalness: 0.25 })
  );
  refTower.position.set(2.35, 3.8, -4.6);
  tagSemantic(refTower, 'environment');
  root.add(refTower);

  const heroTower = makeFlexingTower({ width: 1.55, depth: 1.55, height: 8.6, nTiers: 18, accentHex: 0x38bdf8 });
  heroTower.group.position.set(-0.25, 0, -3.2);
  root.add(heroTower.group);

  const staticRefAnchor = new THREE.Object3D();
  staticRefAnchor.position.set(2.35, 7.5, -4.6);
  root.add(staticRefAnchor);

  const observer = buildRegisteredCharacter(makeHumanFn, {
    character_id: charSpec.character_id || 'char_street_observer_01',
    shirt_hex: charSpec.shirt_hex ?? 0x2563eb,
    pants_hex: charSpec.pants_hex ?? 0x1e293b,
    collar_hex: 0xf1f5f9,
  });
  tagSemantic(observer.root, 'character');
  root.add(observer.root);

  const headAnchor = new THREE.Object3D();
  headAnchor.position.set(0, 0.14, 0.04);
  observer.j.head.add(headAnchor);

  const stanceTracker = { epoch: -1, foot: '', anchorXZ: null };
  let lastPhys = {};
  let lastChar = null;

  function update(lt, dur) {
    const tInfo = heroTower.update(lt, { roofDriftM: 0.46, omega: 2.35 });
    const cRes = evaluateCharacterPose(lt, {
      primary_intent: 'brace',
      duration_sec: dur,
      ground_y: 0.0,
      base_x: -0.95,
      base_z: 1.15,
      base_yaw: 0.25,
      reaction_onset_sec: Math.min(0.42, dur * 0.18),
      retreat_distance_m: 0.45,
      threat_world: [-0.25, 6.5, -3.2],
    });
    applyGroundedCharacterPose(observer, cRes);
    // Tilt head distinctly upward toward skyscraper roof
    observer.j.head.rotation.x = -0.52;
    lastChar = getCharacterPerformanceTelemetry(observer, cRes, stanceTracker, [-0.25, 6.5, -3.2]);
    lastPhys = getPhysicalTelemetry({ motion_type: 'flexural_tower_sway' }, {
      vertex_disp_max_m: tInfo.roof_dx_m,
      roof_drift_m: tInfo.roof_dx_m,
      cables_attached: true,
    });
    return { physicalMotion: lastPhys, characterPerformance: lastChar };
  }

  return {
    root: shadow(root),
    update,
    getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, {
      rooftop_sway_apex: heroTower.roofAnchor,
      static_skyline_ref: staticRefAnchor,
      street_observer_head: headAnchor,
    }, []),
    getPhysicalState: () => lastPhys,
    getCharTelemetry: () => lastChar,
  };
}

/**
 * 2. Wide City Skyline Establish + 3. Crosswind Vortex Facade + 4. Plumb-Line Drift Comparison
 */
export function makeSkyscraperExteriorRig({ mode = 'skyline_wide' } = {}) {
  const root = new THREE.Group();
  root.add(makeCityBlocksEnvironment());

  const heroTower = makeFlexingTower({
    width: 1.65,
    depth: 1.65,
    height: 8.8,
    nTiers: 18,
    accentHex: mode === 'plumb_drift' ? 0xfacc15 : 0x38bdf8,
  });
  heroTower.group.position.set(0, 0, -1.2);
  root.add(heroTower.group);

  // Wind vortex ribbons (for cause beat)
  const windTubes = [];
  if (mode === 'wind_vortex') {
    const wMat = new THREE.MeshStandardMaterial({
      color: 0x38bdf8, emissive: 0x0284c7, emissiveIntensity: 0.9, transparent: true, opacity: 0.82,
    });
    for (let i = 0; i < 6; i++) {
      const pts = [];
      const yBase = 4.2 + i * 0.72;
      for (let k = 0; k < 12; k++) {
        const x = -2.8 + k * 0.52;
        const wake = x > 0.6 ? Math.sin(k * 1.1 + i * 1.4) * 0.36 : 0.0;
        const z = (i % 2 === 0 ? 0.92 : -0.92) + wake;
        pts.push(new THREE.Vector3(x, yBase + Math.cos(k * 0.7 + i) * 0.14, z));
      }
      const m = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 24, 0.036, 6, false), wMat);
      tagSemantic(m, 'causal_feature');
      m.userData.baseX = -1.2 + (i % 3) * 0.4;
      root.add(m);
      windTubes.push(m);
    }
  }

  // Static Vertical Plumb Reference Mast + Scale Markers (for lateral roof drift beat)
  const plumbAnchor = new THREE.Object3D();
  if (mode === 'plumb_drift') {
    const plumbMat = new THREE.MeshBasicMaterial({ color: 0xef4444 });
    for (let k = 0; k < 14; k++) {
      const seg = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.42, 0.05), plumbMat);
      seg.position.set(1.18, 0.6 + k * 0.62, -0.35);
      tagSemantic(seg, 'subject');
      root.add(seg);
    }
    plumbAnchor.position.set(1.18, 8.2, -0.35);
    root.add(plumbAnchor);
  }

  // Moving street cars in skyline wide view for urban scale
  const cars = [];
  const carMat = new THREE.MeshStandardMaterial({ color: 0xeab308, roughness: 0.4 });
  for (let c = 0; c < 3; c++) {
    const cm = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.16, 0.52), carMat);
    cm.position.set(-0.35 + c * 0.65, 0.09, 1.5 - c * 2.2);
    tagSemantic(cm, 'environment');
    root.add(cm);
    cars.push(cm);
  }

  let lastPhys = {};
  function update(lt) {
    const drift = mode === 'skyline_wide' ? 0.24 : (mode === 'wind_vortex' ? 0.44 : 0.54);
    const tInfo = heroTower.update(lt, { roofDriftM: drift, omega: 2.25 });
    windTubes.forEach((wt, i) => {
      wt.position.x = ((lt * 2.2 + i * 0.45) % 1.8) - 0.9;
    });
    cars.forEach((cm, idx) => {
      cm.position.z = (((lt * 1.4 + idx * 2.4) % 9.0) - 4.5);
    });
    lastPhys = getPhysicalTelemetry({ motion_type: 'flexural_tower_sway' }, {
      vertex_disp_max_m: tInfo.roof_dx_m,
      roof_drift_m: tInfo.roof_dx_m,
      cables_attached: true,
    });
    return lastPhys;
  }

  return {
    root: shadow(root),
    update,
    getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, {
      tower_mid_profile: heroTower.midAnchor,
      windward_facade_vortex: heroTower.midAnchor,
      plumb_drift_tip: heroTower.roofAnchor,
      plumb_static_ref: plumbAnchor,
    }, []),
    getPhysicalState: () => lastPhys,
  };
}

/**
 * 5. Interior Upper-Floor Office Space: Swinging pendant lamp, desk, coffee cup & grounded worker reacting.
 */
export function makeSkyscraperOfficeInteriorRig(makeHumanFn, charSpec = {}) {
  const root = new THREE.Group();

  // Warm interior floor & ceiling & window wall overlooking shifting exterior skyline
  const floorMat = new THREE.MeshStandardMaterial({ color: 0x3b332c, roughness: 0.78 });
  const wallMat = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.85 });
  const deskMat = new THREE.MeshStandardMaterial({ color: 0x7c5839, roughness: 0.65 });
  const frameMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.45, metalness: 0.65 });

  const floor = new THREE.Mesh(new THREE.BoxGeometry(6.5, 0.16, 6.0), floorMat);
  floor.position.set(0, -0.08, 0);
  floor.receiveShadow = true;
  tagSemantic(floor, 'environment');
  const ceiling = new THREE.Mesh(new THREE.BoxGeometry(6.5, 0.16, 6.0), wallMat);
  ceiling.position.set(0, 2.75, 0);
  tagSemantic(ceiling, 'environment');
  root.add(floor, ceiling);

  // Floor-to-ceiling window mullions on back wall z = -1.6
  for (const mx of [-2.1, -0.7, 0.7, 2.1]) {
    const mullion = new THREE.Mesh(new THREE.BoxGeometry(0.10, 2.75, 0.12), frameMat);
    mullion.position.set(mx, 1.38, -1.55);
    tagSemantic(mullion, 'environment');
    root.add(mullion);
  }
  const sill = new THREE.Mesh(new THREE.BoxGeometry(5.8, 0.36, 0.22), frameMat);
  sill.position.set(0, 0.18, -1.55);
  tagSemantic(sill, 'environment');
  root.add(sill);

  // Exterior distant skyline visible through office glass (shifts subtly opposite office sway!)
  const extSkyline = new THREE.Group();
  tagSemantic(extSkyline, 'environment');
  const extMat = new THREE.MeshStandardMaterial({ color: 0x64748b, emissive: 0x1e293b, emissiveIntensity: 0.45 });
  for (const [ex, eh, ez] of [[-2.4, 3.2, -5.5], [-0.4, 4.1, -6.2], [1.6, 2.9, -5.2], [3.0, 3.8, -6.8]]) {
    const b = new THREE.Mesh(new THREE.BoxGeometry(1.1, eh, 1.1), extMat);
    b.position.set(ex, 0.4, ez);
    extSkyline.add(b);
  }
  root.add(extSkyline);

  // Office desk + monitor + coffee cup
  const deskGroup = new THREE.Group();
  tagSemantic(deskGroup, 'subject');
  const top = new THREE.Mesh(new THREE.BoxGeometry(1.45, 0.08, 0.78), deskMat);
  top.position.set(-0.45, 0.76, -0.25);
  const legL = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.74, 0.68), frameMat);
  legL.position.set(-1.10, 0.37, -0.25);
  const legR = legL.clone();
  legR.position.x = 0.20;
  const monitor = new THREE.Mesh(new THREE.BoxGeometry(0.54, 0.34, 0.04), frameMat);
  monitor.position.set(-0.62, 1.02, -0.45);
  const mug = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.05, 0.11, 14), new THREE.MeshStandardMaterial({ color: 0xf8fafc }));
  mug.position.set(-0.08, 0.855, -0.18);
  deskGroup.add(top, legL, legR, monitor, mug);
  root.add(deskGroup);

  // Swinging ceiling pendant lamp (primary visible cue of building motion inside office!)
  const lampPivot = new THREE.Group();
  lampPivot.position.set(-0.35, 2.68, -0.15);
  tagSemantic(lampPivot, 'causal_feature');
  const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.88, 8), frameMat);
  cord.position.y = -0.44;
  const shade = new THREE.Mesh(
    new THREE.ConeGeometry(0.24, 0.20, 20, 1, true),
    new THREE.MeshStandardMaterial({ color: 0xfacc15, emissive: 0xf59e0b, emissiveIntensity: 0.65, side: THREE.DoubleSide })
  );
  shade.position.y = -0.92;
  const bulb = new THREE.Mesh(
    new THREE.SphereGeometry(0.075, 12, 10),
    new THREE.MeshBasicMaterial({ color: 0xfef9c3 })
  );
  bulb.position.y = -0.94;
  lampPivot.add(cord, shade, bulb);
  root.add(lampPivot);

  const lampAnchor = new THREE.Object3D();
  lampAnchor.position.set(0, -0.92, 0);
  lampPivot.add(lampAnchor);

  const worker = buildRegisteredCharacter(makeHumanFn, {
    character_id: charSpec.character_id || 'char_office_worker_01',
    shirt_hex: charSpec.shirt_hex ?? 0x0ea5e9,
    pants_hex: charSpec.pants_hex ?? 0x1e293b,
    collar_hex: 0xf8fafc,
  });
  tagSemantic(worker.root, 'character');
  root.add(worker.root);

  const workerHeadAnchor = new THREE.Object3D();
  workerHeadAnchor.position.set(0, 0.14, 0.04);
  worker.j.head.add(workerHeadAnchor);

  const stanceTracker = { epoch: -1, foot: '', anchorXZ: null };
  let lastPhys = {};
  let lastChar = null;

  function update(lt, dur) {
    const sway = Math.sin(lt * 2.25);
    lampPivot.rotation.z = sway * 0.24;
    extSkyline.position.x = -sway * 0.36;
    mug.position.x = -0.08 + sway * 0.015;

    const cRes = evaluateCharacterPose(lt, {
      primary_intent: 'brace',
      duration_sec: dur,
      ground_y: 0.0,
      base_x: 0.58,
      base_z: 0.22,
      base_yaw: -0.62,
      reaction_onset_sec: Math.min(0.45, dur * 0.20),
      retreat_distance_m: 0.36,
      threat_world: [-0.35, 1.85, -0.15],
    });
    applyGroundedCharacterPose(worker, cRes);
    worker.j.head.rotation.x = -0.22;
    lastChar = getCharacterPerformanceTelemetry(worker, cRes, stanceTracker, [-0.35, 1.85, -0.15]);
    lastPhys = getPhysicalTelemetry({ motion_type: 'interior_pendulum_sway' }, {
      vertex_disp_max_m: Number((Math.abs(sway) * 0.24).toFixed(4)),
      lamp_angle_rad: Number((sway * 0.24).toFixed(4)),
      cables_attached: true,
    });
    return { physicalMotion: lastPhys, characterPerformance: lastChar };
  }

  return {
    root: shadow(root),
    update,
    getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, {
      office_pendant_lamp: lampAnchor,
      office_worker_head: workerHeadAnchor,
    }, []),
    getPhysicalState: () => lastPhys,
    getCharTelemetry: () => lastChar,
  };
}

/**
 * 6. Tuned Mass Damper (TMD) LayeredCutaway, Counter-Phase Mechanical View, and Before/After Split.
 */
export function makeSkyscraperDamperCutawayRig({ mode = 'cutaway' } = {}) {
  const root = new THREE.Group();

  if (mode === 'before_after') {
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(24, 24),
      new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.85 })
    );
    floor.rotation.x = -Math.PI / 2;
    tagSemantic(floor, 'environment');
    root.add(floor);

    // Left: UNDAMPED tower swaying noticeably; Right: DAMPED tower steady with green beacon
    const undamped = makeFlexingTower({ width: 1.15, depth: 1.15, height: 6.4, nTiers: 14, accentHex: 0xf97316, hasDamperBeacon: false });
    undamped.group.position.set(-1.35, 0, 0);
    const damped = makeFlexingTower({ width: 1.15, depth: 1.15, height: 6.4, nTiers: 14, accentHex: 0x22c55e, hasDamperBeacon: true });
    damped.group.position.set(1.35, 0, 0);
    root.add(undamped.group, damped.group);

    let lastPhys = {};
    function updateSplit(lt) {
      const uInfo = undamped.update(lt, { roofDriftM: 0.48, omega: 2.35, dampingFactor: 1.0 });
      const dInfo = damped.update(lt, { roofDriftM: 0.48, omega: 2.35, dampingFactor: 0.16 });
      lastPhys = getPhysicalTelemetry({ motion_type: 'damped_vs_undamped_comparison' }, {
        vertex_disp_max_m: uInfo.roof_dx_m,
        undamped_drift_m: uInfo.roof_dx_m,
        damped_drift_m: dInfo.roof_dx_m,
        cables_attached: true,
      });
      return lastPhys;
    }

    return {
      root: shadow(root),
      update: updateSplit,
      getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, {
        damped_tower_top: damped.roofAnchor,
        rooftop_sway_apex: undamped.roofAnchor,
      }, []),
      getPhysicalState: () => lastPhys,
    };
  }

  // Upper mechanical penthouse LayeredCutaway with suspended Tuned Mass Damper (TMD) sphere + hydraulic pistons
  const cutaway = new LayeredCutaway({
    id: 'skyscraper_tmd_cutaway',
    worldAnchor: [0, 1.45, 0.0],
    clipNormal: [0, 0, -1],
    clipConstantStart: 1.35,
    clipConstantOpen: -0.15,
  });

  const frameGroup = new THREE.Group();
  tagSemantic(frameGroup, 'subject');
  const steelFrameMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.36, metalness: 0.78 });
  const glassWallMat = new THREE.MeshPhysicalMaterial({
    color: 0x38bdf8, transparent: true, opacity: 0.44, roughness: 0.16, metalness: 0.25, side: THREE.DoubleSide,
  });

  // Outer curtain wall box that slides open cleanly via LayeredCutaway
  const outerShell = new THREE.Mesh(new THREE.BoxGeometry(2.45, 2.75, 2.15), glassWallMat);
  outerShell.position.set(0, 1.45, 0);
  tagSemantic(outerShell, 'subject');
  cutaway.addOuterShell(outerShell, { applyClip: true });

  // Structural steel mechanical cage (moves with building sway!)
  const cageGroup = new THREE.Group();
  tagSemantic(cageGroup, 'subject');
  for (const sx of [-1.05, 1.05]) {
    for (const sz of [-0.90, 0.90]) {
      const col = new THREE.Mesh(new THREE.BoxGeometry(0.14, 2.65, 0.14), steelFrameMat);
      col.position.set(sx, 1.45, sz);
      cageGroup.add(col);
    }
  }
  const topBeam = new THREE.Mesh(new THREE.BoxGeometry(2.35, 0.18, 2.0), steelFrameMat);
  topBeam.position.set(0, 2.78, 0);
  const botSlab = new THREE.Mesh(new THREE.BoxGeometry(2.45, 0.16, 2.10), steelFrameMat);
  botSlab.position.set(0, 0.14, 0);
  cageGroup.add(topBeam, botSlab);
  cutaway.addInternalComponent('penthouse_frame', cageGroup, { layerIndex: 1 });

  // Giant Tuned Mass Damper (TMD) Pendulum Sphere + 4 suspension cables + hydraulic cylinders
  const tmdPivot = new THREE.Group();
  tmdPivot.position.set(0, 2.70, 0);
  tagSemantic(tmdPivot, 'causal_feature');
  const sphereMat = new THREE.MeshStandardMaterial({
    color: 0xd97706, emissive: 0x78350f, emissiveIntensity: 0.28, roughness: 0.24, metalness: 0.88,
  });
  const tmdSphere = new THREE.Mesh(new THREE.SphereGeometry(0.62, 32, 24), sphereMat);
  tmdSphere.position.set(0, -1.42, 0);
  const ringBand = new THREE.Mesh(
    new THREE.TorusGeometry(0.64, 0.045, 12, 36),
    new THREE.MeshStandardMaterial({ color: 0xfacc15, roughness: 0.3, metalness: 0.85 })
  );
  ringBand.rotation.x = Math.PI / 2;
  ringBand.position.set(0, -1.42, 0);
  tmdPivot.add(tmdSphere, ringBand);

  const cableMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, metalness: 0.85, roughness: 0.25 });
  for (const [cx, cz] of [[-0.42, -0.35], [0.42, -0.35], [-0.42, 0.35], [0.42, 0.35]]) {
    const cab = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 1.42, 8), cableMat);
    cab.position.set(cx * 0.5, -0.71, cz * 0.5);
    cab.rotation.z = Math.atan2(cx, 1.42);
    cab.rotation.x = -Math.atan2(cz, 1.42);
    tmdPivot.add(cab);
  }
  cutaway.addInternalComponent('tmd_pendulum_sphere', tmdPivot, { layerIndex: 2, materialId: 'mat_tmd_sphere' });

  // Hydraulic viscous damper pistons linking cage bottom to TMD sphere
  const hydGroup = new THREE.Group();
  const pistonMat = new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x0369a1, emissiveIntensity: 0.45, metalness: 0.82, roughness: 0.22 });
  const pistonL = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.055, 0.95, 10), pistonMat);
  pistonL.position.set(-0.62, 0.72, 0);
  pistonL.rotation.z = -1.15;
  const pistonR = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.055, 0.95, 10), pistonMat);
  pistonR.position.set(0.62, 0.72, 0);
  pistonR.rotation.z = 1.15;
  tagSemantic(pistonL, 'causal_feature');
  tagSemantic(pistonR, 'causal_feature');
  hydGroup.add(pistonL, pistonR);
  cutaway.addInternalComponent('hydraulic_dampers', hydGroup, { layerIndex: 3, materialId: 'mat_hydraulic_piston' });

  // Dynamic 3D opposing force bars in counterphase mode (showing frame push vs counterweight pull)
  const frameBarMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
  const damperBarMat = new THREE.MeshBasicMaterial({ color: 0xf97316 });
  const frameForceBar = new THREE.Mesh(new THREE.BoxGeometry(0.65, 0.09, 0.09), frameBarMat);
  frameForceBar.position.set(0, 2.86, 0.28);
  const damperForceBar = new THREE.Mesh(new THREE.BoxGeometry(0.65, 0.09, 0.09), damperBarMat);
  damperForceBar.position.set(0, 1.88, 0.78);
  frameForceBar.visible = (mode === 'counterphase');
  damperForceBar.visible = (mode === 'counterphase');
  tagSemantic(frameForceBar, 'causal_feature');
  tagSemantic(damperForceBar, 'causal_feature');
  root.add(frameForceBar, damperForceBar);

  root.add(cutaway.root);

  const sphereAnchor = new THREE.Object3D();
  sphereAnchor.position.set(0, -1.42, 0.25);
  tmdPivot.add(sphereAnchor);

  const frameAnchor = new THREE.Object3D();
  frameAnchor.position.set(0, 2.55, 0.5);
  cageGroup.add(frameAnchor);

  let lastPhys = {};
  function updateCutaway(lt, dur) {
    const u = clamp(lt / Math.max(0.2, dur), 0, 1);
    const reveal = mode === 'counterphase' ? 1.0 : easeInOut(clamp(u * 1.45, 0, 1));
    cutaway.setReveal(reveal, { slideOffset: [0.35, 0.0, 0.25] });

    const ev = evaluateFlexuralTowerSway(lt, 1.0, {
      roofDriftM: mode === 'counterphase' ? 0.34 : 0.28,
      omega: 2.35,
      dampingFactor: 1.0,
    });
    cutaway.internalGroup.position.x = ev.dx;
    cutaway.internalGroup.rotation.z = ev.rotZ * 0.45;
    // Pendulum swings cleanly in OPPOSITE phase!
    const swingAngle = clamp(-ev.wave * 0.34, -0.45, 0.45);
    tmdPivot.rotation.z = swingAngle;
    pistonL.scale.set(1, clamp(1.0 + ev.wave * 0.22, 0.72, 1.28), 1);
    pistonR.scale.set(1, clamp(1.0 - ev.wave * 0.22, 0.72, 1.28), 1);

    if (mode === 'counterphase') {
      frameForceBar.position.x = ev.dx + Math.sign(ev.dx || 1) * 0.42;
      frameForceBar.scale.x = Math.max(0.25, Math.abs(ev.wave) * 1.35);
      damperForceBar.position.x = -ev.dx - Math.sign(ev.dx || 1) * 0.42;
      damperForceBar.scale.x = Math.max(0.25, Math.abs(ev.wave) * 1.45);
    }

    lastPhys = getPhysicalTelemetry({ motion_type: 'tuned_mass_damper_counterphase' }, {
      vertex_disp_max_m: Number((Math.abs(ev.dx) + Math.abs(swingAngle) * 1.4).toFixed(4)),
      frame_dx_m: Number(ev.dx.toFixed(4)),
      damper_swing_rad: Number(swingAngle.toFixed(4)),
      cables_attached: true,
      cutaway_reveal: Number(reveal.toFixed(3)),
    });
    return lastPhys;
  }

  return {
    root: shadow(root),
    cutaway,
    update: updateCutaway,
    getAnchorsTelemetry: cam => computeAnchorsTelemetry(cam, {
      damper_pendulum_sphere: sphereAnchor,
      counterphase_tower_frame: frameAnchor,
    }, []),
    getPhysicalState: () => lastPhys,
  };
}
"""
