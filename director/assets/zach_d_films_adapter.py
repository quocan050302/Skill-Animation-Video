"""Single-Engine Adapter for `zach-d-films` (3D Cartoon Three.js Studio Explainer — ZDF-MOTION-01).

Uses ONLY:
- `vendor/claude-animation-skills/skills/zach-d-films/engine/src/{anim.js,human.js,props.js,materials.js,textures.js}`
- Shared `kit/node_modules/three` and `@fontsource/montserrat`
- Modular ZDF-only procedural 3D modules emitted strictly inside `engine_work/src/`:
  `camera_executor.js`, `character_action_rig.js`, `layered_cutaway.js`,
  `mechanical_systems.js`, `novel_props.js`, `shots.js`, `director_main.js`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

from . import link_kit_node_modules
from ..camera_execution import CAMERA_EXECUTOR_JS
from ..editorial_overlay import EDITORIAL_OVERLAY_RENDERER_JS, build_editorial_timeline
from .zdf_rigs import CHARACTER_ACTION_RIG_JS, LAYERED_CUTAWAY_JS
from .zdf_mechanical_scenes import MECHANICAL_SYSTEMS_JS
from .zdf_aircraft_window_scenes import AIRCRAFT_WINDOW_SCENES_JS
from .zdf_boston_molasses_scenes import BOSTON_MOLASSES_SCENES_JS
from .physical_motion_primitives import PHYSICAL_MOTION_PRIMITIVES_JS
from .character_performance import CHARACTER_PERFORMANCE_JS
from .zdf_tacoma_bridge_scenes import TACOMA_BRIDGE_SCENES_JS


NOVEL_3D_PROPS_JS = r"""import * as THREE from 'three';
import { materials } from './materials.js';
import { rng, woodTexture } from './textures.js';
import { LayeredCutaway } from './layered_cutaway.js';
import { buildRegisteredCharacter } from './character_action_rig.js';

function shadow(o) {
  o.traverse(c => { if (c.isMesh) { c.castShadow = true; c.receiveShadow = true; } });
  return o;
}

export function forcePedestal() {
  const M = materials();
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.48, 0.92, 36), M.steelDark);
  base.position.y = 0.46;
  const top = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.44, 0.06, 36), M.steelBright);
  top.position.y = 0.95;
  g.add(base, top);
  return shadow(g);
}

export function energyCore(accentHex = 0x3fa9f5) {
  const g = new THREE.Group();
  const coreMat = new THREE.MeshStandardMaterial({
    color: accentHex, emissive: accentHex, emissiveIntensity: 0.65, roughness: 0.2, metalness: 0.1
  });
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.16, 3), coreMat);
  const ringMat = new THREE.MeshStandardMaterial({ color: 0xd8dee9, metalness: 0.9, roughness: 0.25 });
  const r1 = new THREE.Mesh(new THREE.TorusGeometry(0.26, 0.016, 12, 64), ringMat);
  const r2 = new THREE.Mesh(new THREE.TorusGeometry(0.32, 0.014, 12, 64), ringMat);
  r2.rotation.x = Math.PI / 2;
  g.add(core, r1, r2);
  g.core = core; g.r1 = r1; g.r2 = r2;
  return shadow(g);
}

export function cutawaySlabStack() {
  const M = materials();
  const g = new THREE.Group();
  const layers = [
    [0.52, 0.06, 0.52, M.steelBright],
    [0.48, 0.09, 0.48, M.copper],
    [0.52, 0.08, 0.52, M.steelDark],
  ];
  g.layers = [];
  layers.forEach(([w, h, d, mat]) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    g.add(m);
    g.layers.push(m);
  });
  return shadow(g);
}

// ---------- Procedural Seeded Textures for Roman Props ----------
function makeSandTexture(seed = 17) {
  const r = rng(seed);
  const c = document.createElement('canvas');
  c.width = c.height = 512;
  const ctx = c.getContext('2d');
  const grad = ctx.createRadialGradient(256, 256, 20, 256, 256, 256);
  grad.addColorStop(0, '#e6c696');
  grad.addColorStop(0.65, '#d8b482');
  grad.addColorStop(1, '#c59e6a');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 4200; i++) {
    const x = r() * 512, y = r() * 512;
    const shade = r() < 0.5 ? 245 : 155;
    ctx.fillStyle = `rgba(${shade}, ${Math.round(shade * 0.82)}, ${Math.round(shade * 0.58)}, ${0.08 + r() * 0.14})`;
    ctx.fillRect(x, y, 1.5 + r() * 2.5, 1.5 + r() * 2.5);
  }
  ctx.strokeStyle = 'rgba(130, 95, 55, 0.16)';
  ctx.lineWidth = 3;
  for (let rad = 50; rad <= 230; rad += 38) {
    ctx.beginPath();
    ctx.arc(256, 256, rad, 0, Math.PI * 2);
    ctx.stroke();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

function makeScutumTexture(emblemHex = '#f4c430') {
  const c = document.createElement('canvas');
  c.width = 256; c.height = 384;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#8b1e24';
  ctx.fillRect(0, 0, 256, 384);
  ctx.strokeStyle = emblemHex;
  ctx.lineWidth = 10;
  ctx.strokeRect(14, 14, 228, 356);
  ctx.fillStyle = emblemHex;
  for (const sy of [-1, 1]) {
    ctx.save();
    ctx.translate(128, 192 + sy * 88);
    ctx.scale(1, sy);
    ctx.beginPath();
    ctx.moveTo(0, -18); ctx.lineTo(64, -46); ctx.lineTo(42, -8); ctx.lineTo(74, 12); ctx.lineTo(14, 6);
    ctx.lineTo(0, 32); ctx.lineTo(-14, 6); ctx.lineTo(-74, 12); ctx.lineTo(-42, -8); ctx.lineTo(-64, -46);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function makeTabletTexture(headerTxt, bigTxt, bgHex = '#2a211b', borderHex = '#d9a441', bigColor = '#ffd166') {
  const c = document.createElement('canvas');
  c.width = 512; c.height = 340;
  const ctx = c.getContext('2d');
  ctx.fillStyle = bgHex;
  ctx.fillRect(0, 0, 512, 340);
  ctx.strokeStyle = borderHex;
  ctx.lineWidth = 16;
  ctx.strokeRect(14, 14, 484, 312);
  ctx.strokeStyle = 'rgba(255,255,255,0.14)';
  ctx.lineWidth = 3;
  ctx.strokeRect(28, 28, 456, 284);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  const fitFont = (txt, startPx) => {
    let sz = startPx;
    while (sz > 28) {
      ctx.font = `700 ${sz}px Cap, sans-serif`;
      if (ctx.measureText(txt).width <= 420) break;
      sz -= 4;
    }
  };

  ctx.fillStyle = '#e9dec9';
  fitFont(headerTxt, 42);
  ctx.fillText(headerTxt, 256, 102);

  ctx.fillStyle = bigColor;
  fitFont(bigTxt, 92);
  ctx.fillText(bigTxt, 256, 224);

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

let _romanMats = null;
export function romanMaterials() {
  if (_romanMats) return _romanMats;
  const sandTex = makeSandTexture(42);
  const woodTex = woodTexture(19);
  _romanMats = {
    sand: new THREE.MeshStandardMaterial({ map: sandTex, roughness: 0.94, metalness: 0.02 }),
    travertine: new THREE.MeshStandardMaterial({ color: 0xe3d2b4, roughness: 0.86, metalness: 0.04 }),
    travertineDark: new THREE.MeshStandardMaterial({ color: 0xbda682, roughness: 0.9 }),
    bronze: new THREE.MeshPhysicalMaterial({ color: 0xd49a45, metalness: 0.92, roughness: 0.28, clearcoat: 0.2 }),
    gold: new THREE.MeshPhysicalMaterial({ color: 0xf4c430, metalness: 0.96, roughness: 0.18, emissive: 0x3b2600, emissiveIntensity: 0.25 }),
    silver: new THREE.MeshPhysicalMaterial({ color: 0xdbe2ea, metalness: 0.94, roughness: 0.22 }),
    crimson: new THREE.MeshStandardMaterial({ color: 0xa4161a, roughness: 0.72 }),
    darkWood: new THREE.MeshStandardMaterial({ map: woodTex, color: 0x6f4528, roughness: 0.8 }),
    leatherWrap: new THREE.MeshStandardMaterial({ color: 0x5c3a21, roughness: 0.7 }),
    scutumFace: new THREE.MeshStandardMaterial({ map: makeScutumTexture('#f4c430'), roughness: 0.55, metalness: 0.15, side: THREE.DoubleSide }),
  };
  return _romanMats;
}

export function addGladiatorBracers(human) {
  const RM = romanMaterials();
  for (const side of ['lWr', 'rWr']) {
    const cuff = new THREE.Mesh(new THREE.CylinderGeometry(0.047, 0.044, 0.11, 18), RM.leatherWrap);
    cuff.position.y = 0.015;
    cuff.castShadow = cuff.receiveShadow = true;
    human.j[side].add(cuff);
  }
}

export function romanPlinth(height = 0.72, topR = 0.30) {
  const RM = romanMaterials();
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.BoxGeometry(topR * 2.2, 0.10, topR * 2.2), RM.travertineDark);
  base.position.y = 0.05;
  const col = new THREE.Mesh(new THREE.CylinderGeometry(topR * 0.78, topR * 0.90, height - 0.18, 20), RM.travertine);
  col.position.y = 0.10 + (height - 0.18) * 0.5;
  const cap = new THREE.Mesh(new THREE.BoxGeometry(topR * 2.15, 0.09, topR * 2.15), RM.travertine);
  cap.position.y = height - 0.045;
  const trim = new THREE.Mesh(new THREE.TorusGeometry(topR * 0.85, 0.018, 10, 28), RM.bronze);
  trim.rotation.x = Math.PI / 2;
  trim.position.y = height - 0.09;
  g.add(base, col, cap, trim);
  return shadow(g);
}

export function trainingPalus() {
  const RM = romanMaterials();
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.28, 0.08, 24), RM.travertineDark);
  base.position.y = 0.04;
  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.085, 0.095, 1.52, 20), RM.darkWood);
  post.position.y = 0.80;
  for (const y of [0.55, 0.95, 1.32]) {
    const band = new THREE.Mesh(new THREE.TorusGeometry(0.092, 0.014, 8, 24), RM.bronze);
    band.rotation.x = Math.PI / 2;
    band.position.y = y;
    g.add(band);
  }
  const top = new THREE.Mesh(new THREE.SphereGeometry(0.09, 20, 14), RM.darkWood);
  top.position.y = 1.56;
  g.add(base, post, top);
  return shadow(g);
}

export function arenaStage({ radius = 4.6, wallArc = true } = {}) {
  const RM = romanMaterials();
  const g = new THREE.Group();
  const floor = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius + 0.15, 0.08, 64), RM.sand);
  floor.position.y = -0.041;
  floor.receiveShadow = true;
  g.add(floor);

  const curb = new THREE.Mesh(new THREE.TorusGeometry(radius - 0.12, 0.11, 12, 64), RM.travertine);
  curb.rotation.x = Math.PI / 2;
  curb.position.y = 0.02;
  curb.receiveShadow = true;
  g.add(curb);

  if (wallArc) {
    const wallR = radius + 0.95;
    const count = 9;
    for (let i = 0; i < count; i++) {
      const a = Math.PI + ((i / (count - 1)) - 0.5) * 1.95;
      const px = Math.sin(a) * wallR, pz = Math.cos(a) * wallR;
      const pil = new THREE.Mesh(new THREE.BoxGeometry(0.46, 2.6, 0.42), RM.travertine);
      pil.position.set(px, 1.3, pz);
      pil.lookAt(0, 1.3, 0);
      pil.castShadow = pil.receiveShadow = true;
      g.add(pil);
      if (i < count - 1) {
        const a2 = Math.PI + (((i + 0.5) / (count - 1)) - 0.5) * 1.95;
        const lx = Math.sin(a2) * wallR, lz = Math.cos(a2) * wallR;
        const span = new THREE.Mesh(new THREE.BoxGeometry(1.18, 0.42, 0.36), RM.travertineDark);
        span.position.set(lx, 2.38, lz);
        span.lookAt(0, 2.38, 0);
        g.add(span);
      }
    }
  }
  return g;
}

export function romanHelmet(crestHex = 0xb81d24) {
  const RM = romanMaterials();
  const M = materials();
  const g = new THREE.Group();
  const dome = new THREE.Mesh(new THREE.SphereGeometry(0.124, 32, 20, 0, Math.PI * 2, 0, Math.PI * 0.44), RM.bronze);
  dome.position.set(0, 0.134, -0.008);
  dome.scale.set(0.98, 1.15, 1.08);
  dome.rotation.x = -0.10;
  g.add(dome);
  const brow = new THREE.Mesh(new THREE.TorusGeometry(0.118, 0.011, 8, 32, Math.PI * 0.85), RM.gold);
  brow.rotation.set(Math.PI * 0.44, 0, Math.PI * 0.075);
  brow.position.set(0, 0.155, 0.018);
  g.add(brow);
  for (const s of [-1, 1]) {
    const cg = new THREE.Mesh(new THREE.BoxGeometry(0.014, 0.09, 0.055), RM.bronze);
    cg.position.set(s * 0.095, 0.095, -0.005);
    cg.rotation.set(0.08, -s * 0.25, -s * 0.08);
    g.add(cg);
  }
  const neck = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.042, 0.075), M.steel);
  neck.position.set(0, 0.095, -0.102);
  neck.rotation.x = 0.62;
  g.add(neck);
  const crestMat = new THREE.MeshStandardMaterial({ color: crestHex, roughness: 0.78 });
  for (let i = 0; i < 11; i++) {
    const t = (i / 10) * 2 - 1;
    const ang = t * 1.05;
    const seg = new THREE.Mesh(new THREE.BoxGeometry(0.022, 0.085, 0.036), crestMat);
    seg.position.set(0, 0.275 + Math.cos(ang) * 0.04, Math.sin(ang) * 0.115 - 0.01);
    seg.rotation.x = ang;
    g.add(seg);
  }
  return shadow(g);
}

