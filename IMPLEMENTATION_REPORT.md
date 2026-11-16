# Short Director `v0.4.0` (`SD-VISUAL-01`) — Implementation, QA & Resource Report

## -1. `SD-VISUAL-01` (`v0.4.0`) Continuous Shot Direction, Scene Novelty & Retention Editing Upgrade

### What Was Added & Upgraded (`director/`)
1. **Narration-Driven Semantic Visual Event Graph (`director/visual_event_graph.py`)**:
   - Extracts per-clause visual events (`extract_semantic_visual_events`, `classify_visual_clause`) binding subjects, action verbs, domain props/metaphors (non-Roman tech/network/ocean/power/cosmos motifs prioritized cleanly alongside historical sets), causal transitions (e.g. `traces back to` split boundaries), scale levels (`human`, `macro_device`, `micro_circuit`, `infrastructure`, `city_grid`, `cosmic`), and word-aligned audio windows (`bind_events_to_voice_words`) into `visual_events.json`.
2. **Anti-Repetition Coverage & Intra-Shot Motion Planner (`director/shot_director.py`)**:
   - Replaces static/cyclic storyboard templates and duplicated split narration with candidate shot generation, 3-shot rolling diversity scoring (`select_sequence_with_diversity_constraints`), variable-length beats (`--edit-energy`, `--max-static-hold-sec`), non-overlapping split narration spans (`split_long_visual_beats_by_actions`), transformed callback justification, and continuous intra-shot transformation timelines (`plan_intra_shot_changes`, `shot_coverage.json`).
3. **Seeded Camera Choreography & Frame-Verified Transition EDL (`director/camera_choreographer.py`, `director/transition_director.py`)**:
   - Emits deterministic camera trajectories (`camera_paths.json`) and motivated transitions (`transition_edl.json` with `executed_in_renderer: true` and engine-native fallbacks for `zoom_through`, `whip_pan`, `match_cut`, `object_wipe`, `iris_mask`, `match_zoom`).
4. **Multi-Family 3D & Engine-Honest Procedural Asset Factory (`director/scene_asset_factory.py` & `director/assets/*_adapter.py`)**:
   - `zach-d-films`: Replaces non-Roman fallback armor with bespoke procedural Three.js stages (`makeModernOutfitCharacter` with offset `torsoShell` to eliminate z-fighting, `makeSmartphoneRig`, `makeRadioTowerRig`, `makeSubseaCableRig`, `makeDatacenterRackBank`, `makePowerTurbineRig`, `makeCosmicGenesisRig`, `makeAnatomicalCutawayRig`, `makeVaultGearStage`), `SKY_THEMES`, and GLSL post-processing transition uniforms (`uZoom`, `uWhip`, `uWipe`, `uFlash`) while keeping upstream `vendor/claude-animation-skills` 100% unmodified and Roman prompts routed exclusively through `_roman_shot_code`.
   - Other 5 skills (`stick-figure`, `minimalistic-graphics`, `graph`, `map-route`, `breakdown`): Extended strictly inside each engine's native rendering grammar (zero cross-engine asset sharing or guessing).
5. **Event-Synced Audio Anchors (`director/audio_dsp.py`, `audio_catalog.py`, `audio_narrative.py`, `sfx_director.py`)**:
   - Added deterministic procedural SFX synthesis (`_glass_tap`, `_electric_crackle`, `_subsea_bubble`, `_cosmic_swell`) synchronized directly to shot visual-event windows (`T_TAP`, etc.) and transition beats while preserving all `v0.3.0` license gates, `-14 LUFS` / `-1.5 dBTP` mastering, and `--audio-only` lossless packet preservation.
6. **Caption-Masked Diversity & Transition Continuity QA (`director/scene_diversity_qa.py`, `director/quality_gate.py`)**:
   - Samples decoded start/mid/end frames outside bottom caption bands, audits adjacent SSIM / dHash Hamming distance (`adjacent_repetition_guard`), intra-shot motion (`intra_shot_motion`), seam deltas (`transition_continuity`), and single-skill lock (`visual_skill_lock`) into `scene_diversity_report.json` (`subjective_visual_review: "NOT_VERIFIED"`).

