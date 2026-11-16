# Short Director Plugin Guardrails

Whenever invoking `/short-director` or operating inside a Short Director run:

1. **Strict One-Skill Lock (Fail-Closed)**:
   - Valid engine names are strictly: `zach-d-films`, `stick-figure`, `minimalistic-graphics`, `map-route`, `breakdown`, `graph`.
   - When the user explicitly specifies a skill (`--skill <name>`, `Skill: <name>`, or unambiguous natural language), lock `selected_skill` immediately before loading any visual engine. Read and execute ONLY that skill's `SKILL.md`, visual engine, and neutral shared `kit/` utilities. Never inspect, import, copy, or run any of the other five engines.
   - When no skill is specified (`auto` mode), compare ONLY the six capability descriptions during planning, select and lock ONE `selected_skill` for the entire run, and never blend secondary shots, guest inserts, or fallback engines.
   - On unsupported scenes or errors, extend the locked engine or fail closed with a clear diagnostic — never switch engines silently.

2. **Bespoke Visuals, Scene Novelty & Continuous Motion**:
   - Do not reuse upstream demo narratives (such as the pirate eye-patch reel or ancient armor bullet demo) or default non-Roman scripts into medieval/Roman gladiator armor. Generate fresh beat-driven geometry, props, cutaway reveals, camera choreography, and motivated transitions strictly inside the locked engine's visual language.
   - Build semantic `visual_events.json` -> `shot_coverage.json` -> `camera_paths.json` -> `transition_edl.json` before rendering, preventing adjacent duplicate compositions without repeating identical narration across split cuts.
   - Ensure every shot `update(t)` / `renderAtTime(t)` is pure, time-deterministic, and seeded so parallel workers match serial renders.

3. **Truthful 4K & Technical QA**:
   - Portrait `9:16` (`1080x1920` preview and `2160x3840` final at requested `30` or `60` fps).
   - Declare `native_4k: true` ONLY when rasterized at `2160x3840` before encoding; otherwise explicitly declare `upscaled` with exact source dimensions and scaling filter.
   - Run style-lock audits (`style_lock_audit.json`) BEFORE rendering and again BEFORE final delivery, plus post-render perceptual scene diversity & transition QC (`scene_diversity_report.json`) and `ffprobe`/audio QC (`qc_report.json`, `audio/audio_qc_report.json`). Never claim unverified subjective retention/viewing (`NOT_VERIFIED` if no human viewer inspected playback).

4. **Licensing & Factual Integrity**:
   - Never rip third-party footage, copyrighted music, or unverified voice clones. Verify local TTS model language coverage before claiming support (e.g., Kokoro v1.0 does not support Vietnamese; macOS `say` supports Vietnamese only when a `vi_VN` voice such as `Linh` is installed).
   - Verify SHA-256 checksums, explicit license JSON, commercial rights, and mandatory CC BY attribution (`audio/credits_audio.txt`) before using any external or optional read-only `QA-Unified-Video-Studio` audio asset; label native DSP audio as `procedural` (never `'copyright-free'`).
   - Treat audio (`audio_catalog`, `audio_narrative`, `music_director`, `sfx_director`, `mix_audio`) strictly as a shared non-visual service: audio code must never open, import, or swap visual engine skills, and `--audio-only` must preserve picture packets losslessly (`-c:v copy`).
   - Never invent chart numbers in `graph` (hedge or label illustrative trajectories explicitly), and never claim `map-route` schematic city geometry is GIS-accurate.