export function romanScutum() {
  const RM = romanMaterials();
  const shape = new THREE.Shape();
  shape.moveTo(-0.22, -0.32);
  shape.lineTo(0.22, -0.32);
  shape.lineTo(0.23, 0.32);
  shape.lineTo(-0.23, 0.32);
  shape.closePath();

  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: 0.020, bevelEnabled: true, bevelThickness: 0.008, bevelSize: 0.008, bevelSegments: 2, curveSegments: 16,
  });
  const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i);
    p.setZ(i, p.getZ(i) - x * x * 1.15);
  }
  geo.computeVertexNormals();

  const g = new THREE.Group();
  const body = new THREE.Mesh(geo, RM.scutumFace);
  g.add(body);
  for (const y of [-0.32, 0.32]) {
    const trim = new THREE.Mesh(new THREE.BoxGeometry(0.44, 0.024, 0.034), RM.bronze);
    trim.position.set(0, y, -0.02);
    g.add(trim);
  }
  const umbo = new THREE.Mesh(new THREE.SphereGeometry(0.064, 24, 16, 0, Math.PI * 2, 0, Math.PI * 0.50), RM.gold);
  umbo.rotation.x = Math.PI / 2;
  umbo.position.set(0, 0, 0.016);
  g.add(umbo);
  return shadow(g);
}

export function denariusStack({ count = 12, radius = 0.075, height = 0.018, gold = true } = {}) {
  const RM = romanMaterials();
  const mat = gold ? RM.gold : RM.silver;
  const g = new THREE.Group();
  g.coins = [];
  for (let i = 0; i < count; i++) {
    const coin = new THREE.Group();
    const disc = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, height * 0.85, 24), mat);
    const rim = new THREE.Mesh(new THREE.TorusGeometry(radius * 0.93, height * 0.24, 8, 24), mat);
    rim.rotation.x = Math.PI / 2;
    rim.position.y = height * 0.38;
    coin.add(disc, rim);
    const jx = Math.sin(i * 2.1) * radius * 0.08;
    const jz = Math.cos(i * 3.3) * radius * 0.08;
    coin.position.set(jx, height * 0.5 + i * height * 1.02, jz);
    g.add(coin);
    g.coins.push(coin);
  }
  return shadow(g);
}

export function romanScrollTablet(headerTxt, bigTxt, accentHex = 0xd4a017) {
  const RM = romanMaterials();
  const g = new THREE.Group();
  const hexStr = '#' + accentHex.toString(16).padStart(6, '0');
  const tex = makeTabletTexture(headerTxt, bigTxt, '#211915', hexStr, hexStr);
  const frame = new THREE.Mesh(new THREE.BoxGeometry(0.68, 0.45, 0.045), RM.darkWood);
  const face = new THREE.Mesh(
    new THREE.PlaneGeometry(0.62, 0.40),
    new THREE.MeshStandardMaterial({ map: tex, roughness: 0.45, emissive: accentHex, emissiveIntensity: 0.14 })
  );
  face.position.z = 0.024;
  g.add(frame, face);
  return shadow(g);
}

export function togaSash() {
  const RM = romanMaterials();
  const g = new THREE.Group();
  const band = new THREE.Mesh(new THREE.TorusGeometry(0.205, 0.036, 12, 36), RM.crimson);
  band.scale.set(1.06, 1.38, 0.68);
  band.position.set(0, 0.12, 0);
  band.rotation.z = -0.58;
  g.add(band);
  return shadow(g);
}

export function balanceScale50x() {
  const RM = romanMaterials();
  const g = new THREE.Group();
  const plinth = romanPlinth(0.22, 0.26);
  g.add(plinth);
  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.040, 1.18, 24), RM.bronze);
  post.position.y = 0.80;
  const finial = new THREE.Mesh(new THREE.SphereGeometry(0.052, 20, 14), RM.gold);
  finial.position.y = 1.41;
  g.add(post, finial);

  const beamPivot = new THREE.Group();
  beamPivot.position.set(0, 1.30, 0);
  g.add(beamPivot);

  const beam = new THREE.Mesh(new THREE.BoxGeometry(0.76, 0.034, 0.040), RM.bronze);
  beamPivot.add(beam);

  const mkPan = (xOff) => {
    const arm = new THREE.Group();
    arm.position.set(xOff, -0.015, 0);
    beamPivot.add(arm);
    for (const dx of [-0.07, 0.07]) {
      const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.005, 0.34, 8), RM.bronze);
      rod.position.set(dx * 0.5, -0.17, 0);
      rod.rotation.z = dx > 0 ? 0.16 : -0.16;
      arm.add(rod);
    }
    const pan = new THREE.Mesh(new THREE.CylinderGeometry(0.145, 0.115, 0.030, 28), RM.gold);
    pan.position.y = -0.35;
    arm.add(pan);
    return arm;
  };

  const leftArm = mkPan(-0.32);
  const rightArm = mkPan(0.32);
  const stack1x = denariusStack({ count: 3, radius: 0.062, height: 0.016, gold: false });
  stack1x.position.set(0, -0.33, 0);
  leftArm.add(stack1x);

  const tab1x = romanScrollTablet('RENTAL', '1x', 0xdbe2ea);
  tab1x.scale.setScalar(0.50);
  beamPivot.add(tab1x);
  tab1x.position.set(-0.30, 0.24, 0.02);

  const stack50x = denariusStack({ count: 24, radius: 0.068, height: 0.016, gold: true });
  stack50x.position.set(0, -0.33, 0);
  rightArm.add(stack50x);

  const tab50x = romanScrollTablet('PENALTY', '50x', 0xff4d4d);
  tab50x.scale.setScalar(0.54);
  beamPivot.add(tab50x);
  tab50x.position.set(0.30, 0.28, 0.02);

  g.setTilt = (rad) => {
    beamPivot.rotation.z = rad;
    leftArm.rotation.z = -rad;
    rightArm.rotation.z = -rad;
    tab1x.rotation.z = -rad;
    tab50x.rotation.z = -rad;
  };
  g.stack50x = stack50x;
  g.rightPan = rightArm;
  return shadow(g);
}

// ---------- Non-Roman Multi-Family Scene Builders ----------

function makeScreenTexture(headline = 'READY', btnText = 'SEND', sent = false) {
  const c = document.createElement('canvas');
  c.width = 256; c.height = 512;
  const ctx = c.getContext('2d');
  const bg = ctx.createLinearGradient(0, 0, 0, 512);
  bg.addColorStop(0, '#0f172a');
  bg.addColorStop(1, '#1e293b');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, 256, 512);
  ctx.fillStyle = 'rgba(255,255,255,0.08)';
  ctx.fillRect(16, 28, 224, 52);
  ctx.fillStyle = '#94a3b8';
  ctx.font = '700 20px Cap, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('DIRECT LINK', 128, 60);
  ctx.fillStyle = sent ? '#0ea5e9' : '#2563eb';
  ctx.beginPath();
  ctx.roundRect(24, 150, 208, 92, 22);
  ctx.fill();
  ctx.fillStyle = '#ffffff';
  ctx.font = '700 26px Cap, sans-serif';
  ctx.fillText(headline, 128, 204);
  ctx.fillStyle = sent ? '#10b981' : '#38bdf8';
  ctx.beginPath();
  ctx.roundRect(44, 340, 168, 68, 34);
  ctx.fill();
  ctx.fillStyle = '#07131d';
  ctx.font = '700 28px Cap, sans-serif';
  ctx.fillText(sent ? 'SENT' : btnText, 128, 383);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

function makeRackTexture(seed = 11) {
  const r = rng(seed);
  const c = document.createElement('canvas');
  c.width = 256; c.height = 512;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#111622';
  ctx.fillRect(0, 0, 256, 512);
  for (let row = 0; row < 16; row++) {
    const y = 14 + row * 30;
    ctx.fillStyle = '#1e2638';
    ctx.fillRect(14, y, 228, 22);
    for (let led = 0; led < 9; led++) {
      const x = 24 + led * 22;
      const roll = r();
      ctx.fillStyle = roll > 0.62 ? '#38bdf8' : (roll > 0.30 ? '#34d399' : '#334155');
      ctx.fillRect(x, y + 7, 10, 8);
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

export function makeModernOutfitCharacter(makeHumanFn, charSpecOrHex = 0x2563eb) {
  const charSpec = typeof charSpecOrHex === 'object' ? charSpecOrHex : { shirt_hex: charSpecOrHex };
  return buildRegisteredCharacter(makeHumanFn, charSpec);
}

export function makeSmartphoneRig({ sent = false, scale = 1.0 } = {}) {
  const M = materials();
  const g = new THREE.Group();
  const chassisMat = new THREE.MeshPhysicalMaterial({ color: 0x1e293b, metalness: 0.82, roughness: 0.25, clearcoat: 0.6 });
  const frameMat = new THREE.MeshPhysicalMaterial({ color: 0x94a3b8, metalness: 0.92, roughness: 0.20 });
  const pcbMat = new THREE.MeshStandardMaterial({ color: 0x0f5132, roughness: 0.45, metalness: 0.25 });
  const chipMat = new THREE.MeshPhysicalMaterial({ color: 0x111827, metalness: 0.4, roughness: 0.2, clearcoat: 0.8 });
  const traceMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, emissive: 0xd97706, emissiveIntensity: 0.55, metalness: 0.9, roughness: 0.2 });

  const backShell = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.56, 0.016), chassisMat);
  backShell.position.z = -0.018;
  g.add(backShell);

  const internals = new THREE.Group();
  g.add(internals);
  const pcb = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.50, 0.008), pcbMat);
  pcb.position.z = -0.004;
  internals.add(pcb);

  const batt = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.25, 0.014), M.steelDark);
  batt.position.set(-0.025, -0.08, 0.006);
  const battBadge = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.05, 0.004), new THREE.MeshStandardMaterial({ color: 0x10b981, emissive: 0x059669, emissiveIntensity: 0.45 }));
  battBadge.position.set(-0.025, -0.06, 0.014);
  internals.add(batt, battBadge);

  const soc = new THREE.Mesh(new THREE.BoxGeometry(0.095, 0.095, 0.012), chipMat);
  soc.position.set(0.03, 0.11, 0.007);
  internals.add(soc);

  const pulses = [];
  for (let i = 0; i < 6; i++) {
    const tr = new THREE.Mesh(new THREE.BoxGeometry(0.006, 0.18, 0.004), traceMat);
    tr.position.set(-0.04 + i * 0.022, 0.13, 0.003);
    internals.add(tr);
    const pkt = new THREE.Mesh(new THREE.SphereGeometry(0.011, 14, 10), new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x38bdf8, emissiveIntensity: 1.5 }));
    pkt.position.set(-0.04 + i * 0.022, 0.05, 0.012);
    internals.add(pkt);
    pulses.push(pkt);
  }

  const frontGlass = new THREE.Group();
  g.add(frontGlass);
  const bezel = new THREE.Mesh(new THREE.BoxGeometry(0.285, 0.565, 0.014), frameMat);
  const scrMat = new THREE.MeshStandardMaterial({
    map: makeScreenTexture(sent ? 'DELIVERED' : 'HELLO WORLD', 'SEND', sent),
    emissive: sent ? 0x0ea5e9 : 0x1d4ed8, emissiveIntensity: 0.45, roughness: 0.15,
  });
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.255, 0.515), scrMat);
  screen.position.z = 0.008;
  frontGlass.position.z = 0.014;
  frontGlass.add(bezel, screen);

  const tapRing = new THREE.Mesh(
    new THREE.TorusGeometry(0.055, 0.006, 12, 36),
    new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x38bdf8, emissiveIntensity: 1.4, transparent: true, opacity: 0.0 })
  );
  tapRing.position.set(0, -0.11, 0.028);
  frontGlass.add(tapRing);

  g.scale.setScalar(scale);
  g.frontGlass = frontGlass;
  g.internals = internals;
  g.pulses = pulses;
  g.tapRing = tapRing;
  g.screenMat = scrMat;
  g.getTelemetry = (peelU = 0) => ({
    cutaway_id: 'smartphone_device_cutaway',
    has_clip_plane: false,
    reveal_u: Number(peelU.toFixed(4)),
    layers_count: 3,
    components_count: 4,
    internal_component_count: 4,
    internal_component_names: ['pcb', 'lithium_battery', 'soc_chip', 'copper_traces'],
  });
  return shadow(g);
}

export function makeRadioTowerRig() {
  const M = materials();
  const g = new THREE.Group();
  const hilltop = new THREE.Mesh(new THREE.CylinderGeometry(1.15, 1.55, 0.42, 36), new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.9 }));
  hilltop.position.y = 0.21;
  g.add(hilltop);
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.16, 1.95, 6), M.steelBright);
  mast.position.y = 1.38;
  g.add(mast);
  for (let k = 0; k < 4; k++) {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.14 - k * 0.022, 0.012, 8, 6), M.steelDark);
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.72 + k * 0.38;
    g.add(ring);
  }
  const beaconMat = new THREE.MeshStandardMaterial({ color: 0xef4444, emissive: 0xff2222, emissiveIntensity: 1.8 });
  const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.048, 20, 14), beaconMat);
  beacon.position.y = 2.38;
  g.add(beacon);

  const rfRings = [];
  for (let i = 0; i < 4; i++) {
    const rm = new THREE.Mesh(
      new THREE.TorusGeometry(0.25, 0.012, 12, 48),
      new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x38bdf8, emissiveIntensity: 1.3, transparent: true, opacity: 0.8 })
    );
    rm.position.y = 2.38;
    rm.rotation.x = Math.PI / 3;
    g.add(rm);
    rfRings.push(rm);
  }
  g.rfRings = rfRings;
  g.beacon = beacon;
  return shadow(g);
}

export function makeSubseaCableRig(seed = 23) {
  const M = materials();
  const g = new THREE.Group();
  const bedGeo = new THREE.PlaneGeometry(8.5, 6.5, 42, 32);
  bedGeo.rotateX(-Math.PI / 2);
  const pos = bedGeo.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), z = pos.getZ(i);
    pos.setY(i, 0.06 * Math.sin(x * 1.4 + seed) + 0.05 * Math.cos(z * 1.8));
  }
  bedGeo.computeVertexNormals();
  const seabed = new THREE.Mesh(bedGeo, new THREE.MeshStandardMaterial({ color: 0x164e63, roughness: 0.92, metalness: 0.05 }));
  g.add(seabed);

  const cable = new THREE.Group();
  cable.position.set(0, 0.34, 0);
  cable.rotation.y = -0.38;
  g.add(cable);

  const jacketMat = new THREE.MeshStandardMaterial({ color: 0xfacc15, roughness: 0.45, metalness: 0.1 });
  const jacket = new THREE.Mesh(new THREE.CylinderGeometry(0.145, 0.145, 1.5, 32), jacketMat);
  jacket.rotation.z = Math.PI / 2;
  jacket.position.x = -1.25;
  cable.add(jacket);

  const armor = new THREE.Mesh(new THREE.CylinderGeometry(0.112, 0.112, 2.2, 24), M.steelBright);
  armor.rotation.z = Math.PI / 2;
  armor.position.x = -0.45;
  cable.add(armor);

  const glassCore = new THREE.Mesh(
    new THREE.CylinderGeometry(0.068, 0.068, 3.6, 28),
    new THREE.MeshPhysicalMaterial({ color: 0x67e8f9, emissive: 0x06b6d4, emissiveIntensity: 0.7, transparent: true, opacity: 0.85, roughness: 0.1 })
  );
  glassCore.rotation.z = Math.PI / 2;
  cable.add(glassCore);

  const pulses = [];
  for (let i = 0; i < 6; i++) {
    const p = new THREE.Mesh(
      new THREE.SphereGeometry(0.088, 20, 14),
      new THREE.MeshStandardMaterial({ color: 0xe0f2fe, emissive: 0x38bdf8, emissiveIntensity: 1.9 })
    );
    cable.add(p);
    pulses.push(p);
  }
  g.cable = cable;
  g.pulses = pulses;
  return shadow(g);
}

