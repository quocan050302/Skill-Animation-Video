# Baseline Code & Architecture Function Map (`HEAD = 233ace08`)

## 1. Story, Event & Causal Planning Layer
- **`director/visual_event_graph.py`**:
  - `extract_semantic_visual_events(script_sentences, selected_skill, words=..., scene_hint=...)`: parses clauses (`VERB_PATTERNS`, `DOMAIN_PROP_RULES`, `UNSUPPORTED_EXACT_DOMAIN_RULES`), emits `events`, intra-shot multi-phase `sub_activities` (`approach -> action -> reaction`), `beat_constraints`, `character_id`, `relevant_prop`.
  - **Gap**: Lacks first-class causal graph links (`cause_event_ids`, `result_event_ids`, `proof_type`, `expected_visible_consequence`, `counterfactual_failure`) and world state transition tokens shared with camera & QA.
- **`director/visual_storytelling_director.py`**:
  - `plan_story_action_graph(...)`, `plan_world_state_transitions(...)`, `score_story_diversity(...)`, `validate_narrative_causality(...)`, `validate_reveal_order(...)`.
  - **Gap**: Existing causality check tracks monotonic Boston/Tacoma/generic state tags and reveal-order tokens, rather than generalizable `CausalEvent` -> `VisualEvidenceContract` proof contracts and persistent world state conservation across cuts.

## 2. Shot Direction, Composition & Camera Execution Layer
- **`director/shot_director.py`**:
  - `split_long_visual_beats_by_actions(...)`, `generate_candidate_shot_set(...)`, `score_shot_candidates(...)`, `select_sequence_with_diversity_constraints(...)`, `plan_editorial_coverage(...)`.
  - **Gap**: `score_shot_candidates` optimizes framing/angle/motion diversity (`anti_clone_override`, `anti_triplet_override`), not explicit Q1–Q5 camera information gain (`causal_visibility_gain`, `action_anchoring`, `novel_evidence_gain`).
- **`director/cinematic_composition.py`**:
  - `design_frame_for_action(...)`, `plan_reveal_camera(...)`, `score_visual_progression(...)`, `write_frame_design_intent(...)`.
  - **Gap**: Defines `salient_action_anchor` and safe rects, yet lacks `CameraIntentContract` (`why_this_shot`, `what_viewer_learns`, `target_causal_feature_id`, `counterfactual_loss_if_omitted`, `reference_anchor_id`).
- **`director/camera_choreographer.py` & `director/camera_execution.py`**:
  - `plan_camera_path(...)`, `build_camera_plan(...)`, `CAMERA_EXECUTOR_JS`, `evaluate_camera_path_py(...)`, `evaluate_camera_trace_accuracy(...)`.
  - **Preserve**: Single-authority Three.js + Python camera evaluator; zero drift tolerated (`pos <= 0.015 * diag`, `ori <= 0.65 deg`, `fov <= 0.65 deg`).

## 3. Editorial Design System, Curiosity Headlines & Tracked Pointers
- **`director/curiosity_director.py` & `director/editorial_overlay.py` & `director/editorial_design_system.py`**:
  - `find_curiosity_beats(...)`, `plan_attention_pointer(...)`, `validate_reveal_lock(...)`, `build_editorial_timeline(...)`, `derive_editorial_role(...)`.
  - **Gap**: Overlays carry `target_semantic_id`, `target_mesh_ids`, `pointer_reason`, yet do not bind formally to `narrative_claim_id`, `proof_target_id`, `why_this_overlay`, and `semantic_region_of_change`, nor support contextual atmospheric/causal proof zones cleanly.

## 4. 3D Scene Assets, Engine Adapter & Audio/SFX
- **`director/scene_asset_factory.py`**:
  - `ZDF_ARCHETYPE_REGISTRY`, `build_character_and_prop_registry(...)`, `_map_family_to_generator(...)`, `compile_scene_entities(...)`, `materialize_engine_scene(...)`.
- **`director/assets/zach_d_films_adapter.py`**:
  - `_build_non_roman_scene_shot_code(...)`, `_build_zach_shots_js(...)`, `resolveSemanticRole(obj, sceneRef)` (`causal_feature=0x00ff00`, `character=0x0000ff`, `subject=0xff0000`, `environment=0x282828`), `window.renderMatteAtTime`.
- **`director/audio_narrative.py` & `director/sfx_director.py`**:
  - `extract_sound_events(...)`, `select_procedural_sfx(...)`, `render_sfx_stem(...)`.
  - **Note**: Extend cleanly with atmospheric haze/fog/cough/street/stove/bus audio intents tied to visible action timestamps without breaking Tacoma/Boston/elevator cues.

## 5. Quality Gates & Decoded Visual QA
- **`director/decoded_visual_quality.py`**, **`director/visual_storytelling_qa.py`**, **`director/cinematic_composition_qa.py`**, **`director/quality_gate.py`**, **`director/retention_qa.py`**:
  - Decode 270x480 RGB + WebGL semantic mattes (`_masks_from_matte_rgb`), check camera-compensated motion, figure-ground edge separation, pointer tracking error (`<= 36 px` at 1080), historical claims qualifiers, and A/B VO PCM SHA parity.
  - **Gap**: Need `semantic_visual_evidence_qa.py` for decoded claim coverage (`visual_claim_coverage.json`), before/action/after proof strips (`event_aligned_before_action_after.jpg`), relative displacement against fixed reference (`reference_fixed` / landmarks), transition causal continuity, semantic pointer verification (`pointer_semantics.json`), blocking vs advisory WARN discipline, and `N01`–`N40` metamorphic negative suite.
