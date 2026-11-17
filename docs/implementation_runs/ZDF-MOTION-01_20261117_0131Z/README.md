# ZDF-MOTION-01 Execution & Verification Log (`2026-11-17T01:31Z`)

## 0. Baseline Startup Audit & Safety Check

- **Repository Root**: `D:\Project_github\Skill-animations\short-director\Skill-Animation-Video`
- **Branch**: `master` (`## master...origin/master`)
- **Baseline HEAD SHA**: `8a09f4e8a63a219d78e4889ab0c6154954076ef2` (`v0.4.0`, 2026-11-16)
- **Remote Origin**: `https://github.com/quocan050302/Skill-Animation-Video.git`
- **Upstream Submodule (`vendor/claude-animation-skills`)**: Initialized cleanly at pinned SHA `5dbea55c23aa6a5c93dc3cfb5583840513b56b94` (`git -C vendor/claude-animation-skills status --porcelain` clean / empty)

### Host Toolchain & Resource Preflight
| Component | Observed Value | Notes |
|---|---|---|
| OS | Windows 11 (PowerShell) | CPU: 12 logical cores; RAM: 31.75 GiB total (~6.66 GiB free) |
| Disk Free | Drive `D:` 54.54 GiB start / 54.13 GiB hero render | `DiskBudgetGuard` floor: `max(4 GiB, 20% free)` (~10.9 GiB) |
| Python | `3.12.10` | `numpy 2.5.4`, `scipy 1.18.1`, `soundfile 0.14.0`, `PIL 13.0.0` |
| Node.js | `v26.13.1` | `playwright` + `three` in `vendor/claude-animation-skills/kit/node_modules` |
| FFmpeg / FFprobe | `9.0.2-full_build-www.gyan.dev` | Forced `yuv420p` (`color_range=tv`), `lowpass=f=18000` + `alimiter(level=false)` |
| Browser / WebGL | `C:\Program Files\Google\Chrome\Application\chrome.exe` | ANGLE `d3d11` (`Intel UHD Graphics 730`), verified seeded parity |
| TTS | Windows `System.Speech` (`Microsoft David Desktop`, `en-US`) | Invoked via PowerShell `-EncodedCommand` (`Rate=1`) |

### Baseline vs Final Test Suite Comparison
- **Clean Pre-Edit Checkout** (`docs/implementation_runs/ZDF-MOTION-01_20261117_0131Z/baseline_unittest.log`): `Ran 36 tests in 9.076s` — `24 ok`, `12 fail/error` (uninitialized submodule + Windows browser/TTS gaps + `test_a4` symlink privilege).
- **Post-Change Async DAG Full Validation** (`python tools/run_validation_async.py --mode full --workers 2`, `docs/implementation_runs/ZDF-MOTION-01_20261117_0131Z/logs/validation_summary.json`):
  **ALL 7 DAG TASKS `PASS` in `328.77s`** (`unit_and_negative` `1.39s`, `visual_event_coverage` `0.22s`, `audio_determinism` `5.69s`, `zdf_motion01_matrix` `15.92s`, `determinism_and_resources` `51.08s`, `visual_scene_factory_e2e` `130.41s`, `smoke_all_engines` `307.16s`).
- **Post-Change Canonical Discovery** (`python -m unittest discover -s tests -v`, `docs/implementation_runs/ZDF-MOTION-01_20261117_0131Z/logs/unittest_discover_final.log`):
  `Ran 42 tests in 492.787s` — **41 `ok`**, **1 `ERROR`**: `test_a4_corrupt_zero_wrong_hash_and_path_traversal_rejected` failed ONLY on `sym.symlink_to(outside)` (`OSError: [WinError 1314] A required privilege is not held by the client` on unprivileged Windows without Developer Mode; `test_audio_catalog_and_licenses.py` left untouched cleanly).

---

## 1. Architectural Upgrades & Function-Level Change Map

