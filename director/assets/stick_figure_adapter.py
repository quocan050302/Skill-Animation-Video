"""Single-Engine Adapter for `stick-figure` (Canvas2D + IK Stick Rig + Procedural World).

Uses ONLY:
- `vendor/claude-animation-skills/skills/stick-figure/engine/template/web/{lib.js,chars.js,env.js,fonts/*}`
- Bespoke generated `novel_world.js`, `shots.js`, and resolution-independent `compositor.js`
  supporting both `1080x1920` preview and true vector `2160x3840` native 4K!
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List


NOVEL_WORLD_JS = r"""// ---------- Short Director v0.2.0: Bespoke Stick-Figure Extensions ----------
// Extends upstream lib.js, chars.js, env.js strictly inside the stick-figure ink-and-cel visual grammar.
const easeInOut = ease;

function arcPt(x0, y0, x1, y1, h, u) {
  const k = clamp(u, 0, 1);
  return [lerp(x0, x1, k), lerp(y0, y1, k) - Math.sin(k * Math.PI) * h];
}

function anticipate(u) {
  const k = clamp(u, 0, 1);
  const c1 = 1.70158, c3 = c1 + 1;
  return c3 * k * k * k - c1 * k * k;
}

function drawAccessory(ctx, kind, x, y, s, col = '#2b2d42') {
  ctx.save();
  ctx.translate(x, y - 0.765 * s);
  ctx.scale(s, s);
  if (kind === 'glasses') {
    ctx.lineWidth = 0.015; ctx.strokeStyle = INK;
    circle(ctx, -0.072, -0.005, 0.055); ctx.stroke();
    circle(ctx, 0.072, -0.005, 0.055); ctx.stroke();
    line(ctx, -0.017, -0.005, 0.017, -0.005, 0.015, INK);
  } else if (kind === 'beanie') {
    ctx.beginPath();
    ctx.arc(0, -0.05, 0.195, Math.PI * 1.05, Math.PI * 1.95);
    ctx.closePath();
    fillStroke(ctx, col, 0.018);
    rrect(ctx, -0.205, -0.08, 0.41, 0.055, 0.025);
    fillStroke(ctx, '#ffb703', 0.016);
    circle(ctx, 0, -0.26, 0.042);
    fillStroke(ctx, '#ffb703', 0.016);
  } else if (kind === 'headband') {
    rrect(ctx, -0.195, -0.095, 0.39, 0.042, 0.018);
    fillStroke(ctx, col, 0.016);
  }
  ctx.restore();
}

function drawStudioBackdrop(ctx, t, cam, pal, variant = 'day') {
  applyCam(ctx, cam, 0.08);
  const top = variant === 'night' ? '#141b34' : variant === 'warm' ? '#f4a261' : pal.sky_top;
  const bot = variant === 'night' ? '#2c3e6b' : variant === 'warm' ? '#fff1d0' : pal.sky_bot;
  drawSky(ctx, top, bot, -400, 1280);

  applyCam(ctx, cam, 0.14);
  if (variant === 'night') {
    const R = rng(77);
    for (let i = 0; i < 28; i++) {
      const sx = R() * 1280 - 100, sy = R() * 820 + 60;
      const tw = 0.35 + 0.65 * Math.abs(Math.sin(t * 2.4 + i));
      circle(ctx, sx, sy, 2.5 + (i % 3) * 1.5);
      ctx.fillStyle = `rgba(255,248,210,${tw.toFixed(2)})`;
      ctx.fill();
    }
  } else {
    drawSun(ctx, 860, 250, 78, t, 0.85);
    drawCloud(ctx, 180 + t * 8, 300, 105, 11, 0.92);
    drawCloud(ctx, 820 + t * 5, 420, 85, 12, 0.88);
  }

  // Midground architectural hills / studio wall wainscoting
  applyCam(ctx, cam, 0.38);
  ctx.beginPath();
  ctx.moveTo(-600, 1240);
  ctx.quadraticCurveTo(180, 1020, 560, 1130);
  ctx.quadraticCurveTo(960, 1230, 1680, 1060);
  ctx.lineTo(1680, 2200); ctx.lineTo(-600, 2200); ctx.closePath();
  fillStroke(ctx, variant === 'night' ? '#233154' : '#8ecae6', 5);

  // Foreground perspective floor
  applyCam(ctx, cam, 1.0);
  const fg = ctx.createLinearGradient(0, 1200, 0, 2100);
  fg.addColorStop(0, variant === 'night' ? '#2c2a3e' : pal.ground);
  fg.addColorStop(1, variant === 'night' ? '#191824' : '#c9965b');
  ctx.fillStyle = fg;
  ctx.fillRect(-700, 1200, 2500, 1000);
  line(ctx, -700, 1200, 1800, 1200, 6, INK);
  // Subtle floor perspective planks
  for (let i = -4; i <= 8; i++) {
    const x0 = 540 + (i - 2) * 140, x1 = 540 + (i - 2) * 340;
    line(ctx, x0, 1200, x1, 2100, 3, 'rgba(32,26,35,0.16)');
  }
}

