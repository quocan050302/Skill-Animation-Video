# Baseline Proof Runs — Inspected Scene & Shot Timelines

Only proofs genuinely present locally on Windows are detailed with shot timings below; remote macOS Skyscraper MP4s are explicitly marked unavailable locally.

## 1. Local Tacoma Narrows R2 Proof (`runs/sd_retention03_r2_tacoma_proof_20261118`)
- **Duration**: `43.333s` encoded (`43.35s` planned), `2160x3840` upscaled (`upscaled_lanczos_from_1080x1920`), `overall_status = WARN` (`shot_06` edge sep `6.6 < 12.0`).
- **Shot Sequence**:
  - `shot_00 [0.0..4.933]`: `zach3d:tacoma_hook_telephoto_stage` (`CU_TelephotoSpan`, `bridge_hook_initial_sway`) — Overlay `THE ROAD / WAS MOVING!`
  - `shot_01 [4.933..9.633]`: `zach3d:tacoma_wide_establish_stage` — `TACOMA NARROWS`
  - `shot_02 [9.633..13.933]`: `zach3d:tacoma_roadway_wave_stage` (`bridge_vertical_bounce`)
  - `shot_03 [13.933..17.267]`: `zach3d:tacoma_wide_establish_stage` (`bridge_vertical_bounce`) — `2,800 FT MAIN SPAN`
  - `shot_04 [17.267..21.833]`: `zach3d:tacoma_under_deck_girder_stage` (`plate_girder_wind_loading`) — `8-FT PLATE GIRDER`
  - `shot_05 [21.833..26.367]`: `zach3d:tacoma_torsion_twist_stage` (`torsional_flutter_escalation`) — `THEN IT / STARTED TWISTING`
  - `shot_06 [26.367..28.367]`: `zach3d:tacoma_shore_onlooker_stage` (`bridge_shore_reaction`)
  - `shot_07 [28.367..30.667]`: `zach3d:tacoma_torsion_twist_stage` (`torsional_flutter_escalation`) — `WHOLE DECK TWISTING`
  - `shot_08 [30.667..36.8]`: `zach3d:tacoma_collapse_plunge_stage` (`bridge_span_collapse`) — `SPAN BROKE FREE`
  - `shot_09 [36.8..40.233]`: `zach3d:tacoma_aftermath_stage` (`bridge_collapse_aftermath`) — `0 HUMAN FATALITIES`
  - `shot_10 [40.233..43.35]`: `zach3d:tacoma_aftermath_stage` (`bridge_code_redesign_aftermath`)
- **Casual Causal Critique (Target for SD-RETENTION-04 Upgrade)**:
  - `shot_01` and `shot_03` reuse `tacoma_wide_establish_stage`; `shot_05` and `shot_07` reuse `tacoma_torsion_twist_stage`; `shot_09` and `shot_10` reuse `tacoma_aftermath_stage` without distinct causal world-state progression metadata or explicit camera Q1–Q5 contracts explaining *what new visual proof* each cut reveals.

## 2. Local Boston Molasses R2 Proof (`runs/sd_retention03_r2_boston_proof_20261118`)
- **Duration**: `31.633s` encoded (`31.636s` planned), `overall_status = WARN` (`shot_03` edge sep `11.7 < 12.0`, `shot_07` edge sep `6.5 < 12.0`).
- **Shot Sequence**: `10` shots across `boston_street_hook_stage` (x2), `boston_molasses_reveal_stage`, `boston_tank_leak_stage`, `boston_tank_rupture_stage`, `boston_wave_street_stage`, `boston_elevated_rail_impact_stage`, `boston_rescue_aftermath_stage`, `boston_harbor_payoff_stage`, `boston_engineering_cutaway_stage`.
- **Causal Critique**: Same-hook repeat (`shot_00`, `shot_01` both `boston_street_hook_stage`) and `pointer_reason = None` on all 7 Boston overlays (R2 Tacoma had rich `pointer_reason`s while Boston fallback missed them).

## 3. Remote MacOS Skyscraper Proof (`runs/sd_retention03_r2_skyscraper_20261117`)
- **Local MP4 Status**: `UNAVAILABLE_LOCAL_MP4` (`LOCAL_ONLY_ON_HOST` on macOS during checkpoint `b393789`).
- **Curated Evidence Inspected in Git**: `docs/implementation_runs/SD-RETENTION-03_R2_20261117_1135Z/qa_summary.json` (`38.3s`, `2160x3840` native 4K, `overall_status = PASS`, `pointer_tracking` 11/11 tips <= 13.29px).
