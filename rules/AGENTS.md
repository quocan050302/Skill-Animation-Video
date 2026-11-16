# Short Director Plugin Guardrails

Whenever invoking `/short-director` or operating inside a Short Director run:

1. **Strict One-Skill Lock (Fail-Closed)**:
   - Valid engine names are strictly: `zach-d-films`, `stick-figure`, `minimalistic-graphics`, `map-route`, `breakdown`, `graph`.
   - When the user explicitly specifies a skill (`--skill <name>`, `Skill: <name>`, or unambiguous natural language), lock `selected_skill` immediately before loading any visual engine. Read and execute ONLY that skill's `SKILL.md`, visual engine, and neutral shared `kit/` utilities. Never inspect, import, copy, or run any of the other five engines.
   - When no skill is specified (`auto` mode), compare ONLY the six capability descriptions during planning, select and lock ONE `selected_skill` for the entire run, and never blend secondary shots, guest inserts, or fallback engines.
   - On unsupported scenes or errors, extend the locked engine or fail closed with a clear diagnostic — never switch engines silently.

2. **Bespoke Visuals & Organic Motion**:
   - Do not reuse upstream demo narratives (such as the pirate eye-patch reel or ancient armor bullet demo) as fake output for new prompts. Generate fresh beat-driven geometry, poses, props, camera blocking, and transitions inside the locked engine's visual language.
   - Ensure every shot `update(t)` / `renderFrame(f)` is pure, time-deterministic, and seeded so parallel workers match serial renders.

3. **Truthful 4K & Technical QA**:
   - Portrait `9:16` (`1080x1920` preview and `2160x3840` final at requested `30` or `60` fps).
   - Declare `native_4k: true` ONLY when rasterized at `2160x3840` before encoding; otherwise explicitly declare `upscaled` with exact source dimensions and scaling filter.
   - Run style-lock audits (`style_lock_audit.json`) BEFORE rendering and again BEFORE final delivery, followed by `ffprobe` + decoded frame and audio checks (`qc_report.json`). Never report `PASS` for unrun, skipped, or unverified checks.

4. **Licensing & Factual Integrity**:
   - Never rip third-party footage, copyrighted music, or unverified voice clones. Verify local TTS model language coverage before claiming support (e.g., Kokoro v1.0 does not support Vietnamese; macOS `say` supports Vietnamese only when a `vi_VN` voice such as `Linh` is installed).
   - Never invent chart numbers in `graph` (hedge or label illustrative trajectories explicitly), and never claim `map-route` schematic city geometry is GIS-accurate.
