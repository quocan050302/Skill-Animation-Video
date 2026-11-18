# SD-RETENTION-04.R1 Implementation Map

## New Core Modules
1. **`director/visual_causality_director.py`**:
   - Core contracts: `CausalEvent`, `VisualEvidenceContract`, `VALID_PROOF_TYPES` (11 mechanism proof classes), `EVIDENCE_SUPPORTED`, `EVIDENCE_UNSUPPORTED`, `PHYSICS_VISUAL_APPROX`.
   - Core functions: `classify_causal_proof`, `link_cause_effect_chain`, `make_evidence_contract`, `validate_world_state_conservation`, `bind_causal_events_to_voice`, `build_causal_event_graph`, `write_causal_traceability`.
   - Outputs per run: `causal_event_graph.json`, `causal_evidence_contracts.json`, `causal_traceability.csv`.
2. **`director/action_camera_director.py`**:
   - Core contracts: `CameraIntentContract` (Q1–Q5 rationale, target causal feature vs fixed reference landmark, justification rule, counterfactual omission loss, info-gain metrics).
   - Core functions: `score_camera_information_gain`, `select_camera_intent`, `resolve_causal_focal_path`, `build_camera_intent_contract`, `validate_camera_proof_visibility`, `plan_action_driven_camera`.
   - Outputs per run: `camera_intent_report.json`.
3. **`director/semantic_visual_evidence_qa.py`**:
   - Core QA checks: `audit_visual_claim_coverage`, `audit_relative_motion_evidence`, `audit_claim_pointer_semantics`, `audit_causal_transition_visibility`, `audit_story_silent_comprehension_proxies`, `audit_ab_vo_and_metric_consistency`, `run_semantic_visual_evidence_qa`.
   - Visual diagnostics: `render_event_aligned_before_action_after_strip`, `write_qa_failure_examples`.
   - Outputs per run: `visual_claim_coverage.json`, `pointer_semantics.json`, `causal_evidence_gaps.csv`, `semantic_matte_alignment.json`, `causal_gates_status.json`, `qa/event_aligned_before_action_after.jpg`, `qa/qa_failures_visual_examples/`.
4. **`director/assets/zdf_london_smog_scenes.py`**:
   - `LONDON_SMOG_SCENES_JS`: `makeLondonStreetFogRig`, `makeCoalCombustionCutawayRig` (with `LayeredCutaway` telemetry), `makeLondonAtmosphericInversionRig` (labeled `ILLUSTRATIVE AIRFLOW`), `makeLondonBusVisibilityRig`, `makeLondonPedestrianReactionRig`, `makeLondonAftermathRig`.

## Integrated Extensions to Existing Pipeline
- **Planning & Story (`director/visual_event_graph.py`, `director/visual_storytelling_director.py`, `director/build_storyboard.py`)**: General atmospheric phenomenon rules, pre-1960 period anachronism check, causal sequence rules, 1:1 shot-to-causal event binding, and Q1–Q5 camera intent injection inside `build_storyboard_and_bible`.
- **Staging & Camera (`director/scene_asset_factory.py`, `director/shot_director.py`, `director/camera_choreographer.py`)**: Registered 6 London 1952 archetypes, `char_london_pedestrian_01`, setup candidates, and distinct shot camera keyframes (retaining `camera_execution.py` single-authority verification).
- **Overlays & Pointers (`director/curiosity_director.py`, `director/editorial_overlay.py`)**: Curiosity hooks (`NOON LOOKED / LIKE MIDNIGHT!`, `TRAPPED BY / WARM AIR!`), semantic target meshes, and unified binding of `causal_event_id`, `narrative_claim_id`, `target_entity_id`, `target_feature_id`, `proof_target_id`, `semantic_region_of_change`, `why_this_overlay`.
- **WebGL Engine & Mattes (`director/assets/zach_d_films_adapter.py`)**: `skyTheme` additions (`london_smog_ochre`, `london_inversion_twilight`, `london_clean_recovery`), extended `MATTE_HEX` (`cause_source`, `effect_result`, `reference_fixed`), fog-free `renderMatteAtTime` isolation (`scene.fog = null`, `fog: false`, `matteSkip` handling), and per-shot London scene wiring.
- **Audio & Voice Fidelity (`director/audio_narrative.py`, `director/audio_dsp.py`, `director/parse_script.py`)**: Atmospheric London SFX event cues, scalar cutoff fix in `_wind_bridge_gust`, and bit-exact PCM preservation when copying mono WAV `user_voice_file` inputs for A/B experiments.
- **QA & Test Suite (`director/decoded_visual_quality.py`, `director/quality_gate.py`, `tests/test_sd_retention04_causality.py`, `tests/test_sd_retention04_camera_and_visual_proof.py`, `tools/run_validation_async.py`)**: End-to-end wiring of `semantic_causal_visual_evidence` gate and full 27-module async DAG coverage (`N01`–`N40`).