export function makeDatacenterRackBank(seed = 41) {
  const M = materials();
  const g = new THREE.Group();
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(7.0, 8.0), new THREE.MeshStandardMaterial({ color: 0x0b1120, roughness: 0.3, metalness: 0.5 }));
  floor.rotation.x = -Math.PI / 2;
  g.add(floor);

  const rackFace = new THREE.MeshStandardMaterial({ map: makeRackTexture(seed), emissive: 0x0ea5e9, emissiveIntensity: 0.28, roughness: 0.4 });
  const chassis = new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.75, roughness: 0.35 });

  for (let row = 0; row < 4; row++) {
    for (const side of [-1, 1]) {
      const rack = new THREE.Group();
      rack.position.set(side * 0.72, 1.0, 0.8 - row * 1.15);
      const boxM = new THREE.Mesh(new THREE.BoxGeometry(0.56, 2.0, 0.86), chassis);
      const front = new THREE.Mesh(new THREE.PlaneGeometry(0.50, 1.88), rackFace);
      front.position.x = -side * 0.282;
      front.rotation.y = -side * Math.PI / 2;
      rack.add(boxM, front);
      g.add(rack);
    }
  }
  const trunk = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.06, 4.8), M.copper);
  trunk.position.set(0, 2.12, -0.8);
  g.add(trunk);

  const packets = [];
  for (let i = 0; i < 6; i++) {
    const sp = new THREE.Mesh(new THREE.SphereGeometry(0.055, 16, 12), new THREE.MeshStandardMaterial({ color: 0x34d399, emissive: 0x34d399, emissiveIntensity: 1.7 }));
    sp.position.set(0, 2.05, 1.0 - i * 0.7);
    g.add(sp);
    packets.push(sp);
  }
  g.packets = packets;
  return shadow(g);
}

export function makePowerTurbineRig() {
  const M = materials();
  const g = new THREE.Group();
  const plinth = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.28, 1.2), M.steelDark);
  plinth.position.y = 0.14;
  g.add(plinth);
  const housing = new THREE.Mesh(new THREE.TorusGeometry(0.58, 0.09, 16, 48, Math.PI * 1.45), M.copper);
  housing.position.set(0, 1.15, 0);
  housing.rotation.z = -0.35;
  g.add(housing);
  const rotor = new THREE.Group();
  rotor.position.set(0, 1.15, 0);
  g.add(rotor);
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.34, 24), M.steelBright);
  hub.rotation.x = Math.PI / 2;
  rotor.add(hub);
  for (let k = 0; k < 8; k++) {
    const blade = new THREE.Mesh(new THREE.BoxGeometry(0.075, 0.42, 0.025), M.steel);
    const a = (k / 8) * Math.PI * 2;
    blade.position.set(Math.cos(a) * 0.30, Math.sin(a) * 0.30, 0);
    blade.rotation.z = a + 0.35;
    blade.rotation.y = 0.35;
    rotor.add(blade);
  }
  const coilGlow = new THREE.Mesh(
    new THREE.TorusGeometry(0.68, 0.022, 12, 48),
    new THREE.MeshStandardMaterial({ color: 0xfbbf24, emissive: 0xf59e0b, emissiveIntensity: 1.4 })
  );
  coilGlow.position.set(0, 1.15, 0);
  g.add(coilGlow);
  g.rotor = rotor;
  g.coilGlow = coilGlow;
  return shadow(g);
}

export function makeCosmicGenesisRig(seed = 88) {
  const r = rng(seed);
  const g = new THREE.Group();
  const starMat = new THREE.MeshStandardMaterial({ color: 0xfef08a, emissive: 0xf59e0b, emissiveIntensity: 1.9, roughness: 0.2 });
  const star = new THREE.Mesh(new THREE.IcosahedronGeometry(0.38, 4), starMat);
  g.add(star);
  const ring1 = new THREE.Mesh(
    new THREE.TorusGeometry(0.75, 0.026, 14, 72),
    new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x0284c7, emissiveIntensity: 0.85, roughness: 0.3 })
  );
  ring1.rotation.x = 1.15;
  const ring2 = new THREE.Mesh(
    new THREE.TorusGeometry(1.12, 0.018, 12, 72),
    new THREE.MeshStandardMaterial({ color: 0xfb923c, emissive: 0xea580c, emissiveIntensity: 0.75 })
  );
  ring2.rotation.set(0.75, 0.5, 0.3);
  g.add(ring1, ring2);

  const orbiters = [];
  for (let i = 0; i < 10; i++) {
    const rad = 0.55 + (i % 4) * 0.24;
    const m = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.055 + r() * 0.03, 1),
      new THREE.MeshStandardMaterial({ color: i % 2 ? 0xd9733f : 0x7dd3fc, emissive: i % 2 ? 0x9a3412 : 0x0369a1, emissiveIntensity: 0.5, metalness: 0.75, roughness: 0.25 })
    );
    m.userData.rad = rad;
    m.userData.phase = i * 0.85;
    g.add(m);
    orbiters.push(m);
  }
  for (let i = 0; i < 40; i++) {
    const theta = r() * Math.PI * 2, phi = Math.acos(2 * r() - 1);
    const d = 5.5 + r() * 6.0;
    const s = new THREE.Mesh(new THREE.SphereGeometry(0.032, 6, 6), new THREE.MeshBasicMaterial({ color: 0xf8fafc }));
    s.position.set(d * Math.sin(phi) * Math.cos(theta), d * Math.cos(phi), d * Math.sin(phi) * Math.sin(theta));
    g.add(s);
  }
  g.star = star; g.ring1 = ring1; g.ring2 = ring2; g.orbiters = orbiters;
  return g;
}

/**
 * Upgraded Stylized/Schematic Anatomical Cutaway using LayeredCutaway with real clipping plane + multi-layer structure.
 */
export function makeAnatomicalCutawayRig(isBrain = true) {
  const cutaway = new LayeredCutaway({
    id: isBrain ? 'stylized_brain_cutaway' : 'stylized_heart_cutaway',
    worldAnchor: [0, 1.25, 0.02],
    clipNormal: [0, 0, -1],
    clipConstantStart: 0.42,
    clipConstantOpen: 0.02,
  });

  const shellMat = new THREE.MeshPhysicalMaterial({
    color: 0x93c5fd, transparent: true, opacity: 0.36, roughness: 0.16, metalness: 0.08, clearcoat: 0.7, side: THREE.DoubleSide
  });
  const shell = new THREE.Mesh(new THREE.SphereGeometry(0.42, 36, 28), shellMat);
  shell.position.y = 1.25;
  cutaway.addOuterShell(shell, { applyClip: true });

  const organMat = new THREE.MeshStandardMaterial({
    color: isBrain ? 0xf472b6 : 0xe11d48,
    emissive: isBrain ? 0x9d174d : 0x881337,
    emissiveIntensity: 0.45,
    roughness: 0.42,
  });
  const lobes = [];
  if (isBrain) {
    for (const side of [-1, 1]) {
      const lobe = new THREE.Mesh(new THREE.SphereGeometry(0.20, 28, 22), organMat);
      lobe.scale.set(0.82, 1.0, 1.25);
      lobe.position.set(side * 0.11, 1.26, 0.02);
      cutaway.addInternalComponent('cortex_hemisphere_' + (side < 0 ? 'l' : 'r'), lobe, { layerIndex: 1 });
      lobes.push(lobe);
    }
    cutaway.addConnectionEdge('neural_tract', [[-0.14, 1.22, 0.05], [0.0, 1.32, 0.04], [0.14, 1.24, 0.05]], 0.010, 0xfef08a);
  } else {
    const heart = new THREE.Mesh(new THREE.SphereGeometry(0.24, 32, 24), organMat);
    heart.scale.set(0.85, 1.22, 0.85);
    heart.position.set(0, 1.22, 0.02);
    cutaway.addInternalComponent('schematic_chambers', heart, { layerIndex: 1 });
    lobes.push(heart);
    cutaway.addConnectionEdge('vessel_arch', [[-0.08, 1.12, 0.04], [0.0, 1.42, 0.04], [0.10, 1.18, 0.04]], 0.014, 0xef4444);
  }
  cutaway.addFlowPulseOnEdge(0, 0xfef08a, 0.022, 0.0);
  cutaway.addFlowPulseOnEdge(0, 0xfef08a, 0.022, 0.5);

  const root = shadow(cutaway.root);
  root.cutaway = cutaway;
  root.lobes = lobes;
  root.representation = 'schematic/stylized';
  return root;
}

export function makeVaultGearStage() {
  const M = materials();
  const RM = romanMaterials();
  const g = new THREE.Group();
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.62, 0.24, 36), M.steelDark);
  base.position.y = 0.12;
  g.add(base);
  const gears = [];
  for (let idx = 0; idx < 3; idx++) {
    const gear = new THREE.Group();
    const r = 0.26 - idx * 0.05;
    const rimM = new THREE.Mesh(new THREE.TorusGeometry(r, 0.032, 10, 28), idx % 2 ? RM.bronze : M.steelBright);
    gear.add(rimM);
    for (let t = 0; t < 10; t++) {
      const tooth = new THREE.Mesh(new THREE.BoxGeometry(0.045, 0.06, 0.045), idx % 2 ? RM.bronze : M.steelBright);
      const a = (t / 10) * Math.PI * 2;
      tooth.position.set(Math.cos(a) * (r + 0.04), Math.sin(a) * (r + 0.04), 0);
      tooth.rotation.z = a;
      gear.add(tooth);
    }
    gear.position.set((idx - 1) * 0.28, 0.88 + idx * 0.24, (idx - 1) * 0.06);
    g.add(gear);
    gears.push(gear);
  }
  g.gears = gears;
  return shadow(g);
}
"""


DIRECTOR_MAIN_JS = r"""import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { SHOTS, CAPTIONS, DURATION, FADES, TRANSITIONS } from './shots.js';
import { EDITORIAL_TIMELINE } from './editorial_timeline.js';
import { EditorialOverlayController } from './editorial_overlay_renderer.js';

const params = new URLSearchParams(location.search);
const SCALE = Math.max(1, Number(params.get('scale') || 1));
const W = 1080, H = 1920;

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(SCALE);
renderer.setSize(W, H, false);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.03;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.localClippingEnabled = true;
document.getElementById('stage').prepend(renderer.domElement);

const SKY_FRAG = `
  uniform vec3 top, mid, horizon, floorC; varying vec3 vDir;
  void main(){
    vec3 d = normalize(vDir);
    float y = d.y;
    vec3 c = y > 0.0 ? mix(mix(horizon, mid, smoothstep(0.0,0.12,y)), top, smoothstep(0.1,0.8,y))
                     : mix(horizon, floorC, smoothstep(0.0,-0.08,y));
    gl_FragColor = vec4(c,1.0);
    #include <colorspace_fragment>
  }`;
const SKY_THEMES = {
  day: { top: 0x2b78d6, mid: 0x5b9fea, horizon: 0x92c3f2, floorC: 0xa9cdf1, sun: 2.35, hemi: 0.78 },
  dusk: { top: 0x161b3a, mid: 0x3b2e5a, horizon: 0xc26d4a, floorC: 0x3a2d36, sun: 1.85, hemi: 0.55 },
  ocean_deep: { top: 0x041c2c, mid: 0x0a3d5c, horizon: 0x156585, floorC: 0x092433, sun: 1.60, hemi: 0.65 },
  datacenter_dark: { top: 0x060b16, mid: 0x0f172a, horizon: 0x1e293b, floorC: 0x090f1a, sun: 1.75, hemi: 0.58 },
  cosmic: { top: 0x02040a, mid: 0x090d22, horizon: 0x1b1536, floorC: 0x050712, sun: 1.90, hemi: 0.48 },
  lab_studio: { top: 0x1e3a5f, mid: 0x355c7d, horizon: 0x6c8ead, floorC: 0x2b3e50, sun: 2.25, hemi: 0.80 },
  boston_overcast: { top: 0x5c6d7e, mid: 0x8998a6, horizon: 0xb7c0c7, floorC: 0x6c747a, sun: 1.95, hemi: 0.88 },
  boston_amber: { top: 0x262938, mid: 0x5a4648, horizon: 0xb37452, floorC: 0x3d302c, sun: 2.05, hemi: 0.65 },
  tacoma_overcast: { top: 0x4b5f73, mid: 0x7b90a4, horizon: 0xb4c2cf, floorC: 0x364a59, sun: 2.05, hemi: 0.86 },
  tacoma_storm: { top: 0x2b3b4e, mid: 0x4c6074, horizon: 0x8c9aa6, floorC: 0x22323f, sun: 1.90, hemi: 0.76 },
  tacoma_aftermath: { top: 0x354354, mid: 0x64788c, horizon: 0xa4b3c0, floorC: 0x283846, sun: 1.75, hemi: 0.82 },
};

function skyMaterial(theme = 'day') {
  const cfg = SKY_THEMES[theme] || SKY_THEMES.day;
  return new THREE.ShaderMaterial({
    uniforms: {
      top: { value: new THREE.Color(cfg.top) }, mid: { value: new THREE.Color(cfg.mid) },
      horizon: { value: new THREE.Color(cfg.horizon) }, floorC: { value: new THREE.Color(cfg.floorC) },
    },
    vertexShader: `varying vec3 vDir; void main(){ vDir = (modelMatrix*vec4(position,1.)).xyz - cameraPosition; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.); gl_Position.z = gl_Position.w; }`,
    fragmentShader: SKY_FRAG, side: THREE.BackSide, depthWrite: false, toneMapped: false,
  });
}

