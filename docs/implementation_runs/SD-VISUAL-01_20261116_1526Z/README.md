# `SD-VISUAL-01` Implementation Run Log — `2026-11-16T15:26Z`

## 0. Baseline Audit (Pre-Code)

- **Workspace Root**: `/Users/macbook/.gemini/antigravity/scratch/short-director`
- **Git Branch & HEAD**: `master` @ `b68c1bee2702635cb95c4375612736bc7c5fed43`
- **Remote Origin**: `https://github.com/quocan050302/Skill-Animation-Video.git`
- **Working Tree Before Edits**: Clean (existing `runs/` untouched: `acceptance_stick_figure`, `roman_gladiator_zdf`, `sd_audio_demo_sf`)
- **Upstream Submodule (`vendor/claude-animation-skills`)**: Pinned SHA `5dbea55c23aa6a5c93dc3cfb5583840513b56b94`, `git status --porcelain` clean
- **Host Toolchain**:
  - Python `3.13.0`, Node.js `v22.22.3`, FFmpeg `6.0`, FFprobe `4.4-tessus`
  - Playwright `1.49.1` Chromium (`arm64` Apple Metal WebGL backend verified)
  - Free disk at Step 0: `~18.8 GiB` (`19,713,316` 1024-blocks on `/System/Volumes/Data`)
- **Baseline Test Suite Verification**:
  - Command: `python3 -m unittest discover -s tests -v`
  - Result: **`Ran 27 tests in 283.680s` -> `OK` (`EXIT=0`)**, logged at `docs/implementation_runs/SD-VISUAL-01_20261116_1526Z/baseline_unittest.log`

---

## 1. Inspected Baseline Signatures & Verified Limitations

1. **`director/parse_script.py::parse_script_and_build_voice`, `analyze_facts_and_entities`**:
   - Emits `sentences`, `beats` (sentence-level), `entities_and_facts` (`user_numbers`, `detected_motifs` weighted toward early clock/brain/armor/Roman keywords), and word timestamps (`voice.words`).
   - Limitation: Long 5–8s sentences stay grouped into single beats unless total shots < 4.
2. **`director/build_storyboard.py::ENGINE_CAMERA_GRAMMAR`, `build_storyboard_and_bible`**:
   - Cycles through a small `mid_pool[(i - 1) % len(mid_pool)]` and `motifs[i % len(motifs)]`, causing adjacent repetition on longer scripts.
   - When splitting `<4` shots (lines 150–158), copies identical `seg["text"]` into both left and right halves.
   - Outputs static `transition_out` labels without a dedicated transition EDL or continuous motion/camera path trace.
3. **`director/assets/zach_d_films_adapter.py::_build_zach_shots_js`, `_roman_shot_code`, `_generic_armor_shot_code`, `generate_engine_project`**:
   - Non-Roman prompts fall directly into `_generic_armor_shot_code(i, s, total_shots)`, clothing characters in `'vest' | 'chainmail' | 'plate' | 'archer'` beside `forcePedestal` + `energyCore` regardless of whether the story is about smartphones, networks, biology, energy grids, or space.
   - Inspection of unmodified `vendor/claude-animation-skills/skills/zach-d-films/engine/src/human.js` confirms `makeHuman('plain')` cleanly builds an unarmored stylized character onto which custom procedural clothing/props/cutaways can be mounted purely in `engine_work/src/` (`novel_props.js` + modular scene families).
4. **Other 5 Engines (`stick_figure_adapter.py`, `minimalistic_graphics_adapter.py`, `graph_adapter.py`, `map_route_adapter.py`, `breakdown_adapter.py`)**:
   - Each uses clean engine-specific templates (`Canvas2D`, `SVG+GSAP`, `SVG+GSAP+viewportG`, `Three.js InstancedMesh`, `Three.js RoomEnvironment`), but `shots.js` / `renderAtTime(t)` only switches between 3–4 hardcoded `setup_type` strings and does not execute in-shot event timelines, diverse scene families, or full EDL-backed transition continuity.
5. **`director/render_node.mjs`, `director/render_scene.py`, `director/edit_timeline.py`**:
   - Already renders pure deterministic `renderAtTime(t)` via `image2pipe` (`0 bytes` raw intermediate PNGs).
   - Transition execution currently relies solely on per-frame transitions inside HTML/JS (`stick-figure` whip/iris mask, `zach-d-films` `FADES`), while `match_zoom` / `cut_on_action` / portal / mask wipes on non-`stick-figure` engines are largely metadata-only.
6. **`director/audio_narrative.py::extract_sound_events`, `build_audio_narrative_plan`**:
   - Reads `shot.staging.visual_events`, `setup_type`, `props`, and `transition_out`. Expanding `shot.staging.visual_events` directly from a grounded `VisualEventGraph` enables seamless SFX sync within `<=1` frame without breaking any v0.3 audio/license/LUFS invariant.
7. **`director/quality_gate.py::run_final_quality_gate`, `audit_style_lock`**:
   - Checks only basic 2-frame `frame_mad` motion + `blackdetect`, with no pHash/SSIM adjacency deduplication, semantic novelty diversity score, camera trace audit, or transition continuity audit.

---

## 2. Planned Architecture (`SD-VISUAL-01`)