function drawPropMotif(ctx, motif, x, y, s, t, progress = 0.5) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(s, s);
  if (motif === 'clock') {
    circle(ctx, 0, 0, 95); fillStroke(ctx, '#fffdf7', 7);
    circle(ctx, 0, 0, 80); ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(32,26,35,0.2)'; ctx.stroke();
    // 20-min green zone vs 60-min red zone arc
    ctx.beginPath(); ctx.moveTo(0, 0);
    ctx.arc(0, 0, 74, -Math.PI / 2, -Math.PI / 2 + TAU * Math.min(0.34, progress));
    ctx.closePath(); ctx.fillStyle = 'rgba(63,163,91,0.38)'; ctx.fill();
    for (let k = 0; k < 12; k++) {
      const a = k / 12 * TAU - Math.PI / 2;
      line(ctx, Math.cos(a) * 66, Math.sin(a) * 66, Math.cos(a) * 80, Math.sin(a) * 80, k % 3 === 0 ? 5 : 3);
    }
    const ang = -Math.PI / 2 + progress * TAU;
    line(ctx, 0, 0, Math.cos(ang) * 62, Math.sin(ang) * 62, 7, '#e63946');
    line(ctx, 0, 0, Math.cos(ang * 0.15 - 1.1) * 42, Math.sin(ang * 0.15 - 1.1) * 42, 7, INK);
    circle(ctx, 0, 0, 9); fillStroke(ctx, '#ffb703', 4);
    // Twin alarm bells on top
    for (const side of [-1, 1]) {
      const ring = Math.sin(t * 28) * (progress > 0.7 ? 5 : 0);
      ctx.save(); ctx.translate(side * 62 + ring, -88); ctx.rotate(side * 0.45);
      ctx.beginPath(); ctx.arc(0, 0, 26, Math.PI, 0); ctx.closePath();
      fillStroke(ctx, '#ffb703', 5);
      ctx.restore();
    }
  } else if (motif === 'battery') {
    rrect(ctx, -64, -110, 128, 210, 18); fillStroke(ctx, '#f8f9fa', 7);
    rrect(ctx, -28, -130, 56, 22, 7); fillStroke(ctx, '#adb5bd', 6);
    const lvl = clamp(progress, 0.08, 1);
    const bh = 178 * lvl;
    const col = lvl > 0.55 ? '#3fa35b' : lvl > 0.28 ? '#ffb703' : '#e63946';
    rrect(ctx, -48, 84 - bh, 96, bh, 10); fillStroke(ctx, col, 4);
    // Lightning bolt icon
    path(ctx, [[8, -48], [-22, 4], [2, 4], [-10, 52], [26, -6], [2, -6]]);
    fillStroke(ctx, '#fff3b0', 4);
  } else if (motif === 'coffee') {
    rrect(ctx, -56, -55, 112, 118, [8, 8, 28, 28]); fillStroke(ctx, '#f4f1de', 7);
    ctx.beginPath(); ctx.arc(56, 2, 32, -Math.PI / 2, Math.PI / 2);
    ctx.lineWidth = 11; ctx.strokeStyle = '#f4f1de'; ctx.stroke();
    ctx.lineWidth = 6; ctx.strokeStyle = INK; ctx.stroke();
    ellipse(ctx, 0, -52, 50, 12); fillStroke(ctx, '#6f4e37', 5);
    // Organic rising steam wisps (secondary motion)
    for (let i = -1; i <= 1; i++) {
      const sy = -80 - ((t * 42 + i * 25) % 55);
      const sx = i * 24 + Math.sin(t * 4 + i) * 9;
      const al = 1 - Math.abs((sy + 108) / 55);
      ctx.save(); ctx.globalAlpha = clamp(al, 0, 0.75);
      ctx.beginPath(); ctx.moveTo(sx, sy + 24);
      ctx.quadraticCurveTo(sx + 12, sy + 12, sx - 4, sy);
      ctx.lineWidth = 5; ctx.strokeStyle = '#ffffff'; ctx.lineCap = 'round'; ctx.stroke();
      ctx.restore();
    }
  } else if (motif === 'scale') {
    line(ctx, 0, 85, 0, -75, 8, INK);
    rrect(ctx, -60, 82, 120, 18, 8); fillStroke(ctx, '#8d99ae', 5);
    const tilt = Math.sin(t * 2.2) * 0.18 + (progress - 0.5) * 0.35;
    ctx.save(); ctx.translate(0, -68); ctx.rotate(tilt);
    line(ctx, -95, 0, 95, 0, 7, INK);
    for (const side of [-1, 1]) {
      line(ctx, side * 88, 0, side * 88, 52, 4, INK);
      ctx.beginPath(); ctx.arc(side * 88, 56, 30, 0, Math.PI); ctx.closePath();
      fillStroke(ctx, side < 0 ? '#ffb703' : '#4cc9f0', 5);
    }
    ctx.restore();
  } else {
    // Brain / idea spark / wave motif
    ctx.beginPath();
    const lobes = [[-36, -18, 40], [0, -38, 44], [38, -16, 38], [32, 22, 34], [-28, 22, 34]];
    lobes.forEach(([lx, ly, lr]) => { ctx.moveTo(lx + lr, ly); ctx.arc(lx, ly, lr, 0, TAU); });
    ctx.lineWidth = 11; ctx.strokeStyle = INK; ctx.stroke();
    ctx.fillStyle = '#ffafcc'; ctx.fill();
    // Neural spark pulses along curve
    for (let k = 0; k < 4; k++) {
      const a = t * 2.8 + k * (TAU / 4);
      const px = Math.cos(a) * 58, py = Math.sin(a) * 42 - 8;
      sparkle(ctx, px, py, 14 + 5 * Math.sin(t * 6 + k), 0.85);
    }
  }
  ctx.restore();
}