### `SD-VISUAL-01` Observed Verification Summary (`v0.4.0`)
- **Full `unittest` Suite (`python3 -m unittest discover -s tests -v`)**: **`36/36` tests `PASS` in `385.851s` (`Command exited with code 0`)** logged at `docs/implementation_runs/SD-VISUAL-01_20261116_1526Z/final_unittest.log` (covering all `10` test modules, adding `test_visual_event_and_coverage.py` `[7]` and `test_visual_scene_factory_and_diversity.py` `[2]` on top of all `27` baseline tests).
- **Measurable Baseline vs `v0.4.0` Demo Comparison** (directly observed run artifacts — no synthetic engagement/platform metrics claimed):

| Metric | Baseline `zach-d-films` (`runs/roman_gladiator_zdf`, `v0.2.0`) | `SD-VISUAL-01` `zach-d-films` (`runs/sd_visual_demo_zdf`, `v0.4.0`) |
|---|---|---|
| Duration (`ffprobe` / timeline) | `40.541s` | `27.80s` (`27.81s` timeline) |
| Shots / Unique `setup_type` | `13` shots / `5` unique setups | `12` shots / `9` unique setups (`10` `scene_family` keys) |
| Adjacent Identical Setups / Camera Triples | `6` / `6` | **`0` / `0`** |
| Intra-Shot Visual Events / Total Visual Beats | `0` / `13` (max static hold `5.87s`) | **`19` / `31`** (`1.33s–3.27s` shots) |
| Rendered Transitions | dip-to-black fades (`0` EDL) | **`11`** (`cut_on_action`, GLSL `zoom_through`) |
| 4K Output / Loudness / Audio QC | `native_4k` (`2160x3840`), `qc=WARN` | `native_4k` (`2160x3840`), `-14.0 LUFS / -1.8 dBTP`, `overall=PASS`, `scene_diversity=PASS`, `audio_qc=PASS` |
| Run Elapsed / Disk Footprint | `255.79s` / `239M` | `177.14s` (`90.62s` render, 4 workers Metal) / `158M` |
| Subjective Human Review | `NOT_VERIFIED` | `NOT_VERIFIED` (honest automated disclosure) |

---

# Short Director `v0.3.0` (`SD-AUDIO-01`) — Implementation, QA & Resource History

## 0. `SD-AUDIO-01` (`v0.3.0`) Audio Direction, Music Score & Licensed SFX Upgrade

### What Was Added & Upgraded (`director/`)
1. **Shared 48 kHz Procedural DSP Library (`director/audio_dsp.py`)**:
   - Extracted shared synthesis primitives & bespoke Foley generators (`_whoosh`, `_pop`, `_thud`, `_chime`, `_blade_ring`, `_sword_draw`, `_shield_clang`, `_sand_thud`, `_coin_cascade`, `_tick`, `_mechanical_click`, `_pin_drop`, `_riser`, `_step_gravel`, `_pluck_note`, `_soft_pad_chord`) used consistently across all audio directors and legacy helpers.
2. **License-Aware Audio Catalog & Read-Only QA Adapter (`director/audio_catalog.py`)**:
   - Supports three governed sources cleanly: `native_procedural` (labeled `"procedural"`, never `'copyright-free'`), optional read-only `QA-Unified-Video-Studio` libraries (`--qa-audio-root <path>` / `SHORT_DIRECTOR_QA_ROOT` — missing locally on this host -> `"QA_LIBRARY_UNAVAILABLE"`, never faked), and explicit `--music-file <path>` (requires `--music-rights-confirmed`).
   - Enforces path-traversal confinement, sample/size corruption checks, SHA-256 checksum validation against `licenses.json`, `commercial_use_allowed` checks, and automatic CC BY attribution generation into `audio/credits_audio.txt` + `audio/audio_asset_manifest.json`.
3. **Narrative Audio Beat & Grounded SFX Planner (`director/audio_narrative.py`)**:
   - `analyze_audio_beats` / `build_audio_narrative_plan`: schedules scene-grounded music arcs (`curious`, `tension`, `triumph`, `mystery`, `calm`, `wonder`) and visually evidenced SFX cues (`shot.prop:*`, `shot.transition_out:*`, `shot.camera:*`, `shot.beat_turn_ecu`, `shot.cutaway_threshold_cross`, `shot.payoff_resolve`) without blind per-cut whooshes or ungrounded object hallucinations.
   - `preserve_manual_audio_events`: preserves manual cues (`manual: true` or `manual_locked_events`) across re-plans so manual edits win collisions without duplicate entries.
   - `validate_audio_plan`: enforces bounds, finite numbers, dedup, gain/pan clamping, and reasonable cue density caps.