1. **`director/visual_event_graph.py`** -> `<run>/visual_events.json`
2. **`director/shot_director.py`** -> `<run>/shot_coverage.json` (feeding enriched `storyboard.json` + `--edit-energy`, `--scene-novelty`, `--max-static-hold-sec`, `--visual-plan-in`)
3. **`director/camera_choreographer.py` & `director/transition_director.py`** -> `<run>/camera_paths.json` + `<run>/transition_edl.json` (`--transition-policy`)
4. **`director/scene_asset_factory.py`** + deeper multi-family **Three.js 3D scene synthesis** in `zach_d_films_adapter.py` (human+device, network/cable, data center/power grid, cutaway anatomical/device layer reveal, cosmic/macro-micro bridge, transformed callback, plus silhouette/camera bounds validator) + honest distinct upgrades in `stick-figure`, `minimalistic-graphics`, `graph`, `map-route`, and `breakdown`
5. **Audio Sync Hook**: link visual event anchors directly into `audio_narrative.py` / `sfx_director.py` (action-matched Foley + dynamic breath pauses) while preserving all v0.3 LUFS/TP/license/remux guarantees
6. **`director/scene_diversity_qa.py`** + `quality_gate.py` integration -> `<run>/scene_diversity_report.json`
7. **Full Regression & Original 25–35s 3D Science Demo + All-Engine Tests -> Commit & Push**

---

## 3. Delivered Results, Visual Audit Catches & Final Verification (`v0.4.0`)

### Visual & Functional Catches Fixed During Execution
1. **Three.js Shirt Mesh Z-Fighting & Shot 0 Headroom (`director/assets/zach_d_films_adapter.py`)**: Visual inspection of `runs/sd_visual_demo_zdf/stills/` initially revealed horizontal z-fighting wave bands on `makeModernOutfitCharacter` where a generic `CylinderGeometry` intersected `human.js`'s tapered `torsoShell`, plus tight top headroom in `human_device_stage`. Replacing the cylinder with `torsoShell(0.18, 0.54, 0.018)` / `torsoShell(-0.14, 0.20, 0.016)` imported cleanly from `'./human.js'` (without mutating `vendor/`) and pulling `human_device_stage` camera `z` from `2.58..2.08` to `2.78..2.28` (`lookAt y=1.20`) completely eliminated the artifacts in the final `contact_sheet.jpg`, `still_1.567.png`, and `still_26.855.png`.
2. **Scoped `motif` ReferenceError in `stick-figure` Backdrop (`director/assets/stick_figure_adapter.py`)**: Full-suite run (`task-849`) caught a misplaced `else if (motif === ...)` branch inside `drawStudioBackdrop` causing `test_b1`, `test_b4`, and `test_seeded_frame_hashes_and_serial_vs_concurrent_parity` to raise `ReferenceError: motif is not defined`. Removed the stray branch cleanly inside `drawStudioBackdrop` (`drawPropMotif` already owns motif drawing).
3. **Domain Prop Rule Ordering & Causal Splits (`director/visual_event_graph.py`, `director/shot_director.py`)**: Prioritized `power_turbine` ahead of generic battery matching and plural tokens (`turbines`), plus added backward causal boundary splitting (`traces? back to`) and re-classification per split span so adjacent cuts never duplicate narration or stale props.

### Verified Test Suite & Demo Runs (Post-Final-Edit)
- **Full `unittest` Suite**: `python3 -m unittest discover -s tests -v` -> **`Ran 36 tests in 385.851s` -> `OK` (`EXIT=0`)** (`docs/implementation_runs/SD-VISUAL-01_20261116_1526Z/final_unittest.log`), covering:
  - `test_visual_event_and_coverage.py` (`7/7` OK)
  - `test_visual_scene_factory_and_diversity.py` (`2/2` OK)
  - `test_audio_catalog_and_licenses.py` (`4/4` OK)
  - `test_audio_integration_smoke.py` (`3/3` OK: `stick-figure` 4K E2E + lossless `--audio-only` remix, `minimalistic-graphics`, read-only QA CC BY attribution)
  - `test_audio_mix_determinism.py` (`2/2` OK)
  - `test_audio_narrative_planning.py` (`6/6` OK)
  - `test_audio_only_remux.py` (`1/1` OK)
  - `test_determinism_and_resources.py` (`2/2` OK)
  - `test_smoke_all_engines.py` (`2/2` OK: all 5 remaining visual engines `graph`, `minimalistic-graphics`, `map-route`, `breakdown`, `zach-d-films` + unmodified `vendor/claude-animation-skills`)
  - `test_unit_and_negative.py` (`7/7` OK)
- **Original 3D `zach-d-films` Native 4K Demo (`runs/sd_visual_demo_zdf/`, logged at `docs/implementation_runs/SD-VISUAL-01_20261116_1526Z/demo_zdf_run.log`)**:
  - `27.80s` (`2160x3840 @ 30 fps`, `native_4k: true`, `42,914,486` bytes final 4K MP4; `158M` total run dir), `177.14s` total elapsed (`90.62s` Metal WebGL render on 4 workers).
  - `12` shots, `9` unique setups across `10` `scene_family` keys, `0` adjacent identical setups, `0` adjacent identical camera triples, `19` intra-shot visual events (`31` visual beats), `11` frame-verified transitions (`cut_on_action`, GLSL `zoom_through`), `16/16` grounded SFX cues, `-14.0 LUFS / -1.8 dBTP`, `overall_qc_status = PASS`, `scene_diversity_status = PASS`, `audio_qc_status = PASS`, `subjective_visual_review = NOT_VERIFIED`, `subjective_editorial_listening = NOT_VERIFIED`.
- **Upstream Submodule Integrity**: `git -C vendor/claude-animation-skills status --porcelain` = empty (`5dbea55c23aa6a5c93dc3cfb5583840513b56b94` unmodified).
