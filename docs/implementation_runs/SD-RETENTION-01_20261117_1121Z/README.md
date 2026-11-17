# SD-RETENTION-01.R1 Execution & Verification Log (`2026-11-17T11:21Z`)

## 0. Baseline Startup Audit, Branch & Host Toolchain

- **Repository Root**: `D:\Project_github\Skill-animations\short-director\Skill-Animation-Video`
- **Original Base Branch**: `master` @ `6d9f31e5f3d4a9f9127543bb3648c031de09a3fb` (`origin/master` synced cleanly)
- **Feature Branch (Forked Cleanly from `origin/master`)**: `feat/sd-retention-01-expressive-editorial`
- **Remote Origin**: `https://github.com/quocan050302/Skill-Animation-Video.git`
- **Submodule (`vendor/claude-animation-skills`)**: Initialized cleanly at pinned SHA `5dbea55c23aa6a5c93dc3cfb5583840513b56b94` (untouched)
- **Safety Guarantees**:
  - `master` remains untouched; all edits and commits target `feat/sd-retention-01-expressive-editorial`.
  - Pre-existing runs (`runs/zdf_motion01_elevator_20261117_0131Z/`) preserved untouched and never reused as demo frames/stills/MP4s.

### Host Toolchain & Pre-Edit Observations
| Component | Observed Value | Notes |
|---|---|---|
| OS & CPU | Windows 11 (AMD64), 12 logical cores | Shell: PowerShell |
| RAM | 31.75 GiB total (~11.01 GiB free at startup) | Python `3.12.10` (`numpy 2.5.4`, `scipy 1.18.1`, `soundfile 0.14.0`, `PIL 13.0.0`) |
| Disk Free | Drive `D:` 53.98 GiB free | `DiskBudgetGuard` floor: `max(4 GiB, 20% initial free)` (~10.8 GiB) |
| Browser & WebGL | `C:\Program Files\Google\Chrome\Application\chrome.exe` | ANGLE `d3d11`, Playwright + Three.js offline |
| Offline Fonts | `vendor/claude-animation-skills/kit/node_modules/@fontsource/montserrat/files/` (`400`–`900` `.woff2`) + `kit/fonts/` | Local-only font assets; zero runtime CDN download |
| Neural TTS (`kokoro`) | Not installed (`kokoro_onnx` / `onnxruntime` / `kit/models/` absent) | Must report `neural_prosody=False` honestly when using SAPI5 |
| Offline SAPI5 TTS | Windows `System.Speech` (`Microsoft David Desktop`, `Microsoft Zira Desktop`) | Live `SpeakSsml` probe confirmed real rate (`-18%`/`+20%`), pitch (`-20%`/`+25%`), emphasis (`+4.0 dB`, `111.4 Hz`), and `<break time='500ms'/>` support |
| `gh` CLI | Not installed on host | Step 8/11 demo handoff reports `PREVIEW_CREATED_LOCAL_ONLY` honestly if remote upload requires `gh` |

### Baseline Test Snapshot (Before Code Edits)
- Archived in `logs/baseline_unittest.log` via `python -m unittest discover -s tests -v`.
- **Result**: `Ran 42 tests in 493.433s` — **41 `ok`**, **1 `ERROR`** (`test_a4_corrupt_zero_wrong_hash_and_path_traversal_rejected` failed solely on `sym.symlink_to(outside)` due to unprivileged Windows `WinError 1314`).

---

## 1. Acceptance Matrix (`G01`–`G21`)

