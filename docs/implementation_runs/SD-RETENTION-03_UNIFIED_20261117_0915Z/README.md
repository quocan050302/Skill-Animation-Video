# SD-RETENTION-03.UNIFIED.R1 Execution Record — *The Bridge That Twisted Itself Apart*

**Execution Branch**: `feat/sd-retention-01-expressive-editorial` (forked from `master` @ `6d9f31e5f3d4a9f9127543bb3648c031de09a3fb`; baseline commit `ab5928922a45745099ee82aafa15d020166ac381`)  
**Scope**: Unified upgrade integrating Semantic Multi-Theme Editorial Design System, Curiosity Headlines & Impact Pointers, Deterministic Physical Motion Primitives (including Boston continuous viscous wave repair + Tacoma Narrows 1940 8-scene suite), Grounded Foot-Locked Character Performance, 9:16 Cinematic Composition Solver, Role-Mapped SFX, and False-Pass-Proof QA inside `zach-d-films` without regressing the other 5 isolated visual engines.

---

## 1. Delivered Architecture & Code Modules (`(a)`–`(h)` Single Unified Pipeline)

| Layer | Modules Added / Updated |
|---|---|
| Multi-Theme Editorial Design | [editorial_design_system.py](../../../director/editorial_design_system.py), [editorial_theme_renderer.py](../../../director/assets/editorial_theme_renderer.py), [curiosity_director.py](../../../director/curiosity_director.py), [editorial_overlay.py](../../../director/editorial_overlay.py) |
| Physical Motion & Bridge / Molasses Physics | [physical_motion.py](../../../director/physical_motion.py), [physical_motion_primitives.py](../../../director/assets/physical_motion_primitives.py), [zdf_tacoma_bridge_scenes.py](../../../director/assets/zdf_tacoma_bridge_scenes.py), [zdf_boston_molasses_scenes.py](../../../director/assets/zdf_boston_molasses_scenes.py) |
| Grounded Character Performance | [character_performance.py](../../../director/character_performance.py), [assets/character_performance.py](../../../director/assets/character_performance.py) |
| Story, Camera, Composition & Pipeline Plumbing | [visual_event_graph.py](../../../director/visual_event_graph.py), [visual_storytelling_director.py](../../../director/visual_storytelling_director.py), [scene_asset_factory.py](../../../director/scene_asset_factory.py), [shot_director.py](../../../director/shot_director.py), [camera_choreographer.py](../../../director/camera_choreographer.py), [cinematic_composition.py](../../../director/cinematic_composition.py), [cinematic_composition_qa.py](../../../director/cinematic_composition_qa.py), [zach_d_films_adapter.py](../../../director/assets/zach_d_films_adapter.py), [build_storyboard.py](../../../director/build_storyboard.py), [run.py](../../../director/run.py) |
| Role-Mapped Audio & Collapse Timing | [audio_dsp.py](../../../director/audio_dsp.py), [sfx_director.py](../../../director/sfx_director.py), [mix_audio.py](../../../director/mix_audio.py), [audio_narrative.py](../../../director/audio_narrative.py) |
| False-Pass-Proof QA & Validation | [visual_storytelling_qa.py](../../../director/visual_storytelling_qa.py), [retention_qa.py](../../../director/retention_qa.py), [quality_gate.py](../../../director/quality_gate.py), [run_validation_async.py](../../../tools/run_validation_async.py) |

---

## 2. Primary Showcase Deliverable: *The Bridge That Twisted Itself Apart* (1940 Tacoma Narrows)

- **Run Directory**: [`runs/sd_retention03_tacoma_bridge_20261117_1005Z/`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/)
- **Enhanced 4K Native Master**: [`enhanced_B/final_4k.mp4`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/enhanced_B/final_4k.mp4) (`2160x3840`, `30.0 fps`, `39.933s`, `45.12 MiB`, H.264 + AAC 48 kHz stereo, `native_4k: true`, high-freq sharpness ratio vs bilinear 1080p = `1.1914`)
- **Enhanced 1080p Preview**: [`enhanced_B/preview_1080.mp4`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/enhanced_B/preview_1080.mp4) (`1080x1920`, `30.0 fps`)
- **Baseline 1080p Control**: [`baseline_A/preview_1080.mp4`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/baseline_A/preview_1080.mp4) (`1080x1920`, `39.967s`, `--editorial-theme legacy --curiosity-layer off --voice-style legacy --caption-mode plain --callout-mode off`)
- **Verified Historical Claims & Disclosures**: [`demo/historical_claims.json`](demo/historical_claims.json), [`demo/factual_sources.md`](demo/factual_sources.md) (WSDOT + FHWA facts; all 3D deformation explicitly marked `stylized_illustrative`)