// NOVEL NON-TEMPLATE SCENE: Interactive Cross-Section Mechanism Cutaway
// Built 100% in stick-figure ink-and-cel visual grammar (thick #201a23 outlines, cel-shaded shapes, Poppins labels)
function drawNovelMechanismCutaway(ctx, lt, dur, t, shotSpec, pal) {
  const u = clamp(lt / Math.max(0.1, dur), 0, 1);
  // Blueprint cel-shaded card background
  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, '#182238'); g.addColorStop(1, '#0e1525');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

  // Subtle hand-drawn grid inside safe zone
  ctx.strokeStyle = 'rgba(142,202,230,0.12)'; ctx.lineWidth = 2;
  for (let x = 120; x <= 960; x += 84) line(ctx, x, 240, x, 1220, 2, 'rgba(142,202,230,0.10)');
  for (let y = 260; y <= 1220; y += 84) line(ctx, 120, y, 960, y, 2, 'rgba(142,202,230,0.10)');

  const hh = shake(t * 0.35, 3, 1, 9);
  const cam = { x: 540 + hh[0], y: 940 + hh[1], z: kf(u, [[0, 0.96], [0.25, 1.03, easeOut], [1, 1.08]]), r: 0 };
  applyCam(ctx, cam, 1);

  // Main cutaway frame panel (safe inside x:130..950, y:290..1180)
  rrect(ctx, 135, 290, 810, 870, 34);
  fillStroke(ctx, '#f8f5ec', 8);
  shadeShape(ctx, () => rrect(ctx, 135, 290, 810, 870, 34), 1, 0.08, 0.25, [135, 290, 810, 870]);

  // Top wave meter: Light Stage vs Deep Slow-Wave Threshold
  rrect(ctx, 185, 345, 710, 250, 22);
  fillStroke(ctx, '#1d2d44', 6);

  // Threshold divider line
  const threshX = 540;
  ctx.save();
  ctx.setLineDash([12, 10]);
  line(ctx, threshX, 360, threshX, 580, 4, '#ffb703');
  ctx.restore();

  // Animated physiological / mechanism wave drawing across panel
  const waveProg = easeInOut(clamp(u * 1.25, 0, 1));
  ctx.beginPath();
  const maxX = lerp(205, 875, waveProg);
  for (let x = 205; x <= maxX; x += 6) {
    const past = x > threshX;
    const freq = past ? 0.022 : 0.065;
    const amp = past ? 68 : 24;
    const wy = 470 + Math.sin((x - 205) * freq - t * 5.5) * amp;
    if (x === 205) ctx.moveTo(x, wy); else ctx.lineTo(x, wy);
  }
  ctx.lineWidth = 7;
  ctx.strokeStyle = waveProg > 0.52 ? '#ff6b6b' : '#4cc9f0';
  ctx.lineCap = 'round'; ctx.stroke();

  // Moving tracer dot on wave tip
  const tipPast = maxX > threshX;
  const tipY = 470 + Math.sin((maxX - 205) * (tipPast ? 0.022 : 0.065) - t * 5.5) * (tipPast ? 68 : 24);
  circle(ctx, maxX, tipY, 14);
  fillStroke(ctx, tipPast ? '#ff6b6b' : '#4cc9f0', 5);

  // Stick-figure scientist/observer inspecting cutaway at bottom-left + dynamic mechanism dial at bottom-right
  const pointReach = kf(u, [[0.1, 0], [0.4, 1, backOut]]);
  drawStick(ctx, {
    x: 330, y: 1125, s: 470,
    cols: PAL.blue, hat: 'none',
    headTilt: tipPast ? 0.09 : -0.05,
    bob: Math.sin(t * 3.2) * 0.006,
    arms: {
      L: [0.35, -0.2],
      R: pointReach > 0 ? { ik: [lerp(0.22, 0.48, pointReach), lerp(-0.45, -0.92, pointReach)], bend: -1 } : [0.3, -0.1],
    },
    legs: { L: [0.12, -0.04], R: [0.14, -0.04] },
    face: tipPast
      ? { eyes: 'wide', look: [0.65, -0.45], mouth: 'o', browUp: 1 }
      : { eyes: 'normal', look: [0.5, -0.35], mouth: 'smile' },
  });
  drawAccessory(ctx, 'glasses', 330, 1125, 470);

  // Mechanism prop linked to wave progress
  drawPropMotif(ctx, shotSpec.primaryMotif || 'clock', 725, 860, 1.55, t, waveProg);

  // Clean visual tag inside card (no sentence clutter)
  text(ctx, tipPast ? 'DEEP THRESHOLD' : 'LIGHT ZONE', 540, 645, 36, tipPast ? '#e63946' : '#2a9d8f', '#ffffff', 6, 'Poppins', 700);
}