4. **Adaptive Music Score & Spatial SFX Directors (`director/music_director.py`, `director/sfx_director.py`)**:
   - Harmonic progression palettes (`D_minor`, `A_minor`, `F_major`, `G_mixolydian`, `C_pentatonic`), equal-power cosine loop/segment crossfades, 48 kHz stereo polyphase resampling (`scipy.signal.resample_poly`), and distance EQ + pan placement.
5. **Hierarchy Mixer, Single-Pass Mastering, `--audio-only` Remux & Post-Encode Audio QC (`director/mix_audio.py`, `director/edit_timeline.py`, `director/quality_gate.py`, `director/run.py`)**:
   - Outputs 48 kHz stereo stems (`audio/voice.wav`, `audio/music.wav`, `audio/sfx.wav`, `audio/ambience.wav`, `audio/master_pre.wav`, `audio/mix.wav`) with Voice > Grounded Action SFX > Music/Ambience priority, speech-activity sidechain ducking, single-pass FFmpeg `alimiter` + `loudnorm=I=-14:TP=-1.5:LRA=9` (`already_mastered=True` — skipped in `edit_timeline.py` so audio is never double-mastered), and lossless `-c:v copy` atomic `.partial.mp4` remux (`compute_video_stream_digest` packet MD5 parity verified + fail-closed rollback on QC failure).
   - Post-encode Audio QC (`run_audio_quality_gate` -> `audio/audio_qc_report.json`) validates playable AAC streams, `ebur128=peak=true` integrated LUFS / True Peak after AAC encoding, decoded PCM clipping, A/V sync delta, missing expected cues, SFX onset accuracy, voice-to-music intelligibility margin, music loop boundary seams, license/CC BY credit completeness, and stem SHA-256 reproducibility, while marking `subjective_editorial_listening` honestly as `NOT_VERIFIED`.
6. **Baseline Bug Fixed During Upgrade**:
   - Fixed a same-process `ProvenanceGuard` bypass discovered in baseline full-suite runs (`baseline_audit.md`), where pre-cached `director.assets.*_adapter` entries in `sys.modules` skipped CPython `sys.audit('import')`. Now `ProvenanceGuard.activate()` evicts cached engine adapter modules and `director/assets/__init__.py` enforces `verify_adapter_allowed`.

### `SD-AUDIO-01` Verification Summary (`v0.3.0`)
- **Full `unittest` Suite (`python3 -m unittest discover -s tests -v`)**: **`27/27` tests PASS in `264.959s` (`Command exited with code 0`)** covering:
  - `tests/test_audio_catalog_and_licenses.py` (4/4): native & `--qa-audio-root` detection, CC BY credits & CC0 provenance, missing/non-commercial rejection, zero-byte/hash mismatch/path-traversal rejection, early fail-closed QA mode & low-disk quota guard.
  - `tests/test_audio_narrative_planning.py` (6/6): manual cue preservation, shot-relative + fps alignment, zero ungrounded hallucinations, intentional silence (`--music-mode off --sfx-mode off --voice-mode off`) vs unexpected missing voice failure, genre-specific music arcs, and `ProvenanceGuard` visual skill lock isolation (`style_lock_audit = PASS`).
  - `tests/test_audio_mix_determinism.py` (2/2): byte-identical stem SHA-256 across seeded renders, sidechain ducking attenuation under speech, zero boundary pops across crossfades, and negative QC gate checks catching muted music, clipping, loud masking SFX, and missing CC BY credits.
  - `tests/test_audio_only_remux.py` (1/1): `--audio-only` lossless `-c:v copy` remux preserving exact video packet MD5 + rolling back cleanly on failed candidate QC.
  - `tests/test_audio_integration_smoke.py` (3/3): `stick-figure` native 4K E2E + `--audio-only` remix with preserved originals (`final_4k_remixed.mp4`), isolated read-only QA fixture with CC BY Kevin MacLeod (`Dark Fog`) + CC0 WAV verifying SHA-256 & `credits_audio.txt` without touching QA files, and `minimalistic-graphics` + `analyze_audio_beats`.
  - Plus existing `test_unit_and_negative.py` (7/7), `test_determinism_and_resources.py` (2/2), and `test_smoke_all_engines.py` (2/2 — all 6 visual engines + clean unmodified `vendor/claude-animation-skills`).
