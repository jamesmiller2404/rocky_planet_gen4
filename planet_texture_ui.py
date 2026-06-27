r"""
Local browser UI for tuning rocky planet texture parameters.

Run:
    .\.venv\Scripts\python.exe planet_texture_ui.py

Then open:
    http://127.0.0.1:8765
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import time
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from PIL import Image

from rocky_planet_gen import (
    LAND_PALETTE_LABELS,
    LAND_PALETTES,
    PLANET_FAMILIES,
    PRESETS,
    PlanetConfig,
    TEXTURE_MAP_NAMES,
    build_maps,
    render_globe_preview,
    resolve_planet_colors,
    resolve_quad_workers,
    selected_texture_maps,
    save_map_set,
    save_quad_sphere_maps_low_memory,
    write_html_preview,
    write_quad_sphere_manifest,
)


HOST = "127.0.0.1"
PORT = int(os.environ.get("PLANET_TEXTURE_UI_PORT", "8765"))
QUAD_WORKERS = resolve_quad_workers(os.environ.get("PLANET_QUAD_WORKERS"))
OUTPUT_ROOT = Path("output")
SAVED_CONFIG_ROOT = OUTPUT_ROOT / "saved_configs"
UI_STATE_VERSION = 1


PARAM_GROUPS = [
    {
        "name": "Planet Type",
        "params": [
            ("planet_family", None, None, "select"),
            ("biosphere_strength", 0.00, 1.00, 0.01),
            ("atmosphere_density", 0.00, 1.00, 0.01),
            ("surface_age", 0.00, 1.00, 0.01),
            ("geologic_activity", 0.00, 1.00, 0.01),
            ("volatile_ice_strength", 0.00, 1.00, 0.01),
            ("tidal_lock_strength", 0.00, 1.00, 0.01),
            ("lava_activity", 0.00, 1.00, 0.01),
        ],
    },
    {
        "name": "Land And Ocean Shape",
        "params": [
            ("land_coverage", 0.05, 1.00, 0.01),
            ("continent_scale", 0.25, 5.00, 0.05),
            ("continent_detail", 1, 10, 1),
            ("continent_roughness", 0.20, 0.90, 0.01),
            ("continent_contrast", 0.05, 0.45, 0.01),
            ("island_density", 0.00, 1.00, 0.01),
            ("island_scale", 0.00, 80.00, 0.50),
            ("island_threshold", 0.00, 0.95, 0.01),
            ("island_chain_strength", 0.00, 1.00, 0.01),
            ("island_min_continent_distance", 0.00, 0.08, 0.001),
            ("island_max_continent_distance", 0.00, 0.50, 0.005),
            ("island_min_area", 0.00, 0.002, 0.00001),
            ("island_max_area", 0.00, 0.05, 0.0001),
        ],
    },
    {
        "name": "Shorelines And Shelves",
        "params": [
            ("shoreline_complexity", 0.00, 1.00, 0.01),
            ("shoreline_noise_scale", 2.00, 60.00, 0.50),
            ("shoreline_detail", 1, 10, 1),
            ("shoreline_erosion", 0.00, 0.70, 0.01),
            ("beach_width", 0.005, 0.120, 0.005),
            ("shelf_width", 0.02, 0.35, 0.01),
        ],
    },
    {
        "name": "Biomes And Climate",
        "params": [
            ("biome_scale", 1.00, 24.00, 0.25),
            ("biome_complexity", 1, 10, 1),
            ("desert_coverage", 0.00, 1.00, 0.01),
            ("forest_coverage", 0.00, 1.00, 0.01),
            ("polar_ice_size", 0.00, 0.75, 0.01),
            ("polar_ice_scale", 0.35, 5.00, 0.05),
            ("polar_ice_complexity", 0.00, 1.00, 0.01),
            ("polar_ice_fragmentation", 0.00, 1.00, 0.01),
            ("polar_ice_shelf_strength", 0.00, 1.00, 0.01),
            ("polar_ice_solidity", 0.00, 1.00, 0.01),
            ("snow_threshold", 0.20, 1.00, 0.01),
        ],
    },
    {
        "name": "Mountains And Height",
        "params": [
            ("mountain_density", 0.00, 1.00, 0.01),
            ("mountain_scale", 2.00, 40.00, 0.50),
            ("mountain_sharpness", 0.00, 1.00, 0.01),
            ("mountain_height", 0.00, 1.20, 0.01),
            ("mountain_boundary_alignment", 0.00, 1.00, 0.01),
        ],
    },
    {
        "name": "Impact Craters",
        "params": [
            ("crater_density", 0.00, 1.00, 0.01),
            ("crater_min_radius", 0.001, 0.060, 0.001),
            ("crater_max_radius", 0.002, 0.140, 0.001),
            ("crater_depth", 0.00, 1.00, 0.01),
            ("crater_rim_height", 0.00, 1.00, 0.01),
            ("crater_rim_width", 0.00, 1.00, 0.01),
            ("crater_erosion", 0.00, 1.00, 0.01),
            ("crater_land_bias", 0.00, 1.00, 0.01),
            ("crater_color_strength", 0.00, 1.00, 0.01),
            ("crater_small_density", 0.00, 1.00, 0.01),
            ("crater_medium_density", 0.00, 1.00, 0.01),
            ("crater_large_basin_density", 0.00, 1.00, 0.01),
            ("crater_ray_strength", 0.00, 1.00, 0.01),
            ("crater_floor_darkening", 0.00, 1.00, 0.01),
            ("crater_micro_pitting", 0.00, 1.00, 0.01),
        ],
    },
    {
        "name": "Moon Surface",
        "params": [
            ("moon_basin_strength", 0.00, 1.00, 0.01),
            ("moon_basin_scale", 0.15, 5.00, 0.05),
            ("moon_regolith_variation", 0.00, 1.00, 0.01),
        ],
    },
    {
        "name": "Cloud Creation",
        "params": [
            ("cloud_coverage", 0.00, 1.00, 0.01),
            ("cloud_scale", 0.20, 6.00, 0.05),
            ("cloud_detail", 1, 8, 1),
            ("cloud_roughness", 0.10, 0.90, 0.01),
            ("cloud_softness", 0.005, 0.60, 0.005),
            ("cloud_land_correlation", 0.00, 1.00, 0.01),
            ("cloud_opacity", 0.00, 1.00, 0.01),
            ("cloud_shadow_strength", 0.00, 1.00, 0.01),
            ("cloud_shadow_softness", 0.00, 1.00, 0.01),
            ("cloud_latitude_bias", -1.00, 1.00, 0.01),
            ("cloud_band_strength", 0.00, 1.00, 0.01),
            ("cloud_latitude_warp", 0.00, 2.00, 0.01),
            ("cloud_hemisphere_imbalance", 0.00, 2.00, 0.01),
            ("cloud_wind_stretch", 0.00, 1.00, 0.01),
            ("cloud_breakup", 0.00, 1.00, 0.01),
            ("storm_density", 0.00, 1.00, 0.01),
            ("spiral_storm_strength", 0.00, 1.00, 0.01),
            ("polar_cloud_strength", 0.00, 1.00, 0.01),
            ("polar_cloud_asymmetry", 0.00, 2.00, 0.01),
        ],
    },
    {
        "name": "Nebula Compositing",
        "params": [
            ("nebula_intensity", 0.00, 2.00, 0.01),
            ("nebula_coverage", 0.00, 1.00, 0.01),
            ("nebula_scale", 0.15, 8.00, 0.05),
            ("nebula_detail", 1, 8, 1),
            ("nebula_roughness", 0.10, 0.95, 0.01),
            ("nebula_warp", 0.00, 2.00, 0.01),
            ("nebula_filament_strength", 0.00, 1.00, 0.01),
            ("nebula_star_density", 0.00, 1.00, 0.01),
            ("nebula_color_mix", 0.00, 1.00, 0.01),
            ("nebula_color_softness", 0.00, 1.00, 0.01),
            ("nebula_base_color", "#000000", "#ffffff", "color"),
            ("nebula_core_color", "#000000", "#ffffff", "color"),
            ("nebula_accent_color", "#000000", "#ffffff", "color"),
        ],
    },
    {
        "name": "City Lights",
        "params": [
            ("city_lights_strength", 0.00, 1.00, 0.01),
            ("city_density", 0.00, 1.00, 0.01),
            ("megacity_count", 0, 80, 1),
            ("coastal_city_bias", 0.00, 1.00, 0.01),
            ("inland_city_bias", 0.00, 1.00, 0.01),
            ("city_sprawl", 0.00, 1.00, 0.01),
            ("road_network_strength", 0.00, 1.00, 0.01),
            ("light_temperature", 0.00, 1.00, 0.01),
        ],
    },
    {
        "name": "Palette Colors",
        "params": [
            ("land_color_count", 2, 9, 1),
            ("region_tint_count", 0, 8, 1),
            ("land_lowland_color", "#000000", "#ffffff", "color"),
            ("land_vegetation_color", "#000000", "#ffffff", "color"),
            ("land_forest_color", "#000000", "#ffffff", "color"),
            ("land_dry_color", "#000000", "#ffffff", "color"),
            ("land_desert_color", "#000000", "#ffffff", "color"),
            ("land_rock_color", "#000000", "#ffffff", "color"),
            ("land_beach_color", "#000000", "#ffffff", "color"),
            ("land_snow_color", "#000000", "#ffffff", "color"),
            ("land_ice_color", "#000000", "#ffffff", "color"),
            ("ocean_base_color", "#000000", "#ffffff", "color"),
            ("ocean_flat_color_strength", 0.00, 1.00, 0.01),
            ("ocean_shelf_color", "#000000", "#ffffff", "color"),
            ("ocean_shelf_color_strength", 0.00, 1.00, 0.01),
        ],
    },
    {
        "name": "Color Variation",
        "params": [
            ("ocean_current_strength", 0.00, 0.60, 0.01),
            ("land_color_variation", 0.00, 0.70, 0.01),
            ("continent_color_variation", 0.00, 0.80, 0.01),
            ("continent_color_scale", 0.50, 8.00, 0.05),
            ("continent_color_diversity", 0.00, 1.00, 0.01),
            ("continent_color_blend_smoothness", 0.00, 1.00, 0.01),
            ("land_brightness", -0.50, 0.50, 0.01),
            ("land_contrast", 0.50, 2.00, 0.01),
            ("ocean_color_variation", 0.00, 0.70, 0.01),
            ("ocean_shallow_tint_strength", 0.00, 1.00, 0.01),
            ("ocean_shelf_brightness", -0.50, 0.50, 0.01),
            ("ocean_shelf_contrast", 0.50, 2.00, 0.01),
            ("ocean_depth_tint_strength", 0.00, 1.00, 0.01),
            ("ocean_latitude_tint_strength", 0.00, 1.00, 0.01),
            ("ocean_productivity_strength", 0.00, 0.70, 0.01),
            ("ocean_sediment_strength", 0.00, 0.70, 0.01),
            ("ocean_brightness", -0.50, 0.50, 0.01),
            ("ocean_contrast", 0.50, 2.00, 0.01),
            ("ocean_hue_shift", -0.50, 0.50, 0.01),
            ("ocean_saturation", 0.00, 3.00, 0.01),
            ("ocean_colorizer_hue", 0.00, 1.00, 0.01),
            ("ocean_colorizer_strength", 0.00, 1.00, 0.01),
            ("mineral_tint_strength", 0.00, 0.80, 0.01),
            ("wetland_tint_strength", 0.00, 0.60, 0.01),
            ("iron_oxide_tint_strength", 0.00, 0.80, 0.01),
            ("basalt_tint_strength", 0.00, 0.80, 0.01),
            ("salt_flat_tint_strength", 0.00, 0.80, 0.01),
            ("clay_tint_strength", 0.00, 0.80, 0.01),
        ],
    },
    {
        "name": "Advanced Land Tints",
        "params": [
            ("land_ochre_tint_color", "#000000", "#ffffff", "color"),
            ("land_rust_tint_color", "#000000", "#ffffff", "color"),
            ("land_wet_tint_color", "#000000", "#ffffff", "color"),
            ("land_tundra_tint_color", "#000000", "#ffffff", "color"),
            ("land_highland_tint_color", "#000000", "#ffffff", "color"),
            ("land_iron_oxide_tint_color", "#000000", "#ffffff", "color"),
            ("land_basalt_tint_color", "#000000", "#ffffff", "color"),
            ("land_salt_flat_tint_color", "#000000", "#ffffff", "color"),
            ("land_clay_tint_color", "#000000", "#ffffff", "color"),
            ("land_solid_ice_tint_color", "#000000", "#ffffff", "color"),
        ],
    },
]

INT_PARAMS = {
    key
    for group in PARAM_GROUPS
    for key, _minimum, _maximum, step in group["params"]
    if isinstance(step, int)
}

COLOR_PARAMS = {
    key
    for group in PARAM_GROUPS
    for key, _minimum, _maximum, step in group["params"]
    if step == "color"
}

STRING_PARAMS = {
    key
    for key, value in PRESETS["earthlike"].items()
    if isinstance(value, str)
}

UI_DEFAULT_OVERRIDES = {
    key: 0.0
    for group in PARAM_GROUPS
    for key, _minimum, _maximum, _step in group["params"]
    if key.startswith("island_")
}
UI_DEFAULT_OVERRIDES["shelf_width"] = 0.08

CLOUD_RECIPES = {
    "none": {
        "label": "No clouds",
        "values": {
            "cloud_coverage": 0.0,
            "cloud_opacity": 0.0,
            "cloud_shadow_strength": 0.0,
            "cloud_latitude_warp": 0.0,
            "cloud_hemisphere_imbalance": 0.0,
            "storm_density": 0.0,
            "spiral_storm_strength": 0.0,
            "polar_cloud_strength": 0.0,
            "polar_cloud_asymmetry": 0.0,
        },
    },
    "earthlike": {
        "label": "Earthlike",
        "values": {
            "cloud_coverage": 0.46,
            "cloud_scale": 1.25,
            "cloud_detail": 5,
            "cloud_roughness": 0.48,
            "cloud_softness": 0.22,
            "cloud_land_correlation": 0.55,
            "cloud_opacity": 0.78,
            "cloud_shadow_strength": 0.36,
            "cloud_shadow_softness": 0.34,
            "cloud_latitude_bias": 0.18,
            "cloud_band_strength": 0.24,
            "cloud_latitude_warp": 1.00,
            "cloud_hemisphere_imbalance": 1.00,
            "cloud_wind_stretch": 0.38,
            "cloud_breakup": 0.34,
            "storm_density": 0.24,
            "spiral_storm_strength": 0.18,
            "polar_cloud_strength": 0.10,
            "polar_cloud_asymmetry": 1.00,
        },
    },
    "stormy": {
        "label": "Stormy",
        "values": {
            "cloud_coverage": 0.64,
            "cloud_scale": 1.10,
            "cloud_detail": 6,
            "cloud_roughness": 0.56,
            "cloud_softness": 0.20,
            "cloud_land_correlation": 0.38,
            "cloud_opacity": 0.88,
            "cloud_shadow_strength": 0.46,
            "cloud_shadow_softness": 0.28,
            "cloud_latitude_bias": 0.10,
            "cloud_band_strength": 0.36,
            "cloud_latitude_warp": 1.25,
            "cloud_hemisphere_imbalance": 1.15,
            "cloud_wind_stretch": 0.54,
            "cloud_breakup": 0.30,
            "storm_density": 0.72,
            "spiral_storm_strength": 0.46,
            "polar_cloud_strength": 0.14,
            "polar_cloud_asymmetry": 1.15,
        },
    },
    "thin_haze": {
        "label": "Thin haze",
        "values": {
            "cloud_coverage": 0.34,
            "cloud_scale": 0.85,
            "cloud_detail": 4,
            "cloud_roughness": 0.38,
            "cloud_softness": 0.42,
            "cloud_land_correlation": 0.48,
            "cloud_opacity": 0.38,
            "cloud_shadow_strength": 0.14,
            "cloud_shadow_softness": 0.58,
            "cloud_latitude_bias": 0.04,
            "cloud_band_strength": 0.12,
            "cloud_latitude_warp": 0.55,
            "cloud_hemisphere_imbalance": 0.45,
            "cloud_wind_stretch": 0.22,
            "cloud_breakup": 0.18,
            "storm_density": 0.04,
            "spiral_storm_strength": 0.0,
            "polar_cloud_strength": 0.18,
            "polar_cloud_asymmetry": 0.70,
        },
    },
    "broken_marine": {
        "label": "Broken marine",
        "values": {
            "cloud_coverage": 0.40,
            "cloud_scale": 2.25,
            "cloud_detail": 5,
            "cloud_roughness": 0.54,
            "cloud_softness": 0.16,
            "cloud_land_correlation": 0.20,
            "cloud_opacity": 0.74,
            "cloud_shadow_strength": 0.32,
            "cloud_shadow_softness": 0.26,
            "cloud_latitude_bias": 0.22,
            "cloud_band_strength": 0.28,
            "cloud_latitude_warp": 1.45,
            "cloud_hemisphere_imbalance": 1.20,
            "cloud_wind_stretch": 0.62,
            "cloud_breakup": 0.64,
            "storm_density": 0.18,
            "spiral_storm_strength": 0.08,
            "polar_cloud_strength": 0.04,
            "polar_cloud_asymmetry": 0.85,
        },
    },
}


def ui_preset_defaults() -> dict:
    return {
        name: {**values, **UI_DEFAULT_OVERRIDES}
        for name, values in PRESETS.items()
    }


def preview_image_for_map(name: str, arr: np.ndarray) -> Image.Image:
    clipped = np.clip(arr, 0, 255 if arr.ndim == 3 else 1)
    if arr.ndim == 2:
        clipped = clipped * 255.0
        return Image.fromarray(clipped.astype(np.uint8), "L")
    return Image.fromarray(clipped.astype(np.uint8), "RGB")


def image_data_url(arr: np.ndarray, name: str = "color") -> str:
    image = preview_image_for_map(name, arr)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def preview_maps_payload(maps: dict) -> dict:
    return {
        name: {
            "label": TEXTURE_MAP_LABELS.get(name, name.replace("_", " ").title()),
            "image": image_data_url(maps[name], name),
        }
        for name in TEXTURE_MAP_NAMES
        if name in maps
    }


def sanitized_name(value: str, fallback: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value.strip()).strip("._-")
    return clean or fallback


def unique_output_dir(name: str) -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    base = OUTPUT_ROOT / name
    if not base.exists():
        return base
    suffix = time.strftime("%H%M%S")
    candidate = OUTPUT_ROOT / f"{name}_{suffix}"
    counter = 2
    while candidate.exists():
        candidate = OUTPUT_ROOT / f"{name}_{suffix}_{counter}"
        counter += 1
    return candidate


def config_from_payload(payload: dict, preview: bool) -> PlanetConfig:
    preset = str(payload.get("preset", "earthlike"))
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset: {preset}")

    data = dict(PRESETS[preset])
    params = payload.get("params", {})
    if not isinstance(params, dict):
        raise ValueError("params must be an object")

    for key in data:
        if key in params:
            value = params[key]
            if key in STRING_PARAMS:
                value = str(value)
                if key == "land_palette" and value not in LAND_PALETTES:
                    raise ValueError(f"Unknown land palette: {value}")
                if key == "planet_family" and value not in PLANET_FAMILIES:
                    raise ValueError(f"Unknown planet family: {value}")
                data[key] = value
            else:
                data[key] = int(value) if key in INT_PARAMS else float(value)

    if preview:
        width = int(payload.get("preview_width", 512))
        height = max(32, width // 2)
    else:
        width = int(payload.get("width", 2048))
        height = int(payload.get("height", 1024))

    if width < 64 or height < 32:
        raise ValueError("Width must be at least 64 and height must be at least 32.")

    return PlanetConfig(
        preset=preset,
        seed=int(payload.get("seed", 42)),
        width=width,
        height=height,
        **data,
    )


TEXTURE_MAP_LABELS = {
    "color": "Color",
    "height": "Height",
    "normal": "Normal",
    "roughness": "Roughness",
    "land_mask": "Land mask",
    "shoreline_mask": "Shoreline mask",
    "ocean_depth": "Ocean depth",
    "cloud_mask": "Cloud mask",
    "cloud_shadow": "Cloud shadow",
    "nebula_color": "Nebula color",
    "nebula_alpha": "Nebula alpha",
    "nebula_stars": "Nebula stars",
    "city_lights": "City lights",
    "atmosphere_haze": "Atmosphere haze",
    "emissive_heat": "Emissive heat",
}

PARAM_LABELS = {
    "planet_family": "Planet family",
    "biosphere_strength": "Biosphere strength",
    "atmosphere_density": "Atmosphere density",
    "surface_age": "Surface age",
    "geologic_activity": "Geologic activity",
    "volatile_ice_strength": "Volatile ice strength",
    "tidal_lock_strength": "Tidal locking",
    "lava_activity": "Lava activity",
    "crater_small_density": "Small crater density",
    "crater_medium_density": "Medium crater density",
    "crater_large_basin_density": "Large basin density",
    "crater_ray_strength": "Fresh ray strength",
    "crater_floor_darkening": "Floor darkening",
    "crater_micro_pitting": "Micro-pitting",
    "moon_basin_strength": "Maria basin strength",
    "moon_basin_scale": "Maria basin scale",
    "moon_regolith_variation": "Regolith variation",
    "cloud_coverage": "Cloud coverage",
    "cloud_scale": "System size",
    "cloud_detail": "Cloud detail",
    "cloud_roughness": "Raggedness",
    "cloud_softness": "Edge softness",
    "cloud_land_correlation": "Land-form correlation",
    "cloud_opacity": "Cloud opacity",
    "cloud_shadow_strength": "Shadow strength",
    "cloud_shadow_softness": "Shadow softness",
    "cloud_latitude_bias": "Latitude bias",
    "cloud_band_strength": "Atmospheric bands",
    "cloud_latitude_warp": "3D band warp",
    "cloud_hemisphere_imbalance": "Hemisphere imbalance",
    "cloud_wind_stretch": "Wind stretch",
    "cloud_breakup": "Cloud breakup",
    "storm_density": "Storm density",
    "spiral_storm_strength": "Spiral storm strength",
    "polar_cloud_strength": "Polar cloud strength",
    "polar_cloud_asymmetry": "Polar texture asymmetry",
    "nebula_intensity": "Nebula intensity",
    "nebula_coverage": "Nebula coverage",
    "nebula_scale": "Nebula scale",
    "nebula_detail": "Nebula detail",
    "nebula_roughness": "Nebula raggedness",
    "nebula_warp": "Nebula warp",
    "nebula_filament_strength": "Filament strength",
    "nebula_star_density": "Star density",
    "nebula_color_mix": "Color mix",
    "nebula_color_softness": "Color boundary softness",
    "nebula_base_color": "Base gas color",
    "nebula_core_color": "Core emission color",
    "nebula_accent_color": "Accent gas color",
}


def texture_maps_from_payload(payload: dict) -> tuple[str, ...]:
    requested = payload.get("texture_maps")
    if not isinstance(requested, list):
        return TEXTURE_MAP_NAMES
    return selected_texture_maps(requested)


def metadata_for_config(
    cfg: PlanetConfig,
    projection: str,
    face_size: int | None = None,
    texture_maps: tuple[str, ...] | None = None,
    ui_state: dict | None = None,
    output_kind: str = "texture_output",
) -> dict:
    metadata = asdict(cfg)
    metadata["output_projection"] = projection
    metadata["output_texture_maps"] = list(texture_maps or TEXTURE_MAP_NAMES)
    metadata["output_kind"] = output_kind
    if face_size is not None:
        metadata["quad_sphere_face_size"] = face_size
    if ui_state is not None:
        metadata["ui_state"] = ui_state
    resolved_palette = resolve_planet_colors(cfg)
    metadata["resolved_palette_rgb"] = {
        name: [int(round(channel)) for channel in color]
        for name, color in resolved_palette.items()
    }
    return metadata


def ui_state_from_payload(
    payload: dict,
    cfg: PlanetConfig,
    projection: str,
    face_size: int | None,
    texture_maps: tuple[str, ...],
) -> dict:
    params = {}
    source_params = payload.get("params", {})
    if not isinstance(source_params, dict):
        source_params = {}
    defaults = ui_preset_defaults().get(cfg.preset, {})
    for key in defaults:
        params[key] = source_params.get(key, getattr(cfg, key, defaults[key]))
    return {
        "version": UI_STATE_VERSION,
        "preset": cfg.preset,
        "seed": cfg.seed,
        "width": cfg.width,
        "height": cfg.height,
        "preview_width": int(payload.get("preview_width", 512)),
        "projection": projection,
        "face_size": int(face_size if face_size is not None else payload.get("face_size", min(cfg.width, cfg.height))),
        "texture_maps": list(texture_maps),
        "params": params,
    }


def metadata_from_payload(payload: dict, output_kind: str = "texture_output") -> dict:
    cfg = config_from_payload(payload, preview=False)
    projection = str(payload.get("projection", "equirectangular"))
    texture_maps = texture_maps_from_payload(payload)
    face_size = int(payload.get("face_size") or min(cfg.width, cfg.height))
    ui_state = ui_state_from_payload(payload, cfg, projection, face_size, texture_maps)
    metadata_face_size = face_size if projection == "quad_sphere" else None
    return metadata_for_config(cfg, projection, metadata_face_size, texture_maps, ui_state, output_kind)


def image_file_summary(path: Path) -> dict:
    with Image.open(path) as image:
        width, height = image.size
        mode = image.mode
    return {
        "path": str(path.resolve()),
        "file": path.name,
        "width": width,
        "height": height,
        "mode": mode,
        "bytes": path.stat().st_size,
    }


def timed_stage(report: dict, name: str, label: str, fn):
    started = time.perf_counter()
    try:
        return fn()
    finally:
        report["stages"].append(
            {
                "name": name,
                "label": label,
                "seconds": time.perf_counter() - started,
            }
        )


def save_map_set_with_report(out_dir: Path, maps: dict, texture_maps: tuple[str, ...], report: dict) -> None:
    for name in texture_maps:
        started = time.perf_counter()
        save_map_set(out_dir, maps, (name,))
        write_seconds = time.perf_counter() - started
        path = out_dir / f"{name}.png"
        entry = {
            "name": name,
            "projection": "equirectangular",
            "write_seconds": write_seconds,
            "files": [image_file_summary(path)] if path.exists() else [],
        }
        report["maps"].append(entry)


def summarize_quad_sphere_maps(quad_dir: Path, face_dirs: list[str], texture_maps: tuple[str, ...]) -> list[dict]:
    entries = []
    for name in texture_maps:
        face_files = []
        for face in face_dirs:
            path = quad_dir / face / f"{name}.png"
            if path.exists():
                info = image_file_summary(path)
                info["face"] = face
                face_files.append(info)
        stitched_path = quad_dir / f"{name}_cubemap_cross.png"
        stitched = image_file_summary(stitched_path) if stitched_path.exists() else None
        entries.append(
            {
                "name": name,
                "projection": "quad_sphere",
                "face_count": len(face_files),
                "files": face_files,
                "stitched_atlas": stitched,
                "bytes": sum(item["bytes"] for item in face_files) + (stitched["bytes"] if stitched else 0),
            }
        )
    return entries


def save_planet_output(payload: dict) -> tuple[Path, dict]:
    cfg = config_from_payload(payload, preview=False)
    projection = str(payload.get("projection", "equirectangular"))
    texture_maps = texture_maps_from_payload(payload)
    output_name = sanitized_name(
        str(payload.get("output_name", "")),
        f"{cfg.preset}_{cfg.seed}_{time.strftime('%Y%m%d_%H%M%S')}",
    )
    out_dir = unique_output_dir(output_name)
    out_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "preset": cfg.preset,
        "seed": cfg.seed,
        "projection": projection,
        "texture_maps": list(texture_maps),
        "requested_size": {"width": cfg.width, "height": cfg.height},
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stages": [],
        "maps": [],
    }
    total_started = time.perf_counter()

    if projection == "quad_sphere":
        face_size = int(payload.get("face_size") or min(cfg.width, cfg.height))
        if face_size < 32:
            raise ValueError("Quad-sphere face size must be at least 32.")
        quad_dir = out_dir / "quad_sphere"
        quad_dir.mkdir(parents=True, exist_ok=True)
        report["face_size"] = face_size
        report["quad_workers"] = QUAD_WORKERS
        timed_stage(
            report,
            "quad_sphere_maps",
            "Generate and write quad-sphere faces",
            lambda: save_quad_sphere_maps_low_memory(quad_dir, cfg, face_size, texture_maps, quad_workers=QUAD_WORKERS),
        )
        timed_stage(
            report,
            "quad_sphere_manifest",
            "Write quad-sphere manifest",
            lambda: write_quad_sphere_manifest(out_dir, face_size, texture_maps),
        )
        ui_state = ui_state_from_payload(payload, cfg, "quad_sphere", face_size, texture_maps)
        metadata = metadata_for_config(cfg, "quad_sphere", face_size, texture_maps, ui_state)
        face_dirs = sorted(path.name for path in quad_dir.iterdir() if path.is_dir())
        report["maps"] = summarize_quad_sphere_maps(quad_dir, face_dirs, texture_maps)
        report["face_count"] = len(face_dirs)
    else:
        maps = timed_stage(
            report,
            "build_maps",
            "Build selected texture maps",
            lambda: build_maps(cfg, texture_maps),
        )
        timed_stage(
            report,
            "write_maps",
            "Write selected texture maps",
            lambda: save_map_set_with_report(out_dir, maps, texture_maps, report),
        )
        if "color" in texture_maps:
            timed_stage(
                report,
                "preview_assets",
                "Write preview assets",
                lambda: (
                    render_globe_preview(maps["color"], maps["height"], out_dir / "preview.png"),
                    write_html_preview(out_dir, f"{cfg.preset} planet preview", texture_maps),
                ),
            )
        ui_state = ui_state_from_payload(payload, cfg, "equirectangular", int(payload.get("face_size") or min(cfg.width, cfg.height)), texture_maps)
        metadata = metadata_for_config(cfg, "equirectangular", texture_maps=texture_maps, ui_state=ui_state)

    timed_stage(
        report,
        "metadata",
        "Write preset metadata",
        lambda: (out_dir / "preset.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8"),
    )
    report["total_seconds"] = time.perf_counter() - total_started
    report["output_dir"] = str(out_dir.resolve())
    (out_dir / "generation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return out_dir, report


def save_config_only(payload: dict) -> Path:
    metadata = metadata_from_payload(payload, "config")
    ui_state = metadata["ui_state"]
    fallback_name = f"{ui_state['preset']}_{ui_state['seed']}_{time.strftime('%Y%m%d_%H%M%S')}"
    output_name = sanitized_name(str(payload.get("output_name", "")), fallback_name)
    SAVED_CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    out_dir = unique_config_dir(output_name)
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "preset.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return out_dir


def unique_config_dir(name: str) -> Path:
    base = SAVED_CONFIG_ROOT / name
    if not base.exists():
        return base
    suffix = time.strftime("%H%M%S")
    candidate = SAVED_CONFIG_ROOT / f"{name}_{suffix}"
    counter = 2
    while candidate.exists():
        candidate = SAVED_CONFIG_ROOT / f"{name}_{suffix}_{counter}"
        counter += 1
    return candidate


def output_summary(out_dir: Path, report: dict | None = None) -> dict:
    quad_dir = out_dir / "quad_sphere"
    stitched = sorted(path.name for path in quad_dir.glob("*_cubemap_cross.png")) if quad_dir.exists() else []
    face_dirs = sorted(path.name for path in quad_dir.iterdir() if path.is_dir()) if quad_dir.exists() else []
    generated_maps = [f"{name}.png" for name in TEXTURE_MAP_NAMES if (out_dir / f"{name}.png").exists()]
    if quad_dir.exists():
        generated_maps = [
            f"{name}.png"
            for name in TEXTURE_MAP_NAMES
            if any((quad_dir / face / f"{name}.png").exists() for face in face_dirs)
        ]
    summary = {
        "output_dir": str(out_dir.resolve()),
        "quad_sphere_faces": face_dirs,
        "stitched_quad_sphere_maps": stitched,
        "generated_maps": generated_maps,
    }
    if report is not None:
        summary["generation_report"] = report
    return summary


def validate_texture_maps(value) -> list[str]:
    if not isinstance(value, list):
        return list(TEXTURE_MAP_NAMES)
    return list(selected_texture_maps(value))


def normalize_ui_state(data: dict) -> dict:
    state = data.get("ui_state")
    if isinstance(state, dict):
        preset = str(state.get("preset", data.get("preset", "earthlike")))
        if preset not in PRESETS:
            preset = "earthlike"
        params = dict(ui_preset_defaults()[preset])
        loaded_params = state.get("params", {})
        if isinstance(loaded_params, dict):
            for key in params:
                if key in loaded_params:
                    params[key] = loaded_params[key]
        if params.get("land_palette") not in LAND_PALETTES:
            params["land_palette"] = ui_preset_defaults()[preset].get("land_palette", "natural_earth")
        return {
            "version": int(state.get("version", UI_STATE_VERSION)),
            "preset": preset,
            "seed": int(state.get("seed", data.get("seed", 42))),
            "width": max(64, int(state.get("width", data.get("width", 2048)))),
            "height": max(32, int(state.get("height", data.get("height", 1024)))),
            "preview_width": int(state.get("preview_width", 512)),
            "projection": "quad_sphere" if state.get("projection") == "quad_sphere" else "equirectangular",
            "face_size": max(32, int(state.get("face_size", data.get("quad_sphere_face_size", min(int(data.get("width", 2048)), int(data.get("height", 1024))))))),
            "texture_maps": validate_texture_maps(state.get("texture_maps", data.get("output_texture_maps", TEXTURE_MAP_NAMES))),
            "params": params,
        }

    preset = str(data.get("preset", "earthlike"))
    if preset not in PRESETS:
        preset = "earthlike"
    params = dict(ui_preset_defaults()[preset])
    for key in params:
        if key in data:
            params[key] = data[key]
    if params.get("land_palette") not in LAND_PALETTES:
        params["land_palette"] = ui_preset_defaults()[preset].get("land_palette", "natural_earth")
    width = max(64, int(data.get("width", 2048)))
    height = max(32, int(data.get("height", 1024)))
    return {
        "version": 0,
        "preset": preset,
        "seed": int(data.get("seed", 42)),
        "width": width,
        "height": height,
        "preview_width": 512,
        "projection": "quad_sphere" if data.get("output_projection") == "quad_sphere" else "equirectangular",
        "face_size": max(32, int(data.get("quad_sphere_face_size", min(width, height)))),
        "texture_maps": validate_texture_maps(data.get("output_texture_maps", TEXTURE_MAP_NAMES)),
        "params": params,
    }


def load_saved_state(path_text: str) -> dict:
    path = Path(path_text)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists() or path.name != "preset.json":
        raise ValueError("Choose an existing preset.json file.")

    data = json.loads(path.read_text(encoding="utf-8"))
    state = normalize_ui_state(data)
    resolved_path = path.resolve()
    try:
        list_path = str(resolved_path.relative_to(Path.cwd().resolve()))
    except ValueError:
        list_path = str(resolved_path)
    state["path"] = str(resolved_path)
    state["list_path"] = list_path
    state["folder_name"] = resolved_path.parent.name
    return state


def saved_config_entry(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = normalize_ui_state(data)
    except Exception:
        return None
    try:
        relative_path = str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        relative_path = str(path.resolve())
    return {
        "name": path.parent.name,
        "path": relative_path,
        "kind": data.get("output_kind", "texture_output"),
        "preset": state["preset"],
        "seed": state["seed"],
        "projection": state["projection"],
        "texture_maps": state["texture_maps"],
        "modified": path.stat().st_mtime,
    }


def list_saved_configs() -> dict:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    entries = []
    for path in OUTPUT_ROOT.rglob("preset.json"):
        entry = saved_config_entry(path)
        if entry is not None:
            entries.append(entry)
    entries.sort(key=lambda item: item["modified"], reverse=True)
    return {"items": entries}


def deletable_saved_folder(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    output_root = OUTPUT_ROOT.resolve()
    if path.name != "preset.json" or not path.exists():
        raise ValueError("Choose an existing preset.json file.")
    if not path.is_relative_to(output_root):
        raise ValueError("Saved planet must be inside the output folder.")
    folder = path.parent
    if folder == output_root or folder == Path.cwd().resolve():
        raise ValueError("Refusing to delete the output root.")
    return folder


def delete_saved_config(path_text: str) -> dict:
    folder = deletable_saved_folder(path_text)
    deleted = str(folder.resolve())
    shutil.rmtree(folder)
    return {"deleted": deleted, **list_saved_configs()}


def default_payload() -> dict:
    land_palette_colors = {
        key: {
            **{
                f"land_{name}_color": f"#{int(color[0]):02x}{int(color[1]):02x}{int(color[2]):02x}"
                for name, color in {
                    "lowland": palette["colors"]["grass"],
                    "vegetation": palette["colors"]["forest"],
                    "forest": palette["colors"]["dark_forest"],
                    "dry": palette["colors"]["dry_plain"],
                    "desert": palette["colors"]["desert"],
                    "rock": palette["colors"]["rock"],
                    "beach": palette["colors"]["beach"],
                    "snow": palette["colors"]["snow"],
                    "ice": palette["colors"]["ice"],
                }.items()
            },
            **{
                f"land_{name}_tint_color": f"#{int(color[0]):02x}{int(color[1]):02x}{int(color[2]):02x}"
                for name, color in {
                    "ochre": palette["tints"]["ochre"],
                    "rust": palette["tints"]["rust"],
                    "wet": palette["tints"]["dark_wet"],
                    "tundra": palette["tints"]["cool_tundra"],
                    "highland": palette["tints"]["pale_highland"],
                    "iron_oxide": palette["tints"]["iron_oxide"],
                    "basalt": palette["tints"]["basalt"],
                    "salt_flat": palette["tints"]["salt_flat"],
                    "clay": palette["tints"]["clay"],
                    "solid_ice": palette["tints"]["solid_ice"],
                }.items()
            },
        }
        for key, palette in LAND_PALETTES.items()
    }
    return {
        "presets": sorted(PRESETS),
        "defaults": ui_preset_defaults(),
        "param_groups": [
            {
                "name": group["name"],
                "params": [
                    {
                        "key": key,
                        "label": PARAM_LABELS.get(key, key.replace("_", " ").title()),
                        "type": "color" if key in COLOR_PARAMS else ("select" if step == "select" else "range"),
                        "min": minimum,
                        "max": maximum,
                        "step": step,
                        "options": [
                            {"key": option_key, "label": option_label}
                            for option_key, option_label in PLANET_FAMILIES.items()
                        ] if key == "planet_family" else None,
                        "integer": key in INT_PARAMS,
                    }
                    for key, minimum, maximum, step in group["params"]
                ],
            }
            for group in PARAM_GROUPS
        ],
        "texture_maps": [
            {"key": key, "label": TEXTURE_MAP_LABELS.get(key, key.replace("_", " ").title())}
            for key in TEXTURE_MAP_NAMES
        ],
        "cloud_recipes": CLOUD_RECIPES,
        "land_palettes": [
            {"key": key, "label": LAND_PALETTE_LABELS.get(key, key.replace("_", " ").title())}
            for key in LAND_PALETTES
        ],
        "land_palette_colors": land_palette_colors,
    }


class PlanetUiHandler(BaseHTTPRequestHandler):
    server_version = "PlanetTextureUI/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.write_text(UI_HTML, "text/html")
        elif parsed.path == "/api/defaults":
            self.write_json(default_payload())
        elif parsed.path == "/api/config/list":
            self.write_json(list_saved_configs())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self.read_json()
            if parsed.path == "/api/preview":
                cfg = config_from_payload(payload, preview=True)
                maps = build_maps(cfg)
                self.write_json(
                    {
                        "color": image_data_url(maps["color"], "color"),
                        "maps": preview_maps_payload(maps),
                        "summary": {
                            "preset": cfg.preset,
                            "seed": cfg.seed,
                            "preview_size": f"{cfg.width}x{cfg.height}",
                        },
                    }
                )
            elif parsed.path == "/api/save":
                out_dir, report = save_planet_output(payload)
                self.write_json(output_summary(out_dir, report))
            elif parsed.path == "/api/config/save":
                out_dir = save_config_only(payload)
                self.write_json({"output_dir": str(out_dir.resolve()), "preset_path": str((out_dir / "preset.json").resolve())})
            elif parsed.path == "/api/config/delete":
                self.write_json(delete_saved_config(str(payload.get("path", ""))))
            elif parsed.path == "/api/load":
                self.write_json(load_saved_state(str(payload.get("path", ""))))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def read_json(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def write_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def write_text(self, text: str, content_type: str) -> None:
        raw = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")


UI_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rocky Planet Texture UI</title>
<style>
:root {
  color-scheme: dark;
  --bg: #111214;
  --panel: #191b1f;
  --panel-2: #22252b;
  --line: #343840;
  --text: #f1f2f3;
  --muted: #a9b0ba;
  --accent: #55b7a5;
  --warn: #e8b85a;
  --error: #ee6b6e;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
main {
  display: grid;
  grid-template-columns: minmax(320px, 410px) minmax(0, 1fr);
  min-height: 100vh;
}
aside {
  border-right: 1px solid var(--line);
  background: var(--panel);
  padding: 16px;
  overflow: auto;
  max-height: 100vh;
}
.preview {
  padding: 18px;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 16px;
}
h1 {
  margin: 0 0 14px;
  font-size: 18px;
  font-weight: 650;
}
h2 {
  margin: 0;
  font-size: 13px;
  font-weight: 650;
  color: var(--muted);
}
.control-tabs {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  margin: 12px 0 10px;
}
.tab-button {
  min-height: 34px;
  padding: 6px 4px;
  font-size: 13px;
}
.tab-button.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #071210;
  font-weight: 700;
}
.tab-panel {
  display: none;
}
.tab-panel.active {
  display: block;
}
.row {
  display: grid;
  grid-template-columns: 1fr 120px;
  gap: 10px;
  align-items: center;
  margin: 10px 0;
}
.row label {
  min-width: 0;
  overflow-wrap: anywhere;
}
.row input[type="number"],
.row input[type="color"],
.row input[type="text"],
select {
  width: 100%;
  min-height: 34px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #101115;
  color: var(--text);
  padding: 6px 8px;
}
input[type="range"] {
  width: 100%;
}
.color-control {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 52px;
  gap: 10px;
  align-items: center;
  margin: 10px 0;
}
.color-control label {
  min-width: 0;
  overflow-wrap: anywhere;
}
.color-control input[type="color"] {
  width: 52px;
  min-height: 34px;
  padding: 2px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #101115;
}
details {
  border-top: 1px solid var(--line);
  padding: 10px 0;
}
summary {
  cursor: pointer;
  color: var(--text);
  font-weight: 650;
}
.slider-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 76px;
  gap: 10px;
  align-items: center;
  margin-top: 10px;
}
.slider-head span {
  color: var(--muted);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 14px;
}
button {
  min-height: 36px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--panel-2);
  color: var(--text);
  cursor: pointer;
}
button.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #071210;
  font-weight: 700;
}
button:disabled {
  opacity: 0.55;
  cursor: progress;
}
.image-grid {
  display: grid;
  grid-template-columns: minmax(280px, 2fr) minmax(260px, 1fr);
  gap: 16px;
  align-items: start;
}
figure {
  margin: 0;
  background: #07080a;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}
figcaption {
  padding: 8px 10px;
  color: var(--muted);
  border-top: 1px solid var(--line);
}
img {
  display: block;
  width: 100%;
  height: auto;
}
.texture-figure {
  display: grid;
  grid-template-rows: auto minmax(180px, auto) auto;
}
.texture-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(150px, 220px) auto;
  gap: 10px;
  align-items: center;
  padding: 8px;
  border-bottom: 1px solid var(--line);
}
.texture-toolbar label {
  color: var(--muted);
  font-size: 12px;
}
.texture-toolbar select {
  min-height: 30px;
}
.cloud-layer-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.cloud-layer-toggle input {
  width: 15px;
  height: 15px;
  margin: 0;
}
.texture-figure img {
  min-height: 180px;
  object-fit: contain;
}
.globe-figure {
  display: grid;
  grid-template-rows: auto minmax(260px, 1fr) auto;
}
.globe-toolbar {
  display: grid;
  grid-template-columns: 74px minmax(120px, 1fr) auto auto minmax(110px, 1fr) 48px;
  gap: 8px;
  align-items: center;
  padding: 8px;
  border-bottom: 1px solid var(--line);
}
.globe-toolbar label,
.globe-toolbar span {
  color: var(--muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.globe-toolbar button {
  min-height: 30px;
}
.cloud-recipes {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin: 10px 0 4px;
}
.cloud-recipes button {
  min-height: 30px;
  padding: 4px 6px;
  font-size: 12px;
}
.globe-canvas-wrap {
  display: grid;
  place-items: center;
  min-height: 260px;
  background:
    radial-gradient(circle at center, rgba(85, 183, 165, 0.08), transparent 62%),
    #040506;
}
#globeCanvas {
  display: block;
  width: 100%;
  max-width: 560px;
  aspect-ratio: 1;
  cursor: grab;
  touch-action: none;
}
#globeCanvas.dragging {
  cursor: grabbing;
}
.status {
  min-height: 42px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  color: var(--muted);
  padding: 10px 12px;
  overflow-wrap: anywhere;
}
.status.error { color: var(--error); }
.status.ok { color: var(--accent); }
.status.busy { color: var(--warn); }
.load-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 76px;
  gap: 8px;
  margin-top: 8px;
}
.saved-planets-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 14px;
}
.saved-planets-head h3 {
  margin: 0;
  font-size: 14px;
}
.saved-planets-head button {
  width: auto;
  min-height: 28px;
  padding: 4px 9px;
  font-size: 12px;
}
.saved-planets {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}
.saved-planet {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #11151d;
  padding: 8px;
}
.saved-planet.loaded {
  border-color: var(--accent);
  background: #12201b;
  box-shadow: 0 0 0 1px rgba(61, 220, 151, 0.35);
}
.saved-planet-title {
  color: var(--text);
  font-size: 13px;
  overflow-wrap: anywhere;
}
.saved-planet-meta {
  color: var(--muted);
  font-size: 12px;
  margin-top: 2px;
}
.saved-planet button {
  min-height: 30px;
}
.saved-planet-actions {
  display: flex;
  gap: 6px;
}
.saved-planet-actions button {
  width: auto;
  min-width: 58px;
  padding: 5px 8px;
}
.saved-planet-actions .danger {
  border-color: rgba(255, 107, 107, 0.5);
  color: var(--error);
}
.hint {
  margin: 4px 0 10px;
  color: var(--muted);
  font-size: 12px;
}
.map-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 8px 0 12px;
}
.map-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.map-actions {
  display: flex;
  gap: 6px;
}
.map-actions button {
  width: auto;
  min-height: 28px;
  padding: 4px 9px;
  font-size: 12px;
}
.map-option {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 6px 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #11151d;
  color: var(--text);
  font-size: 13px;
}
.map-option input {
  width: 16px;
  height: 16px;
  margin: 0;
}
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  padding: 18px;
  background: rgba(5, 6, 8, 0.72);
}
.modal-backdrop[hidden] {
  display: none;
}
.report-modal {
  width: min(1040px, 100%);
  max-height: min(820px, calc(100vh - 36px));
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  box-shadow: 0 18px 70px rgba(0, 0, 0, 0.55);
  overflow: hidden;
}
.report-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}
.report-head h2 {
  color: var(--text);
  font-size: 16px;
}
.report-close {
  width: 36px;
  min-height: 32px;
  font-size: 20px;
  line-height: 1;
}
.report-body {
  overflow: auto;
  padding: 16px;
}
.report-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}
.report-stat {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #11151d;
  padding: 9px 10px;
}
.report-stat-label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
}
.report-stat-value {
  margin-top: 3px;
  color: var(--text);
  font-size: 13px;
  overflow-wrap: anywhere;
}
.report-section-title {
  margin: 14px 0 8px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
.report-stage-list {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}
.report-stage {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding: 5px 0;
}
.report-stage span:last-child {
  color: var(--accent);
  font-variant-numeric: tabular-nums;
}
.report-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.report-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}
.report-table th,
.report-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}
.report-table th {
  color: var(--muted);
  font-size: 12px;
  font-weight: 650;
}
.report-table td {
  font-size: 13px;
}
.report-table tr:last-child td {
  border-bottom: 0;
}
.report-note {
  margin: 10px 0 0;
  color: var(--muted);
  font-size: 12px;
}
@media (max-width: 900px) {
  main { grid-template-columns: 1fr; }
  aside { max-height: none; border-right: 0; border-bottom: 1px solid var(--line); }
  .image-grid { grid-template-columns: 1fr; }
  .map-options { grid-template-columns: 1fr; }
  .report-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
</head>
<body>
<main>
  <aside>
    <h1>Rocky Planet Texture UI</h1>
    <section>
      <div class="row">
        <label for="preset">Preset</label>
        <select id="preset"></select>
      </div>
      <div class="row">
        <label for="landPalette">Land palette</label>
        <select id="landPalette"></select>
      </div>
      <div class="row">
        <label for="seed">Seed</label>
        <input id="seed" type="number" min="0" step="1" value="42">
      </div>
      <div class="row">
        <label for="previewWidth">Preview width</label>
        <select id="previewWidth">
          <option>384</option>
          <option selected>512</option>
          <option>768</option>
          <option>1024</option>
        </select>
      </div>
    </section>
    <nav class="control-tabs" aria-label="Control sections">
      <button class="tab-button active" type="button" data-tab="terrainTab">Terrain</button>
      <button class="tab-button" type="button" data-tab="colorTab">Color</button>
      <button class="tab-button" type="button" data-tab="effectsTab">Effects</button>
      <button class="tab-button" type="button" data-tab="saveTab">Save</button>
    </nav>
    <div class="tab-panels">
      <div id="terrainTab" class="tab-panel active"></div>
      <div id="colorTab" class="tab-panel"></div>
      <div id="effectsTab" class="tab-panel"></div>
      <div id="saveTab" class="tab-panel">
    <details open>
      <summary>Save Output</summary>
      <div class="row">
        <label for="projection">Projection</label>
        <select id="projection">
          <option value="equirectangular">Equirectangular</option>
          <option value="quad_sphere">Quad-sphere faces</option>
        </select>
      </div>
      <p class="hint" id="projectionHint">Quad-sphere saves six face folders and streamed stitched *_cubemap_cross.png atlases.</p>
      <div class="map-header">
        <label>Texture maps</label>
        <div class="map-actions" aria-label="Texture map selection actions">
          <button id="selectAllMapsBtn" type="button">All</button>
          <button id="selectNoMapsBtn" type="button">None</button>
        </div>
      </div>
      <div class="map-options" id="textureMapOptions"></div>
      <p class="hint">Unchecked maps are skipped during save. Color and height are still computed for previews, but only checked maps are written.</p>
      <div class="row">
        <label for="resolutionPreset">Map size preset</label>
        <select id="resolutionPreset">
          <option value="1024x512">1024 x 512</option>
          <option value="2048x1024" selected>2048 x 1024</option>
          <option value="4096x2048">4096 x 2048</option>
          <option value="8192x4096">8192 x 4096</option>
          <option value="custom">Custom</option>
        </select>
      </div>
      <div class="row">
        <label for="width">Width</label>
        <input id="width" type="number" min="64" step="64" value="2048">
      </div>
      <div class="row">
        <label for="height">Height</label>
        <input id="height" type="number" min="32" step="32" value="1024">
      </div>
      <div class="row">
        <label for="faceSizePreset">Quad face preset</label>
        <select id="faceSizePreset">
          <option value="256">256</option>
          <option value="512">512</option>
          <option value="1024" selected>1024</option>
          <option value="2048">2048</option>
          <option value="4096">4096</option>
          <option value="custom">Custom</option>
        </select>
      </div>
      <div class="row">
        <label for="faceSize">Quad face size</label>
        <input id="faceSize" type="number" min="32" step="32" value="1024">
      </div>
      <div class="row">
        <label for="outputName">Folder name</label>
        <input id="outputName" type="text" placeholder="auto timestamp">
      </div>
      <div class="actions">
        <button id="resetBtn">Reset Preset</button>
        <button id="randomSeedBtn">Random Seed</button>
        <button id="previewBtn">Render Preview</button>
        <button id="saveConfigBtn">Save Config</button>
        <button id="saveBtn" class="primary">Save Texture Output</button>
      </div>
      <div class="saved-planets-head">
        <h3>Saved Planets</h3>
        <button id="refreshSavedBtn" type="button">Refresh</button>
      </div>
      <div class="saved-planets" id="savedPlanets">
        <p class="hint">No saved planets loaded yet.</p>
      </div>
      <div class="load-row">
        <input id="loadPath" type="text" placeholder="output/example/preset.json">
        <button id="loadBtn">Load</button>
      </div>
    </details>
      </div>
    </div>
  </aside>
  <section class="preview">
    <div class="status" id="status">Loading controls...</div>
    <div class="image-grid">
      <figure class="texture-figure">
        <div class="texture-toolbar">
          <label for="previewMapSelect">Preview map</label>
          <select id="previewMapSelect"></select>
          <label class="cloud-layer-toggle" for="textureCloudLayerToggle">
            <input id="textureCloudLayerToggle" type="checkbox" checked>
            Cloud layer
          </label>
        </div>
        <img id="colorPreview" alt="Texture map preview">
        <figcaption id="texturePreviewCaption">texture map preview</figcaption>
      </figure>
      <figure class="globe-figure">
        <div class="globe-toolbar">
          <button id="globePlayPause" type="button">Pause</button>
          <select id="globeViewMode" aria-label="Globe preview mode">
            <option value="surface_clouds" selected>Surface + clouds</option>
            <option value="surface">Surface only</option>
            <option value="cloud_mask">Cloud mask</option>
          </select>
          <label class="cloud-layer-toggle" for="globeCloudLayerToggle">
            <input id="globeCloudLayerToggle" type="checkbox" checked>
            Cloud layer
          </label>
          <label for="globeSpeed">Speed</label>
          <input id="globeSpeed" type="range" min="0.05" max="2" step="0.05" value="0.35">
          <span id="globeSpeedValue">0.35x</span>
        </div>
        <div class="globe-canvas-wrap">
          <canvas id="globeCanvas" width="560" height="560" aria-label="Interactive globe preview"></canvas>
        </div>
        <figcaption>drag to rotate globe preview</figcaption>
      </figure>
    </div>
  </section>
</main>
<div class="modal-backdrop" id="generationReportModal" hidden>
  <section class="report-modal" role="dialog" aria-modal="true" aria-labelledby="generationReportTitle">
    <header class="report-head">
      <h2 id="generationReportTitle">Generation Report</h2>
      <button class="report-close" id="generationReportClose" type="button" aria-label="Close generation report">&times;</button>
    </header>
    <div class="report-body" id="generationReportBody"></div>
  </section>
</div>
<script>
let schema = null;
let debounceTimer = null;
let inFlight = false;
let previewMaps = {};
let texturePreviewToken = 0;
let loadedPlanet = null;

const els = {
  preset: document.getElementById("preset"),
  landPalette: document.getElementById("landPalette"),
  seed: document.getElementById("seed"),
  previewWidth: document.getElementById("previewWidth"),
  resolutionPreset: document.getElementById("resolutionPreset"),
  width: document.getElementById("width"),
  height: document.getElementById("height"),
  projection: document.getElementById("projection"),
  faceSizePreset: document.getElementById("faceSizePreset"),
  faceSize: document.getElementById("faceSize"),
  outputName: document.getElementById("outputName"),
  status: document.getElementById("status"),
  colorPreview: document.getElementById("colorPreview"),
  previewMapSelect: document.getElementById("previewMapSelect"),
  texturePreviewCaption: document.getElementById("texturePreviewCaption"),
  textureCloudLayerToggle: document.getElementById("textureCloudLayerToggle"),
  globeCanvas: document.getElementById("globeCanvas"),
  globePlayPause: document.getElementById("globePlayPause"),
  globeViewMode: document.getElementById("globeViewMode"),
  globeCloudLayerToggle: document.getElementById("globeCloudLayerToggle"),
  globeSpeed: document.getElementById("globeSpeed"),
  globeSpeedValue: document.getElementById("globeSpeedValue"),
  terrainTab: document.getElementById("terrainTab"),
  colorTab: document.getElementById("colorTab"),
  effectsTab: document.getElementById("effectsTab"),
  tabButtons: Array.from(document.querySelectorAll(".tab-button")),
  textureMapOptions: document.getElementById("textureMapOptions"),
  selectAllMapsBtn: document.getElementById("selectAllMapsBtn"),
  selectNoMapsBtn: document.getElementById("selectNoMapsBtn"),
  saveConfigBtn: document.getElementById("saveConfigBtn"),
  refreshSavedBtn: document.getElementById("refreshSavedBtn"),
  savedPlanets: document.getElementById("savedPlanets"),
  loadPath: document.getElementById("loadPath"),
  generationReportModal: document.getElementById("generationReportModal"),
  generationReportClose: document.getElementById("generationReportClose"),
  generationReportBody: document.getElementById("generationReportBody"),
};

const globe = {
  ctx: els.globeCanvas.getContext("2d", {willReadFrequently: true}),
  textureCanvas: document.createElement("canvas"),
  cloudCanvas: document.createElement("canvas"),
  textureData: null,
  cloudData: null,
  textureWidth: 0,
  textureHeight: 0,
  cloudWidth: 0,
  cloudHeight: 0,
  yaw: 0,
  pitch: 0,
  playing: true,
  dragging: false,
  lastX: 0,
  lastY: 0,
  lastFrameTime: 0,
  speed: parseFloat(els.globeSpeed.value),
};
globe.textureCtx = globe.textureCanvas.getContext("2d", {willReadFrequently: true});
globe.cloudCtx = globe.cloudCanvas.getContext("2d", {willReadFrequently: true});

function syncResolutionPreset() {
  const value = `${parseInt(els.width.value, 10)}x${parseInt(els.height.value, 10)}`;
  const match = Array.from(els.resolutionPreset.options).some((option) => option.value === value);
  els.resolutionPreset.value = match ? value : "custom";
}

function applyResolutionPreset() {
  if (els.resolutionPreset.value === "custom") return;
  const [width, height] = els.resolutionPreset.value.split("x");
  els.width.value = width;
  els.height.value = height;
}

function syncFaceSizePreset() {
  const value = String(parseInt(els.faceSize.value, 10));
  const match = Array.from(els.faceSizePreset.options).some((option) => option.value === value);
  els.faceSizePreset.value = match ? value : "custom";
}

function applyFaceSizePreset() {
  if (els.faceSizePreset.value === "custom") return;
  els.faceSize.value = els.faceSizePreset.value;
}

function setStatus(text, kind = "") {
  els.status.className = `status ${kind}`;
  els.status.textContent = text;
}

function formatSeconds(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
  if (value < 0.01) return "<0.01 s";
  if (value < 60) return `${value.toFixed(2)} s`;
  const minutes = Math.floor(value / 60);
  const seconds = value - minutes * 60;
  return `${minutes}m ${seconds.toFixed(1)}s`;
}

function formatBytes(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
  const units = ["B", "KB", "MB", "GB"];
  let amount = value;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatMapName(name) {
  return String(name || "").replace(/_/g, " ");
}

function makeEl(tag, className = "", text = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function appendReportStat(container, label, value) {
  const stat = makeEl("div", "report-stat");
  stat.appendChild(makeEl("div", "report-stat-label", label));
  stat.appendChild(makeEl("div", "report-stat-value", value));
  container.appendChild(stat);
}

function summarizeMapDimensions(entry) {
  const files = entry.files || [];
  if (entry.projection === "quad_sphere") {
    const face = files[0];
    const faceText = face ? `${face.width} x ${face.height} faces` : "n/a";
    const atlas = entry.stitched_atlas;
    return atlas ? `${faceText}; atlas ${atlas.width} x ${atlas.height}` : faceText;
  }
  const file = files[0];
  return file ? `${file.width} x ${file.height}` : "n/a";
}

function summarizeMapModes(entry) {
  const modes = new Set((entry.files || []).map(file => file.mode).filter(Boolean));
  if (entry.stitched_atlas && entry.stitched_atlas.mode) modes.add(entry.stitched_atlas.mode);
  return modes.size ? Array.from(modes).join(", ") : "n/a";
}

function summarizeMapBytes(entry) {
  if (typeof entry.bytes === "number") return entry.bytes;
  return (entry.files || []).reduce((total, file) => total + (file.bytes || 0), 0);
}

function closeGenerationReport() {
  els.generationReportModal.hidden = true;
}

function showGenerationReport(report) {
  if (!report) return;
  const body = els.generationReportBody;
  body.replaceChildren();

  const summary = makeEl("div", "report-summary");
  appendReportStat(summary, "Total time", formatSeconds(report.total_seconds));
  appendReportStat(summary, "Projection", String(report.projection || "n/a").replace(/_/g, " "));
  appendReportStat(summary, "Preset / seed", `${report.preset || "n/a"} / ${report.seed ?? "n/a"}`);
  appendReportStat(summary, "Output", report.output_dir || "n/a");
  if (report.projection === "quad_sphere") {
    appendReportStat(summary, "Quad faces", `${report.face_count || 0} at ${report.face_size || "n/a"} px`);
    appendReportStat(summary, "Workers", String(report.quad_workers || "n/a"));
  } else if (report.requested_size) {
    appendReportStat(summary, "Map size", `${report.requested_size.width} x ${report.requested_size.height}`);
  }
  body.appendChild(summary);

  body.appendChild(makeEl("div", "report-section-title", "Save stages"));
  const stages = makeEl("div", "report-stage-list");
  for (const stage of report.stages || []) {
    const row = makeEl("div", "report-stage");
    row.appendChild(makeEl("span", "", stage.label || stage.name || "Stage"));
    row.appendChild(makeEl("span", "", formatSeconds(stage.seconds)));
    stages.appendChild(row);
  }
  body.appendChild(stages);

  body.appendChild(makeEl("div", "report-section-title", "Texture maps"));
  const tableWrap = makeEl("div", "report-table-wrap");
  const table = makeEl("table", "report-table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const label of ["Map", "Files", "Dimensions", "Mode", "Size", "Map time"]) {
    headRow.appendChild(makeEl("th", "", label));
  }
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  for (const entry of report.maps || []) {
    const row = document.createElement("tr");
    const fileCount = (entry.files || []).length + (entry.stitched_atlas ? 1 : 0);
    const timeText = typeof entry.write_seconds === "number"
      ? formatSeconds(entry.write_seconds)
      : "included in save stage";
    for (const value of [
      formatMapName(entry.name),
      String(fileCount),
      summarizeMapDimensions(entry),
      summarizeMapModes(entry),
      formatBytes(summarizeMapBytes(entry)),
      timeText,
    ]) {
      row.appendChild(makeEl("td", "", value));
    }
    tbody.appendChild(row);
  }
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  body.appendChild(tableWrap);

  const reportPath = report.output_dir ? `${report.output_dir}\\generation_report.json` : "generation_report.json";
  body.appendChild(makeEl("p", "report-note", `Saved report: ${reportPath}`));
  if (report.projection === "equirectangular") {
    body.appendChild(makeEl("p", "report-note", "Equirectangular map computation is a shared build stage; per-map time shows PNG write time."));
  }

  els.generationReportModal.hidden = false;
}

function normalizeSavedPath(path) {
  return String(path || "").replace(/\\/g, "/").replace(/^\.\//, "").toLowerCase();
}

function pathsMatch(left, right) {
  const normalizedLeft = normalizeSavedPath(left);
  const normalizedRight = normalizeSavedPath(right);
  return Boolean(normalizedLeft && normalizedRight && normalizedLeft === normalizedRight);
}

function isLoadedSavedPlanet(item) {
  if (!loadedPlanet) return false;
  return pathsMatch(item.path, loadedPlanet.listPath) || pathsMatch(item.path, loadedPlanet.path);
}

function updateSavedPlanetHighlight() {
  for (const row of els.savedPlanets.querySelectorAll(".saved-planet")) {
    const isLoaded = Boolean(loadedPlanet) && (
      pathsMatch(row.dataset.path, loadedPlanet.listPath) || pathsMatch(row.dataset.path, loadedPlanet.path)
    );
    row.classList.toggle("loaded", isLoaded);
    const loadButton = row.querySelector("button[data-load-button='1']");
    if (loadButton) {
      loadButton.textContent = isLoaded ? "Loaded" : "Load";
    }
    if (isLoaded) {
      row.setAttribute("aria-current", "true");
    } else {
      row.removeAttribute("aria-current");
    }
  }
}

function sliderId(key) {
  return `param_${key}`;
}

function valueId(key) {
  return `value_${key}`;
}

function getDefaults() {
  return schema.defaults[els.preset.value];
}

function tabForGroup(name) {
  if (["Palette Colors", "Color Variation", "Advanced Land Tints"].includes(name)) {
    return els.colorTab;
  }
  if (["Cloud Creation", "Cloud Layer", "City Lights"].includes(name)) {
    return els.effectsTab;
  }
  return els.terrainTab;
}

function applyCloudRecipe(recipeKey) {
  const recipe = schema.cloud_recipes[recipeKey];
  if (!recipe) return;
  for (const [key, value] of Object.entries(recipe.values || {})) {
    const slider = document.getElementById(sliderId(key));
    if (slider) {
      slider.value = value;
      syncValue(key);
    }
  }
  schedulePreview(0);
}

function renderControls() {
  els.preset.innerHTML = "";
  for (const preset of schema.presets) {
    const option = document.createElement("option");
    option.value = preset;
    option.textContent = preset;
    els.preset.appendChild(option);
  }
  els.preset.value = "earthlike";

  els.landPalette.innerHTML = "";
  for (const palette of schema.land_palettes) {
    const option = document.createElement("option");
    option.value = palette.key;
    option.textContent = palette.label;
    els.landPalette.appendChild(option);
  }

  els.terrainTab.innerHTML = "";
  els.colorTab.innerHTML = "";
  els.effectsTab.innerHTML = "";
  for (const group of schema.param_groups) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = group.name;
    details.appendChild(summary);

    if (group.name === "Cloud Creation" && schema.cloud_recipes) {
      const recipes = document.createElement("div");
      recipes.className = "cloud-recipes";
      for (const [key, recipe] of Object.entries(schema.cloud_recipes)) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = recipe.label;
        button.addEventListener("click", () => applyCloudRecipe(key));
        recipes.appendChild(button);
      }
      details.appendChild(recipes);
    }

    for (const param of group.params) {
      if (param.type === "select") {
        const row = document.createElement("div");
        row.className = "color-control";
        const label = document.createElement("label");
        label.htmlFor = sliderId(param.key);
        label.textContent = param.label;
        const select = document.createElement("select");
        select.id = sliderId(param.key);
        select.dataset.key = param.key;
        for (const optionData of param.options || []) {
          const option = document.createElement("option");
          option.value = optionData.key;
          option.textContent = optionData.label;
          select.appendChild(option);
        }
        select.addEventListener("change", () => schedulePreview(0));
        row.append(label, select);
        details.appendChild(row);
        continue;
      }

      if (param.type === "color") {
        const row = document.createElement("div");
        row.className = "color-control";
        const label = document.createElement("label");
        label.htmlFor = sliderId(param.key);
        label.textContent = param.label;
        const input = document.createElement("input");
        input.type = "color";
        input.id = sliderId(param.key);
        input.dataset.key = param.key;
        input.addEventListener("input", () => schedulePreview());
        row.append(label, input);
        details.appendChild(row);
        continue;
      }

      const head = document.createElement("div");
      head.className = "slider-head";
      const label = document.createElement("label");
      label.htmlFor = sliderId(param.key);
      label.textContent = param.label;
      const value = document.createElement("span");
      value.id = valueId(param.key);
      head.append(label, value);

      const slider = document.createElement("input");
      slider.type = "range";
      slider.id = sliderId(param.key);
      slider.min = param.min;
      slider.max = param.max;
      slider.step = param.step;
      slider.dataset.key = param.key;
      slider.dataset.integer = param.integer ? "1" : "0";
      slider.addEventListener("input", () => {
        syncValue(param.key);
        schedulePreview();
      });

      details.append(head, slider);
    }
    tabForGroup(group.name).appendChild(details);
  }
  applyPresetDefaults();
}

function renderTextureMapOptions() {
  els.textureMapOptions.innerHTML = "";
  els.previewMapSelect.innerHTML = "";
  for (const map of schema.texture_maps) {
    const label = document.createElement("label");
    label.className = "map-option";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = map.key;
    input.checked = true;
    input.dataset.textureMap = "1";

    const span = document.createElement("span");
    span.textContent = map.label;

    label.append(input, span);
    els.textureMapOptions.append(label);

    const option = document.createElement("option");
    option.value = map.key;
    option.textContent = map.label;
    els.previewMapSelect.appendChild(option);
  }
  els.previewMapSelect.value = "color";
}

function syncValue(key) {
  const slider = document.getElementById(sliderId(key));
  if (!slider || slider.type === "color" || slider.tagName === "SELECT") return;
  const value = document.getElementById(valueId(key));
  value.textContent = slider.dataset.integer === "1"
    ? String(parseInt(slider.value, 10))
    : Number(slider.value).toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function applyPresetDefaults() {
  const defaults = getDefaults();
  for (const key of Object.keys(defaults)) {
    const slider = document.getElementById(sliderId(key));
    if (slider) {
      slider.value = defaults[key];
      syncValue(key);
    }
  }
  els.landPalette.value = defaults.land_palette || "natural_earth";
  els.outputName.value = "";
  schedulePreview(0);
}

function applyLandPaletteColors() {
  const colors = schema.land_palette_colors[els.landPalette.value] || {};
  for (const [key, value] of Object.entries(colors)) {
    const slider = document.getElementById(sliderId(key));
    if (slider) {
      slider.value = value;
      syncValue(key);
    }
  }
  schedulePreview(0);
}

function getParams() {
  const params = {};
  for (const group of schema.param_groups) {
    for (const param of group.params) {
      const slider = document.getElementById(sliderId(param.key));
      params[param.key] = (param.type === "color" || param.type === "select")
        ? slider.value
        : (param.integer ? parseInt(slider.value, 10) : parseFloat(slider.value));
    }
  }
  params.land_palette = els.landPalette.value;
  return params;
}

function getSelectedTextureMaps() {
  return Array.from(els.textureMapOptions.querySelectorAll("input[data-texture-map='1']:checked"))
    .map(input => input.value);
}

function setTextureMapSelection(checked) {
  const selected = Array.isArray(checked) ? new Set(checked) : null;
  for (const input of els.textureMapOptions.querySelectorAll("input[data-texture-map='1']")) {
    input.checked = selected ? selected.has(input.value) : checked;
  }
}

function cloudOverlayEnabled() {
  return Boolean(els.textureCloudLayerToggle && els.textureCloudLayerToggle.checked);
}

function syncCloudLayerToggles(checked) {
  els.textureCloudLayerToggle.checked = checked;
  els.globeCloudLayerToggle.checked = checked;
  setTexturePreviewMap(els.previewMapSelect.value);
  drawGlobe();
}

function loadPreviewImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Unable to load preview image."));
    image.src = src;
  });
}

async function cloudOverlayDataUrl(surfaceSrc, cloudSrc) {
  const [surfaceImage, cloudImage] = await Promise.all([
    loadPreviewImage(surfaceSrc),
    loadPreviewImage(cloudSrc),
  ]);
  const canvas = document.createElement("canvas");
  canvas.width = surfaceImage.naturalWidth;
  canvas.height = surfaceImage.naturalHeight;
  const ctx = canvas.getContext("2d", {willReadFrequently: true});
  ctx.drawImage(surfaceImage, 0, 0);
  const surface = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const cloudCanvas = document.createElement("canvas");
  cloudCanvas.width = canvas.width;
  cloudCanvas.height = canvas.height;
  const cloudCtx = cloudCanvas.getContext("2d", {willReadFrequently: true});
  cloudCtx.drawImage(cloudImage, 0, 0, canvas.width, canvas.height);
  const cloud = cloudCtx.getImageData(0, 0, canvas.width, canvas.height);

  for (let i = 0; i < surface.data.length; i += 4) {
    const alpha = Math.min(0.92, cloud.data[i] / 255);
    if (alpha <= 0) continue;
    surface.data[i] = surface.data[i] * (1 - alpha) + 248 * alpha;
    surface.data[i + 1] = surface.data[i + 1] * (1 - alpha) + 250 * alpha;
    surface.data[i + 2] = surface.data[i + 2] * (1 - alpha) + 246 * alpha;
  }

  ctx.putImageData(surface, 0, 0);
  return canvas.toDataURL("image/png");
}

async function setTexturePreviewMap(key) {
  const token = ++texturePreviewToken;
  const map = previewMaps[key];
  if (!map) {
    els.colorPreview.removeAttribute("src");
    els.texturePreviewCaption.textContent = "render a preview to inspect texture maps";
    return;
  }
  const shouldCompositeClouds = key === "color" && cloudOverlayEnabled() && previewMaps.cloud_mask;
  if (shouldCompositeClouds) {
    els.texturePreviewCaption.textContent = "color texture map preview with cloud layer";
    try {
      const image = await cloudOverlayDataUrl(map.image, previewMaps.cloud_mask.image);
      if (token !== texturePreviewToken) return;
      els.colorPreview.src = image;
      els.colorPreview.alt = "Color texture map preview with cloud layer";
    } catch (_error) {
      if (token !== texturePreviewToken) return;
      els.colorPreview.src = map.image;
      els.colorPreview.alt = `${map.label} texture map preview`;
      els.texturePreviewCaption.textContent = "color texture map preview; cloud layer unavailable";
    }
    return;
  }
  els.colorPreview.src = map.image;
  els.colorPreview.alt = `${map.label} texture map preview`;
  els.texturePreviewCaption.textContent = key === "color" && previewMaps.cloud_mask
    ? `${map.label.toLowerCase()} texture map preview; cloud layer off`
    : `${map.label.toLowerCase()} texture map preview`;
}

function setPreviewMaps(maps) {
  previewMaps = maps || {};
  if (!previewMaps[els.previewMapSelect.value]) {
    els.previewMapSelect.value = previewMaps.color ? "color" : Object.keys(previewMaps)[0] || "color";
  }
  setTexturePreviewMap(els.previewMapSelect.value);
}

function getPayload() {
  return {
    preset: els.preset.value,
    seed: parseInt(els.seed.value, 10) || 0,
    preview_width: parseInt(els.previewWidth.value, 10),
    width: parseInt(els.width.value, 10),
    height: parseInt(els.height.value, 10),
    projection: els.projection.value,
    face_size: parseInt(els.faceSize.value, 10),
    output_name: els.outputName.value,
    texture_maps: getSelectedTextureMaps(),
    params: getParams(),
  };
}

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || data.error) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

async function getJson(path) {
  const response = await fetch(path);
  const data = await response.json();
  if (!response.ok || data.error) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

function setGlobeTextures(surfaceSrc, cloudSrc) {
  let remaining = cloudSrc ? 2 : 1;
  const finish = () => {
    remaining -= 1;
    if (remaining <= 0) drawGlobe();
  };
  const image = new Image();
  image.onload = () => {
    globe.textureWidth = image.naturalWidth;
    globe.textureHeight = image.naturalHeight;
    globe.textureCanvas.width = globe.textureWidth;
    globe.textureCanvas.height = globe.textureHeight;
    globe.textureCtx.clearRect(0, 0, globe.textureWidth, globe.textureHeight);
    globe.textureCtx.drawImage(image, 0, 0);
    globe.textureData = globe.textureCtx.getImageData(0, 0, globe.textureWidth, globe.textureHeight).data;
    finish();
  };
  image.src = surfaceSrc;

  if (!cloudSrc) {
    globe.cloudData = null;
    globe.cloudWidth = 0;
    globe.cloudHeight = 0;
    return;
  }

  const cloudImage = new Image();
  cloudImage.onload = () => {
    globe.cloudWidth = cloudImage.naturalWidth;
    globe.cloudHeight = cloudImage.naturalHeight;
    globe.cloudCanvas.width = globe.cloudWidth;
    globe.cloudCanvas.height = globe.cloudHeight;
    globe.cloudCtx.clearRect(0, 0, globe.cloudWidth, globe.cloudHeight);
    globe.cloudCtx.drawImage(cloudImage, 0, 0);
    globe.cloudData = globe.cloudCtx.getImageData(0, 0, globe.cloudWidth, globe.cloudHeight).data;
    finish();
  };
  cloudImage.src = cloudSrc;
}

function syncGlobeSpeed() {
  globe.speed = parseFloat(els.globeSpeed.value);
  els.globeSpeedValue.textContent = `${globe.speed.toFixed(2).replace(/0$/, "").replace(/\.$/, "")}x`;
}

function setGlobePlaying(playing) {
  globe.playing = playing;
  els.globePlayPause.textContent = playing ? "Pause" : "Play";
}

function activateTab(tabId) {
  for (const button of els.tabButtons) {
    const active = button.dataset.tab === tabId;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  }
  for (const panel of document.querySelectorAll(".tab-panel")) {
    panel.classList.toggle("active", panel.id === tabId);
  }
}

function bindTabs() {
  for (const button of els.tabButtons) {
    button.addEventListener("click", () => activateTab(button.dataset.tab));
  }
}

function sizeGlobeCanvas() {
  const rect = els.globeCanvas.getBoundingClientRect();
  const displaySize = Math.max(240, Math.round(Math.min(rect.width || 560, 560)));
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
  const size = Math.round(displaySize * dpr);
  if (els.globeCanvas.width !== size || els.globeCanvas.height !== size) {
    els.globeCanvas.width = size;
    els.globeCanvas.height = size;
  }
  return size;
}

function drawGlobe() {
  const size = sizeGlobeCanvas();
  const ctx = globe.ctx;
  ctx.clearRect(0, 0, size, size);

  if (!globe.textureData) {
    ctx.fillStyle = "#050608";
    ctx.fillRect(0, 0, size, size);
    ctx.fillStyle = "#a9b0ba";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = `${Math.max(12, Math.round(size / 34))}px system-ui, sans-serif`;
    ctx.fillText("Render a preview", size / 2, size / 2);
    return;
  }

  const image = ctx.createImageData(size, size);
  const data = image.data;
  const radius = size * 0.46;
  const center = size / 2;
  const yaw = globe.yaw;
  const pitch = globe.pitch;
  const cosYaw = Math.cos(yaw);
  const sinYaw = Math.sin(yaw);
  const cosPitch = Math.cos(pitch);
  const sinPitch = Math.sin(pitch);
  const light = [-0.45, 0.35, 0.82];
  const lightLen = Math.hypot(light[0], light[1], light[2]);
  light[0] /= lightLen;
  light[1] /= lightLen;
  light[2] /= lightLen;

  for (let py = 0; py < size; py += 1) {
    const sy = (center - py) / radius;
    for (let px = 0; px < size; px += 1) {
      const sx = (px - center) / radius;
      const r2 = sx * sx + sy * sy;
      const i = (py * size + px) * 4;
      if (r2 > 1) {
        data[i + 3] = 0;
        continue;
      }

      const sz = Math.sqrt(1 - r2);
      const py1 = sy * cosPitch - sz * sinPitch;
      const pz1 = sy * sinPitch + sz * cosPitch;
      const x = sx * cosYaw + pz1 * sinYaw;
      const y = py1;
      const z = -sx * sinYaw + pz1 * cosYaw;
      const lon = Math.atan2(x, z);
      const lat = Math.asin(Math.max(-1, Math.min(1, y)));
      let u = Math.floor(((lon + Math.PI) / (Math.PI * 2)) * globe.textureWidth) % globe.textureWidth;
      if (u < 0) u += globe.textureWidth;
      const v = Math.max(0, Math.min(globe.textureHeight - 1, Math.floor(((Math.PI / 2 - lat) / Math.PI) * globe.textureHeight)));
      const ti = (v * globe.textureWidth + u) * 4;
      let cloudValue = 0;
      if (globe.cloudData) {
        const cu = Math.max(0, Math.min(globe.cloudWidth - 1, Math.floor((u / globe.textureWidth) * globe.cloudWidth)));
        const cv = Math.max(0, Math.min(globe.cloudHeight - 1, Math.floor((v / globe.textureHeight) * globe.cloudHeight)));
        cloudValue = globe.cloudData[(cv * globe.cloudWidth + cu) * 4] / 255;
      }

      const shade = 0.18 + Math.max(0, sx * light[0] + sy * light[1] + sz * light[2]) * 0.95;
      const rim = Math.max(0, Math.min(1, (1 - sz) * 1.4));
      const atmosphere = [72, 122, 176];
      const edgeAlpha = 1 - Math.max(0, Math.min(1, (r2 - 0.88) / 0.12));
      const blend = rim * 0.18;
      let red = (globe.textureData[ti] * (1 - blend)) + atmosphere[0] * blend;
      let green = (globe.textureData[ti + 1] * (1 - blend)) + atmosphere[1] * blend;
      let blue = (globe.textureData[ti + 2] * (1 - blend)) + atmosphere[2] * blend;
      if (els.globeViewMode.value === "cloud_mask") {
        red = green = blue = 28 + cloudValue * 227;
      } else if (els.globeViewMode.value === "surface_clouds" && cloudOverlayEnabled() && cloudValue > 0) {
        const cloudAlpha = Math.min(0.92, cloudValue);
        const cloudShade = 0.70 + Math.max(0, sx * light[0] + sy * light[1] + sz * light[2]) * 0.38;
        red = red * (1 - cloudAlpha) + 248 * cloudShade * cloudAlpha;
        green = green * (1 - cloudAlpha) + 250 * cloudShade * cloudAlpha;
        blue = blue * (1 - cloudAlpha) + 246 * cloudShade * cloudAlpha;
      }
      data[i] = Math.min(255, red * shade);
      data[i + 1] = Math.min(255, green * shade);
      data[i + 2] = Math.min(255, blue * shade);
      data[i + 3] = Math.round(255 * edgeAlpha);
    }
  }
  ctx.putImageData(image, 0, 0);
}

function animateGlobe(timestamp) {
  const elapsed = globe.lastFrameTime ? Math.min(0.08, (timestamp - globe.lastFrameTime) / 1000) : 0;
  globe.lastFrameTime = timestamp;
  if (globe.playing && !globe.dragging && globe.textureData) {
    globe.yaw = (globe.yaw + elapsed * globe.speed * 0.45) % (Math.PI * 2);
    drawGlobe();
  }
  requestAnimationFrame(animateGlobe);
}

function bindGlobeControls() {
  syncGlobeSpeed();
  els.globePlayPause.addEventListener("click", () => setGlobePlaying(!globe.playing));
  els.globeViewMode.addEventListener("change", drawGlobe);
  els.textureCloudLayerToggle.addEventListener("change", () => syncCloudLayerToggles(els.textureCloudLayerToggle.checked));
  els.globeCloudLayerToggle.addEventListener("change", () => syncCloudLayerToggles(els.globeCloudLayerToggle.checked));
  els.globeSpeed.addEventListener("input", syncGlobeSpeed);
  els.globeCanvas.addEventListener("pointerdown", (event) => {
    setGlobePlaying(false);
    globe.dragging = true;
    globe.lastX = event.clientX;
    globe.lastY = event.clientY;
    els.globeCanvas.classList.add("dragging");
    els.globeCanvas.setPointerCapture(event.pointerId);
  });
  els.globeCanvas.addEventListener("pointermove", (event) => {
    if (!globe.dragging) return;
    const dx = event.clientX - globe.lastX;
    const dy = event.clientY - globe.lastY;
    globe.lastX = event.clientX;
    globe.lastY = event.clientY;
    globe.yaw = (globe.yaw + dx * 0.008) % (Math.PI * 2);
    globe.pitch = Math.max(-1.25, Math.min(1.25, globe.pitch + dy * 0.008));
    drawGlobe();
  });
  const endDrag = (event) => {
    if (!globe.dragging) return;
    globe.dragging = false;
    els.globeCanvas.classList.remove("dragging");
    if (els.globeCanvas.hasPointerCapture(event.pointerId)) {
      els.globeCanvas.releasePointerCapture(event.pointerId);
    }
  };
  els.globeCanvas.addEventListener("pointerup", endDrag);
  els.globeCanvas.addEventListener("pointercancel", endDrag);
  window.addEventListener("resize", drawGlobe);
  requestAnimationFrame(animateGlobe);
}

function schedulePreview(delay = 350) {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(renderPreview, delay);
}

async function renderPreview() {
  if (inFlight) {
    schedulePreview(500);
    return;
  }
  inFlight = true;
  setButtons(true);
  setStatus("Rendering preview...", "busy");
  try {
    const data = await postJson("/api/preview", getPayload());
    setPreviewMaps(data.maps || {color: {label: "Color", image: data.color}});
    const surfaceImage = data.maps && data.maps.color ? data.maps.color.image : data.color;
    const cloudImage = data.maps && data.maps.cloud_mask ? data.maps.cloud_mask.image : null;
    setGlobeTextures(surfaceImage, cloudImage);
    const loadedText = loadedPlanet ? `${loadedPlanet.name} - ` : "";
    setStatus(`Preview ready: ${loadedText}${data.summary.preset}, seed ${data.summary.seed}, ${data.summary.preview_size}`, "ok");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    inFlight = false;
    setButtons(false);
  }
}

function setButtons(disabled) {
  for (const id of ["previewBtn", "saveBtn", "saveConfigBtn", "resetBtn", "randomSeedBtn", "loadBtn", "refreshSavedBtn"]) {
    document.getElementById(id).disabled = disabled;
  }
}

async function refreshSavedPlanets(showStatus = false) {
  try {
    const data = await getJson("/api/config/list");
    renderSavedPlanets(data.items || []);
    if (showStatus) {
      setStatus(`Found ${data.items.length} saved planet${data.items.length === 1 ? "" : "s"}.`, "ok");
    }
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function renderSavedPlanets(items) {
  els.savedPlanets.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "No saved planets found in output/.";
    els.savedPlanets.appendChild(empty);
    return;
  }
  for (const item of items.slice(0, 24)) {
    const row = document.createElement("div");
    row.className = "saved-planet";
    row.dataset.path = item.path;
    if (isLoadedSavedPlanet(item)) {
      row.classList.add("loaded");
      row.setAttribute("aria-current", "true");
    }

    const text = document.createElement("div");
    const title = document.createElement("div");
    title.className = "saved-planet-title";
    title.textContent = item.name;
    const meta = document.createElement("div");
    meta.className = "saved-planet-meta";
    const date = new Date((item.modified || 0) * 1000);
    const maps = Array.isArray(item.texture_maps) ? item.texture_maps.length : 0;
    const loadedText = isLoadedSavedPlanet(item) ? "Currently loaded - " : "";
    meta.textContent = `${loadedText}${item.kind === "config" ? "Config" : "Output"} - ${item.preset}, seed ${item.seed} - ${item.projection} - ${maps} maps - ${date.toLocaleString()}`;
    text.append(title, meta);

    const actions = document.createElement("div");
    actions.className = "saved-planet-actions";

    const loadButton = document.createElement("button");
    loadButton.type = "button";
    loadButton.dataset.loadButton = "1";
    loadButton.textContent = isLoadedSavedPlanet(item) ? "Loaded" : "Load";
    loadButton.addEventListener("click", () => loadSavedPlanet(item.path));

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "danger";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", () => deleteSavedPlanet(item));
    actions.append(loadButton, deleteButton);

    row.append(text, actions);
    els.savedPlanets.appendChild(row);
  }
}

function setLoadedPlanetFromData(data) {
  if (!data || !data.path) {
    loadedPlanet = null;
    updateSavedPlanetHighlight();
    return;
  }
  const sourcePath = data.list_path || data.path;
  const parts = String(sourcePath || "").replace(/\\/g, "/").split("/");
  loadedPlanet = {
    path: data.path,
    listPath: data.list_path || data.path,
    name: data.folder_name || parts[Math.max(0, parts.length - 2)] || "loaded planet",
  };
  updateSavedPlanetHighlight();
}

function clearLoadedPlanetIfPath(path) {
  if (!loadedPlanet) return;
  if (pathsMatch(path, loadedPlanet.listPath) || pathsMatch(path, loadedPlanet.path)) {
    loadedPlanet = null;
    updateSavedPlanetHighlight();
  }
}

async function saveOutput() {
  const selectedMaps = getSelectedTextureMaps();
  if (!selectedMaps.length) {
    setStatus("Choose at least one texture map to save.", "error");
    return;
  }
  setButtons(true);
  setStatus(`Saving ${selectedMaps.length} texture map${selectedMaps.length === 1 ? "" : "s"}...`, "busy");
  try {
    const data = await postJson("/api/save", getPayload());
    const stitched = data.stitched_quad_sphere_maps || [];
    const generated = data.generated_maps || [];
    const generatedText = generated.length ? ` Maps: ${generated.join(", ")}` : "";
    if (stitched.length) {
      setStatus(`Saved quad-sphere output: ${data.output_dir}. Stitched atlases: ${stitched.join(", ")}.${generatedText}`, "ok");
    } else {
      setStatus(`Saved texture output: ${data.output_dir}.${generatedText}`, "ok");
    }
    showGenerationReport(data.generation_report);
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setButtons(false);
  }
}

async function saveConfigOnly() {
  setButtons(true);
  setStatus("Saving planet configuration...", "busy");
  try {
    const data = await postJson("/api/config/save", getPayload());
    setStatus(`Saved planet configuration: ${data.preset_path}.`, "ok");
    await refreshSavedPlanets(false);
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setButtons(false);
  }
}

async function deleteSavedPlanet(item) {
  const ok = window.confirm(`Delete "${item.name}" from disk? This removes its saved folder and cannot be undone.`);
  if (!ok) return;
  setButtons(true);
  setStatus(`Deleting ${item.name}...`, "busy");
  try {
    const data = await postJson("/api/config/delete", {path: item.path});
    clearLoadedPlanetIfPath(item.path);
    renderSavedPlanets(data.items || []);
    setStatus(`Deleted saved planet: ${item.name}.`, "ok");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setButtons(false);
  }
}

function applyLoadedState(data) {
  els.preset.value = data.preset;
  els.seed.value = data.seed;
  els.previewWidth.value = data.preview_width || "512";
  els.width.value = data.width;
  els.height.value = data.height;
  els.projection.value = data.projection === "quad_sphere" ? "quad_sphere" : "equirectangular";
  els.faceSize.value = data.face_size;
  els.outputName.value = "";
  if (data.params.land_palette) {
    els.landPalette.value = data.params.land_palette;
  }
  syncResolutionPreset();
  syncFaceSizePreset();
  setTextureMapSelection(data.texture_maps || []);
  for (const [key, value] of Object.entries(data.params || {})) {
    const slider = document.getElementById(sliderId(key));
    if (slider) {
      slider.value = value;
      syncValue(key);
    }
  }
}

async function loadSavedPlanet(path) {
  setButtons(true);
  setStatus("Loading saved planet...", "busy");
  try {
    const data = await postJson("/api/load", {path});
    applyLoadedState(data);
    setLoadedPlanetFromData(data);
    setStatus("Loaded saved planet settings.", "ok");
    schedulePreview(0);
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setButtons(false);
  }
}

async function loadPresetJson() {
  setButtons(true);
  setStatus("Loading preset.json...", "busy");
  try {
    const data = await postJson("/api/load", {path: els.loadPath.value});
    applyLoadedState(data);
    setLoadedPlanetFromData(data);
    setStatus("Loaded settings.", "ok");
    schedulePreview(0);
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setButtons(false);
  }
}

async function boot() {
  const response = await fetch("/api/defaults");
  schema = await response.json();
  renderControls();
  renderTextureMapOptions();
  bindGlobeControls();
  bindTabs();

  els.preset.addEventListener("change", applyPresetDefaults);
  els.landPalette.addEventListener("change", applyLandPaletteColors);
  els.seed.addEventListener("change", () => schedulePreview(0));
  els.previewWidth.addEventListener("change", () => schedulePreview(0));
  els.previewMapSelect.addEventListener("change", () => setTexturePreviewMap(els.previewMapSelect.value));
  els.resolutionPreset.addEventListener("change", applyResolutionPreset);
  els.width.addEventListener("change", syncResolutionPreset);
  els.height.addEventListener("change", syncResolutionPreset);
  els.faceSizePreset.addEventListener("change", applyFaceSizePreset);
  els.faceSize.addEventListener("change", syncFaceSizePreset);
  els.selectAllMapsBtn.addEventListener("click", () => setTextureMapSelection(true));
  els.selectNoMapsBtn.addEventListener("click", () => setTextureMapSelection(false));
  document.getElementById("previewBtn").addEventListener("click", () => schedulePreview(0));
  document.getElementById("saveBtn").addEventListener("click", saveOutput);
  document.getElementById("saveConfigBtn").addEventListener("click", saveConfigOnly);
  document.getElementById("resetBtn").addEventListener("click", applyPresetDefaults);
  document.getElementById("randomSeedBtn").addEventListener("click", () => {
    els.seed.value = Math.floor(Math.random() * 1000000);
    schedulePreview(0);
  });
  document.getElementById("refreshSavedBtn").addEventListener("click", () => refreshSavedPlanets(true));
  document.getElementById("loadBtn").addEventListener("click", loadPresetJson);
  els.generationReportClose.addEventListener("click", closeGenerationReport);
  els.generationReportModal.addEventListener("click", event => {
    if (event.target === els.generationReportModal) closeGenerationReport();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !els.generationReportModal.hidden) closeGenerationReport();
  });
  refreshSavedPlanets(false);
}

boot().catch(error => setStatus(error.message, "error"));
</script>
</body>
</html>
"""


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), PlanetUiHandler)
    print(f"Rocky Planet Texture UI running at http://{HOST}:{PORT}")
    print(f"Quad-sphere worker processes: {QUAD_WORKERS}")
    print("Press Ctrl+C to stop the server.")
    server.serve_forever()


if __name__ == "__main__":
    main()
