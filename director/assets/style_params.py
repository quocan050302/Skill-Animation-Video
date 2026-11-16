"""Parameterized style adapter configuration for each of the six engines.

Each skill has its own native visual parameters (line weight, curve tension,
silhouette language, lighting, texture/grain treatment, caption style, color grade)
without ever crossing visual systems.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass
class StyleAdapterParams:
    engine: str
    line_weight: float
    curve_tension: float
    silhouette_language: str
    lighting_preset: str
    texture_treatment: str
    grain_amount: float
    vignette_strength: float
    caption_style: Dict[str, Any]
    color_grading: Dict[str, Any]
    palette: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_style_params(selected_skill: str, mood: str = "vibrant", seed: int = 42) -> StyleAdapterParams:
    """Create rich, engine-authentic visual style parameters for the single locked skill."""
    if selected_skill == "stick-figure":
        palettes = {
            "vibrant": {
                "sky_top": "#2f95e8",
                "sky_bot": "#d4f0fc",
                "ground": "#e6b87d",
                "accent_primary": "#e63946",
                "accent_secondary": "#ffb703",
                "accent_cool": "#2a9d8f",
                "ink": "#201a23",
                "paper": "#f7f3eb",
            },
            "scientific": {
                "sky_top": "#1d3557",
                "sky_bot": "#a8dadc",
                "ground": "#dbe7ee",
                "accent_primary": "#e76f51",
                "accent_secondary": "#f4a261",
                "accent_cool": "#457b9d",
                "ink": "#1a1821",
                "paper": "#f5f7fa",
            },
        }
        pal = palettes.get(mood, palettes["vibrant"])
        return StyleAdapterParams(
            engine="stick-figure",
            line_weight=0.018,
            curve_tension=0.55,
            silhouette_language="oversized_expressive_head_bean_torso_ik_limbs",
            lighting_preset="cel_rim_plus_radial_glow",
            texture_treatment="procedural_paper_grain_and_cel_halves",
            grain_amount=0.065,
            vignette_strength=0.28,
            caption_style={
                "font_family": "Poppins",
                "font_weight": 700,
                "size_px": 70,
                "case": "lowercase_clean",
                "max_words": 2,
                "y_anchor": 1345,
                "outline_px": 13,
                "pop_overshoot": 1.18,
            },
            color_grading={"contrast": 1.04, "saturation": 1.08, "warmth": 0.02},
            palette=pal,
        )

    if selected_skill == "zach-d-films":
        return StyleAdapterParams(
            engine="zach-d-films",
            line_weight=0.0,
            curve_tension=0.5,
            silhouette_language="lathe_capsule_3d_mannequin_glossy_studio",
            lighting_preset="three_point_softbox_pmrem_blue_sky",
            texture_treatment="procedural_canvas_brushed_metal_wood_skin",
            grain_amount=0.018,
            vignette_strength=0.28,
            caption_style={
                "font_family": "Montserrat",
                "font_weight": 700,
                "size_px": 68,
                "case": "sentence",
                "max_words": 3,
                "y_anchor": 1440,
                "shadow_blur": 16,
            },
            color_grading={"aces_exposure": 1.02, "bloom": 0.36, "contrast": 1.03},
            palette={
                "sky_top": "#2b78d6",
                "sky_mid": "#5b9fea",
                "sky_horizon": "#92c3f2",
                "ripple_force": "#ff2a2a",
                "accent_metal": "#c8d0da",
            },
        )

    if selected_skill == "graph":
        dark = (seed % 2 == 1 and mood == "dark")
        return StyleAdapterParams(
            engine="graph",
            line_weight=6.0,
            curve_tension=0.5,
            silhouette_language="catmull_rom_spline_tabular_counter_grid",
            lighting_preset="flat_editorial_high_contrast",
            texture_treatment="crisp_vector_hairline_grid",
            grain_amount=0.01,
            vignette_strength=0.05,
            caption_style={
                "font_family": "Inter",
                "font_weight": 600,
                "size_px": 42,
                "case": "sentence",
                "max_words": 4,
                "y_anchor": 1540,
            },
            color_grading={"contrast": 1.02, "saturation": 1.0, "dark_mode": dark},
            palette={
                "bg": "#0a0a0c" if dark else "#ffffff",
                "fg": "#ffffff" if dark else "#0a0a0c",
                "muted": "#8a8e96",
                "grid": "#24262b" if dark else "#e6e8ec",
                "accent": "#2563eb" if not dark else "#60a5fa",
            },
        )

    if selected_skill == "minimalistic-graphics":
        return StyleAdapterParams(
            engine="minimalistic-graphics",
            line_weight=2.6,
            curve_tension=0.6,
            silhouette_language="monochrome_hairline_geometry_single_solid_dot",
            lighting_preset="pure_contrast_matte_void",
            texture_treatment="clean_svg_stroke_masks",
            grain_amount=0.015,
            vignette_strength=0.08,
            caption_style={
                "font_family": "Poppins",
                "font_weight": 400,
                "size_px": 42,
                "case": "lowercase_period",
                "max_words": 6,
                "y_anchor": 250,
            },
            color_grading={"contrast": 1.0, "saturation": 0.0},
            palette={"bg": "#000000", "fg": "#f4f4f4", "soft": "#9e9e9e"},
        )

    if selected_skill == "map-route":
        return StyleAdapterParams(
            engine="map-route",
            line_weight=0.34,
            curve_tension=0.45,
            silhouette_language="white_architectural_massing_ribbon_route_drop_pin",
            lighting_preset="hemisphere_daylight_soft_directional_sun",
            texture_treatment="matte_architectural_maquette",
            grain_amount=0.015,
            vignette_strength=0.14,
            caption_style={
                "font_family": "Inter",
                "font_weight": 600,
                "size_px": 40,
                "case": "sentence",
                "max_words": 4,
                "y_anchor": 1460,
            },
            color_grading={"contrast": 1.02, "saturation": 1.04},
            palette={"bg": "#eef0f1", "block": "#ffffff", "park": "#d3e9c6", "river": "#9fcbf2", "accent": "#2f7cf6", "pin": "#f0483e"},
        )

    if selected_skill == "breakdown":
        return StyleAdapterParams(
            engine="breakdown",
            line_weight=2.0,
            curve_tension=0.4,
            silhouette_language="exploded_axial_pbr_layers_elbow_leader_callouts",
            lighting_preset="dark_studio_room_env_warm_rim",
            texture_treatment="pbr_anodized_metal_glass_pcb_canvas",
            grain_amount=0.02,
            vignette_strength=0.22,
            caption_style={
                "font_family": "JetBrains Mono",
                "font_weight": 500,
                "size_px": 34,
                "case": "uppercase_technical",
                "max_words": 4,
                "y_anchor": 1520,
            },
            color_grading={"aces_exposure": 1.05, "contrast": 1.04},
            palette={"bg_inner": "#2a2d33", "bg_outer": "#0a0b0d", "fg": "#f3f1ed", "muted": "#8b9098", "accent": "#F08A5D"},
        )

    raise ValueError(f"Unsupported engine for style params: {selected_skill}")