### Single-Authority Camera Choreography (`G1`, `I1`)
- **`director/camera_execution.py` (NEW)**: Defines canonical contract `SCHEMA_VERSION = "sd-camera-exec-1"`, `CAMERA_EXECUTOR_JS` (`evalCameraPath`, `applyCameraPath`), matching Python evaluator `evaluate_camera_path_py()`, `look_at_quaternion()`, `quaternion_angle_deg()`, `collect_camera_trace_samples()`, and `evaluate_camera_trace_accuracy()`. Enforces `pos_tol = max(0.03, 0.015 * scene_diag)`, `ori_tol_deg = 0.65`, `fov_tol_deg = 0.65`, floor height `y >= 0.08`, target distance `>= 0.20`, collider AABB checks, and `focal_anchor_uv` visibility outside transition windows.
- **`director/camera_choreographer.py`**: Added `_resolve_zdf_scene_meta(shot)` and `_zdf_keyframes_for_generator(gen, shot, anchor_pos, move, fov, sx, seed_off)`. Updated `plan_camera_path()` & `build_camera_plan()` to anchor paths on real `focal_anchor` coordinates, respect `locked_camera_keyframes` / `camera_locked`, and emit distinct framings per ZDF setup variant (e.g., wide motor drive vs tight right-side caliper clamp macro).
- **`director/render_node.mjs` & `director/render_scene.py`**: Added `trace` mode reading `window.__LAST_RENDER_TELEMETRY__`; fixed Windows `fileURLToPath`, ANGLE `d3d11` mapping, and `scale=in_range=pc:out_range=tv,format=yuv420p`. `render_stills_and_shots(..., camera_plan=None, transition_edl=None)` runs `DiskBudgetGuard` pre-stills and pre-parallel, samples contact-hit & transition midpoint stills, executes `trace` on `zach-d-films`, writes `logs/raw_render_telemetry.json` and `camera_execution_trace.json`, and fails closed if inaccurate or colliding.

### Truthful Two-Source Transitions (`G2`, `I2`)
- **`director/transition_director.py`**: Added `_bridge_contract(...)` and `finalize_transition_edl_verification(edl, audit_details, evidence_path=None)`. Transitions start `executed_in_renderer=False`, `execution_status="PLANNED"`, `verification_status="PLANNED_UNVERIFIED"` until decoded MP4 + telemetry inspection confirms intermediate 2-source composition.
- **`director/assets/zach_d_films_adapter.py`**: `DIRECTOR_MAIN_JS` allocates two offscreen `WebGLRenderTarget`s (`rtA`, `rtB`) and GLSL `compositeMat` supporting `zoom_through`, `match_cut`, `object_wipe`, and `whip_pan` blended toward projected `focal_anchor_uv` centroids, emitting live `telemetry.transition` (`active`, `method`, `alpha`, `anchor_a_uv`, `anchor_b_uv`).

### Persistent Character Identity, Physical 2-Bone Contact IK & Multilayer 3D Cutaways (`G3`, `G4`, `I5`, `I6`, `I9`)
- **`director/assets/zdf_rigs.py` (NEW)**:
  - `CHARACTER_ACTION_RIG_JS`: `buildRegisteredCharacter(makeHumanFn, charSpec)` applies immutable `character_registry` material IDs (`shirt_hex`, `pants_hex`, `collar_hex`, `shoe_hex`) with continuous shoulder/elbow caps and extended sleeves eliminating hinge/wrist gaps; `solveFingerContactIK(human, side, targetTipWorld, poleWorld, approachDirWorld)` & `updateButtonPressAction()` solve 2-bone IK (`a=0.30, b=0.27`, `tipLocalOffset=0.156`) with anticipatory lean and plunger depress, emitting `world_error_m`.
  - `LAYERED_CUTAWAY_JS`: `LayeredCutaway` class using real Three.js `THREE.Plane` `clippingPlanes` (with `renderer.localClippingEnabled = true`), distinct `layer_index` internal sub-assemblies, `TubeGeometry` connection curves, edge-bound flowing particles, and `getTelemetry()` reporting `layers_count`, `components_count`, and `has_clip_plane`.
