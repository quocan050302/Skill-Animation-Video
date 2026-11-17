"""Verification Tests for Multi-Theme Semantic Editorial Design System (G01-G04, G19, N01-N04, N31)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from director.editorial_design_system import (
    EditorialRole,
    EditorialThemeSemanticError,
    ROLE_STYLE_VARIANTS,
    derive_editorial_role,
    emit_design_tokens_json,
    measure_text_layout,
    select_overlay_variant,
    split_curiosity_lines,
    validate_theme_semantics,
)


class TestEditorialDesignSystem(unittest.TestCase):
    def test_g01_g02_role_derivation_and_multi_variant_registry(self) -> None:
        # G01: Every core role has >=2 distinct variants with explicit semantic hierarchy
        for role in (
            EditorialRole.LOCATION_TIME,
            EditorialRole.CURIOSITY_HEADLINE,
            EditorialRole.WARNING_DANGER,
            EditorialRole.VERIFIED_FACT,
            EditorialRole.EXPLANATION,
            EditorialRole.AFTERMATH_SOBER,
            EditorialRole.TRANSITION_EMPHASIS,
        ):
            variants = ROLE_STYLE_VARIANTS[role.value]
            self.assertGreaterEqual(len(variants), 2, f"Expected >=2 variants for role {role.value}")
            self.assertEqual(len({v.variant_id for v in variants}), len(variants))

        # Verify distinct hierarchy: curiosity headline >= 86px vs quiet location_time <= 36px
        r_hook, _ = derive_editorial_role({"editorial_intent": "curiosity_hook", "beat_role": "hook", "narration_text": "Wait until you look at the bridge."})
        r_loc, _ = derive_editorial_role({"editorial_intent": "context_establish", "beat_role": "common_belief", "physical_action": "wide_establish", "narration_text": "Washington, 1940"})
        r_warn, _ = derive_editorial_role({"editorial_intent": "twist_escalation", "physical_action": "bridge_torsion_flutter", "narration_text": "Then it started twisting"})
        r_fact, _ = derive_editorial_role({"factual_claim_id": "main_span_2800ft", "candidate_type": "verified_counter", "candidate_label": "2,800 FT SPAN", "narration_text": "2,800 ft steel deck"})
        r_aft, _ = derive_editorial_role({"editorial_intent": "aftermath_takeaway", "beat_role": "payoff", "narration_text": "Twenty-one died in the surge."})

        self.assertEqual(r_hook, EditorialRole.CURIOSITY_HEADLINE)
        self.assertEqual(r_loc, EditorialRole.LOCATION_TIME)
        self.assertEqual(r_warn, EditorialRole.WARNING_DANGER)
        self.assertEqual(r_fact, EditorialRole.VERIFIED_FACT)
        self.assertEqual(r_aft, EditorialRole.AFTERMATH_SOBER)

        s_hook = select_overlay_variant(r_hook, contrast_needs="extreme", seed=42)
        s_loc = select_overlay_variant(r_loc, seed=42)
        self.assertGreaterEqual(s_hook.font_size_1080, 80)
        self.assertLessEqual(s_loc.font_size_1080, 36)
        self.assertEqual(s_loc.sfx_intent, "silent_context")
        self.assertEqual(s_hook.sfx_intent, "headline_hit_warm")

    def test_g03_g04_mobile_viewport_layout_and_tokens_emission(self) -> None:
        l1, l2 = split_curiosity_lines("THE ROAD / WAS MOVING!")
        self.assertEqual((l1, l2), ("THE ROAD", "WAS MOVING!"))

        spec = select_overlay_variant(EditorialRole.CURIOSITY_HEADLINE, contrast_needs="extreme", seed=42)
        for vw in (320, 360, 390, 1080):
            lay = measure_text_layout("THE ROAD / WAS MOVING!", spec, viewport=vw)
            self.assertTrue(lay["fits_safe_width"], f"Hero headline overflowed safe width at {vw}px: {lay}")
            if vw == 360:
                self.assertTrue(lay["meets_mobile_360_min"])

        with tempfile.TemporaryDirectory() as td:
            res = emit_design_tokens_json(
                Path(td),
                roles_plan=[{
                    "overlay_id": "ov_00",
                    "role": "curiosity_headline",
                    "variant_id": spec.variant_id,
                    "style_id": spec.style_id,
                    "why_role": "Opening hook",
                }],
                selected_skill="zach-d-films",
            )
            self.assertTrue((Path(td) / "editorial_design_tokens.json").exists())
            self.assertTrue((Path(td) / "editorial_roles_plan.json").exists())
            self.assertEqual(res["roles_plan"]["events"][0]["role"], "curiosity_headline")

    def test_g19_generalizes_beyond_tacoma_and_boston(self) -> None:
        # Fresh science topic with neither Tacoma nor Boston keywords
        r_a, _ = derive_editorial_role({"editorial_intent": "curiosity_hook", "narration_text": "Why does lightning strike inside a volcanic ash plume?"})
        r_b, _ = derive_editorial_role({"physical_action": "charge_separation", "narration_text": "Colliding tephra grains strip electrons apart."})
        r_c, _ = derive_editorial_role({"candidate_type": "verified_counter", "candidate_label": "30,000 C SPARK", "narration_text": "30,000 volts across turbulent ash."})
        self.assertEqual({r_a, r_b, r_c}, {EditorialRole.CURIOSITY_HEADLINE, EditorialRole.EXPLANATION, EditorialRole.VERIFIED_FACT})

    def test_negative_traps_n01_n02_n03_n04_n31(self) -> None:
        # N01: Curiosity headline in small metadata font size (<64px) rejected
        with self.assertRaises(EditorialThemeSemanticError):
            validate_theme_semantics([{
                "overlay_id": "ov_0",
                "role": "curiosity_headline",
                "variant_id": "hero_v1_gold_red_display",
                "font_size_1080": 32,
                "label": "LOOK AT THIS!",
                "anchor_id": "bridge_midspan_twist",
            }])

        # N02: Repeated identical location_time cards >= 4 consecutive rejected
        with self.assertRaises(EditorialThemeSemanticError):
            validate_theme_semantics([
                {"overlay_id": f"ov_{i}", "role": "location_time", "bg_shape": "capsule", "label": f"LOC {i}"}
                for i in range(4)
            ])

        # N03: Danger styling applied to neutral location context rejected
        with self.assertRaises(EditorialThemeSemanticError):
            validate_theme_semantics([{
                "overlay_id": "ov_bad_warn",
                "role": "warning_danger",
                "variant_id": "warn_v1_coral_impact",
                "label": "WASHINGTON, 1940",
                "anchor_id": "bridge_midspan_twist",
                "pointer_shape": "impact_arrow",
            }])

        # N04: Warning pointer without real physical anchor (stage_center / default) rejected
        with self.assertRaises(EditorialThemeSemanticError):
            validate_theme_semantics([{
                "overlay_id": "ov_bad_anch",
                "role": "warning_danger",
                "variant_id": "warn_v1_coral_impact",
                "label": "GIRDER BUFFETING",
                "pointer_shape": "impact_arrow",
                "anchor_id": "stage_center",
            }])

        # N31: Verified numeric fact without source_fact_ids/fact_source rejected when facts passed
        with self.assertRaises(EditorialThemeSemanticError):
            validate_theme_semantics(
                [{
                    "overlay_id": "ov_bad_fact",
                    "role": "verified_fact",
                    "variant_id": "fact_v1_crisp_slate",
                    "label": "42 MPH WIND",
                    "pointer_shape": "none",
                }],
                facts={"claims": []},
            )


if __name__ == "__main__":
    unittest.main()