const pmrem = new THREE.PMREMGenerator(renderer);
const envScene = new THREE.Scene();
{
  const s = new THREE.Mesh(new THREE.SphereGeometry(20, 32, 16), skyMaterial('day'));
  s.material.toneMapped = true; envScene.add(s);
  const panel = (w, h, pos, inten) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(inten, inten, inten), side: THREE.DoubleSide }));
    m.position.set(...pos); m.lookAt(0, 0, 0); envScene.add(m);
  };
  panel(8, 4, [-6, 8, 6], 3.0);
  panel(4, 10, [9, 3, -2], 1.5);
}
const envTex = pmrem.fromScene(envScene, 0.02).texture;

export function makeStage({ shadowSize = 3, sunDir = [-3, 6, 4], sun = null, skyTheme = 'day', showShadowFloor = true } = {}) {
  const th = SKY_THEMES[skyTheme] || SKY_THEMES.day;
  const scene = new THREE.Scene();
  scene.environment = envTex;
  scene.environmentIntensity = skyTheme === 'cosmic' ? 0.65 : 1.0;
  const sky = new THREE.Mesh(new THREE.SphereGeometry(80, 32, 16), skyMaterial(skyTheme));
  sky.frustumCulled = false; sky.renderOrder = -10;
  scene.add(sky); scene.userData.sky = sky;
  if (showShadowFloor) {
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), new THREE.ShadowMaterial({ color: 0x0c1b33, opacity: 0.30 }));
    ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);
  }
  scene.add(new THREE.HemisphereLight(0xcfe4ff, 0x4b5c73, th.hemi));
  const key = new THREE.DirectionalLight(0xfff3e6, sun ?? th.sun);
  key.position.set(...sunDir); key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  const c = key.shadow.camera; c.left = c.bottom = -shadowSize; c.right = c.top = shadowSize; c.near = 0.5; c.far = 30;
  key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02;
  scene.add(key, key.target);
  const rim = new THREE.DirectionalLight(0xdbe9ff, 1.25); rim.position.set(4, 3, -5); scene.add(rim);
  return scene;
}

const rt = new THREE.WebGLRenderTarget(W * SCALE, H * SCALE, { samples: SCALE >= 2 ? 0 : 2, type: THREE.HalfFloatType });
const rtA = new THREE.WebGLRenderTarget(W * SCALE, H * SCALE, { type: THREE.HalfFloatType });
const rtB = new THREE.WebGLRenderTarget(W * SCALE, H * SCALE, { type: THREE.HalfFloatType });

const compositeMat = new THREE.ShaderMaterial({
  uniforms: {
    tA: { value: rtA.texture },
    tB: { value: rtB.texture },
    uAlpha: { value: 0.0 },
    uMode: { value: 0 }, // 1=zoom_through, 2=match_cut, 3=object_wipe, 4=whip_pan
    uAnchorA: { value: new THREE.Vector2(0.5, 0.5) },
    uAnchorB: { value: new THREE.Vector2(0.5, 0.5) },
  },
  vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
  fragmentShader: `
    uniform sampler2D tA, tB;
    uniform float uAlpha;
    uniform int uMode;
    uniform vec2 uAnchorA, uAnchorB;
    varying vec2 vUv;
    void main(){
      float p = clamp(uAlpha, 0.0, 1.0);
      if (uMode == 1) {
        // True 2-source zoom_through portal bridge: outgoing plunges toward anchorA while incoming opens radially
        float sA = mix(1.0, 0.42, p * p);
        float sB = mix(1.85, 1.0, smoothstep(0.0, 1.0, p));
        vec2 uvA = clamp(uAnchorA + (vUv - uAnchorA) * sA, 0.001, 0.999);
        vec2 uvB = clamp(uAnchorB + (vUv - uAnchorB) * sB, 0.001, 0.999);
        vec4 colA = texture2D(tA, uvA);
        vec4 colB = texture2D(tB, uvB);
        float d = length((vUv - uAnchorA) * vec2(0.5625, 1.0));
        float rad = p * 1.25;
        float portal = smoothstep(rad + 0.16, rad - 0.16, d) * smoothstep(0.0, 0.30, p);
        float mixF = clamp(max(portal, smoothstep(0.62, 1.0, p)), 0.0, 1.0);
        gl_FragColor = mix(colA, colB, mixF);
      } else if (uMode == 2) {
        // True 2-source match_cut: aligns focal centroids & dissolves cleanly
        vec2 dA = (uAnchorB - uAnchorA) * (p * 0.35);
        vec2 dB = (uAnchorA - uAnchorB) * ((1.0 - p) * 0.35);
        vec4 colA = texture2D(tA, clamp(vUv - dA, 0.001, 0.999));
        vec4 colB = texture2D(tB, clamp(vUv - dB, 0.001, 0.999));
        float m = smoothstep(0.05, 0.95, p);
        gl_FragColor = mix(colA, colB, m);
      } else if (uMode == 3) {
        // True 2-source object_wipe: physical bevel divider sweeps left->right revealing target scene
        float cutX = p * 1.18 - 0.09;
        float edge = vUv.x + (vUv.y - 0.5) * 0.14;
        float maskB = 1.0 - smoothstep(cutX - 0.018, cutX + 0.018, edge);
        float bar = smoothstep(0.026, 0.0, abs(edge - cutX));
        vec4 colA = texture2D(tA, vUv);
        vec4 colB = texture2D(tB, vUv);
        vec3 mixed = mix(colA.rgb, colB.rgb, maskB);
        mixed = mix(mixed, vec3(0.10, 0.16, 0.26), bar * 0.85);
        gl_FragColor = vec4(mixed, 1.0);
      } else if (uMode == 4) {
        // True 2-source whip_pan: directional horizontal handoff + motion smear across both shots
        float shift = p;
        vec4 acc = vec4(0.0);
        float blurAmt = sin(p * 3.14159) * 0.022;
        for (int i = -2; i <= 2; i++) {
          float ox = float(i) * blurAmt;
          vec2 uA = vec2(vUv.x + shift * 0.85 + ox, vUv.y);
          vec2 uB = vec2(vUv.x - (1.0 - shift) * 0.85 + ox, vUv.y);
          vec4 cA = (uA.x >= 0.0 && uA.x <= 1.0) ? texture2D(tA, clamp(uA, 0.001, 0.999)) : texture2D(tB, clamp(uB, 0.001, 0.999));
          vec4 cB = (uB.x >= 0.0 && uB.x <= 1.0) ? texture2D(tB, clamp(uB, 0.001, 0.999)) : texture2D(tA, clamp(uA, 0.001, 0.999));
          acc += mix(cA, cB, smoothstep(0.25, 0.75, p));
        }
        gl_FragColor = acc * 0.20;
      } else {
        gl_FragColor = mix(texture2D(tA, vUv), texture2D(tB, vUv), p);
      }
    }`,
  depthTest: false, depthWrite: false, toneMapped: false,
});
const compositeScene = new THREE.Scene();
const compositeCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
compositeScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), compositeMat));

const composer = new EffectComposer(renderer, rt);
const renderPass = new RenderPass(new THREE.Scene(), new THREE.PerspectiveCamera());
const bloom = new UnrealBloomPass(new THREE.Vector2(W * SCALE, H * SCALE), 0.22, 0.4, 1.5);
const grade = new ShaderPass({
  uniforms: {
    tDiffuse: { value: null },
    uVig: { value: 0.24 },
  },
  vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader: `uniform sampler2D tDiffuse; uniform float uVig; varying vec2 vUv;
    void main(){
      gl_FragColor = texture2D(tDiffuse, vUv);
      vec2 q = vUv - 0.5; q.x *= 0.5625;
      gl_FragColor.rgb *= 1.0 - uVig * smoothstep(0.18, 0.62, length(q));
    }`,
});
composer.addPass(renderPass);
composer.addPass(bloom);
composer.addPass(new OutputPass());
composer.addPass(grade);

const capEl = document.getElementById('cap');
const fadeEl = document.getElementById('fade');
const overlayCtrl = new EditorialOverlayController(document.getElementById('stage'), capEl, EDITORIAL_TIMELINE);
const built = new Map();
function getShot(i) {
  if (!built.has(i)) built.set(i, SHOTS[i].build({ makeStage, W, H }));
  return built.get(i);
}

window.TOTAL_DURATION = DURATION;
window.SHOT_SPANS = SHOTS.map(s => [s.start, s.end]);

function findActiveTransition(t) {
  for (let k = 0; k < (TRANSITIONS || []).length; k++) {
    const tr = TRANSITIONS[k];
    if (!tr || !tr.duration || tr.duration <= 0) continue;
    const half = tr.duration * 0.5;
    const t0 = tr.boundary - half;
    const t1 = tr.boundary + half;
    if (t >= t0 && t <= t1) {
      const alpha = Math.max(0, Math.min(1, (t - t0) / Math.max(1e-5, t1 - t0)));
      return { ...tr, alpha, index: k };
    }
  }
  return null;
}

const MODE_CODES = { zoom_through: 1, match_cut: 2, object_wipe: 3, whip_pan: 4 };

window.renderAtTime = (rawT) => {
  const t = Math.max(0, Math.min(rawT, DURATION - 1e-4));
  let idx = SHOTS.findIndex(s => t >= s.start && t < s.end);
  if (idx < 0) idx = SHOTS.length - 1;
  const def = SHOTS[idx];
  const shot = getShot(idx);
  const lt = Math.max(0, t - def.start);

  const activeTr = findActiveTransition(t);
  const trCode = activeTr ? (MODE_CODES[activeTr.method] || 0) : 0;

  let camTel = null;
  let contactTel = null;
  let cutawayTel = null;
  let narrativeActionTel = null;
  let physMotionTel = null;
  let charPerfTel = null;
  let shotAnchors = {};
  let trTel = { active: false, method: def.tr || 'cut', alpha: 0.0, from_shot: def.id, to_shot: null };

  if (activeTr && trCode > 0 && activeTr.from_idx < SHOTS.length - 1) {
    const iA = activeTr.from_idx;
    const iB = activeTr.to_idx;
    const defA = SHOTS[iA];
    const defB = SHOTS[iB];
    const shotA = getShot(iA);
    const shotB = getShot(iB);
    const ltA = Math.max(0.0, Math.min(defA.end - defA.start, t - defA.start));
    const ltB = Math.max(0.0, Math.min(defB.end - defB.start, t - defB.start));

    const trOptsA = trCode === 1
      ? { transitionFovScale: 1.0 - 0.24 * activeTr.alpha * activeTr.alpha }
      : (trCode === 4 ? { transitionYawDelta: 0.36 * activeTr.alpha * activeTr.alpha } : {});
    const trOptsB = trCode === 1
      ? { transitionFovScale: 1.0 + 0.22 * (1 - activeTr.alpha) * (1 - activeTr.alpha) }
      : (trCode === 4 ? { transitionYawDelta: -0.36 * (1 - activeTr.alpha) * (1 - activeTr.alpha) } : {});

    const rA = shotA.update(ltA, t, trOptsA) || {};
    const rB = shotB.update(ltB, t, trOptsB) || {};

    shotA.scene.userData.sky.position.copy(shotA.camera.position);
    shotB.scene.userData.sky.position.copy(shotB.camera.position);

    const prevRT = renderer.getRenderTarget();
    renderer.setRenderTarget(rtA);
    renderer.clear();
    renderer.render(shotA.scene, shotA.camera);
    renderer.setRenderTarget(rtB);
    renderer.clear();
    renderer.render(shotB.scene, shotB.camera);
    renderer.setRenderTarget(prevRT);

    const fuvA = rA.camTel?.focal_anchor_uv;
    const fuvB = rB.camTel?.focal_anchor_uv;
    compositeMat.uniforms.uAlpha.value = activeTr.alpha;
    compositeMat.uniforms.uMode.value = trCode;
    if (fuvA && fuvA.in_front) compositeMat.uniforms.uAnchorA.value.set(Math.max(0.15, Math.min(0.85, fuvA.u)), 1.0 - Math.max(0.15, Math.min(0.85, fuvA.v)));
    else compositeMat.uniforms.uAnchorA.value.set(0.5, 0.5);
    if (fuvB && fuvB.in_front) compositeMat.uniforms.uAnchorB.value.set(Math.max(0.15, Math.min(0.85, fuvB.u)), 1.0 - Math.max(0.15, Math.min(0.85, fuvB.v)));
    else compositeMat.uniforms.uAnchorB.value.set(0.5, 0.5);

    renderPass.scene = compositeScene;
    renderPass.camera = compositeCam;
    const rMain = idx === iA ? rA : rB;
    camTel = rMain.camTel || null;
    contactTel = rMain.contact || null;
    cutawayTel = rMain.cutaway || null;
    narrativeActionTel = rMain.narrativeAction || null;
    physMotionTel = rMain.physicalMotion || null;
    charPerfTel = rMain.characterPerformance || null;
    shotAnchors = { ...(rMain.anchors || {}), default: camTel?.focal_anchor_uv || null };
    bloom.strength = ((rMain.bloom ?? 0.30) * 0.52);
    renderer.toneMappingExposure = rMain.exposure ?? 1.03;
    composer.render();

    trTel = {
      active: true,
      transition_id: activeTr.transition_id,
      method: activeTr.method,
      alpha: Number(activeTr.alpha.toFixed(4)),
      from_shot: defA.id,
      to_shot: defB.id,
      anchor_a_uv: [Number(compositeMat.uniforms.uAnchorA.value.x.toFixed(4)), Number(compositeMat.uniforms.uAnchorA.value.y.toFixed(4))],
      anchor_b_uv: [Number(compositeMat.uniforms.uAnchorB.value.x.toFixed(4)), Number(compositeMat.uniforms.uAnchorB.value.y.toFixed(4))],
    };
  } else {
    const r = shot.update(lt, t, {}) || {};
    const cam = shot.camera;
    shot.scene.userData.sky.position.copy(cam.position);
    renderPass.scene = shot.scene;
    renderPass.camera = cam;
    bloom.strength = (r.bloom ?? 0.30) * 0.52;
    renderer.toneMappingExposure = r.exposure ?? 1.03;
    composer.render();
    camTel = r.camTel || null;
    contactTel = r.contact || null;
    cutawayTel = r.cutaway || null;
    narrativeActionTel = r.narrativeAction || null;
    physMotionTel = r.physicalMotion || null;
    charPerfTel = r.characterPerformance || null;
    shotAnchors = { ...(r.anchors || {}), default: camTel?.focal_anchor_uv || null };
  }

  const ovTel = overlayCtrl.renderAtTime(t, shotAnchors);

  window.__LAST_RENDER_TELEMETRY__ = {
    time_sec: Number(t.toFixed(4)),
    shot_index: idx,
    shot_id: def.id,
    camera: camTel,
    transition: trTel,
    contact: contactTel,
    cutaway: cutawayTel,
    narrative_action: narrativeActionTel,
    physical_motion: physMotionTel,
    character_performance: charPerfTel,
    anchors: shotAnchors,
    overlay: ovTel,
  };

  let f = 0;
  for (const [a, b, c2, d] of FADES) {
    if (t >= a && t < d) f = Math.max(f, t < b ? (t - a) / (b - a) : t < c2 ? 1 : (d - t) / (d - c2));
  }
  fadeEl.style.opacity = f;
  return idx;
};