### Measured Technical Metrics (`enhanced_B` vs `baseline_A`)

| Metric | `baseline_A` (Legacy) | `enhanced_B` (Unified `SD-RETENTION-03`) | Source Artifact |
|---|---|---|---|
| **Overall Technical QC** | `PASS` (`TECHNICAL_ACCEPTANCE_PASS`) | `PASS` (`TECHNICAL_ACCEPTANCE_PASS`) | [`enhanced_B/qc_report.json`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/enhanced_B/qc_report.json) |
| **Shots / Unique Setups / Adjacency Clones** | 9 shots / 8 setups / 0 clones | 9 shots / 8 setups / 0 clones | [`enhanced_B/scene_diversity_report.json`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/enhanced_B/scene_diversity_report.json) |
| **Editorial Semantic Roles Rendered** | `[]` (`callout_mode="off"`) | **6 distinct roles** (`curiosity_headline`, `location_time`, `verified_fact`, `explanation`, `warning_danger`, `aftermath_sober`) | [`enhanced_B/editorial_roles_plan.json`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/enhanced_B/editorial_roles_plan.json) |
| **Pointer Tip Accuracy (`<= 36 px` limit)** | N/A | **Worst error `13.53 px`** (`9` settled tips checked; `ov_00`: `7.33px`, `ov_03`: `13.53px`, `ov_04`: `7.41px`, `ov_05`: `7.50px`) | [`enhanced_B/pointer_tracking.json`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/enhanced_B/pointer_tracking.json) |
| **Bridge Physical Deformation & Cable Continuity** | Same deterministic geometry (`cables_attached: true`) | `max_vertex_disp_m: 2.7m`, `max_deck_roll_span_rad: 0.3183`, collapse onset `30.817s`, `cables_attached_all: true`, zero NaN | [`enhanced_B/world_state_telemetry.json`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/enhanced_B/world_state_telemetry.json) |
| **Shore Onlooker Foot Grounding (`human.js` FK)** | Same grounded rig | `worst_penetration_m: 0.0m`, `worst_stance_slide_m: 0.0m`, `move_toward_threat_dot: -1.0` | [`enhanced_B/character_performance_telemetry.json`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/enhanced_B/character_performance_telemetry.json) |
| **Audio Loudness & Role SFX Sync** | `-14.3 LUFS`, `-2.5 dBTP`, 14 cues | `-14.5 LUFS`, `-2.5 dBTP`, 18 cues + pre-collapse anticipation duck (`-13.5 dB`) | [`ab_comparison/ab_report.json`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/ab_comparison/ab_report.json) |
| **Voice Prosody Metrics (`Microsoft Zira Desktop`)** | `wps_span=33.98%`, `f0_span=13.24Hz`, `rms_span=1.51dB` | `wps_span=56.21%` (+22.23%), `f0_span=25.05Hz` (+11.81Hz), `rms_span=2.35dB` | [`ab_comparison/ab_report.json`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/ab_comparison/ab_report.json) |
| **Mobile Scaled DOM Caption Gaps** | Plain unstyled block | `320px`: `6.82px`, `360px`: `7.68px`, `390px`: `8.32px` (zero word overlap) | [`qa/tacoma_mobile_360.png`](qa/tacoma_mobile_360.png) |

### Visual Evidence Sheets
- [`qa/tacoma_role_breakdown_sheet.jpg`](qa/tacoma_role_breakdown_sheet.jpg) — All 6 semantic roles + shore onlooker verified in decoded frames
- [`qa/tacoma_ab_side_by_side_sheet.jpg`](qa/tacoma_ab_side_by_side_sheet.jpg) — Event-aligned `baseline_A` vs `enhanced_B`
- [`qa/tacoma_overlay_on_off_diff.jpg`](qa/tacoma_overlay_on_off_diff.jpg) — Identical-seed ON vs OFF pixel diff proof
- [`qa/tacoma_torsion_collapse_progression.jpg`](qa/tacoma_torsion_collapse_progression.jpg) — Deck bend -> wind vortex girder -> violent torsion -> center span snap & water splash -> sober aftermath
- [`SHA256SUMS.txt`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/SHA256SUMS.txt)

---

## 3. Separate Boston Molasses Repair Proof (`BOSTON_REGRESSION_PROOF`)

