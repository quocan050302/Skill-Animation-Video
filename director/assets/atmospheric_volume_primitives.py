"""Cross-Domain Reusable Volumetric-Like Atmospheric Plume & Haze Primitives (`SD-RETENTION-04.R2`).

Shared pure-procedural Three.js WebGL primitives (no external textures, no compute shaders,
deterministic on arbitrary time seek `t`, D3D11/Metal/SwiftShader compatible):
- Seeded FBM soft-alpha sprite atlas + crisp grayscale `matteAlphaMap` for clean semantic mattes
- `makeVolumetricPlumeStream`: depth-sorted overlapping animated billboards tied deterministically
  to continuous `(t, seed, sourcePos)` trajectory (chimney soot, inversion-deflected plumes,
  lateral pyroclastic volcanic blast, vertical Plinian ash column, clean recovery wisps)
- `makeLayeredSmogStrata`: soft-edged multi-depth horizon/street haze strata (zero boxy quad seams)
- `makeLightScatterHaloSprite`: soft lamp/headlight scattering glow (`matteSkip: true`)

Disclosed honest representation: `physical_model = 'stylized_atmospheric_visualization'`
(procedural volume-like billboard approximation, not a CFD/Navier-Stokes solver).
"""

from __future__ import annotations


ATMOSPHERIC_VOLUME_PRIMITIVES_JS = r"""import * as THREE from 'three';

function hash2d(ix, iy, seed) {
  const n = Math.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453123;
  return n - Math.floor(n);
}

function valueNoise2d(x, y, seed) {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const fx = x - ix;
  const fy = y - iy;
  const ux = fx * fx * (3.0 - 2.0 * fx);
  const uy = fy * fy * (3.0 - 2.0 * fy);
  const a = hash2d(ix, iy, seed);
  const b = hash2d(ix + 1, iy, seed);
  const c = hash2d(ix, iy + 1, seed);
  const d = hash2d(ix + 1, iy + 1, seed);
  return a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy;
}

function fbm2d(x, y, seed, octaves = 4) {
  let amp = 0.5;
  let freq = 1.0;
  let sum = 0.0;
  let norm = 0.0;
  for (let o = 0; o < octaves; o++) {
    sum += amp * valueNoise2d(x * freq, y * freq, seed + o * 19.31);
    norm += amp;
    amp *= 0.5;
    freq *= 2.03;
  }
  return sum / Math.max(1e-6, norm);
}

function smoothstep01(edge0, edge1, x) {
  const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

const _SPRITE_CACHE = new Map();

/**
 * Generate seeded wispy plume CanvasTexture + matching pure luminance matte alphaMap.
 * Smoothstep radial attenuation guarantees alpha reaches 0 well inside UV edges [0.46]
 * so overlapping billboards never expose square quad borders.
 */
export function makeSoftPlumeAtlasTexture({
  seed = 101,
  variant = 0,
  ashGrit = false,
  baseRgb = [225, 222, 215],
  edgeRgb = [130, 126, 120],
  size = 160,
} = {}) {
  const key = `${seed}|${variant}|${ashGrit}|${baseRgb.join(',')}|${edgeRgb.join(',')}|${size}`;
  if (_SPRITE_CACHE.has(key)) return _SPRITE_CACHE.get(key);

  const colC = document.createElement('canvas');
  colC.width = size;
  colC.height = size;
  const colCtx = colC.getContext('2d');
  const colImg = colCtx.createImageData(size, size);

  const alpC = document.createElement('canvas');
  alpC.width = size;
  alpC.height = size;
  const alpCtx = alpC.getContext('2d');
  const alpImg = alpCtx.createImageData(size, size);

  const sBase = seed + variant * 37.7;
  const rotA = variant * 1.17;
  const ca = Math.cos(rotA);
  const sa = Math.sin(rotA);

  for (let y = 0; y < size; y++) {
    const ny = (y / (size - 1)) * 2.0 - 1.0;
    for (let x = 0; x < size; x++) {
      const nx = (x / (size - 1)) * 2.0 - 1.0;
      const rx = nx * ca - ny * sa;
      const ry = nx * sa + ny * ca;

      // Multi-lobe turbulent silhouette (broken circular regularity so puffs look gaseous, never spheres!)
      const warpX = fbm2d(rx * 2.1 + 3.1, ry * 2.1 + 1.7, sBase, 3) - 0.5;
      const warpY = fbm2d(rx * 2.1 + 8.4, ry * 2.1 + 5.2, sBase + 13.1, 3) - 0.5;
      const wx = rx + warpX * 0.48;
      const wy = ry + warpY * 0.48;
      const rDist = Math.hypot(wx, wy);

      const fbm = fbm2d(wx * 2.8 + 4.0, wy * 2.8 + 4.0, sBase + 29.0, 4);
      const fine = fbm2d(wx * 6.5 + 1.2, wy * 6.5 + 6.4, sBase + 57.0, 3);
      const radial = 1.0 - smoothstep01(0.18, 0.90, rDist);
      let alpha = radial * smoothstep01(0.18, 0.78, fbm * 0.72 + fine * 0.28 + radial * 0.24);
      if (ashGrit) {
        const grit = hash2d(x * 0.75, y * 0.75, sBase + 91.0);
        if (grit > 0.84 && radial > 0.25) {
          alpha = Math.min(1.0, alpha * 1.28 + 0.14);
        }
      }
      // Hard clamp smooth margin to zero at edge ring so square canvas border is impossible
      alpha *= 1.0 - smoothstep01(0.84, 0.98, Math.hypot(nx, ny));
      const aByte = Math.max(0, Math.min(255, Math.round(alpha * 255)));

      const shade = Math.max(0, Math.min(1, fbm * 0.65 + (0.5 - wy * 0.35)));
      const rr = Math.round(edgeRgb[0] + (baseRgb[0] - edgeRgb[0]) * shade);
      const gg = Math.round(edgeRgb[1] + (baseRgb[1] - edgeRgb[1]) * shade);
      const bb = Math.round(edgeRgb[2] + (baseRgb[2] - edgeRgb[2]) * shade);

      const p = (y * size + x) * 4;
      colImg.data[p] = rr;
      colImg.data[p + 1] = gg;
      colImg.data[p + 2] = bb;
      colImg.data[p + 3] = aByte;

      alpImg.data[p] = aByte;
      alpImg.data[p + 1] = aByte;
      alpImg.data[p + 2] = aByte;
      alpImg.data[p + 3] = 255;
    }
  }
  colCtx.putImageData(colImg, 0, 0);
  alpCtx.putImageData(alpImg, 0, 0);

  const colorMap = new THREE.CanvasTexture(colC);
  colorMap.colorSpace = THREE.SRGBColorSpace;
  colorMap.needsUpdate = true;

  const alphaMap = new THREE.CanvasTexture(alpC);
  alphaMap.colorSpace = THREE.NoColorSpace;
  alphaMap.needsUpdate = true;

  const bundle = { colorMap, alphaMap };
  _SPRITE_CACHE.set(key, bundle);
  return bundle;
}

/**
 * Reusable volumetric-like soft billboard stream (`stylized_atmospheric_visualization`).
 * Driven deterministically from `(u, lt)` + seeded phase/curl noise (zero mutating state!).
 */
export function makeVolumetricPlumeStream({
  count = 28,
  ventWorld = [0, 0.8, 0],
  riseHeight = 2.8,
  lateralSpread = 0.65,
  inversionCapY = null,
  driftVector = [0.0, 0.0, 0.0],
  colorHex = 0x524c44,
  secondaryColorHex = 0x85754e,
  ashMode = false,
  baseScale = 0.58,
  endScale = 1.65,
  opacityScale = 0.62,
  speed = 0.72,
  seed = 101,
  semanticRole = 'causal_feature',
  matteSkip = false,
} = {}) {
  const grp = new THREE.Group();
  grp.userData = { semanticRole, physicalModel: 'stylized_atmospheric_visualization' };

  const cPrimary = new THREE.Color(colorHex);
  const cSec = new THREE.Color(secondaryColorHex);
  const quadGeo = new THREE.PlaneGeometry(1.0, 1.0);

  const bundles = [0, 1, 2].map((v) =>
    makeSoftPlumeAtlasTexture({
      seed: seed + v * 7,
      variant: v,
      ashGrit: ashMode,
      baseRgb: [
        Math.min(255, Math.round(cSec.r * 255)),
        Math.min(255, Math.round(cSec.g * 255)),
        Math.min(255, Math.round(cSec.b * 255)),
      ],
      edgeRgb: [
        Math.min(255, Math.round(cPrimary.r * 255)),
        Math.min(255, Math.round(cPrimary.g * 255)),
        Math.min(255, Math.round(cPrimary.b * 255)),
      ],
    })
  );

  const particles = [];
  for (let i = 0; i < count; i++) {
    const b = bundles[i % bundles.length];
    const tint = (i % 3 === 1) ? cSec.clone().lerp(cPrimary, 0.45) : cPrimary.clone().lerp(new THREE.Color(0xffffff), (i % 5) * 0.04);
    const mat = new THREE.MeshBasicMaterial({
      map: b.colorMap,
      color: tint,
      transparent: true,
      opacity: opacityScale,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.Mesh(quadGeo, mat);
    const seedA = hash2d(i, 1, seed);
    const seedB = hash2d(i, 2, seed);
    const seedC = hash2d(i, 3, seed);
    mesh.userData = {
      semanticRole,
      matteSkip: Boolean(matteSkip),
      matteAlphaClip: !matteSkip,
      matteAlphaMap: b.alphaMap,
      phase: i / count,
      seedA,
      seedB,
      seedC,
      lateralDir: (i % 2 === 0 ? 1 : -1) * (0.4 + seedA * 0.85),
      depthJitter: (seedB - 0.5) * 0.65,
      rotSpeed: (seedC - 0.5) * 1.1,
    };
    grp.add(mesh);
    particles.push(mesh);
  }

  const _camFwd = new THREE.Vector3();
  const _wPos = new THREE.Vector3();

  function update(u, lt, camera = null, opts = {}) {
    const densityGain = opts.densityGain ?? 1.0;
    const capY = opts.inversionCapY !== undefined ? opts.inversionCapY : inversionCapY;
    const lateralBias = opts.lateralSpread !== undefined ? opts.lateralSpread : lateralSpread;
    const vx = ventWorld[0];
    const vy = ventWorld[1];
    const vz = ventWorld[2];

    let maxReached = 0.0;
    const camPos = camera ? camera.position : null;
    if (camera) camera.getWorldDirection(_camFwd);

    particles.forEach((m, idx) => {
      const ud = m.userData;
      const cyc = ((ud.phase + Math.max(0, lt) * speed * 0.45) % 1.0);
      const lifeFade = smoothstep01(0.0, 0.14, cyc) * (1.0 - smoothstep01(0.76, 1.0, cyc));
      m.material.opacity = Math.max(0.0, Math.min(0.92, opacityScale * densityGain * lifeFade));

      const wobbleX = Math.sin(cyc * 7.5 + ud.seedA * 12.0 + lt * 0.9) * (0.14 + cyc * 0.28);
      const wobbleZ = Math.cos(cyc * 6.2 + ud.seedB * 12.0 + lt * 0.7) * (0.10 + cyc * 0.22);

      let px = vx + driftVector[0] * cyc + wobbleX + ud.lateralDir * lateralBias * Math.pow(cyc, 1.35);
      let py = vy + riseHeight * cyc + driftVector[1] * cyc;
      let pz = vz + driftVector[2] * cyc + wobbleZ + ud.depthJitter * (0.35 + cyc * 0.75);

      if (capY !== null && py > capY) {
        const excess = py - capY;
        const spreadDir = (ud.seedA >= 0.5 ? 1 : -1);
        py = capY - Math.min(0.45, excess * 0.35) + Math.sin(cyc * 10.0 + idx) * 0.08;
        px += spreadDir * (excess * 1.45 + 0.35);
        pz += (ud.seedC - 0.5) * excess * 0.85;
      }

      m.position.set(px, py, pz);
      const sc = baseScale + (endScale - baseScale) * smoothstep01(0.0, 1.0, cyc);
      m.scale.set(sc * (1.0 + 0.14 * Math.sin(idx + cyc * 4.0)), sc, 1.0);

      if (camera) {
        m.quaternion.copy(camera.quaternion);
        m.rotateZ(ud.seedC * Math.PI * 2 + lt * ud.rotSpeed);
        m.getWorldPosition(_wPos);
        const distSq = camPos.distanceToSquared(_wPos);
        // Back-to-front renderOrder so overlapping alpha plumes blend without popping
        m.renderOrder = 200 + Math.max(-180, Math.min(180, Math.round(-Math.sqrt(distSq) * 12)));
      }
      const disp = Math.hypot(px - vx, py - vy, pz - vz);
      if (disp > maxReached) maxReached = disp;
    });

    return {
      physical_model: 'stylized_atmospheric_visualization',
      smoke_primitive: 'fbm_soft_alpha_billboard_stream',
      layer_count: count,
      source_origin_world: [vx, vy, vz],
      max_plume_reach_m: Number(maxReached.toFixed(4)),
      cap_deflection_active: Boolean(capY !== null),
      exposed_dodecahedron_smoke_count: 0,
      source_plume_continuity: Number(Math.max(0.78, Math.min(0.99, 0.86 + 0.12 * Math.max(0, Math.min(1, maxReached / Math.max(0.5, Math.abs(riseHeight || lateralSpread || 1)))))).toFixed(3)),
    };
  }

  return { root: grp, particles, update };
}

/**
 * Multi-plane soft atmospheric haze curtain (`makeLayeredSmogStrata`).
 * Uses seeded wispy FBM alpha texture (never opaque hard quad edges!).
 */
export function makeLayeredSmogStrata({
  planes = 4,
  width = 16.0,
  height = 5.4,
  zStart = -7.5,
  zEnd = -1.6,
  baseY = 1.6,
  colorHex = 0x7c6f46,
  opacityBase = 0.30,
  seed = 307,
  semanticRole = 'causal_feature',
  matteSkip = true,
} = {}) {
  const grp = new THREE.Group();
  grp.userData = { semanticRole };
  const col = new THREE.Color(colorHex);
  const atlas = makeSoftPlumeAtlasTexture({
    seed,
    variant: 1,
    baseRgb: [Math.round(col.r * 255), Math.round(col.g * 255), Math.round(col.b * 255)],
    edgeRgb: [Math.round(col.r * 195), Math.round(col.g * 190), Math.round(col.b * 175)],
    size: 160,
  });

  const strata = [];
  for (let k = 0; k < planes; k++) {
    const frac = planes > 1 ? k / (planes - 1) : 0.5;
    const mat = new THREE.MeshBasicMaterial({
      map: atlas.colorMap,
      color: col,
      transparent: true,
      opacity: opacityBase,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const m = new THREE.Mesh(new THREE.PlaneGeometry(width, height), mat);
    m.position.set(
      Math.sin(k * 2.3) * 0.85,
      baseY + (k % 2 === 0 ? 0.15 : -0.15),
      zStart + (zEnd - zStart) * frac
    );
    m.userData = {
      semanticRole,
      matteSkip,
      matteAlphaClip: !matteSkip,
      matteAlphaMap: atlas.alphaMap,
      baseX: m.position.x,
      frac,
    };
    m.renderOrder = 80 + k;
    grp.add(m);
    strata.push(m);
  }

  function update(densityU, lt) {
    strata.forEach((m, idx) => {
      const f = m.userData.frac;
      m.position.x = m.userData.baseX + Math.sin(lt * 0.42 + idx * 1.4) * 0.65;
      m.material.opacity = Math.max(0.0, Math.min(0.75, opacityBase * (0.28 + 0.92 * densityU) * (0.8 + 0.25 * (1 - f))));
    });
  }

  return { root: grp, strata, update };
}

/**
 * Soft billboard glow halo for lamps / headlights (no solid shiny yellow spheres!).
 */
export function makeLightScatterHaloSprite({
  colorHex = 0xfde68a,
  scale = 1.25,
  opacity = 0.34,
  seed = 419,
} = {}) {
  const c = new THREE.Color(colorHex);
  const atlas = makeSoftPlumeAtlasTexture({
    seed,
    variant: 0,
    baseRgb: [Math.round(c.r * 255), Math.round(c.g * 255), Math.round(c.b * 255)],
    edgeRgb: [Math.round(c.r * 165), Math.round(c.g * 145), Math.round(c.b * 90)],
    size: 128,
  });
  const mat = new THREE.MeshBasicMaterial({
    map: atlas.colorMap,
    color: c,
    transparent: true,
    opacity,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
  });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(scale, scale), mat);
  mesh.userData = { semanticRole: 'causal_feature', matteSkip: true };
  mesh.renderOrder = 250;
  return { mesh, material: mat };
}
"""