| Gate | Requirement | Planned Implementation / Proof |
|---|---|---|
| `G01` | Fresh branch from clean `origin/master`; `master` untouched; `vendor` clean | Git provenance log & pre/post branch checks |
| `G02` | `docs/implementation_runs/SD-RETENTION-01_<TS>/` created pre-edit + `factual_sources.md` | Present before source edits |
| `G03` | `DiskBudgetGuard` forecasts A/B 1080p + 4K + workspace; clean temp staging | `director/preflight.py` + disk telemetry |
| `G04` | Honest voice capability disclosure (`neural_prosody`, `ssml_supported`, real probes) | `director/preflight.py`, `director/voice_prosody.py`, `voice_delivery_report.json` |
| `G05` | Semantic `voice_prosody_plan.json` + token conservation + real rate/pitch/emphasis/pause | `director/voice_prosody.py` + `director/parse_script.py` + `test_voice_prosody.py` |
| `G06` | Honest word/phrase timing provenance (`word_anchor_confidence="ESTIMATED"` when heuristically aligned) | `director/parse_script.py` + `director/retention_qa.py` |
| `G07` | Single authoritative `editorial_timeline.json` aligned cleanly across VO/caption/overlay/SFX | `director/editorial_overlay.py` + cross-track invariant checks |
| `G08` | Kinetic captions & smart 3D callouts in ZDF without clutter, safe-margin spill, or occlusion | `editorial_overlay_renderer.js`, `zach_d_films_adapter.py`, `test_editorial_overlays.py` |
| `G09` | Overlay diff proof (non-zero pixels in expected overlay region without obscuring 3D anchor) | `director/retention_qa.py::audit_overlay_render` |
| `G10` | Dynamic 3D focus rings/arrows track `camera.project` & hide when offscreen/occluded | `editorial_overlay_renderer.js::getOverlayTelemetry` + `audit_annotation_tracking` |
| `G11` | Verified numeric callouts only (no unverified/invented statistics promoted as counters) | `factual_sources.md` + negative number-invention guard |
| `G12` | Motivated layered SFX locked to `editorial_timeline.json`, anti-fatigue, contrast ducking, twist silence | `director/audio_dsp.py`, `director/sfx_director.py`, `director/music_director.py`, `director/mix_audio.py` |
| `G13` | Preserve 6-engine single-skill lock, audio catalog licenses/paths, 5 non-ZDF engines untouched | Isolation checks across all 6 visual skills |
| `G14` | Portable Windows path-traversal `test_a4` without skipping security checks | `tests/test_audio_catalog_and_licenses.py` + symlink fallback |
| `G15` | Brand-new 30–35s airplane-window bleed-hole 3D demo (`A` 1080p, `B` 1080p, `B` native 4K) | `director/assets/zdf_aircraft_window_scenes.py` + `runs/sd_retention01_airplane_window_...` |
| `G16` | Full decoded `B - A` A/B evidence (`voice_ab_probe.wav`, stills, contact sheets, JSON metrics) | `ab_comparison/` + human-readable Markdown report |
| `G17` | 16 mandatory negative / fault-injection traps fail closed | `tests/test_voice_prosody.py`, `test_editorial_overlays.py`, `test_retention_audio_sync.py`, `test_retention_e2e.py` |
| `G18` | Bounded async validation (`T0`–`T12`) & deterministic multithread/seed output | `tools/run_validation_async.py --mode full` |
| `G19` | Full `python -m unittest discover -s tests -v` (`0` failures, `0` errors) | `logs/unittest_discover_final.log` |
| `G20` | Truthful status labels (`subjective_* = NOT_VERIFIED`, zero invented claims/URLs) | `qc_report.json`, `run_manifest.json`, `demo_delivery_status.json` |
| `G21` | Updated `README.md`, `skills/short-director/SKILL.md`, scoped commits & push to feature branch | Remote `origin/feat/sd-retention-01-expressive-editorial` |

---

## 2. Architecture & Modules Implemented (`+4` New Runtime Modules, `+4` New Test Suites, Engine-Locked Upgrades)

### New Modules Created
- **`director/voice_prosody.py`**: `SCHEMA_VERSION = "sd-voice-prosody-1"`, `get_backend_capabilities()`, `score_emphasis_candidates()`, `plan_phrase_delivery()`, `build_prosody_plan()`, `validate_prosody_plan()`, `measure_voice_delivery()`, `write_prosody_artifacts()`, `render_voice_ab_probe()`, `check_token_conservation()`.
- **`director/editorial_overlay.py`**: `SCHEMA_VERSION = "sd-editorial-timeline-1"`, `plan_kinetic_captions()`, `extract_editorial_focus_events()`, `plan_3d_callouts()`, `validate_overlay_plan()`, `build_editorial_timeline()`, `EDITORIAL_OVERLAY_RENDERER_JS` (`EditorialOverlayController` SVG + DOM kinetic renderer with `camera.project` & occlusion hiding).
- **`director/assets/zdf_aircraft_window_scenes.py`**: `AIRCRAFT_WINDOW_SCENES_JS` (`makeAircraftWindowAssemblyRig()`, `computeAnchorsTelemetry()`): 3-pane multi-layer pressurized cabin window assembly (dark slate fuselage bulkhead + brushed bezel, outer structural pane, middle fail-safe pane with pierced circular bleed hole + brass collar, inner scratch pane, `LayeredCutaway` separation, crimson pressure vectors, moisture defogging particles, raycast occlusion anchors).
- **`director/retention_qa.py`**: `audit_prosody_delivery()`, `audit_word_alignment()`, `audit_overlay_render()`, `audit_annotation_tracking()`, `audit_sfx_editorial_sync()`, `audit_editorial_fatigue()`, `compare_ab_versions()`, `run_retention_editorial_qa()`.

