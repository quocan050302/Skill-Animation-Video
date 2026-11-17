# Skill-Animation-Video

## Short Director (`v0.4.0`) — Antigravity Plugin

Production-hardened vertical shorts (`9:16`, `1080x1920` preview + `2160x3840` 4K delivery at `30`/`60` fps) built for Google Antigravity with a **machine-enforceable, fail-closed single-skill lock**, **semantic visual event & continuous shot direction (`SD-VISUAL-01`)**, and **narrative music & licensed SFX direction (`SD-AUDIO-01`)**.

## Supported Engines (Strict Single-Skill Lock)

| Skill Name | Visual System & Grammar | Native 4K Support |
|---|---|---|
| `stick-figure` | Expressive 2D cartoon world, oversized-head stick rigs, arm IK, cel outlines, novel cutaway/split stages, whip & iris-mask transitions, Poppins Bold 1–2 word pop captions | **Native `2160x3840`** (`Canvas2D` vector `scale=2`) |
| `zach-d-films` | 3D procedural cartoon studio explainer (`Three.js`), PMREM softbox sky, slow-motion force-ripple impacts, sparks, ACES Filmic bloom, Montserrat captions | **Native `2160x3840`** (`WebGLRenderer` `pixelRatio=2` on Metal) or labeled Lanczos upscale |
| `graph` | High-contrast editorial Catmull-Rom line chart (`Inter` + `Inter Tight`), tabular live counter, inflection slope tangent & delta stems (never invents chart figures) | **Native `2160x3840`** (`SVG` + `DOM` `deviceScaleFactor=2`) |
| `minimalistic-graphics` | Pure black-and-white hairline line art (`#000` / `#f4f4f4`), solitary dot protagonist, pendulum momentum & rising step arcs, quiet lowercase Poppins captions | **Native `2160x3840`** (`SVG` + `DOM` `deviceScaleFactor=2`) |
| `map-route` | Matte white 3D instanced city blocks, parks, river, animated route ribbon, bouncing red pin, ETA & destination cards, explicit `SCHEMATIC 3D ROUTE` non-GIS disclosure | **Native `2160x3840`** (`WebGL` + `DOM` `deviceScaleFactor=2`) or labeled Lanczos upscale |
| `breakdown` | Dark studio 3D PBR exploded-view assembly (`RoomEnvironment`), 6 axial layers, JetBrains Mono right-column callouts, animated SVG elbow leader lines | **Native `2160x3840`** (`WebGL` + `DOM` `deviceScaleFactor=2`) or labeled Lanczos upscale |

## Installation in Google Antigravity

### Option 1: Global User Plugin (`~/.gemini/config/plugins/`)
Link or copy the plugin bundle into `~/.gemini/config/plugins/short-director`:
```bash
mkdir -p ~/.gemini/config/plugins/short-director
cp -R plugin.json README.md assets rules skills ~/.gemini/config/plugins/short-director/
```

### Option 2: Workspace Plugin Discovery (`.agents/plugins/`)
Open `/Users/macbook/.gemini/antigravity/scratch/short-director` as your active Antigravity workspace. `.agents/plugins/short-director` is pre-configured so Antigravity discovers the plugin automatically.

### Option 3: Antigravity CLI (`agy`)
If using the `agy` CLI:
```bash
agy plugin install /Users/macbook/.gemini/antigravity/scratch/short-director
```

*(Note: Never invoke `vendor/claude-animation-skills/install.sh` — that upstream script registers Claude Code `~/.claude/skills` symlinks rather than Antigravity plugins.)*

## Usage

### In Antigravity Chat (`/short-director`)
```text
/short-director --skill stick-figure Why does a 20-minute power nap sharpen memory while a 60-minute nap makes you groggy?
/short-director --skill graph Monthly users climbed from 1,200 in Jan to 4,800 in Mar, 19,500 in Jun, and 84,000 in Sep
/short-director Home to Harbour Station, 3.2 km in 10 minutes
```

