"""Multi-Theme Semantic Editorial Design System (`SD-RETENTION-03` Workstream 1).

Maps narrative intent + verified factual context to disciplined editorial roles
(`EditorialRole`), role-specific typography/layout/pointer/SFX specs (`OverlayStyleSpec`),
responsive text-fit estimation (320/360/390/1080), fail-closed semantic validation,
and versioned design token / role plan emission.

Never mutates colors at random across shots; every visual treatment carries explicit
informational hierarchy and semantic justification (`why_role`, `style_id`, `source_fact_ids`).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = "sd-editorial-design-tokens-1"
SAFE_BOX = (100.0, 175.0, 980.0, 1345.0)


class EditorialThemeSemanticError(ValueError):
    """Fail closed when editorial theme violates role hierarchy, contrast, or factual integrity."""


class EditorialRole(str, Enum):
    LOCATION_TIME = "location_time"
    CURIOSITY_HEADLINE = "curiosity_headline"
    WARNING_DANGER = "warning_danger"
    VERIFIED_FACT = "verified_fact"
    EXPLANATION = "explanation"
    AFTERMATH_SOBER = "aftermath_sober"
    TRANSITION_EMPHASIS = "transition_emphasis"
    NONE = "none"


@dataclass(frozen=True)
class OverlayStyleSpec:
    role: str
    style_id: str
    variant_id: str
    font_family: str
    font_size_1080: int
    font_weight: int
    line_height: float
    max_lines: int
    max_words: int
    stroke_width: int
    shadow: str
    fill_rule: str
    bg_shape: str
    accent_rule: str
    primary_color: str
    secondary_color: str
    outline_color: str
    bg_fill: str
    entry_easing: str
    anim_budget_frames: int
    pointer_shape: str
    sfx_intent: str
    min_duration: float
    max_duration: float
    safe_region: Tuple[int, int, int, int]
    contrast_ratio_min: float
    semantic_priority: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Canonical role-aware style registry (2-3 meaningful variants per core role;
# never the same dark-gold box across every role).
ROLE_STYLE_VARIANTS: Dict[str, Tuple[OverlayStyleSpec, ...]] = {
    EditorialRole.LOCATION_TIME.value: (
        OverlayStyleSpec(
            role="location_time",
            style_id="loc_minimal_chip_v1",
            variant_id="loc_v1_clean_slate",
            font_family="'Cap', sans-serif",
            font_size_1080=34,
            font_weight=700,
            line_height=1.18,
            max_lines=2,
            max_words=6,
            stroke_width=0,
            shadow="0 2px 10px rgba(0,0,0,0.45)",
            fill_rule="solid_offwhite",
            bg_shape="capsule",
            accent_rule="left_hairline_neutral",
            primary_color="#f1f5f9",
            secondary_color="#cbd5e1",
            outline_color="#0f172a",
            bg_fill="rgba(15, 23, 42, 0.58)",
            entry_easing="cubic_fade_slide",
            anim_budget_frames=8,
            pointer_shape="none",
            sfx_intent="silent_context",
            min_duration=1.6,
            max_duration=3.2,
            safe_region=(96, 170, 984, 340),
            contrast_ratio_min=4.5,
            semantic_priority=3,
        ),
        OverlayStyleSpec(
            role="location_time",
            style_id="loc_stamp_strip_v2",
            variant_id="loc_v2_date_band",
            font_family="'Cap', sans-serif",
            font_size_1080=32,
            font_weight=700,
            line_height=1.18,
            max_lines=2,
            max_words=6,
            stroke_width=2,
            shadow="0 2px 8px rgba(0,0,0,0.65)",
            fill_rule="solid_offwhite",
            bg_shape="marker_chip",
            accent_rule="underline_muted_slate",
            primary_color="#e2e8f0",
            secondary_color="#94a3b8",
            outline_color="#090d16",
            bg_fill="rgba(12, 18, 28, 0.42)",
            entry_easing="cubic_fade_slide",
            anim_budget_frames=7,
            pointer_shape="none",
            sfx_intent="silent_context",
            min_duration=1.5,
            max_duration=3.0,
            safe_region=(96, 170, 984, 340),
            contrast_ratio_min=4.5,
            semantic_priority=3,
        ),
    ),
    EditorialRole.CURIOSITY_HEADLINE.value: (
        OverlayStyleSpec(
            role="curiosity_headline",
            style_id="hero_two_tone_gold_red_v1",
            variant_id="hero_v1_gold_red_display",
            font_family="'Cap', sans-serif",
            font_size_1080=92,
            font_weight=900,
            line_height=1.04,
            max_lines=2,
            max_words=6,
            stroke_width=11,
            shadow="0 10px 26px rgba(0,0,0,0.88)",
            fill_rule="two_tone_line_split",
            bg_shape="transparent",
            accent_rule="second_line_danger_red",
            primary_color="#facc15",
            secondary_color="#ef4444",
            outline_color="#060911",
            bg_fill="transparent",
            entry_easing="overshoot_pop_5f",
            anim_budget_frames=6,
            pointer_shape="impact_arrow",
            sfx_intent="headline_hit_warm",
            min_duration=1.35,
            max_duration=2.45,
            safe_region=(88, 178, 992, 620),
            contrast_ratio_min=6.5,
            semantic_priority=1,
        ),
        OverlayStyleSpec(
            role="curiosity_headline",
            style_id="hero_two_tone_white_gold_v2",
            variant_id="hero_v2_white_amber_display",
            font_family="'Cap', sans-serif",
            font_size_1080=86,
            font_weight=900,
            line_height=1.05,
            max_lines=2,
            max_words=6,
            stroke_width=10,
            shadow="0 9px 24px rgba(0,0,0,0.86)",
            fill_rule="two_tone_line_split",
            bg_shape="transparent",
            accent_rule="second_line_amber_pop",
            primary_color="#ffffff",
            secondary_color="#facc15",
            outline_color="#060911",
            bg_fill="transparent",
            entry_easing="overshoot_pop_5f",
            anim_budget_frames=6,
            pointer_shape="impact_arrow",
            sfx_intent="headline_hit_warm",
            min_duration=1.35,
            max_duration=2.45,
            safe_region=(88, 178, 992, 620),
            contrast_ratio_min=6.5,
            semantic_priority=1,
        ),
    ),
    EditorialRole.WARNING_DANGER.value: (
        OverlayStyleSpec(
            role="warning_danger",
            style_id="warn_arrow_badge_v1",
            variant_id="warn_v1_coral_impact",
            font_family="'Cap', sans-serif",
            font_size_1080=52,
            font_weight=800,
            line_height=1.10,
            max_lines=2,
            max_words=5,
            stroke_width=6,
            shadow="0 6px 18px rgba(0,0,0,0.82)",
            fill_rule="alert_coral_white",
            bg_shape="marker_chip",
            accent_rule="red_impact_ring_arrow",
            primary_color="#fef2f2",
            secondary_color="#f87171",
            outline_color="#140404",
            bg_fill="rgba(69, 10, 10, 0.72)",
            entry_easing="draw_snap_6f",
            anim_budget_frames=8,
            pointer_shape="impact_arrow",
            sfx_intent="warning_tension_pulse",
            min_duration=1.25,
            max_duration=2.60,
            safe_region=(96, 200, 984, 720),
            contrast_ratio_min=5.5,
            semantic_priority=1,
        ),
        OverlayStyleSpec(
            role="warning_danger",
            style_id="warn_ring_pointer_v2",
            variant_id="warn_v2_amber_alert_tag",
            font_family="'Cap', sans-serif",
            font_size_1080=50,
            font_weight=800,
            line_height=1.12,
            max_lines=2,
            max_words=5,
            stroke_width=6,
            shadow="0 6px 18px rgba(0,0,0,0.80)",
            fill_rule="alert_amber_orange",
            bg_shape="transparent",
            accent_rule="double_pulse_focus_ring",
            primary_color="#fb923c",
            secondary_color="#fef3c7",
            outline_color="#090d16",
            bg_fill="transparent",
            entry_easing="draw_snap_6f",
            anim_budget_frames=8,
            pointer_shape="focus_circle",
            sfx_intent="warning_tension_pulse",
            min_duration=1.25,
            max_duration=2.60,
            safe_region=(96, 200, 984, 720),
            contrast_ratio_min=5.5,
            semantic_priority=2,
        ),
    ),
    EditorialRole.VERIFIED_FACT.value: (
        OverlayStyleSpec(
            role="verified_fact",
            style_id="fact_clean_stat_card_v1",
            variant_id="fact_v1_crisp_slate",
            font_family="'Cap', sans-serif",
            font_size_1080=50,
            font_weight=800,
            line_height=1.14,
            max_lines=2,
            max_words=6,
            stroke_width=0,
            shadow="0 6px 18px rgba(0,0,0,0.42)",
            fill_rule="high_contrast_card",
            bg_shape="clean_stat_card",
            accent_rule="top_sky_rule",
            primary_color="#0f172a",
            secondary_color="#0369a1",
            outline_color="#ffffff",
            bg_fill="rgba(248, 250, 252, 0.94)",
            entry_easing="smooth_settle_6f",
            anim_budget_frames=6,
            pointer_shape="curved_leader",
            sfx_intent="fact_soft_tick",
            min_duration=1.6,
            max_duration=2.8,
            safe_region=(96, 210, 984, 720),
            contrast_ratio_min=7.0,
            semantic_priority=2,
        ),
        OverlayStyleSpec(
            role="verified_fact",
            style_id="fact_navy_numeral_v2",
            variant_id="fact_v2_navy_crisp",
            font_family="'Cap', sans-serif",
            font_size_1080=52,
            font_weight=800,
            line_height=1.12,
            max_lines=2,
            max_words=6,
            stroke_width=0,
            shadow="0 8px 20px rgba(0,0,0,0.52)",
            fill_rule="high_contrast_numeral",
            bg_shape="clean_stat_card",
            accent_rule="left_cyan_bar",
            primary_color="#f8fafc",
            secondary_color="#7dd3fc",
            outline_color="#0f172a",
            bg_fill="rgba(15, 23, 42, 0.90)",
            entry_easing="smooth_settle_6f",
            anim_budget_frames=6,
            pointer_shape="mini_fact_tag",
            sfx_intent="fact_soft_tick",
            min_duration=1.6,
            max_duration=2.8,
            safe_region=(96, 210, 984, 720),
            contrast_ratio_min=7.0,
            semantic_priority=2,
        ),
    ),
    EditorialRole.EXPLANATION.value: (
        OverlayStyleSpec(
            role="explanation",
            style_id="exp_curved_leader_v1",
            variant_id="exp_v1_sky_leader",
            font_family="'Cap', sans-serif",
            font_size_1080=46,
            font_weight=700,
            line_height=1.15,
            max_lines=2,
            max_words=6,
            stroke_width=5,
            shadow="0 4px 14px rgba(0,0,0,0.72)",
            fill_rule="light_line_label",
            bg_shape="transparent",
            accent_rule="curved_sky_leader",
            primary_color="#f8fafc",
            secondary_color="#38bdf8",
            outline_color="#090d16",
            bg_fill="transparent",
            entry_easing="leader_draw_8f",
            anim_budget_frames=8,
            pointer_shape="curved_leader",
            sfx_intent="pointer_draw_swish",
            min_duration=1.4,
            max_duration=2.6,
            safe_region=(96, 190, 984, 740),
            contrast_ratio_min=5.0,
            semantic_priority=2,
        ),
        OverlayStyleSpec(
            role="explanation",
            style_id="exp_focus_ring_v2",
            variant_id="exp_v2_mint_circle",
            font_family="'Cap', sans-serif",
            font_size_1080=44,
            font_weight=700,
            line_height=1.15,
            max_lines=2,
            max_words=6,
            stroke_width=4,
            shadow="0 4px 12px rgba(0,0,0,0.68)",
            fill_rule="light_ring_callout",
            bg_shape="capsule",
            accent_rule="dashed_mint_ring",
            primary_color="#f1f5f9",
            secondary_color="#34d399",
            outline_color="#090d16",
            bg_fill="rgba(9, 13, 22, 0.56)",
            entry_easing="leader_draw_8f",
            anim_budget_frames=8,
            pointer_shape="focus_circle",
            sfx_intent="pointer_draw_swish",
            min_duration=1.4,
            max_duration=2.6,
            safe_region=(96, 190, 984, 740),
            contrast_ratio_min=5.0,
            semantic_priority=2,
        ),
    ),
    EditorialRole.AFTERMATH_SOBER.value: (
        OverlayStyleSpec(
            role="aftermath_sober",
            style_id="aft_quiet_strip_v1",
            variant_id="aft_v1_sober_dissolve",
            font_family="'Cap', sans-serif",
            font_size_1080=40,
            font_weight=700,
            line_height=1.20,
            max_lines=2,
            max_words=7,
            stroke_width=3,
            shadow="0 3px 12px rgba(0,0,0,0.65)",
            fill_rule="desaturated_slate",
            bg_shape="quiet_strip",
            accent_rule="muted_silver_hairline",
            primary_color="#e2e8f0",
            secondary_color="#94a3b8",
            outline_color="#090d16",
            bg_fill="rgba(15, 23, 42, 0.52)",
            entry_easing="slow_dissolve_12f",
            anim_budget_frames=12,
            pointer_shape="none",
            sfx_intent="silent_sober",
            min_duration=2.0,
            max_duration=3.4,
            safe_region=(96, 200, 984, 460),
            contrast_ratio_min=4.5,
            semantic_priority=3,
        ),
        OverlayStyleSpec(
            role="aftermath_sober",
            style_id="aft_editorial_note_v2",
            variant_id="aft_v2_editorial_caption",
            font_family="'Cap', sans-serif",
            font_size_1080=42,
            font_weight=700,
            line_height=1.18,
            max_lines=2,
            max_words=7,
            stroke_width=4,
            shadow="0 3px 12px rgba(0,0,0,0.65)",
            fill_rule="desaturated_warm_gray",
            bg_shape="transparent",
            accent_rule="none",
            primary_color="#cbd5e1",
            secondary_color="#94a3b8",
            outline_color="#090d16",
            bg_fill="transparent",
            entry_easing="slow_dissolve_12f",
            anim_budget_frames=12,
            pointer_shape="none",
            sfx_intent="silent_sober",
            min_duration=2.0,
            max_duration=3.4,
            safe_region=(96, 200, 984, 460),
            contrast_ratio_min=4.5,
            semantic_priority=3,
        ),
    ),
    EditorialRole.TRANSITION_EMPHASIS.value: (
        OverlayStyleSpec(
            role="transition_emphasis",
            style_id="tr_underline_glow_v1",
            variant_id="tr_v1_marker_underline",
            font_family="'Cap', sans-serif",
            font_size_1080=44,
            font_weight=800,
            line_height=1.15,
            max_lines=1,
            max_words=4,
            stroke_width=4,
            shadow="0 4px 14px rgba(0,0,0,0.75)",
            fill_rule="underline_glow",
            bg_shape="transparent",
            accent_rule="underline_amber_draw",
            primary_color="#fde68a",
            secondary_color="#f59e0b",
            outline_color="#090d16",
            bg_fill="transparent",
            entry_easing="smooth_settle_6f",
            anim_budget_frames=6,
            pointer_shape="underline_emphasis",
            sfx_intent="transition_whoosh_soft",
            min_duration=1.1,
            max_duration=2.0,
            safe_region=(100, 220, 980, 620),
            contrast_ratio_min=4.8,
            semantic_priority=3,
        ),
        OverlayStyleSpec(
            role="transition_emphasis",
            style_id="tr_minimal_tag_v2",
            variant_id="tr_v2_quiet_bridge_tag",
            font_family="'Cap', sans-serif",
            font_size_1080=42,
            font_weight=700,
            line_height=1.15,
            max_lines=1,
            max_words=4,
            stroke_width=4,
            shadow="0 4px 12px rgba(0,0,0,0.70)",
            fill_rule="marker_pill",
            bg_shape="capsule",
            accent_rule="top_amber_dot",
            primary_color="#f8fafc",
            secondary_color="#fbbf24",
            outline_color="#090d16",
            bg_fill="rgba(15, 23, 42, 0.60)",
            entry_easing="smooth_settle_6f",
            anim_budget_frames=6,
            pointer_shape="underline_emphasis",
            sfx_intent="transition_whoosh_soft",
            min_duration=1.1,
            max_duration=2.0,
            safe_region=(100, 220, 980, 620),
            contrast_ratio_min=4.8,
            semantic_priority=3,
        ),
    ),
}


def derive_editorial_role(
    beat: Dict[str, Any],
    action_graph: Optional[Dict[str, Any]] = None,
    spoken_words: Optional[List[Dict[str, Any]]] = None,
    facts: Optional[Dict[str, Any]] = None,
    historical_tone: str = "serious",
) -> Tuple[EditorialRole, str]:
    """Deterministically infer informational role from narrative action and verified facts."""
    intent = str(beat.get("editorial_intent") or "").lower()
    act = str(beat.get("physical_action") or "").lower()
    role_tag = str(beat.get("beat_role") or "").lower()
    cand_type = str(beat.get("candidate_type") or "").lower()
    cand_lbl = str(beat.get("candidate_label") or "").lower()
    cand_sub = str(beat.get("candidate_sublabel") or "").lower()
    text = str(beat.get("narration_text") or "").lower()
    cand_text = f"{cand_lbl} {cand_sub}".strip() or text

    if intent == "curiosity_hook" or (role_tag == "hook" and not intent):
        return EditorialRole.CURIOSITY_HEADLINE, "Opening curiosity hook guides eye to initial anomaly"
    if intent in ("twist_escalation", "structural_collapse") or any(
        k in f"{act} {cand_text}" for k in ("rupture", "twist", "collapse", "torsion", "fail-safe", "failsafe", "gave way")
    ) or any(k in text for k in ("gave way", "violent twist", "started twisting")):
        if any(k in f"{act} {cand_text} {text}" for k in ("twist", "torsion", "rupture", "gave way", "fail-safe")):
            return EditorialRole.WARNING_DANGER, "Active structural failure or torsion escalation point"
    if intent == "context_establish" or (
        ("location" in act or "establish" in act or "wide" in act or "street" in act)
        and role_tag in ("common_belief", "setup", "context")
        and any(k in cand_text for k in ("boston", "north end", "tacoma", "puget", "1919", "1940", "washington", "narrows"))
    ):
        return EditorialRole.LOCATION_TIME, "New historical setting/location establishment"
    if intent == "aftermath_takeaway" or any(
        k in act for k in ("aftermath", "rescue", "overview", "payoff")
    ) or role_tag == "payoff" or any(k in cand_text for k in ("died", "injured", "killed", "code overhaul", "aftermath")):
        return EditorialRole.AFTERMATH_SOBER, "Sober aftermath / human cost / engineering lesson payoff"
    if (cand_type == "verified_counter" or beat.get("factual_claim_id") or (
        re.search(r"\b\d+(?:\.\d+)?\b", cand_text)
        and any(k in cand_text for k in ("million", "mph", "november", "feet", "ft", "1940", "1919", "gallons", "panes", "est"))
    )):
        if any(k in f"{cand_text} {text}" for k in ("died", "injured", "killed")) and historical_tone == "serious":
            return EditorialRole.AFTERMATH_SOBER, "Sensitive factual casualty summary uses sober treatment"
        return EditorialRole.VERIFIED_FACT, "Verified numerical/date fact backed by source manifest"
    return EditorialRole.EXPLANATION, "Spatial/mechanical explanation anchored to 3D physical feature"


def select_overlay_variant(
    role: EditorialRole,
    contrast_needs: str = "high",
    shot_occupancy: Optional[Dict[str, Any]] = None,
    prior_roles: Optional[List[Dict[str, Any]]] = None,
    seed: int = 42,
) -> OverlayStyleSpec:
    """Select an appropriate visual variant for `role` deterministically without random colors."""
    key = role.value if isinstance(role, EditorialRole) else str(role)
    variants = ROLE_STYLE_VARIANTS.get(key) or ROLE_STYLE_VARIANTS[EditorialRole.EXPLANATION.value]
    prior = list(prior_roles or [])
    last_vid = prior[-1].get("variant_id") if prior else None

    # Prefer a distinct treatment from the previous matching-role overlay when available
    idx = abs(int(seed) + len(prior)) % len(variants)
    chosen = variants[idx]
    if last_vid and chosen.variant_id == last_vid and len(variants) > 1:
        chosen = variants[(idx + 1) % len(variants)]
    if contrast_needs == "extreme" and key == EditorialRole.CURIOSITY_HEADLINE.value:
        chosen = variants[0]
    return chosen


def split_curiosity_lines(label: str, max_lines: int = 2) -> Tuple[str, str]:
    """Split a concise 2-5 word headline into balanced top and bottom lines."""
    clean = re.sub(r"\s+", " ", str(label or "").replace("/", " / ").strip())
    if "/" in clean:
        parts = [p.strip() for p in clean.split("/") if p.strip()]
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
    toks = [t for t in clean.split(" ") if t]
    if len(toks) <= 1 or max_lines <= 1:
        return clean, ""
    mid = max(1, len(toks) // 2)
    return " ".join(toks[:mid]), " ".join(toks[mid:])


def measure_text_layout(
    text: str,
    spec: OverlayStyleSpec,
    viewport: int = 1080,
    font_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute wrapped line metrics and responsive viewport legibility across 320/360/390/1080."""
    scale = float(viewport) / 1080.0
    is_hero = spec.role == EditorialRole.CURIOSITY_HEADLINE.value
    char_w_ratio = float((font_metrics or {}).get("char_w_ratio", 0.66 if is_hero else 0.56))
    words = [w for w in re.sub(r"\s+", " ", str(text or "")).replace("/", " ").split(" ") if w]
    sx0, sy0, sx1, sy1 = spec.safe_region
    max_w_1080 = max(240.0, (sx1 - sx0) - (100.0 if is_hero else 48.0))

    # Fit font size conservatively so longest line never overflows horizontal safe box
    font_sz = float(spec.font_size_1080)
    if spec.role == EditorialRole.CURIOSITY_HEADLINE.value:
        l1, l2 = split_curiosity_lines(text, max_lines=spec.max_lines)
        lines = [ln for ln in (l1, l2) if ln]
    else:
        lines = []
        cur = ""
        for w in words:
            cand = f"{cur} {w}".strip() if cur else w
            if len(cand) * font_sz * char_w_ratio <= max_w_1080 * 0.72 or not cur:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        lines = lines[: max(1, spec.max_lines)]

    longest_chars = max((len(ln) for ln in lines), default=1)
    est_line_w_1080 = longest_chars * font_sz * char_w_ratio + spec.stroke_width * 2.0
    if est_line_w_1080 > max_w_1080:
        shrink = max_w_1080 / max(1.0, est_line_w_1080)
        font_sz = max(26.0, round(font_sz * shrink, 1))
        est_line_w_1080 = longest_chars * font_sz * char_w_ratio + spec.stroke_width * 2.0

    box_w_1080 = min(max_w_1080, max(260.0, est_line_w_1080 + 44.0))
    box_h_1080 = max(58.0, len(lines) * font_sz * spec.line_height + (28.0 if spec.bg_shape != "transparent" else 16.0))
    px_at_viewport = round(font_sz * scale, 2)

    return {
        "viewport_width": int(viewport),
        "font_size_1080": round(font_sz, 1),
        "font_size_viewport_px": px_at_viewport,
        "lines": lines,
        "line_count": len(lines),
        "word_count": len(words),
        "est_box_1080": [round(box_w_1080, 1), round(box_h_1080, 1)],
        "fits_safe_width": est_line_w_1080 <= max_w_1080 + 1.0,
        "meets_mobile_360_min": (px_at_viewport >= 22.0) if (viewport == 360 and spec.role == EditorialRole.CURIOSITY_HEADLINE.value) else True,
    }