### Updated Core Modules
- **`director/preflight.py`**: Added `requested_backend` support (`auto|kokoro|windows_sapi|macos_say`), `DiskBudgetGuard.estimate_ab_demo_bytes()`, and honest `backend_capabilities` matrix in `PreflightResult.voice_backends`.
- **`director/parse_script.py`**: Added phrase-level prosody execution (batched single-process SAPI5 `SpeakSsml` + Kokoro speed/pauses + macOS `say` rate/pauses), sample-exact cursor timing, honest `word_anchor_confidence` (`ESTIMATED` for CDF heuristic vs `EXACT_FORCED`), and `measure_voice_delivery()` fail-closed verification.
- **`director/build_storyboard.py` & `director/render_scene.py`**: Generates `editorial_timeline.json`, `overlay_plan.json`, `overlay_coverage.json`; captures WebGL telemetry (`anchors`, `overlay`) at active overlay midpoints in `raw_render_telemetry.json`.
- **`director/assets/zach_d_films_adapter.py`**: Wired `EditorialOverlayController`, `AIRCRAFT_WINDOW_SCENES_JS`, per-shot aircraft window scenes & raycast anchors (`zach-d-films` only; non-ZDF engines receive `callout_mode="off"` and zero overlay controller injection).
- **`director/visual_event_graph.py`, `director/scene_asset_factory.py`, `director/shot_director.py`, `director/camera_choreographer.py`**: Added `airplane_window_bleed` domain classification, `zach3d:airplane_window_hole_stage` registry + 5 distinct setups/camera trajectories, and split-fragment domain preservation.
- **`director/audio_dsp.py`, `director/audio_catalog.py`, `director/sfx_director.py`, `director/audio_narrative.py`, `director/mix_audio.py`**: Added `_ui_pop_soft`, `_marker_ring_draw`, `_arrow_swish`, `_reveal_soft`, `_low_sting`, `_airflow_hiss`, synced editorial overlay SFX to `editorial_timeline.json` with anti-double-pop guards, and added cosine-ramped twist-beat music contrast ducking.
- **`director/quality_gate.py`, `director/run.py`**: Wired `editorial_retention_finish`, `editorial_qa_report.json`, `editorial_attention_timeline.json`, CLI flags (`--voice-style`, `--voice-backend`, `--voice-prosody-in`, `--voice-pause-strength`, `--voice-compare-ab`, `--caption-mode`, `--callout-mode`, `--verified-numbers-json`), and `tests/test_audio_catalog_and_licenses.py` portable `test_a4` Windows fallback.

---

## 3. Airplane Window Demo & A/B Objective Evidence (`runs/sd_retention01_airplane_window_20261117_1150Z`)

- **Topic & Script**: *Why Airplane Windows Have a Tiny Hole (Bleed / Breather Hole)* grounded in `factual_sources.md` (`14 CFR § 25.775`, `FAA AC 25.775-1`, 3-pane multi-layer assembly).
- **Delivery Declaration (`demo_delivery_status.json`)**: `PREVIEW_CREATED_LOCAL_ONLY` (`gh` CLI absent on host; local MP4/WAV paths & SHA-256 checksums recorded verbatim).
- **Version A (`baseline_A`, `--voice-style legacy --caption-mode plain --callout-mode off --render-4k-mode upscale`)**:
  - `preview_1080.mp4`: `15,616,422` bytes (`1080x1920`, `30 fps`, `30.863s`, `-15.3 LUFS`, `-2.4 dBTP`)
  - Voice prosody span: `phrase_count=8`, `wps_dynamic_span_pct=47.43%`, `rms_dynamic_span_db=2.20 dB`, `f0_median_span_hz=7.88 Hz`
  - SFX cues: `11`; `scene_diversity_status=PASS`, `camera_execution_status=PASS`, `editorial_finish_status=PASS`
