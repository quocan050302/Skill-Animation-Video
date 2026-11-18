# Implementation Plan & Gates — SD-RETENTION-04.R2 (`2026-11-18T04:58Z`)

## 1. Execution & Safety Parameters
- **Branch**: `feat/sd-retention-01-expressive-editorial` (forked from `742da8f4a53231d5cdd1c0c80d5733a28d6d6f45`, master untouched @ `6d9f31e`).
- **Disk Reserve**: `48.77 GiB` free / `144.02 GiB` (`33.86%`). Preserve `>= 20%` (`~28.8 GiB`) or `>= 12 GiB` free. Single concurrent GPU/Chrome 4K render lock; async CPU validation bounded (`--workers 2`, tested `1 vs 2` parity).
- **TTS Capability**: `windows_sapi` (`Microsoft David Desktop`, `Microsoft Zira Desktop`); `neural_voice_available: false` (`NOT_AVAILABLE`), `word_anchor_confidence: ESTIMATED`. Zero unrequested large model installs.

## 2. Workstreams & Required Fixes
1. **P0-A Shared Volumetric-Like Atmosphere Engine (`director/assets/atmospheric_volume_primitives.py`)**:
   - Replace `DodecahedronGeometry` smoke balls with depth-sorted soft FBM sprite billboards, soft alpha-mapped mattes (`matteAlphaClip`), layered atmospheric strata, and deterministic analytic time-seek `f(t, seed, state)`.
2. **P0-B 3D Label Removal & Mobile Safe Typography (`zdf_london_smog_scenes.py`, `editorial_design_system.py`, `editorial_theme_renderer.py`, `decoded_visual_quality.py`, `retention_qa.py`)**:
   - Remove giant `PlaneGeometry(3.2, 0.74)` `ILLUSTRATIVE AIRFLOW` 3D card; emit projected 3D bounds & DOM glyph-box `overlay_visibility_proof` across `320, 360, 390, 1080` px viewports.
3. **P0-C / P1 London Pacing, Setup Diversity & Character Polish (`shot_director.py`, `zdf_london_smog_scenes.py`, `camera_choreographer.py`, `action_camera_director.py`)**:
   - Eliminate repeated `setup_type`s (`shot_01->02`, `shot_03->04`) -> target `scene_diversity_and_retention: PASS` (`adjacent_identical_setups == 0`).
   - Sharp 0–3s noon blackout consequence; distinct chimney cutaway vs rooftop stacks skyline; distinct inversion lid slide vs street-canyon trap; lantern bus visibility; grounded scarf-cough pedestrian stance; sunlit vs smoky Clean Air Act 1956 payoff.
   - Separate `planned_camera_info_gain` (planning heuristic) from decoded `observed_proof_gain` (`observed_evidence_report.json`).
4. **Mount St. Helens 1980 New 3D Demo (`director/assets/zdf_st_helens_scenes.py`)**:
   - Fresh assets, fresh seed, USGS-grounded script, 7+ distinct causal presentations (North Flank Bulge Hook -> Cryptodome Cutaway -> M5.1 Landslide Avalanche -> >300 mph Lateral Blast -> Forest/Ridge Flatten -> Plinian Ash Column -> Horseshoe Crater Before/After).
5. **P0-D Semantic QA, N41–N60 Traps & Non-Destructive Backtests (`semantic_visual_evidence_qa.py`, `quality_gate.py`, `zdf_boston_molasses_scenes.py`, `zdf_tacoma_bridge_scenes.py`)**:
   - Separate classification (`ENGINE_TECHNICAL_PASS`, `DEMO_EDITORIAL_REVIEW_REQUIRED`, `HUMAN_VISUAL_REVIEW_REQUIRED`, `PRODUCTION_RELEASE_READY`).
   - Keep pre-R4 Boston FAIL / Tacoma WARN logs immutable (`pre_R4_status`); fix Boston & Tacoma matte/telemetry roots cleanly and run isolated new replacement backtest renders (`new_R4_R2_status`).
   - Add 4 new test modules covering N41–N60 and register in `tools/run_validation_async.py`.

## 3. Gate Matrix
- `G0`–`G1`: Clean git/env/static imports/six-skill lock
- `G2`–`G4`: `N01`–`N60` + `tools/run_validation_async.py --mode full --workers 2` + `python -m unittest discover -s tests -v` (exit 0, 100% coverage)
- `G5`–`G8`: Live WebGL mattes/seeks, London A/B (same VO PCM), Mount St. Helens 1080p & native 4K, 360px strips & safezones, isolated Boston/Tacoma backtests
- `G9`: Final acceptance manifests, checksums, README, git commit & push to `feat/sd-retention-01-expressive-editorial`.
