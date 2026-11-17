# SD-RETENTION-02.R1 Execution & Verification Log (`2026-11-17T06:41Z`)

## 0. Baseline Audit, Branch Provenance & Constraints

- **Repository Root**: `D:\Project_github\Skill-animations\short-director\Skill-Animation-Video`
- **Existing Branch Used**: `feat/sd-retention-01-expressive-editorial` (descends from `master` @ `6d9f31e5f3d4a9f9127543bb3648c031de09a3fb`)
- **Starting HEAD SHA**: `3cea6e5ecda307a29a4dac1220d10e1ca04d0b9a` (matches `origin/feat/sd-retention-01-expressive-editorial`)
- **Upstream Submodule**: `vendor/claude-animation-skills` clean at `5dbea55c23aa6a5c93dc3cfb5583840513b56b94` (unmodified)
- **Host Resources**: Windows 11, 12 logical cores, `53.48 GiB` free on `D:`, offline Windows SAPI5 voices `Microsoft David Desktop` & `Microsoft Zira Desktop`; `kit/models/` absent (no offline Kokoro/Whisper ONNX models installed).
- **Prior Run Safety**: Existing `SD-RETENTION-01` docs and prior `runs/` media preserved untouched and never reused as inputs/frames.

---

## 1. Phase Acceptance Plan (`R2.1`–`R2.7` & Gates 1–13)

| Phase | Target | Verification Plan |
|---|---|---|
| `R2.1` | Generalizable `visual_storytelling_director.py` (`story_action_graph.json`, world-state progression, causal reveal lock) + `boston_molasses_1919` domain | `test_visual_storytelling_director.py` (>=3 distinct topics + anti-repetition + reveal-order traps) |
| `R2.2` | Multi-location 1919 Boston 3D scenes (`zdf_boston_molasses_scenes.py`: North End street, 1915 riveted tank, seam leak/rupture, molasses gravity current wave, elevated rail impact, 1919 crowd, rescue aftermath, overview) | `test_boston_molasses_scenes.py` (real WebGL time-varying deformation, crowd motion, occlusion telemetry, 1919 period integrity) |
| `R2.3` | Voice candidate audit & natural rhythmic narration (`voice_prosody.py`, `voice_candidate_eval.py`, `parse_script.py`, `VOICE_LISTENING_CHECKLIST.md`) | `test_voice_prosody.py` (A/B + multi-voice candidates, smooth seams, token conservation, N11/N12 traps, `NOT_VERIFIED` subjective rule) |
| `R2.4` | Physical caption word separation (`flex-wrap`, measured inter-word spacing), phone-width readability (`320`/`360`/`390`/`1080`), delayed reveal (`molasses` / stats), clean tracked callouts | `test_editorial_overlays.py` (ON/OFF pixel proof, word spacing >= threshold at 360px & 1080px, early-spoiler trap N06/N08) |
| `R2.5` | Restrained action-bound SFX (`tank_structural_groan`, `rivet_tension_ping`, `tank_rupture_impact`, `molasses_wave_rush`, `street_obstacle_impact`, etc.) + pre-rupture quiet & casualty music thin-out | `test_retention_audio_sync.py` (<= 1 frame physical sync, N13/N24 traps, lossless `--audio-only` packet check) |
| `R2.6` | Critical QA false-pass fixes (`audit_overlay_render` true pixel/telemetry/mask proof, `compare_ab_versions` event-aligned `ab_alignment.json`) + `visual_storytelling_qa.py` | `test_storytelling_qa.py` + `N01`–`N24` negative traps failing closed |
| `R2.7` | Bounded async DAG (`tools/run_validation_async.py`), disk guard, full regression & new showcase demo *"The Day Boston Was Flooded With Molasses"* (`baseline_A`, `enhanced_B` 1080p + native 4K) | `run_validation_async.py --mode full` + `python -m unittest discover -s tests -v` (`0` fail/error) |

---

## 2. Implemented Changes (`R2.1`–`R2.6`)

1. **Event-Driven Visual Storytelling (`R2.1`)**:
   - Added [`director/visual_storytelling_director.py`](../../../director/visual_storytelling_director.py) (`plan_story_action_graph`, `plan_world_state_transitions`, `score_story_diversity`, `validate_reveal_order`, `validate_narrative_causality`, causal & 1919 period integrity guards).
   - Updated [`director/visual_event_graph.py`](../../../director/visual_event_graph.py), [`director/scene_asset_factory.py`](../../../director/scene_asset_factory.py), [`director/shot_director.py`](../../../director/shot_director.py), [`director/camera_choreographer.py`](../../../director/camera_choreographer.py), and [`director/build_storyboard.py`](../../../director/build_storyboard.py) with `story_action_graph.json`, sub-shot action reclassification, `boston_*` stage registration (`ZDF_ARCHETYPE_REGISTRY`), period 1919 character outfits, and reveal-order spoiler locks while keeping non-ZDF engines locked & isolated.
