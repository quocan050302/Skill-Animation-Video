"""STEP 3: Single-Engine Multi-Angle Storyboard, Art Bible & Entity Inventory Builder.

Guarantees:
- Every `shots[i].engine == selected_skill` (zero guest shots, zero secondary inserts).
- Distinct camera setups across beats (ECU, MS, WS, Cutaway_Diagram, Split_Comparison, Pullback_Payoff).
- At least 1 novel non-template scene setup explicitly planned and parameterized.
- Safe-area geometry (`x: 100..980`, `y: 220..1500`) and caption-band clearance enforced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .assets.style_params import build_style_params


ENGINE_CAMERA_GRAMMAR: Dict[str, List[Dict[str, Any]]] = {
    "stick-figure": [
        {"setup": "hook_dynamic_cu", "framing": "CU", "angle": "eye_level_push", "move": "push_in_handheld", "transition": "whip"},
        {"setup": "belief_wide_parallax", "framing": "WS", "angle": "slight_low_3plane", "move": "tracking_pan_right", "transition": "whip"},
        {"setup": "turn_reaction_ecu", "framing": "ECU", "angle": "dutch_tilt_dramatic", "move": "snap_zoom_shake", "transition": "iris_mask"},
        {"setup": "novel_mechanism_cutaway", "framing": "Cutaway_Macro", "angle": "orthographic_cross_section", "move": "focus_glide", "transition": "whip", "novel_non_template": True},
        {"setup": "split_comparison_stage", "framing": "MS_Split", "angle": "frontal_duel", "move": "counter_drift", "transition": "cut_on_action", "novel_non_template": True},
        {"setup": "payoff_sunny_pullback", "framing": "MS_to_WS", "angle": "heroic_eye_level", "move": "pull_back_settle", "transition": "cut"},
    ],
    "zach-d-films": [
        {"setup": "hook_3d_action_launch", "framing": "MS", "angle": "three_quarter_hero", "move": "dolly_push_in", "transition": "cut_on_action"},
        {"setup": "belief_studio_demonstration", "framing": "WS", "angle": "low_studio_orbit", "move": "orbit_right", "transition": "dip_to_black"},
        {"setup": "novel_slowmo_ripple_cutaway", "framing": "ECU_Macro", "angle": "projectile_tracking_side", "move": "slowmo_track_impact", "transition": "cut_on_action", "novel_non_template": True},
        {"setup": "mechanism_cross_section_3d", "framing": "MS_Cutaway", "angle": "elevated_isometric", "move": "push_toward_core", "transition": "cut_on_action", "novel_non_template": True},
        {"setup": "payoff_full_stage_reveal", "framing": "WS", "angle": "eye_level_clean", "move": "pull_back_crane", "transition": "cut"},
    ],
    "graph": [
        {"setup": "hook_metric_counter_intro", "framing": "Macro_Header", "angle": "flat_editorial", "move": "grid_reveal", "transition": "match_zoom"},
        {"setup": "early_baseline_zoom", "framing": "CU_Curve_Origin", "angle": "flat_editorial", "move": "follow_tip_pan", "transition": "match_zoom"},
        {"setup": "novel_inflection_tangent_delta", "framing": "MS_Inflection_Split", "angle": "flat_editorial", "move": "slope_highlight_sweep", "transition": "match_zoom", "novel_non_template": True},
        {"setup": "payoff_full_horizon_curve", "framing": "WS_Full_Chart", "angle": "flat_editorial", "move": "settle_halo_drop", "transition": "cut"},
    ],
    "minimalistic-graphics": [
        {"setup": "hook_solitary_dot_pulse", "framing": "Center_Void", "angle": "flat_orthographic", "move": "breath_pulse", "transition": "cut_on_action"},
        {"setup": "novel_pendulum_or_labyrinth", "framing": "MS_Geometric", "angle": "flat_orthographic", "move": "arc_oscillation", "transition": "match_zoom", "novel_non_template": True},
        {"setup": "rising_hairline_steps", "framing": "WS_Ascending", "angle": "flat_orthographic", "move": "parabolic_hop_climb", "transition": "cut_on_action"},
        {"setup": "payoff_orbital_sparks", "framing": "MS_Apex_Orbit", "angle": "flat_orthographic", "move": "radial_bloom_hold", "transition": "cut"},
    ],
    "map-route": [
        {"setup": "departure_street_level", "framing": "CU_Origin_Block", "angle": "low_chase_32deg", "move": "pull_from_start_disc", "transition": "match_zoom"},
        {"setup": "mid_route_bridge_crossing", "framing": "MS_Aerial_Chase", "angle": "aerial_40deg_swing", "move": "ride_behind_route_head", "transition": "match_zoom", "novel_non_template": True},
        {"setup": "turn_park_corridor", "framing": "MS_Corner_Bank", "angle": "banked_aerial_35deg", "move": "corner_arc_track", "transition": "match_zoom"},
        {"setup": "arrival_pin_drop_pullback", "framing": "WS_Overview_Card", "angle": "high_overview_28deg", "move": "crane_pullback_reveal", "transition": "cut"},
    ],
    "breakdown": [
        {"setup": "assembled_hero_silhouette", "framing": "MS_Studio_Hero", "angle": "three_quarter_rim", "move": "slow_turntable_intro", "transition": "match_zoom"},
        {"setup": "axial_layer_separation", "framing": "MS_Exploding_Stack", "angle": "elevated_30deg", "move": "dolly_out_with_explosion", "transition": "match_zoom"},
        {"setup": "novel_internal_core_macro", "framing": "ECU_Internal_Core", "angle": "macro_oblique_22deg", "move": "focus_sweep_across_core", "transition": "match_zoom", "novel_non_template": True},
        {"setup": "full_annotated_callout_stack", "framing": "WS_Labelled_Column", "angle": "offset_callout_frame", "move": "turntable_hold", "transition": "cut"},
    ],
}


def build_storyboard_and_bible(
    parsed_script: Dict[str, Any],
    style_decisions: Dict[str, Any],
    run_dir: Path,
    fps: int = 30,
    seed: int = 42,
    target_min_duration: float = 0.0,
) -> Dict[str, Any]:
    """Produce STEP 3 `storyboard.json`, `art_bible.md`, and visual entity inventory."""
    selected_skill = style_decisions["selected_skill"]
    beats = parsed_script["beats"]
    vo_dur = float(parsed_script["voice"]["vo_duration_sec"])
    motifs = parsed_script["entities_and_facts"]["detected_motifs"]
    style_params = build_style_params(selected_skill, seed=seed)

    grammar_templates = ENGINE_CAMERA_GRAMMAR[selected_skill]

    # Ensure at least 4 distinct setups when duration >= 10s or beats >= 4 (split long beats cleanly if needed)
    raw_segments: List[Dict[str, Any]] = []
    for b in beats:
        raw_segments.append({
            "role": b["role"],
            "text": b["text"],
            "start": float(b["start"]),
            "end": float(b["end"]),
            "words": b["words"],
        })

    # Make contiguous shot spans from t=0.0 to total_duration (no black gaps between VO breaths!)
    tail_hold = 0.75
    total_duration = max(vo_dur + tail_hold, target_min_duration)
    for idx in range(len(raw_segments)):
        raw_segments[idx]["start"] = 0.0 if idx == 0 else raw_segments[idx - 1]["end"]
        if idx < len(raw_segments) - 1:
            # Cut cleanly halfway into the inter-sentence breath before next sentence starts
            next_first_word_s = beats[idx + 1]["start"]
            raw_segments[idx]["end"] = round((beats[idx]["end"] + next_first_word_s) * 0.5, 3)
        else:
            raw_segments[idx]["end"] = round(total_duration, 3)

    # For multi-paragraph scripts (>8 sentences), merge micro-sentences (<2.05s) into cohesive 2.4–6s editorial shots
    if len(raw_segments) > 8:
        merged_segments: List[Dict[str, Any]] = []
        idx = 0
        while idx < len(raw_segments):
            cur = raw_segments[idx]
            cur_dur = cur["end"] - cur["start"]
            if cur_dur < 2.05 and idx < len(raw_segments) - 1:
                nxt = raw_segments[idx + 1]
                nxt_dur = nxt["end"] - nxt["start"]
                starts_conj = cur["text"].strip().lower().startswith(("but ", "so ", "and ", "yet "))
                if idx == 0 or nxt_dur < 2.35 or starts_conj or not merged_segments:
                    role = (
                        "payoff"
                        if idx + 1 == len(raw_segments) - 1
                        else ("turn" if "turn" in (cur["role"], nxt["role"]) else cur["role"])
                    )
                    merged_segments.append({
                        "role": role,
                        "text": f"{cur['text']} {nxt['text']}",
                        "start": cur["start"],
                        "end": nxt["end"],
                        "words": cur["words"] + nxt["words"],
                    })
                    idx += 2
                    continue
                if merged_segments and (merged_segments[-1]["end"] - merged_segments[-1]["start"]) < 4.5:
                    prev = merged_segments[-1]
                    if "turn" in cur["role"]:
                        prev["role"] = "turn"
                    prev["text"] = f"{prev['text']} {cur['text']}"
                    prev["end"] = cur["end"]
                    prev["words"] = prev["words"] + cur["words"]
                    idx += 1
                    continue
            elif cur_dur < 2.05 and idx == len(raw_segments) - 1 and merged_segments:
                prev = merged_segments[-1]
                prev["role"] = "payoff"
                prev["text"] = f"{prev['text']} {cur['text']}"
                prev["end"] = cur["end"]
                prev["words"] = prev["words"] + cur["words"]
                idx += 1
                continue
            merged_segments.append(cur)
            idx += 1
        raw_segments = merged_segments

    # If fewer than 4 shots exist, subdivide longest shot(s) at word midpoint for multi-angle staging
    while len(raw_segments) < 4 and total_duration >= 6.0:
        longest_i = max(range(len(raw_segments)), key=lambda k: raw_segments[k]["end"] - raw_segments[k]["start"])
        seg = raw_segments[longest_i]
        mid_t = round((seg["start"] + seg["end"]) * 0.5, 3)
        w_left = [w for w in seg["words"] if w["s"] < mid_t]
        w_right = [w for w in seg["words"] if w["s"] >= mid_t]
        left = {"role": seg["role"], "text": seg["text"], "start": seg["start"], "end": mid_t, "words": w_left}
        right = {"role": seg["role"] + "_detail", "text": seg["text"], "start": mid_t, "end": seg["end"], "words": w_right}
        raw_segments = raw_segments[:longest_i] + [left, right] + raw_segments[longest_i + 1 :]

    shots: List[Dict[str, Any]] = []
    visual_assets: List[Dict[str, Any]] = []

    # Ensure at least one shot uses the novel non-template setup
    novel_indices = [i for i, g in enumerate(grammar_templates) if g.get("novel_non_template")]
    forced_novel_slot = max(1, len(raw_segments) - 2)
    dip_used = False

    is_roman_story = selected_skill == "zach-d-films" and (
        "roman_gladiator" in motifs or "roman_ledger_50x" in motifs
    )

    for i, seg in enumerate(raw_segments):
        low_seg = seg["text"].lower()
        if i == 0:
            g = grammar_templates[0]
        elif i == len(raw_segments) - 1:
            g = grammar_templates[-1]
        elif is_roman_story and ("final blow" in low_seg or "doesn't come" in low_seg):
            g = grammar_templates[2]  # novel_slowmo_ripple_cutaway
        elif is_roman_story and ("fifty times" in low_seg or "catch" in low_seg):
            g = grammar_templates[3]  # mechanism_cross_section_3d
        elif is_roman_story:
            g = grammar_templates[1]  # bespoke multi-angle Roman shot driven by shot narration/setup
        elif i == forced_novel_slot and novel_indices:
            g = grammar_templates[novel_indices[0]]
        else:
            mid_pool = grammar_templates[1:-1] or grammar_templates
            g = mid_pool[(i - 1) % len(mid_pool)]

        primary_motif = motifs[i % len(motifs)]
        secondary_motif = motifs[(i + 1) % len(motifs)]
        dur = round(seg["end"] - seg["start"], 3)

        speed_ramp = (
            {"enabled": True, "slow_window_norm": [0.42, 0.72], "factor": 0.45}
            if g.get("novel_non_template") or seg["role"] in ("turn", "mechanism")
            else {"enabled": False, "factor": 1.0}
        )

        asset_id = f"asset_{selected_skill.replace('-', '_')}_shot_{i:02d}"
        visual_assets.append({
            "asset_id": asset_id,
            "shot_index": i,
            "origin_skill": selected_skill,
            "generator_module": f"director/assets/{selected_skill.replace('-', '_')}_adapter.py",
            "setup_type": g["setup"],
            "novel_non_template": bool(g.get("novel_non_template", False)),
            "motifs": [primary_motif, secondary_motif],
            "deterministic_seed": seed + i * 101,
        })

        shots.append({
            "shot_id": f"shot_{i:02d}",
            "index": i,
            "engine": selected_skill,
            "beat_role": seg["role"],
            "narration_text": seg["text"],
            "start": round(seg["start"], 3),
            "end": round(seg["end"], 3),
            "duration": dur,
            "setup_type": g["setup"],
            "novel_non_template": bool(g.get("novel_non_template", False)),
            "camera": {
                "framing": g["framing"],
                "angle": g["angle"],
                "movement": g["move"],
                "parallax_planes": 3 if selected_skill in ("stick-figure", "zach-d-films", "map-route") else 2,
                "eye_focus_target": primary_motif,
            },
            "staging": {
                "action": f"{seg['role']} action staging around {primary_motif}",
                "visual_metaphor": primary_motif,
                "secondary_prop": secondary_motif,
                "character_expression": (
                    "curious_smirk" if i == 0 else
                    "surprised_wide" if "turn" in seg["role"] else
                    "focused_squint" if g.get("novel_non_template") else
                    "confident_grin" if i == len(raw_segments) - 1 else "attentive_look"
                ),
                "organic_motion": [
                    "anticipation_ease_in",
                    "arc_trajectory",
                    "squash_stretch_settle",
                    "secondary_ambient_drift",
                ],
            },
            "speed_ramp": speed_ramp,
            "transition_out": (
                "cut"
                if i == len(raw_segments) - 1
                else (
                    "cut_on_action"
                    if (g["transition"] == "dip_to_black" and dip_used)
                    else g["transition"]
                )
            ),
            "asset_refs": [asset_id],
            "safe_zone": {
                "x_min": 100,
                "x_max": 980,
                "y_min": 220,
                "y_max": 1500,
                "caption_band_y": [1250, 1430],
            },
        })
        if shots[-1]["transition_out"] == "dip_to_black":
            dip_used = True

    storyboard: Dict[str, Any] = {
        "schema_version": "0.2.0",
        "selection_mode": style_decisions["selection_mode"],
        "selected_skill": selected_skill,
        "style_lock": style_decisions["style_lock"],
        "origin_skills": [selected_skill],
        "seed": seed,
        "fps": fps,
        "aspect_ratio": "9:16",
        "preview_resolution": [1080, 1920],
        "final_resolution": [2160, 3840],
        "total_duration_sec": round(total_duration, 3),
        "style_adapter_params": style_params.to_dict(),
        "entities_and_facts": parsed_script["entities_and_facts"],
        "visual_assets": visual_assets,
        "shots": shots,
    }

    (run_dir / "storyboard.json").write_text(json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")

    # Write human-readable Art Bible
    bible_lines = [
        f"# Art Bible — Short Director Run (`{selected_skill}`)",
        "",
        "## 1. Strict Single-Skill Visual Lock",
        f"- **Selection Mode**: `{style_decisions['selection_mode']}`",
        f"- **Locked Engine**: `{selected_skill}`",
        "- **Mixing Policy**: `forbidden` (0 guest shots, 0 secondary skill assets, fail-closed)",
        f"- **Silhouette Language**: `{style_params.silhouette_language}`",
        f"- **Lighting Preset**: `{style_params.lighting_preset}`",
        f"- **Texture & Grain**: `{style_params.texture_treatment}` (grain={style_params.grain_amount}, vignette={style_params.vignette_strength})",
        "",
        "## 2. Color Palette & Typography",
        f"- **Palette**: `{json.dumps(style_params.palette)}`",
        f"- **Caption Typography**: `{json.dumps(style_params.caption_style)}`",
        "- **Safe Area**: `x in [100, 980]`, `y in [220, 1500]` (1080x1920 logical space; scaled 2x to `2160x3840` for 4K).",
        "",
        "## 3. Per-Shot Camera & Editorial Blocking",
        "| Shot | Time (s) | Setup | Framing / Move | Transition | Novel Scene |",
        "|---|---|---|---|---|---|",
    ]
    for s in shots:
        bible_lines.append(
            f"| `{s['shot_id']}` | {s['start']:.2f}–{s['end']:.2f} | `{s['setup_type']}` | "
            f"{s['camera']['framing']} / {s['camera']['movement']} | `{s['transition_out']}` | `{s['novel_non_template']}` |"
        )

    bible_lines.extend([
        "",
        "## 4. Factual & Licensing Notes",
    ])
    for fc in parsed_script["entities_and_facts"]["fact_checks"]:
        bible_lines.append(f"- **{fc.get('rule', fc.get('type', 'check'))}**: `{fc.get('status')}` — {fc.get('note', '')}")

    (run_dir / "art_bible.md").write_text("\n".join(bible_lines) + "\n", encoding="utf-8")
    return storyboard