- **`director/assets/zdf_mechanical_scenes.py` (NEW)**: Procedural Three.js rigs for `makePushButtonPanelRig()` (plunger surface at `[0.24, 1.16, 0.24]` normal `[-1,0,0]`), `makeControllerCabinetRig()`, `makeTractionDriveMachineRig()`, `makeElevatorShaftRig()` (car & counterweight moving in exact opposition + flashing rail sensors + bus flow), `makeLandingDoorsRig()` (leveling interlock before bi-parting slide), and `makeSchematicMechanismStage(labelText)`.
- **`director/assets/zach_d_films_adapter.py`**: Updated `makeModernOutfitCharacter(makeHumanFn, charSpecOrHex)`, upgraded `makeAnatomicalCutawayRig(isBrain)` onto `LayeredCutaway` + `getTelemetry()` on `makeSmartphoneRig`, updated `DIRECTOR_MAIN_JS`, and rewrote `_build_non_roman_scene_shot_code` + `_build_zach_shots_js` to remove the global `is_roman` override (`G5`, `I7`), drive ALL cameras via `applyCameraPath(c, evalCameraPath(KFS, u))`, and route every shot cleanly by its own domain/generator.

### Per-Shot Multi-Domain Grounding & Non-Template Anti-Drift (`G5`, `I7`, `I8`)
- **`director/visual_event_graph.py`**: Added `plan_contact_action()`, elevator/mechanical & `UNSUPPORTED_EXACT_DOMAIN_RULES` (`bicycle_drivetrain`, `espresso_pressure_valve`), per-clause Roman gating, cosmic/elevator disambiguation, and guarded bare comma fallback so lead-in phrases aren't split into subjectless shards.
- **`director/scene_asset_factory.py`**: Added `ZDF_ARCHETYPE_REGISTRY`, `build_character_and_prop_registry()`, `_map_family_to_generator(selected_skill, fam, prop, unsupported_exact_domain=None, require_exact_scene=False)` raising `UnsupportedSceneError("UNSUPPORTED_SCENE_REQUIRED: ...")` when exact archetype is absent, `validate_entity_continuity()` character/prop material/scale invariant checks, and sub-beat `scene_family` resolution inside `materialize_engine_scene()`.
- **`director/shot_director.py`**: Expanded `ENGINE_CANDIDATE_SPACES["zach-d-films"]` with grounded elevator & mechanical macro setups, prevented cross-family `setup_type` costume swapping when a family match exists, coalesced short single-stage ZDF splits, and preserved `character_id`, `contact_action`, `camera_locked`, `locked_camera_keyframes`, and `intentional_hold`.
- **`director/build_storyboard.py`**: Compiles entity/character/prop registries BEFORE `build_camera_plan()` so camera choreography locks onto real scene `focal_anchor`s and collider boxes.

### Decoded-Frame Non-Adjacent Dedup, 4 Hz Motion & Multi-Frame Transition QA (`G6`, `I3`, `I4`)
- **`director/scene_diversity_qa.py`**:
  - Added `_crop_central_roi()`, `_luma_hist_16()`, `_hist_cosine()`, `_decode_timeline_4hz()`, `_verify_nontrivial_transition_frames()`, `audit_camera_execution()`.
  - Updated `sample_perceptual_frames()` & `detect_adjacent_repetitions()` to compute ALL adjacent and non-adjacent `(i, j)` pairs across full masked frame + central action ROI (`SSIM`, `dHash`, 16-bin luma histogram cosine), rejecting clones even under renamed `setup_type`/camera labels and verifying callbacks actually changed pixels.
  - Updated `audit_intra_shot_motion()` to enforce `max_static_hold_sec`, mask captions (`64%..82%`), inspect ROI MAD + 4 Hz timeline contiguous dead holds.
  - Updated `audit_transition_continuity()` to verify 5-sample progression + intermediate `raw_traces` transition telemetry against hard-cut or `executed_in_renderer=True` spoofing and invoke `finalize_transition_edl_verification()`.
  - `run_scene_diversity_qa()` now emits `visual_qc_timeline.json` and writes flag crops into `logs/qc_flags/` only on failing shots.