// NOVEL NON-TEMPLATE SCENE 2: Split-Stage Side-by-Side Comparison
function drawSplitComparisonStage(ctx, lt, dur, t, shotSpec, pal) {
  const u = clamp(lt / Math.max(0.1, dur), 0, 1);
  // Left warm crisp zone vs Right groggy cool zone
  ctx.fillStyle = '#fff3d6'; ctx.fillRect(0, 0, W / 2, H);
  ctx.fillStyle = '#222a42'; ctx.fillRect(W / 2, 0, W / 2, H);
  line(ctx, W / 2, 0, W / 2, H, 10, INK);

  // Floor line across both halves
  ctx.fillStyle = '#e7c68d'; ctx.fillRect(0, 1180, W / 2, 800);
  ctx.fillStyle = '#161b2c'; ctx.fillRect(W / 2, 1180, W / 2, 800);
  line(ctx, 0, 1180, W, 1180, 7, INK);

  // Left figure: energized hop with anticipation & squash-stretch
  const hopPhase = (lt * 1.35) % 1;
  const jumpY = hopPhase < 0.45 ? -Math.sin(hopPhase / 0.45 * Math.PI) * 95 : 0;
  const sq = hopPhase < 0.08 ? 0.86 : (hopPhase > 0.45 && hopPhase < 0.58 ? 0.88 : 1.0);
  drawStick(ctx, {
    x: 285, y: 1165 + jumpY, s: 460, squash: sq,
    cols: PAL.green, hat: 'none',
    arms: hopPhase < 0.45 ? POSE.handsUp.arms : { L: [0.5, -0.4], R: [2.3, 0.3] },
    legs: hopPhase < 0.45 ? { L: [0.45, -0.7], R: [0.45, -0.7] } : POSE.idle.legs,
    face: { eyes: 'happy', mouth: 'grin', browUp: 0.6 },
  });
  sparkle(ctx, 165, 690, 34 * (0.6 + 0.4 * Math.sin(t * 5)), 0.9);
  drawPropMotif(ctx, 'battery', 285, 490, 0.95, t, 0.92);

  // Right figure: slumped groggy spiral-eyed figure
  drawStick(ctx, {
    x: 795, y: 1165, s: 460, t,
    cols: PAL.purple, hat: 'beanie',
    lean: 0.14 + Math.sin(t * 2) * 0.03,
    headTilt: 0.22,
    arms: { L: [0.18, 0.08], R: [0.15, 0.1] },
    legs: { L: [0.18, -0.12], R: [0.2, -0.1] },
    face: { eyes: 'spiral', mouth: 'frown', browAng: -0.25 },
  });
  sweat(ctx, 885, 810 + ((lt * 55) % 45), 26, 0.85);
  drawPropMotif(ctx, 'battery', 795, 490, 0.95, t, 0.18);
}
"""


def _build_shots_js(storyboard: Dict[str, Any], words: List[Dict[str, Any]]) -> str:
    pal = storyboard["style_adapter_params"]["palette"]
    shots = storyboard["shots"]
    js_lines: List[str] = [
        f"const STYLE_PAL = {json.dumps(pal)};",
        f"const WORDS = {json.dumps(words, ensure_ascii=False)};",
        "window.WARP = null;",
        "const SHOTS = [];",
    ]

    for i, s in enumerate(shots):
        start = s["start"]
        end = s["end"]
        dur = max(0.2, round(end - start, 3))
        tr = s["transition_out"]
        setup = s["setup_type"]
        motif = s["staging"]["visual_metaphor"]
        sec_motif = s["staging"]["secondary_prop"]
        expr = s["staging"]["character_expression"]

        spec_json = json.dumps({"primaryMotif": motif, "secondaryMotif": sec_motif, "expr": expr, "index": i})

        if setup == "novel_mechanism_cutaway":
            body = f"drawNovelMechanismCutaway(ctx, lt, {dur}, t, {spec_json}, STYLE_PAL);"
        elif setup == "split_comparison_stage":
            body = f"drawSplitComparisonStage(ctx, lt, {dur}, t, {spec_json}, STYLE_PAL);"
        elif i == 0:
            # Hook CU: immediate motion on frame 1! Character leans in, raises prop along parabolic arc
            body = f"""
  const u = clamp(lt / {dur}, 0, 1);
  const hh = shake(t * 0.35, 3.5, 1, {i + 2});
  const cam = {{ x: 540 + hh[0], y: 930 + hh[1] - u * 28, z: 1.02 + easeOut(u) * 0.10, r: Math.sin(t * 0.6) * 0.005 }};
  drawStudioBackdrop(ctx, t, cam, STYLE_PAL, 'day');
  applyCam(ctx, cam, 1);
  const reach = kf(u, [[0, 0.15], [0.18, 0.05], [0.52, 1.0, backOut], [1, 1.0]]);
  const propPos = arcPt(760, 1080, 740, 760, 90, reach);
  drawPropMotif(ctx, {json.dumps(motif)}, propPos[0], propPos[1], 1.35, t, 0.3 + 0.5 * u);
  const blink = (u > 0.58 && u < 0.64) ? 1 : 0;
  drawStick(ctx, {{
    x: 410, y: 1520, s: 880,
    cols: PAL.red, hat: 'none',
    bob: Math.sin(t * 3.4) * 0.005,
    headTilt: kf(u, [[0, 0.04], [0.45, -0.08, backOut], [1, -0.04]]),
    arms: {{
      L: [0.35, -0.18],
      R: {{ ik: [(propPos[0] - 410) / 880 - 0.08, (propPos[1] - 1520) / 880 + 0.05], bend: -1 }}
    }},
    legs: POSE.idle.legs,
    face: {{ eyes: u > 0.42 ? 'wide' : 'normal', look: [0.45, -0.2], blink, mouth: u > 0.45 ? 'grin' : 'smirk', browOne: -1 }},
    shadow: false
  }});
  drawAccessory(ctx, 'headband', 410, 1520, 880, '#e63946');
