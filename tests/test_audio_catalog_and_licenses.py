"""Unit & Negative Regression Tests for Audio Catalog, Read-Only QA Adapter, Licenses & SHA-256."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from director.audio_catalog import (
    AudioAsset,
    LicensePolicy,
    compute_file_sha256,
    discover_native_audio_assets,
    discover_qa_audio_assets,
    resolve_audio_asset,
    validate_audio_asset,
    write_audio_asset_manifest,
    write_credits_file,
)
from director.preflight import check_disk_quota, preflight_audio_assets, resolve_qa_audio_root


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _write_sine_wav(path: Path, sr: int = 48000, dur: float = 0.8, freq: float = 440.0, channels: int = 1) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(sr * dur), dtype=np.float32) / sr
    sig = 0.25 * np.sin(2.0 * np.pi * freq * t)
    if channels == 2:
        sig = np.stack([sig, sig * 0.9], axis=1)
    sf.write(str(path), sig, sr)
    return compute_file_sha256(path)


class TestAudioCatalogAndLicenses(unittest.TestCase):
    def test_a1_a2_native_and_qa_root_detection(self) -> None:
        native = discover_native_audio_assets(PROJECT_ROOT)
        self.assertGreaterEqual(len([a for a in native if a.asset_type == "music"]), 5)
        self.assertGreaterEqual(len([a for a in native if a.asset_type == "sfx"]), 10)
        for a in native:
            self.assertEqual(a.license_type, "procedural")
            self.assertNotIn("copyright-free", json.dumps(a.to_dict()).lower())

        # Missing explicit --qa-audio-root reports cleanly without crash
        with tempfile.TemporaryDirectory() as td:
            miss = Path(td) / "no_qa_here"
            qa_p, status, _ = resolve_qa_audio_root(PROJECT_ROOT, cli_qa_root=miss)
            self.assertIsNone(qa_p)
            self.assertEqual(status, "QA_LIBRARY_UNAVAILABLE")

            # Valid read-only QA fixture via SHORT_DIRECTOR_QA_ROOT env
            qa_root = Path(td) / "QA_Mock"
            (qa_root / "audio" / "music").mkdir(parents=True)
            old_env = os.environ.get("SHORT_DIRECTOR_QA_ROOT")
            try:
                os.environ["SHORT_DIRECTOR_QA_ROOT"] = str(qa_root)
                found, st2, _ = resolve_qa_audio_root(PROJECT_ROOT)
                self.assertEqual(found, qa_root.resolve())
                self.assertEqual(st2, "QA_LIBRARY_MOUNTED_READONLY")
            finally:
                if old_env is None:
                    os.environ.pop("SHORT_DIRECTOR_QA_ROOT", None)
                else:
                    os.environ["SHORT_DIRECTOR_QA_ROOT"] = old_env

    def test_a3_ccby_credits_cc0_provenance_and_missing_license_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            qa = Path(td) / "QA"
            fog = qa / "audio" / "music" / "external_dark_fog.wav"
            drops = qa / "audio" / "real_sfx" / "external_water_drops.wav"
            unlic = qa / "audio" / "real_sfx" / "mystery_unlicensed.wav"
            noncomm = qa / "audio" / "music" / "personal_only_track.wav"

            sha_fog = _write_sine_wav(fog, sr=44100, dur=1.2, freq=220.0, channels=2)
            sha_drops = _write_sine_wav(drops, sr=22050, dur=0.5, freq=880.0, channels=1)
            _ = _write_sine_wav(unlic, sr=48000, dur=0.4)
            sha_nc = _write_sine_wav(noncomm, sr=48000, dur=1.0)

            lic_dir = qa / "audio" / "licenses"
            lic_dir.mkdir(parents=True)
            credit_str = '"Dark Fog" Kevin MacLeod (incompetech.com) Licensed under Creative Commons: By Attribution 4.0 License http://creativecommons.org/licenses/by/4.0/'
            (lic_dir / "licenses.json").write_text(json.dumps({
                "assets": [
                    {
                        "filename": "external_dark_fog.wav",
                        "license_type": "cc-by-4.0",
                        "author": "Kevin MacLeod",
                        "title": "Dark Fog",
                        "source_url": "https://incompetech.com",
                        "license_url": "http://creativecommons.org/licenses/by/4.0/",
                        "commercial_use_allowed": True,
                        "attribution_required": True,
                        "attribution_text": credit_str,
                        "sha256": sha_fog,
                    },
                    {
                        "filename": "external_water_drops.wav",
                        "license_type": "cc0",
                        "author": "Freesound CC0 Contributor",
                        "title": "Water Drops",
                        "source_url": "https://freesound.org",
                        "commercial_use_allowed": True,
                        "attribution_required": False,
                        "sha256": sha_drops,
                    },
                    {
                        "filename": "personal_only_track.wav",
                        "license_type": "personal_only",
                        "author": "Restricted Pack",
                        "commercial_use_allowed": False,
                        "sha256": sha_nc,
                    },
                ]
            }), encoding="utf-8")

            qa_assets = discover_qa_audio_assets(qa)
            by_stem = {Path(a.file_path).stem: a for a in qa_assets}
            policy = LicensePolicy()
            vals = {}

            v_fog = validate_audio_asset(by_stem["external_dark_fog"], policy, [qa])
            self.assertTrue(v_fog.ok)
            self.assertEqual(v_fog.computed_sha256, sha_fog)
            vals[by_stem["external_dark_fog"].asset_id] = v_fog

            v_drops = validate_audio_asset(by_stem["external_water_drops"], policy, [qa])
            self.assertTrue(v_drops.ok)
            self.assertTrue(v_drops.needs_resample)  # 22050 Hz mono -> needs_resample=True
            vals[by_stem["external_water_drops"].asset_id] = v_drops

            # Missing license JSON for real SFX MUST reject
            v_unlic = validate_audio_asset(by_stem["mystery_unlicensed"], policy, [qa])
            self.assertFalse(v_unlic.ok)
            self.assertIn("Missing verified license", v_unlic.reason)
            vals[by_stem["mystery_unlicensed"].asset_id] = v_unlic

            # commercial_use_allowed=False MUST reject
            v_nc = validate_audio_asset(by_stem["personal_only_track"], policy, [qa])
            self.assertFalse(v_nc.ok)
            vals[by_stem["personal_only_track"].asset_id] = v_nc

            # Credits & Asset Manifest check
            cred_p = Path(td) / "credits_audio.txt"
            write_credits_file(cred_p, [by_stem["external_dark_fog"], by_stem["external_water_drops"]], vals)
            cred_txt = cred_p.read_text(encoding="utf-8")
            self.assertIn(credit_str, cred_txt)
            self.assertIn("CC0 Public Domain", cred_txt)

            man_p = Path(td) / "audio_asset_manifest.json"
            write_audio_asset_manifest(
                man_p,
                qa_assets,
                vals,
                {by_stem["external_dark_fog"].asset_id: ["music:seg_00"]},
                "QA_LIBRARY_MOUNTED_READONLY",
                qa,
            )
            man = json.loads(man_p.read_text(encoding="utf-8"))
            self.assertEqual(man["rejected_assets_count"], 2)

    def test_a4_corrupt_zero_wrong_hash_and_path_traversal_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            qa = Path(td) / "QA"
            qa.mkdir(parents=True)
            outside = Path(td) / "secret_outside.wav"
            sha_out = _write_sine_wav(outside)

            # 1. Corrupt WAV
            corrupt = qa / "corrupt.wav"
            corrupt.write_bytes(b"NOT_A_REAL_RIFF_WAV_HEADER_0000000000000000000000000000")
            a_cor = AudioAsset("cor", "qa_real_sfx", "sfx", file_path=str(corrupt), license_type="cc0")
            self.assertFalse(validate_audio_asset(a_cor, LicensePolicy(), [qa]).ok)

            # 2. Zero-length WAV
            empty = qa / "zero.wav"
            empty.write_bytes(b"")
            a_zero = AudioAsset("zer", "qa_real_sfx", "sfx", file_path=str(empty), license_type="cc0")
            self.assertFalse(validate_audio_asset(a_zero, LicensePolicy(), [qa]).ok)

            # 3. Wrong SHA-256
            good = qa / "good.wav"
            _write_sine_wav(good)
            a_badsha = AudioAsset("bsha", "qa_real_sfx", "sfx", file_path=str(good), license_type="cc0", expected_sha256="0" * 64)
            v_sha = validate_audio_asset(a_badsha, LicensePolicy(), [qa])
            self.assertFalse(v_sha.ok)
            self.assertIn("SHA-256 mismatch", v_sha.reason)

            # 4. Path traversal (`..`), nested escape, direct outside-root & symlink escape rejected
            a_trav = AudioAsset("trav", "qa_real_sfx", "sfx", file_path=str(qa / ".." / "secret_outside.wav"), license_type="cc0")
            self.assertFalse(validate_audio_asset(a_trav, LicensePolicy(), [qa]).ok)

            a_nested_trav = AudioAsset("trav2", "qa_real_sfx", "sfx", file_path=str(qa / "sub" / ".." / ".." / "secret_outside.wav"), license_type="cc0")
            v_nested = validate_audio_asset(a_nested_trav, LicensePolicy(), [qa])
            self.assertFalse(v_nested.ok)
            self.assertIn("..", v_nested.reason)

            a_outside = AudioAsset("out_direct", "qa_real_sfx", "sfx", file_path=str(outside), license_type="cc0", expected_sha256=sha_out)
            v_out = validate_audio_asset(a_outside, LicensePolicy(), [qa])
            self.assertFalse(v_out.ok)
            self.assertIn("escapes", v_out.reason)

            sym = qa / "escape_link.wav"
            try:
                sym.symlink_to(outside)
                a_sym = AudioAsset("sym", "qa_real_sfx", "sfx", file_path=str(sym), license_type="cc0", expected_sha256=sha_out)
                v_sym = validate_audio_asset(a_sym, LicensePolicy(), [qa])
                self.assertFalse(v_sym.ok)
                self.assertIn("escapes", v_sym.reason)
            except OSError as exc:
                # Unprivileged Windows accounts lack SeCreateSymbolicLinkPrivilege (WinError 1314)
                if getattr(exc, "winerror", None) != 1314:
                    raise
                sibling = qa.parent / "QAEscapeSibling"
                sibling.mkdir(exist_ok=True)
                sib_wav = sibling / "leak.wav"
                sib_wav.write_bytes(outside.read_bytes())
                a_sib = AudioAsset("sib_prefix", "qa_real_sfx", "sfx", file_path=str(sib_wav), license_type="cc0")
                v_sib = validate_audio_asset(a_sib, LicensePolicy(), [qa])
                self.assertFalse(v_sib.ok)
                self.assertIn("escapes", v_sib.reason)

    def test_a19_a20_qa_mode_fails_early_and_low_disk_fails_closed(self) -> None:
        # --music-mode qa-library with no QA library must fail preflight early!
        pf = preflight_audio_assets(
            project_root=PROJECT_ROOT,
            qa_audio_root=None,
            qa_status="QA_LIBRARY_UNAVAILABLE",
            music_mode="qa-library",
            disk_free_gb=20.0,
        )
        self.assertFalse(pf["ok"])
        self.assertTrue(any("qa-library" in e for e in pf["errors"]))

        # auto mode succeeds with QA_LIBRARY_UNAVAILABLE warning
        pf_auto = preflight_audio_assets(
            project_root=PROJECT_ROOT,
            qa_audio_root=None,
            qa_status="QA_LIBRARY_UNAVAILABLE",
            music_mode="auto",
            disk_free_gb=20.0,
        )
        self.assertTrue(pf_auto["ok"])
        self.assertTrue(any("QA_LIBRARY_UNAVAILABLE" in w for w in pf_auto["warnings"]))

        # Very low disk fails preflight safely
        pf_low = preflight_audio_assets(
            project_root=PROJECT_ROOT,
            qa_audio_root=None,
            qa_status="QA_LIBRARY_UNAVAILABLE",
            music_mode="auto",
            disk_free_gb=0.01,
        )
        self.assertFalse(pf_low["ok"])
        ok_d, _, _ = check_disk_quota(PROJECT_ROOT, min_free_gb=999_999.0)
        self.assertFalse(ok_d)


if __name__ == "__main__":
    unittest.main()