### Direct CLI Execution (`director/run.py`)
```bash
cd /Users/macbook/.gemini/antigravity/scratch/short-director
python3 -m director.run \
  --skill stick-figure \
  --out-dir runs/my_short \
  --fps 30 \
  --seed 42 \
  --render-4k-mode native \
  "Your fresh script or question here"
```

## Multi-Theme Editorial Design, Physical Motion & Character Grounding (`SD-RETENTION-03`)
- **Semantic Editorial Design System (`editorial_design_system.py`, `editorial_theme_renderer.py`, `curiosity_director.py`)**: Maps narrative beats to distinct semantic roles (`location_time`, `curiosity_headline`, `warning_danger`, `verified_fact`, `explanation`, `aftermath_sober`, `transition_emphasis`) with 2+ variants per role (`--editorial-theme role-aware|legacy`), SVG outlined two-tone hero headlines (`<= 2` per reel), black-stroked red impact arrows pointing to verified 3D anchors (`tip_target_error_px <= 36px`), mobile 320/360/390/1080 layout verification, strict early-spoiler reveal locks, and persisted `editorial_design_tokens.json` / `editorial_roles_plan.json` / `pointer_tracking.json` (scoped strictly to `zach-d-films`).
- **Deterministic Physical Motion & Boston Wave Repair (`physical_motion.py`, `assets/physical_motion_primitives.py`, `assets/zdf_boston_molasses_scenes.py`, `assets/zdf_tacoma_bridge_scenes.py`)**: Pure stateless `pose(t)` curves for beams, torsional bridge decks, parabolic collapse trajectories, and coastal waves; replaces Boston's disconnected spheres with a continuous `40x22` deformable viscous heightfield mesh and builds an 8-scene stylized-illustrative 1940 Tacoma Narrows suspension bridge library (`cables_attached: true`, `world_state_telemetry.json`).
- **Foot-Locked Character Performance (`character_performance.py`, `assets/character_performance.py`)**: Analytic FK step stride + `drop` sole-to-ground leveling matched to `human.js` skeleton geometry (`thigh=0.44`, `shin=0.45`, `sole=0.0735`), keeping stance foot slide `<= 0.08m`, floor penetration `<= 0.03m`, and threat-retreat heading verifiable in `character_performance_telemetry.json`.
- **Cinematic Composition, Role SFX & False-Pass-Proof QA (`cinematic_composition.py`, `cinematic_composition_qa.py`, `audio_narrative.py`, `visual_storytelling_qa.py`, `retention_qa.py`)**: Audits 9:16 negative-space vs caption separation (`composition_report.json`), adds calm `silent_context` / `silent_sober` editorial discipline, role-mapped DSP cues (`headline_hit_warm`, `warning_tension_pulse`, `wind_bridge_gust`, `steel_cable_groan`, `span_collapse_splash`), pre-collapse silence anticipation ducks, and fail-closed `build_ab_alignment` (`script_similarity >= 0.85`, no blind shot-index fallback).
- **New Editorial Controls**: `--editorial-theme role-aware|legacy`, `--curiosity-layer auto|off`.

