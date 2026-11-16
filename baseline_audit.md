# Baseline Workspace Audit — `SD-AUDIO-01`

**Date**: 2026-11-16  
**Repository Root**: `/Users/macbook/.gemini/antigravity/scratch/short-director`  
**Branch**: `master`  
**Local Commit SHA**: `824abce0a26c9f29a6a6b3087250af0780d3bc28`  
**Upstream Submodule (`vendor/claude-animation-skills`)**: `-5dbea55c23aa6a5c93dc3cfb5583840513b56b94` (unmodified MIT baseline)  
**Working Tree Status**: Clean (`git status --short` = empty on `master`)

---

## 1. Verified Runtime & Toolchain Versions

| Component | Verified Value / Version | Verification Method |
|---|---|---|
| Python | `Python 3.13.0` (`/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`) | `VERIFIED` (`python3 -V`) |
| FFmpeg / FFprobe | `ffmpeg 6.0` (filters verified: `ebur128`, `loudnorm`, `astats`, `silencedetect`, `blackdetect`, `alimiter`) | `VERIFIED` (`ffmpeg -version`, `ffmpeg -filters`) |
| NumPy / SciPy / SoundFile | `numpy 2.1.3`, `scipy 1.18.1`, `soundfile 0.14.0` | `VERIFIED` (`python3 -c ...`) |
| Browser / WebGL | Playwright `1.49.1` Chromium (`arm64` Metal backend) | `VERIFIED` (`tests/test_determinism_and_resources.py`) |
| Voice TTS | macOS `say` (`Samantha` `en_US`, `Linh` `vi_VN` available); Kokoro v1.0 & Parakeet models absent (`kit/models/` not downloaded) | `VERIFIED` (`runs/roman_gladiator_zdf/logs/preflight.json`) |

---

## 2. QA Audio Library Availability Check (`QA-Unified-Video-Studio`)

| Check Location | Result | Notes |
|---|---|---|
| Env `SHORT_DIRECTOR_QA_ROOT` | Unset (`None`) | `VERIFIED` (`env` scan) |
| Trusted workspace siblings & common macOS user roots (`~/.gemini/antigravity/*`, `~/Projects`, `~/Desktop`, `~/Documents`, `~/Downloads`, `~/Developer`) | `QA_LIBRARY_UNAVAILABLE` | `VERIFIED` (`ls -d ...` check returned no `QA-Unified-Video-Studio` local checkout) |
| Available External QA WAV Beds / SFX Count Locally | `0` external beds, `0` external SFX (`0` bytes) | `VERIFIED` (`QA_LIBRARY_UNAVAILABLE`; integration will support `--qa-audio-root` / `SHORT_DIRECTOR_QA_ROOT` read-only mounts plus strict schema/hash/license tests with isolated fixtures) |

---

## 3. Baseline Test Suite Run (`python3 -m unittest discover -s tests -v`)

Executed on clean `HEAD = 824abce0a26c9f29a6a6b3087250af0780d3bc28` (`elapsed = 205.906s`, **exit code `1`**):

- **`test_determinism_and_resources.py`** (`2/2 PASS`):
  - `test_disk_quota_guard_and_worker_cap`: `ok`
  - `test_seeded_frame_hashes_and_serial_vs_concurrent_parity`: `ok`
- **`test_smoke_all_engines.py`** (`2/2 PASS`):
  - `test_remaining_five_engines_smoke_renders`: `ok` (`graph`, `minimalistic-graphics`, `map-route`, `breakdown`, `zach-d-films`)
  - `test_upstream_repo_unmodified_and_standalone_prepare_works`: `ok`
- **`test_unit_and_negative.py`** (`6/7 PASS, 1 FAIL`):
  - `test_explicit_mode_blocks_reading_other_five_skill_mds_and_adapters`: **`FAIL`** when run after `test_smoke_all_engines` inside the same Python process (`discover` order).
    - **Root Cause (`VERIFIED`)**: `test_smoke_all_engines` imported `director.assets.zach_d_films_adapter` into `sys.modules`. Later in the same interpreter, `__import__("director.assets.zach_d_films_adapter")` hit CPython 3.13's `sys.modules` cache without firing a `sys.audit("import", ...)` event, bypassing `ProvenanceGuard._handle_event("import", ...)`.
    - **Fix Planned**: Evict cached `director.assets.*_adapter` entries from `sys.modules` on `ProvenanceGuard.activate()` and guard module access explicitly.