2. **Modular 1919 Boston 3D Scenes & True Geometric Contact (`R2.2`)**:
   - Created [`director/assets/zdf_boston_molasses_scenes.py`](../../../director/assets/zdf_boston_molasses_scenes.py) with deterministic WebGL rigs (`makeNorthEndStreet1919`, `makeMolassesStorageTank1919`, `makeSeamLeakAndRivetFailureRig`, `makeMolassesGravityCurrentRig`, `makeElevatedRailAndStreetImpactRig`, `makePeriodCrowdActionRig`, `makeRescueAndAftermathRig`, `makeBostonSteelSectionCutawayRig` via `LayeredCutaway`, and `makeBostonLocationOverview`).
   - Updated [`director/assets/zach_d_films_adapter.py`](../../../director/assets/zach_d_films_adapter.py) to wire all 9 `zach3d:boston_*_stage` generators, emit `narrativeAction`, and expose real Three.js `world_error_m` geometric measurements at tank rupture and elevated-rail surge impact.
3. **Expressive Voice, Candidate Audit & Smooth Boundaries (`R2.3`)**:
   - Extended [`director/preflight.py`](../../../director/preflight.py), [`director/voice_prosody.py`](../../../director/voice_prosody.py), and [`director/parse_script.py`](../../../director/parse_script.py) with `--voice-id` selection, storytelling cadence intents (`hook_whispered_curiosity`, `quiet_foreshadow`, `rupture_burst`, `danger_acceleration`, `human_cost`, `reflective_payoff`), 12 ms raised-cosine phrase-boundary fades (`_apply_phrase_edge_envelope`), and temporary `.ps1` `-File` SAPI5 invocation preventing Windows `CreateProcess` command-line truncation.
   - Created [`director/voice_candidate_eval.py`](../../../director/voice_candidate_eval.py) generating multi-voice WAV candidates (`voice_only_A.wav`, `voice_only_B.wav`, `voice_only_Zira.wav`, `voice_ab_probe.wav`) plus `VOICE_LISTENING_CHECKLIST.md` with honest `neural_prosody=False` & `subjective_voice_quality_status="NOT_VERIFIED"`.
4. **Flex Kinetic Captions & Grounded Reveal-Locked Callouts (`R2.4`)**:
   - Updated [`director/editorial_overlay.py`](../../../director/editorial_overlay.py) to flex-wrap captions (`columnGap: 0.40em`, `rowGap: 0.20em`, active scale capped at `1.05x`), export real `getBoundingClientRect()` DOM spacing (`caption_layout`), enlarge phone-readable callouts, enforce spoken-word spoiler gating (`>= 0.60s` active window), and bind historical labels strictly to verified claims (`"RIVETED STEEL SEAM"`, `"~2.3M GALLONS"`, `"~35 MPH EST."`, `"21 LIVES LOST"`).
5. **Action-Bound Audio & Mixing (`R2.5`)**:
   - Added bespoke disaster/period DSP synthesis & ambiences in [`director/audio_dsp.py`](../../../director/audio_dsp.py), [`director/sfx_director.py`](../../../director/sfx_director.py), [`director/audio_catalog.py`](../../../director/audio_catalog.py), [`director/audio_narrative.py`](../../../director/audio_narrative.py), and [`director/mix_audio.py`](../../../director/mix_audio.py), synchronizing `tank_rupture_impact` & `street_obstacle_impact` to physical contact hits (`<= 1` frame) and quieting pre-rupture & casualty music beds.
6. **False-Pass-Proof Post-Render QA & Async DAG Validation (`R2.6`–`R2.7`)**:
   - Upgraded [`director/retention_qa.py`](../../../director/retention_qa.py) (`audit_overlay_render` luminance-mean std check + DOM telemetry + optional matched ON/OFF diff; `compare_ab_versions` event-aligned `ab_alignment.json` failing closed on mismatched scripts).
   - Added [`director/visual_storytelling_qa.py`](../../../director/visual_storytelling_qa.py) (`visual_storytelling_qa_report.json`), wired into [`director/quality_gate.py`](../../../director/quality_gate.py) and [`director/run.py`](../../../director/run.py) (`--voice-id`, `--historical-claims-json`, `--factual-sources-note`), plus [`tools/run_validation_async.py`](../../../tools/run_validation_async.py) and tests in `tests/`.

---

## 3. Showcase Deliverable Verification — *The Day Boston Was Flooded With Molasses*

Rendered locally inside `runs/sd_retention02_boston_molasses_20261117_0725Z/` (`delivery_status: PREVIEW_CREATED_LOCAL_ONLY`, `github_release_status: NOT_UPLOADED_GH_CLI_ABSENT`; heavy video binaries excluded from Git tracking):