- **Version B (`enhanced_B`, `--voice-style cinematic --caption-mode kinetic --callout-mode smart --sfx-density detailed --voice-compare-ab --render-4k-mode native`)**:
  - `preview_1080.mp4`: `14,508,789` bytes (`1080x1920`, `30 fps`, `34.896s`)
  - `final_4k.mp4`: `49,792,288` bytes (`2160x3840`, `h264`, `yuv420p`, `30 fps`, `34.896s`, `aac 48000Hz stereo`), `native_4k=True` (`high_freq_edge_ratio_vs_1080p_bilinear=1.2528`), `-15.6 LUFS`, `-2.4 dBTP`
  - Voice prosody span: `phrase_count=14`, `wps_dynamic_span_pct=67.49%` (`+20.06%`), `rms_dynamic_span_db=5.94 dB` (`+3.74 dB`), `f0_median_span_hz=16.59 Hz` (`+8.71 Hz`), `voice_ab_probe.wav` generated
  - SFX cues: `17`; Camera errors: `worst_pos_err_m=0.0`, `worst_ori_err_deg=0.165`, `worst_fov_err_deg=0.0`; All `editorial_retention_finish` sub-checks (`prosody_delivery`, `word_alignment`, `overlay_render`, `annotation_tracking`, `sfx_editorial_sync`, `editorial_fatigue`) = `PASS`; factual tone audit `WARN_HEDGED` (`"never"` flagged honestly -> `overall_qc_status=WARN`, `release_status=TECHNICAL_ACCEPTANCE_PASS`).
  - Paired visual frame deltas (`ab_report.json`): `has_measurable_visual_diff=True` (`frame_mad` `9.85..43.83`, `caption_band_mad` `14.14..75.18`).
- **Visual Stills & Contact Sheets Verified via `read_file`**: Inspected `baseline_A/contact_sheet.jpg`, `enhanced_B/contact_sheet.jpg`, and `enhanced_B/stills/still_{1.883,3.707,8.767,12.117,14.966,24.716,32.465}.png` — confirmed crisp 3-pane optical/frame contrast, real gold bleed-hole ring + curved leaders inside safe bounds (`100..980 x 220..1500`), caption legibility above bottom threshold, and zero panel overflow.

---

## 4. Post-Change Test Results (After Final Edit)

| Suite / Command | Result | Duration | Notes & Log Path |
|---|---|---|---|
| `python tools/run_validation_async.py --mode full --workers 2` | **12/12 `PASS` (`exit=0`)** | `329.80s` | `logs/async_dag/validation_summary.json` (`audio_catalog_licenses`, `unit_and_negative`, `visual_event_coverage`, `audio_determinism`, `voice_prosody`, `zdf_motion01_matrix`, `editorial_overlays`, `determinism_and_resources`, `visual_scene_factory_e2e`, `retention_audio_sync`, `retention_e2e`, `smoke_all_engines`) |
| `python -m unittest discover -s tests -v` | **50/50 `OK` (`exit=0`)** | `510.025s` | `logs/unittest_discover_final.log` (`0` failures, `0` errors, `0` skipped — includes `test_a4` portable fix & 16 negative traps) |
| Submodule & Branch Verification | Clean | — | `vendor/claude-animation-skills` clean at `5dbea55...`; `master` untouched at `6d9f31e...`; all work scoped on `feat/sd-retention-01-expressive-editorial` |

---

## 5. Honest Truthfulness & `NOT_VERIFIED` Declarations
- `subjective_visual_review = NOT_VERIFIED` (human eye-check of rendered PNGs performed on sampled stills/contact sheets, full continuous video playback & aesthetic sign-off by user not performed here)
- `subjective_editorial_listening = NOT_VERIFIED` (no human playback of WAV/MP4 audio mix)
- `subjective_voice_quality_status = NOT_VERIFIED` (`Microsoft David Desktop` is offline SAPI5 `neural_prosody=False`, confirmed via `voice_delivery_report.json`)
- `viewer_retention_status = NOT_VERIFIED` (objective timing/prosody/contrast/overlay audits are engineering proxies only, never proof of watch-time or virality)
- `word_anchor_confidence = "ESTIMATED"` (phrase-bounded bandpass vocal-energy CDF; forced ASR aligner unavailable offline)