window.SHORT_DIRECTOR_READY = document.fonts.ready.then(() => { window.renderAtTime(0); return true; });
"""


def _build_captions_list(words: List[Dict[str, Any]]) -> List[List[Any]]:
    out: List[List[Any]] = []
    cur: List[Dict[str, Any]] = []
    for i, w in enumerate(words):
        cur.append(w)
        txt = " ".join(x["w"] for x in cur)
        stop = txt.endswith((".", ",", "?", "!", ";", ":"))
        if stop or len(cur) >= 3 or len(txt) >= 18:
            clean = txt.rstrip(".,;:")
            entry: List[Any] = [round(cur[0]["s"], 3), clean]
            if i == len(words) - 1:
                entry.append(round(cur[-1]["e"] + 0.35, 3))
            out.append(entry)
            cur = []
    if cur:
        clean = " ".join(x["w"] for x in cur).rstrip(".,;:")
        out.append([round(cur[0]["s"], 3), clean, round(cur[-1]["e"] + 0.35, 3)])
    return out


def _cam_helper_js(cam_path: Dict[str, Any] | None, fallback_pos: List[float], fallback_look: List[float], fallback_fov: int) -> str:
    kfs = (cam_path or {}).get("keyframes") or [
        {"t_norm": 0.0, "pos": fallback_pos, "look": fallback_look, "fov": fallback_fov, "roll": 0.0, "ease": "quintic"},
        {"t_norm": 1.0, "pos": fallback_pos, "look": fallback_look, "fov": fallback_fov, "roll": 0.0, "ease": "quintic"},
    ]
    return json.dumps(kfs)


def _anchor_helper_js(shot: Dict[str, Any]) -> str:
    fa = shot.get("focal_anchor") or (shot.get("camera_path") or {}).get("focal_anchor") or {"anchor_id": "stage_center", "world_pos": [0.0, 1.18, 0.0], "radius_m": 0.25}
    return json.dumps(fa)


def _roman_shot_code(i: int, shot: Dict[str, Any], total_shots: int) -> str:
    start, end = shot["start"], shot["end"]
    dur = max(0.2, round(end - start, 3))
    low = shot["narration_text"].lower()
    setup = shot["setup_type"]
    kfs_json = _cam_helper_js(shot.get("camera_path"), [-0.35, 1.26, 4.05], [0.0, 0.90, 0.10], 39)
    anchor_json = _anchor_helper_js(shot)

    if i == 0:
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.5, sunDir: [-3, 7, 5] }});
  scene.add(arenaStage({{ radius: 4.5, wallArc: true }}));
  const fighter = makeHuman('vest'); addGladiatorBracers(fighter);
  fighter.root.position.set(-0.46, 0, 0.16); fighter.root.rotation.y = 1.08; scene.add(fighter.root);
  const fHelm = romanHelmet(0xc92a2a); fighter.j.head.add(fHelm);
  const fSh = romanScutum(); fighter.j.lEl.add(fSh); fSh.position.set(0.08, -0.15, 0.06); fSh.rotation.set(0, 1.15, 0); fSh.scale.setScalar(0.84);
  const fSw = sword(); fighter.j.rWr.add(fSw); fSw.position.set(0, -0.065, 0); fSw.rotation.x = Math.PI / 2;
  const opp = makeHuman('plate'); addGladiatorBracers(opp);
  opp.root.position.set(0.46, 0, -0.14); opp.root.rotation.y = -1.78; scene.add(opp.root);
  const oHelm = romanHelmet(0xd9a441); opp.j.head.add(oHelm);
  const oSw = sword(); opp.j.rWr.add(oSw); oSw.position.set(0, -0.065, 0); oSw.rotation.x = Math.PI / 2;
  const ped = romanPlinth(0.55, 0.24); ped.position.set(0.02, 0, 0.72); scene.add(ped);
  const coins = denariusStack({{ count: 14, radius: 0.065, height: 0.017, gold: true }});
  coins.position.set(0.02, 0.56, 0.72); scene.add(coins);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 39);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const bob = Math.sin(lt * 3.1) * 0.03;
      fighter.setPose({{
        ...STAND, drop: -0.09 + bob * 0.4,
        spine: [0.12, 0.18, 0], chest: [0.06, 0.14, 0],
        lHip: [-0.28, 0, 0.14], lKn: [0.42, 0, 0], rHip: [0.16, 0, -0.14], rKn: [0.22, 0, 0],
        lSh: [-0.55, 0.25, 0.25], lEl: [-0.85, 0, 0], rSh: [-0.45, -0.1, -0.32], rEl: [-0.62, 0, 0],
      }});
      opp.setPose({{
        ...STAND, drop: -0.08 - bob * 0.4,
        spine: [0.12, -0.18, 0], chest: [0.08, -0.14, 0],
        lHip: [-0.26, 0, 0.14], lKn: [0.40, 0, 0], rHip: [0.20, 0, -0.14], rKn: [0.24, 0, 0],
        rSh: [-0.82 + Math.sin(lt * 2.2) * 0.08, 0, -0.22], rEl: [-0.72, 0, 0], lSh: [-0.35, 0, 0.3], lEl: [-0.8, 0, 0],
      }});
      coins.rotation.y = lt * 0.85;
      const pop = easeOut(clamp(u * 2.2, 0, 1));
      coins.scale.set(1, Math.max(0.05, pop), 1);
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.34, camTel }};
    }}
  }};
}}"""

    if "final blow" in low or "doesn't come" in low or setup == "novel_slowmo_ripple_cutaway":
        TI = round(dur * 0.46, 3)
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 2.2, sunDir: [-2, 6, 5] }});
  scene.add(arenaStage({{ radius: 4.2, wallArc: false }}));
  const fallen = makeHuman('vest'); addGladiatorBracers(fallen);
  fallen.root.position.set(0.0, 0, 0.15); fallen.root.rotation.y = 0.25; scene.add(fallen.root);
  const disc = new THREE.Mesh(new THREE.CircleGeometry(0.28, 36), new THREE.MeshBasicMaterial({{ visible: false }}));
  disc.position.set(0.02, 0.82, 0.29); scene.add(disc);
  const rp = rippleOverlay(disc);
  const sw = sword(); scene.add(sw);
  const sp = sparks(85, {{ speed: 0.42, spread: 1.4, gravity: -0.35, life: 0.9, size: 0.008, seed: 29, dir: V(0, 0.4, 1), color: [1, 0.32, 0.14] }});
  sp.position.set(0.02, 0.84, 0.30); scene.add(sp);
  const tab = romanScrollTablet('BLOW', 'HALTED', 0xff4d4d);
  tab.scale.setScalar(0.46); tab.position.set(0.02, 1.32, 0.08); scene.add(tab);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 36);
  const TI = {TI};
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const before = easeOut(clamp(lt / TI, 0, 1));
      const hitT = lt - TI;
      const tremble = hitT > 0 ? Math.sin(hitT * 26) * Math.exp(-hitT * 2.2) * 0.014 : 0;
      fallen.setPose({{
        drop: -0.48, pelvis: [-0.25, 0.1, 0], spine: [-0.24, 0, 0], chest: [-0.15 + tremble, 0, 0],
        neck: [-0.28, 0.15, 0], head: [-0.22, 0.12, 0],
        lHip: [-1.2, 0, 0.18], lKn: [1.6, 0, 0], rHip: [-0.8, 0, -0.16], rKn: [1.4, 0, 0],
        lSh: [-0.95, 0.1, 0.35], lEl: [-0.75, 0, 0], rSh: [-0.95, -0.1, -0.35], rEl: [-0.75, 0, 0],
      }});
      fallen.setMouth(hitT < 0 ? 0.65 * before : lerp(0.65, 0.22, clamp(hitT * 1.4, 0, 1)));
      const stopTarget = V(0.02, 0.84, 0.34);
      const bladeDir = V(-0.42, -0.82, -0.38).normalize();
      const swDist = lerp(0.88, 0.05, before) + tremble;
      const tipPos = stopTarget.clone().addScaledVector(bladeDir, -swDist);
      sw.quaternion.setFromUnitVectors(V(0, 1, 0), bladeDir);
      sw.position.copy(tipPos).addScaledVector(bladeDir, -0.94);
      const ru = rp.material.uniforms;
      ru.uCenter.value.set(0, 0, 0);
      ru.uAmp.value = hitT > 0 ? Math.min(1.0, hitT * 4.5) * (1.0 - 0.35 * smooth(range(hitT, 0.8, 2.0))) : 0.0;
      ru.uRadius.value = hitT > 0 ? 0.04 + easeOut(range(hitT, 0, 1.2)) * 0.24 : 0.0;
      ru.uRings.value = 180.0; ru.uSpot.value = 0.045; ru.uSpotAmp.value = 1.1; ru.uTime.value = lt * 0.8;
      tab.scale.setScalar(hitT > 0.05 ? 0.48 * easeOut(clamp((hitT - 0.05) * 4, 0, 1)) : 0.001);
      sp.update(hitT);
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: hitT > 0 && hitT < 0.35 ? 0.62 : 0.34, camTel }};
    }}
  }};
}}"""

    if "fifty times" in low or "catch" in low or setup == "mechanism_cross_section_3d":
        TSLAM = round(dur * 0.24, 3)
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 3.5, sunDir: [-3, 7, 4] }});
  scene.add(arenaStage({{ radius: 4.3, wallArc: true }}));
  const scaleObj = balanceScale50x();
  scaleObj.position.set(0, 0.0, 0.05);
  scene.add(scaleObj);
  const rippleDisc = new THREE.Mesh(new THREE.CircleGeometry(0.45, 36), new THREE.MeshBasicMaterial({{ visible: false }}));
  rippleDisc.rotation.x = -Math.PI / 2; rippleDisc.position.set(0.32, 0.05, 0.05); scene.add(rippleDisc);
  const rp = rippleOverlay(rippleDisc);
  const sp = sparks(110, {{ speed: 1.5, spread: 1.6, gravity: -3.5, life: 0.75, size: 0.015, seed: 50, color: [1.0, 0.78, 0.18] }});
  sp.position.set(0.32, 0.92, 0.05); scene.add(sp);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 39);
  const TSLAM = {TSLAM};
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const dropProgress = easeOut(clamp((lt - TSLAM) / 0.35, 0, 1));
      const bounce = lt > TSLAM ? Math.exp(-(lt - TSLAM) * 5.2) * Math.sin((lt - TSLAM) * 18) * 0.08 : 0;
      scaleObj.stack50x.coins.forEach((cn, idx) => {{
        const reveal = clamp(dropProgress * 24 - idx * 0.45, 0, 1);
        cn.visible = reveal > 0.02; cn.scale.setScalar(easeOut(reveal));
      }});
      scaleObj.setTilt(-0.34 * dropProgress + bounce);
      const it = lt - TSLAM;
      const ru = rp.material.uniforms;
      ru.uCenter.value.set(0, 0, 0);
      ru.uAmp.value = it > 0 ? Math.min(1.0, it * 5.0) * (1.0 - 0.25 * smooth(range(it, 0.9, 2.5))) : 0.0;
      ru.uRadius.value = it > 0 ? 0.06 + easeOut(range(it, 0, 1.2)) * 0.38 : 0.0;
      ru.uRings.value = 150.0; ru.uSpot.value = 0.06; ru.uSpotAmp.value = 0.9; ru.uTime.value = lt;
      sp.update(it - 0.15);
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: it > 0 && it < 0.4 ? 0.58 : 0.34, camTel }};
    }}
  }};
}}"""

    # Generic Roman arena messenger / organizer shot (safe per-shot!)
    return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.0, sunDir: [-2.5, 6.5, 4] }});
  scene.add(arenaStage({{ radius: 4.5, wallArc: true }}));
  const org = makeHuman('vest'); addGladiatorBracers(org);
  org.root.position.set(-0.28, 0, 0.10); org.root.rotation.y = 0.28; scene.add(org.root);
  org.j.chest.add(togaSash());
  const plinth = romanPlinth(0.84, 0.20); plinth.position.set(0.30, 0, 0.16); scene.add(plinth);
  const coins = denariusStack({{ count: 14, radius: 0.068, height: 0.017, gold: true }});
  coins.position.set(0.30, 0.85, 0.16); scene.add(coins);
  const badge = romanScrollTablet('ROME', 'ARENA', 0xf4c430);
  badge.scale.setScalar(0.48); badge.position.set(0.28, 1.54, 0.16); scene.add(badge);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 39);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      org.setPose({{
        ...STAND,
        chest: [Math.sin(lt * 2.1) * 0.02, -0.14, 0], head: [0.04, -0.20 + Math.sin(lt * 3.0) * 0.08, 0],
        rSh: [-0.58 - easeOut(u) * 0.18, 0, -0.26], rEl: [-0.55, 0, 0],
      }});
      org.setMouth(0.20 + 0.18 * Math.abs(Math.sin(lt * 6.0)));
      coins.rotation.y = lt * 0.95;
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.34, camTel }};
    }}
  }};
}}"""


def _build_non_roman_scene_shot_code(
    i: int,
    s: Dict[str, Any],
    total_shots: int,
    seed: int = 42,
    char_registry: Dict[str, Any] | None = None,
) -> str:
    start, end = s["start"], s["end"]
    dur = max(0.2, round(end - start, 3))
    gen = str(s.get("procedural_generator") or "")
    prop = str((s.get("staging") or {}).get("visual_metaphor") or "idea_spark")
    nar_low = str(s.get("narration_text") or "").lower()
    is_callback = bool(s.get("callback_reason"))
    cam_path = s.get("camera_path")
    kfs_json = _cam_helper_js(cam_path, [0.4, 1.38, 2.0], [0.0, 1.18, 0.0], 34)
    anchor_json = _anchor_helper_js(s)

    creg = char_registry or {}
    cid = str((s.get("staging") or {}).get("character_id") or "char_protagonist_01")
    char_spec = creg.get(cid) or {"character_id": cid, "shirt_hex": 0x2563EB, "pants_hex": 0x1E293B, "collar_hex": 0xE2E8F0}
    char_spec_json = json.dumps(char_spec)

    contact_spec = (s.get("staging") or {}).get("contact_action")
    contact_json = json.dumps(contact_spec) if contact_spec else json.dumps({
        "verb": "press_button",
        "performer_id": cid,
        "target_id": "call_button_01",
        "hit_time_rel_sec": round(dur * 0.44, 3),
        "hold_duration_sec": 0.16,
        "target_world": [0.24, 1.16, 0.24],
        "target_normal": [-1.0, 0.0, 0.0],
        "target_radius_m": 0.028,
        "button_depress_m": 0.008,
    })

    if gen.startswith("zach3d:tacoma_"):
        cfg_map = {
            "zach3d:tacoma_hook_telephoto_stage": ("tacoma_overcast", "bridge_hook_initial_sway", "tacoma_midspan_telephoto_hook", "{ mode: 'wobble_hook', verticalAmp: 0.16, torsionRad: 0.18 }", False, False, 0.24),
            "zach3d:tacoma_wide_establish_stage": ("tacoma_overcast", "strait_wide_establish", "tacoma_narrows_strait_1940", "{ mode: 'vertical_wave', verticalAmp: 0.14, torsionRad: 0.10 }", True, False, 0.24),
            "zach3d:tacoma_roadway_wave_stage": ("tacoma_overcast", "bridge_vertical_bounce", "tacoma_roadway_center_deck", "{ mode: 'vertical_wave', verticalAmp: 0.28, torsionRad: 0.08 }", False, False, 0.25),
            "zach3d:tacoma_under_deck_girder_stage": ("tacoma_storm", "plate_girder_wind_loading", "tacoma_under_deck_girder_bay", "{ mode: 'vertical_wave', verticalAmp: 0.16, torsionRad: 0.18 }", False, True, 0.28),
            "zach3d:tacoma_torsion_twist_stage": ("tacoma_storm", "torsional_flutter_escalation", "tacoma_midspan_torsion_zone_1940", "{ mode: 'torsion_heavy', verticalAmp: 0.18, torsionRad: 0.40 }", False, False, 0.30),
            "zach3d:tacoma_collapse_plunge_stage": ("tacoma_storm", "bridge_span_collapse", "tacoma_center_span_collapse_1940", f"{{ mode: 'collapse', verticalAmp: 0.18, torsionRad: 0.38, collapseOnsetSec: {round(dur * 0.38, 3)} }}", True, False, 0.34),
            "zach3d:tacoma_aftermath_stage": ("tacoma_aftermath", "bridge_collapse_aftermath", "tacoma_narrows_aftermath_wide_1940", "{ mode: 'aftermath', verticalAmp: 0.02, torsionRad: 0.03, aftermathCollapsed: true }", True, False, 0.22),
        }
        if gen == "zach3d:tacoma_shore_onlooker_stage":
            return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.5, skyTheme: 'tacoma_storm', sunDir: [-3, 7, 5] }});
  const env = makePugetSoundEnvironment({{ includeShore: false }});
  env.root.position.set(0, -1.8, -5.5);
  scene.add(env.root);
  const bgBridge = makeTacomaSuspensionBridgeRig({{ deckBaseY: 0.9, spanLength: 14.0, nSegments: 18, includeCar: false }});
  bgBridge.root.position.set(0, 0, -6.5);
  scene.add(bgBridge.root);
  const shore = makeTacomaShoreOnlookerRig(makeHuman, {char_spec_json});
  scene.add(shore.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 36);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      env.update(lt, 0.0);
      const bTel = bgBridge.update(lt, {dur}, {{ mode: 'torsion_heavy', verticalAmp: 0.20, torsionRad: 0.42 }});
      const cTel = shore.update(lt, {dur}, [0, 2.2, -6.5]);
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      const anchors = {{ ...shore.getAnchorsTelemetry(c), ...bgBridge.getAnchorsTelemetry(c) }};
      return {{
        bloom: 0.26, camTel, anchors,
        physicalMotion: bTel,
        characterPerformance: cTel,
        narrativeAction: getNarrativeActionTelemetry({{
          locationId: 'tacoma_west_shore_approach_1940',
          physicalAction: 'shore_onlooker_reaction',
          actorCount: 1,
          structuralState: cTel,
        }}),
      }};
    }}
  }};
}}"""
        sky_t, phys_act, loc_id, upd_args, inc_shore, show_wind, bloom_v = cfg_map[gen]
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 7.5, skyTheme: '{sky_t}', sunDir: [-4, 8, 6] }});
  const env = makePugetSoundEnvironment({{ includeShore: {'true' if inc_shore else 'false'} }});
  scene.add(env.root);
  const bridge = makeTacomaSuspensionBridgeRig({{
    deckBaseY: 2.45, spanLength: 15.6, nSegments: 22,
    showWindStreams: {'true' if show_wind else 'false'}, includeCar: true
  }});
  scene.add(bridge.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 36);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const bTel = bridge.update(lt, {dur}, {upd_args});
      const splash = bTel.collapse_active ? clamp((lt - {round(dur * 0.38, 3)}) / 0.9, 0, 1) : 0.0;
      env.update(lt, splash);
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      const anchors = bridge.getAnchorsTelemetry(c);
      return {{
        bloom: {bloom_v}, camTel, anchors,
        physicalMotion: bridge.getPhysicalState(),
        narrativeAction: getNarrativeActionTelemetry({{
          locationId: '{loc_id}',
          physicalAction: '{phys_act}',
          structuralState: bTel,
        }}),
      }};
    }}
  }};
}}"""

    if gen == "zach3d:boston_street_hook_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.5, skyTheme: 'boston_overcast', sunDir: [-3, 7, 5] }});
  const street = makeNorthEndStreet1919({{ streetLength: 14.0, includeCart: true }});
  scene.add(street.root);
  const tank = makeMolassesStorageTank1919({{ radius: 1.65, height: 3.2 }});
  tank.position.set(-0.35, 0, -4.8); scene.add(tank);
  const crowd = makePeriodCrowdActionRig(makeHuman, {char_spec_json}, 'pedestrians');
  scene.add(crowd.root);
  const heroTarget = new THREE.Object3D(); heroTarget.position.set(0.0, 1.35, 0.20); scene.add(heroTarget);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 38);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const actTel = crowd.update(lt, {dur}, 'street_turn');
      if (street.wheelMeshes) street.wheelMeshes.forEach(w => {{ w.rotation.x = lt * 0.9; }});
      if (street.cartGroup) street.cartGroup.position.z = lerp(-1.85, -0.95, easeInOut(u));
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      const anchors = computeAnchorsTelemetry(c, {{ street_hero_look: heroTarget }}, []);
      return {{
        bloom: 0.24, camTel, anchors,
        characterPerformance: actTel?.character_performance || null,
        narrativeAction: getNarrativeActionTelemetry({{
          locationId: 'boston_north_end_street_1919',
          physicalAction: 'street_rumble_foreshadow',
          actorCount: crowd.actors.length,
          structuralState: actTel,
        }}),
      }};
    }}
  }};
}}"""

    if gen == "zach3d:boston_molasses_reveal_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.5, skyTheme: 'boston_overcast', sunDir: [-2, 6, 4] }});
  const street = makeNorthEndStreet1919({{ streetLength: 13.0, includeCart: false }});
  scene.add(street.root);
  const tank = makeMolassesStorageTank1919({{ radius: 1.55, height: 3.1 }});
  tank.position.set(0.0, 0, -4.4); scene.add(tank);
  const wave = makeMolassesGravityCurrentRig({{ width: 3.8, height: 1.6 }});
  scene.add(wave.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 36);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const wTel = wave.update(lt, {dur}, {{ zStart: -2.8, zEnd: 0.65 }});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      const anchors = wave.getAnchorsTelemetry(c);
      return {{
        bloom: 0.28, camTel, anchors,
        narrativeAction: getNarrativeActionTelemetry({{
          locationId: 'boston_commercial_alley_1919',
          physicalAction: 'thick_fluid_reveal',
          fluidFrontPos: wTel.wave_front_z,
        }}),
      }};
    }}
  }};
}}"""

    if gen == "zach3d:boston_tank_leak_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 3.8, skyTheme: 'boston_overcast', sunDir: [-3, 6, 4] }});
  const street = makeNorthEndStreet1919({{ streetLength: 12.0, includeCart: false }});
  scene.add(street.root);
  const tank = makeMolassesStorageTank1919({{ radius: 1.65, height: 3.25 }});
  tank.position.set(0.0, 0, -1.25); scene.add(tank);
  const seep = makeSeamLeakAndRivetFailureRig({{ mode: 'seep' }});
  seep.root.position.set(-0.25, 0, 0.14);
  scene.add(seep.root);
  const crowd = makePeriodCrowdActionRig(makeHuman, {char_spec_json}, 'dock_worker');
  scene.add(crowd.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 34);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const sTel = seep.update(lt, {dur});
      const wTel = crowd.update(lt, {dur}, 'inspect_leak');
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      const anchors = seep.getAnchorsTelemetry(c);
      return {{
        bloom: 0.30, camTel, anchors,
        narrativeAction: getNarrativeActionTelemetry({{
          locationId: 'usia_tank_base_1915',
          physicalAction: 'chronic_seam_seepage',
          actorCount: crowd.actors.length,
          structuralState: {{ ...sTel, ...wTel }},
        }}),
      }};
    }}
  }};
}}"""

    if gen == "zach3d:boston_tank_rupture_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.0, skyTheme: 'boston_amber', sunDir: [-3, 7, 5] }});
  const street = makeNorthEndStreet1919({{ streetLength: 12.0, includeCart: false }});
  scene.add(street.root);
  const rup = makeSeamLeakAndRivetFailureRig({{ mode: 'rupture' }});
  scene.add(rup.root);
  const droplets = sparks(55, {{ speed: 1.85, spread: 1.6, gravity: -4.2, life: 0.95, size: 0.022, dir: V(0, 0.35, 1), seed: {seed + i}, color: [0.36, 0.17, 0.06] }});
  droplets.position.set(0.0, 1.25, 0.56); scene.add(droplets);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const CONTACT = {contact_json};
  const HIT_T = CONTACT?.hit_time_rel_sec ?? {round(dur * 0.46, 3)};
  const c = cam(KFS[0].fov || 35);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const rState = rup.update(lt, {dur}, HIT_T);
      droplets.update(lt - HIT_T);
      const shake = (lt > HIT_T && lt < HIT_T + 0.38) ? Math.sin((lt - HIT_T) * 55) * Math.exp(-(lt - HIT_T) * 6.0) * 0.014 : 0;
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, {{ ...poseCam, roll: (poseCam.roll || 0) + shake }}, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      const anchors = rup.getAnchorsTelemetry(c);
      return {{
        bloom: rState.ruptureProgress > 0.05 ? 0.40 : 0.28,
        camTel, anchors,
        contact: {{ hit_time_rel_sec: HIT_T, rupture_progress: rState.ruptureProgress, world_error_m: rState.world_error_m }},
        narrativeAction: getNarrativeActionTelemetry({{
          locationId: 'usia_tank_base_1915',
          physicalAction: 'tank_panel_rupture',
          structuralState: rState,
        }}),
      }};
    }}
  }};
}}"""

    if gen == "zach3d:boston_wave_street_stage":
        is_speed = (s.get("setup_type") == "boston_wave_speed_sweep") or any(k in nar_low for k in ("35", "faster", "race", "horse"))
        z_start_val = -0.8 if is_speed else -2.6
        z_end_val = 3.2 if is_speed else 2.2
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.8, skyTheme: 'boston_amber', sunDir: [-3, 7, 5] }});
  const street = makeNorthEndStreet1919({{ streetLength: 15.0, includeCart: true }});
  scene.add(street.root);
  const wave = makeMolassesGravityCurrentRig({{ width: 4.3, height: 1.72 }});
  scene.add(wave.root);
  const crowd = makePeriodCrowdActionRig(makeHuman, {char_spec_json}, 'pedestrians');
  crowd.root.position.set(0, 0, 1.35);
  scene.add(crowd.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 36);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const wTel = wave.update(lt, {dur}, {{ zStart: {z_start_val}, zEnd: {z_end_val} }});
      const aTel = crowd.update(lt, {dur}, 'retreat_run');
      if (street.wheelMeshes) street.wheelMeshes.forEach(w => {{ w.rotation.x = lt * 2.2; }});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      const anchors = wave.getAnchorsTelemetry(c);
      return {{
        bloom: 0.30, camTel, anchors,
        physicalMotion: wTel,
        characterPerformance: aTel?.character_performance || null,
        narrativeAction: getNarrativeActionTelemetry({{
          locationId: 'commercial_street_corridor_1919',
          physicalAction: {'"wave_speed_chase_escalation"' if is_speed else '"molasses_wave_surge"'},
          actorCount: crowd.actors.length,
          fluidFrontPos: wTel.wave_front_z,
          structuralState: aTel,
        }}),
      }};
    }}
  }};
}}"""

    if gen == "zach3d:boston_elevated_rail_impact_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.8, skyTheme: 'boston_amber', sunDir: [-3, 7, 5] }});
  const street = makeNorthEndStreet1919({{ streetLength: 14.0, includeCart: false }});
  scene.add(street.root);
  const rail = makeElevatedRailAndStreetImpactRig();
  scene.add(rail.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const CONTACT = {contact_json};
  const HIT_T = CONTACT?.hit_time_rel_sec ?? {round(dur * 0.44, 3)};
  const c = cam(KFS[0].fov || 36);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const rTel = rail.update(lt, {dur}, HIT_T);
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      const anchors = rail.getAnchorsTelemetry(c);
      return {{
        bloom: rTel.hit_active ? 0.36 : 0.28, camTel, anchors,
        contact: {{ hit_time_rel_sec: HIT_T, rail_deflection_rad: rTel.rail_deflection_rad, world_error_m: rTel.world_error_m }},
        narrativeAction: getNarrativeActionTelemetry({{
          locationId: 'elevated_rail_trestle_1919',
          physicalAction: 'street_structure_impact',
          structuralState: rTel,
        }}),
      }};
    }}
  }};
}}"""

    if gen == "zach3d:boston_rescue_aftermath_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.2, skyTheme: 'dusk', sunDir: [-2, 5, 4], sun: 1.35 }});
  const street = makeNorthEndStreet1919({{ streetLength: 13.0, includeCart: false }});
  scene.add(street.root);
  const rescue = makeRescueAndAftermathRig(makeHuman);
  scene.add(rescue.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 35);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const rTel = rescue.update(lt, {dur});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      const anchors = rescue.getAnchorsTelemetry(c);
      return {{
        bloom: 0.34, camTel, anchors,
        narrativeAction: getNarrativeActionTelemetry({{
          locationId: 'north_end_aftermath_sector_1919',
          physicalAction: 'rescue_and_settling_aftermath',
          actorCount: 2,
          structuralState: rTel,
        }}),
      }};
    }}
  }};
}}"""

    if gen == "zach3d:boston_engineering_cutaway_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 2.8, skyTheme: 'lab_studio', sunDir: [-3, 6, 4] }});
  const sec = makeBostonSteelSectionCutawayRig();
  scene.add(sec.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 33);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const sTel = sec.update(lt, {dur});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      const anchors = sec.getAnchorsTelemetry(c);
      return {{
        bloom: 0.42, camTel, anchors,
        cutaway: sec.getTelemetry(),
        narrativeAction: getNarrativeActionTelemetry({{
          locationId: 'engineering_analysis_section',
          physicalAction: 'structural_defect_cutaway',
          cutawayState: sTel,
        }}),
      }};
    }}
  }};
}}"""

    if gen == "zach3d:boston_harbor_payoff_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 6.5, skyTheme: 'boston_amber', sunDir: [-4, 8, 5] }});
  const ov = makeBostonLocationOverview();
  scene.add(ov.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 38);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      const anchors = ov.getAnchorsTelemetry(c);
      return {{
        bloom: 0.30, camTel, anchors,
        narrativeAction: getNarrativeActionTelemetry({{
          locationId: 'boston_harbor_north_end_overview',
          physicalAction: 'historical_overview_pullback',
        }}),
      }};
    }}
  }};
}}"""

    if gen == "zach3d:airplane_window_hole_stage":
        setup = str(s.get("setup_type") or "")
        is_failsafe = (setup == "airplane_window_failsafe_cutaway") or any(k in nar_low for k in ("fails", "failure", "backup", "crack"))
        is_moisture = (setup == "airplane_window_moisture_vent") or any(k in nar_low for k in ("moisture", "fog", "frost", "condensation", "clear"))
        is_exploded = (setup == "airplane_window_layers_exploded") or any(k in nar_low for k in ("three layers", "outer pane", "middle pane", "scratch", "layers"))
        is_pressure = (setup == "airplane_window_pressure_equalize") or any(k in nar_low for k in ("pressure", "cruise", "equalizes", "equalize", "outward", "carries"))
        exp_target = 0.85 if is_exploded else (0.55 if is_pressure else (0.48 if is_failsafe else (0.35 if is_moisture else 0.14)))
        cut_target = 0.72 if (is_exploded or is_failsafe) else (0.42 if is_pressure else 0.08)
        show_press = "true" if (is_pressure or is_failsafe) else "false"
        outer_dmg = "true" if (is_failsafe and ("fails" in nar_low or "backup" in nar_low or setup == "airplane_window_failsafe_cutaway")) else "false"
        moist_flg = "true" if is_moisture else "false"
        sky_theme = "dusk" if is_failsafe else ("lab_studio" if (is_exploded or is_pressure) else "datacenter_dark")
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 2.6, skyTheme: '{sky_theme}' }});
  const aw = makeAircraftWindowAssemblyRig({{ mode: {json.dumps(setup)}, outerDamaged: {outer_dmg}, moistureDemo: {moist_flg} }});
  scene.add(aw.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 32);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const rev = smooth(clamp(u * 1.45, 0, 1));
      aw.updateAssembly(lt, {dur}, {{
        explodeAmount: lerp({exp_target * 0.25:.3f}, {exp_target:.3f}, rev),
        cutawayAmount: lerp(0.0, {cut_target:.3f}, rev),
        showPressure: {show_press},
      }});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      const anchors = aw.getAnchorsTelemetry(c);
      return {{ bloom: {outer_dmg} ? 0.50 : 0.38, camTel, cutaway: aw.getTelemetry(), anchors }};
    }}
  }};
}}"""

    if gen == "zach3d:elevator_lobby_button_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 2.8, skyTheme: 'day' }});
  const man = makeModernOutfitCharacter(makeHuman, {char_spec_json});
  man.root.position.set(-0.20, 0, 0.10); man.root.rotation.y = 1.12; scene.add(man.root);
  const panel = makePushButtonPanelRig();
  scene.add(panel);
  const sp = sparks(35, {{ speed: 0.35, spread: 1.2, gravity: -0.2, life: 0.5, size: 0.007, dir: V(-1, 0.2, 0), seed: {seed + i}, color: [0.96, 0.65, 0.12] }});
  sp.position.set(0.23, 1.16, 0.24); scene.add(sp);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const CONTACT = {contact_json};
  const c = cam(KFS[0].fov || 34);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const cRes = updateButtonPressAction(man, CONTACT, lt, STAND);
      panel.setButtonState(cRes.button_depress_m, cRes.button_lit);
      man.setMouth(0.08 + 0.12 * Math.abs(Math.sin(lt * 4.5)));
      sp.update(lt - CONTACT.hit_time_rel_sec);
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: cRes.button_lit ? 0.54 : 0.28, camTel, contact: cRes }};
    }}
  }};
}}"""

    if gen == "zach3d:controller_cabinet_cutaway_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 2.2, skyTheme: 'datacenter_dark' }});
  const cab = makeControllerCabinetRig();
  scene.add(cab.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 32);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      cab.updateCabinet(lt, {dur});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.45, camTel, cutaway: cab.getTelemetry() }};
    }}
  }};
}}"""

    if gen == "zach3d:traction_machine_room_stage":
        decel_flag = "true" if ("slow" in nar_low or "brake" in nar_low or "approach" in nar_low) else "false"
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 3.0, skyTheme: 'lab_studio' }});
  const mach = makeTractionDriveMachineRig();
  scene.add(mach.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 34);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      mach.updateDrive(lt, {dur}, {{ decelerate: {decel_flag} }});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.40, camTel, cutaway: mach.getTelemetry() }};
    }}
  }};
}}"""

    if gen == "zach3d:elevator_shaft_cutaway_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 3.4, skyTheme: 'datacenter_dark' }});
  const shaft = makeElevatorShaftRig();
  scene.add(shaft.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 32);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      shaft.updateShaft(lt, {dur});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.42, camTel, cutaway: shaft.getTelemetry() }};
    }}
  }};
}}"""

    if gen == "zach3d:elevator_landing_doors_stage":
        start_open = "false"
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 3.2, skyTheme: 'day' }});
  const portal = makeLandingDoorsRig();
  scene.add(portal);
  const man = makeModernOutfitCharacter(makeHuman, {char_spec_json});
  man.root.position.set(-0.22, 0, 0.44); man.root.rotation.y = 0.48; scene.add(man.root);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 34);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      portal.updatePortal(lt, {dur}, {{ startOpen: {start_open} }});
      const nod = Math.sin(lt * 2.4) * 0.04;
      man.setPose({{
        ...STAND,
        chest: [0.02, 0.14, 0],
        head: [nod, 0.22, 0],
        rSh: [-0.18 - 0.12 * smooth(u), 0.06, -0.18],
        rEl: [-0.40, 0, 0],
      }});
      man.setMouth(0.14 + 0.16 * Math.abs(Math.sin(lt * 5.0)));
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.34, camTel }};
    }}
  }};
}}"""

    if gen == "zach3d:schematic_mechanism_stage":
        dom_label = str(s.get("unsupported_exact_domain") or prop or "SCHEMATIC")
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 2.8, skyTheme: 'lab_studio' }});
  const mech = makeSchematicMechanismStage({json.dumps(dom_label)});
  scene.add(mech);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 34);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      mech.wheels.forEach((w, idx) => {{ w.rotation.z = -lt * (idx === 0 ? 1.8 : 2.9); }});
      mech.link.position.y = 1.05 + Math.sin(lt * 3.0) * 0.06;
      mech.link.rotation.z = Math.sin(lt * 3.0) * 0.18;
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.32, camTel }};
    }}
  }};
}}"""

    if gen == "zach3d:human_device_stage" or (prop == "phone_screen" and gen != "zach3d:device_cutaway_stage"):
        sent_flag = "true" if (is_callback or i == total_shots - 1) else "false"
        theme = "lab_studio" if sent_flag == "true" else "day"
        t_tap = round(float(contact_spec.get("hit_time_rel_sec", dur * 0.42)) if isinstance(contact_spec, dict) else (dur * 0.42), 3)
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 2.6, skyTheme: '{theme}' }});
  const man = makeModernOutfitCharacter(makeHuman, {char_spec_json});
  man.root.position.set(-0.08, 0, 0.02); man.root.rotation.y = 0.42; scene.add(man.root);
  const phone = makeSmartphoneRig({{ sent: {sent_flag}, scale: 0.78 }});
  phone.position.set(0.16, 1.28, 0.28); phone.rotation.set(-0.14, -0.32, 0.04);
  scene.add(phone);
  phone.updateMatrixWorld(true);
  const _btnW = phone.tapRing.getWorldPosition(new THREE.Vector3());
  const _btnN = new THREE.Vector3(0, 0, 1).transformDirection(phone.matrixWorld).normalize();
  const sp = sparks(45, {{ speed: 0.45, spread: 1.4, gravity: -0.2, life: 0.7, size: 0.008, dir: V(0, 0.2, 1), seed: {seed + i}, color: [0.22, 0.74, 0.97] }});
  sp.position.copy(_btnW); scene.add(sp);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 35);
  const T_TAP = {t_tap};
  const PHONE_CONTACT = {{ verb: 'tap_screen', performer_id: {json.dumps(cid)}, target_id: 'phone_send_button_01', hit_time_rel_sec: T_TAP, hold_duration_sec: 0.14, target_world: [_btnW.x, _btnW.y, _btnW.z], target_normal: [_btnN.x, _btnN.y, _btnN.z], target_radius_m: 0.055, button_depress_m: 0.004 }};
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const postTap = lt - T_TAP;
      const cRes = updateButtonPressAction(man, PHONE_CONTACT, lt, STAND);
      man.setMouth({0.35 if sent_flag == 'true' else 0.14} + 0.15 * Math.abs(Math.sin(lt * 5.0)));
      phone.rotation.y = -0.34 + Math.sin(lt * 1.4) * 0.03;
      if (postTap > 0) {{
        const ringU = clamp(postTap / 0.55, 0, 1);
        phone.tapRing.scale.setScalar(0.5 + easeOut(ringU) * 3.2);
        phone.tapRing.material.opacity = (1.0 - ringU) * 0.95;
      }} else {{
        phone.tapRing.material.opacity = 0.0;
      }}
      sp.update(postTap);
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: postTap > 0 && postTap < 0.35 ? 0.62 : 0.30, camTel, contact: cRes }};
    }}
  }};
}}"""

    if gen == "zach3d:device_cutaway_stage" or prop in ("microchip_pcb", "battery_cell"):
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 2.2, skyTheme: 'datacenter_dark' }});
  const phone = makeSmartphoneRig({{ sent: false, scale: 1.40 }});
  phone.position.set(0, 1.24, 0);
  scene.add(phone);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 32);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const peel = easeInOut(clamp(u * 1.55, 0, 1));
      phone.frontGlass.position.set(-0.22 * peel, 0.06 * peel, 0.014 + 0.22 * peel);
      phone.frontGlass.rotation.y = -0.38 * peel;
      phone.rotation.y = lerp(-0.35, 0.42, easeInOut(u));
      phone.pulses.forEach((p, k) => {{
        const cyc = ((lt * 1.9 + k * 0.18) % 1.0);
        p.position.y = lerp(-0.14, 0.21, cyc);
        p.scale.setScalar(0.85 + 0.45 * Math.sin(cyc * Math.PI));
      }});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.48, camTel, cutaway: phone.getTelemetry(peel) }};
    }}
  }};
}}"""

    if gen == "zach3d:network_relay_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 3.5, skyTheme: 'dusk' }});
  const tower = makeRadioTowerRig();
  scene.add(tower);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 36);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      tower.beacon.material.emissiveIntensity = 1.1 + Math.abs(Math.sin(lt * 5.0)) * 1.4;
      tower.rfRings.forEach((rm, k) => {{
        const prog = ((lt * 0.85 + k * 0.25) % 1.0);
        rm.scale.setScalar(0.5 + prog * 4.4);
        rm.material.opacity = (1.0 - prog) * 0.88;
      }});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.44, camTel }};
    }}
  }};
}}"""

    if gen == "zach3d:subsea_fiber_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 3.5, skyTheme: 'ocean_deep', showShadowFloor: false }});
  const rig = makeSubseaCableRig({seed + i});
  scene.add(rig);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 34);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      rig.pulses.forEach((p, k) => {{
        const s = ((lt * 1.35 + k * 0.167) % 1.0);
        p.position.set(lerp(-1.65, 1.70, s), 0.0, 0.0);
      }});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.56, camTel }};
    }}
  }};
}}"""

    if gen == "zach3d:datacenter_aisle_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.0, skyTheme: 'datacenter_dark', showShadowFloor: false }});
  const dc = makeDatacenterRackBank({seed + i * 7});
  scene.add(dc);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 38);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      dc.packets.forEach((sp, k) => {{
        const cyc = ((lt * 1.6 + k * 0.16) % 1.0);
        sp.position.z = lerp(1.4, -3.2, cyc);
        sp.position.x = Math.sin(lt * 3 + k) * 0.08;
      }});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.50, camTel }};
    }}
  }};
}}"""

    if gen == "zach3d:power_turbine_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 3.0, skyTheme: 'lab_studio' }});
  const tb = makePowerTurbineRig();
  scene.add(tb);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 34);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      tb.rotor.rotation.z = -lt * (4.5 + u * 6.5);
      tb.coilGlow.material.emissiveIntensity = 1.0 + 0.65 * Math.abs(Math.sin(lt * 7.5));
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.48, camTel }};
    }}
  }};
}}"""

    if gen == "zach3d:cosmic_scale_bridge_stage":
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.0, skyTheme: 'cosmic', showShadowFloor: false }});
  const cosmos = makeCosmicGenesisRig({seed + i});
  cosmos.position.set(0, 1.25, 0);
  scene.add(cosmos);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 38);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      cosmos.star.rotation.y = lt * 0.55;
      cosmos.star.scale.setScalar(1.0 + Math.sin(lt * 3.5) * 0.06);
      cosmos.ring1.rotation.z = lt * 0.45;
      cosmos.ring2.rotation.y = -lt * 0.35;
      cosmos.orbiters.forEach((m, k) => {{
        const a = m.userData.phase + lt * (0.9 + (k % 3) * 0.35);
        m.position.set(Math.cos(a) * m.userData.rad, Math.sin(a * 0.6) * 0.14, Math.sin(a) * m.userData.rad);
        m.rotation.x = lt * 1.8; m.rotation.y = lt * 1.4;
      }});
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.68, camTel }};
    }}
  }};
}}"""

    if gen == "zach3d:anatomical_cutaway_stage":
        is_brain = "true" if ("brain" in prop or "neuron" in prop) else "false"
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 2.4, skyTheme: 'datacenter_dark' }});
  const rig = makeAnatomicalCutawayRig({is_brain});
  scene.add(rig);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 32);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const openU = easeInOut(clamp(u * 1.8, 0, 1));
      rig.cutaway.setReveal(openU);
      rig.cutaway.updateFlow(lt, 1.2);
      const pulse = 1.0 + 0.05 * Math.sin(lt * 5.2);
      rig.lobes.forEach(l => l.scale.set(0.85 * pulse, 1.05 * pulse, 1.0 * pulse));
      rig.rotation.y = lerp(-0.35, 0.35, easeInOut(u));
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.45, camTel, cutaway: rig.cutaway.getTelemetry() }};
    }}
  }};
}}"""

    return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 2.8, skyTheme: 'lab_studio' }});
  const man = makeModernOutfitCharacter(makeHuman, {char_spec_json});
  man.root.position.set(-0.24, 0, 0); man.root.rotation.y = 0.32; scene.add(man.root);
  const ped = forcePedestal(); ped.position.set(0.32, 0, 0.08); scene.add(ped);
  const gearStage = makeVaultGearStage();
  gearStage.scale.setScalar(0.52); gearStage.position.set(0.32, 0.98, 0.08); scene.add(gearStage);
  const core = energyCore({0xf59e0b if i == total_shots - 1 else 0x38bdf8});
  core.position.set(0.32, 1.44, 0.08); core.scale.setScalar(0.56); scene.add(core);
  const KFS = {kfs_json};
  const ANCHOR = {anchor_json};
  const c = cam(KFS[0].fov || 34);
  return {{
    scene, camera: c,
    update(lt, gT, trOpts = {{}}) {{
      const u = clamp(lt / {dur}, 0, 1);
      const wave = Math.sin(lt * 2.6) * 0.06;
      man.setPose({{
        ...STAND,
        chest: [Math.sin(lt * 1.8) * 0.02, -0.15, 0],
        head: [wave * 0.5, -0.22, 0],
        rSh: [-0.65 - easeOut(u) * 0.25, 0, -0.25],
        rEl: [-0.45, 0, 0]
      }});
      man.setMouth(0.18 + 0.22 * Math.abs(Math.sin(lt * 6.5)));
      gearStage.gears.forEach((gr, k) => {{ gr.rotation.z = lt * (k % 2 ? -1.4 : 1.4); }});
      core.r1.rotation.y = lt * 2.4; core.r2.rotation.x = lt * 1.9;
      const poseCam = evalCameraPath(KFS, u);
      const camTel = applyCameraPath(c, poseCam, {{ aspect: 1080/1920, focalAnchor: ANCHOR, ...trOpts }});
      return {{ bloom: 0.34, camTel }};
    }}
  }};
}}"""