- **Baseline A (`baseline_A/`)**: `legacy` voice (`Microsoft David Desktop`), `plain` captions, `callout_mode=off`, `1080x1920` preview (`34.226s`, SHA-256 `b0ae211c395c8ee347c4ac78f2eadcc95ee6d57ee127399affdfb09e7dd83a24`, `14,399,416 bytes`), `overall_status: PASS`.
- **Enhanced B (`enhanced_B/`)**: `cinematic` voice (`Microsoft David Desktop`), `kinetic` captions, `smart` overlays, **true native 4K (`2160x3840`)** + `1080x1920` preview:
  - `preview_1080.mp4`: `1080x1920` H.264 `30 fps`, video `39.833s` / audio `39.853s`, `13,396,950 bytes`, SHA-256 `f1500c86f434c2a948595a4cf2953df91f9dd21fb6a6159be01ea17038c8fdc6`.
  - `final_4k.mp4`: `2160x3840` H.264 `30 fps`, `native_4k: true`, `high_freq_edge_ratio_vs_1080p_bilinear: 1.258`, `46,601,706 bytes`, SHA-256 `73946b9412f4b75d37a45d096871aabdb22580932851993a60158cfd105081ba`.
  - **Audio / Loudness (`ffprobe` + `ebur128`)**: Integrated `-14.9 LUFS`, `LRA: 2.8 LU`, `True Peak: -2.3 dBTP` / `-2.3 dBFS`, `0` clipping; `17` SFX cues (`max_sync_err_ms: 0.0` on overlay cues); voice spans `WPS 125.5%`, `RMS 3.63 dB`, `F0 14.93 Hz`, `max_pause_error_ms: 0`.
  - **Cinematography & Story QA**: `distinct_setups_verified: 10`, `distinct_actions_count: 10`, `distinct_locations_count: 9`, `max_unchanged_asset_run: 1`, `worst_pos_err_m: 0.0`, `worst_ori_err_deg: 0.166`, `worst_contact_err_m: 0.0047`, `caption_layout min_word_gap_px: 17.34` (`89` DOM chunks, `0` overlaps), `historical_claims: PASS` (`6` claims / `7` overlays).
  - **Controlled A/B & ON/OFF Pixel Diff (`ab_comparison/`)**: `ab_alignment.json` aligns all `10` narrative events (`script_similarity: 1.0`); matched frame at `t=17.976s` (`ov_03`: `~2.3M GALLONS`) shows `roi_mad_pixels: 53.707` between `overlay_on_frame.png` and `overlay_off_frame.png`.
  - **Visual Inspection**: Reviewed `enhanced_B/contact_sheet.jpg`, `ab_comparison/overlay_on_frame.png`, `ab_comparison/overlay_off_frame.png`, and decoded `stills/` frames verifying period 1919 staging, caption legibility, non-spoiler opening (`molasses` callout gated until `7.752s`), layered steel cutaway flow pulse, and dusk lantern rescue composition.

### Honest Limitations & Mandatory `NOT_VERIFIED` Statuses
- **Host Voice Engine Capability**: Local host provides offline concatenative SAPI5 desktop voices (`Microsoft David Desktop`, `Microsoft Zira Desktop`) only; `kit/models/` contains no offline Kokoro/Whisper ONNX models (`neural_prosody: false`, `word_anchor_confidence: "ESTIMATED"`).
- **Mandatory `NOT_VERIFIED` Subjective Gates**:
  - `subjective_visual_review`: **`NOT_VERIFIED`**
  - `subjective_editorial_listening`: **`NOT_VERIFIED`**
  - `subjective_voice_quality_status`: **`NOT_VERIFIED`**
  - `viewer_retention_status`: **`NOT_VERIFIED`**

---

## 4. Final Automated Validation Gates (Executed After Final Code Edit)

1. **Bounded Async Validation DAG**:
   `python tools/run_validation_async.py --mode full --workers 2 --log-dir docs/implementation_runs/SD-RETENTION-02_20261117_0641Z/logs/async_dag_final`
   - **Result**: `overall_status: PASS`, **`15/15` tasks PASSED** in `399.08s` (`audio_catalog_licenses`, `unit_and_negative`, `visual_event_coverage`, `audio_determinism`, `voice_prosody`, `visual_storytelling_dir`, `storytelling_qa`, `zdf_motion01_matrix`, `editorial_overlays`, `retention_audio_sync`, `boston_molasses_scenes`, `determinism_and_resources`, `smoke_all_engines`, `visual_scene_factory_e2e`, `retention_e2e`).
2. **Full Canonical Unittest Suite**:
   `python -m unittest discover -s tests -v`
   - **Result**: **`Ran 59 tests in 579.762s — OK`** (`0` failures, `0` errors, `0` skipped).