- **Run Directory**: [`runs/sd_retention03_boston_repair_proof_20261117_1036Z/`](../../../runs/sd_retention03_boston_repair_proof_20261117_1036Z/) (`overall_qc_status: "PASS"`, `unique_setups: 9`, `unique_scene_families: 9`)
- **Wave Surface Repair**: Replaced 6 disconnected sphere lobes in `makeMolassesGravityCurrentRig` with a smooth `40x22` deformable viscous heightfield mesh (`surface_mode: continuous_viscous_heightfield`, `max_vertex_disp_m: 2.0489m`) carrying coupled wooden barrel/crate/plank debris cleanly along the wave crest.
- **Pedestrian Retreat Grounding**: Upgraded `makePeriodCrowdActionRig` onto `evaluateCharacterPose` + `applyGroundedCharacterPose`, achieving `worst_penetration_m: 0.0131m` (`<= 0.03m`), `worst_stance_slide_m: 0.001m` (`<= 0.08m`), and verified threat-away displacement (`move_toward_threat_dot: -1.0`).
- **Before vs After Visual Sheet**: [`qa/boston_before_after_wave_crowd.jpg`](qa/boston_before_after_wave_crowd.jpg) compared against read-only [`qa/boston_baseline_ref/`](qa/boston_baseline_ref/).

---

## 4. Technical Gates (`G01`–`G22`) & Negative Traps (`N01`–`N32`) Matrix

- **Design System & Curiosity**: `test_editorial_design_system.py` + `test_curiosity_director.py` verify 2+ style variants per role, mobile viewport sizing, token emission, 3rd non-Tacoma/Boston topic generalization (`G19`), `N01` (`<64px` hero rejection), `N02` (repeated box rejection), `N03` (danger styling on neutral location rejection), `N04` (missing 3D anchor rejection), `N09` (early reveal lock rejection), `N10` (duplicate headline rejection), and `N31` (unverified numeric fact rejection).
- **Physical Motion & Character Grounding**: `test_physical_motion.py` + `test_character_performance.py` verify WebGL bridge torsion/collapse/viscous waves, out-of-order seek bit-for-bit determinism (`N20`), `human.js` FK sole grounding, plus traps `N13`–`N15`, `N17`–`N19`, `N21`–`N22`.
- **Composition, Sync, Isolation & False-Pass QA**: `test_cinematic_composition.py` + `test_retention03_integration.py` + `test_storytelling_qa.py` + `test_editorial_overlays.py` + `test_boston_molasses_scenes.py` verify portrait composition & collision guards (`N07`), pointer tip accuracy (`<= 36px`, trap `N29`), event-locked A/B alignment (`N25`, removing blind `normalized_shot_index` fallback), role SFX sync, single-skill isolation (`stick-figure` stays `legacy` + `callout_mode="off"`), and 3rd science topic execution (`N32`).
- **Validation Logs Location**: [`logs/async_dag/validation_summary.json`](logs/async_dag/validation_summary.json) (populated by `python tools/run_validation_async.py --mode full --workers 2` right before final commit).

---

## 5. Honest Capabilities & Pending Human Review Checklist (`NOT_VERIFIED`)

All automated QC reports explicitly leave the following human-evaluation fields **`NOT_VERIFIED`**:
- `subjective_visual_review`: `"NOT_VERIFIED"`
- `subjective_editorial_listening`: `"NOT_VERIFIED"`
- `subjective_voice_quality_status`: `"NOT_VERIFIED"` (`neural_prosody: false`, local offline Windows SAPI5 `Microsoft Zira Desktop`, `word_anchor_confidence: "ESTIMATED"`)
- `viewer_retention_status`: `"NOT_VERIFIED"`

### Pending Human Review Items
1. Watch [`enhanced_B/final_4k.mp4`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/enhanced_B/final_4k.mp4) at phone viewing distance on portrait hardware to confirm emotional pacing, arrow legibility at ~32s (`SPAN BROKE FREE`), and caption readability across rapid motion cuts.
2. Listen on studio/phone speakers to verify whether offline Windows SAPI5 (`Microsoft Zira Desktop` + SSML prosody) is acceptable vs routing a human recording (`--voice-file`) or neural TTS backend, and confirm pre-collapse anticipation ducking (`-13.5 dB` at ~30.6s) feels dramatically balanced against the water-splash impact.
3. Review A/B retention preference between [`baseline_A/preview_1080.mp4`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/baseline_A/preview_1080.mp4) and [`enhanced_B/preview_1080.mp4`](../../../runs/sd_retention03_tacoma_bridge_20261117_1005Z/enhanced_B/preview_1080.mp4) with real human viewers before making editorial retention claims.
