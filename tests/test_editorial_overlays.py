"""Verification Tests for R2/R3: Kinetic Captions, 3D Tracked Overlays, WebGL Occlusion & Traps (N4-N9, N16)."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from director.assets import build_locked_engine_workspace
from director.build_storyboard import build_storyboard_and_bible
from director.editorial_overlay import (
    OverlaySafetyError,
    build_editorial_timeline,
    plan_kinetic_captions,
    validate_overlay_plan,
)
from director.parse_script import parse_script_and_build_voice
from director.preflight import find_browser_executable
from director.provenance_guard import ProvenanceGuard
from director.retention_qa import audit_annotation_tracking, audit_editorial_fatigue, audit_overlay_render
from director.route_styles import route_and_lock_style


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"


class TestEditorialOverlays(unittest.TestCase):
    def tearDown(self) -> None:
        ProvenanceGuard.deactivate()

    def test_negative_traps_n4_n5_n6_n9_n16(self) -> None:
        words = [{"w": f"w{i}", "s": i * 0.2, "e": (i + 1) * 0.2, "line": 0} for i in range(6)]
        # N4: Chunk size > 4 or caption leaving safe area triggers fatigue/safety fail
        bad_tl_chunk = {
            "caption_chunks": [{"chunk_id": "c0", "start": 0.0, "end": 1.2, "words": words, "bbox": [100, 1365, 980, 1485]}],
            "overlays": [],
            "free_screen_ratio": 1.0,
        }
        self.assertEqual(audit_editorial_fatigue(bad_tl_chunk)["status"], "FAIL")

        # N5: Simultaneous overlays > 2 rejected
        bad_spam = {
            "caption_chunks": [],
            "overlays": [
                {"overlay_id": "o1", "start": 1.0, "end": 3.0, "placement_box": [110, 250, 400, 340], "verified": True},
                {"overlay_id": "o2", "start": 1.0, "end": 3.0, "placement_box": [560, 250, 880, 340], "verified": True},
                {"overlay_id": "o3", "start": 1.5, "end": 2.8, "placement_box": [200, 420, 500, 510], "verified": True},
            ],
        }
        with self.assertRaises(OverlaySafetyError):
            validate_overlay_plan(bad_spam)

        # N6: Overlay box colliding with bottom caption band (`y1 > 1335`) rejected
        bad_cap_collide = {
            "caption_chunks": [],
            "overlays": [
                {"overlay_id": "o1", "start": 1.0, "end": 2.5, "placement_box": [150, 1280, 520, 1410], "verified": True},
            ],
        }
        with self.assertRaises(OverlaySafetyError):
            validate_overlay_plan(bad_cap_collide)

        # N9 & N16: Unverified counter / missing fact_source rejected
        bad_num = {
            "caption_chunks": [],
            "overlays": [
                {"overlay_id": "c1", "type": "verified_counter", "start": 1.0, "end": 2.5, "placement_box": [120, 260, 460, 360], "verified": False},
            ],
        }
        with self.assertRaises(OverlaySafetyError):
            validate_overlay_plan(bad_num)
        self.assertEqual(audit_editorial_fatigue(bad_num)["status"], "FAIL")

    def test_n7_n8_webgl_tracking_occlusion_and_overlay_pixel_diff_proof(self) -> None:
        browser_exe = find_browser_executable()
        self.assertIsNotNone(browser_exe)
        script = (
            "Why is there a tiny hole in every airplane window? "
            "An airplane window actually has three layers: outer pressure pane, middle fail-safe pane, and inner scratch pane. "
            "That tiny bleed hole equalizes cabin pressure and vents moisture so the window stays clear!"
        )
        prompt = f"/short-director --skill zach-d-films {script}"
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            run_on = td_p / "ov_on"
            run_off = td_p / "ov_off"
            run_off.mkdir(parents=True, exist_ok=True)

            dec, cleaned, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill="zach-d-films", upstream_sha="test")
            ps = parse_script_and_build_voice(cleaned, "zach-d-films", run_on, KIT_DIR, voice_mode="off")
            sb_on = build_storyboard_and_bible(ps, dec, run_on, fps=30, seed=42, caption_mode="kinetic", callout_mode="smart")
            ep_on = build_locked_engine_workspace("zach-d-films", PROJECT_ROOT, run_on, sb_on, ps)
            ProvenanceGuard.deactivate()

            dec2, cleaned2, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill="zach-d-films", upstream_sha="test")
            sb_off = build_storyboard_and_bible(ps, dec2, run_off, fps=30, seed=42, caption_mode="plain", callout_mode="off")
            ep_off = build_locked_engine_workspace("zach-d-films", PROJECT_ROOT, run_off, sb_off, ps)
            ProvenanceGuard.deactivate()

            tl_on = json.loads((run_on / "editorial_timeline.json").read_text(encoding="utf-8"))
            self.assertGreater(len(tl_on["overlays"]), 0)
            ov0 = tl_on["overlays"][0]
            t_mid = round(0.5 * (ov0["start"] + ov0["end"]), 3)

            render_mjs = PROJECT_ROOT / "director" / "render_node.mjs"
            env = os.environ.copy()
            env["PLAYWRIGHT_CHROME_PATH"] = browser_exe

            # Capture live trace telemetry at active overlay midpoints
            tr_res = subprocess.run(
                ["node", str(render_mjs), "trace", ep_on["entry_html"], f"{t_mid:.4f}", "1", "d3d11"],
                capture_output=True, text=True, check=True, env=env,
            )
            traces = json.loads([l for l in tr_res.stdout.splitlines() if l.startswith("{")][-1])["traces"]
            tr_audit = audit_annotation_tracking(traces, tl_on)
            self.assertEqual(tr_audit["status"], "PASS", f"Tracking telemetry failed: {tr_audit}")
            self.assertGreater(tr_audit["visible_tracked_count"], 0)

            # N7 trap: If tampered trace says overlay remained visible while occluded=True -> MUST FAIL
            tampered_traces = json.loads(json.dumps(traces))
            aid = ov0["anchor_id"]
            tampered_traces[0]["telemetry"]["anchors"][aid] = {"u": 0.5, "v": 0.5, "in_front": True, "occluded": True}
            for item in tampered_traces[0]["telemetry"]["overlay"]["overlays"]:
                if item["anchor_id"] == aid:
                    item["visible"] = True
            self.assertEqual(audit_annotation_tracking(tampered_traces, tl_on)["status"], "FAIL")

            # N8 proof: Rendered pixels WITH smart overlay differ cleanly inside overlay placement_box vs baseline OFF
            st_on = td_p / "st_on"
            st_off = td_p / "st_off"
            subprocess.run(
                ["node", str(render_mjs), "stills", ep_on["entry_html"], str(st_on), f"{t_mid:.3f}", "1", "d3d11"],
                check=True, capture_output=True, env=env,
            )
            subprocess.run(
                ["node", str(render_mjs), "stills", ep_off["entry_html"], str(st_off), f"{t_mid:.3f}", "1", "d3d11"],
                check=True, capture_output=True, env=env,
            )
            img_on = np.asarray(Image.open(st_on / f"still_{t_mid:.3f}.png").convert("RGB"), dtype=np.float32)
            img_off = np.asarray(Image.open(st_off / f"still_{t_mid:.3f}.png").convert("RGB"), dtype=np.float32)
            bx0, by0, bx1, by1 = [int(v) for v in ov0["placement_box"]]
            box_mad = float(np.mean(np.abs(img_on[by0:by1, bx0:bx1] - img_off[by0:by1, bx0:bx1])))
            self.assertGreater(box_mad, 4.0, f"N8 overlay pixel diff too small ({box_mad:.2f})")

            # Mobile & desktop kinetic caption flex word-spacing check across 320/360/390/1080 widths
            kit_nm = (PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit" / "node_modules").resolve()
            cap_test_js = f"""
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {{ createRequire }} from 'node:module';
const require = createRequire(import.meta.url);
const {{ chromium }} = require({json.dumps(str(kit_nm / 'playwright'))});

