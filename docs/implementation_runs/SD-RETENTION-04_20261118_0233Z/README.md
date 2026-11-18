# SD-RETENTION-04.R1 — Visual Causality, Action-Driven Camera & Semantic Evidence QA

- **Run ID**: `SD-RETENTION-04_20261118_0233Z`
- **Target Branch**: `feat/sd-retention-01-expressive-editorial` (master untouched @ `6d9f31e5f3d4a9f9127543bb3648c031de09a3fb`)
- **Inspected Baseline HEAD**: `233ace0871a8fa4654bccafdda52e377c2ac1f1a` (`Merge pull request #1 from quocan050302/feat/sd-retention-03-r2-visual-quality`, descending from `896689f4140e15f01bf927679240ee0119e30212`)
- **Upstream Submodule**: `vendor/claude-animation-skills` @ `5dbea55c23aa6a5c93dc3cfb5583840513b56b94` (clean, unmodified)
- **Brand-New 3D Demo Target**: `"The Day London Disappeared into Smog"` (`runs/sd_retention04_london_smog_20261118_0233Z/`)

---

## Pre-Implementation Baseline Audit (2026-11-18T02:33Z)

Before modifying any source code, full repository & host inspection established:

1. **Host Environment (`host_environment.json`)**:
   - OS: Windows AMD64 (`12` CPU cores, `49.64 GiB` free disk / `144.02 GiB` total)
   - Toolchain: `ffmpeg` 9.0.2, `ffprobe`, Node.js, Chrome (`webgl_backend: "d3d11"`), Kit ready (`kit_ready: true`)
   - Voice backend: `windows_sapi` (`Microsoft David Desktop`, `Microsoft Zira Desktop`), `neural_prosody: false`, `word_anchor_confidence: ESTIMATED` (spoken rates/pitch/pauses vary via SSML; non-neural concatenative voice disclosed honestly)
   - Audio assets: `QA_LIBRARY_UNAVAILABLE` locally (native procedural DSP audio engine active)

2. **Baseline QA & Local Proof Status (`baseline_qa_summary.json`, `baseline_runs_manifest.json`)**:
   - Baseline tests logged in R2 (`SD-RETENTION-03_R2_20261117_1135Z`): `25` test modules, `79` unittests passing (`async_dag` 497.38s, `canonical_unittest_discover` 613.33s).
   - Local R2 Tacoma proof (`runs/sd_retention03_r2_tacoma_proof_20261118`): `overall_status: WARN`, `release_status: TECHNICAL_ACCEPTANCE_PASS`, `decoded_visual_quality: WARN` (`Shot shot_06 low figure-ground edge separation (6.6 < 12.0)`).
   - Local R2 Boston proof (`runs/sd_retention03_r2_boston_proof_20261118`): `overall_status: WARN`, `release_status: TECHNICAL_ACCEPTANCE_PASS`, `decoded_visual_quality: WARN` (`shot_03` 11.7 < 12.0, `shot_07` 6.5 < 12.0).
   - MacOS R2 Skyscraper proof (`runs/sd_retention03_r2_skyscraper_20261117`): `.mp4` `UNAVAILABLE_LOCAL_MP4` (`LOCAL_ONLY_ON_HOST` on macOS; contact sheets curated in `docs/implementation_runs/SD-RETENTION-03_R2_20261117_1135Z/qa/`).