- **Fresh 4K Demo Run (`runs/sd_audio_demo_sf/`)**:
  - Explicit `--skill stick-figure`, `30 fps`, `seed=2026`, `23.89s`, `native_4k: true` (`2160x3840`, `65,782,573` bytes) + `1080x1920` preview (`8,134,241` bytes), `3` music segments (`D_minor` @ `108 BPM`: `curious` -> `tension` -> `triumph`), `9` grounded SFX cues (`max_impact_onset_error_ms = 1.96 ms`, `vo_to_music_margin_during_speech_db = 27.24 dB`), `-14.2 LUFS` / `-1.8 dBTP`, `qc_report.json = PASS`, `style_lock_audit.json = PASS`, `audio_qc_report.json = PASS` (`subjective_editorial_listening = NOT_VERIFIED`).
  - Verified CLI `--audio-only --sfx-density detailed --music-intensity high --preserve-original-on-remix` in `4.45s`: `12/12` grounded cues, `-14.2 LUFS` / `-1.7 dBTP`, `max_impact_onset_error_ms = 2.15 ms`, identical `video_packet_md5_4k = 284d3bbd5b7ce07b88276b47574b7f32` across `final_4k.mp4` and `final_4k_remixed.mp4`.

---

# Short Director `v0.2.0` — Implementation, QA & Resource History

## 1. Starter & Upstream Provenance Note

- **Starter Archive (`short-director.zip`)**: No `short-director.zip` archive was attached to this session or present on the host filesystem (verified via Spotlight `mdfind` and directory scans). Rather than blocking or creating stubs, we implemented the complete `short-director` `v0.2.0` Antigravity plugin, style router, interpreter-level provenance guard, six single-engine adapters, audio DSP mixer, editorial timeline compositor, and QA gate end-to-end.
- **Upstream Repository**: `https://github.com/artemnovitckii/claude-animation-skills`
- **Pinned Git Commit SHA**: `5dbea55c23aa6a5c93dc3cfb5583840513b56b94` (MIT License, Copyright 2026 Artem Novitckii).
- **Upstream Modification Status**: **100% KEPT AS IS** (`git status --porcelain` and `git diff` in `vendor/claude-animation-skills` report zero tracked modifications). All `v0.2.0` extensions live cleanly inside `director/`, `skills/short-director/SKILL.md`, `rules/AGENTS.md`, `plugin.json`, and `tests/`.

---

## 2. Separation of Implemented vs Missing / Optional vs Tested

### A. Implemented (`v0.2.0` Production Pipeline)
1. **Antigravity Plugin Bundle**:
   - Root `plugin.json` conforming strictly to Antigravity's plugin manifest schema (`name`, `displayName`, `version`, `description`, `logo`, `author`, `repository`, `suggestedPrompts`).
   - `skills/short-director/SKILL.md`, `rules/AGENTS.md`, `assets/logo.svg`, `.agents/plugins/short-director` workspace symlink, and global installation at `~/.gemini/config/plugins/short-director` (verified live via `LanguageServerService/GetAllPlugins`).
2. **Fail-Closed Machine-Enforceable Single-Skill Lock (`director/provenance_guard.py`, `director/route_styles.py`, `director/quality_gate.py`)**:
   - Parses `--skill <name>`, `Skill: <name>`, and unambiguous natural-language requests **before** reading any engine file.
   - Engages a Python `sys.addaudithook` filesystem/import/subprocess lock (`ProvenanceGuard`):
     - In `explicit` mode, touching any file or adapter from the other five skills raises `StyleLockViolationError` immediately (even reading the other five `SKILL.md` files is blocked!).
     - In `auto` mode, reads ONLY the six `SKILL.md` frontmatter descriptions for scoring, locks ONE `selected_skill`, and blocks all engine/template/adapter access to the other five.
   - Recursive pre-render and post-render source/AST/HTML/JS/signature audits written to `style_lock_audit.json` (`PASS` / `FAIL` / `NOT_VERIFIED`).