def _build_zach_shots_js(storyboard: Dict[str, Any], words: List[Dict[str, Any]]) -> str:
    shots = storyboard["shots"]
    total_dur = storyboard["total_duration_sec"]
    seed = int(storyboard.get("seed", 42))
    captions = _build_captions_list(words)
    char_registry = storyboard.get("character_registry") or {}

    fades: List[List[float]] = []
    transitions_meta: List[Dict[str, Any]] = []
    for idx, s in enumerate(shots):
        tr_out = str(s.get("transition_out") or "cut")
        tr_meta = s.get("transition_meta") or {}
        tr_dur = float(tr_meta.get("duration_sec") or 0.0)
        if tr_out == "dip_to_black":
            t_c = s["end"]
            fades.append([round(t_c - 0.16, 3), round(t_c - 0.03, 3), round(t_c + 0.04, 3), round(t_c + 0.18, 3)])
        if idx < len(shots) - 1 and tr_dur > 0.0 and tr_out not in ("cut", "cut_on_action"):
            transitions_meta.append({
                "transition_id": f"tr_{idx:02d}",
                "from_idx": idx,
                "to_idx": idx + 1,
                "boundary": round(float(s["end"]), 4),
                "duration": tr_dur,
                "method": tr_out,
            })

    fn_blocks: List[str] = []
    list_entries: List[str] = []
    has_any_roman = False
    has_any_non_roman = False

    # Per-shot dispatch strictly from each shot's grounded generator/scene_family (ZERO global is_roman override!)
    for i, s in enumerate(shots):
        tr_out = str(s.get("transition_out") or "cut")
        gen = str(s.get("procedural_generator") or "")
        fam = str(s.get("scene_family") or "")
        shot_is_roman = (gen == "zach3d:roman_historical_stage") or (fam == "roman_historical")
        if shot_is_roman:
            has_any_roman = True
            fn_blocks.append(_roman_shot_code(i, s, len(shots)))
        else:
            has_any_non_roman = True
            fn_blocks.append(_build_non_roman_scene_shot_code(i, s, len(shots), seed=seed, char_registry=char_registry))
        list_entries.append(f"  {{ id: {json.dumps(s['shot_id'])}, start: {s['start']}, end: {s['end']}, tr: {json.dumps(tr_out)}, build: shot_{i} }},")

    novel_symbols: List[str] = []
    if has_any_roman:
        novel_symbols.extend([
            "addGladiatorBracers", "romanPlinth", "trainingPalus",
            "arenaStage", "romanHelmet", "romanScutum", "denariusStack",
            "romanScrollTablet", "togaSash", "balanceScale50x",
        ])
    if has_any_non_roman:
        novel_symbols.extend([
            "forcePedestal", "energyCore", "cutawaySlabStack",
            "makeModernOutfitCharacter", "makeSmartphoneRig", "makeRadioTowerRig",
            "makeSubseaCableRig", "makeDatacenterRackBank", "makePowerTurbineRig",
            "makeCosmicGenesisRig", "makeAnatomicalCutawayRig", "makeVaultGearStage",
        ])

    mech_import = (
        """import {
  makePushButtonPanelRig, makeControllerCabinetRig, makeTractionDriveMachineRig,
  makeElevatorShaftRig, makeLandingDoorsRig, makeSchematicMechanismStage
} from './mechanical_systems.js';
import { makeAircraftWindowAssemblyRig } from './aircraft_window_scenes.js';
import {
  makeNorthEndStreet1919, makeMolassesStorageTank1919, makeSeamLeakAndRivetFailureRig,
  makeMolassesGravityCurrentRig, makeElevatedRailAndStreetImpactRig, makePeriodCrowdActionRig,
  makeRescueAndAftermathRig, makeBostonSteelSectionCutawayRig, makeBostonLocationOverview,
  getNarrativeActionTelemetry, computeAnchorsTelemetry
} from './boston_molasses_scenes.js';
import {
  makePugetSoundEnvironment, makeTacomaSuspensionBridgeRig, makeTacomaShoreOnlookerRig
} from './tacoma_bridge_scenes.js';"""
        if has_any_non_roman else ""
    )

    header = f"""import * as THREE from 'three';
import {{ makeHuman }} from './human.js';
import {{ sword, sparks, rippleOverlay }} from './props.js';
import {{ clamp, lerp, smooth, easeOut, easeInOut, range, V, cam }} from './anim.js';
import {{ evalCameraPath, applyCameraPath }} from './camera_executor.js';
import {{ updateButtonPressAction }} from './character_action_rig.js';
import {{
  {', '.join(novel_symbols)}
}} from './novel_props.js';
{mech_import}

export const DURATION = {total_dur};
export const CAPTIONS = {json.dumps(captions, ensure_ascii=False)};
export const FADES = {json.dumps(fades)};
export const TRANSITIONS = {json.dumps(transitions_meta)};

const STAND = {{
  lSh: [0.05, 0, 0.16], rSh: [0.05, 0, -0.16], lEl: [-0.25, 0, 0], rEl: [-0.25, 0, 0],
  lHip: [0, 0, 0.07], rHip: [0, 0, -0.07], lAn: [0, 0, -0.07], rAn: [0, 0, 0.07],
}};
"""
    return header + "\n".join(fn_blocks) + "\nexport const SHOTS = [\n" + "\n".join(list_entries) + "\n];\n"