3. **Critical Functional Gaps Addressed in SD-RETENTION-04.R1 (`audit_function_map.md`)**:
   - **(A) Causal Storytelling (`director/visual_causality_director.py`)**: Convert beat-by-beat descriptions into explicit `CausalEvent` chains (`cause_event_ids` -> `result_event_ids`) with `VisualEvidenceContract` (`expected_visible_consequence`, `counterfactual_failure`, 11 proof types), persistent cross-cut world state conservation, and general domain matching without hardcoding city names.
   - **(B) Action-Driven Camera & Editorial Intent (`director/action_camera_director.py`)**: Require Q1–Q5 `CameraIntentContract` answering why the camera is placed/moving and scoring `causal_visibility_gain`, `action_anchoring`, `novel_evidence_gain`, `camera_motion_justification`, `context_preservation`, `impact_understanding`, while locking overlays/pointers to `semantic_region_of_change` and `narrative_claim_id`.
   - **(C) Semantic Visual Evidence QA (`director/semantic_visual_evidence_qa.py`) & Negative Traps `N01`–`N40`**: Inspect decoded RGB frames, WebGL semantic object-ID mattes (`causal_feature` / `cause_source` / `effect_result` / `character` / `subject` / `reference_fixed`), before/action/after state continuity, pointer region alignment, silent comprehension proxies, blocking vs advisory warnings, and A/B VO PCM parity checks.

> Subjective statuses (`subjective_visual_review`, `subjective_visual_quality`, `subjective_editorial_listening`, `subjective_voice_quality_status`, `viewer_retention_status`) remain explicitly `NOT_VERIFIED`.

---

## Implementation Closeout Results (2026-11-18)

### 1. Post-Edit Full Validation Gates (0 Edits After Run)
- **Async Validation DAG** (`python tools/run_validation_async.py --mode full --workers 2`): **`PASS`** — `27/27` modules covered (`missing_modules: []`), elapsed `600.27s` ([`logs/async_dag/validation_summary.json`](logs/async_dag/validation_summary.json)).
- **Canonical Full Discovery Suite** (`python -m unittest discover -s tests -v`): **`OK` (exit code `0`)** — `Ran 92 tests in 720.378s` ([`logs/canonical_unittest_discover.log`](logs/canonical_unittest_discover.log)).
- **Negative & Metamorphic Traps (`N01`–`N40`)**: **`40/40 PASS`** ([`negative_traps_report.json`](negative_traps_report.json)).

### 2. Brand-New 3D Explainer Demo — `"The Day London Disappeared into Smog"`
- **Strict Single-Skill Lock**: `zach-d-films` (`selection_mode: explicit`, `0` violations across `28` inspected files).
- **Rendered Video Deliverables (`LOCAL_ONLY_GITIGNORED`, excluded from Git)**:
  - **Enhanced B Final 4K**: `D:\Project_github\Skill-animations\short-director\Skill-Animation-Video\runs\sd_retention04_london_smog_20261118_0233Z\enhanced_B\final_4k.mp4` (`2160x3840`, `30.0 fps`, `39.3333s`, `52,190,384` bytes, `native_4k: true`, `high_freq_edge_ratio_vs_1080p_bilinear: 1.1547`, `h264/yuv420p` + `aac 48000 Hz stereo`, SHA-256 `666eb7962a71357b8c119fa4ebf774f18b3d2d2c369cd89aad23e21627813ed8`).
  - **Enhanced B Preview 1080p**: `D:\Project_github\Skill-animations\short-director\Skill-Animation-Video\runs\sd_retention04_london_smog_20261118_0233Z\enhanced_B\preview_1080.mp4` (`1080x1920`, `15,852,724` bytes, SHA-256 `f2382f0a5dbee0c6cb9481cde7051d606e7138800eac5debada260c95602c749`).
  - **Baseline A Final 4K**: `D:\Project_github\Skill-animations\short-director\Skill-Animation-Video\runs\sd_retention04_london_smog_20261118_0233Z\baseline_A\final_4k.mp4` (`49,159,187` bytes, SHA-256 `0a54e54f924e4e9e793558850d39d468173507ed13e0f163659cff5ef2a7ff73`).
  - **Baseline A Preview 1080p**: `D:\Project_github\Skill-animations\short-director\Skill-Animation-Video\runs\sd_retention04_london_smog_20261118_0233Z\baseline_A\preview_1080.mp4` (`18,111,800` bytes, SHA-256 `323278142f3a7e759de8218170aa2d0e5e38740e61ab6d254204c0b29a38de0b`).
