"""Single-Engine Adapter for `graph` (Editorial Line Graph + Tabular Counter + Slope Delta).

Strictly enforces:
- Pure `/graph` visual language (Inter + Inter Tight, hairline grid, Catmull-Rom spline, tabular counter).
- Principle 8: NEVER invents numbers; uses user-supplied series verbatim, and displays an explicit
  `ILLUSTRATIVE TRAJECTORY` label if only 2 endpoints were given.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List


def _extract_graph_series(parsed_script: Dict[str, Any]) -> Dict[str, Any]:
    raw = parsed_script["raw_input_script"]
    nums = list(parsed_script["entities_and_facts"]["user_numbers"])
    if len(nums) < 2:
        raise ValueError("Graph adapter requires >= 2 explicit numbers from user script.")

    illustrative = False
    if len(nums) == 2:
        illustrative = True
        v0, v1 = nums[0], nums[1]
        # Smooth illustrative ease-in curve between real user endpoints, explicitly disclosed on screen!
        nums = [round(v0 + (v1 - v0) * ((k / 6.0) ** 2.1), 2) for k in range(7)]

    # Extract optional time labels (months/quarters) from raw script
    found_labels = re.findall(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Q[1-4]|20\d\d)\b", raw, flags=re.IGNORECASE)
    if len(found_labels) >= 2:
        labels = [x.capitalize() if len(x) == 3 else x.upper() for x in found_labels[: len(nums)]]
        while len(labels) < len(nums):
            labels.append(f"P{len(labels) + 1}")
    else:
        labels = [f"T{i + 1}" for i in range(len(nums))]

    # Extract concise noun metric label
    noun_match = re.search(r"\b(followers|users|stars|revenue|subscribers|downloads|views|orders|mrr|sales)\b", raw, flags=re.IGNORECASE)
    metric_label = noun_match.group(1).capitalize() if noun_match else "Metric trajectory"
    prefix = "$" if "$" in raw else ""
    suffix = "%" if "%" in raw else ""
    return {
        "label": metric_label,
        "values": nums,
        "labels": labels,
        "final": nums[-1],
        "prefix": prefix,
        "suffix": suffix,
        "illustrative": illustrative,
    }


def generate_engine_project(
    project_root: Path,
    run_dir: Path,
    storyboard: Dict[str, Any],
    parsed_script: Dict[str, Any],
) -> Dict[str, Any]:
    upstream_graph = project_root / "vendor" / "claude-animation-skills" / "skills" / "graph"
    kit_dir = project_root / "vendor" / "claude-animation-skills" / "kit"
    work_dir = run_dir / "engine_work" / "web"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Touch ONLY skills/graph/template.html for provenance reference + copy neutral kit fonts & GSAP
    upstream_tpl = (upstream_graph / "template.html").resolve()
    _ = upstream_tpl.read_text(encoding="utf-8")

    (work_dir / "fonts").mkdir(parents=True, exist_ok=True)
    visual_sources: List[str] = [str(upstream_tpl)]
    for wf in (kit_dir / "fonts").glob("*.woff2"):
        shutil.copy2(wf.resolve(), work_dir / "fonts" / wf.name)
        visual_sources.append(str(wf.resolve()))
    (work_dir / "vendor").mkdir(parents=True, exist_ok=True)
    shutil.copy2((kit_dir / "vendor" / "gsap.min.js").resolve(), work_dir / "vendor" / "gsap.min.js")

    series = _extract_graph_series(parsed_script)
    spec_payload = {
        "series": series,
        "shots": storyboard["shots"],
        "words": parsed_script["voice"]["words"],
        "palette": storyboard["style_adapter_params"]["palette"],
        "totalDuration": storyboard["total_duration_sec"],
    }

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
@font-face{{font-family:'Inter';font-weight:500;src:url(fonts/inter-500-normal.woff2) format('woff2')}}
@font-face{{font-family:'Inter';font-weight:600;src:url(fonts/inter-600-normal.woff2) format('woff2')}}
@font-face{{font-family:'Inter Tight';font-weight:700;src:url(fonts/inter-tight-latin-700-normal.woff2) format('woff2')}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1080px;height:1920px;overflow:hidden;background:var(--bg,#fff)}}
#root{{position:relative;width:1080px;height:1920px;overflow:hidden;background:var(--bg,#fff);color:var(--fg,#0a0a0c)}}
#lab{{position:absolute;left:120px;top:300px;font:500 34px 'Inter';color:#7e828a;letter-spacing:.01em}}
#badge{{position:absolute;right:120px;top:306px;font:600 22px 'Inter';color:#6b7280;letter-spacing:.08em;padding:6px 14px;border:1.5px solid #d1d5db;border-radius:99px;display:none}}
#num{{position:absolute;left:114px;top:358px;font:700 172px/1 'Inter Tight';letter-spacing:-.045em;font-variant-numeric:tabular-nums;white-space:nowrap}}
#subcap{{position:absolute;left:120px;width:840px;top:1510px;text-align:center;font:600 40px/1.25 'Inter';color:var(--fg,#0a0a0c)}}
svg{{position:absolute;left:0;top:0}}
</style></head>
<body>
<div id="root">
  <div id="lab"></div>
  <div id="badge">ILLUSTRATIVE TRAJECTORY</div>
  <div id="num">0</div>
  <svg id="stageSvg" width="1080" height="1920" viewBox="0 0 1080 1920">
    <g id="viewportG">
      <line id="g2" x1="120" y1="740" x2="960" y2="740" stroke="#e6e8ec" stroke-width="2"/>
      <line id="g1" x1="120" y1="1040" x2="960" y2="1040" stroke="#e6e8ec" stroke-width="2"/>
      <line id="g0" x1="120" y1="1340" x2="960" y2="1340" stroke="#0a0a0c" stroke-width="2.5"/>
      <g id="deltas"></g>
      <g id="months"></g>
      <line id="tangent" x1="0" y1="0" x2="0" y2="0" stroke="#8a8e96" stroke-width="2.5" stroke-dasharray="6 8" opacity="0"/>
      <line id="drop" x1="0" y1="0" x2="0" y2="0" stroke="#0a0a0c" stroke-width="2" stroke-dasharray="4 8" opacity="0"/>
      <path id="line" fill="none" stroke="#0a0a0c" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
      <circle id="halo" r="14" fill="#0a0a0c" opacity="0"/>
      <circle id="tip" r="13" fill="#0a0a0c" stroke="#ffffff" stroke-width="5"/>
    </g>
  </svg>
  <div id="subcap"></div>
</div>
<script src="vendor/gsap.min.js"></script>
<script>
const DATA = {json.dumps(spec_payload, ensure_ascii=False)};
const S = DATA.series;
const SHOTS = DATA.shots;
const WORDS = DATA.words;
document.getElementById('lab').textContent = S.label;
if (S.illustrative) document.getElementById('badge').style.display = 'block';

const X0 = 120, X1 = 950, Y0 = 1340, Y1 = 740;
const V = S.values.map(Number);
const vmax = Math.max(...V, 1);
const px = i => X0 + i * (X1 - X0) / Math.max(1, V.length - 1);
const py = v => Y0 - (v / vmax) * (Y0 - Y1);
const P = V.map((v, i) => [px(i), py(v)]);

let d = `M${{P[0][0]}},${{P[0][1]}}`;
for (let i = 0; i < P.length - 1; i++) {{
  const p0 = P[Math.max(0, i - 1)], p1 = P[i], p2 = P[i + 1], p3 = P[Math.min(P.length - 1, i + 2)];
  const k = 0.5 / 3;
  const c1 = [p1[0] + (p2[0] - p0[0]) * k, p1[1] + (p2[1] - p0[1]) * k];
  const c2 = [p2[0] - (p3[0] - p1[0]) * k, p2[1] - (p3[1] - p1[1]) * k];
  d += ` C${{c1[0].toFixed(1)}},${{c1[1].toFixed(1)}} ${{c2[0].toFixed(1)}},${{c2[1].toFixed(1)}} ${{p2[0]}},${{p2[1]}}`;
}}
const lineEl = document.getElementById('line');
lineEl.setAttribute('d', d);
const totalLen = lineEl.getTotalLength();
lineEl.setAttribute('stroke-dasharray', totalLen);

const mg = document.getElementById('months');
const dg = document.getElementById('deltas');
S.labels.forEach((m, i) => {{
  if (i >= V.length) return;
  const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  t.setAttribute('x', px(i)); t.setAttribute('y', 1396); t.setAttribute('text-anchor', 'middle');
  t.setAttribute('fill', '#8a8e96'); t.setAttribute('font-family', 'Inter'); t.setAttribute('font-size', '25');
  t.textContent = m; mg.appendChild(t);
  // Novel step-delta impulse stems for inflection shot
  const stem = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  stem.setAttribute('x1', px(i)); stem.setAttribute('x2', px(i));
  stem.setAttribute('y1', Y0); stem.setAttribute('y2', py(V[i]));
  stem.setAttribute('stroke', '#d1d5db'); stem.setAttribute('stroke-width', '3');
  stem.setAttribute('opacity', '0');
  dg.appendChild(stem);
}});

const numEl = document.getElementById('num');
const fmt = x => (S.prefix || '') + Math.round(x).toLocaleString('en-US') + (S.suffix || '');
{{
  const widest = fmt(S.final);
  const sz = Math.min(172, Math.floor(840 / Math.max(1, widest.length * 0.56)));
  numEl.style.fontSize = sz + 'px';
}}

// Word-chunk captions (up to 4 words)
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

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const easeInOut = u => u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;

window.TOTAL_DURATION = DATA.totalDuration;
window.SHOT_SPANS = SHOTS.map(s => [s.start, s.end]);

window.renderAtTime = function(rawT) {{
  const t = clamp(rawT, 0, DATA.totalDuration - 1e-4);
  const drawEnd = DATA.totalDuration * 0.84;
  const p = easeInOut(clamp((t - 0.2) / Math.max(0.5, drawEnd - 0.2), 0, 1));
  const q = p * totalLen;
  lineEl.setAttribute('stroke-dashoffset', totalLen - q);
  const pt = lineEl.getPointAtLength(Math.max(0.05, q));
  const tip = document.getElementById('tip'), halo = document.getElementById('halo');
  tip.setAttribute('cx', pt.x); tip.setAttribute('cy', pt.y);
  halo.setAttribute('cx', pt.x); halo.setAttribute('cy', pt.y);

  const curVal = p >= 0.999 ? S.final : Math.max(V[0] * (1 - p), (Y0 - pt.y) / (Y0 - Y1) * vmax);
  numEl.textContent = fmt(curVal);

  // Multi-shot editorial camera framing on #viewportG!
  let sIdx = SHOTS.findIndex(s => t >= s.start && t < s.end);
  if (sIdx < 0) sIdx = SHOTS.length - 1;
  const shot = SHOTS[sIdx];
  const setup = shot.setup_type;
  const vg = document.getElementById('viewportG');
  const tang = document.getElementById('tangent');
  const stems = dg.querySelectorAll('line');

  if (setup === 'early_baseline_zoom') {{
    const z = 1.32;
    const tx = 540 - pt.x * z, ty = 1080 - pt.y * z;
    vg.setAttribute('transform', `translate(${{tx.toFixed(1)}},${{ty.toFixed(1)}}) scale(${{z}})`);
    tang.setAttribute('opacity', '0');
    stems.forEach(el => el.setAttribute('opacity', '0'));
  }} else if (setup === 'novel_inflection_tangent_delta') {{
    // Novel inflection analysis view: show vertical impulse stems + instantaneous slope tangent!
    const z = 1.16;
    const tx = 540 - pt.x * z, ty = 1040 - pt.y * z;
    vg.setAttribute('transform', `translate(${{tx.toFixed(1)}},${{ty.toFixed(1)}}) scale(${{z}})`);
    const ptA = lineEl.getPointAtLength(Math.max(0.05, q - 35));
    const ptB = lineEl.getPointAtLength(Math.min(totalLen, q + 35));
    const dx = ptB.x - ptA.x, dy = ptB.y - ptA.y;
    const len = Math.hypot(dx, dy) || 1;
    tang.setAttribute('x1', pt.x - dx / len * 130); tang.setAttribute('y1', pt.y - dy / len * 130);
    tang.setAttribute('x2', pt.x + dx / len * 130); tang.setAttribute('y2', pt.y + dy / len * 130);
    tang.setAttribute('opacity', '0.85');
    stems.forEach((el, k) => el.setAttribute('opacity', px(k) <= pt.x ? '0.65' : '0'));
  }} else {{
    vg.setAttribute('transform', 'translate(0,0) scale(1)');
    tang.setAttribute('opacity', '0');
    stems.forEach((el, k) => el.setAttribute('opacity', p >= 0.98 ? '0.28' : '0'));
  }}

  // Payoff landing halo + drop line
  const drop = document.getElementById('drop');
  if (p >= 0.98) {{
    const tailU = clamp((t - drawEnd) / 0.8, 0, 1);
    halo.setAttribute('r', (14 + tailU * 52).toFixed(1));
    halo.setAttribute('opacity', ((1 - tailU) * 0.24).toFixed(2));
    drop.setAttribute('x1', pt.x); drop.setAttribute('x2', pt.x);
    drop.setAttribute('y1', pt.y + 18); drop.setAttribute('y2', pt.y + 18 + (Y0 - pt.y - 18) * tailU);
    drop.setAttribute('opacity', '0.85');
  }} else {{
    halo.setAttribute('opacity', '0');
    drop.setAttribute('opacity', '0');
  }}

  const c = CHUNKS.find(ch => t >= ch.s && t < ch.e);
  document.getElementById('subcap').textContent = c ? c.text : '';
  return sIdx;
}};

window.SHORT_DIRECTOR_READY = Promise.all([
  document.fonts.load('500 34px Inter'),
  document.fonts.load('700 160px "Inter Tight"'),
]).then(() => {{ window.renderAtTime(0); return true; }});
</script>
</body></html>
"""
    index_path = work_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    visual_sources.extend([str(Path(__file__).resolve()), str(index_path.resolve())])

    return {
        "engine": "graph",
        "work_dir": str((run_dir / "engine_work").resolve()),
        "entry_html": str(index_path.resolve()),
        "capture_mode": "page_jpeg",
        "supports_native_4k": True,
        "uses_webgl": False,
        "visual_sources": visual_sources,
    }
