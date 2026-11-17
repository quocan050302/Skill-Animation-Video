"""Verification Tests for Deterministic Physical Motion Primitives & Continuity (G12-G14, N13-N15, N20-N22)."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from director.assets import build_locked_engine_workspace
from director.build_storyboard import build_storyboard_and_bible
from director.parse_script import parse_script_and_build_voice
from director.physical_motion import (
    PhysicalMotionSpecError,
    plan_contact_schedule,
    plan_motion_intent,
    plan_physics_telemetry,
    validate_motion_params,
)
from director.preflight import find_browser_executable
from director.provenance_guard import ProvenanceGuard
from director.route_styles import route_and_lock_style
from director.visual_storytelling_qa import audit_physical_and_character_telemetry


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"


class TestPhysicalMotion(unittest.TestCase):
    def tearDown(self) -> None:
        ProvenanceGuard.deactivate()

    def test_g12_g13_motion_planner_validation_and_contact_schedule(self) -> None:
        sh_tor = {"shot_id": "s04", "start": 10.0, "end": 14.5, "duration": 4.5, "procedural_generator": "zach3d:tacoma_torsion_twist_stage", "physical_action": "torsion_deck_twist"}
        sh_col = {"shot_id": "s06", "start": 20.0, "end": 25.0, "duration": 5.0, "procedural_generator": "zach3d:tacoma_collapse_plunge_stage", "physical_action": "span_collapse_plunge"}

        spec_t = plan_motion_intent(sh_tor, seed=42)
        spec_c = plan_motion_intent(sh_col, seed=42)
        self.assertEqual(spec_t["motion_type"], "torsion_span")
        self.assertEqual(spec_c["motion_type"], "staged_span_collapse")
        self.assertEqual(spec_t["fidelity_disclosure"], "stylized_illustrative")
        sched = plan_contact_schedule([sh_tor, sh_col], {})
        self.assertEqual(len(sched), 2)
        self.assertAlmostEqual(sched[1]["hit_time_rel_sec"], 5.0 * 0.38, places=2)

    def test_negative_traps_n13_n14_n15_n21_n22(self) -> None:
        # N15: collapse_onset_sec preceding torsion_onset_sec fails closed
        with self.assertRaises(PhysicalMotionSpecError):
            validate_motion_params({"duration_sec": 4.0, "torsion_onset_sec": 2.5, "collapse_onset_sec": 1.0})

        # N21: NaN parameters rejected
        with self.assertRaises(PhysicalMotionSpecError):
            validate_motion_params({"duration_sec": 4.0, "amplitude": float("nan")})

        sb = {
            "shots": [
                {"shot_id": "shot_03", "duration": 3.0, "procedural_generator": "zach3d:tacoma_torsion_twist_stage", "physical_action": "torsion_deck_twist"},
            ]
        }
        # N13/N14: Frozen vertex displacement (<0.03m) on claimed torsion shot MUST FAIL
        frozen_traces = [{"shot_id": "shot_03", "time_sec": 1.0, "telemetry": {"physical_motion": {"vertex_disp_max_m": 0.002, "deck_roll_span_rad": 0.0, "cables_attached": True}}}]
        self.assertEqual(audit_physical_and_character_telemetry(sb, raw_traces=frozen_traces)["status"], "FAIL")

        # N22: Detached suspender cables MUST FAIL
        bad_cables = [{"shot_id": "shot_03", "time_sec": 1.0, "telemetry": {"physical_motion": {"vertex_disp_max_m": 0.35, "deck_roll_span_rad": 0.28, "cables_attached": False}}}]
        self.assertEqual(audit_physical_and_character_telemetry(sb, raw_traces=bad_cables)["status"], "FAIL")

        # N21: NaN physics telemetry MUST FAIL
        nan_traces = [{"shot_id": "shot_03", "time_sec": 1.0, "telemetry": {"physical_motion": {"vertex_disp_max_m": float("nan")}}}]
        self.assertTrue(plan_physics_telemetry(nan_traces)["nan_detected"])

    def test_g14_n20_tacoma_webgl_bridge_deformation_and_out_of_order_seek_determinism(self) -> None:
        browser_exe = find_browser_executable()
        self.assertIsNotNone(browser_exe)
        script = (
            "In July 1940, the Tacoma Narrows Bridge ribboned across Puget Sound. "
            "Drivers saw the roadbed bend upward and bounce cars. "
            "Eight-foot solid plate girders caught crosswinds below. "
            "On November 7, 1940, the bridge started twisting violently until the center span broke free and plunged into Puget Sound."
        )
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td)
            prompt = f"/short-director --skill zach-d-films {script}"
            dec, cleaned, _ = route_and_lock_style(PROJECT_ROOT, prompt, cli_skill="zach-d-films", upstream_sha="test")
            ps = parse_script_and_build_voice(cleaned, "zach-d-films", rd, KIT_DIR, voice_mode="off")
            sb = build_storyboard_and_bible(ps, dec, rd, fps=30, seed=42, caption_mode="kinetic", callout_mode="smart")
            ep = build_locked_engine_workspace("zach-d-films", PROJECT_ROOT, rd, sb, ps)

            shots_js = (Path(ep["work_dir"]) / "src" / "shots.js").read_text(encoding="utf-8")
            self.assertIn("makeTacomaSuspensionBridgeRig", shots_js)

            kit_nm = (PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit" / "node_modules").resolve()
            sh_twist = next((s for s in sb["shots"] if "torsion" in str(s.get("procedural_generator") or "")), sb["shots"][min(3, len(sb["shots"]) - 1)])
            sh_col = next((s for s in sb["shots"] if "collapse" in str(s.get("procedural_generator") or "")), sb["shots"][-1])
            t_tw = round(0.5 * (sh_twist["start"] + sh_twist["end"]), 3)
            t_col_pre = round(sh_col["start"] + 0.15, 3)
            t_col_post = round(sh_col["start"] + max(0.8, sh_col["duration"] * 0.72), 3)

            seek_script = f"""
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {{ createRequire }} from 'node:module';
const require = createRequire(import.meta.url);
const {{ chromium }} = require({json.dumps(str(kit_nm / 'playwright'))});
const workDir = {json.dumps(str(ep['work_dir']))};
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
const angleBackend = process.platform === 'darwin' ? 'metal' : (process.platform === 'win32' ? 'd3d11' : 'swiftshader');
const browser = await chromium.launch({{ executablePath: process.env.PLAYWRIGHT_CHROME_PATH, headless: true, args: ['--no-sandbox', '--use-gl=angle', `--use-angle=${{angleBackend}}`] }});
const out = {{}};
try {{
  const page = await browser.newPage({{ viewport: {{ width: 1080, height: 1920 }} }});
  await page.goto(`http://127.0.0.1:${{port}}/index.html`, {{ waitUntil: 'load' }});
  await page.evaluate(() => window.SHORT_DIRECTOR_READY);

  // Forward pass
  for (const t of [{t_tw}, {t_col_pre}, {t_col_post}]) {{
    await page.evaluate(x => window.renderAtTime(x), t);
    const tel = await page.evaluate(() => window.__LAST_RENDER_TELEMETRY__);
    const buf = await page.screenshot({{ type: 'png' }});
    out['fwd_' + t] = {{ hash: crypto.createHash('sha256').update(buf).digest('hex'), phys: tel.physical_motion }};
  }}
  // Out-of-order seek back to torsion after visiting post-collapse (must match bit-for-bit!)
  for (const t of [{t_col_pre}, {t_tw}, {t_col_post}]) {{
    await page.evaluate(x => window.renderAtTime(x), t);
    const tel = await page.evaluate(() => window.__LAST_RENDER_TELEMETRY__);
    const buf = await page.screenshot({{ type: 'png' }});
    out['rev_' + t] = {{ hash: crypto.createHash('sha256').update(buf).digest('hex'), phys: tel.physical_motion }};
  }}
}} finally {{
  await browser.close();
  server.close();
}}
console.log(JSON.stringify(out));
"""
            env = os.environ.copy()
            env["PLAYWRIGHT_CHROME_PATH"] = browser_exe
            res = subprocess.run(["node", "--input-type=module", "-e", seek_script], cwd=str(PROJECT_ROOT), capture_output=True, text=True, check=True, env=env)
            data = json.loads([ln for ln in res.stdout.splitlines() if ln.startswith("{")][-1])

            for t in (t_tw, t_col_pre, t_col_post):
                self.assertEqual(data[f"fwd_{t}"]["hash"], data[f"rev_{t}"]["hash"], f"N20 out-of-order seek non-deterministic at t={t}")
            self.assertGreaterEqual(data[f"fwd_{t_tw}"]["phys"]["vertex_disp_max_m"], 0.12)
            self.assertTrue(data[f"fwd_{t_tw}"]["phys"]["cables_attached"])
            self.assertFalse(data[f"fwd_{t_col_pre}"]["phys"]["collapse_active"])
            self.assertTrue(data[f"fwd_{t_col_post}"]["phys"]["collapse_active"])


if __name__ == "__main__":
    unittest.main()