- **`director/quality_gate.py` & `director/run.py`**: Propagated `max_static_hold_sec`, added fail-closed `checks["camera_execution"]`, added `release_status` (`TECHNICAL_ACCEPTANCE_PASS` vs `FAIL`) and `subjective_visual_review` / `subjective_editorial_listening = "NOT_VERIFIED"` into `qc_report.json` & `run_manifest.json`.

### Windows Portability & Audio Sync (`G7`)
- **`director/preflight.py`, `director/assets/__init__.py`, `director/assets/breakdown_adapter.py`, `director/assets/map_route_adapter.py`, `director/provenance_guard.py`, `director/quality_gate.py`**: Added `link_kit_node_modules()` junction fallback on Windows, accepted junctions in `audit_style_lock()`, normalized Windows paths in `_check_resolved_path()`, added `probe_windows_sapi_voices()`, Chrome/Edge probing, `d3d11` default, and `DiskBudgetGuard`.
- **`director/parse_script.py`**: Added Windows `System.Speech` TTS synthesis (`-EncodedCommand`, `Rate=1`).
- **`director/edit_timeline.py`**: Enforced `scale=...:out_range=tv,format=yuv420p -pix_fmt yuv420p -color_range tv` on 1080p and 4K encodes (curing FFmpeg 9 `yuvj420p`).
- **`director/mix_audio.py`**: Updated `_master_pre_to_final_wav` to `alimiter(level=false) -> loudnorm(TP=-2.4) -> lowpass(18kHz) -> alimiter(limit=0.74, level=false)` curing AAC transient overshoot (`smoke_breakdown`: `-15.6 LUFS, -2.4 dBTP`).
- **`director/audio_dsp.py`, `director/audio_catalog.py`, `director/sfx_director.py`, `director/audio_narrative.py`**: Added 6 elevator/mechanical SFX generators (`elevator_button_click`, `relay_cabinet_click`, `motor_drive_hum`, `sheave_cable_whir`, `door_slide_open`, `elevator_arrival_chime`) and bound `elevator_button_click` strictly to `contact_action["hit_time_rel_sec"]` while scoping Roman foley per shot rather than global motif leaks.

---

## 2. T01–T20 Test & Verification Status Matrix (`tests/test_zdf_motion01.py`)

| Gate | Requirement Verified | Method & Status |
|---|---|---|
| `T01` | Three.js telemetry == planned `camera_paths.json` (pos, quat, FOV, focal UV) | `test_t01_t02_t03`: **PASS** (`worst_pos_err_m <= 0.02`, `ori <= 0.65°`) |
| `T02` | Tampered/hardcoded camera pos divergence fails closed | `test_t01_t02_t03`: **PASS** (tampered trace -> `FAIL`) |
| `T03` | Floor penetration & wall collider intersection rejected | `test_t01_t02_t03`: **PASS** (`evaluate_camera_trace_accuracy` & bounds check `FAIL`) |
| `T04` | Planned transitions start unverified; genuine 2-source wipe/blend verified on decoded frames | `test_t04_t05`: **PASS** (`VERIFIED_DECODED`, `executed_in_renderer=True`) |
| `T05` | Hard-cut spoofed as `zoom_through` & pre-set `executed_in_renderer=True` rejected | `test_t04_t05`: **PASS** (`audit_transition_continuity == FAIL`) |
| `T06` | Character registry invariant across shots; mutation raises `UnsupportedSceneError`; zero `shirt_palette` | `test_t06_t07_t08`: **PASS** |
| `T07` | Real WebGL 2-bone IK finger contact on elevator button (`world_error_m <= 0.025m`); miss tamper fails | `test_t06_t07_t08`: **PASS** (hero `0.000m`, tampered `0.095m` -> `FAIL`) |
| `T08` | Real Three.js `LayeredCutaway` (`clippingPlanes`, `layers_count >= 3`, `components_count >= 2`); empty tamper fails | `test_t06_t07_t08`: **PASS** |
| `T09` | Per-shot mixed-domain dispatch (`Roman -> phone -> cosmos`) | `test_t09_t10`: **PASS** |
| `T10` | Unsupported exact domain (`bicycle shifts gears`) fails when strict & flags `UNSUPPORTED_EXACT_ARCHETYPE_FALLBACK_SCHEMATIC` otherwise | `test_t09_t10`: **PASS** |
| `T11` | Non-adjacent visual clone detection across differing `setup_type`/camera labels | `test_t11_t12`: **PASS** (`shot_00->shot_02` -> `FAIL`) |
| `T12` | Caption-only motion on frozen scene + `max_static_hold_sec` propagation rejected | `test_t11_t12`: **PASS** |
| `T13` | `elevator_button_click` SFX locked to `hit_time_sec` (`<= 0.034s`), LUFS/TP QA | `test_t13_to_t20`: **PASS** |
| `T14`–`T20` | Style lock error, 5-engine isolation, seed determinism, `DiskBudgetGuard`, validation fail-closed, camera lock, `>=4` hero stages | `test_t13_to_t20` + `smoke_all_engines`: **PASS** |

