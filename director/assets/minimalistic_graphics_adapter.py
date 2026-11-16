"""Single-Engine Adapter for `minimalistic-graphics` (B&W Hairline Line-Art + Solitary Dot).

Strictly locks to `/minimalistic-graphics` aesthetic:
- Pure black background (`#000`), hairline white strokes (`2.6px`), one solid white dot (`r=31`),
  quiet lowercase Poppins text, squash-and-stretch hops, plus a novel geometric pendulum/arc motif.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List


def generate_engine_project(
    project_root: Path,
    run_dir: Path,
    storyboard: Dict[str, Any],
    parsed_script: Dict[str, Any],
) -> Dict[str, Any]:
    upstream_mg = project_root / "vendor" / "claude-animation-skills" / "skills" / "minimalistic-graphics"
    kit_dir = project_root / "vendor" / "claude-animation-skills" / "kit"
    work_dir = run_dir / "engine_work" / "web"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    upstream_tpl = (upstream_mg / "template.html").resolve()
    _ = upstream_tpl.read_text(encoding="utf-8")

    (work_dir / "fonts").mkdir(parents=True, exist_ok=True)
    visual_sources: List[str] = [str(upstream_tpl)]
    for wf in (kit_dir / "fonts").glob("*.woff2"):
        shutil.copy2(wf.resolve(), work_dir / "fonts" / wf.name)
        visual_sources.append(str(wf.resolve()))
    (work_dir / "vendor").mkdir(parents=True, exist_ok=True)
    shutil.copy2((kit_dir / "vendor" / "gsap.min.js").resolve(), work_dir / "vendor" / "gsap.min.js")

    sentences = [s.lower().strip() for s in parsed_script["sentences"]]
    payload = {
        "sentences": sentences,
        "shots": storyboard["shots"],
        "totalDuration": storyboard["total_duration_sec"],
    }

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
@font-face{{font-family:'Poppins';font-weight:400;src:url(fonts/poppins-latin-400-normal.woff2) format('woff2')}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1080px;height:1920px;overflow:hidden;background:#000}}
#root{{position:relative;width:1080px;height:1920px;overflow:hidden;background:#000}}
#cap{{position:absolute;left:110px;width:860px;top:250px;text-align:center;font:400 42px/1.28 'Poppins';color:#f4f4f4;letter-spacing:-.005em}}
svg{{position:absolute;left:0;top:0}}
</style></head>
<body>
<div id="root">
  <div id="cap"></div>
  <svg width="1080" height="1920" viewBox="0 0 1080 1920">
    <g id="motifPendulum" fill="none" stroke="#f4f4f4" stroke-width="2.6" opacity="0">
      <line x1="540" y1="520" x2="540" y2="560" stroke="#9e9e9e"/>
      <path id="pendArc" stroke="#555" stroke-dasharray="6 10" d="M 260 980 Q 540 1180 820 980"/>
      <line id="pendRod" x1="540" y1="540" x2="540" y2="1040"/>
    </g>
    <g id="motifBalance" fill="none" stroke="#f4f4f4" stroke-width="2.6" opacity="0">
      <polygon points="540,1040 508,1115 572,1115" stroke="#9e9e9e"/>
      <line id="balBeam" x1="250" y1="1035" x2="830" y2="1035"/>
      <circle id="balCounter" cx="290" cy="1005" r="18" fill="none" stroke="#9e9e9e"/>
    </g>
    <g id="bars" fill="none" stroke="#f4f4f4" stroke-width="2.6"></g>
    <circle id="orbit" r="145" fill="none" stroke="#f4f4f4" stroke-width="2.2" stroke-dasharray="6 10" opacity="0"/>
    <ellipse id="ring" rx="225" ry="48" fill="none" stroke="#9e9e9e" stroke-width="2" opacity="0"/>
    <g id="sparks" fill="#f4f4f4"></g>
    <circle id="pulse" cx="540" cy="960" r="34" fill="none" stroke="#f4f4f4" stroke-width="2.6" opacity="0"/>
    <ellipse id="ball" cx="540" cy="960" rx="31" ry="31" fill="#f4f4f4"/>
  </svg>
</div>
<script>
const DATA = {json.dumps(payload, ensure_ascii=False)};
const SHOTS = DATA.shots;
const NS = 'http://www.w3.org/2000/svg';
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const easeOut = t => 1 - Math.pow(1 - clamp(t, 0, 1), 3);

// 5 rising hairline steps
const N = 5, LX = 150, RX = 860, BW = 110;
const pitch = (RX - LX - BW) / (N - 1);
const BX = [...Array(N)].map((_, k) => LX + BW / 2 + k * pitch);
const TOP = [...Array(N)].map((_, k) => 1260 - k * 170);
const barsG = document.getElementById('bars');
const barEls = BX.map((x, k) => {{
  const r = document.createElementNS(NS, 'rect');
  r.setAttribute('x', (x - BW / 2).toFixed(1));
  r.setAttribute('y', '1960');
  r.setAttribute('width', BW);
  r.setAttribute('height', '1600');
  barsG.appendChild(r);
  return r;
}});

const spG = document.getElementById('sparks');
const sparkEls = [...Array(20)].map((_, i) => {{
  const c = document.createElementNS(NS, 'circle');
  c.setAttribute('r', i % 3 === 0 ? '6' : '4');
  c.setAttribute('opacity', '0');
  spG.appendChild(c);
  return c;
}});

window.TOTAL_DURATION = DATA.totalDuration;
window.SHOT_SPANS = SHOTS.map(s => [s.start, s.end]);

window.renderAtTime = function(rawT) {{
  const t = clamp(rawT, 0, DATA.totalDuration - 1e-4);
  let sIdx = SHOTS.findIndex(s => t >= s.start && t < s.end);
  if (sIdx < 0) sIdx = SHOTS.length - 1;
  const shot = SHOTS[sIdx];
  const u = clamp((t - shot.start) / Math.max(0.1, shot.end - shot.start), 0, 1);

  const lineIdx = Math.min(DATA.sentences.length - 1, Math.floor((sIdx / Math.max(1, SHOTS.length)) * DATA.sentences.length));
  document.getElementById('cap').textContent = DATA.sentences[lineIdx] || '';

  const ball = document.getElementById('ball');
  const pulse = document.getElementById('pulse');
  const pendG = document.getElementById('motifPendulum');
  const balG = document.getElementById('motifBalance');
  const orbit = document.getElementById('orbit');
  const ring = document.getElementById('ring');

  // Reset defaults
  pendG.setAttribute('opacity', '0');
  balG.setAttribute('opacity', '0');
  barsG.setAttribute('opacity', '0');
  orbit.setAttribute('opacity', '0');
  ring.setAttribute('opacity', '0');
  pulse.setAttribute('opacity', '0');
  sparkEls.forEach(c => c.setAttribute('opacity', '0'));

  // Rendered `match_zoom` viewport transform across shot seam
  const prevShot = sIdx > 0 ? SHOTS[sIdx - 1] : null;
  let zVp = 1.0;
  if (shot.transition_out === 'match_zoom' && sIdx < SHOTS.length - 1 && (shot.end - t) < 0.14) {{
    zVp = 1.0 + Math.pow(1.0 - (shot.end - t) / 0.14, 2) * 0.12;
  }} else if (prevShot && prevShot.transition_out === 'match_zoom' && (t - shot.start) < 0.14) {{
    zVp = 1.12 - easeOut((t - shot.start) / 0.14) * 0.12;
  }}
  document.querySelector('svg').style.transform = `scale(${{zVp.toFixed(4)}})`;
  document.querySelector('svg').style.transformOrigin = '540px 960px';

  if (shot.setup_type === 'hook_solitary_dot_pulse') {{
    const sc = u < 0.25 ? easeOut(u / 0.25) * 1.15 : lerp(1.15, 1.0, clamp((u - 0.25) / 0.3, 0, 1));
    ball.setAttribute('cx', 540); ball.setAttribute('cy', 980);
    ball.setAttribute('rx', 31 * sc); ball.setAttribute('ry', 31 * sc);
    pulse.setAttribute('cx', 540); pulse.setAttribute('cy', 980);
    pulse.setAttribute('r', 34 + u * 150);
    pulse.setAttribute('opacity', ((1 - u) * 0.75).toFixed(2));
  }} else if (shot.setup_type === 'novel_pendulum_or_labyrinth') {{
    // Novel B&W geometric pendulum building momentum arc
    pendG.setAttribute('opacity', '1');
    const amp = lerp(0.22, 0.58, u);
    const ang = Math.sin(u * Math.PI * 3.5) * amp;
    const L = 500;
    const bx = 540 + Math.sin(ang) * L, by = 540 + Math.cos(ang) * L;
    document.getElementById('pendRod').setAttribute('x2', bx.toFixed(1));
    document.getElementById('pendRod').setAttribute('y2', by.toFixed(1));
    ball.setAttribute('cx', bx.toFixed(1)); ball.setAttribute('cy', by.toFixed(1));
    ball.setAttribute('rx', '31'); ball.setAttribute('ry', '31');
  }} else if (shot.setup_type === 'kinetic_balance_beam') {{
    // Novel kinetic equilibrium beam & rolling ball transformation
    balG.setAttribute('opacity', '1');
    const tilt = Math.sin(u * Math.PI) * -0.18 + (u > 0.55 ? 0.14 : -0.10);
    const dx = 285, dy = Math.sin(tilt) * dx;
    const beam = document.getElementById('balBeam');
    beam.setAttribute('x1', (540 - dx).toFixed(1)); beam.setAttribute('y1', (1035 - dy).toFixed(1));
    beam.setAttribute('x2', (540 + dx).toFixed(1)); beam.setAttribute('y2', (1035 + dy).toFixed(1));
    const bx = lerp(410, 745, easeOut(u));
    const by = 1035 + ((bx - 540) / dx) * dy - 31;
    ball.setAttribute('cx', bx.toFixed(1)); ball.setAttribute('cy', by.toFixed(1));
    ball.setAttribute('rx', '31'); ball.setAttribute('ry', '31');
    const bc = document.getElementById('balCounter');
    bc.setAttribute('cx', (540 - 250).toFixed(1)); bc.setAttribute('cy', (1035 - dy - 20).toFixed(1));
  }} else if (shot.setup_type === 'rising_hairline_steps') {{
    barsG.setAttribute('opacity', '1');
    const stepFloat = u * (N - 1);
    const k = Math.min(N - 2, Math.floor(stepFloat));
    const frac = stepFloat - k;
    barEls.forEach((r, idx) => {{
      const rev = clamp((u * N - idx * 0.65), 0, 1);
      r.setAttribute('y', lerp(1960, TOP[idx], easeOut(rev)).toFixed(1));
    }});
    const bx = lerp(BX[k], BX[k + 1], frac);
    const by = lerp(TOP[k] - 31, TOP[k + 1] - 31, frac) - Math.sin(frac * Math.PI) * 115;
    const stretch = Math.sin(frac * Math.PI);
    ball.setAttribute('cx', bx.toFixed(1)); ball.setAttribute('cy', by.toFixed(1));
    ball.setAttribute('rx', (31 * (1 - stretch * 0.12)).toFixed(1));
    ball.setAttribute('ry', (31 * (1 + stretch * 0.16)).toFixed(1));
  }} else {{
    // Payoff apex orbit + radial spark burst
    barsG.setAttribute('opacity', '0.32');
    barEls.forEach((r, idx) => r.setAttribute('y', TOP[idx]));
    const ox = BX[N - 1], oy = TOP[N - 1] - 31;
    ball.setAttribute('cx', ox); ball.setAttribute('cy', oy);
    ball.setAttribute('rx', '31'); ball.setAttribute('ry', '31');
    orbit.setAttribute('cx', ox); orbit.setAttribute('cy', oy);
    orbit.setAttribute('opacity', easeOut(u * 2).toFixed(2));
    orbit.setAttribute('transform', `rotate(${{(u * 55).toFixed(1)}} ${{ox}} ${{oy}})`);
    ring.setAttribute('cx', ox); ring.setAttribute('cy', oy);
    ring.setAttribute('opacity', easeOut(Math.max(0, u * 2 - 0.2)).toFixed(2));
    sparkEls.forEach((c, i) => {{
      const a = (i / sparkEls.length) * Math.PI * 2;
      const dist = easeOut(u) * (185 + (i % 4) * 32);
      c.setAttribute('cx', (ox + Math.cos(a) * dist).toFixed(1));
      c.setAttribute('cy', (oy + Math.sin(a) * dist).toFixed(1));
      c.setAttribute('opacity', (Math.sin(clamp(u * 1.2, 0, 1) * Math.PI * 0.85) * 0.85).toFixed(2));
    }});
  }}
  return sIdx;
}};

window.SHORT_DIRECTOR_READY = document.fonts.load('400 42px Poppins').then(() => {{ window.renderAtTime(0); return true; }});
</script>
</body></html>
"""
    index_path = work_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    visual_sources.extend([str(Path(__file__).resolve()), str(index_path.resolve())])

    return {
        "engine": "minimalistic-graphics",
        "work_dir": str((run_dir / "engine_work").resolve()),
        "entry_html": str(index_path.resolve()),
        "capture_mode": "page_jpeg",
        "supports_native_4k": True,
        "uses_webgl": False,
        "visual_sources": visual_sources,
    }
