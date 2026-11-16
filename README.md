# Skill-Animation-Video

## Short Director (`v0.3.0`) — Antigravity Plugin

Production-hardened vertical shorts (`9:16`, `1080x1920` preview + `2160x3840` 4K delivery at `30`/`60` fps) built for Google Antigravity with a **machine-enforceable, fail-closed single-skill lock** across the six existing animation engines plus narrative music & licensed SFX direction (`SD-AUDIO-01`).

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

## Narrative Music & SFX Director (`v0.3.0` Changelog)
- **Visual-Grounded Audio Direction** (`audio_narrative.py`, `music_director.py`, `sfx_director.py`): Aligns cohesive thematic music arcs and frame-accurate Foley/SFX directly to shot setups, grounded objects, and transitions rather than generic per-cut pops/whooshes.
- **Optional Read-Only `QA-Unified-Video-Studio` Integration** (`audio_catalog.py`): Supports `--qa-audio-root <path>` or `SHORT_DIRECTOR_QA_ROOT` with SHA-256 verification, `ffprobe` decodability checks, path-traversal guards, commercial rights gating, and automatic `audio/credits_audio.txt` attribution (falling back cleanly to procedural synthesis with `QA_LIBRARY_UNAVAILABLE` when absent).
- **Audio Switches & Lossless `--audio-only` Remix**: `--music-mode auto|procedural|qa-library|file|off`, `--sfx-mode auto|procedural|qa-library|off`, `--sfx-density sparse|balanced|detailed`, `--music-gain-db`, `--sfx-gain-db`, `--music-intensity`, `--audio-plan-in`, `--audio-only` (preserves video packets losslessly via `-c:v copy`), and `--voice-mode auto|off`.
- **Single-Pass Mastering & Post-Encode Audio QC**: `audio/voice.wav`, `music.wav`, `sfx.wav`, `ambience.wav`, `master_pre.wav`, `mix.wav`, plus post-AAC `ebur128` LUFS/True Peak, onset, intelligibility, boundary-click, and license QC in `audio/audio_qc_report.json`.

## Outputs Per Run

Every completed run writes verified artifacts to `<out-dir>/`:
- `style_decisions.json` — Immutable `selection_mode`, `selected_skill`, `style_lock`, and upstream commit provenance
- `storyboard.json` & `art_bible.md` — Per-shot camera blocking, setups, transitions, style parameters, and `visual_assets` inventory
- `style_lock_audit.json` — Recursive AST/HTML/JS source & `sys.addaudithook` runtime audit proving zero foreign-skill files or imports
- `audio/` — `audio_plan.json`, `audio_director_notes.md`, `music_cue_sheet.json`, `sfx_cue_sheet.json`, `audio_asset_manifest.json`, `audio_mix_report.json`, `audio_qc_report.json`, `credits_audio.txt`, and 48 kHz stereo stems (`voice.wav`, `music.wav`, `sfx.wav`, `ambience.wav`, `master_pre.wav`, `mix.wav`)
- `stills/` & `contact_sheet.jpg` — First, busiest, and end frames of every shot plus 9:16 safe-area sheet
- `preview_1080.mp4` — `1080x1920` H.264 + single-pass `-14 LUFS` AAC stereo preview
- `final_4k.mp4` — `2160x3840` H.264 + single-pass `-14 LUFS` AAC stereo master (with truthful `native_4k` vs `upscaled` declaration)
- `qc_report.json` & `run_manifest.json` — Complete `PASS`/`FAIL`/`WARN`/`NOT_RUN` technical QC report and `ffprobe`/audio metrics

## Running the Test Suite

```bash
python3 -m unittest discover -s tests -v
```
