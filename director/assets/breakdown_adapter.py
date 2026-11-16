"""Single-Engine Adapter for `breakdown` (3D Studio Exploded View + Leader Callouts).

Strictly locks to `/breakdown` visual language:
- Dark studio radial vignette backdrop, Three.js PBR `RoomEnvironment` materials,
  6 exploding axial layers, JetBrains Mono + Inter right-column callouts, animated SVG elbow leaders,
  plus multi-angle camera blocking (silhouette -> explosion -> novel internal core macro -> full annotated stack).
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List


def _extract_breakdown_labels(raw_script: str) -> Dict[str, Any]:
    # Parse colon-delimited list if user provided component names: e.g. "Anatomy: a, b, c, d, e, f"
    title = "Assembly"
    m_colon = re.match(r"^([^:]{2,32}):\s*(.+)$", raw_script.strip())
    if m_colon:
        title = m_colon.group(1).strip()[:22]
        items = [x.strip(" .") for x in re.split(r"[,;]", m_colon.group(2)) if x.strip()]
    else:
        words = re.findall(r"[A-Za-z]+", raw_script)
        title = " ".join(words[:2]).title() if words else "Device"
        items = []

    default_layers = [
        ["Top Cap", "anodized shell"],
        ["Upper Matrix", "precision interface"],
        ["Structural Ring", "machined alloy"],
        ["Core Logic", "active driver unit"],
        ["Energy Cell", "regulated module"],
        ["Base Housing", "damped mount"],
    ]
    labels: List[List[str]] = []
    for idx in range(6):
        if idx < len(items):
            nm = items[idx][:18].title()
            labels.append([nm, f"layer 0{idx + 1} · precision"])
        else:
            labels.append(default_layers[idx])

    cylindrical = any(k in raw_script.lower() for k in ("espresso", "portafilter", "lens", "camera", "switch", "motor", "cup", "battery"))
    return {
        "title": title,
        "subtitle": "Exploded View",
        "labels": labels,
        "shape_mode": "cylindrical_core" if cylindrical else "rounded_slab",
        "accent": "#F08A5D",
    }


def generate_engine_project(
    project_root: Path,
    run_dir: Path,
    storyboard: Dict[str, Any],
    parsed_script: Dict[str, Any],
) -> Dict[str, Any]:
    upstream_bd = project_root / "vendor" / "claude-animation-skills" / "skills" / "breakdown"
    kit_dir = project_root / "vendor" / "claude-animation-skills" / "kit"
    work_dir = run_dir / "engine_work" / "web"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    upstream_tpl = (upstream_bd / "template.html").resolve()
    _ = upstream_tpl.read_text(encoding="utf-8")

    (work_dir / "fonts").mkdir(parents=True, exist_ok=True)
    visual_sources: List[str] = [str(upstream_tpl)]
    for wf in (kit_dir / "fonts").glob("*.woff2"):
        shutil.copy2(wf.resolve(), work_dir / "fonts" / wf.name)
        visual_sources.append(str(wf.resolve()))

    os.symlink(str((kit_dir / "node_modules").resolve()), str(work_dir / "node_modules"))

    bd_spec = _extract_breakdown_labels(parsed_script["raw_input_script"])
    payload = {
        "spec": bd_spec,
        "shots": storyboard["shots"],
        "words": parsed_script["voice"]["words"],
        "totalDuration": storyboard["total_duration_sec"],
    }

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
@font-face{{font-family:'Inter';font-weight:600;src:url(fonts/inter-600-normal.woff2) format('woff2')}}
@font-face{{font-family:'JB';font-weight:500;src:url(fonts/jetbrains-mono-latin-500-normal.woff2) format('woff2')}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1080px;height:1920px;overflow:hidden;background:#0b0c0e}}
#root{{position:relative;width:1080px;height:1920px;overflow:hidden;font-family:'Inter',sans-serif;
  background:radial-gradient(ellipse 80% 55% at 42% 48%,#2a2d33 0%,#16181b 55%,#0a0b0d 100%)}}
#c{{position:absolute;left:0;top:0;width:1080px;height:1920px;display:block}}
#hd{{position:absolute;left:110px;top:250px;font:500 26px 'JB';letter-spacing:.15em;color:#8b9098}}
#hd b{{color:#f3f1ed;font-weight:500}}
svg{{position:absolute;left:0;top:0}}
.lb{{position:absolute;left:0;top:0;width:260px;opacity:0}}
.lb .n{{font:500 23px 'JB';color:#F08A5D;letter-spacing:.06em}}
.lb .t{{margin-top:5px;font:600 29px/1.08 'Inter';color:#f3f1ed}}
.lb .s{{margin-top:6px;font:500 19px 'JB';color:#8b9098}}
#cap{{position:absolute;left:110px;width:860px;top:1455px;text-align:center;font:500 32px/1.25 'JB';color:#e9e6e1}}
</style>
<script type="importmap">{{"imports":{{"three":"./node_modules/three/build/three.module.js","three/addons/":"./node_modules/three/examples/jsm/"}}}}</script>
</head>
<body>
<div id="root">
  <canvas id="c"></canvas>
  <div id="hd"><b id="hdt"></b> / <span id="hds"></span></div>
  <svg width="1080" height="1920" viewBox="0 0 1080 1920" id="leads"></svg>
  <div id="labels"></div>
  <div id="cap"></div>
</div>
<script type="module">
import * as THREE from 'three';
import {{ RoomEnvironment }} from 'three/addons/environments/RoomEnvironment.js';

const DATA = {json.dumps(payload, ensure_ascii=False)};
const SPEC = DATA.spec;
const SHOTS = DATA.shots;
const WORDS = DATA.words;
const params = new URLSearchParams(location.search);
const SCALE = Math.max(1, Number(params.get('scale') || 1));
const W = 1080, H = 1920, DUR = DATA.totalDuration;

document.getElementById('hdt').textContent = SPEC.title.toUpperCase();
document.getElementById('hds').textContent = SPEC.subtitle.toUpperCase();

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const easeInOut = x => x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;

const renderer = new THREE.WebGLRenderer({{ canvas: document.getElementById('c'), antialias: true, alpha: true, preserveDrawingBuffer: true }});
renderer.setPixelRatio(SCALE);
renderer.setSize(W, H, false);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.06;

const scene = new THREE.Scene();
const pm = new THREE.PMREMGenerator(renderer);
scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.8;
const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(-6, 12, 8); scene.add(key);
const rim = new THREE.DirectionalLight(0xffd9c2, 1.3); rim.position.set(8, 4, -6); scene.add(rim);

const camera = new THREE.PerspectiveCamera(26, W / H, 0.5, 200);
const assembly = new THREE.Group();
scene.add(assembly);

const Y_ASSEM = [-0.6, -0.35, -0.1, 0.15, 0.4, 0.65];
const Y_EXPLO = [-2.8, -1.65, -0.55, 0.65, 1.85, 3.05];
const colors = [0x3b4250, 0xb87f4e, 0x264653, 0xa9adb3, 0xe76f51, 0xd8e2ec];
const parts = [];

for (let i = 0; i < 6; i++) {{
  const g = new THREE.Group();
  const isGlass = i === 5;
  const mat = new THREE.MeshPhysicalMaterial({{
    color: colors[i],
    metalness: isGlass ? 0.05 : 0.72,
    roughness: isGlass ? 0.08 : 0.28,
    transparent: isGlass,
    opacity: isGlass ? 0.42 : 1.0,
    clearcoat: isGlass ? 1.0 : 0.35,
  }});
  let mesh;
  if (SPEC.shape_mode === 'cylindrical_core') {{
    const rad = 1.75 - Math.abs(i - 2.5) * 0.14;
    const geo = (i === 2 || i === 4)
      ? new THREE.TorusGeometry(rad * 0.82, 0.22, 20, 64)
      : new THREE.CylinderGeometry(rad, rad * 0.94, 0.32, 64);
    if (i === 2 || i === 4) geo.rotateX(Math.PI / 2);
    mesh = new THREE.Mesh(geo, mat);
  }} else {{
    mesh = new THREE.Mesh(new THREE.BoxGeometry(3.4 - (i === 3 ? 0.5 : 0), 0.26, 6.2 - (i === 3 ? 0.8 : 0)), mat);
  }}
  g.add(mesh);
  // Internal coil/detail on core layer 3
  if (i === 3) {{
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.95, 0.09, 16, 48), new THREE.MeshStandardMaterial({{ color: 0xf08a5d, metalness: 0.9, roughness: 0.2 }}));
    ring.rotation.x = Math.PI / 2; ring.position.y = 0.18;
    g.add(ring);
  }}
  assembly.add(g);
  parts.push(g);
}}

// Build 6 right-column callout DOM labels + SVG leaders (top layer index 5 first -> bottom index 0)
const leads = document.getElementById('leads'), labRoot = document.getElementById('labels');
const NS = 'http://www.w3.org/2000/svg';
const lineEls = [], dotEls = [], labEls = [];
const LX = 685;
const LY = [460, 625, 790, 955, 1120, 1285];

SPEC.labels.forEach(([nm, sub], k) => {{
  const ln = document.createElementNS(NS, 'polyline');
  ln.setAttribute('fill', 'none'); ln.setAttribute('stroke', '#c9ccd1'); ln.setAttribute('stroke-width', '2'); ln.setAttribute('opacity', '0');
  const dt = document.createElementNS(NS, 'circle');
  dt.setAttribute('r', '6'); dt.setAttribute('fill', SPEC.accent); dt.setAttribute('opacity', '0');
  leads.appendChild(ln); leads.appendChild(dt);
  lineEls.push(ln); dotEls.push(dt);

  const d = document.createElement('div');
  d.className = 'lb';
  d.innerHTML = `<div class="n">0${{k + 1}}</div><div class="t">${{nm}}</div><div class="s">${{sub}}</div>`;
  d.style.transform = `translate(${{LX + 20}}px,${{LY[k] - 32}}px)`;
  labRoot.appendChild(d);
  labEls.push(d);
}});

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

const tmpV = new THREE.Vector3();
function projectPart(partObj) {{
  tmpV.set(1.35, 0, 0);
  partObj.localToWorld(tmpV);
  tmpV.project(camera);
  return [(tmpV.x + 1) * 0.5 * W, (1 - tmpV.y) * 0.5 * H];
}}

window.TOTAL_DURATION = DUR;
window.SHOT_SPANS = SHOTS.map(s => [s.start, s.end]);

window.renderAtTime = function(rawT) {{
  const t = clamp(rawT, 0, DUR - 1e-4);
  let sIdx = SHOTS.findIndex(s => t >= s.start && t < s.end);
  if (sIdx < 0) sIdx = SHOTS.length - 1;
  const curS = SHOTS[sIdx];
  const prevS = sIdx > 0 ? SHOTS[sIdx - 1] : null;
  const setup = curS.setup_type;
  const uShot = clamp((t - curS.start) / Math.max(0.25, curS.end - curS.start), 0, 1);
  const ex = easeInOut(clamp((t - DUR * 0.14) / (DUR * 0.42), 0, 1));

  // Rendered `match_zoom` seam FOV ramp
  let fovZoom = 0;
  if (curS.transition_out === 'match_zoom' && sIdx < SHOTS.length - 1 && (curS.end - t) < 0.14) {{
    fovZoom = -3.8 * Math.pow(1 - (curS.end - t) / 0.14, 2);
  }} else if (prevS && prevS.transition_out === 'match_zoom' && (t - curS.start) < 0.14) {{
    fovZoom = 3.2 * (1 - (t - curS.start) / 0.14);
  }}
  camera.fov = 26 + fovZoom;
  camera.updateProjectionMatrix();

  parts.forEach((p, i) => {{
    p.position.y = Y_ASSEM[i] + (Y_EXPLO[i] - Y_ASSEM[i]) * ex;
  }});
  assembly.rotation.y = THREE.MathUtils.degToRad(-32 + t * 11);
  assembly.rotation.x = THREE.MathUtils.degToRad(3 * Math.sin(t * 1.2));

  let showCallouts = 0;
  if (setup === 'novel_internal_core_macro') {{
    camera.clearViewOffset();
    camera.position.set(4.5, 1.2, 13.5);
    camera.lookAt(0, 0.65, 0);
    showCallouts = 0;
  }} else if (setup === 'top_down_subsystem_orbit') {{
    camera.clearViewOffset();
    const ang = -0.35 + uShot * 0.85;
    camera.position.set(Math.sin(ang) * 14.5, 18.0 - uShot * 3.0, Math.cos(ang) * 14.5);
    camera.lookAt(0, 1.25, 0);
    showCallouts = 0;
  }} else if (setup === 'assembled_hero_silhouette') {{
    camera.clearViewOffset();
    camera.position.set(6.0, 6.5, 22.0);
    camera.lookAt(0, 0, 0);
    showCallouts = 0;
  }} else {{
    camera.setViewOffset(W, H, 145, 0, W, H);
    camera.position.set(6.5, 10.5, 31.0);
    camera.lookAt(0, 0.15, 0);
    showCallouts = setup === 'full_annotated_callout_stack' ? 1 : clamp((ex - 0.55) * 2.2, 0, 1);
  }}

  camera.updateMatrixWorld();
  assembly.updateMatrixWorld(true);
  renderer.render(scene, camera);

  for (let k = 0; k < 6; k++) {{
    const pIdx = 5 - k;
    const [ax, ay] = projectPart(parts[pIdx]);
    const mx = Math.max(ax + 35, LX - 85), ey = LY[k];
    lineEls[k].setAttribute('points', `${{ax.toFixed(1)}},${{ay.toFixed(1)}} ${{mx.toFixed(1)}},${{ey}} ${{LX}},${{ey}}`);
    lineEls[k].setAttribute('opacity', (showCallouts * 0.85).toFixed(2));
    dotEls[k].setAttribute('cx', ax.toFixed(1)); dotEls[k].setAttribute('cy', ay.toFixed(1));
    dotEls[k].setAttribute('opacity', showCallouts.toFixed(2));
    labEls[k].style.opacity = showCallouts.toFixed(2);
  }}

  const ch = CHUNKS.find(c => t >= c.s && t < c.e);
  document.getElementById('cap').textContent = ch ? ch.text.toUpperCase() : '';
  return sIdx;
}};

window.SHORT_DIRECTOR_READY = Promise.all([
  document.fonts.load('600 30px Inter'),
  document.fonts.load('500 24px JB'),
]).then(() => {{ window.renderAtTime(0); return true; }});
</script>
</body></html>
"""
    index_path = work_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    visual_sources.extend([str(Path(__file__).resolve()), str(index_path.resolve())])

    return {
        "engine": "breakdown",
        "work_dir": str((run_dir / "engine_work").resolve()),
        "entry_html": str(index_path.resolve()),
        "capture_mode": "page_jpeg",
        "supports_native_4k": True,
        "uses_webgl": True,
        "visual_sources": visual_sources,
    }