"""
        elif "turn" in s["beat_role"] or setup == "turn_reaction_ecu":
            # Dramatic turn ECU: night shift, dutch camera snap, surprised reaction + burst
            body = f"""
  const u = clamp(lt / {dur}, 0, 1);
  const snap = kf(u, [[0, 0], [0.22, 1, backOut], [1, 1]]);
  const hh = shake(t * 0.8, 5 * (1 - u * 0.5), 1, {i + 5});
  const cam = {{ x: 540 + hh[0], y: 940 + hh[1], z: lerp(1.0, 1.18, easeOut(u)), r: lerp(-0.025, 0.012, u) }};
  drawStudioBackdrop(ctx, t, cam, STYLE_PAL, 'night');
  applyCam(ctx, cam, 1);
  if (u > 0.14 && u < 0.72) {{
    burst(ctx, 540, 770, 260 * snap, 13, '#ffb703', {i + 7}, 0.58);
  }}
  drawStick(ctx, {{
    x: 540, y: 1620, s: 980,
    cols: PAL.yellow, hat: 'none',
    squash: kf(u, [[0, 1], [0.12, 0.88], [0.3, 1.05, backOut], [0.5, 1]]),
    arms: POSE.handsUp.arms,
    legs: POSE.idle.legs,
    face: {{ eyes: 'wide', look: [0, -0.1], mouth: 'o', browUp: 1, browAng: -0.25 }},
    shadow: false
  }});
  sweat(ctx, 720, 790 + u * 65, 34, clamp(u * 2.5, 0, 0.9));
