# Credits, Provenance & Licensing

## Upstream Animation Engines (`claude-animation-skills`)

- **Repository**: https://github.com/artemnovitckii/claude-animation-skills
- **Author**: Artem Novitckii (`artem@altari.ai`)
- **Pinned Commit SHA**: `5dbea55c23aa6a5c93dc3cfb5583840513b56b94` (`2026-11-01 15:53:30 +1300`, *"Fix what a cold-start test of /zach-d-films found"*)
- **License**: MIT License (`vendor/claude-animation-skills/LICENSE`)

```text
MIT License

Copyright (c) 2026 Artem Novitckii

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

## Bundled Fonts (SIL Open Font License 1.1)

All fonts used by the engines and Short Director adapters are open-source SIL OFL 1.1 fonts shipped in `vendor/claude-animation-skills/` or `kit/node_modules/@fontsource/montserrat`:
- **Inter** (`kit/fonts/OFL-inter.txt`)
- **Inter Tight** (`kit/fonts/OFL-intertight.txt`)
- **JetBrains Mono** (`kit/fonts/OFL-jetbrainsmono.txt`)
- **Poppins** (`kit/fonts/OFL-poppins.txt`, `skills/stick-figure/engine/template/web/fonts/OFL-poppins.txt`)
- **Lora** (`skills/stick-figure/engine/template/web/fonts/OFL-lora.txt`)
- **Montserrat** (`@fontsource/montserrat` 5.1.0, SIL OFL 1.1)

## Runtime Libraries & Tools

- **Three.js** (`0.169.0`, MIT License) — WebGL 3D procedural geometry, materials, and post-processing for `zach-d-films`, `map-route`, and `breakdown`.
- **GSAP** (`3.12.5`, Standard "No Charge" GreenSock License) — Deterministic timeline tweening for `graph` and `minimalistic-graphics`.
- **Playwright** (`1.49.1`, Apache-2.0 License) — Headless Chromium / Metal WebGL deterministic frame rasterization.
- **FFmpeg / FFprobe** (`6.0`, LGPL/GPL system binary) — Image-pipe H.264 video encoding, timeline muxing, EBU R128 loudness normalization (`loudnorm`), and technical QC inspection.
- **NumPy & SciPy & SoundFile** (BSD Licenses) — Procedural 48 kHz sound synthesis (`director/audio_dsp.py`, `director/music_director.py`, `director/sfx_director.py`), vocal formant envelope word alignment, sidechain ducking, and stem hashing.
- **Audio Assets & Licensing (`SD-AUDIO-01`, v0.3.0)**:
  - Standalone procedural stems are synthesized natively via NumPy/SciPy (`license_type: "procedural"` — never claimed as `'copyright-free'`).
  - Optional external read-only mounting (`--qa-audio-root <path>` or `SHORT_DIRECTOR_QA_ROOT`) supports verified commercial-safe `cc0` / `cc-by-*` beds and real SFX with mandatory SHA-256 verification and automatic CC BY credit generation in `audio/credits_audio.txt` (e.g., Kevin MacLeod / `incompetech.com` CC BY 4.0 when `"Dark Fog"` is resolved). Missing or non-commercial licenses fail closed.
- **Voice Synthesis**:
  - macOS native `say` (`NSSpeechSynthesizer` system voices, e.g. `Samantha`/`Daniel` for `en`, `Linh` for `vi_VN` when installed locally) — offline system-licensed TTS.
  - Optional `kokoro-onnx` (`Apache-2.0`, Kokoro-82M v1.0) and `sherpa-onnx` (`Apache-2.0`, NVIDIA Parakeet TDT 0.6B v2) when installed via `--voice` models; language coverage is verified before invocation (Kokoro v1.0 is NOT used for Vietnamese).

## Upstream Source Modification Matrix (`KEPT AS IS` vs `MODIFIED`)

All tracked files inside `vendor/claude-animation-skills` (`5dbea55c23aa6a5c93dc3cfb5583840513b56b94`) are **KEPT AS IS** (`git diff` = empty, zero tracked lines modified), ensuring 100% compatibility with upstream standalone single-engine runs:

| Upstream Path | Status | Notes |
|---|---|---|
| `vendor/claude-animation-skills/kit/anim.py` | **KEPT AS IS** | Unmodified upstream helper; standalone quick skills continue to work unchanged. |
| `vendor/claude-animation-skills/kit/words.py` | **KEPT AS IS** | Unmodified Parakeet word-timing helper; invoked optionally when sherpa-onnx models exist. |
| `vendor/claude-animation-skills/kit/setup.sh` | **KEPT AS IS** | Inspected, not blindly invoked via `install.sh` (Claude Code `~/.claude/skills` linking avoided). |
| `vendor/claude-animation-skills/skills/stick-figure/**` | **KEPT AS IS** | Base `lib.js`, `chars.js`, `env.js`, and fonts are copied into isolated per-run workspaces and extended via `director/assets/stick_figure_adapter.py` without mutating upstream files. |
| `vendor/claude-animation-skills/skills/zach-d-films/**` | **KEPT AS IS** | Base `anim.js`, `human.js`, `props.js`, `materials.js`, `textures.js` copied into isolated per-run workspaces and extended via `director/assets/zach_d_films_adapter.py`. |
| `vendor/claude-animation-skills/skills/graph/**` | **KEPT AS IS** | Upstream `build.py` + `template.html` preserved intact; multi-shot native-4K extension implemented cleanly in `director/assets/graph_adapter.py`. |
| `vendor/claude-animation-skills/skills/minimalistic-graphics/**` | **KEPT AS IS** | Upstream `build.py` + `template.html` preserved intact; multi-motif extension implemented in `director/assets/minimalistic_graphics_adapter.py`. |
| `vendor/claude-animation-skills/skills/map-route/**` | **KEPT AS IS** | Upstream `build.py` + `template.html` preserved intact; multi-shot camera & custom street route extension implemented in `director/assets/map_route_adapter.py`. |
| `vendor/claude-animation-skills/skills/breakdown/**` | **KEPT AS IS** | Upstream `build.py` + `template.html` preserved intact; parametric multi-layer 3D assembly extension implemented in `director/assets/breakdown_adapter.py`. |
| `director/**`, `skills/short-director/SKILL.md`, `plugin.json`, `rules/AGENTS.md`, `tests/**` | **v0.3.0 (`SD-AUDIO-01`)** | Full Antigravity Short Director plugin, fail-closed provenance guard, single-skill adapters, deterministic 4K renderer, narrative audio/music/SFX directors, license/SHA-256 gate, `--audio-only` lossless remuxer, timeline editor, and post-encode audio/video QA gate. |