- **Enhanced B Technical QC Summary (`qa_summary.json`, `gates_status.csv`)**:
  - `overall_status: WARN`, `release_status: TECHNICAL_ACCEPTANCE_PASS`; `15/16` top-level checks `PASS` including `semantic_causal_visual_evidence: PASS` (`5/5` causal sub-gates `PASS`, `claim_coverage_ratio: 1.0`, `camera_intent_mean_info_gain: 0.896`), `decoded_visual_quality: PASS`, `camera_execution: PASS` (`worst_pos_err_m: 0.0`, `worst_ori_err_deg: 0.152`), `audio_levels_and_ducking: PASS` (`integrated_lufs: -15.0`, `true_peak_dbtp: -2.3`).
  - Preserved honest `WARN`: `scene_diversity_and_retention: WARN` (`adjacent_repetition_guard` flags `shot_01->shot_02` and `shot_03->shot_04` sharing `setup_type`; `hard_clone_count: 0`, `masked_ssim` `-0.0752` and `0.1063`).
- **A/B Parity & Comparison**:
  - `audit_ab_vo_and_metric_consistency`: **`PASS`** (`vo_pcm_identical: true`, `vo_pcm_sha256: fcaed921c9077f99a394d9eb2684b2501aaa4024a4a4bb3fbb836b0b03dcc041`), `voice_stem_pcm_parity: true`, `ab_alignment: PASS` (`pairs: 8`), SFX cues `14` (A) vs `21` (B), `has_measurable_visual_diff: true`.
- **Curated Visual Contact Sheets**:
  - [`qa/london_hook_0_3s_strip.jpg`](qa/london_hook_0_3s_strip.jpg)
  - [`qa/london_decoded_visual_proof_sheet.jpg`](qa/london_decoded_visual_proof_sheet.jpg)
  - [`qa/london_event_aligned_before_action_after.jpg`](qa/london_event_aligned_before_action_after.jpg)
  - [`qa/london_ab_frame_diff_grid.jpg`](qa/london_ab_frame_diff_grid.jpg)

### 3. Non-Destructive Legacy Backtests (`backtests_report.json`)
- **Tacoma Narrows 1940 (`runs/sd_retention03_r2_tacoma_proof_20261118`)**: `world_state_conservation: PASS`, `semantic_qa_status: WARN` (`visual_claim_coverage: PASS`, `claim_pointer_semantics: PASS`, `causal_transition_visibility: PASS`, `silent_comprehension_proxy: PASS`; advisory warning on `shot_00` `reference_fixed` matte pixels).
- **Boston Molasses 1919 (`runs/sd_retention03_r2_boston_proof_20261118`)**: `world_state_conservation: PASS`, `semantic_qa_status: FAIL` (`claim_coverage_ratio: 0.80 < 0.85` — pre-R4 Boston mattes lacked `causal_feature` tags on `cev_001`/`cev_004` and `vdisp=0.0000m` telemetry on `shot_01`/`shot_04`, surfacing legacy gaps honestly).
- **Skyscraper Damper (`macOS`)**: `UNAVAILABLE_LOCAL_MP4` (`LOCAL_ONLY_ON_HOST`).

### 4. Preserved Honest Non-Verification & Physics Disclosures
- `subjective_visual_review`, `subjective_visual_quality`, `subjective_editorial_listening`, `subjective_voice_quality_status`, and `viewer_retention_status` remain **`NOT_VERIFIED`**.
- `neural_prosody: false`, `word_anchor_confidence: ESTIMATED` (Windows SAPI5 concatenative TTS).
- Physics representation remains disclosed as `visualized_physical_approximation` (procedural Three.js kinematics/shaders, not a CFD/FEM solver).
- Full artifact checksums & lineage: [`final_manifest.json`](final_manifest.json), [`artifact_lineage.json`](artifact_lineage.json), [`SHA256SUMS.txt`](SHA256SUMS.txt).