"""
        elif i == len(shots) - 1:
            # Payoff pullback: sunny wide hero landing, sparkle, resolved posture
            body = f"""
  const u = clamp(lt / {dur}, 0, 1);
  const hh = shake(t * 0.25, 2.2, 1, {i + 9});
  const cam = {{ x: 540 + hh[0], y: 960 + hh[1], z: lerp(1.14, 0.98, easeInOut(u)), r: 0 }};
  drawStudioBackdrop(ctx, t, cam, STYLE_PAL, 'warm');
  applyCam(ctx, cam, 1);
  drawPropMotif(ctx, {json.dumps(motif)}, 780, 910, 1.25, t, 0.34);
  drawPropMotif(ctx, {json.dumps(sec_motif)}, 260, 930, 1.1, t, 0.95);
  const sq = kf(u, [[0, 0.9], [0.22, 1.04, backOut], [0.45, 1.0]]);
  drawStick(ctx, {{
    x: 530, y: 1230, s: 560, squash: sq,
    cols: PAL.blue, hat: 'none',
    bob: Math.sin(t * 2.8) * 0.005,
    arms: {{ L: [0.9, -2.1], R: [2.35, 0.25] }},
    legs: POSE.hips.legs,
    face: {{ eyes: 'happy', mouth: 'grin', browUp: 0.4 }}
  }});
  sparkle(ctx, 690, 680, 44 * kf(u, [[0.15, 0], [0.35, 1, backOut], [0.85, 0.6]]), 0.95);
"""
        else:
            # Wide tracking action setup: character walks across 3-plane parallax stage toward prop
            body = f"""
  const u = clamp(lt / {dur}, 0, 1);
  const walkU = clamp(u / 0.78, 0, 1);
  const cx = lerp(280, 520, easeInOut(walkU));
  const hh = shake(t * 0.35, 3, 1, {i + 11});
  const cam = {{ x: lerp(470, 560, u) + hh[0], y: 960 + hh[1], z: 1.0 + u * 0.06, r: 0 }};
  drawStudioBackdrop(ctx, t, cam, STYLE_PAL, 'day');
  applyCam(ctx, cam, 1);
  drawPropMotif(ctx, {json.dumps(motif)}, 800, 1020, 1.35, t, u);
  const walking = u < 0.78;
  drawStick(ctx, {{
    x: cx, y: 1225 - (walking ? Math.abs(Math.sin(lt * 11)) * 18 : 0),
    s: 520,
    cols: PAL.red, hat: 'none',
    lean: walking ? 0.08 : 0,
    arms: walking ? {{ L: [0.3 - Math.sin(lt * 11) * 0.55, -0.3], R: [0.3 + Math.sin(lt * 11) * 0.55, -0.3] }} : POSE.hips.arms,
    legs: walking ? {{ L: [Math.sin(lt * 11) * 0.5 + 0.05, -Math.max(0, Math.sin(lt * 11 + 1)) * 0.65], R: [-Math.sin(lt * 11) * 0.5 + 0.05, -Math.max(0, -Math.sin(lt * 11 + 1)) * 0.65] }} : POSE.idle.legs,
    face: {{ eyes: 'normal', look: [0.6, -0.1], mouth: walking ? 'smile' : 'smirk' }}
  }});
  if (walking) puff(ctx, cx - 95, 1220, 32, t, '#efe5d5', {i + 3}, 0.55);
"""

        js_lines.append(
            f"SHOTS.push({{ start: {start}, end: {end}, tr: {json.dumps(tr)}, draw(ctx, lt, t) {{{body}\n}} }});"
        )

    return "\n".join(js_lines) + "\n"


COMPOSITOR_4K_JS = r"""// ---------- Resolution-Independent Native 1080p / 4K Stick-Figure Compositor ----------
const params = new URLSearchParams(location.search);
const RENDER_SCALE = Math.max(1, Number(params.get('scale') || 1));
const PW = W * RENDER_SCALE, PH = H * RENDER_SCALE;

const canvas = document.getElementById('c');
canvas.width = PW; canvas.height = PH;
canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
const out = canvas.getContext('2d');

const buf = document.createElement('canvas');
buf.width = PW; buf.height = PH;
const bctx = buf.getContext('2d');

const bufPrev = document.createElement('canvas');
bufPrev.width = PW; bufPrev.height = PH;
const pctx = bufPrev.getContext('2d');

// Override applyCam & darkness so logical 1080x1920 coordinates scale cleanly to PW x PH vectorially!
applyCam = function(ctx, cam, depth = 1) {
  ctx.setTransform(RENDER_SCALE, 0, 0, RENDER_SCALE, 0, 0);
  const z = 1 + (cam.z - 1) * depth;
  ctx.translate(W / 2, H / 2);
  ctx.rotate((cam.r || 0) * depth);
  ctx.scale(z, z);
  ctx.translate(-(540 + (cam.x - 540) * depth), -(960 + (cam.y - 960) * depth));
};

darkness = function(ctx, a, col = '#050407') {
  if (a <= 0) return;
  ctx.save();
  ctx.setTransform(RENDER_SCALE, 0, 0, RENDER_SCALE, 0, 0);
  ctx.globalAlpha = clamp(a);
  ctx.fillStyle = col;
  ctx.fillRect(0, 0, W, H);
  ctx.restore();
};

const TOTAL_DURATION = SHOTS[SHOTS.length - 1].end;
window.TOTAL_DURATION = TOTAL_DURATION;
window.SHOT_SPANS = SHOTS.map(s => [s.start, s.end]);