---

## 3. Acceptance Deliverables, Performance, Backtests & Unchanged Boundaries

### New Native 4K Elevator Hero Demo (`runs/zdf_motion01_elevator_20261117_0131Z/`)
- **Runtime**: `303.19s` total (`stills: 11.8s`, `scene render: 208.19s`, `workers: 2`, ANGLE `d3d11`, `disk_free_gb_at_start: 54.13`, directory size `182.72 MB`)
- **Video Contract**: `2160x3840` (`native_4k: true`), `1080x1920` preview, H.264 `yuv420p`, `30.0 fps`, `31.597s`, `8` shots, `7` unique setups, `0` adjacent repeats
- **Verified Camera & Action Metrics**: `84` sampled frames, `worst_pos_err_m: 0.0`, `worst_ori_err_deg: 0.155`, `worst_fov_err_deg: 0.0`, `worst_contact_err_m: 0.0`, `cutaway_checks: 6`, `7/7` transitions `VERIFIED_DECODED`, `max_dead_hold_sec_observed: 0.0`
- **Verified Audio Metrics**: `-14.9 LUFS`, `-1.5 dBTP`, `22/22` grounded SFX cues, `audio_qc_status: PASS`
- **Subjective Flags**: `subjective_visual_review: NOT_VERIFIED`, `subjective_editorial_listening: NOT_VERIFIED`, `release_status: TECHNICAL_ACCEPTANCE_PASS`

### Three Low-Cost Backtests (`docs/implementation_runs/ZDF-MOTION-01_20261117_0131Z/logs/backtests_report.json`)
| Backtest | Duration | Shot Routing Verified | QA / Camera Trace Result |
|---|---|---|---|
| `roman_gladiator` | `10.113s` | `zach3d:roman_historical_stage`, `zach3d:studio_demonstrator_stage`, `zach3d:roman_historical_stage` | `PASS` (`pos_err: 0.0`, `ori_err: 0.165°`) |
| `bicycle_unsupported` | `26.410s` | `shot_00` flagged `zach3d:schematic_mechanism_stage` / `UNSUPPORTED_EXACT_ARCHETYPE_FALLBACK_SCHEMATIC` (no Roman armor leak) | `PASS` (`pos_err: 0.0`, `ori_err: 0.153°`) |
| `mixed_roman_phone_cosmos` | `10.582s` | `roman_historical_stage` -> `human_device_stage` -> `network_relay_stage` -> `cosmic_scale_bridge_stage` | `PASS` (`pos_err: 0.0`, `ori_err: 0.162°`, `contact_err: 0.0m`) |

### Unchanged Components (Preserved Intact)
- `vendor/claude-animation-skills` tracked submodule files & pinned commit `5dbea55c23aa6a5c93dc3cfb5583840513b56b94` (0 modifications).
- Single-skill lock policies in `director/route_styles.py` and core engine separation across the remaining 5 engines (`stick-figure`, `minimalistic-graphics`, `graph`, `map-route`, `breakdown` — zero foreign geometry adapters mixed).
- Existing audio license/catalog security suite (`tests/test_audio_catalog_and_licenses.py`).