---

## 4. What Is Already Implemented vs What Is Missing (`SD-AUDIO-01` Scope)

### Already Implemented (`v0.2.0` Baseline — `VERIFIED`)
1. `director/mix_audio.py`: Synthesizes 48 kHz stereo `audio/mix.wav`, `audio/sfx.wav`, `audio/music.wav`, and `audio/audio_mix_report.json` with high-pass filtered + soft-knee compressed VO, ambient bandpass bed, single fixed `Dm7 -> Bbmaj7 -> Fmaj7 -> C6` chord progression (`prog_minor` -> `prog_bright`), transition `whoosh` / `thud`, hook `pop`, `mechanism_ticks_and_chime`, payoff `sparkle_arpeggio`, and VO sidechain ducking (`-14 LUFS` mastered via FFmpeg `loudnorm` in `edit_timeline.py`).
2. `director/quality_gate.py`: Verifies `ffprobe` streams, decoded PCM overall RMS/peak dBFS, and `silencedetect > 1.2s` on `final_4k.mp4`.
3. Single-visual-skill lock (`route_styles.py`, `provenance_guard.py`) + 6 engine adapters + deterministic `image2pipe` WebGL/Canvas2D 4K rendering.
4. Untouched local user runs inside `runs/` (`runs/acceptance_stick_figure`, `runs/roman_gladiator_zdf` including renamed `Why Roman Gladiators Didn’t Always Fight to the Death.mp4`).

### Missing / Gaps to Build (`SD-AUDIO-01` Requirements)
1. **No Narrative & Visual-Grounded Audio Planner (`director/audio_narrative.py`)**: Currently `mix_audio.py` hardcodes a `t=0.04` pop and triggers generic ticks/chime only if `novel_non_template=True`, with zero `AudioNarrativePlan` grounded in visible shot actions/props, no emotion-aligned dynamic music score arc, no manual cue lock preservation, and no `--audio-plan-in`.
2. **No Asset Catalog / Read-Only QA License & SHA-256 Gate (`director/audio_catalog.py`)**: No discovery, SHA-256 verification, `ffprobe` decode gate, path-traversal block, CC BY mandatory credit emission (`credits_audio.txt`), or `audio_asset_manifest.json`.
3. **No Dedicated Music & SFX Directors (`director/music_director.py`, `director/sfx_director.py`)**: Single static chord progression (`Dm7->Bb->F->C`) across all scripts; no `--music-mode` (`auto|procedural|qa-library|file|off`), `--music-gain-db`, `--music-intensity`, `--sfx-mode`, `--sfx-density`, `--sfx-gain-db`, motion-matched stereo pan, or `music_cue_sheet.json` / `sfx_cue_sheet.json`.
4. **Incomplete Stems & Double-Limiting Risk (`director/mix_audio.py`, `director/edit_timeline.py`)**: Missing `voice.wav`, `ambience.wav`, `master_pre.wav`, intentional `--voice-mode` handling, and `--audio-only` lossless packet-copy (`-c:v copy`) remix without touching picture; `edit_timeline.py` currently always applies `alimiter + loudnorm` without coordinating pre-master vs post-master single pass.
5. **Shallow Post-Encode Audio QC (`director/quality_gate.py`)**: No post-AAC `ebur128=peak=true` Integrated LUFS & True Peak (`dBTP`) verification, no SFX onset sync check, no VO-masking check, no loop/crossfade seam check, and no license/credit check (`audio_qc_report.json`).
6. **Pre-4K Audio Preflight (`director/preflight.py`, `director/run.py`)**: Audio planning & license validation currently happen *after* expensive 4K scene rendering instead of failing closed early before 4K rendering.