## Expressive Editorial Upgrade (`SD-RETENTION-01`)
- **Semantic Voice Prosody & Capability Truth (`voice_prosody.py`, `parse_script.py`, `preflight.py`)**: Decomposes sentences into expressive phrase units with emphasis keyword scoring, token conservation guards, controlled pauses, SAPI5 SSML `<prosody>/<emphasis>/<break>` (or Kokoro/macOS speed+silence), waveform prosody verification (`voice_delivery_report.json`), honest `neural_prosody` / `word_anchor_confidence="ESTIMATED"` disclosures, and `--voice-compare-ab` side-by-side probes (`voice_ab_probe.wav`).
- **Kinetic Typography & Smart 3D Callouts (`editorial_overlay.py`, `zach_d_films_adapter.py`)**: Unifies captions, overlays, and SFX timing onto `editorial_timeline.json`; renders word-synced emphasis pops/underlines plus `THREE.Raycaster`-occluded & `camera.project`-tracked focus rings, leader arrows, and fact-grounded counters strictly inside the portrait safe margin in `zach-d-films` without bleeding into the other 5 visual engines.
- **Motivated Editorial Audio Sync (`audio_dsp.py`, `audio_narrative.py`, `mix_audio.py`)**: Warm non-fatiguing DSP cues (`ui_pop_soft`, `marker_ring_draw`, `arrow_swish`, `reveal_soft`, `low_sting`, `airflow_hiss`), overlay timestamp locking, anti-double-pop guards, and twist-beat music contrast ducking.
- **Evidence-Based Retention QA (`retention_qa.py`, `quality_gate.py`)**: Audits voice delivery waves, tracking telemetry, decoded overlay pixel deltas, SFX sync, and fatigue bounds into `editorial_qa_report.json` while keeping `subjective_visual_review`, `subjective_editorial_listening`, `subjective_voice_quality_status`, and `viewer_retention_status` explicitly labeled `NOT_VERIFIED` without human review.
- **New CLI Flags**: `--voice-style legacy|natural|cinematic`, `--voice-backend auto|kokoro|windows_sapi|macos_say`, `--voice-prosody-in PATH`, `--voice-pause-strength FLOAT`, `--voice-compare-ab`, `--caption-mode plain|kinetic|phrase`, `--callout-mode off|smart`, `--verified-numbers-json PATH`.

## Event-Driven Visual Storytelling & Fail-Closed QA (`SD-RETENTION-02`)
- **Story Action Graph & World-State Progression (`visual_storytelling_director.py`, `build_storyboard.py`, `shot_director.py`)**: Plans explicit `story_action_graph.json` (`narrative_event_id`, location IDs, physical actions, world-state causality) and enforces causal reveal ordering (`reveal_order` locks preventing premature term/statistic spoilers on hook shots) across arbitrary 3D storytelling topics, plus modular 1919 Boston scenes (`director/assets/zdf_boston_molasses_scenes.py`) with Three.js mechanical contact & `LayeredCutaway` geometry.
- **Voice Fidelity, Candidates & Seam Smoothing (`voice_candidate_eval.py`, `parse_script.py`, `preflight.py`, `voice_prosody.py`)**: Supports `--voice-id` routing, 12 ms raised-cosine phrase-boundary fades eliminating splice clicks, Windows `-File` `.ps1` SAPI5 synthesis avoiding long-SSML command-line limits, and multi-candidate WAV export + `VOICE_LISTENING_CHECKLIST.md`.
- **Flex Kinetic Captions & Grounded Callouts (`editorial_overlay.py`, `zach_d_films_adapter.py`)**: Renders flex-wrapped captions with measured inter-word DOM gaps (`columnGap: 0.40em`, active scale capped at `1.05x`), mobile-legible smart callout boxes, bespoke disaster/foley DSP cues (`audio_dsp.py`, `sfx_director.py`), and `--historical-claims-json` / `--factual-sources-note` validation.
- **False-Pass-Proof Post-Render QA (`visual_storytelling_qa.py`, `retention_qa.py`, `quality_gate.py`)**: Fixes `audit_overlay_render` using true spatial luma std (`patch.mean(axis=2)`), Chromium DOM telemetry, and optional ON/OFF ROI MAD diffing; replaces timestamp-only A/B diffing with event-aligned `ab_alignment.json` (`compare_ab_versions`); and audits `story_action_coverage`, `reveal_order_decoded`, `caption_layout`, `period_integrity`, and `historical_claims` into `visual_storytelling_qa_report.json`.

