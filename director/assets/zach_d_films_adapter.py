"""Single-Engine Adapter for `zach-d-films` (3D Cartoon Three.js Studio Explainer).

Uses ONLY:
- `vendor/claude-animation-skills/skills/zach-d-films/engine/src/{anim.js,human.js,props.js,materials.js,textures.js}`
- Shared `kit/node_modules/three` and `@fontsource/montserrat`
- Bespoke procedural 3D modules generated solely inside `engine_work/src/` (`novel_props.js`, `shots.js`, `director_main.js`).
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List


NOVEL_3D_PROPS_JS = r"""import * as THREE from 'three';
import { torsoShell } from './human.js';
import { materials } from './materials.js';
import { rng, woodTexture } from './textures.js';

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

// ---------- Procedural Seeded Textures for Bespoke Roman Props ----------
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

  // Auto-scale text cleanly inside tablet safe padding (420px max width) so long words NEVER clip!
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

// Add leather/bronze gladiator wrist bracers ('manica') cleanly covering human wrist seam
export function addGladiatorBracers(human) {
  const RM = romanMaterials();
  for (const side of ['lWr', 'rWr']) {
    const cuff = new THREE.Mesh(new THREE.CylinderGeometry(0.047, 0.044, 0.11, 18), RM.leatherWrap);
    cuff.position.y = 0.015;
    cuff.castShadow = cuff.receiveShadow = true;
    human.j[side].add(cuff);
  }
}

// Fluted Roman travertine plinth pedestal (grounded on arena floor)
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

// Roman wooden combat training post ('palus') driven into the arena sand
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

// Roman Coliseum sandy floor + distant curved stone arcade
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

// Roman Imperial Galea Helmet: sits high cleanly above eyes & eyebrows (eyes 100% visible!)
export function romanHelmet(crestHex = 0xb81d24) {
  const RM = romanMaterials();
  const M = materials();
  const g = new THREE.Group();
  // Upper bowl ends at phi = 0.44 * PI so it leaves eyes (y=0.11) & brows (y=0.134) unobstructed!
  const dome = new THREE.Mesh(new THREE.SphereGeometry(0.124, 32, 20, 0, Math.PI * 2, 0, Math.PI * 0.44), RM.bronze);
  dome.position.set(0, 0.134, -0.008);
  dome.scale.set(0.98, 1.15, 1.08);
  dome.rotation.x = -0.10;
  g.add(dome);
  // Forehead brow guard above eyebrows
  const brow = new THREE.Mesh(new THREE.TorusGeometry(0.118, 0.011, 8, 32, Math.PI * 0.85), RM.gold);
  brow.rotation.set(Math.PI * 0.44, 0, Math.PI * 0.075);
  brow.position.set(0, 0.155, 0.018);
  g.add(brow);
  // Hinged cheek guards set beside face (z = -0.01 so face remains expressive)
  for (const s of [-1, 1]) {
    const cg = new THREE.Mesh(new THREE.BoxGeometry(0.014, 0.09, 0.055), RM.bronze);
    cg.position.set(s * 0.095, 0.095, -0.005);
    cg.rotation.set(0.08, -s * 0.25, -s * 0.08);
    g.add(cg);
  }
  // Angled neck apron flare behind skull
  const neck = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.042, 0.075), M.steel);
  neck.position.set(0, 0.095, -0.102);
  neck.rotation.x = 0.62;
  g.add(neck);
  // Arched horsehair crest cleanly above dome top
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

// Solid 3D Curved Rectangular Roman Scutum Shield (matches props.js solid ExtrudeGeometry method!)
export function romanScutum() {
  const RM = romanMaterials();
  const shape = new THREE.Shape();
  shape.moveTo(-0.22, -0.32);
  shape.lineTo(0.22, -0.32);
  shape.lineTo(0.23, 0.32);
  shape.lineTo(-0.23, 0.32);
  shape.closePath();

  const geo = new THREE.ExtrudeGeometry(shape, {
    depth: 0.020,
    bevelEnabled: true,
    bevelThickness: 0.008,
    bevelSize: 0.008,
    bevelSegments: 2,
    curveSegments: 16,
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

  // Brass rim edges top/bottom & central bronze Umbo boss
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

// Gleaming Roman coin stack
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

// Roman wax-and-bronze display tablet with auto-fitted crisp label text
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

// Roman Organizers' crimson shoulder toga sash attached cleanly onto chest group
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

// Compact 9:16-framed Roman Balance Scale comparing 1x Rent vs 50x Penalty inside safe zone
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

  // Beam half-width 0.30 so BOTH 1x and 50x plaques stay 100% inside narrow 9:16 frame!
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

// ---------- SD-VISUAL-01: Non-Roman 3D Multi-Family Scene Builders ----------

function makeScreenTexture(headline = 'READY', btnText = 'SEND', sent = false) {
  const c = document.createElement('canvas');
  c.width = 256; c.height = 512;
  const ctx = c.getContext('2d');
  const bg = ctx.createLinearGradient(0, 0, 0, 512);
  bg.addColorStop(0, '#0f172a');
  bg.addColorStop(1, '#1e293b');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, 256, 512);

  // Header bar
  ctx.fillStyle = 'rgba(255,255,255,0.08)';
  ctx.fillRect(16, 28, 224, 52);
  ctx.fillStyle = '#94a3b8';
  ctx.font = '700 20px Cap, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('DIRECT LINK', 128, 60);

  // Chat bubble
  ctx.fillStyle = sent ? '#0ea5e9' : '#2563eb';
  ctx.beginPath();
  ctx.roundRect(24, 150, 208, 92, 22);
  ctx.fill();
  ctx.fillStyle = '#ffffff';
  ctx.font = '700 26px Cap, sans-serif';
  ctx.fillText(headline, 128, 204);

  // Action pill
  ctx.fillStyle = sent ? '#10b981' : '#38bdf8';
  ctx.beginPath();
  ctx.roundRect(44, 340, 168, 68, 34);
  ctx.fill();
  ctx.fillStyle = '#07131d';
  ctx.font = '700 28px Cap, sans-serif';
  ctx.fillText(sent ? 'SENT ✓' : btnText, 128, 383);

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

export function makeModernOutfitCharacter(makeHumanFn, accentHex = 0x2b6cb0) {
  const h = makeHumanFn('plain');
  const shirtMat = new THREE.MeshStandardMaterial({ color: accentHex, roughness: 0.78, metalness: 0.05 });
  const accentMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, roughness: 0.55 });
  // Smooth torsoShell jacket/shirt sleeves over base mesh (+0.016..0.018 offset avoids z-fighting; zero armor!)
  const chestG = torsoShell(0.18, 0.54, 0.018);
  chestG.translate(0, -0.2, 0);
  const chestShirt = new THREE.Mesh(chestG, shirtMat);
  chestShirt.castShadow = true;
  chestShirt.receiveShadow = true;
  h.j.chest.add(chestShirt);

  const spineShirt = new THREE.Mesh(torsoShell(-0.14, 0.20, 0.016), shirtMat);
  spineShirt.castShadow = true;
  spineShirt.receiveShadow = true;
  h.j.spine.add(spineShirt);

  const collar = new THREE.Mesh(new THREE.TorusGeometry(0.105, 0.018, 8, 24), accentMat);
  collar.rotation.x = Math.PI / 2;
  collar.position.set(0, 0.34, 0.01);
  collar.castShadow = true;
  h.j.chest.add(collar);
  return h;
}

export function makeSmartphoneRig({ sent = false, scale = 1.0 } = {}) {
  const M = materials();
  const g = new THREE.Group();
  const chassisMat = new THREE.MeshPhysicalMaterial({ color: 0x1e293b, metalness: 0.82, roughness: 0.25, clearcoat: 0.6 });
  const frameMat = new THREE.MeshPhysicalMaterial({ color: 0x94a3b8, metalness: 0.92, roughness: 0.20 });
  const pcbMat = new THREE.MeshStandardMaterial({ color: 0x0f5132, roughness: 0.45, metalness: 0.25 });
  const chipMat = new THREE.MeshPhysicalMaterial({ color: 0x111827, metalness: 0.4, roughness: 0.2, clearcoat: 0.8 });
  const traceMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, emissive: 0xd97706, emissiveIntensity: 0.55, metalness: 0.9, roughness: 0.2 });

  // Back frame & interior PCB assembly (visible during cutaway reveal)
  const backShell = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.56, 0.016), chassisMat);
  backShell.position.z = -0.018;
  g.add(backShell);

  const internals = new THREE.Group();
  g.add(internals);

  const pcb = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.50, 0.008), pcbMat);
  pcb.position.z = -0.004;
  internals.add(pcb);

  // Lithium battery cell
  const batt = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.25, 0.014), M.steelDark);
  batt.position.set(-0.025, -0.08, 0.006);
  const battBadge = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.05, 0.004), new THREE.MeshStandardMaterial({ color: 0x10b981, emissive: 0x059669, emissiveIntensity: 0.45 }));
  battBadge.position.set(-0.025, -0.06, 0.014);
  internals.add(batt, battBadge);

  // SoC chip + gold copper traces
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

  // Front glass OLED assembly (detaches forward cleanly on cutaway!)
  const frontGlass = new THREE.Group();
  g.add(frontGlass);
  const bezel = new THREE.Mesh(new THREE.BoxGeometry(0.285, 0.565, 0.014), frameMat);
  const scrMat = new THREE.MeshStandardMaterial({
    map: makeScreenTexture(sent ? 'DELIVERED' : 'HELLO WORLD', 'SEND', sent),
    emissive: sent ? 0x0ea5e9 : 0x1d4ed8,
    emissiveIntensity: 0.45,
    roughness: 0.15,
  });
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.255, 0.515), scrMat);
  screen.position.z = 0.008;
  frontGlass.position.z = 0.014;
  frontGlass.add(bezel, screen);

  // Sending ring ripple on screen tap point
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

  // Expanding RF emission wavefront toruses
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
  // Procedural rippled seabed terrain
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

  // Cutaway armored fiber-optic trunk laying diagonally across seabed
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

  // Exposed luminous optical glass core running through cutaway window
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
  // Overhead fiber trunk & fast light packets
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
  // Glowing charge core / magnetic field arcs
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

  // Crystallized elemental orbs (copper & silicon planetary seeds)
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
  // Distant stars
  for (let i = 0; i < 40; i++) {
    const theta = r() * Math.PI * 2, phi = Math.acos(2 * r() - 1);
    const d = 5.5 + r() * 6.0;
    const s = new THREE.Mesh(new THREE.SphereGeometry(0.032, 6, 6), new THREE.MeshBasicMaterial({ color: 0xf8fafc }));
    s.position.set(d * Math.sin(phi) * Math.cos(theta), d * Math.cos(phi), d * Math.sin(phi) * Math.sin(theta));
    g.add(s);
  }
  g.star = star;
  g.ring1 = ring1;
  g.ring2 = ring2;
  g.orbiters = orbiters;
  return g;
}