def validate_theme_semantics(
    overlays: List[Dict[str, Any]],
    story: Optional[Dict[str, Any]] = None,
    facts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fail closed on tiny hero headlines, repetitive boxes, danger-on-neutral location, or missing sources."""
    errors: List[str] = []
    warnings: List[str] = []

    loc_streak = 0
    box_style_streak = 0
    prev_bg_sig: Optional[Tuple[str, str]] = None

    spec_index = {
        spec.variant_id: spec
        for specs in ROLE_STYLE_VARIANTS.values()
        for spec in specs
    }

    for ov in overlays:
        role = str(ov.get("role") or "")
        vid = str(ov.get("variant_id") or "")
        spec = spec_index.get(vid)
        font_sz = float(ov.get("font_size_1080") or (spec.font_size_1080 if spec else 32))
        bg_shape = str(ov.get("bg_shape") or (spec.bg_shape if spec else "capsule"))
        accent_color = str(ov.get("accent_color") or (spec.secondary_color if spec else ""))
        label = str(ov.get("label") or "")
        low = label.lower()

        if role == EditorialRole.CURIOSITY_HEADLINE.value:
            if font_sz < 64.0:
                errors.append(
                    f"N01: Curiosity headline '{label}' uses small metadata font size ({font_sz}px < 64px)"
                )
            if any(k in low for k in ("died", "killed", "death toll", "fatalities")):
                errors.append(
                    f"Curiosity giant red display must not sensationalize casualties ('{label}')"
                )

        if role == EditorialRole.WARNING_DANGER.value:
            if any(k in low for k in ("washington, 1940", "boston, 1919", "north end, boston")) and "twist" not in low and "leak" not in low:
                errors.append(f"N03: Danger styling applied to neutral location label '{label}'")

        if role == EditorialRole.LOCATION_TIME.value:
            loc_streak += 1
            if loc_streak >= 4:
                errors.append("N02: >=4 consecutive shots carry redundant location_time cards")
        else:
            loc_streak = 0

        sig = (role, bg_shape)
        if sig == prev_bg_sig and bg_shape not in ("transparent",) and role != EditorialRole.CURIOSITY_HEADLINE.value:
            box_style_streak += 1
            if box_style_streak >= 4:
                errors.append(
                    f"N02: Identical overlay treatment {sig} repeated {box_style_streak} consecutive overlays"
                )
        else:
            box_style_streak = 1
            prev_bg_sig = sig

        # Require pointer target binding for impact/warning/explanation pointers
        if role in (EditorialRole.WARNING_DANGER.value, EditorialRole.EXPLANATION.value) and ov.get("pointer_shape") not in (None, "none"):
            anch = str(ov.get("anchor_id") or "")
            if not anch or anch in ("stage_center", "default"):
                errors.append(f"N04: Overlay {ov.get('overlay_id')} ('{label}') lacks real 3D feature anchor (got '{anch}')")

        # Require grounded fact source for numeric verified facts
        if facts is not None and role == EditorialRole.VERIFIED_FACT.value:
            nums = re.findall(r"\d+(?:\.\d+)?", label)
            if nums and not ov.get("fact_source") and not ov.get("source_fact_ids"):
                errors.append(f"N31: Numeric verified_fact '{label}' lacks source_fact_ids / fact_source")

    if errors:
        raise EditorialThemeSemanticError("; ".join(errors))

    return {
        "status": "PASS",
        "checked_overlays": len(overlays),
        "warnings": warnings,
    }


def emit_design_tokens_json(
    run_dir: Optional[Path],
    roles_plan: List[Dict[str, Any]],
    selected_skill: str,
) -> Dict[str, Any]:
    """Persist `editorial_design_tokens.json` and `editorial_roles_plan.json` for traceability."""
    tokens_doc = {
        "schema_version": SCHEMA_VERSION,
        "selected_skill": selected_skill,
        "roles": {
            role: [spec.to_dict() for spec in specs]
            for role, specs in ROLE_STYLE_VARIANTS.items()
        },
        "hierarchy_contract": {
            "curiosity_headline_min_1080_px": 64,
            "verified_fact_min_1080_px": 48,
            "explanation_range_1080_px": [42, 64],
            "location_time_range_1080_px": [30, 44],
            "max_consecutive_identical_boxes": 3,
        },
    }
    plan_doc = {
        "schema_version": "sd-editorial-roles-plan-1",
        "selected_skill": selected_skill,
        "events": roles_plan,
    }
    if run_dir is not None:
        (run_dir / "editorial_design_tokens.json").write_text(
            json.dumps(tokens_doc, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (run_dir / "editorial_roles_plan.json").write_text(
            json.dumps(plan_doc, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return {"tokens": tokens_doc, "roles_plan": plan_doc}