## Continuous Shot Direction & Scene Novelty (`v0.4.0` Changelog)
- **Semantic Visual Event Graph (`visual_event_graph.py`)**: Extracts subjects, verbs, props, causality, scale shifts, and word-anchored event windows (`visual_events.json`) directly from narration + verified audio timing.
- **Anti-Repetition Coverage Planner (`shot_director.py`)**: Replaces cyclic shot templates and duplicated split text with candidate generation, rolling 3-shot diversity scoring, justified transformed callbacks, intra-shot transformation schedules, and non-overlapping narration spans (`shot_coverage.json`).
- **Camera Choreography & Transition EDL (`camera_choreographer.py`, `transition_director.py`)**: Deterministic seeded trajectories (`camera_paths.json`) and rendered transitions (`zoom_through`, `whip_pan`, `match_cut`, `object_wipe`, `iris_mask`, `match_zoom`) recorded with frame-level verification (`transition_edl.json`).
- **Multi-Family 3D & Single-Skill Asset Factory (`scene_asset_factory.py`, `zach_d_films_adapter.py`)**: Non-Roman scripts generate domain-matched Three.js procedural scenes (human + smartphone tap, glass-peel PCB cutaway, RF tower, subsea fiber cable, data center aisle, power turbine, cosmic star-forge, anatomical cutaway) instead of falling back to armored characters; all other 5 skills receive honest engine-native upgrades.
- **Scene Diversity & Continuity QA (`scene_diversity_qa.py`)**: Caption-masked pHash/SSIM adjacency deduplication, live intra-shot motion checks, and seam verification written to `scene_diversity_report.json`.
- **New Editorial Controls**: `--edit-energy calm|balanced|dynamic`, `--scene-novelty standard|high`, `--transition-policy motivated|simple`, `--max-static-hold-sec`, `--visual-plan-in`.

## Narrative Music & SFX Director (`v0.3.0` Retained)
- **Visual-Grounded Audio Direction** (`audio_narrative.py`, `music_director.py`, `sfx_director.py`): Aligns cohesive thematic music arcs and frame-accurate Foley/SFX directly to shot setups, grounded objects, and transitions rather than generic per-cut pops/whooshes.
- **Optional Read-Only `QA-Unified-Video-Studio` Integration** (`audio_catalog.py`): Supports `--qa-audio-root <path>` or `SHORT_DIRECTOR_QA_ROOT` with SHA-256 verification, `ffprobe` decodability checks, path-traversal guards, commercial rights gating, and automatic `audio/credits_audio.txt` attribution (falling back cleanly to procedural synthesis with `QA_LIBRARY_UNAVAILABLE` when absent).
- **Audio Switches & Lossless `--audio-only` Remix**: `--music-mode auto|procedural|qa-library|file|off`, `--sfx-mode auto|procedural|qa-library|off`, `--sfx-density sparse|balanced|detailed`, `--music-gain-db`, `--sfx-gain-db`, `--music-intensity`, `--audio-plan-in`, `--audio-only` (preserves video packets losslessly via `-c:v copy`), and `--voice-mode auto|off`.
- **Single-Pass Mastering & Post-Encode Audio QC**: `audio/voice.wav`, `music.wav`, `sfx.wav`, `ambience.wav`, `master_pre.wav`, `mix.wav`, plus post-AAC `ebur128` LUFS/True Peak, onset, intelligibility, boundary-click, and license QC in `audio/audio_qc_report.json`.

## Outputs Per Run