def generate_engine_project(
    project_root: Path,
    run_dir: Path,
    storyboard: Dict[str, Any],
    parsed_script: Dict[str, Any],
) -> Dict[str, Any]:
    """Create `<run_dir>/engine_work` using ONLY `skills/zach-d-films` 3D modules + shared `kit`."""
    upstream_zdf = project_root / "vendor" / "claude-animation-skills" / "skills" / "zach-d-films" / "engine"
    kit_dir = project_root / "vendor" / "claude-animation-skills" / "kit"
    work_dir = run_dir / "engine_work"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    src_dst = work_dir / "src"
    src_dst.mkdir(parents=True, exist_ok=True)

    visual_sources: List[str] = []
    for fname in ("anim.js", "human.js", "props.js", "materials.js", "textures.js"):
        src = (upstream_zdf / "src" / fname).resolve()
        shutil.copy2(src, src_dst / fname)
        visual_sources.append(str(src))

    link_kit_node_modules(kit_dir / "node_modules", work_dir / "node_modules")

    cam_exec_p = src_dst / "camera_executor.js"
    cam_exec_p.write_text(CAMERA_EXECUTOR_JS, encoding="utf-8")

    char_rig_p = src_dst / "character_action_rig.js"
    char_rig_p.write_text(CHARACTER_ACTION_RIG_JS, encoding="utf-8")

    cutaway_p = src_dst / "layered_cutaway.js"
    cutaway_p.write_text(LAYERED_CUTAWAY_JS, encoding="utf-8")

    mech_p = src_dst / "mechanical_systems.js"
    mech_p.write_text(MECHANICAL_SYSTEMS_JS, encoding="utf-8")

    aw_p = src_dst / "aircraft_window_scenes.js"
    aw_p.write_text(AIRCRAFT_WINDOW_SCENES_JS, encoding="utf-8")

    boston_p = src_dst / "boston_molasses_scenes.js"
    boston_p.write_text(BOSTON_MOLASSES_SCENES_JS, encoding="utf-8")

    phys_p = src_dst / "physical_motion_primitives.js"
    phys_p.write_text(PHYSICAL_MOTION_PRIMITIVES_JS, encoding="utf-8")

    char_perf_p = src_dst / "character_performance.js"
    char_perf_p.write_text(CHARACTER_PERFORMANCE_JS, encoding="utf-8")

    tacoma_p = src_dst / "tacoma_bridge_scenes.js"
    tacoma_p.write_text(TACOMA_BRIDGE_SCENES_JS, encoding="utf-8")

    novel_p = src_dst / "novel_props.js"
    novel_p.write_text(NOVEL_3D_PROPS_JS, encoding="utf-8")

    tl_json_p = run_dir / "editorial_timeline.json"
    if tl_json_p.exists():
        ed_timeline = json.loads(tl_json_p.read_text(encoding="utf-8"))
    else:
        ed_timeline = build_editorial_timeline(
            parsed_script=parsed_script,
            storyboard=storyboard,
            run_dir=None,
            caption_mode=str(storyboard.get("caption_mode", "kinetic")),
            callout_mode=str(storyboard.get("callout_mode", "off")),
            editorial_theme=str(storyboard.get("editorial_theme", "role-aware")),
            curiosity_layer=str(storyboard.get("curiosity_layer", "auto")),
        )
    ed_tl_p = src_dst / "editorial_timeline.js"
    ed_tl_p.write_text("export const EDITORIAL_TIMELINE = " + json.dumps(ed_timeline, ensure_ascii=False) + ";\n", encoding="utf-8")

    ed_ov_p = src_dst / "editorial_overlay_renderer.js"
    ed_ov_p.write_text(EDITORIAL_OVERLAY_RENDERER_JS, encoding="utf-8")

    shots_p = src_dst / "shots.js"
    shots_p.write_text(_build_zach_shots_js(storyboard, parsed_script["voice"]["words"]), encoding="utf-8")

    main_p = src_dst / "director_main.js"
    main_p.write_text(DIRECTOR_MAIN_JS, encoding="utf-8")

    index_html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
  @font-face { font-family: 'Cap'; src: url('node_modules/@fontsource/montserrat/files/montserrat-latin-700-normal.woff2') format('woff2'); font-weight: 700; }
  @font-face { font-family: 'Cap'; src: url('node_modules/@fontsource/montserrat/files/montserrat-latin-800-normal.woff2') format('woff2'); font-weight: 800; }
  @font-face { font-family: 'Cap'; src: url('node_modules/@fontsource/montserrat/files/montserrat-latin-900-normal.woff2') format('woff2'); font-weight: 900; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 1080px; height: 1920px; background: #000; overflow: hidden; }
  #stage { position: relative; width: 1080px; height: 1920px; overflow: hidden; }
  canvas { display: block; width: 1080px; height: 1920px; }
  #cap {
    position: absolute; left: 100px; width: 880px; top: 1390px;
    display: flex; flex-wrap: wrap; justify-content: center; align-items: baseline;
    column-gap: 0.28em; row-gap: 0.14em; text-align: center;
    font: 700 60px/1.15 'Cap', sans-serif; color: #fff; letter-spacing: 0.01em;
    text-shadow: 0 0 4px rgba(0,0,0,.78), 0 4px 16px rgba(0,0,0,.72);
    z-index: 15; pointer-events: none;
  }
  #fade { position: absolute; inset: 0; background: #000; opacity: 0; pointer-events: none; z-index: 20; }
