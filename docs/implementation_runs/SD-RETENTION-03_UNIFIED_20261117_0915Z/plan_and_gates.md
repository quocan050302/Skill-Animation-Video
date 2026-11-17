# SD-RETENTION-03.UNIFIED.R1 — Architecture Plan & Verification Matrix (`G01`–`G22`, `N01`–`N32`)

## Dependency Order (`(a)` -> `(h)`)
1. **(a) Scene / Story Action & Physical Anchors**: `visual_event_graph.py`, `visual_storytelling_director.py`, `scene_asset_factory.py`, `physical_motion.py`, `character_performance.py`, `zdf_tacoma_bridge_scenes.py`, `zdf_boston_molasses_scenes.py`.
2. **(b) Editorial Intent + Reveal Policy**: `curiosity_director.py` (hook/twist gap <=2 hero headlines, true physical feature targets, spoiler lock).
3. **(c) Semantic Overlay Role Theme + Layout + Composition**: `editorial_design_system.py`, `cinematic_composition.py` (7 semantic roles: `location_time`, `curiosity_headline`, `warning_danger`, `verified_fact`, `explanation`, `aftermath_sober`, `transition_emphasis`).
4. **(d) Unified Timeline**: `build_storyboard.py` -> `editorial_overlay.py::build_editorial_timeline` (emitting `editorial_design_tokens.json`, `editorial_roles_plan.json`, `editorial_timeline.json`).
5. **(e) WebGL / DOM Deterministic Render**: `editorial_theme_renderer.py` (JS controller), `physical_motion_primitives.py` (JS waves/beams/torsion/collapse), `character_performance.py` (JS grounded locomotion/reaction IK), `zdf_tacoma_bridge_scenes.py`, wired cleanly into `zach_d_films_adapter.py`.
6. **(f) Sound Cues**: `audio_narrative.py`, `sfx_director.py`, `audio_dsp.py`, `mix_audio.py` mapped by editorial role & contact frames (`<= 33.3ms` contact sync, `<= 45ms` UI sync).
7. **(g) False-Pass-Proof QA + A/B**: `retention_qa.py`, `visual_storytelling_qa.py`, `cinematic_composition_qa.py`, `quality_gate.py`, plus `tests/` covering `N01`–`N32` & `G01`–`G22`.
8. **(h) Showcase + Boston Regression + Git Commit/Push**: Fresh Tacoma Narrows A/B + 1080p + true native 4K (`final_4k.mp4`), isolated `overlay_on` vs `overlay_off`, separate Boston wave/crowd repair proof, full async DAG + full unittest suite, scoped commit & push to `feat/sd-retention-01-expressive-editorial`.

## Gate Checklist (`G01`–`G22`)
- `G01`–`G03`: Branch safety, backward compatibility across all 6 engines, 59 legacy tests intact.
- `G04`–`G08`: Multi-theme editorial roles (zero uniform-box repetition, big 2-tone hook headline, real 3D pointer <=36px tip error, 320/360/390/1080 DOM legibility, early-spoiler proof).
- `G09`–`G13`: Camera-locked physical deformation proof, Boston continuous wave fix + foot-grounded locomotion (`<0.08m` slide, `<=0.03m` floor penetration), Tacoma continuous torsion/cable/collapse, 8+ beats composition clarity.
- `G14`–`G17`: Role/contact SFX sync, honest SAPI5 disclosure & `NOT_VERIFIED` subjective gates, bounded async resources, strict frame seek determinism.
- `G18`–`G22`: True ON/OFF A/B pixel proof (no `normalized_shot_index` fallback), verified historical claims (WSDOT + FHWA), full DAG + unittest pass after final edit, FFprobe + 4K honesty.