Every completed run writes verified artifacts to `<out-dir>/`:
- `style_decisions.json` — Immutable `selection_mode`, `selected_skill`, `style_lock`, and upstream commit provenance
- `visual_events.json`, `story_action_graph.json`, `shot_coverage.json`, `camera_paths.json`, `transition_edl.json` — Semantic event graph, narrative story action graph, anti-repetition shot coverage, camera keyframe traces, and frame-verified transition EDL
- `storyboard.json` & `art_bible.md` — Per-shot camera blocking, setups, transitions, style parameters, and `visual_assets` inventory
- `editorial_timeline.json`, `editorial_design_tokens.json`, `editorial_roles_plan.json`, `composition_report.json`, `pointer_tracking.json`, `world_state_telemetry.json`, `character_performance_telemetry.json`, `overlay_plan.json`, `overlay_coverage.json`, `editorial_qa_report.json`, `editorial_attention_timeline.json`, `visual_storytelling_qa_report.json` — Unified editorial timing, multi-theme tokens/role plans, 9:16 composition collision checks, settled pointer tracking error, continuous mesh deformation, foot-grounded character telemetry, and fail-closed storytelling/editorial QA
- `scene_diversity_report.json` & `style_lock_audit.json` — Caption-masked SSIM/dHash diversity QA plus recursive source & `sys.addaudithook` single-skill provenance audit
- `audio/` — `audio_plan.json`, `voice_prosody_plan.json`, `prosody_script.md`, `voice_delivery_report.json`, `audio_director_notes.md`, `music_cue_sheet.json`, `sfx_cue_sheet.json`, `audio_asset_manifest.json`, `audio_mix_report.json`, `audio_qc_report.json`, `credits_audio.txt`, and 48 kHz stereo stems (`voice.wav`, `music.wav`, `sfx.wav`, `ambience.wav`, `master_pre.wav`, `mix.wav`)
- `stills/` & `contact_sheet.jpg` — First, busiest, and end frames of every shot plus 9:16 safe-area sheet
- `preview_1080.mp4` — `1080x1920` H.264 + single-pass `-14 LUFS` AAC stereo preview
- `final_4k.mp4` — `2160x3840` H.264 + single-pass `-14 LUFS` AAC stereo master (with truthful `native_4k` vs `upscaled` declaration)
- `qc_report.json` & `run_manifest.json` — Complete `PASS`/`FAIL`/`WARN`/`NOT_RUN` technical QC report and `ffprobe`/audio metrics

## Running the Test Suite

```bash
python -m unittest discover -s tests -v
python tools/run_validation_async.py --mode full --workers 2
```

## SD-RETENTION-03.R2 Status & Remaining Work (Branch `feat/sd-retention-03-r2-visual-quality`)

Chi tiết đầy đủ xem tại [docs/implementation_runs/SD-RETENTION-03_R2_20261117_1135Z/README.md](docs/implementation_runs/SD-RETENTION-03_R2_20261117_1135Z/README.md).

- **Đã hoàn thành hôm nay (2026-11-17)**:
  - R2.1 `director/decoded_visual_quality.py` + semantic matte pass WebGL + camera-compensated physical motion + mobile `320/360/390/1080` composition QA + fail-closed pointer zero-tip audit.
  - Sửa hình học cầu Tacoma (`zdf_tacoma_bridge_scenes.py`), đồng bộ splash/âm thanh, bổ sung `tagSemantic` cho toàn bộ cảnh Boston (`zdf_boston_molasses_scenes.py`), chặn truyền nhầm `contact_action` (`shot_director.py`), và hoàn thiện bộ cảnh mới Skyscraper 3D + TMD cutaway (`zdf_skyscraper_scenes.py`).
  - Hoàn thiện 32 bẫy `T01`–`T32` (`tests/test_r2_decoded_and_traps.py`) và phủ 100% file `tests/test_*.py` vào `tools/run_validation_async.py` (bao gồm 3 suite audio trước đây bị thiếu).
  - Đã render & PASS QC đầy đủ: **Skyscraper `baseline_A` + `enhanced_B` (Native 4K `2160x3840`, A/B VO PCM parity)** và **Tacoma 1940 Repair Proof**. Checkpoint 15/15 test mục tiêu vừa chạy đạt `OK`.
- **Việc còn lại cần làm nốt ngày mai**:
  1. Thêm preset góc máy xen kẽ cho split shot ở `boston_street_hook`, `boston_tank_rupture`, `boston_elevated_rail_impact` trong `director/shot_director.py` để Boston Proof hết 3 lỗi lặp triplet (`0->1`, `4->5`, `8->9`) và tạo `boston_r2_360_sheet.jpg`.
  2. Chỉnh lại mốc lấy mẫu đỉnh xoắn/sập cho ảnh đối chiếu `tacoma_before_vs_after_360.jpg`.
  3. Chạy trọn bộ `python tools/run_validation_async.py --mode full --workers 2` và `python -m unittest discover -s tests -v` **sau lần sửa code cuối**, rồi chốt `SHA256SUMS.txt` / `gates_status.csv` / `final_manifest.json` và commit/push bản hoàn chỉnh.