</style>
<script type="importmap">
{ "imports": {
  "three": "./node_modules/three/build/three.module.js",
  "three/addons/": "./node_modules/three/examples/jsm/"
} }
</script>
</head><body>
<div id="stage"><div id="fade"></div><div id="cap"></div></div>
<script type="module" src="./src/director_main.js"></script>
</body></html>
"""
    index_p = work_dir / "index.html"
    index_p.write_text(index_html, encoding="utf-8")

    visual_sources.extend([
        str(Path(__file__).resolve()),
        str(cam_exec_p.resolve()),
        str(char_rig_p.resolve()),
        str(cutaway_p.resolve()),
        str(mech_p.resolve()),
        str(aw_p.resolve()),
        str(boston_p.resolve()),
        str(phys_p.resolve()),
        str(char_perf_p.resolve()),
        str(tacoma_p.resolve()),
        str(novel_p.resolve()),
        str(ed_tl_p.resolve()),
        str(ed_ov_p.resolve()),
        str(shots_p.resolve()),
        str(main_p.resolve()),
        str(index_p.resolve()),
    ])

    return {
        "engine": "zach-d-films",
        "work_dir": str(work_dir.resolve()),
        "entry_html": str(index_p.resolve()),
        "capture_mode": "page_jpeg",
        "supports_native_4k": True,
        "uses_webgl": True,
        "visual_sources": visual_sources,
    }
