"""STEP 8 (Acceptance Tests F & G): Seeded Determinism, Serial vs Concurrent & Resource Quotas."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from director.assets import build_locked_engine_workspace
from director.build_storyboard import build_storyboard_and_bible
from director.parse_script import parse_script_and_build_voice
from director.preflight import check_disk_quota, find_browser_executable, run_preflight
from director.provenance_guard import ProvenanceGuard
from director.render_scene import render_stills_and_shots
from director.route_styles import route_and_lock_style


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestDeterminismAndResourceSafety(unittest.TestCase):
    def tearDown(self) -> None:
        ProvenanceGuard.deactivate()

    def test_disk_quota_guard_and_worker_cap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            # Asking for 999,999 GiB free space MUST fail cleanly
            ok, total_gb, free_gb = check_disk_quota(Path(td), min_free_gb=999_999.0)
            self.assertFalse(ok)
            self.assertGreater(total_gb, 0.0)
            self.assertGreater(free_gb, 0.0)

        pf = run_preflight(PROJECT_ROOT, requested_workers=16)
        self.assertLessEqual(pf.recommended_workers, 4)
        self.assertGreaterEqual(pf.recommended_workers, 1)

    def test_seeded_frame_hashes_and_serial_vs_concurrent_parity(self) -> None:
        browser_exe = find_browser_executable()
        self.assertIsNotNone(browser_exe, "Browser executable must exist for frame determinism test")
        render_mjs = PROJECT_ROOT / "director" / "render_node.mjs"
        kit_dir = PROJECT_ROOT / "vendor" / "claude-animation-skills" / "kit"

        with tempfile.TemporaryDirectory() as td:
            run_a = Path(td) / "run_serial"
            run_b = Path(td) / "run_concurrent"

            prompt = "/short-director --skill stick-figure Two quick steps build steady focus. Short breaks protect memory."

            # Build deterministic workspace A (serial workers=1)
            dec_a, clean_a, _ = route_and_lock_style(PROJECT_ROOT, prompt, upstream_sha="test")
            ps_a = parse_script_and_build_voice(clean_a, "stick-figure", run_a, kit_dir)
            sb_a = build_storyboard_and_bible(ps_a, dec_a, run_a, fps=30, seed=1337)
            ep_a = build_locked_engine_workspace("stick-figure", PROJECT_ROOT, run_a, sb_a, ps_a)

            env = os.environ.copy()
            env["PLAYWRIGHT_CHROME_PATH"] = browser_exe

            # Seeded hash pass 1 vs pass 2 on frames 0..12
            r_hash_1 = subprocess.run(
                ["node", str(render_mjs), "hashes", ep_a["entry_html"], "30", "0", "12", "1", "metal"],
                capture_output=True, text=True, check=True, env=env,
            )
            r_hash_2 = subprocess.run(
                ["node", str(render_mjs), "hashes", ep_a["entry_html"], "30", "0", "12", "1", "metal"],
                capture_output=True, text=True, check=True, env=env,
            )
            h1 = json.loads([l for l in r_hash_1.stdout.splitlines() if l.startswith("{")][-1])["hashes"]
            h2 = json.loads([l for l in r_hash_2.stdout.splitlines() if l.startswith("{")][-1])["hashes"]
            self.assertEqual([x["sha256"] for x in h1], [x["sha256"] for x in h2], "Seeded renders must yield identical PNG SHA-256 frame hashes")

            # Serial (workers=1) vs Concurrent (workers=2) shot rendering comparison
            res_serial = render_stills_and_shots(
                PROJECT_ROOT, run_a, dec_a, sb_a, ep_a, browser_exe, webgl_backend="metal", workers=1, render_4k_mode="upscale"
            )
            ProvenanceGuard.deactivate()

            dec_b, clean_b, _ = route_and_lock_style(PROJECT_ROOT, prompt, upstream_sha="test")
            ps_b = parse_script_and_build_voice(clean_b, "stick-figure", run_b, kit_dir)
            sb_b = build_storyboard_and_bible(ps_b, dec_b, run_b, fps=30, seed=1337)
            ep_b = build_locked_engine_workspace("stick-figure", PROJECT_ROOT, run_b, sb_b, ps_b)
            res_conc = render_stills_and_shots(
                PROJECT_ROOT, run_b, dec_b, sb_b, ep_b, browser_exe, webgl_backend="metal", workers=2, render_4k_mode="upscale"
            )

            self.assertEqual(res_serial["total_frames"], res_conc["total_frames"])
            for sa, sb in zip(res_serial["shots"], res_conc["shots"]):
                self.assertEqual(sa["frames"], sb["frames"])
                self.assertEqual(sa["bytes"], sb["bytes"], f"Encoded deterministic shot byte size mismatch on {sa['shot_id']}")

            # Verify owned temp cleanup deleted `<run>/tmp` without touching shared `kit/vendor/gsap.min.js`
            self.assertFalse((run_a / "tmp").exists())
            self.assertTrue((kit_dir / "vendor" / "gsap.min.js").exists())


if __name__ == "__main__":
    unittest.main()
