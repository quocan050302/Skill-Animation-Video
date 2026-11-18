# SD-RETENTION-03.R2 Plan & Acceptance Gates

## Dependency Phases
- **Phase 0**: Baseline git state pinned (`8f53a7a`), new branch `feat/sd-retention-03-r2-visual-quality`, host & disk preflight, baseline run check.
- **Phase 1 (R2.1)**: `director/decoded_visual_quality.py`, semantic object-ID matte extraction in `render_node.mjs` / `zach_d_films_adapter.py`, camera-compensated physical motion separation, zero-sample fail-closed pointer audit, `decoded_visual_quality_report.json` + `subject_visibility_by_shot.json` + `camera_compensated_motion_report.json` + `mobile_qa_320_360_390_1080.json`, negative traps `T01`–`T09`, `T14`, `T25`–`T27`.
- **Phase 2 (R2.2 & R2.3)**: Grounded `salient_action_anchor` & dynamic action bounding volumes in `cinematic_composition.py`, `camera_choreographer.py`, `shot_director.py`, `scene_asset_factory.py`; `frame_design_intent.json` & runtime safe-rect proof; Tacoma bridge contiguous deck / dual-edge torsion / hinged collapse + water splash & continuous world state; Boston regression proof.
- **Phase 3 (R2.4 & R2.5)**: Phased reaction performance (`detect -> orient -> weight_shift -> step_recoil -> recover`), foot-locked grounding, semantic pointer feature-region checks (curved bracket / dual-edge markers for whole-deck torsion), 20%+ overlay-free breathing room, third-domain neutral templates.
- **Phase 4 (R2.6)**: Single event clock, contact SFX <=1 frame, UI cue <=45ms, caption readability across 320/360/390/1080, honest `ESTIMATED` alignment & `NOT_VERIFIED` subjective statuses.
- **Phase 5 (R2.8 Pilot + New Demo)**: Brand-new procedural skyscraper asset & 9+ beat *Why Skyscrapers Sway in the Wind* short (`zdf_skyscraper_scenes.py`), low-res pilot check -> A/B 1080p -> true native 4K `2160x3840` master.
- **Phase 6 (Tacoma & Boston Proofs)**: Focused Tacoma R2 vs R3 repair proof (intro, 22s torsion, ~31s collapse) and Boston continuous heightfield + crowd grounding comparison proof.
- **Phase 7 (R2.7)**: Update `tools/run_validation_async.py` to cover all `tests/test_*.py` suites automatically, implement T01–T32 negative trap tests + positive matrix, run `--mode full --workers 2` AND full canonical `python3 -m unittest discover -s tests -v` AFTER final code edit.
- **Phase 8 & 9**: Media hash/FFprobe/contact sheet verification, README + manifest + SHA256SUMS, git diff/secret check, commit & push new branch, verify remote HEAD.

## QA Status Definitions
- `PASS`: concrete verified automated technical gate
- `FAIL`: contract violation / broken gate
- `WARN`: objectively degraded metric without hard gate breach
- `NOT_VERIFIED`: missing evidence or subjective/human criterion (`subjective_visual_quality`, `subjective_editorial_listening`, `subjective_voice_quality_status`, `viewer_retention_status` NEVER labeled `PASS` by automation)
