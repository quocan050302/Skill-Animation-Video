# Skill-Animation-Video

## Short Director (`v0.2.0`) — Antigravity Plugin

Production-hardened vertical shorts (`9:16`, `1080x1920` preview + `2160x3840` 4K delivery at `30`/`60` fps) built for Google Antigravity with a **machine-enforceable, fail-closed single-skill lock** across six procedural animation engines.

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

## Outputs Per Run

Every completed run writes verified artifacts to `<out-dir>/`:
- `style_decisions.json` — Immutable `selection_mode`, `selected_skill`, `style_lock`, and upstream commit provenance
- `storyboard.json` & `art_bible.md` — Per-shot camera blocking, setups, transitions, style parameters, and `visual_assets` inventory
- `style_lock_audit.json` — Recursive AST/HTML/JS source & `sys.addaudithook` runtime audit proving zero foreign-skill files or imports
- `stills/` & `contact_sheet.jpg` — First, busiest, and end frames of every shot plus 9:16 safe-area sheet
- `preview_1080.mp4` — `1080x1920` H.264 + `-14 LUFS` AAC stereo preview
- `final_4k.mp4` — `2160x3840` H.264 + `-14 LUFS` AAC stereo master (with truthful `native_4k` vs `upscaled` declaration)
- `qc_report.json` & `run_manifest.json` — Complete `PASS`/`FAIL`/`WARN`/`NOT_RUN` technical QC report and `ffprobe` metrics

## Running the Test Suite

```bash
python3 -m unittest -v tests/test_unit_and_negative.py
python3 -m unittest -v tests/test_determinism_and_resources.py
python3 -m unittest -v tests/test_smoke_all_engines.py
```