const workDir = {json.dumps(str(ep_on["work_dir"]))};
const MIME = {{ '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.woff2': 'font/woff2' }};
const server = http.createServer((req, res) => {{
  const rel = decodeURIComponent((req.url || '/').split('?')[0]).replace(/^\\/+/, '') || 'index.html';
  const fp = path.join(workDir, rel);
  fs.readFile(fp, (err, data) => {{
    if (err) {{ res.writeHead(404); res.end('not found'); return; }}
    res.writeHead(200, {{ 'Content-Type': MIME[path.extname(fp)] || 'application/octet-stream' }});
    res.end(data);
  }});
}});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const port = server.address().port;

const browser = await chromium.launch({{ executablePath: process.env.PLAYWRIGHT_CHROME_PATH, headless: true, args: ['--no-sandbox', '--use-gl=angle', '--use-angle=d3d11'] }});
const widths = [320, 360, 390, 1080];
const results = {{}};
try {{
  const page = await browser.newPage({{ viewport: {{ width: 1080, height: 1920 }} }});
  await page.goto(`http://127.0.0.1:${{port}}/index.html`, {{ waitUntil: 'load' }});
  await page.evaluate(() => window.SHORT_DIRECTOR_READY);
  await page.evaluate((t) => window.renderAtTime(t), {t_mid:.3f});
  const baseTel = await page.evaluate(() => window.__LAST_RENDER_TELEMETRY__);
  results['canvas_1080'] = baseTel?.overlay?.caption?.caption_layout || null;

  for (const vw of widths) {{
    await page.setViewportSize({{ width: vw, height: 1920 }});
    const probe = await page.evaluate(() => {{
      const cap = document.getElementById('cap');
      const spans = Array.from(cap.querySelectorAll('span'));
      const gaps = [];
      for (let i = 0; i + 1 < spans.length; i++) {{
        const a = spans[i].getBoundingClientRect();
        const b = spans[i + 1].getBoundingClientRect();
        if (Math.abs(a.top - b.top) < 12) gaps.push(b.left - a.right);
      }}
      const st = getComputedStyle(cap);
      return {{ display: st.display, columnGap: st.columnGap, minGap: gaps.length ? Math.min(...gaps) : 99, spanCount: spans.length }};
    }});
    results['w_' + vw] = probe;
  }}
}} finally {{
  await browser.close();
  server.close();
}}
console.log(JSON.stringify(results));
"""
            pw_res = subprocess.run(["node", "--input-type=module", "-e", cap_test_js], cwd=str(PROJECT_ROOT), capture_output=True, text=True, check=True, env=env)
            cap_rep = json.loads([l for l in pw_res.stdout.splitlines() if l.startswith("{")][-1])
            c_1080 = cap_rep["canvas_1080"]
            self.assertIsNotNone(c_1080)
            self.assertEqual(c_1080["word_overlap_count"], 0)
            if c_1080["min_word_gap_px"] is not None:
                self.assertGreaterEqual(c_1080["min_word_gap_px"], 3.0)
            for key in ("w_320", "w_360", "w_390", "w_1080"):
                self.assertEqual(cap_rep[key]["display"], "flex")
                self.assertGreaterEqual(cap_rep[key]["minGap"], 3.0)

            # Verify semantic multi-theme role metadata is exported in timeline
            self.assertEqual(tl_on.get("editorial_theme"), "role-aware")
            self.assertTrue(any(o.get("role") for o in tl_on["overlays"]))


if __name__ == "__main__":
    unittest.main()