export function makeAnatomicalCutawayRig(isBrain = true) {
  const g = new THREE.Group();
  const shellMat = new THREE.MeshPhysicalMaterial({
    color: 0x93c5fd, transparent: true, opacity: 0.34, roughness: 0.15, metalness: 0.05, clearcoat: 0.8, side: THREE.DoubleSide
  });
  const shell = new THREE.Mesh(new THREE.SphereGeometry(0.42, 36, 28, 0, Math.PI * 1.45), shellMat);
  shell.position.y = 1.25;
  g.add(shell);

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
      g.add(lobe);
      lobes.push(lobe);
    }
  } else {
    const heart = new THREE.Mesh(new THREE.SphereGeometry(0.24, 32, 24), organMat);
    heart.scale.set(0.85, 1.22, 0.85);
    heart.position.set(0, 1.22, 0.02);
    g.add(heart);
    lobes.push(heart);
  }
  const sparkNodes = [];
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    const nd = new THREE.Mesh(new THREE.SphereGeometry(0.028, 12, 10), new THREE.MeshStandardMaterial({ color: 0xfef08a, emissive: 0xfacc15, emissiveIntensity: 1.6 }));
    nd.position.set(Math.cos(a) * 0.16, 1.26 + Math.sin(a) * 0.12, 0.14);
    g.add(nd);
    sparkNodes.push(nd);
  }
  g.shell = shell;
  g.lobes = lobes;
  g.sparkNodes = sparkNodes;
  return shadow(g);
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
import { SHOTS, CAPTIONS, DURATION, FADES } from './shots.js';

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
const composer = new EffectComposer(renderer, rt);
const renderPass = new RenderPass(new THREE.Scene(), new THREE.PerspectiveCamera());
const bloom = new UnrealBloomPass(new THREE.Vector2(W * SCALE, H * SCALE), 0.22, 0.4, 1.5);
const grade = new ShaderPass({
  uniforms: {
    tDiffuse: { value: null },
    uVig: { value: 0.25 },
    uZoom: { value: 0.0 },
    uWhip: { value: 0.0 },
    uWipe: { value: 0.0 },
    uFlash: { value: 0.0 },
  },
  vertexShader: `varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
  fragmentShader: `uniform sampler2D tDiffuse; uniform float uVig; uniform float uZoom; uniform float uWhip; uniform float uWipe; uniform float uFlash; varying vec2 vUv;
    void main(){
      vec2 uv = vUv;
      vec2 cvec = uv - 0.5;
      if (uZoom > 0.001) {
        vec4 acc = vec4(0.0);
        for (int i = 0; i < 4; i++) {
          float s = 1.0 - uZoom * 0.14 * (float(i) / 3.0);
          acc += texture2D(tDiffuse, clamp(0.5 + cvec * s, 0.001, 0.999));
        }
        gl_FragColor = acc * 0.25;
      } else if (abs(uWhip) > 0.001) {
        vec4 acc = vec4(0.0);
        for (int i = -2; i <= 2; i++) {
          acc += texture2D(tDiffuse, clamp(uv + vec2(uWhip * 0.032 * float(i), 0.0), 0.001, 0.999));
        }
        gl_FragColor = acc * 0.20;
      } else {
        gl_FragColor = texture2D(tDiffuse, uv);
      }
      if (uWipe > 0.001) {
        float bar = smoothstep(uWipe - 0.04, uWipe, uv.x) * (1.0 - smoothstep(uWipe, uWipe + 0.04, uv.x));
        gl_FragColor.rgb = mix(gl_FragColor.rgb, vec3(0.07, 0.11, 0.18), bar * 0.85);
      }
      vec2 q = vUv - 0.5; q.x *= 0.5625;
      gl_FragColor.rgb *= 1.0 - uVig * smoothstep(0.18, 0.62, length(q));
      gl_FragColor.rgb += vec3(uFlash * 0.18);
    }`,
});
composer.addPass(renderPass);
composer.addPass(bloom);
composer.addPass(new OutputPass());
composer.addPass(grade);

const capEl = document.getElementById('cap');
const fadeEl = document.getElementById('fade');
const built = new Map();
function getShot(i) {
  if (!built.has(i)) built.set(i, SHOTS[i].build({ makeStage, W, H }));
  return built.get(i);
}

window.TOTAL_DURATION = DURATION;
window.SHOT_SPANS = SHOTS.map(s => [s.start, s.end]);

window.renderAtTime = (rawT) => {
  const t = Math.max(0, Math.min(rawT, DURATION - 1e-4));
  let idx = SHOTS.findIndex(s => t >= s.start && t < s.end);
  if (idx < 0) idx = SHOTS.length - 1;
  const def = SHOTS[idx];
  const prevDef = idx > 0 ? SHOTS[idx - 1] : null;
  const shot = getShot(idx);
  const lt = Math.max(0, t - def.start);
  const dur = Math.max(0.2, def.end - def.start);
  const r = shot.update(lt, t) || {};
  const cam = shot.camera;

  // Deterministic transition execution on camera + optical shader grade (verified on pixels!)
  let tZoom = 0.0, tWhip = 0.0, tWipe = 0.0, tFlash = 0.0;
  const outTr = def.tr || 'cut';
  const inTr = prevDef ? (prevDef.tr || 'cut') : 'cut';
  const rem = def.end - t;

  if (idx < SHOTS.length - 1 && outTr === 'zoom_through' && rem < 0.16) {
    const p = 1.0 - rem / 0.16;
    cam.fov = Math.max(14, (cam.fov || 34) * (1.0 - 0.34 * p * p));
    tZoom = p * 0.9;
  } else if (inTr === 'zoom_through' && lt < 0.16) {
    const p = 1.0 - lt / 0.16;
    cam.fov = Math.max(14, (cam.fov || 34) * (1.0 + 0.28 * p * p));
    tZoom = p * 0.75;
  }

  if (idx < SHOTS.length - 1 && outTr === 'whip_pan' && rem < 0.12) {
    const p = 1.0 - rem / 0.12;
    cam.rotation.y += p * p * 0.42;
    tWhip = p * 1.0;
  } else if (inTr === 'whip_pan' && lt < 0.12) {
    const p = 1.0 - lt / 0.12;
    cam.rotation.y -= p * p * 0.42;
    tWhip = -p * 1.0;
  }

  if ((idx < SHOTS.length - 1 && outTr === 'match_cut' && rem < 0.10) || (inTr === 'match_cut' && lt < 0.10)) {
    const dist = (idx < SHOTS.length - 1 && rem < 0.10) ? (1.0 - rem / 0.10) : (1.0 - lt / 0.10);
    tFlash = dist * 0.55;
  }

  if (idx < SHOTS.length - 1 && outTr === 'object_wipe' && rem < 0.14) {
    tWipe = 0.5 * (1.0 - rem / 0.14) + 0.02;
  } else if (inTr === 'object_wipe' && lt < 0.14) {
    tWipe = 0.5 + 0.5 * (lt / 0.14);
  }

  cam.aspect = W / H; cam.updateProjectionMatrix();
  shot.scene.userData.sky.position.copy(cam.position);
  renderPass.scene = shot.scene;
  renderPass.camera = cam;
  bloom.strength = (r.bloom ?? 0.30) * 0.52;
  grade.uniforms.uZoom.value = tZoom;
  grade.uniforms.uWhip.value = tWhip;
  grade.uniforms.uWipe.value = tWipe;
  grade.uniforms.uFlash.value = tFlash;
  renderer.toneMappingExposure = r.exposure ?? 1.03;
  composer.render();

  const c = CAPTIONS.filter(c => t >= c[0]).pop();
  capEl.textContent = c && (c[2] == null || t < c[2]) ? c[1] : '';
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


def _roman_shot_code(i: int, shot: Dict[str, Any], total_shots: int) -> str:
    start, end = shot["start"], shot["end"]
    dur = max(0.2, round(end - start, 3))
    low = shot["narration_text"].lower()
    setup = shot["setup_type"]

    # 1. Hook ("In Rome, killing your opponent could cost a fortune.")
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

  const c = cam(39);
  return {{
    scene, camera: c,
    update(lt) {{
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
      const s = shake(lt, 0.4, 1);
      place(c, [lerp(-0.35, 0.15, easeInOut(u)) + s[0], lerp(1.26, 1.12, easeInOut(u)) + s[1], lerp(4.05, 3.35, easeInOut(u))], [0.0, 0.90, 0.10]);
      return {{ bloom: 0.34 }};
    }}
  }};
}}"""

    # 2. Slow-motion blade halting inches from chest + Red Force Ripple ("You expect the final blow. But it doesn't come.")
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

  const c = cam(36);
  const TI = {TI};
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      const before = easeOut(clamp(lt / TI, 0, 1));
      const hitT = lt - TI;
      const tremble = hitT > 0 ? Math.sin(hitT * 26) * Math.exp(-hitT * 2.2) * 0.014 : 0;

      fallen.setPose({{
        drop: -0.48,
        pelvis: [-0.25, 0.1, 0], spine: [-0.24, 0, 0], chest: [-0.15 + tremble, 0, 0],
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

      const shk = hitT > 0 && hitT < 0.35 ? shake(lt * 10, 2.2, {i}) : shake(lt, 0.32, {i});
      place(c, [lerp(0.62, 0.40, easeInOut(u)) + shk[0], lerp(1.22, 1.14, u) + shk[1], lerp(1.98, 1.66, easeInOut(u))], [0.02, 1.00, 0.16]);
      return {{ bloom: hitT > 0 && hitT < 0.35 ? 0.62 : 0.34 }};
    }}
  }};
}}"""

    # 3. Balance Scale 50X Catch ("Here's the catch: if a rented gladiator died... fifty times the rental fee.")
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
  rippleDisc.rotation.x = -Math.PI / 2;
  rippleDisc.position.set(0.32, 0.05, 0.05);
  scene.add(rippleDisc);
  const rp = rippleOverlay(rippleDisc);

  const sp = sparks(110, {{ speed: 1.5, spread: 1.6, gravity: -3.5, life: 0.75, size: 0.015, seed: 50, color: [1.0, 0.78, 0.18] }});
  sp.position.set(0.32, 0.92, 0.05); scene.add(sp);

  const c = cam(39);
  const TSLAM = {TSLAM};
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      const dropProgress = easeOut(clamp((lt - TSLAM) / 0.35, 0, 1));
      const bounce = lt > TSLAM ? Math.exp(-(lt - TSLAM) * 5.2) * Math.sin((lt - TSLAM) * 18) * 0.08 : 0;

      scaleObj.stack50x.coins.forEach((cn, idx) => {{
        const reveal = clamp(dropProgress * 24 - idx * 0.45, 0, 1);
        cn.visible = reveal > 0.02;
        cn.scale.setScalar(easeOut(reveal));
      }});
      scaleObj.setTilt(-0.34 * dropProgress + bounce);

      const it = lt - TSLAM;
      const ru = rp.material.uniforms;
      ru.uCenter.value.set(0, 0, 0);
      ru.uAmp.value = it > 0 ? Math.min(1.0, it * 5.0) * (1.0 - 0.25 * smooth(range(it, 0.9, 2.5))) : 0.0;
      ru.uRadius.value = it > 0 ? 0.06 + easeOut(range(it, 0, 1.2)) * 0.38 : 0.0;
      ru.uRings.value = 150.0; ru.uSpot.value = 0.06; ru.uSpotAmp.value = 0.9; ru.uTime.value = lt;
      sp.update(it - 0.15);

      const shk = it > 0 && it < 0.45 ? shake(lt * 10, 2.4, 50) : shake(lt, 0.35, 50);
      place(c, [lerp(-0.28, 0.20, easeInOut(u)) + shk[0], lerp(1.18, 1.26, u) + shk[1], lerp(3.45, 3.05, easeInOut(u))], [0.0, 0.96, 0.05]);
      return {{ bloom: it > 0 && it < 0.4 ? 0.58 : 0.34 }};
    }}
  }};
}}"""

    # 4. Knocked down / Towering opponent ("knocked into the sand", "stands over him")
    if "knocked into the sand" in low or "stands over him" in low or "sword ready" in low:
        is_up_angle = "stands over him" in low or "sword ready" in low
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.0, sunDir: [-2.5, 7, 4] }});
  scene.add(arenaStage({{ radius: 4.5, wallArc: true }}));

  const fallen = makeHuman('vest'); addGladiatorBracers(fallen);
  fallen.root.position.set(-0.20, 0, 0.28); fallen.root.rotation.y = 0.42; scene.add(fallen.root);
  const droppedSh = romanScutum();
  droppedSh.position.set(-0.52, 0.045, 0.48); droppedSh.rotation.set(-Math.PI / 2, 0.25, 0.38); droppedSh.scale.setScalar(0.76); scene.add(droppedSh);

  const opp = makeHuman('plate'); addGladiatorBracers(opp);
  opp.root.position.set(0.28, 0, -0.32); opp.root.rotation.y = -0.32; scene.add(opp.root);
  const oHelm = romanHelmet(0xc92a2a); opp.j.head.add(oHelm);
  const oSw = sword(); opp.j.rWr.add(oSw); oSw.position.set(0, -0.065, 0); oSw.rotation.x = Math.PI / 2;

  const spDust = sparks(45, {{ speed: 1.1, spread: 1.4, gravity: -2.8, life: 0.75, size: 0.016, seed: 12, dir: V(0, 0.5, 0.4), color: [0.95, 0.78, 0.52] }});
  spDust.position.set(-0.20, 0.08, 0.28); scene.add(spDust);
  const c = cam(39);
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      const dropImpact = {'1.0' if is_up_angle else 'easeOut(clamp(u * 2.1, 0, 1))'};
      const slump = Math.sin(u * Math.PI) * 0.03;
      fallen.setPose({{
        drop: -0.45 * dropImpact - 0.06,
        pelvis: [-0.22 * dropImpact, 0.15, 0], spine: [-0.28 * dropImpact + slump, 0, 0], chest: [-0.15 * dropImpact, -0.1, 0],
        neck: [-0.32, 0.12, 0], head: [-0.24, 0.15, 0],
        lHip: [-1.18, 0, 0.18], lKn: [1.58, 0, 0], rHip: [-0.72, 0, -0.18], rKn: [1.35, 0, 0],
        lSh: [0.42, 0, 0.35], lEl: [-0.25, 0, 0], rSh: [-0.82, -0.1, -0.25], rEl: [-0.65, 0, 0],
      }});
      fallen.setMouth(dropImpact > 0.3 ? 0.52 : 0.1);
      const raise = {'lerp(0.65, 1.0, easeInOut(u))' if is_up_angle else 'easeInOut(range(lt, 0.4, 2.0))'};
      opp.setPose({{
        ...STAND, drop: -0.05,
        spine: [0.12, 0.18 * raise, 0], chest: [0.12, 0.22 * raise, 0],
        neck: [0.22, -0.12, 0], head: [0.15, -0.08, 0],
        lSh: [-0.25, 0, 0.32], lEl: [-0.55, 0, 0],
      }});
      opp.root.updateMatrixWorld(true);
      const handPos = opp.root.localToWorld(V(lerp(-0.25, -0.12, raise), lerp(1.38, 1.88, raise), lerp(0.32, 0.22, raise)));
      const tipHint = V(lerp(0.1, -0.15, raise), lerp(-0.5, 0.65, raise), lerp(0.9, 0.45, raise)).applyQuaternion(opp.root.quaternion);
      ikArm(opp, 'r', handPos, opp.root.localToWorld(V(-0.55, 1.25, -0.45)), tipHint);

      spDust.update(lt - 0.15);
      const s = shake(lt, dropImpact < 0.8 ? 1.8 : 0.4, {i});
      {'place(c, [lerp(-0.72, -0.42, easeInOut(u)) + s[0], lerp(0.88, 1.22, u) + s[1], lerp(2.75, 2.35, easeInOut(u))], [0.05, 0.92, 0.0]);' if is_up_angle else 'place(c, [lerp(-0.98, -0.58, easeInOut(u)) + s[0], lerp(1.05, 1.18, u) + s[1], lerp(3.45, 2.85, easeInOut(u))], [0.02, 0.85, 0.0]);'}
      return {{ bloom: 0.30 }};
    }}
  }};
}}"""

    # 5. Training & Preparation ("These fighters were expensive to train, feed, and prepare.")
    if "train" in low or "feed" in low or "prepare" in low:
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.0, sunDir: [-3, 7, 5] }});
  scene.add(arenaStage({{ radius: 4.5, wallArc: true }}));

  const trainee = makeHuman('vest'); addGladiatorBracers(trainee);
  trainee.root.position.set(-0.34, 0, 0.12); trainee.root.rotation.y = 0.88; scene.add(trainee.root);
  const tSh = romanScutum(); trainee.j.lEl.add(tSh); tSh.position.set(0.08, -0.15, 0.06); tSh.rotation.set(0, 1.15, 0); tSh.scale.setScalar(0.80);
  const tSw = sword(); trainee.j.rWr.add(tSw); tSw.position.set(0, -0.065, 0); tSw.rotation.x = Math.PI / 2;

  const palus = trainingPalus();
  palus.position.set(0.32, 0, -0.04); scene.add(palus);

  const spHit = sparks(55, {{ speed: 1.2, spread: 1.4, gravity: -3.5, life: 0.55, size: 0.013, seed: 34, dir: V(-1, 0.4, 0.5), color: [1.0, 0.72, 0.25] }});
  spHit.position.set(0.24, 1.05, 0.0); scene.add(spHit);

  const tab = romanScrollTablet('TRAINING', 'COSTS', 0xf4c430);
  tab.scale.setScalar(0.50); tab.position.set(0.24, 1.82, -0.04); scene.add(tab);

  const c = cam(39);
  const TH = 1.25;
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      const strike = easeIn(range(lt, 0.4, TH));
      const rec = lt > TH ? Math.sin(Math.min(lt - TH, 0.6) / 0.6 * Math.PI) * 0.12 : 0;
      trainee.setPose({{
        ...STAND, drop: -0.08,
        spine: [0.10, lerp(-0.22, 0.35, strike), 0], chest: [0.06, lerp(-0.20, 0.28, strike), 0],
        lSh: [-0.52, 0.2, 0.25], lEl: [-0.85, 0, 0],
        rSh: [lerp(-0.35, -1.05, strike), lerp(-0.35, 0.22, strike), -0.2], rEl: [lerp(-0.95, -0.35, strike), 0, 0],
      }});
      palus.rotation.z = -rec * 0.35;
      spHit.update(lt - TH);
      const s = shake(lt, lt > TH && lt < TH + 0.35 ? 1.8 : 0.35, {i});
      place(c, [lerp(-0.45, 0.28, easeInOut(u)) + s[0], lerp(1.18, 1.12, u) + s[1], lerp(3.45, 2.95, easeInOut(u))], [0.0, 0.96, 0.05]);
      return {{ bloom: 0.32 }};
    }}
  }};
}}"""

    # 6. Rental contract over stone counter ("Organizers often rented them from their owners.")
    if "rented" in low or "owners" in low:
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.0, sunDir: [-3, 7, 4] }});
  scene.add(arenaStage({{ radius: 4.5, wallArc: true }}));

  const fighter = makeHuman('chainmail'); addGladiatorBracers(fighter);
  fighter.root.position.set(-0.40, 0, -0.05); fighter.root.rotation.y = 0.25; scene.add(fighter.root);
  const fSh = romanScutum(); fighter.j.lEl.add(fSh); fSh.position.set(0.08, -0.15, 0.06); fSh.rotation.set(0, 1.15, 0); fSh.scale.setScalar(0.76);

  const org = makeHuman('vest'); addGladiatorBracers(org);
  org.root.position.set(0.42, 0, 0.08); org.root.rotation.y = -0.38; scene.add(org.root);
  org.j.chest.add(togaSash());

  const plinth = romanPlinth(0.84, 0.20); plinth.position.set(0.02, 0, 0.28); scene.add(plinth);
  const stack = denariusStack({{ count: 10, radius: 0.062, height: 0.017, gold: true }});
  stack.position.set(0.02, 0.85, 0.28); scene.add(stack);

  const tab = romanScrollTablet('GLADIATOR', 'RENTED', 0xf4c430);
  tab.scale.setScalar(0.50); tab.position.set(0.02, 1.48, 0.16); scene.add(tab);

  const c = cam(39);
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      fighter.setPose({{
        ...STAND, chest: [Math.sin(lt * 1.8) * 0.02, 0.1, 0],
        lSh: [-0.28, 0, 0.28], lEl: [-0.85, 0, 0], rSh: [-0.30, -0.1, -0.22], rEl: [-0.55, 0, 0],
      }});
      org.setPose({{
        ...STAND,
        chest: [0.04, -0.12, 0], head: [Math.sin(lt * 2.5) * 0.05, -0.18, 0],
        lSh: [-0.55 - easeInOut(u) * 0.2, 0.1, 0.22], lEl: [-0.65, 0, 0],
      }});
      org.setMouth(0.2 + 0.22 * Math.abs(Math.sin(lt * 7.0)));
      const rise = easeOut(clamp(u * 1.8, 0, 1));
      stack.coins.forEach((cn, k) => {{ cn.visible = k < Math.max(1, Math.round(rise * 10)); }});
      stack.rotation.y = lt * 0.9;
      const s = shake(lt, 0.35, {i});
      place(c, [lerp(-0.28, 0.24, easeInOut(u)) + s[0], lerp(1.22, 1.16, u) + s[1], lerp(3.45, 3.05, easeInOut(u))], [0.0, 1.02, 0.05]);
      return {{ bloom: 0.32 }};
    }}
  }};
}}"""

    # 7. Losing didn't mean death / Granted mercy ("losing a match", "granted mercy", "leave the arena alive")
    if "losing a match" in low or "mercy" in low and ("alive" in low or "leave" in low):
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.0, sunDir: [-3, 7, 5] }});
  scene.add(arenaStage({{ radius: 4.5, wallArc: true }}));

  const fighter = makeHuman('vest'); addGladiatorBracers(fighter);
  fighter.root.position.set(-0.28, 0, 0.10); fighter.root.rotation.y = 0.35; scene.add(fighter.root);

  const victor = makeHuman('plate'); addGladiatorBracers(victor);
  victor.root.position.set(0.38, 0, -0.06); victor.root.rotation.y = -0.45; scene.add(victor.root);
  const vHelm = romanHelmet(0xd9a441); victor.j.head.add(vHelm);
  const vSw = sword(); victor.j.rWr.add(vSw); vSw.position.set(0, -0.065, 0); vSw.rotation.x = Math.PI / 2;

  const badge = romanScrollTablet('MERCY', 'ALIVE', 0x52b788);
  badge.scale.setScalar(0.50); badge.position.set(0.04, 1.80, 0.06); scene.add(badge);

  const sp = sparks(45, {{ speed: 0.65, spread: 1.5, gravity: 0.4, life: 1.2, size: 0.015, seed: 71, dir: V(0, 1, 0), color: [0.4, 0.95, 0.55] }});
  sp.position.set(-0.2, 0.85, 0.15); scene.add(sp);
  const c = cam(39);
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      const standUp = easeInOut(clamp(u * 1.35, 0, 1));
      fighter.setPose({{
        drop: lerp(-0.36, -0.02, standUp),
        spine: [lerp(-0.16, 0.02, standUp), 0, 0], chest: [lerp(-0.08, 0.03, standUp), 0.10, 0],
        head: [lerp(-0.18, 0.0, standUp), 0.20, 0],
        lHip: [lerp(-0.90, 0.0, standUp), 0, 0.1], lKn: [lerp(1.20, 0.0, standUp), 0, 0],
        rHip: [lerp(-0.52, 0.0, standUp), 0, -0.1], rKn: [lerp(0.90, 0.0, standUp), 0, 0],
        lSh: [lerp(0.2, -0.15, standUp), 0, 0.25], rSh: [lerp(0.15, -0.35, standUp), 0, -0.25],
      }});
      fighter.setMouth(0.15 + 0.12 * standUp);
      victor.setPose({{
        ...STAND,
        chest: [0.02, -0.20, 0], head: [0.02, -0.20, 0],
        lSh: [-0.52 * standUp, 0.1, 0.28], lEl: [-0.58, 0, 0],
        rSh: [lerp(-0.45, 0.12, standUp), 0, -0.25], rEl: [lerp(-0.7, -0.15, standUp), 0, 0],
      }});
      badge.scale.setScalar(0.50 * easeOut(clamp(u * 2.2, 0, 1)));
      sp.update(lt - 0.35);
      const s = shake(lt, 0.32, {i});
      place(c, [lerp(0.45, -0.22, easeInOut(u)) + s[0], lerp(1.18, 1.26, u) + s[1], lerp(3.25, 3.45, easeInOut(u))], [0.02, 1.00, 0.04]);
      return {{ bloom: 0.35 }};
    }}
  }};
}}"""

    # 8. Valuable investment / financial sense ("valuable investment", "financial sense")
    if "investment" in low or "financial sense" in low:
        tab_top = 'INVESTMENT' if 'investment' in low else 'MATH'
        tab_bot = 'SAVED' if 'investment' in low else 'CLEAR'
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.0, sunDir: [-3, 7, 5] }});
  scene.add(arenaStage({{ radius: 4.5, wallArc: true }}));

  const org = makeHuman('vest'); addGladiatorBracers(org);
  org.root.position.set(-0.34, 0, 0.05); org.root.rotation.y = 0.28; scene.add(org.root);
  org.j.chest.add(togaSash());

  const plinth = romanPlinth(0.84, 0.22); plinth.position.set(0.30, 0, 0.15); scene.add(plinth);
  const coins = denariusStack({{ count: 16, radius: 0.070, height: 0.017, gold: true }});
  coins.position.set(0.30, 0.85, 0.15); scene.add(coins);
  const tab = romanScrollTablet('{tab_top}', '{tab_bot}', 0x52b788);
  tab.scale.setScalar(0.48); tab.position.set(0.30, 1.54, 0.15); scene.add(tab);

  const c = cam(39);
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      org.setPose({{
        ...STAND,
        chest: [0.03, -0.18, 0], head: [0.04, -0.22, 0],
        rSh: [-0.72 - Math.sin(u * Math.PI) * 0.18, 0.12, -0.22], rEl: [-0.45, 0, 0],
      }});
      org.setMouth(0.18 + 0.18 * Math.abs(Math.sin(lt * 6.0)));
      coins.rotation.y = lt * 0.85;
      tab.rotation.y = -0.15 + Math.sin(lt * 1.5) * 0.08;
      const s = shake(lt, 0.32, {i});
      place(c, [lerp(-0.32, 0.22, easeInOut(u)) + s[0], lerp(1.22, 1.16, u) + s[1], lerp(3.35, 3.05, easeInOut(u))], [0.0, 1.00, 0.08]);
      return {{ bloom: 0.34 }};
    }}
  }};
}}"""

    # 9. Final Payoff ("The danger was real... bill.")
    if i == total_shots - 1 or setup == "payoff_full_stage_reveal" or "bill" in low:
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 4.5, sunDir: [-3, 7, 5] }});
  scene.add(arenaStage({{ radius: 4.6, wallArc: true }}));

  const fighter = makeHuman('vest'); addGladiatorBracers(fighter);
  fighter.root.position.set(-0.34, 0, 0.10); fighter.root.rotation.y = 0.25; scene.add(fighter.root);
  const fHelm = romanHelmet(0xd9a441); fighter.j.head.add(fHelm);
  const fSh = romanScutum(); fighter.j.lEl.add(fSh); fSh.position.set(0.08, -0.15, 0.06); fSh.rotation.set(0, 1.15, 0); fSh.scale.setScalar(0.82);
  const fSw = sword(); fighter.j.rWr.add(fSw); fSw.position.set(0, -0.065, 0); fSw.rotation.x = Math.PI / 2;

  const ped = romanPlinth(0.68, 0.22); ped.position.set(0.32, 0, 0.15); scene.add(ped);
  const coins = denariusStack({{ count: 20, radius: 0.072, height: 0.017, gold: true }});
  coins.position.set(0.32, 0.69, 0.15); scene.add(coins);
  const billTab = romanScrollTablet('SURVIVAL', 'THE BILL', 0xf5b700);
  billTab.scale.setScalar(0.48); billTab.position.set(0.32, 1.48, 0.15); scene.add(billTab);

  const sp = sparks(65, {{ speed: 0.9, spread: 1.8, gravity: 0.3, life: 1.4, size: 0.016, seed: 99, dir: V(0, 1, 0), color: [1.0, 0.85, 0.25] }});
  sp.position.set(0.32, 1.05, 0.15); scene.add(sp);
  const c = cam(39);
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      fighter.setPose({{
        ...STAND,
        chest: [Math.sin(lt * 1.8) * 0.02, -0.08, 0], head: [0.02, -0.10, 0],
        lSh: [-0.25, 0.15, 0.25], lEl: [-0.65, 0, 0],
        rSh: [-0.45 - Math.sin(u * Math.PI) * 0.22, 0, -0.25], rEl: [-0.45, 0, 0],
      }});
      coins.rotation.y = lt * 0.7;
      billTab.rotation.y = Math.sin(lt * 1.4) * 0.10 - 0.12;
      sp.update(lt - 0.15);
      const s = shake(lt, 0.32, 9);
      place(c, [lerp(-0.18, 0.05, easeInOut(u)) + s[0], lerp(1.16, 1.38, easeInOut(u)) + s[1], lerp(3.15, 3.85, easeInOut(u))], [0.0, 0.98, 0.08]);
      return {{ bloom: 0.38 }};
    }}
  }};
}}"""

    # 10. Suspense / Danger ("mercy was never guaranteed", "danger was real")
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

  const sw = sword();
  sw.position.set(0.42, 1.62, -0.10); sw.rotation.set(0.25, 0, 2.75); scene.add(sw);
  const badge = romanScrollTablet('MERCY?', 'NOT SURE', 0xe63946);
  badge.scale.setScalar(0.48); badge.position.set(0.28, 1.54, 0.16); scene.add(badge);

  const c = cam(39);
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      org.setPose({{
        ...STAND,
        chest: [Math.sin(lt * 2.1) * 0.02, -0.14, 0], head: [0.04, -0.20 + Math.sin(lt * 3.0) * 0.08, 0],
        rSh: [-0.58 - easeOut(u) * 0.18, 0, -0.26], rEl: [-0.55, 0, 0],
      }});
      org.setMouth(0.22 + 0.2 * Math.abs(Math.sin(lt * 6.0)));
      coins.rotation.y = lt * 0.95;
      sw.position.y = 1.60 + Math.sin(lt * 2.8) * 0.04;
      const s = shake(lt, 0.45, {i});
      place(c, [lerp(0.40, -0.18, easeInOut(u)) + s[0], lerp(1.20, 1.14, u) + s[1], lerp(3.35, 3.00, easeInOut(u))], [0.0, 1.00, 0.10]);
      return {{ bloom: 0.34 }};
    }}
  }};
}}"""


def _cam_helper_js(cam_path: Dict[str, Any] | None, fallback_pos: List[float], fallback_look: List[float], fallback_fov: int) -> str:
    kfs = (cam_path or {}).get("keyframes") or [
        {"t_norm": 0.0, "pos": fallback_pos, "look": fallback_look, "fov": fallback_fov, "roll": 0.0},
        {"t_norm": 1.0, "pos": fallback_pos, "look": fallback_look, "fov": fallback_fov, "roll": 0.0},
    ]
    return json.dumps(kfs)


def _build_non_roman_scene_shot_code(i: int, s: Dict[str, Any], total_shots: int, seed: int = 42) -> str:
    start, end = s["start"], s["end"]
    dur = max(0.2, round(end - start, 3))
    gen = str(s.get("procedural_generator") or "")
    prop = str((s.get("staging") or {}).get("visual_metaphor") or "idea_spark")
    is_callback = bool(s.get("callback_reason"))
    cam_path = s.get("camera_path")
    kfs_json = _cam_helper_js(cam_path, [0.4, 1.38, 2.0], [0.0, 1.18, 0.0], 34)
    shirt_palette = [0x2563eb, 0x0d9488, 0x4f46e5, 0xd97706, 0x0284c7]
    shirt_hex = shirt_palette[i % len(shirt_palette)]

    if gen == "zach3d:human_device_stage" or (prop == "phone_screen" and gen != "zach3d:device_cutaway_stage"):
        sent_flag = "true" if (is_callback or i == total_shots - 1) else "false"
        theme = "lab_studio" if sent_flag == "true" else "day"
        return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 2.6, skyTheme: '{theme}' }});
  const man = makeModernOutfitCharacter(makeHuman, {shirt_hex});
  man.root.position.set(-0.24, 0, 0); man.root.rotation.y = 0.28; scene.add(man.root);
  const phone = makeSmartphoneRig({{ sent: {sent_flag}, scale: 0.78 }});
  phone.position.set(0.26, 1.36, 0.28); phone.rotation.set(-0.16, -0.34, 0.05);
  scene.add(phone);
  const sp = sparks(45, {{ speed: 0.45, spread: 1.4, gravity: -0.2, life: 0.7, size: 0.008, dir: V(0, 0.2, 1), seed: {seed + i}, color: [0.22, 0.74, 0.97] }});
  sp.position.set(0.26, 1.30, 0.32); scene.add(sp);
  const KFS = {kfs_json};
  const c = cam(KFS[0].fov || 35);
  const T_TAP = {round(dur * 0.42, 3)};
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      const tapU = smooth(range(lt, T_TAP - 0.14, T_TAP + 0.06));
      const postTap = lt - T_TAP;
      man.setPose({{
        ...STAND,
        chest: [0.06 * tapU, 0.20, 0],
        head: [0.08 + 0.04 * tapU, 0.16, -0.04],
        lSh: [-0.82, 0.25, 0.22], lEl: [-0.95, 0, 0],
        rSh: [-0.88 - 0.18 * tapU, -0.18, -0.18], rEl: [-0.92 + 0.14 * Math.sin(tapU * Math.PI), 0, 0],
      }});
      man.setMouth({0.35 if sent_flag == 'true' else 0.14} + 0.15 * Math.abs(Math.sin(lt * 5.0)));
      phone.rotation.y = -0.34 + Math.sin(lt * 1.4) * 0.04;
      if (postTap > 0) {{
        const ringU = clamp(postTap / 0.55, 0, 1);
        phone.tapRing.scale.setScalar(0.5 + easeOut(ringU) * 3.2);
        phone.tapRing.material.opacity = (1.0 - ringU) * 0.95;
      }} else {{
        phone.tapRing.material.opacity = 0.0;
      }}
      sp.update(postTap);
      const poseCam = evalCamPath(KFS, u);
      c.fov = poseCam.fov;
      place(c, [lerp(0.55, 0.24, u), lerp(1.50, 1.40, u), lerp(2.78, 2.28, easeInOut(u))], [0.02, 1.20, 0.12], poseCam.roll * 0.4);
      return {{ bloom: postTap > 0 && postTap < 0.35 ? 0.62 : 0.30 }};
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
  const c = cam(KFS[0].fov || 32);
  return {{
    scene, camera: c,
    update(lt) {{
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
      const poseCam = evalCamPath(KFS, u);
      c.fov = poseCam.fov;
      place(c, [Math.sin(u * 0.8 - 0.3) * 1.32, lerp(1.48, 1.32, u), lerp(2.15, 1.68, easeInOut(u))], [0.0, 1.22, 0.02], poseCam.roll * 0.3);
      return {{ bloom: 0.48 }};
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
  const c = cam(KFS[0].fov || 36);
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      tower.beacon.material.emissiveIntensity = 1.1 + Math.abs(Math.sin(lt * 5.0)) * 1.4;
      tower.rfRings.forEach((rm, k) => {{
        const prog = ((lt * 0.85 + k * 0.25) % 1.0);
        rm.scale.setScalar(0.5 + prog * 4.4);
        rm.material.opacity = (1.0 - prog) * 0.88;
      }});
      const poseCam = evalCamPath(KFS, u);
      c.fov = poseCam.fov;
      place(c, [lerp(-1.25, 0.85, easeInOut(u)), lerp(1.25, 2.55, u), lerp(2.85, 2.25, u)], [0.0, lerp(1.65, 2.30, u), 0.0]);
      return {{ bloom: 0.44 }};
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
  const c = cam(KFS[0].fov || 34);
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      rig.pulses.forEach((p, k) => {{
        const s = ((lt * 1.35 + k * 0.167) % 1.0);
        p.position.set(lerp(-1.65, 1.70, s), 0.0, 0.0);
      }});
      const poseCam = evalCamPath(KFS, u);
      c.fov = poseCam.fov;
      place(c, [lerp(-1.65, 1.45, easeInOut(u)), lerp(1.42, 0.98, u), lerp(2.95, 2.30, u)], [0.0, 0.36, 0.0], poseCam.roll * 0.25);
      return {{ bloom: 0.56 }};
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
  const c = cam(KFS[0].fov || 38);
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      dc.packets.forEach((sp, k) => {{
        const cyc = ((lt * 1.6 + k * 0.16) % 1.0);
        sp.position.z = lerp(1.4, -3.2, cyc);
        sp.position.x = Math.sin(lt * 3 + k) * 0.08;
      }});
      const poseCam = evalCamPath(KFS, u);
      c.fov = poseCam.fov;
      place(c, [Math.sin(u * 1.2) * 0.16, lerp(1.32, 1.55, u), lerp(2.85, 0.45, easeInOut(u))], [0.0, 1.18, -2.5]);
      return {{ bloom: 0.50 }};
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
  const c = cam(KFS[0].fov || 34);
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      tb.rotor.rotation.z = -lt * (4.5 + u * 6.5);
      tb.coilGlow.material.emissiveIntensity = 1.0 + 0.65 * Math.abs(Math.sin(lt * 7.5));
      const poseCam = evalCamPath(KFS, u);
      c.fov = poseCam.fov;
      place(c, [Math.sin(u * 0.85 - 0.4) * 1.85, lerp(1.55, 1.25, u), Math.cos(u * 0.85 - 0.4) * 1.85], [0.0, 1.12, 0.0]);
      return {{ bloom: 0.48 }};
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
  const c = cam(KFS[0].fov || 38);
  return {{
    scene, camera: c,
    update(lt) {{
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
      const poseCam = evalCamPath(KFS, u);
      c.fov = poseCam.fov;
      place(c, [lerp(-0.55, 0.75, easeInOut(u)), lerp(1.32, 1.95, u), lerp(2.15, 3.65, easeInOut(u))], [0.0, 1.25, 0.0], poseCam.roll * 0.25);
      return {{ bloom: 0.68 }};
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
  const c = cam(KFS[0].fov || 32);
  return {{
    scene, camera: c,
    update(lt) {{
      const u = clamp(lt / {dur}, 0, 1);
      const pulse = 1.0 + 0.065 * Math.sin(lt * 5.2);
      rig.lobes.forEach(l => l.scale.set(0.85 * pulse, 1.05 * pulse, 1.0 * pulse));
      rig.sparkNodes.forEach((nd, k) => {{
        nd.material.emissiveIntensity = 0.8 + 1.2 * Math.max(0, Math.sin(lt * 6.0 + k * 1.1));
      }});
      rig.rotation.y = lerp(-0.45, 0.35, easeInOut(u));
      const poseCam = evalCamPath(KFS, u);
      c.fov = poseCam.fov;
      place(c, [lerp(0.55, 0.15, easeInOut(u)), 1.32, lerp(1.55, 1.10, easeInOut(u))], [0.0, 1.25, 0.0]);
      return {{ bloom: 0.45 }};
    }}
  }};
}}"""

    # Default General Non-Roman Studio Demonstrator: stylized modern character + grounded prop (ZERO armor!)
    return f"""
function shot_{i}({{ makeStage }}) {{
  const scene = makeStage({{ shadowSize: 2.8, skyTheme: 'lab_studio' }});
  const man = makeModernOutfitCharacter(makeHuman, {shirt_hex});
  man.root.position.set(-0.24, 0, 0); man.root.rotation.y = 0.32; scene.add(man.root);
  const ped = forcePedestal(); ped.position.set(0.32, 0, 0.08); scene.add(ped);
  const gearStage = makeVaultGearStage();
  gearStage.scale.setScalar(0.52); gearStage.position.set(0.32, 0.98, 0.08); scene.add(gearStage);
  const core = energyCore({0xf59e0b if i == total_shots - 1 else 0x38bdf8});
  core.position.set(0.32, 1.44, 0.08); core.scale.setScalar(0.56); scene.add(core);
  const KFS = {kfs_json};
  const c = cam(KFS[0].fov || 34);
  return {{
    scene, camera: c,
    update(lt) {{
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
      const poseCam = evalCamPath(KFS, u);
      c.fov = poseCam.fov;
      place(c, poseCam.pos, poseCam.look, poseCam.roll);
      return {{ bloom: 0.34 }};
    }}
  }};
}}"""


def _build_zach_shots_js(storyboard: Dict[str, Any], words: List[Dict[str, Any]]) -> str:
    shots = storyboard["shots"]
    total_dur = storyboard["total_duration_sec"]
    seed = int(storyboard.get("seed", 42))
    captions = _build_captions_list(words)
    motifs = set(storyboard.get("entities_and_facts", {}).get("detected_motifs", []))
    is_roman = bool({"roman_gladiator", "roman_ledger_50x"} & motifs)

    fades: List[List[float]] = []
    for s in shots:
        if s["transition_out"] == "dip_to_black":
            t_c = s["end"]
            fades.append([round(t_c - 0.16, 3), round(t_c - 0.03, 3), round(t_c + 0.04, 3), round(t_c + 0.18, 3)])

    fn_blocks: List[str] = []
    list_entries: List[str] = []

    for i, s in enumerate(shots):
        tr_out = str(s.get("transition_out") or "cut")
        if is_roman:
            fn_blocks.append(_roman_shot_code(i, s, len(shots)))
        else:
            fn_blocks.append(_build_non_roman_scene_shot_code(i, s, len(shots), seed=seed))
        list_entries.append(f"  {{ start: {s['start']}, end: {s['end']}, tr: {json.dumps(tr_out)}, build: shot_{i} }},")

    novel_imports = (
        """  forcePedestal, energyCore, cutawaySlabStack,
  addGladiatorBracers, romanPlinth, trainingPalus,
  arenaStage, romanHelmet, romanScutum, denariusStack,
  romanScrollTablet, togaSash, balanceScale50x"""
        if is_roman
        else """  forcePedestal, energyCore, cutawaySlabStack,
  makeModernOutfitCharacter, makeSmartphoneRig, makeRadioTowerRig,
  makeSubseaCableRig, makeDatacenterRackBank, makePowerTurbineRig,
  makeCosmicGenesisRig, makeAnatomicalCutawayRig, makeVaultGearStage"""
    )

    header = f"""import * as THREE from 'three';
import {{ makeHuman }} from './human.js';
import {{ sword, sparks, rippleOverlay }} from './props.js';
import {{ clamp, lerp, smooth, easeOut, easeIn, easeInOut, range, V, cam, place, shake, ikArm }} from './anim.js';
import {{
{novel_imports}
}} from './novel_props.js';

export const DURATION = {total_dur};
export const CAPTIONS = {json.dumps(captions, ensure_ascii=False)};
export const FADES = {json.dumps(fades)};

const STAND = {{
  lSh: [0.05, 0, 0.16], rSh: [0.05, 0, -0.16], lEl: [-0.25, 0, 0], rEl: [-0.25, 0, 0],
  lHip: [0, 0, 0.07], rHip: [0, 0, -0.07], lAn: [0, 0, -0.07], rAn: [0, 0, 0.07],
}};

function evalCamPath(kfs, u) {{
  if (!kfs || !kfs.length) return {{ pos: [0.3, 1.38, 2.0], look: [0, 1.18, 0], fov: 34, roll: 0 }};
  const uc = clamp(u, 0, 1);
  for (let i = 0; i < kfs.length - 1; i++) {{
    const a = kfs[i], b = kfs[i + 1];
    if (uc <= b.t_norm + 1e-6) {{
      const segU = easeInOut(clamp((uc - a.t_norm) / Math.max(1e-4, b.t_norm - a.t_norm), 0, 1));
      return {{
        pos: [lerp(a.pos[0], b.pos[0], segU), lerp(a.pos[1], b.pos[1], segU), lerp(a.pos[2], b.pos[2], segU)],
        look: [lerp(a.look[0], b.look[0], segU), lerp(a.look[1], b.look[1], segU), lerp(a.look[2], b.look[2], segU)],
        fov: lerp(a.fov || 34, b.fov || 34, segU),
        roll: lerp(a.roll || 0, b.roll || 0, segU),
      }};
    }}
  }}
  const last = kfs[kfs.length - 1];
  return {{ pos: last.pos, look: last.look, fov: last.fov || 34, roll: last.roll || 0 }};
}}
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

    # Symlink shared neutral kit/node_modules
    nm_link = work_dir / "node_modules"
    os.symlink(str((kit_dir / "node_modules").resolve()), str(nm_link))

    novel_p = src_dst / "novel_props.js"
    novel_p.write_text(NOVEL_3D_PROPS_JS, encoding="utf-8")

    shots_p = src_dst / "shots.js"
    shots_p.write_text(_build_zach_shots_js(storyboard, parsed_script["voice"]["words"]), encoding="utf-8")

    main_p = src_dst / "director_main.js"
    main_p.write_text(DIRECTOR_MAIN_JS, encoding="utf-8")

    index_html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
  @font-face { font-family: 'Cap'; src: url('node_modules/@fontsource/montserrat/files/montserrat-latin-700-normal.woff2') format('woff2'); font-weight: 700; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 1080px; height: 1920px; background: #000; overflow: hidden; }
  #stage { position: relative; width: 1080px; height: 1920px; overflow: hidden; }
  canvas { display: block; width: 1080px; height: 1920px; }
  #cap {
    position: absolute; left: 100px; width: 880px; top: 1390px; text-align: center;
    font: 700 66px/1.1 'Cap', sans-serif; color: #fff; letter-spacing: -0.4px;
    text-shadow: 0 0 4px rgba(0,0,0,.78), 0 4px 16px rgba(0,0,0,.72);
  }
  #fade { position: absolute; inset: 0; background: #000; opacity: 0; pointer-events: none; }
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
        str(novel_p.resolve()),
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