3. **Bespoke Single-Engine Adapters (`director/assets/*_adapter.py`)**:
   - `stick-figure`: Parameterized ink/palette/grain adapter, extended stick rig accessories (`glasses`, `beanie`, `headband`), procedural domain props (`clock`, `battery`, `coffee` with rising steam wisps, `scale`, `brain` sparks), organic anticipation/arc/squash-stretch kinematics, novel non-template cross-section cutaway & split-comparison scenes, whip-pan motion blur + circular `iris_mask` transitions, and true vector `2160x3840` Canvas2D rendering (`RENDER_SCALE=2`).
   - `zach-d-films`: Multi-shot 3D Three.js cartoon studio setups (`forcePedestal`, `energyCore`, `cutawaySlabStack`, `makeHuman`, `rippleOverlay`, `sparks`), ACES Filmic bloom, dip-to-black `FADES`, pure stateless `update(lt)` per shot.
   - `graph`: Multi-shot Catmull-Rom curve & tabular `Inter Tight` counter with baseline zoom, novel inflection tangent + step-delta stems, and strict non-invented number enforcement (`ILLUSTRATIVE TRAJECTORY` badge when interpolating 2 user endpoints).
   - `minimalistic-graphics`: Multi-shot monochrome hairline setups (`#000` / `#f4f4f4`) adding a novel oscillating pendulum momentum scene alongside squash-and-stretch rising steps and radial orbital sparks.
   - `map-route`: Multi-shot procedural 3D city massing, river, parks, custom multi-turn street route, chase/bridge/corner/overview cameras, bouncing pin drop, ETA card, and explicit `SCHEMATIC 3D ROUTE` non-GIS disclosure.
   - `breakdown`: Multi-angle dark studio PBR exploded view (`RoomEnvironment`, cylindrical or slab geometry matched to prompt, novel internal core macro camera, 6 numbered JetBrains Mono right-column callouts & SVG elbow leaders).
4. **Voiceover, Word Alignment, Sound Design & Editorial Timeline (`parse_script.py`, `mix_audio.py`, `edit_timeline.py`)**:
   - Verified host TTS language coverage check (`macos_say` `Samantha`/`Daniel` for `en`, `Linh` `vi_VN` verified on macOS; Kokoro v1.0 explicitly marked `kokoro_supports_vietnamese: false`).
   - Per-sentence synthesis + vocal-formant (`250–3800 Hz`) acoustic energy CDF + local valley snapping for smooth word-level caption timing (`words.json` + `.srt`).
   - 100% procedural DSP sound design (NumPy/SciPy): room/studio ambience bed, tempo-synced musical underscore resolving on the payoff beat, frame-accurate SFX (`whoosh`, `pop`, `thud`, `tick`, `chime`, `sparkle`), VO high-pass + soft-knee compression, envelope sidechain music ducking, and FFmpeg EBU R128 (`-14 LUFS`, `-1.5 dBTP`) mastering.
   - Direct `image2pipe` streaming from Playwright Chromium (Apple M1 Pro Metal WebGL) into `ffmpeg` (`0 bytes` of raw uncompressed frame PNGs written to disk!).

### B. Missing / Optional External Integrations (Documented Honestly)
- **Kokoro-82M & Parakeet 1 GB ONNX Models (`kit/models/`)**: Code paths for `kokoro-onnx` and `sherpa-onnx` Parakeet ASR are implemented and wired in `parse_script.py`, but the optional ~1 GB model download was intentionally skipped on this host to preserve the tight free disk budget (~17.8 GiB free). Host-verified macOS `say` + vocal-formant acoustic energy alignment ran offline with zero model bloat.
- **Blender CLI (`blender`)**: Not installed on this macOS host (`NOT FOUND` in preflight). Genuine 3D scenes (`zach-d-films`, `map-route`, `breakdown`) are rendered natively via Three.js + Apple Metal WebGL in headless Chromium rather than Blender Cycles/EEVEE.
- **Standalone `agy` CLI Binary**: `agy` CLI is not on `PATH` in this shell session (`Antigravity IDE.app` manages plugins via its embedded Language Server); plugin registration was verified directly against Antigravity's live `LanguageServerService/GetAllPlugins` RPC and `.agents/plugins/short-director` + `~/.gemini/config/plugins/short-director`.