// Deterministic grain tiles
const grains = [];
for (let k = 0; k < 4; k++) {
  const g = document.createElement('canvas'); g.width = g.height = 256;
  const gc = g.getContext('2d');
  const id = gc.createImageData(256, 256);
  const R = rng(k + 19);
  for (let i = 0; i < id.data.length; i += 4) {
    const v = 128 + (R() - 0.5) * 110;
    id.data[i] = id.data[i + 1] = id.data[i + 2] = v;
    id.data[i + 3] = 255;
  }
  gc.putImageData(id, 0, 0);
  grains.push(g);
}

// Word-aligned 1-2 word pop captions
const CHUNKS = (() => {
  const ch = []; let cur = null;
  WORDS.forEach((w, i) => {
    const prev = WORDS[i - 1];
    const brk = !cur || cur.words.length >= 2 || (cur.text + ' ' + w.w).length > 14 || /[.,?!]$/.test(prev ? prev.w : '') || (prev && prev.line !== w.line);
    if (brk) { cur = { words: [w], text: w.w, s: w.s, e: w.e }; ch.push(cur); }
    else { cur.words.push(w); cur.text += ' ' + w.w; cur.e = w.e; }
  });
  ch.forEach((c, i) => { const n = ch[i + 1]; c.e = n && n.s - c.e < 0.45 ? n.s : c.e + 0.22; });
  return ch;
})();

const capText = s => s.toLowerCase().replace(/[-\u2013\u2014]/g, ' ').replace(/[^\p{L}\p{N}% ]/gu, '').replace(/\s+/g, ' ').trim();

function drawCaptionScaled(ctx, t) {
  const c = CHUNKS.find(c => t >= c.s && t < c.e);
  if (!c) return;
  const k = clamp((t - c.s) / 0.095);
  const sc = 0.82 + 0.18 * backOut(k);
  ctx.save();
  ctx.setTransform(RENDER_SCALE, 0, 0, RENDER_SCALE, 0, 0);
  ctx.translate(540, 1345);
  ctx.scale(sc, sc);
  ctx.shadowColor = 'rgba(0,0,0,0.55)';
  ctx.shadowBlur = 18 * RENDER_SCALE;
  ctx.shadowOffsetY = 5 * RENDER_SCALE;
  text(ctx, capText(c.text), 0, 0, 70, '#ffffff', '#151219', 14, 'Poppins', 700);
  ctx.shadowColor = 'transparent';
  text(ctx, capText(c.text), 0, 0, 70, '#ffffff', '#151219', 0, 'Poppins', 700);
  ctx.restore();
}

function renderShotTo(ctx, idx, t) {
  const s = SHOTS[idx];
  ctx.setTransform(RENDER_SCALE, 0, 0, RENDER_SCALE, 0, 0);
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'source-over';
  ctx.filter = 'none';
  ctx.fillStyle = '#0e131f';
  ctx.fillRect(0, 0, W, H);
  ctx.save();
  s.draw(ctx, Math.max(0, t - s.start), t);
  ctx.restore();
}

function blitWhip(src, dxLogical, blurLogical) {
  const dx = dxLogical * RENDER_SCALE;
  const blur = blurLogical * RENDER_SCALE;
  const n = blurLogical > 2 ? 7 : 1;
  out.save();
  out.setTransform(1, 0, 0, 1, 0, 0);
  for (let k = 0; k < n; k++) {
    const off = n > 1 ? (k / (n - 1) - 0.5) * blur : 0;
    out.globalAlpha = 1 / (k + 1);
    const x = dx + off;
    out.drawImage(src, x, 0);
    if (x > 0) out.drawImage(src, x - PW, 0);
    if (x < 0) out.drawImage(src, x + PW, 0);
  }
  out.restore();
}

