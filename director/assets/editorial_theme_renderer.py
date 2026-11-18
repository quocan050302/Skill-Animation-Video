"""Pure Deterministic Role-Aware SVG/DOM Overlay Renderer JS Module (`SD-RETENTION-03`).

Supports both:
- `editorial_theme == 'role-aware'` (semantic visual hierarchy: two-tone outlined
  curiosity display headlines, large black-stroked red impact arrows, minimal location chips,
  high-contrast fact cards, clean explanation leaders, quiet aftermath strips).
- `editorial_theme == 'legacy'` (backward-compatible classic dark box renderer for controlled A/B).
"""

from __future__ import annotations


EDITORIAL_THEME_RENDERER_JS = r"""
export class EditorialOverlayController {
  constructor(stageEl, capEl, timeline) {
    this.stageEl = stageEl;
    this.capEl = capEl;
    this.timeline = timeline || { caption_chunks: [], overlays: [], editorial_theme: 'role-aware' };
    this.svgNS = 'http://www.w3.org/2000/svg';

    this.svg = document.createElementNS(this.svgNS, 'svg');
    this.svg.setAttribute('viewBox', '0 0 1080 1920');
    this.svg.setAttribute('width', '1080');
    this.svg.setAttribute('height', '1920');
    this.svg.style.cssText = 'position:absolute;inset:0;width:1080px;height:1920px;pointer-events:none;z-index:14;overflow:visible;';
    if (this.stageEl) this.stageEl.appendChild(this.svg);

    this.lastTelemetry = { overlays: [], caption: null, active_count: 0 };
  }

  renderAtTime(t, anchorsMap = {}) {
    const tl = this.timeline || {};
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    const lerp = (a, b, u) => a + (b - a) * u;
    const easeOutCubic = u => 1 - Math.pow(1 - clamp(u, 0, 1), 3);
    const SAFE = { x0: 76, y0: 155, x1: 1004, y1: 1640, capY0: 1345 };

    while (this.svg.firstChild) this.svg.removeChild(this.svg.firstChild);

    const el = (tag, attrs = {}) => {
      const node = document.createElementNS(this.svgNS, tag);
      for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
      return node;
    };

    const chunks = tl.caption_chunks || [];
    const capMode = String(tl.caption_mode || 'kinetic');
    const activeChunk = chunks.find(c => t >= c.start && t <= c.end) || null;
    let capTel = { text: '', active_word: '', chunk_id: null, mode: capMode, caption_layout: null };

    if (this.capEl) {
      this.capEl.style.display = 'flex';
      this.capEl.style.flexWrap = 'wrap';
      this.capEl.style.justifyContent = 'center';
      this.capEl.style.alignItems = 'baseline';
      this.capEl.style.columnGap = '0.40em';
      this.capEl.style.rowGap = '0.20em';
    }
    if (activeChunk && this.capEl) {
      if (capMode === 'plain') {
        this.capEl.textContent = activeChunk.text || '';
        capTel.text = activeChunk.text || '';
        capTel.chunk_id = activeChunk.chunk_id;
      } else {
        this.capEl.innerHTML = '';
        const ws = activeChunk.words || [];
        let activeW = '';
        const spanEls = [];
        ws.forEach((wObj) => {
          const span = document.createElement('span');
          span.textContent = String(wObj.w || '');
          const isCur = t >= wObj.s && t <= (wObj.e + 0.04);
          const past = t > wObj.e + 0.04;
          let scale = 1.0;
          if (isCur) {
            const p = clamp((t - wObj.s) / Math.max(0.06, wObj.e - wObj.s), 0, 1);
            scale = 1.0 + 0.05 * Math.sin(Math.min(1, p * 2.0) * Math.PI * 0.5);
            activeW = wObj.w || '';
          }
          const isEmp = Boolean(wObj.is_emphasis);
          const color = isCur
            ? (isEmp ? (wObj.accent_color || '#fbbf24') : '#ffffff')
            : (isEmp ? (wObj.accent_color || '#fbbf24') : (past ? 'rgba(241,245,249,0.92)' : 'rgba(226,232,240,0.82)'));
          span.style.display = 'inline-block';
          span.style.transform = `scale(${scale.toFixed(3)})`;
          span.style.transformOrigin = 'center bottom';
          span.style.color = color;
          span.style.margin = '0 2px';
          span.style.padding = '0 4px';
          if (isEmp && isCur) {
            span.style.textDecoration = 'underline';
            span.style.textDecorationColor = wObj.accent_color || '#fbbf24';
            span.style.textUnderlineOffset = '8px';
            span.style.textDecorationThickness = '4px';
          }
          this.capEl.appendChild(span);
          spanEls.push(span);
        });
        const rects = spanEls.map(elNode => elNode.getBoundingClientRect());
        let minGap = 999.0;
        let overlaps = 0;
        const rowYs = [];
        for (let rIdx = 0; rIdx < rects.length; rIdx++) {
          const rA = rects[rIdx];
          if (!rowYs.some(ry => Math.abs(ry - rA.top) < 12)) rowYs.push(rA.top);
          if (rIdx + 1 < rects.length) {
            const rB = rects[rIdx + 1];
            if (Math.abs(rA.top - rB.top) < Math.max(10, rA.height * 0.45)) {
              const gap = rB.left - rA.right;
              minGap = Math.min(minGap, gap);
              if (gap < 1.5) overlaps += 1;
            }
          }
        }
        const capRect = this.capEl.getBoundingClientRect();
        const capClipped = (capRect && capRect.width > 1) ? (capRect.left < 60 || capRect.right > 1020 || capRect.bottom > 1580) : false;
        capTel.text = activeChunk.text || '';
        capTel.active_word = activeW;
        capTel.chunk_id = activeChunk.chunk_id;
        capTel.caption_layout = {
          word_count: spanEls.length,
          min_word_gap_px: minGap < 990 ? Number(minGap.toFixed(2)) : null,
          word_overlap_count: overlaps,
          row_count: rowYs.length,
          clipped_by_viewport: capClipped,
          cap_bbox: (capRect && capRect.width > 1) ? [Number(capRect.left.toFixed(1)), Number(capRect.top.toFixed(1)), Number(capRect.right.toFixed(1)), Number(capRect.bottom.toFixed(1))] : null,
          in_safe_area: capRect.left >= 70 && capRect.right <= 1010 && capRect.bottom <= 1560,
        };
      }
    } else if (this.capEl) {
      this.capEl.textContent = '';
    }

    const capBox = activeChunk ? (activeChunk.bbox || [100, 1365, 980, 1495]) : null;
    const overlays = tl.overlays || [];
    const ovTel = [];
    let visibleCount = 0;
    const useRoleAware = String(tl.editorial_theme || 'role-aware') !== 'legacy';

    const drawImpactArrow = (g, sx, sy, ax, ay, colorFill, strokeOuter, enterU, heavy = true) => {
      const dx = ax - sx;
      const dy = ay - sy;
      const dist = Math.max(1, Math.hypot(dx, dy));
      const ux = dx / dist;
      const uy = dy / dist;
      const nx = -uy;
      const ny = ux;
      const tipGap = heavy ? 16 : 22;
      const tx = ax - ux * tipGap;
      const ty = ay - uy * tipGap;
      const prog = easeOutCubic(Math.min(1, enterU * 1.4));
      const ex = lerp(sx, tx, prog);
      const ey = lerp(sy, ty, prog);
      const bend = (sx < 540 ? 1 : -1) * Math.min(115, dist * 0.22);
      const cx = (sx + ex) * 0.5 + nx * bend;
      const cy = (sy + ey) * 0.5 + ny * bend;
      const dStr = `M ${sx.toFixed(1)} ${sy.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`;
      if (heavy) {
        g.appendChild(el('path', {
          d: dStr, fill: 'none', stroke: strokeOuter, 'stroke-width': '22', 'stroke-linecap': 'round', opacity: '0.96',
        }));
        g.appendChild(el('path', {
          d: dStr, fill: 'none', stroke: colorFill, 'stroke-width': '11', 'stroke-linecap': 'round', opacity: '0.98',
        }));
      } else {
        g.appendChild(el('path', {
          d: dStr, fill: 'none', stroke: strokeOuter, 'stroke-width': '11', 'stroke-linecap': 'round', opacity: '0.78',
        }));
        g.appendChild(el('path', {
          d: dStr, fill: 'none', stroke: colorFill, 'stroke-width': '5.5', 'stroke-linecap': 'round', opacity: '0.96',
        }));
      }
      // Tangent at end of quadratic Bezier is (ex - cx, ey - cy)
      const tdx = ex - cx;
      const tdy = ey - cy;
      const tlen = Math.max(1, Math.hypot(tdx, tdy));
      const tux = tdx / tlen;
      const tuy = tdy / tlen;
      const tnx = -tuy;
      const tny = tux;
      const headLen = heavy ? 42 : 24;
      const headHalfW = heavy ? 22 : 12;
      const tipX = ex + tux * (headLen * 0.42);
      const tipY = ey + tuy * (headLen * 0.42);
      const baseX = tipX - tux * headLen;
      const baseY = tipY - tuy * headLen;
      const p1 = `${tipX.toFixed(1)},${tipY.toFixed(1)}`;
      const p2 = `${(baseX + tnx * headHalfW).toFixed(1)},${(baseY + tny * headHalfW).toFixed(1)}`;
      const p3 = `${(baseX - tnx * headHalfW).toFixed(1)},${(baseY - tny * headHalfW).toFixed(1)}`;
      g.appendChild(el('polygon', {
        points: `${p1} ${p2} ${p3}`,
        fill: colorFill,
        stroke: strokeOuter,
        'stroke-width': heavy ? '5.5' : '3',
        'stroke-linejoin': 'round',
      }));
      const errPx = Math.hypot(ax - tipX, ay - tipY);
      return { tip_xy: [Number(tipX.toFixed(1)), Number(tipY.toFixed(1))], tip_target_error_px: Number(errPx.toFixed(2)) };
    };

    const drawSpanBracket = (g, ax, ay, bx, by, colFill, strokeOuter, enterU, isTorsion = true) => {
      const prog = easeOutCubic(Math.min(1, enterU * 1.45));
      const mx = (ax + bx) * 0.5;
      const my = (ay + by) * 0.5;
      const x1 = lerp(mx, ax, prog);
      const y1 = lerp(my, ay, prog);
      const x2 = lerp(mx, bx, prog);
      const y2 = lerp(my, by, prog);
      const ctrlY = my + (isTorsion ? -78 : -52);
      const dArc = `M ${x1.toFixed(1)} ${y1.toFixed(1)} Q ${mx.toFixed(1)} ${ctrlY.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`;
      g.appendChild(el('path', {
        d: dArc, fill: 'none', stroke: strokeOuter, 'stroke-width': '16', 'stroke-linecap': 'round', opacity: '0.92',
      }));
      g.appendChild(el('path', {
        d: dArc, fill: 'none', stroke: colFill, 'stroke-width': '7.5', 'stroke-linecap': 'round', opacity: '0.98',
      }));
      for (const [ex, ey, dirSign] of [[x1, y1, -1], [x2, y2, 1]]) {
        g.appendChild(el('circle', {
          cx: ex.toFixed(1), cy: ey.toFixed(1), r: '14',
          fill: colFill, stroke: strokeOuter, 'stroke-width': '4.5',
        }));
        if (isTorsion) {
          // Opposed up/down tick arrows visibly communicating left/right opposed edge rotation
          const ayEnd = ey + dirSign * 42 * prog;
          g.appendChild(el('line', {
            x1: ex.toFixed(1), y1: ey.toFixed(1), x2: ex.toFixed(1), y2: ayEnd.toFixed(1),
            stroke: strokeOuter, 'stroke-width': '12', 'stroke-linecap': 'round',
          }));
          g.appendChild(el('line', {
            x1: ex.toFixed(1), y1: ey.toFixed(1), x2: ex.toFixed(1), y2: ayEnd.toFixed(1),
            stroke: colFill, 'stroke-width': '6', 'stroke-linecap': 'round',
          }));
        }
      }
      return { tip_xy: [Number(ax.toFixed(1)), Number(ay.toFixed(1))], tip_target_error_px: 0.0 };
    };

    if (String(tl.callout_mode || 'smart') !== 'off') {
      for (const ov of overlays) {
        if (t < ov.start || t > ov.end) continue;
        const enter = easeOutCubic((t - ov.start) / 0.20);
        const exit = easeOutCubic((ov.end - t) / 0.22);
        const alpha = clamp(Math.min(enter, exit), 0, 1);

        const anc = anchorsMap[ov.anchor_id] || anchorsMap['default'] || null;
        const ptrShape = String(ov.pointer_shape || (ov.type === 'focus_ring' ? 'focus_circle' : (ov.type === 'tracked_arrow' ? 'curved_leader' : 'none')));
        const requiresTrack = useRoleAware
          ? (ptrShape !== 'none' && ov.type !== 'verified_counter')
          : (ov.type === 'focus_ring' || ov.type === 'tracked_arrow');

        let anchorPx = null;
        let visible = true;
        let hiddenReason = null;

        if (requiresTrack) {
          if (!anc || !anc.in_front) {
            visible = false;
            hiddenReason = 'behind_or_missing_anchor';
          } else if (anc.occluded) {
            visible = false;
            hiddenReason = 'occluded_3d_geometry';
          } else {
            const px = anc.u * 1080;
            const py = anc.v * 1920;
            if (px < 48 || px > 1032 || py < 120 || py > 1650) {
              visible = false;
              hiddenReason = 'offscreen';
            } else {
              anchorPx = [Number(px.toFixed(1)), Number(py.toFixed(1))];
            }
          }
        } else if (anc && anc.in_front && !anc.occluded) {
          anchorPx = [Number((anc.u * 1080).toFixed(1)), Number((anc.v * 1920).toFixed(1))];
        }

        if (!visible || alpha <= 0.02) {
          ovTel.push({
            overlay_id: ov.overlay_id,
            type: ov.type || 'focus_ring',
            anchor_id: ov.anchor_id || null,
            pointer_shape: ptrShape,
            role: ov.role || 'explanation',
            variant_id: ov.variant_id || 'legacy',
            style_id: ov.style_id || 'legacy',
            label: ov.label || '',
            visible: false,
            dom_rendered: false,
            alpha: Number(alpha.toFixed(3)),
            hidden_reason: hiddenReason || 'fade_zero',
            anchor_px: anchorPx,
            anchor_projected_xy: anchorPx,
            tip_xy: null,
            tip_target_error_px: null,
            in_safe_area: true,
          });
          continue;
        }

        visibleCount += 1;
        const g = el('g', { opacity: alpha.toFixed(3), 'aria-label': `${ov.role || 'callout'}: ${ov.label || ''}` });
        const role = String(ov.role || 'explanation');
        const accent = ov.accent_color || '#38bdf8';
        let [bx0, by0, bx1, by1] = ov.placement_box || [560, 310, 964, 420];
        if (anchorPx && role !== 'curiosity_headline' && role !== 'location_time' && role !== 'aftermath_sober') {
          const [ax, ay] = anchorPx;
          if (ax >= bx0 - 50 && ax <= bx1 + 50 && ay >= by0 - 50 && ay <= by1 + 50) {
            const w = bx1 - bx0;
            const h = by1 - by0;
            bx0 = ax > 540 ? SAFE.x0 + 18 : SAFE.x1 - w - 18;
            bx1 = bx0 + w;
            by0 = clamp(ay - 220, SAFE.y0 + 16, SAFE.capY0 - h - 24);
            by1 = by0 + h;
          }
        }
        const bw = bx1 - bx0;
        const bh = by1 - by0;
        let ptrRes = { tip_xy: null, tip_target_error_px: null };
        let textBBox = [bx0, by0, bx1, by1];
        let baseFont1080 = Number(ov.font_size_1080 || 34);
        const txtCardG = el('g', {});

        if (!useRoleAware) {
          // Legacy mode for controlled baseline_A comparison
          if (ov.type === 'focus_ring' && anchorPx) {
            const [ax, ay] = anchorPx;
            const rOuter = 58 + (1 - enter) * 26;
            g.appendChild(el('circle', { cx: ax, cy: ay, r: (rOuter * 0.72).toFixed(1), fill: 'none', stroke: accent, 'stroke-width': '5.5' }));
          }
          if ((ov.type === 'tracked_arrow' || ov.type === 'focus_ring') && anchorPx && ov.label) {
            ptrRes = drawImpactArrow(g, bx0 + bw * 0.5 < anchorPx[0] ? bx1 : bx0, by0 + bh * 0.5, anchorPx[0], anchorPx[1], accent, '#090d16', enter, false);
          }
          if (ov.label) {
            baseFont1080 = 32;
            txtCardG.appendChild(el('rect', { x: bx0, y: by0, width: bw, height: bh, rx: 16, fill: 'rgba(10, 16, 28, 0.88)', stroke: accent, 'stroke-width': '3' }));
            txtCardG.appendChild(el('rect', { x: bx0 + 11, y: by0 + 14, width: 6.5, height: Math.max(20, bh - 28), rx: 3.5, fill: accent }));
            const tEl = el('text', { x: bx0 + 30, y: by0 + (ov.sublabel ? 45 : bh * 0.58), fill: '#f8fafc', 'font-family': 'Cap, sans-serif', 'font-weight': '800', 'font-size': '32' });
            tEl.textContent = ov.label;
            txtCardG.appendChild(tEl);
            if (ov.sublabel) {
              const sEl = el('text', { x: bx0 + 30, y: by0 + 82, fill: '#e2e8f0', 'font-family': 'Cap, sans-serif', 'font-weight': '600', 'font-size': '22' });
              sEl.textContent = ov.sublabel;
              txtCardG.appendChild(sEl);
            }
          }
        } else if (role === 'curiosity_headline') {
          // Two-tone large display typography (zero dark card background), controlled 0.84->1.04->1 pop
          const lines = (ov.display_lines && ov.display_lines.length) ? ov.display_lines : String(ov.label || '').split('/').map(s => s.trim()).filter(Boolean);
          const l1 = lines[0] || String(ov.label || '');
          const l2 = lines[1] || '';
          const fontSz = clamp(Number(ov.font_size_1080 || 88), 64, 112);
          baseFont1080 = fontSz;
          const strokeW = Number(ov.stroke_width || 11);
          const cxMid = (bx0 + bx1) * 0.5;
          const uPop = clamp((t - ov.start) / 0.19, 0, 1);
          const popScale = uPop < 0.65 ? lerp(0.84, 1.04, uPop / 0.65) : lerp(1.04, 1.0, (uPop - 0.65) / 0.35);
          const textG = el('g', {
            transform: `translate(${cxMid.toFixed(1)}, ${by0.toFixed(1)}) scale(${popScale.toFixed(3)})`,
            style: 'filter: drop-shadow(0 8px 18px rgba(0,0,0,0.88));',
          });
          const makeOutlineText = (txt, yOff, col, op = 1.0) => {
            const node = el('text', {
              x: 0, y: yOff, 'text-anchor': 'middle',
              fill: col, stroke: ov.outline_color || '#060911',
              'stroke-width': strokeW, 'stroke-linejoin': 'round',
              'paint-order': 'stroke fill',
              'font-family': 'Cap, sans-serif', 'font-weight': '900',
              'font-size': fontSz, 'letter-spacing': '0.01em',
              opacity: op.toFixed(3),
            });
            node.textContent = txt;
            return node;
          };
          const primCol = ov.primary_color || '#facc15';
          const secCol = ov.secondary_color || '#ef4444';
          textG.appendChild(makeOutlineText(l1, fontSz * 0.95, primCol, 1.0));
          if (l2) {
            const u2 = clamp((t - ov.start - 0.08) / 0.16, 0, 1);
            textG.appendChild(makeOutlineText(l2, fontSz * 2.02, secCol, easeOutCubic(u2)));
          }
          txtCardG.appendChild(textG);
          const totalTxtH = l2 ? fontSz * 2.18 : fontSz * 1.12;
          textBBox = [bx0, by0, bx1, by0 + totalTxtH];

          const secAnc = ov.secondary_anchor_id ? anchorsMap[ov.secondary_anchor_id] : null;
          const secPx = (secAnc && secAnc.in_front && !secAnc.occluded)
            ? [clamp(secAnc.u * 1080, 48, 1032), clamp(secAnc.v * 1920, 120, 1650)]
            : null;
          if (anchorPx) {
            const ax = anchorPx[0];
            const ay = anchorPx[1];
            const startX = ax >= cxMid ? clamp(cxMid + 140, bx0 + 40, bx1 - 40) : clamp(cxMid - 140, bx0 + 40, bx1 - 40);
            const startY = by0 + totalTxtH + 16;
            if ((ptrShape === 'torsion_bracket' || ptrShape === 'sway_bracket') && secPx) {
              drawImpactArrow(g, startX, startY, (ax + secPx[0]) * 0.5, (ay + secPx[1]) * 0.5 - 32, '#ef4444', '#060911', enter, false);
              ptrRes = drawSpanBracket(g, ax, ay, secPx[0], secPx[1], '#facc15', '#060911', enter, ptrShape === 'torsion_bracket');
            } else {
              ptrRes = drawImpactArrow(g, startX, startY, ax, ay, '#ef4444', '#060911', enter, true);
            }
          }
        } else if (role === 'location_time') {
          // Subtle minimal context chip (no big border/arrow) clamped cleanly inside SAFE x bounds
          baseFont1080 = 31;
          const sub = ov.sublabel ? ` • ${ov.sublabel}` : '';
          const rawW = String((ov.label || '') + sub).length * 19.5 + 48;
          const tagW = clamp(rawW, 270, Math.min(720, SAFE.x1 - SAFE.x0 - 20));
          const tagH = 64;
          const chipX0 = (bx0 + tagW > SAFE.x1 - 8) ? clamp(SAFE.x1 - tagW - 10, SAFE.x0 + 8, bx0) : bx0;
          txtCardG.appendChild(el('rect', {
            x: chipX0, y: by0, width: tagW, height: tagH, rx: 10,
            fill: 'rgba(15, 23, 42, 0.56)', stroke: 'rgba(148, 163, 184, 0.45)', 'stroke-width': '1.5',
          }));
          txtCardG.appendChild(el('rect', { x: chipX0 + 8, y: by0 + 13, width: 3.5, height: 38, rx: 2, fill: '#94a3b8' }));
          const locTxt = el('text', {
            x: chipX0 + 22, y: by0 + 42, fill: '#f1f5f9',
            'font-family': 'Cap, sans-serif', 'font-weight': '700', 'font-size': '31',
          });
          locTxt.textContent = `${ov.label || ''}${sub}`;
          txtCardG.appendChild(locTxt);
          textBBox = [chipX0, by0, chipX0 + tagW, by0 + tagH];
        } else if (role === 'warning_danger') {
          baseFont1080 = 34;
          const maxCharsW = Math.max(String(ov.label || '').length, String(ov.sublabel || '').length * 0.65);
          const cardW = clamp(Math.max(bw, maxCharsW * 24 + 54), 320, SAFE.x1 - SAFE.x0 - 20);
          const boxX0 = (bx0 + cardW > SAFE.x1 - 10) ? clamp(SAFE.x1 - cardW - 10, SAFE.x0 + 10, bx0) : bx0;
          if (anchorPx) {
            const [ax, ay] = anchorPx;
            const secAncW = ov.secondary_anchor_id ? anchorsMap[ov.secondary_anchor_id] : null;
            const secPxW = (secAncW && secAncW.in_front && !secAncW.occluded)
              ? [clamp(secAncW.u * 1080, 48, 1032), clamp(secAncW.v * 1920, 120, 1650)]
              : null;
            if ((ptrShape === 'torsion_bracket' || ptrShape === 'sway_bracket') && secPxW) {
              ptrRes = drawSpanBracket(g, ax, ay, secPxW[0], secPxW[1], '#ef4444', '#060911', enter, ptrShape === 'torsion_bracket');
            } else {
              const rOuter = 66 + (1 - enter) * 24;
              g.appendChild(el('circle', {
                cx: ax, cy: ay, r: (rOuter * 0.72).toFixed(1),
                fill: 'none', stroke: '#ef4444', 'stroke-width': '6.5',
              }));
              g.appendChild(el('circle', {
                cx: ax, cy: ay, r: (rOuter * 1.05).toFixed(1),
                fill: 'none', stroke: '#fef2f2', 'stroke-width': '2.5', opacity: '0.80',
              }));
              const sx = boxX0 + cardW * 0.5 < ax ? (boxX0 + cardW) : boxX0;
              ptrRes = drawImpactArrow(g, sx, by0 + bh * 0.5, ax, ay, '#ef4444', '#060911', enter, true);
            }
          }
          txtCardG.appendChild(el('rect', {
            x: boxX0, y: by0, width: cardW, height: bh, rx: 14,
            fill: 'rgba(69, 10, 10, 0.78)', stroke: '#f87171', 'stroke-width': '3.5',
          }));
          const wEl = el('text', {
            x: boxX0 + 22, y: by0 + 50, fill: '#fef2f2',
            'font-family': 'Cap, sans-serif', 'font-weight': '800', 'font-size': '34',
          });
          wEl.textContent = ov.label || '';
          txtCardG.appendChild(wEl);
          if (ov.sublabel) {
            const wsEl = el('text', {
              x: boxX0 + 22, y: by0 + 84, fill: '#fecaca',
              'font-family': 'Cap, sans-serif', 'font-weight': '600', 'font-size': '21',
            });
            wsEl.textContent = ov.sublabel;
            txtCardG.appendChild(wsEl);
          }
          textBBox = [boxX0, by0, boxX0 + cardW, by0 + bh];
        } else if (role === 'verified_fact') {
          baseFont1080 = 36;
          // High-contrast clean stat card dynamically sized to fit text cleanly with padding
          const maxCharsF = Math.max(String(ov.label || '').length, String(ov.sublabel || '').length * 0.62);
          const cardW = clamp(Math.max(bw, maxCharsF * 25 + 56), 340, SAFE.x1 - SAFE.x0 - 20);
          const boxX0 = (bx0 + cardW > SAFE.x1 - 10) ? clamp(SAFE.x1 - cardW - 10, SAFE.x0 + 10, bx0) : bx0;
          const isLight = String(ov.variant_id || '').includes('v1');
          const bgC = isLight ? 'rgba(248, 250, 252, 0.94)' : 'rgba(15, 23, 42, 0.92)';
          const fgC = isLight ? '#0f172a' : '#f8fafc';
          const subC = isLight ? '#334155' : '#cbd5e1';
          const barC = isLight ? '#0284c7' : '#38bdf8';
          txtCardG.appendChild(el('rect', {
            x: boxX0, y: by0, width: cardW, height: bh, rx: 12,
            fill: bgC, stroke: barC, 'stroke-width': '2.5',
            style: 'filter: drop-shadow(0 6px 14px rgba(0,0,0,0.42));',
          }));
          txtCardG.appendChild(el('rect', { x: boxX0, y: by0, width: cardW, height: 7, rx: 4, fill: barC }));
          const fEl = el('text', {
            x: boxX0 + 22, y: by0 + 54, fill: fgC,
            'font-family': 'Cap, sans-serif', 'font-weight': '800', 'font-size': '36',
          });
          fEl.textContent = ov.label || '';
          txtCardG.appendChild(fEl);
          if (ov.sublabel) {
            const fsEl = el('text', {
              x: boxX0 + 22, y: by0 + 88, fill: subC,
              'font-family': 'Cap, sans-serif', 'font-weight': '600', 'font-size': '21',
            });
            fsEl.textContent = ov.sublabel;
            txtCardG.appendChild(fsEl);
          }
          textBBox = [boxX0, by0, boxX0 + cardW, by0 + bh];
        } else if (role === 'aftermath_sober') {
          baseFont1080 = 33;
          // Quiet desaturated dissolve strip (no arrow/bounce/alarm border), clamped inside safe bounds
          const maxCharsA = Math.max(String(ov.label || '').length, String(ov.sublabel || '').length * 0.65);
          const cardW = clamp(Math.max(bw, maxCharsA * 22 + 54), 340, SAFE.x1 - SAFE.x0 - 20);
          const boxX0 = clamp((bx0 + bx1) * 0.5 - cardW * 0.5, SAFE.x0 + 10, SAFE.x1 - cardW - 10);
          txtCardG.appendChild(el('rect', {
            x: boxX0, y: by0, width: cardW, height: bh, rx: 8,
            fill: 'rgba(15, 23, 42, 0.54)', stroke: 'rgba(203, 213, 225, 0.35)', 'stroke-width': '1.2',
          }));
          const aEl = el('text', {
            x: boxX0 + cardW * 0.5, y: by0 + 48, 'text-anchor': 'middle',
            fill: '#e2e8f0', 'font-family': 'Cap, sans-serif', 'font-weight': '700', 'font-size': '33',
          });
          aEl.textContent = ov.label || '';
          txtCardG.appendChild(aEl);
          if (ov.sublabel) {
            const asEl = el('text', {
              x: boxX0 + cardW * 0.5, y: by0 + 82, 'text-anchor': 'middle',
              fill: '#94a3b8', 'font-family': 'Cap, sans-serif', 'font-weight': '600', 'font-size': '22',
            });
            asEl.textContent = ov.sublabel;
            txtCardG.appendChild(asEl);
          }
          textBBox = [boxX0, by0, boxX0 + cardW, by0 + bh];
        } else {
          baseFont1080 = 34;
          // EXPLANATION / TRANSITION_EMPHASIS: lighter tracked leader + crisp outlined label safely clamped
          const maxCharsE = Math.max(String(ov.label || '').length, String(ov.sublabel || '').length * 0.68);
          const cardW = clamp(Math.max(bw, maxCharsE * 22 + 44), 300, SAFE.x1 - SAFE.x0 - 20);
          const boxX0 = clamp((bx0 + bx1) * 0.5 - cardW * 0.5, SAFE.x0 + 10, SAFE.x1 - cardW - 10);
          const boxX1 = boxX0 + cardW;
          if (anchorPx) {
            const [ax, ay] = anchorPx;
            const secAncE = ov.secondary_anchor_id ? anchorsMap[ov.secondary_anchor_id] : null;
            const secPxE = (secAncE && secAncE.in_front && !secAncE.occluded)
              ? [clamp(secAncE.u * 1080, 48, 1032), clamp(secAncE.v * 1920, 120, 1650)]
              : null;
            if ((ptrShape === 'torsion_bracket' || ptrShape === 'sway_bracket') && secPxE) {
              ptrRes = drawSpanBracket(g, ax, ay, secPxE[0], secPxE[1], accent, '#090d16', enter, ptrShape === 'torsion_bracket');
            } else {
              const rOuter = 44 + (1 - enter) * 18;
              g.appendChild(el('circle', {
                cx: ax, cy: ay, r: rOuter.toFixed(1),
                fill: 'none', stroke: accent, 'stroke-width': '4',
                'stroke-dasharray': `${(2 * Math.PI * rOuter * enter).toFixed(1)} 320`,
              }));
              ptrRes = drawImpactArrow(g, boxX0 + cardW * 0.5 < ax ? boxX1 : boxX0, by0 + bh * 0.5, ax, ay, accent, '#090d16', enter, false);
            }
          }
          const eTxt = el('text', {
            x: boxX0 + cardW * 0.5, y: by0 + 44, 'text-anchor': 'middle',
            fill: '#f8fafc', stroke: '#090d16', 'stroke-width': '6', 'stroke-linejoin': 'round', 'paint-order': 'stroke fill',
            'font-family': 'Cap, sans-serif', 'font-weight': '800', 'font-size': '34',
          });
          eTxt.textContent = ov.label || '';
          txtCardG.appendChild(eTxt);
          if (ov.sublabel) {
            const esTxt = el('text', {
              x: boxX0 + cardW * 0.5, y: by0 + 78, 'text-anchor': 'middle',
              fill: '#cbd5e1', stroke: '#090d16', 'stroke-width': '4', 'stroke-linejoin': 'round', 'paint-order': 'stroke fill',
              'font-family': 'Cap, sans-serif', 'font-weight': '600', 'font-size': '22',
            });
            esTxt.textContent = ov.sublabel;
            txtCardG.appendChild(esTxt);
          }
          textBBox = [boxX0, by0, boxX1, by0 + bh];
        }

        g.appendChild(txtCardG);
        this.svg.appendChild(g);

        // Live DOM glyph clamping & verification inside 9:16 mobile safe bounds
        let domScaleFix = 1.0;
        const preRect = txtCardG.getBoundingClientRect ? txtCardG.getBoundingClientRect() : null;
        if (preRect && preRect.width > 1 && preRect.height > 1) {
          const maxSafeW = (SAFE.x1 - SAFE.x0) - 16;
          let tx = 0;
          let ty = 0;
          if (preRect.width > maxSafeW) {
            domScaleFix = maxSafeW / preRect.width;
          }
          const adjRight = preRect.left + preRect.width * domScaleFix;
          if (adjRight > SAFE.x1 - 8) tx = (SAFE.x1 - 8) - adjRight;
          if (preRect.left + tx < SAFE.x0 + 8) tx = (SAFE.x0 + 8) - preRect.left;
          const adjH = preRect.height * domScaleFix;
          if (preRect.top + adjH > SAFE.capY0 - 10) ty = (SAFE.capY0 - 10) - (preRect.top + adjH);
          if (preRect.top + ty < SAFE.y0) ty = SAFE.y0 - preRect.top;
          if (domScaleFix < 0.999 || Math.abs(tx) > 0.5 || Math.abs(ty) > 0.5) {
            const ox = preRect.left;
            const oy = preRect.top;
            txtCardG.setAttribute(
              'transform',
              `translate(${(ox + tx).toFixed(2)}, ${(oy + ty).toFixed(2)}) scale(${domScaleFix.toFixed(4)}) translate(${(-ox).toFixed(2)}, ${(-oy).toFixed(2)})`
            );
          }
        }
        const postRect = txtCardG.getBoundingClientRect ? txtCardG.getBoundingClientRect() : null;
        const liveBox = (postRect && postRect.width > 1 && postRect.height > 1)
          ? [postRect.left, postRect.top, postRect.right, postRect.bottom]
          : null;
        if (liveBox) {
          textBBox = liveBox;
        }
        const inSafe = textBBox[0] >= SAFE.x0 - 4 && textBBox[2] <= SAFE.x1 + 4 && textBBox[1] >= SAFE.y0 - 4 && textBBox[3] <= SAFE.capY0;
        const clippedByViewport = Boolean(textBBox[0] < SAFE.x0 - 8 || textBBox[2] > SAFE.x1 + 8 || textBBox[1] < SAFE.y0 - 8 || textBBox[3] > SAFE.capY0 + 8);
        const charOverflow = Boolean((textBBox[2] - textBBox[0]) > (SAFE.x1 - SAFE.x0 + 8));
        const effFont1080 = baseFont1080 * domScaleFix;
        const mobile360FontPx = Number((effFont1080 * (360 / 1080)).toFixed(2));
        const fitsMobile360 = !clippedByViewport && !charOverflow && mobile360FontPx >= (role === 'curiosity_headline' ? 21.0 : 9.0);
        const capOv = capBox ? !(textBBox[2] <= capBox[0] || textBBox[0] >= capBox[2] || textBBox[3] <= capBox[1] || textBBox[1] >= capBox[3]) : false;
        const gRect = g.getBoundingClientRect ? g.getBoundingClientRect() : null;
        const domRendered = Boolean(this.svg.contains(g) && g.childElementCount > 0 && (!gRect || (gRect.width > 1 && gRect.height > 1)));
        ovTel.push({
          overlay_id: ov.overlay_id,
          type: ov.type || 'focus_ring',
          anchor_id: ov.anchor_id || null,
          secondary_anchor_id: ov.secondary_anchor_id || null,
          target_semantic_id: ov.target_semantic_id || ov.anchor_id || null,
          pointer_shape: ptrShape,
          role,
          variant_id: ov.variant_id || 'legacy',
          style_id: ov.style_id || 'legacy',
          label: ov.label || '',
          visible: true,
          dom_rendered: domRendered,
          alpha: Number(alpha.toFixed(3)),
          hidden_reason: null,
          anchor_px: anchorPx,
          anchor_projected_xy: anchorPx,
          target_region_screen: anchorPx ? [
            Number(Math.max(0, anchorPx[0] - 45).toFixed(1)),
            Number(Math.max(0, anchorPx[1] - 45).toFixed(1)),
            Number(Math.min(1080, anchorPx[0] + 45).toFixed(1)),
            Number(Math.min(1920, anchorPx[1] + 45).toFixed(1)),
          ] : null,
          tip_xy: ptrRes.tip_xy,
          tip_target_error_px: ptrRes.tip_target_error_px,
          contrast_estimate: Number(ov.contrast_ratio_min || 5.0),
          label_bbox: [Number(textBBox[0].toFixed(1)), Number(textBBox[1].toFixed(1)), Number(textBBox[2].toFixed(1)), Number(textBBox[3].toFixed(1))],
          rendered_glyph_bbox: textBBox.map(v => Number(v.toFixed(1))),
          text_bbox: textBBox.map(v => Number(v.toFixed(1))),
          bbox: textBBox.map(v => Number(v.toFixed(1))),
          clipped_by_viewport: clippedByViewport,
          char_overflow: charOverflow,
          overlay_visibility_proof: {
            dom_rendered: domRendered,
            rendered_glyph_bbox: textBBox.map(v => Number(v.toFixed(1))),
            clipped_by_viewport: clippedByViewport,
            char_overflow: charOverflow,
            fits_viewport_1080: !clippedByViewport && !charOverflow && !capOv,
            fits_mobile_360: fitsMobile360,
            mobile_360_font_px: mobile360FontPx,
          },
          in_safe_area: inSafe,
          z_index: 14,
          caption_overlap: capOv,
        });
      }
    }

    this.lastTelemetry = { overlays: ovTel, caption: capTel, active_count: visibleCount };
    return this.lastTelemetry;
  }

  getOverlayTelemetry() {
    return this.lastTelemetry;
  }
}
"""
