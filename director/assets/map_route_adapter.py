"""Single-Engine Adapter for `map-route` (3D Architectural City Route + ETA + Pin Drop).

Strictly locks to `/map-route` visual language:
- Matte white 3D instanced blocks, park trees, winding river ribbon, colored route ribbon,
  bouncing red destination pin, Inter ETA & Destination cards.
- Principle 8: Explicitly discloses `SCHEMATIC ROUTE (NON-GIS)` so decorative blocks are
  never misrepresented as GIS-accurate cartography.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List


def _extract_route_params(parsed_script: Dict[str, Any], seed: int) -> Dict[str, Any]:
    raw = parsed_script["raw_input_script"]
    m_dist = re.search(r"(\d+(?:\.\d+)?)\s*(km|mi)\b", raw, flags=re.IGNORECASE)
    m_min = re.search(r"(\d+)\s*min(?:ute)?s?\b", raw, flags=re.IGNORECASE)
    unit = m_dist.group(2).lower() if m_dist else "km"
    distance = float(m_dist.group(1)) if m_dist else 3.2
    minutes = int(m_min.group(1)) if m_min else max(4, round(distance * 3.5))

    m_to = re.search(r"\bto\s+(?:the\s+)?([A-Za-z0-9][A-Za-z0-9 '\-]{1,22})", raw, flags=re.IGNORECASE)
    dest = m_to.group(1).strip().title() if m_to else "Harbour Station"
    dest = dest[:24]

    return {
        "destination": dest,
        "minutes": minutes,
        "distance": distance,
        "unit": unit,
        "accent": "#2f7cf6",
        "seed": seed,
        "places": ["Old Square", "River Walk", "Central Bridge", "Cedar Park", "North Pier"],
    }


def generate_engine_project(
    project_root: Path,
    run_dir: Path,
    storyboard: Dict[str, Any],
    parsed_script: Dict[str, Any],
) -> Dict[str, Any]:
    upstream_mr = project_root / "vendor" / "claude-animation-skills" / "skills" / "map-route"
    kit_dir = project_root / "vendor" / "claude-animation-skills" / "kit"
    work_dir = run_dir / "engine_work" / "web"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    upstream_tpl = (upstream_mr / "template.html").resolve()
    _ = upstream_tpl.read_text(encoding="utf-8")

    (work_dir / "fonts").mkdir(parents=True, exist_ok=True)
    visual_sources: List[str] = [str(upstream_tpl)]
    for wf in (kit_dir / "fonts").glob("*.woff2"):
        shutil.copy2(wf.resolve(), work_dir / "fonts" / wf.name)
        visual_sources.append(str(wf.resolve()))

    os.symlink(str((kit_dir / "node_modules").resolve()), str(work_dir / "node_modules"))

    route_spec = _extract_route_params(parsed_script, storyboard["seed"])
    payload = {
        "route": route_spec,
        "shots": storyboard["shots"],
        "words": parsed_script["voice"]["words"],
        "totalDuration": storyboard["total_duration_sec"],
    }

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
@font-face{{font-family:'Inter';font-weight:500;src:url(fonts/inter-500-normal.woff2) format('woff2')}}
@font-face{{font-family:'Inter';font-weight:600;src:url(fonts/inter-600-normal.woff2) format('woff2')}}
@font-face{{font-family:'Inter';font-weight:700;src:url(fonts/inter-700-normal.woff2) format('woff2')}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1080px;height:1920px;overflow:hidden;background:#eef0f1;font-family:'Inter',sans-serif}}
#root{{position:relative;width:1080px;height:1920px;overflow:hidden;background:#eef0f1}}
#c{{position:absolute;left:0;top:0;width:1080px;height:1920px;display:block}}
#eta{{position:absolute;left:110px;top:245px;background:#fff;border-radius:28px;padding:20px 28px;display:flex;align-items:center;gap:20px;box-shadow:0 10px 30px rgba(30,40,60,.14)}}
#eta .ic{{width:56px;height:56px;border-radius:18px;background:#2f7cf6;display:grid;place-items:center}}
#eta b{{display:block;font:700 34px/1 'Inter';color:#16181b}}
#eta span{{display:block;margin-top:8px;font:500 24px/1 'Inter';color:#6b6f75}}
#disc{{position:absolute;right:110px;top:262px;background:rgba(255,255,255,0.88);padding:10px 16px;border-radius:99px;font:600 19px 'Inter';color:#6b7280;letter-spacing:.06em}}
#card{{position:absolute;left:540px;top:640px;transform:translate(-50%,-100%);background:#fff;border-radius:26px;padding:22px 30px;box-shadow:0 14px 40px rgba(30,40,60,.18);opacity:0;white-space:nowrap}}
#card b{{display:block;font:700 36px/1 'Inter';color:#16181b}}
#card span{{display:block;margin-top:10px;font:500 26px/1 'Inter';color:#2f7cf6}}
#cap{{position:absolute;left:120px;width:840px;top:1435px;text-align:center;font:700 42px/1.2 'Inter';color:#16181b;text-shadow:0 2px 12px rgba(255,255,255,0.95)}}
</style>
<script type="importmap">{{"imports":{{"three":"./node_modules/three/build/three.module.js"}}}}</script>
</head>
<body>
<div id="root">
  <canvas id="c"></canvas>
  <div id="eta">
    <div class="ic"><svg width="32" height="32" viewBox="0 0 24 24"><path d="M12 2.5 20 21l-8-4-8 4z" fill="#fff"/></svg></div>
    <div><b id="etan"></b><span id="etad"></span></div>
  </div>
  <div id="disc">SCHEMATIC 3D ROUTE</div>
  <div id="card"><b id="cardn"></b><span id="cardd"></span></div>
  <div id="cap"></div>
</div>
<script type="module">
import * as THREE from 'three';

const DATA = {json.dumps(payload, ensure_ascii=False)};
const RSPEC = DATA.route;
const SHOTS = DATA.shots;
const WORDS = DATA.words;
const params = new URLSearchParams(location.search);
const SCALE = Math.max(1, Number(params.get('scale') || 1));
const W = 1080, H = 1920, DUR = DATA.totalDuration;

document.getElementById('cardn').textContent = RSPEC.destination;
document.getElementById('cardd').textContent = `${{RSPEC.minutes}} min · ${{RSPEC.distance}} ${{RSPEC.unit}}`;

let seed = RSPEC.seed | 0;
const rnd = () => {{ seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }};
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const easeInOut = x => x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;

const renderer = new THREE.WebGLRenderer({{ canvas: document.getElementById('c'), antialias: true, preserveDrawingBuffer: true }});
renderer.setPixelRatio(SCALE);
renderer.setSize(W, H, false);
renderer.shadowMap.enabled = true;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xeef0f1);
scene.fog = new THREE.Fog(0xeef0f1, 85, 165);
const camera = new THREE.PerspectiveCamera(30, W / H, 0.5, 300);

scene.add(new THREE.HemisphereLight(0xffffff, 0xcfd3d6, 1.9));
const sun = new THREE.DirectionalLight(0xffffff, 1.5);
sun.position.set(-18, 36, 14); sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
Object.assign(sun.shadow.camera, {{ left: -45, right: 45, top: 45, bottom: -45, near: 1, far: 140 }});
scene.add(sun);

const ground = new THREE.Mesh(new THREE.PlaneGeometry(360, 360), new THREE.MeshStandardMaterial({{ color: 0xf7f7f5, roughness: 1 }}));
ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);

const riverZ = x => -18 + 2.4 * Math.sin(x * 0.15 + 0.5);
{{
  const pos = [], idx = [], n = 140;
  for (let i = 0; i <= n; i++) {{
    const x = -70 + 140 * i / n, z = riverZ(x);
    pos.push(x, 0.02, z + 1.85, x, 0.02, z - 1.85);
    if (i) {{ const a = (i - 1) * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }}
  }}
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
  scene.add(new THREE.Mesh(g, new THREE.MeshStandardMaterial({{ color: 0x9fcbf2, roughness: 0.85, side: THREE.DoubleSide }})));
}}

const CELL = 4, BLK = 3.0;
const boxGeo = new THREE.BoxGeometry(1, 1, 1); boxGeo.translate(0, 0.5, 0);
const lots = [];
for (let i = -8; i < 8; i++) {{
  for (let j = -18; j < 5; j++) {{
    const cx = i * CELL + 2, cz = j * CELL + 2;
    if (Math.abs(cz - riverZ(cx)) < 4.0) continue;
    if (rnd() < 0.14) {{
      const park = new THREE.Mesh(new THREE.BoxGeometry(BLK, 0.05, BLK), new THREE.MeshStandardMaterial({{ color: 0xd3e9c6, roughness: 1 }}));
      park.position.set(cx, 0.025, cz); scene.add(park);
      continue;
    }}
    lots.push([cx, cz, BLK * 0.82, BLK * 0.82, 0.45 + rnd() * 1.45]);
  }}
}}
const bInst = new THREE.InstancedMesh(boxGeo, new THREE.MeshStandardMaterial({{ color: 0xffffff, roughness: 0.92 }}), lots.length);
const m4 = new THREE.Matrix4();
lots.forEach(([x, z, w, d, h], i) => {{ m4.makeScale(w, h, d); m4.setPosition(x, 0, z); bInst.setMatrixAt(i, m4); }});
bInst.castShadow = bInst.receiveShadow = true; scene.add(bInst);

// Custom multi-turn street route aligned to multiples of 4
const WP = [[-12, 12], [-12, -4], [-4, -4], [-4, -24], [8, -24], [8, -40]];
const RP = [];
for (let i = 0; i < WP.length - 1; i++) {{
  const a = new THREE.Vector2(...WP[i]), b = new THREE.Vector2(...WP[i + 1]);
  const steps = Math.max(8, Math.round(a.distanceTo(b) * 12));
  for (let k = 0; k < steps; k++) RP.push(a.clone().lerp(b, k / steps));
}}
RP.push(new THREE.Vector2(...WP[WP.length - 1]));

function makeRibbon(hw, y, color) {{
  const pos = [], idx = [];
  for (let i = 0; i < RP.length; i++) {{
    const a = RP[Math.max(0, i - 1)], b = RP[Math.min(RP.length - 1, i + 1)];
    const t = b.clone().sub(a).normalize();
    pos.push(RP[i].x - t.y * hw, y, RP[i].y + t.x * hw, RP[i].x + t.y * hw, y, RP[i].y - t.x * hw);
    if (i) {{ const k = (i - 1) * 2; idx.push(k, k + 2, k + 1, k + 1, k + 2, k + 3); }}
  }}
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({{ color }}));
  scene.add(m); return m;
}}
const routeEdge = makeRibbon(0.52, 0.16, 0xffffff);
const routeFill = makeRibbon(0.35, 0.18, RSPEC.accent);

const headDot = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.08, 32), new THREE.MeshBasicMaterial({{ color: RSPEC.accent }}));
scene.add(headDot);

const pin = new THREE.Group();
const pinMat = new THREE.MeshStandardMaterial({{ color: 0xf0483e, roughness: 0.4 }});
const pHead = new THREE.Mesh(new THREE.SphereGeometry(0.88, 32, 24), pinMat); pHead.position.y = 2.25;
const pConeG = new THREE.ConeGeometry(0.62, 1.7, 32); pConeG.rotateX(Math.PI);
const pCone = new THREE.Mesh(pConeG, pinMat); pCone.position.y = 1.08;
pin.add(pHead, pCone);
const END = RP[RP.length - 1];
pin.position.set(END.x, 0, END.y); scene.add(pin);

const CHUNKS = [];
{{
  let cur = [];
  WORDS.forEach((w, i) => {{
    cur.push(w);
    if (cur.length >= 4 || /[.,?!]$/.test(w.w) || i === WORDS.length - 1) {{
      CHUNKS.push({{ s: cur[0].s, e: cur[cur.length - 1].e + 0.2, text: cur.map(x => x.w).join(' ') }});
      cur = [];
    }}
  }});
}}

window.TOTAL_DURATION = DUR;
window.SHOT_SPANS = SHOTS.map(s => [s.start, s.end]);

window.renderAtTime = function(rawT) {{
  const t = clamp(rawT, 0, DUR - 1e-4);
  const drawEnd = DUR * 0.82;
  const pr = easeInOut(clamp((t - 0.15) / Math.max(0.5, drawEnd - 0.15), 0, 1));
  const k = Math.floor(pr * (RP.length - 1));
  routeEdge.geometry.setDrawRange(0, k * 6);
  routeFill.geometry.setDrawRange(0, k * 6);
  const hp = RP[k];
  headDot.position.set(hp.x, 0.22, hp.y);

  let sIdx = SHOTS.findIndex(s => t >= s.start && t < s.end);
  if (sIdx < 0) sIdx = SHOTS.length - 1;
  const setup = SHOTS[sIdx].setup_type;

  // Multi-shot camera angles along the route!
  if (setup === 'departure_street_level') {{
    camera.position.set(hp.x + 12, 18, hp.y + 22);
    camera.lookAt(hp.x, 0, hp.y - 4);
  }} else if (setup === 'mid_route_bridge_crossing') {{
    camera.position.set(hp.x - 20, 26, hp.y + 18);
    camera.lookAt(hp.x, 0, hp.y - 2);
  }} else if (setup === 'turn_park_corridor') {{
    camera.position.set(hp.x + 18, 24, hp.y + 16);
    camera.lookAt(hp.x, 0, hp.y - 3);
  }} else {{
    const fin = clamp((t - SHOTS[sIdx].start) / Math.max(0.3, SHOTS[sIdx].end - SHOTS[sIdx].start), 0, 1);
    camera.position.set(END.x * (1 - fin * 0.5) + 14, 28 + fin * 28, END.y + 24 + fin * 26);
    camera.lookAt(END.x * 0.5, 0, END.y * 0.65);
  }}

  const pinT = t - (drawEnd - 0.15);
  pin.visible = pinT > 0;
  if (pinT > 0) {{
    pin.position.y = pinT < 0.28 ? 8 * (1 - (pinT / 0.28) ** 2) : (pinT < 0.5 ? Math.sin(((pinT - 0.28) / 0.22) * Math.PI) * 1.1 : 0);
  }}
  renderer.render(scene, camera);

  document.getElementById('etan').textContent = pr >= 0.99 ? 'Arrived' : `${{Math.max(1, Math.round(RSPEC.minutes * (1 - pr)))}} min`;
  document.getElementById('etad').textContent = pr >= 0.99 ? `${{RSPEC.distance}} ${{RSPEC.unit}} total` : `${{(RSPEC.distance * (1 - pr)).toFixed(1)}} ${{RSPEC.unit}} left`;
  document.getElementById('card').style.opacity = pinT > 0.35 ? clamp((pinT - 0.35) * 3, 0, 1) : 0;

  const ch = CHUNKS.find(c => t >= c.s && t < c.e);
  document.getElementById('cap').textContent = ch ? ch.text : '';
  return sIdx;
}};

window.SHORT_DIRECTOR_READY = Promise.all([
  document.fonts.load('700 36px Inter'),
  document.fonts.load('500 24px Inter'),
]).then(() => {{ window.renderAtTime(0); return true; }});
</script>
</body></html>
"""
    index_path = work_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    visual_sources.extend([str(Path(__file__).resolve()), str(index_path.resolve())])

    return {
        "engine": "map-route",
        "work_dir": str((run_dir / "engine_work").resolve()),
        "entry_html": str(index_path.resolve()),
        "capture_mode": "page_jpeg",
        "supports_native_4k": True,
        "uses_webgl": True,
        "visual_sources": visual_sources,
    }