### C. Tested & Verified (`STEP 8` Real Exit Codes)
1. **Primary Acceptance Run (`runs/acceptance_stick_figure/`)**:
   - Fresh script (`20.20s`, `30 fps`, `seed=2026`, `--skill stick-figure`), 5 distinct camera setups including novel cross-section sleep-wave cutaway, whip + circular `iris_mask` transitions, true native `2160x3840` (`final_4k.mp4`, `48.0 MB`, `high_freq_edge_ratio = 1.9709` vs 1080p bilinear) + `1080x1920` (`preview_1080.mp4`, `9.0 MB`), audio RMS `-16.73 dBFS` / peak `-3.55 dBFS` / `0` silence dropouts. `qc_report.json` = `PASS`, `style_lock_audit.json` = `PASS`.
2. **Unit & Negative Style-Lock Regression Suite (`tests/test_unit_and_negative.py`)**:
   - `7/7` tests `PASS` in `0.015s` (exit code `0`): explicit syntax variants, auto capability routing across all 6 genres, unknown skill rejection, `sys.addaudithook` blocking foreign `SKILL.md` reads and foreign adapter imports in explicit mode, auto-scan blocking engine templates before lock, `audit_style_lock` rejecting foreign shot/asset/signature/fallback, `NOT_VERIFIED` on missing guard snapshot, `graph` rejecting invented figures, and Kokoro rejecting Vietnamese claims.
3. **Determinism & Resource Quota Suite (`tests/test_determinism_and_resources.py`)**:
   - `2/2` tests `PASS` in `37.94s` (exit code `0`): identical SHA-256 PNG frame hashes across two seeded renders (`seed=1337`), identical frame counts and byte sizes between serial (`workers=1`) and concurrent (`workers=2`) execution, disk quota fail-closed guard, conservative worker clamping, and owned `<run>/tmp` cleanup preserving `kit/` caches.
4. **All-6-Engine Smoke & Upstream Isolation Suite (`tests/test_smoke_all_engines.py`)**:
   - `2/2` test suites (`5` remaining engine end-to-end smoke renders + upstream isolation check) `PASS` in `181.23s` (exit code `0`): verifies `graph`, `minimalistic-graphics`, `map-route`, `breakdown`, and `zach-d-films` end-to-end alongside the `stick-figure` 4K acceptance run (`6/6` skills verified), and confirms `vendor/claude-animation-skills` `git status --porcelain` is empty and standalone `kit/anim.py` `load_spec` + `prepare` still function untouched.

---

## 3. Render Time, Disk & GPU Requirements

- **Hardware Tested**: Apple M1 Pro (`arm64`, 8 cores, 16 GB unified memory, macOS), headless Chromium with `--use-gl=angle --use-angle=metal`.
- **Render Throughput**:
  - **2D / SVG Native 4K (`2160x3840` @ 30fps, 2 workers)**: ~`49s` scene render (`~105s` end-to-end including TTS, pre-render stills, native 4K encode, 1080p supersampled downscale, contact sheet, and decoded-frame QC) for a `20.2s` (`606`-frame) short (`~12.4 fps` effective 4K throughput).
  - **1080p Preview + Lanczos 4K Upscale Smoke Mode (`30fps`, 2 workers)**: ~`8–18s` per short depending on 2D vs 3D WebGL shadow/bloom complexity.
  - **Software WebGL Fallback (`--use-angle=swiftshader`)**: On headless Linux VMs without a GPU, Three.js engines (`zach-d-films`, `map-route`, `breakdown`) fall back to SwiftShader CPU rasterization and run ~`5–12x` slower (`0.4–1.5s/frame` at 1080p); `--render-4k-mode upscale` is recommended on GPU-less hosts.
- **Disk Footprint & Quota Safety**:
  - Shared `kit/node_modules` + `gsap.min.js`: `43 MB` (reuses existing Playwright/Chrome binary on host).
  - Intermediate raw frame PNGs on disk: **`0 MB`** (frames stream via `image2pipe` directly into `ffmpeg`).
  - Per-run output footprint (`20s` native 4K + 1080p preview + 15 PNG stills + WAV stems): ~`115 MB`.
  - `preflight.py` and `render_scene.py` enforce a minimum `1.5 GiB` free-disk quota before and during rendering and restrict cleanup strictly to `<run_dir>/tmp` and intermediate silent concat files.