window.renderAtTime = function(rawT) {
  const t = clamp(rawT, 0, TOTAL_DURATION - 1e-4);
  let i = SHOTS.findIndex(s => t >= s.start && t < s.end);
  if (i < 0) i = SHOTS.length - 1;
  const s = SHOTS[i];
  const prev = SHOTS[i - 1];
  const WT = 0.18;

  out.setTransform(1, 0, 0, 1, 0, 0);
  out.fillStyle = '#000';
  out.fillRect(0, 0, PW, PH);

  // Motivated transitions: whip pan OR animated iris circle mask!
  if (prev && prev.tr === 'iris_mask' && t < s.start + 0.34) {
    const u = easeOut((t - s.start) / 0.34);
    renderShotTo(pctx, i - 1, s.start - 0.005);
    renderShotTo(bctx, i, t);
    out.drawImage(bufPrev, 0, 0);
    out.save();
    out.beginPath();
    out.arc(PW * 0.5, PH * 0.48, u * Math.hypot(PW, PH) * 0.65, 0, TAU);
    out.clip();
    out.drawImage(buf, 0, 0);
    out.restore();
  } else {
    let dx = 0, blur = 0;
    if (s.tr === 'whip' && i < SHOTS.length - 1 && t > s.end - WT) {
      const p = easeIn((t - (s.end - WT)) / WT);
      dx = -p * 420; blur = p * 220;
    } else if (prev && prev.tr === 'whip' && t < s.start + WT) {
      const p = 1 - easeOut((t - s.start) / WT);
      dx = p * 420; blur = p * 220;
    }
    renderShotTo(bctx, i, t);
    blitWhip(buf, dx, blur);
  }

  // Cohesive vignette + subtle organic film grain
  out.save();
  out.setTransform(RENDER_SCALE, 0, 0, RENDER_SCALE, 0, 0);
  const g = out.createRadialGradient(540, 900, 480, 540, 960, 1260);
  g.addColorStop(0, 'rgba(0,0,0,0)');
  g.addColorStop(1, 'rgba(12,8,22,0.28)');
  out.fillStyle = g;
  out.fillRect(0, 0, W, H);
  const fIdx = Math.round(t * 30);
  out.globalCompositeOperation = 'overlay';
  out.globalAlpha = 0.06;
  const pat = out.createPattern(grains[fIdx % 4], 'repeat');
  out.fillStyle = pat;
  out.translate((fIdx * 37) % 256, (fIdx * 91) % 256);
  out.fillRect(-256, -256, W + 512, H + 512);
  out.restore();

  drawCaptionScaled(out, t);
  return i;
};

window.grabCanvasDataURL = (mime = 'image/jpeg', q = 0.96) => canvas.toDataURL(mime, q);
window.SHORT_DIRECTOR_READY = Promise.all([
  document.fonts.load('700 70px Poppins'),
  document.fonts.load('700 40px Lora'),
]).then(() => { window.renderAtTime(0); return true; });
"""


def generate_engine_project(
    project_root: Path,
    run_dir: Path,
    storyboard: Dict[str, Any],
    parsed_script: Dict[str, Any],
) -> Dict[str, Any]:
    """Create `<run_dir>/engine_work` using ONLY `skills/stick-figure` primitives + bespoke JS."""
    upstream_sf = project_root / "vendor" / "claude-animation-skills" / "skills" / "stick-figure" / "engine" / "template" / "web"
    work_web = run_dir / "engine_work" / "web"
    if work_web.exists():
        shutil.rmtree(work_web)
    work_web.mkdir(parents=True, exist_ok=True)

    visual_sources: List[str] = []
    # Copy ONLY base drawing primitives and OFL fonts from stick-figure (NOT the pirate shots.js!)
    for fname in ("lib.js", "chars.js", "env.js"):
        src = (upstream_sf / fname).resolve()
        shutil.copy2(src, work_web / fname)
        visual_sources.append(str(src))

    fonts_dst = work_web / "fonts"
    fonts_dst.mkdir(parents=True, exist_ok=True)
    for fpath in (upstream_sf / "fonts").iterdir():
        shutil.copy2(fpath.resolve(), fonts_dst / fpath.name)
        visual_sources.append(str(fpath.resolve()))

    novel_path = work_web / "novel_world.js"
    novel_path.write_text(NOVEL_WORLD_JS, encoding="utf-8")

    shots_js_path = work_web / "shots.js"
    shots_js_path.write_text(_build_shots_js(storyboard, parsed_script["voice"]["words"]), encoding="utf-8")

    comp_path = work_web / "compositor.js"
    comp_path.write_text(COMPOSITOR_4K_JS, encoding="utf-8")

    index_html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>
@font-face{font-family:Poppins;font-weight:700;src:url(fonts/Poppins-Bold.ttf)}
@font-face{font-family:Lora;font-weight:400 700;src:url(fonts/Lora-Variable.ttf)}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden;background:#000}
</style></head><body>
<canvas id="c"></canvas>
<script src="lib.js"></script>
<script src="chars.js"></script>
<script src="env.js"></script>
<script src="novel_world.js"></script>
<script src="shots.js"></script>
<script src="compositor.js"></script>
</body></html>
"""
    index_path = work_web / "index.html"
    index_path.write_text(index_html, encoding="utf-8")

    visual_sources.extend([
        str(Path(__file__).resolve()),
        str(novel_path.resolve()),
        str(shots_js_path.resolve()),
        str(comp_path.resolve()),
        str(index_path.resolve()),
    ])

    return {
        "engine": "stick-figure",
        "work_dir": str((run_dir / "engine_work").resolve()),
        "entry_html": str(index_path.resolve()),
        "capture_mode": "canvas_jpeg",
        "supports_native_4k": True,
        "uses_webgl": False,
        "visual_sources": visual_sources,
    }
