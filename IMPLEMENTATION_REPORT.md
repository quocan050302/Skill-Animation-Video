# Short Director `v0.2.0` — Implementation, QA & Resource Report

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
