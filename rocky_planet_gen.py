"""
Standalone rocky/ocean planet texture generator.

This app does not use Blender. It generates baked texture maps and previews:

    python rocky_planet_gen.py --preset earthlike --seed 42 --width 2048 --height 1024 --out output/earthlike

Outputs:
    color.png
    height.png
    normal.png
    roughness.png
    land_mask.png
    shoreline_mask.png
    ocean_depth.png
    cloud_mask.png
    city_lights.png
    preview.png
    preview.html
    preset.json

Quad-sphere output:
    python rocky_planet_gen.py --preset earthlike --seed 42 --quad-sphere --face-size 1024 --out output/earthlike_quad

    Writes six face folders under quad_sphere/:
        px, nx, py, ny, pz, nz

    Also writes transparent 3x4 cubemap-cross atlases under quad_sphere/,
    rotated 90 degrees clockwise from the original 4x3 layout:
        color_cubemap_cross.png, height_cubemap_cross.png, ...
"""

from __future__ import annotations

import argparse
import colorsys
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


PRESETS = {
    "earthlike": {
        "land_coverage": 0.46,
        "continent_scale": 1.55,
        "continent_detail": 7,
        "continent_roughness": 0.58,
        "continent_contrast": 0.19,
        "shoreline_complexity": 0.62,
        "shoreline_noise_scale": 18.0,
        "shoreline_detail": 5,
        "shoreline_erosion": 0.18,
        "beach_width": 0.045,
        "shelf_width": 0.14,
        "island_density": 0.38,
        "island_scale": 34.0,
        "island_threshold": 0.73,
        "island_chain_strength": 0.35,
        "island_min_continent_distance": 0.012,
        "island_max_continent_distance": 0.0,
        "island_min_area": 0.00001,
        "island_max_area": 0.006,
        "biome_scale": 8.0,
        "biome_complexity": 6,
        "desert_coverage": 0.27,
        "forest_coverage": 0.56,
        "mountain_density": 0.42,
        "mountain_scale": 16.0,
        "mountain_sharpness": 0.68,
        "mountain_height": 0.62,
        "polar_ice_size": 0.16,
        "polar_ice_scale": 2.15,
        "polar_ice_complexity": 0.62,
        "polar_ice_fragmentation": 0.42,
        "polar_ice_shelf_strength": 0.62,
        "polar_ice_solidity": 0.62,
        "snow_threshold": 0.74,
        "ocean_current_strength": 0.18,
        "land_palette": "natural_earth",
        "land_color_variation": 0.22,
        "continent_color_variation": 0.48,
        "continent_color_scale": 2.60,
        "continent_color_diversity": 0.72,
        "continent_color_blend_smoothness": 0.65,
        "ocean_base_color": "#074876",
        "ocean_flat_color_strength": 0.00,
        "ocean_shelf_color": "#44cdbc",
        "ocean_shelf_color_strength": 0.00,
        "ocean_color_variation": 0.18,
        "ocean_shallow_tint_strength": 0.38,
        "ocean_shelf_brightness": 0.00,
        "ocean_shelf_contrast": 1.00,
        "ocean_depth_tint_strength": 0.34,
        "ocean_latitude_tint_strength": 0.30,
        "ocean_productivity_strength": 0.28,
        "ocean_sediment_strength": 0.22,
        "ocean_brightness": 0.00,
        "ocean_contrast": 1.00,
        "ocean_hue_shift": 0.00,
        "ocean_saturation": 1.00,
        "ocean_colorizer_hue": 0.55,
        "ocean_colorizer_strength": 0.00,
        "land_brightness": 0.00,
        "land_contrast": 1.00,
        "mineral_tint_strength": 0.26,
        "wetland_tint_strength": 0.16,
        "iron_oxide_tint_strength": 0.12,
        "basalt_tint_strength": 0.08,
        "salt_flat_tint_strength": 0.05,
        "clay_tint_strength": 0.10,
        "cloud_coverage": 0.46,
        "cloud_scale": 1.25,
        "cloud_detail": 5,
        "cloud_roughness": 0.48,
        "cloud_softness": 0.22,
        "cloud_land_correlation": 0.55,
        "cloud_opacity": 0.78,
        "city_lights_strength": 0.72,
        "city_density": 0.46,
        "megacity_count": 14,
        "coastal_city_bias": 0.74,
        "inland_city_bias": 0.38,
        "city_sprawl": 0.42,
        "road_network_strength": 0.46,
        "light_temperature": 0.58,
    },
    "archipelago": {
        "land_coverage": 0.32,
        "continent_scale": 2.75,
        "continent_detail": 8,
        "continent_roughness": 0.66,
        "continent_contrast": 0.15,
        "shoreline_complexity": 0.86,
        "shoreline_noise_scale": 28.0,
        "shoreline_detail": 6,
        "shoreline_erosion": 0.34,
        "beach_width": 0.06,
        "shelf_width": 0.18,
        "island_density": 0.82,
        "island_scale": 48.0,
        "island_threshold": 0.64,
        "island_chain_strength": 0.74,
        "island_min_continent_distance": 0.008,
        "island_max_continent_distance": 0.0,
        "island_min_area": 0.000005,
        "island_max_area": 0.004,
        "biome_scale": 12.0,
        "biome_complexity": 7,
        "desert_coverage": 0.18,
        "forest_coverage": 0.66,
        "mountain_density": 0.34,
        "mountain_scale": 20.0,
        "mountain_sharpness": 0.55,
        "mountain_height": 0.42,
        "polar_ice_size": 0.08,
        "polar_ice_scale": 2.80,
        "polar_ice_complexity": 0.76,
        "polar_ice_fragmentation": 0.68,
        "polar_ice_shelf_strength": 0.52,
        "polar_ice_solidity": 0.56,
        "snow_threshold": 0.82,
        "ocean_current_strength": 0.24,
        "land_palette": "lush_green",
        "land_color_variation": 0.26,
        "continent_color_variation": 0.44,
        "continent_color_scale": 4.20,
        "continent_color_diversity": 0.70,
        "continent_color_blend_smoothness": 0.70,
        "ocean_base_color": "#0b6d92",
        "ocean_flat_color_strength": 0.00,
        "ocean_shelf_color": "#44cdbc",
        "ocean_shelf_color_strength": 0.00,
        "ocean_color_variation": 0.24,
        "ocean_shallow_tint_strength": 0.56,
        "ocean_shelf_brightness": 0.00,
        "ocean_shelf_contrast": 1.00,
        "ocean_depth_tint_strength": 0.26,
        "ocean_latitude_tint_strength": 0.18,
        "ocean_productivity_strength": 0.42,
        "ocean_sediment_strength": 0.34,
        "ocean_brightness": 0.04,
        "ocean_contrast": 1.08,
        "ocean_hue_shift": 0.00,
        "ocean_saturation": 1.00,
        "ocean_colorizer_hue": 0.55,
        "ocean_colorizer_strength": 0.00,
        "land_brightness": 0.00,
        "land_contrast": 1.00,
        "mineral_tint_strength": 0.18,
        "wetland_tint_strength": 0.20,
        "iron_oxide_tint_strength": 0.08,
        "basalt_tint_strength": 0.10,
        "salt_flat_tint_strength": 0.03,
        "clay_tint_strength": 0.12,
        "cloud_coverage": 0.54,
        "cloud_scale": 1.75,
        "cloud_detail": 5,
        "cloud_roughness": 0.50,
        "cloud_softness": 0.24,
        "cloud_land_correlation": 0.48,
        "cloud_opacity": 0.82,
        "city_lights_strength": 0.66,
        "city_density": 0.42,
        "megacity_count": 10,
        "coastal_city_bias": 0.88,
        "inland_city_bias": 0.24,
        "city_sprawl": 0.36,
        "road_network_strength": 0.38,
        "light_temperature": 0.60,
    },
    "supercontinent": {
        "land_coverage": 0.58,
        "continent_scale": 0.95,
        "continent_detail": 7,
        "continent_roughness": 0.52,
        "continent_contrast": 0.23,
        "shoreline_complexity": 0.48,
        "shoreline_noise_scale": 13.0,
        "shoreline_detail": 5,
        "shoreline_erosion": 0.12,
        "beach_width": 0.035,
        "shelf_width": 0.11,
        "island_density": 0.16,
        "island_scale": 26.0,
        "island_threshold": 0.80,
        "island_chain_strength": 0.22,
        "island_min_continent_distance": 0.018,
        "island_max_continent_distance": 0.0,
        "island_min_area": 0.00002,
        "island_max_area": 0.010,
        "biome_scale": 6.5,
        "biome_complexity": 6,
        "desert_coverage": 0.46,
        "forest_coverage": 0.36,
        "mountain_density": 0.55,
        "mountain_scale": 11.0,
        "mountain_sharpness": 0.78,
        "mountain_height": 0.78,
        "polar_ice_size": 0.20,
        "polar_ice_scale": 1.65,
        "polar_ice_complexity": 0.48,
        "polar_ice_fragmentation": 0.30,
        "polar_ice_shelf_strength": 0.70,
        "polar_ice_solidity": 0.74,
        "snow_threshold": 0.70,
        "ocean_current_strength": 0.12,
        "land_palette": "dry_savanna",
        "land_color_variation": 0.24,
        "continent_color_variation": 0.52,
        "continent_color_scale": 2.00,
        "continent_color_diversity": 0.80,
        "continent_color_blend_smoothness": 0.55,
        "ocean_base_color": "#063f70",
        "ocean_flat_color_strength": 0.00,
        "ocean_shelf_color": "#44cdbc",
        "ocean_shelf_color_strength": 0.00,
        "ocean_color_variation": 0.14,
        "ocean_shallow_tint_strength": 0.24,
        "ocean_shelf_brightness": 0.00,
        "ocean_shelf_contrast": 1.00,
        "ocean_depth_tint_strength": 0.32,
        "ocean_latitude_tint_strength": 0.28,
        "ocean_productivity_strength": 0.18,
        "ocean_sediment_strength": 0.30,
        "ocean_brightness": -0.03,
        "ocean_contrast": 1.10,
        "ocean_hue_shift": 0.00,
        "ocean_saturation": 1.00,
        "ocean_colorizer_hue": 0.55,
        "ocean_colorizer_strength": 0.00,
        "land_brightness": 0.00,
        "land_contrast": 1.00,
        "mineral_tint_strength": 0.28,
        "wetland_tint_strength": 0.12,
        "iron_oxide_tint_strength": 0.18,
        "basalt_tint_strength": 0.12,
        "salt_flat_tint_strength": 0.08,
        "clay_tint_strength": 0.16,
        "cloud_coverage": 0.34,
        "cloud_scale": 0.95,
        "cloud_detail": 4,
        "cloud_roughness": 0.44,
        "cloud_softness": 0.20,
        "cloud_land_correlation": 0.66,
        "cloud_opacity": 0.72,
        "city_lights_strength": 0.70,
        "city_density": 0.40,
        "megacity_count": 12,
        "coastal_city_bias": 0.36,
        "inland_city_bias": 0.72,
        "city_sprawl": 0.48,
        "road_network_strength": 0.52,
        "light_temperature": 0.55,
    },
    "dry_rocky": {
        "land_coverage": 0.68,
        "continent_scale": 1.35,
        "continent_detail": 8,
        "continent_roughness": 0.64,
        "continent_contrast": 0.20,
        "shoreline_complexity": 0.55,
        "shoreline_noise_scale": 21.0,
        "shoreline_detail": 6,
        "shoreline_erosion": 0.22,
        "beach_width": 0.025,
        "shelf_width": 0.08,
        "island_density": 0.12,
        "island_scale": 30.0,
        "island_threshold": 0.82,
        "island_chain_strength": 0.28,
        "island_min_continent_distance": 0.018,
        "island_max_continent_distance": 0.0,
        "island_min_area": 0.00002,
        "island_max_area": 0.008,
        "biome_scale": 10.0,
        "biome_complexity": 7,
        "desert_coverage": 0.72,
        "forest_coverage": 0.12,
        "mountain_density": 0.62,
        "mountain_scale": 18.0,
        "mountain_sharpness": 0.86,
        "mountain_height": 0.86,
        "polar_ice_size": 0.04,
        "polar_ice_scale": 2.40,
        "polar_ice_complexity": 0.56,
        "polar_ice_fragmentation": 0.36,
        "polar_ice_shelf_strength": 0.34,
        "polar_ice_solidity": 0.44,
        "snow_threshold": 0.88,
        "ocean_current_strength": 0.08,
        "land_palette": "red_desert",
        "land_color_variation": 0.34,
        "continent_color_variation": 0.58,
        "continent_color_scale": 2.70,
        "continent_color_diversity": 0.85,
        "continent_color_blend_smoothness": 0.42,
        "ocean_base_color": "#05315e",
        "ocean_flat_color_strength": 0.00,
        "ocean_shelf_color": "#44cdbc",
        "ocean_shelf_color_strength": 0.00,
        "ocean_color_variation": 0.08,
        "ocean_shallow_tint_strength": 0.16,
        "ocean_shelf_brightness": 0.00,
        "ocean_shelf_contrast": 1.00,
        "ocean_depth_tint_strength": 0.20,
        "ocean_latitude_tint_strength": 0.16,
        "ocean_productivity_strength": 0.08,
        "ocean_sediment_strength": 0.12,
        "ocean_brightness": -0.02,
        "ocean_contrast": 1.06,
        "ocean_hue_shift": 0.00,
        "ocean_saturation": 1.00,
        "ocean_colorizer_hue": 0.55,
        "ocean_colorizer_strength": 0.00,
        "land_brightness": 0.00,
        "land_contrast": 1.00,
        "mineral_tint_strength": 0.38,
        "wetland_tint_strength": 0.06,
        "iron_oxide_tint_strength": 0.30,
        "basalt_tint_strength": 0.18,
        "salt_flat_tint_strength": 0.14,
        "clay_tint_strength": 0.12,
        "cloud_coverage": 0.18,
        "cloud_scale": 1.15,
        "cloud_detail": 4,
        "cloud_roughness": 0.46,
        "cloud_softness": 0.16,
        "cloud_land_correlation": 0.42,
        "cloud_opacity": 0.62,
        "city_lights_strength": 0.34,
        "city_density": 0.18,
        "megacity_count": 5,
        "coastal_city_bias": 0.24,
        "inland_city_bias": 0.38,
        "city_sprawl": 0.26,
        "road_network_strength": 0.18,
        "light_temperature": 0.62,
    },
    "frozen_ocean": {
        "land_coverage": 0.28,
        "continent_scale": 1.85,
        "continent_detail": 6,
        "continent_roughness": 0.50,
        "continent_contrast": 0.18,
        "shoreline_complexity": 0.40,
        "shoreline_noise_scale": 12.0,
        "shoreline_detail": 4,
        "shoreline_erosion": 0.10,
        "beach_width": 0.02,
        "shelf_width": 0.10,
        "island_density": 0.18,
        "island_scale": 22.0,
        "island_threshold": 0.78,
        "island_chain_strength": 0.24,
        "island_min_continent_distance": 0.014,
        "island_max_continent_distance": 0.0,
        "island_min_area": 0.00002,
        "island_max_area": 0.007,
        "biome_scale": 7.0,
        "biome_complexity": 5,
        "desert_coverage": 0.10,
        "forest_coverage": 0.18,
        "mountain_density": 0.38,
        "mountain_scale": 13.0,
        "mountain_sharpness": 0.60,
        "mountain_height": 0.38,
        "polar_ice_size": 0.48,
        "polar_ice_scale": 1.30,
        "polar_ice_complexity": 0.58,
        "polar_ice_fragmentation": 0.48,
        "polar_ice_shelf_strength": 0.88,
        "polar_ice_solidity": 0.82,
        "snow_threshold": 0.48,
        "ocean_current_strength": 0.10,
        "land_palette": "cold_tundra",
        "land_color_variation": 0.16,
        "continent_color_variation": 0.34,
        "continent_color_scale": 2.10,
        "continent_color_diversity": 0.60,
        "continent_color_blend_smoothness": 0.75,
        "ocean_base_color": "#294f72",
        "ocean_flat_color_strength": 0.00,
        "ocean_shelf_color": "#44cdbc",
        "ocean_shelf_color_strength": 0.00,
        "ocean_color_variation": 0.16,
        "ocean_shallow_tint_strength": 0.18,
        "ocean_shelf_brightness": 0.00,
        "ocean_shelf_contrast": 1.00,
        "ocean_depth_tint_strength": 0.42,
        "ocean_latitude_tint_strength": 0.62,
        "ocean_productivity_strength": 0.10,
        "ocean_sediment_strength": 0.06,
        "ocean_brightness": 0.06,
        "ocean_contrast": 0.88,
        "ocean_hue_shift": 0.00,
        "ocean_saturation": 1.00,
        "ocean_colorizer_hue": 0.55,
        "ocean_colorizer_strength": 0.00,
        "land_brightness": 0.00,
        "land_contrast": 1.00,
        "mineral_tint_strength": 0.14,
        "wetland_tint_strength": 0.08,
        "iron_oxide_tint_strength": 0.05,
        "basalt_tint_strength": 0.08,
        "salt_flat_tint_strength": 0.03,
        "clay_tint_strength": 0.06,
        "cloud_coverage": 0.56,
        "cloud_scale": 1.10,
        "cloud_detail": 5,
        "cloud_roughness": 0.46,
        "cloud_softness": 0.28,
        "cloud_land_correlation": 0.60,
        "cloud_opacity": 0.82,
        "city_lights_strength": 0.30,
        "city_density": 0.16,
        "megacity_count": 4,
        "coastal_city_bias": 0.46,
        "inland_city_bias": 0.12,
        "city_sprawl": 0.20,
        "road_network_strength": 0.14,
        "light_temperature": 0.50,
    },
}


OCEAN_COLORS = {
    "deep_ocean": np.array([4, 20, 66], dtype=np.float32),
    "ocean_mid": np.array([7, 72, 118], dtype=np.float32),
    "shallow_ocean": np.array([35, 154, 166], dtype=np.float32),
}


def rgb_from_hex(value: str) -> np.ndarray:
    text = str(value).strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(channel * 2 for channel in text)
    if len(text) != 6:
        raise ValueError(f"Invalid ocean base color: {value!r}. Use #RRGGBB.")
    try:
        channels = [int(text[index : index + 2], 16) for index in range(0, 6, 2)]
    except ValueError as exc:
        raise ValueError(f"Invalid ocean base color: {value!r}. Use #RRGGBB.") from exc
    return np.array(channels, dtype=np.float32)


def ocean_colors_from_base(value: str) -> dict[str, np.ndarray]:
    base = rgb_from_hex(value)
    deep = base * 0.42 + np.array([0, 6, 34], dtype=np.float32) * 0.58
    shallow = base * 0.46 + np.array([78, 208, 198], dtype=np.float32) * 0.54
    return {
        "deep_ocean": np.clip(deep, 0.0, 255.0),
        "ocean_mid": np.clip(base, 0.0, 255.0),
        "shallow_ocean": np.clip(shallow, 0.0, 255.0),
    }


LAND_PALETTE_LABELS = {
    "natural_earth": "Natural Earth",
    "lush_green": "Lush Green",
    "dry_savanna": "Dry Savanna",
    "red_desert": "Red Desert",
    "basaltic_dark": "Basaltic Dark",
    "pale_sedimentary": "Pale Sedimentary",
    "cold_tundra": "Cold Tundra",
    "alien_mineral": "Alien Mineral",
}


LAND_PALETTE_DATA = {
    "natural_earth": {
        "colors": {
            "beach": [196, 178, 119],
            "dark_forest": [6, 54, 18],
            "forest": [18, 125, 34],
            "grass": [70, 155, 38],
            "dry_plain": [94, 76, 42],
            "desert": [128, 86, 45],
            "rock": [88, 84, 76],
            "snow": [235, 242, 238],
            "ice": [194, 228, 240],
        },
        "region_tints": [
            [158, 126, 62],
            [150, 60, 32],
            [32, 35, 36],
            [30, 92, 38],
            [194, 172, 108],
            [70, 106, 100],
        ],
        "tints": {
            "ochre": [126, 98, 50],
            "rust": [98, 50, 30],
            "dark_wet": [24, 58, 28],
            "cool_tundra": [70, 100, 70],
            "pale_highland": [118, 112, 94],
            "iron_oxide": [122, 48, 28],
            "basalt": [36, 38, 40],
            "salt_flat": [218, 210, 178],
            "clay": [146, 92, 58],
            "solid_ice": [244, 248, 248],
        },
    },
    "lush_green": {
        "colors": {
            "beach": [204, 190, 126],
            "dark_forest": [5, 46, 20],
            "forest": [16, 118, 42],
            "grass": [72, 172, 62],
            "dry_plain": [104, 120, 54],
            "desert": [148, 114, 58],
            "rock": [84, 90, 72],
            "snow": [235, 242, 236],
            "ice": [190, 226, 236],
        },
        "region_tints": [
            [126, 146, 62],
            [114, 76, 42],
            [42, 50, 44],
            [28, 104, 44],
            [176, 166, 106],
            [68, 114, 86],
        ],
        "tints": {
            "ochre": [122, 112, 52],
            "rust": [92, 54, 32],
            "dark_wet": [18, 58, 28],
            "cool_tundra": [70, 112, 78],
            "pale_highland": [126, 130, 100],
            "iron_oxide": [112, 54, 30],
            "basalt": [34, 40, 38],
            "salt_flat": [216, 210, 178],
            "clay": [132, 94, 62],
            "solid_ice": [244, 248, 248],
        },
    },
    "dry_savanna": {
        "colors": {
            "beach": [210, 190, 128],
            "dark_forest": [28, 58, 24],
            "forest": [58, 104, 38],
            "grass": [128, 152, 60],
            "dry_plain": [146, 120, 58],
            "desert": [176, 128, 64],
            "rock": [104, 94, 76],
            "snow": [236, 240, 232],
            "ice": [198, 226, 232],
        },
        "region_tints": [
            [172, 136, 68],
            [146, 82, 44],
            [56, 52, 44],
            [70, 104, 44],
            [202, 176, 112],
            [92, 106, 78],
        ],
        "tints": {
            "ochre": [150, 116, 54],
            "rust": [112, 62, 34],
            "dark_wet": [34, 66, 28],
            "cool_tundra": [92, 110, 76],
            "pale_highland": [142, 128, 96],
            "iron_oxide": [136, 58, 30],
            "basalt": [48, 44, 40],
            "salt_flat": [224, 212, 174],
            "clay": [160, 102, 58],
            "solid_ice": [244, 248, 248],
        },
    },
    "red_desert": {
        "colors": {
            "beach": [202, 170, 112],
            "dark_forest": [34, 50, 22],
            "forest": [72, 94, 34],
            "grass": [118, 118, 46],
            "dry_plain": [138, 76, 42],
            "desert": [178, 82, 44],
            "rock": [104, 76, 64],
            "snow": [236, 240, 234],
            "ice": [198, 224, 232],
        },
        "region_tints": [
            [174, 94, 46],
            [156, 48, 30],
            [48, 38, 36],
            [84, 86, 36],
            [208, 142, 84],
            [108, 86, 76],
        ],
        "tints": {
            "ochre": [154, 86, 42],
            "rust": [122, 44, 28],
            "dark_wet": [38, 54, 24],
            "cool_tundra": [96, 92, 74],
            "pale_highland": [138, 104, 88],
            "iron_oxide": [152, 42, 24],
            "basalt": [42, 36, 36],
            "salt_flat": [226, 202, 164],
            "clay": [168, 78, 48],
            "solid_ice": [244, 248, 248],
        },
    },
    "basaltic_dark": {
        "colors": {
            "beach": [158, 150, 112],
            "dark_forest": [8, 38, 28],
            "forest": [24, 84, 54],
            "grass": [70, 110, 62],
            "dry_plain": [70, 76, 58],
            "desert": [96, 84, 62],
            "rock": [52, 54, 54],
            "snow": [230, 236, 234],
            "ice": [182, 214, 224],
        },
        "region_tints": [
            [104, 94, 62],
            [94, 52, 42],
            [24, 28, 30],
            [28, 76, 58],
            [154, 146, 106],
            [68, 92, 92],
        ],
        "tints": {
            "ochre": [104, 92, 56],
            "rust": [82, 48, 38],
            "dark_wet": [14, 48, 36],
            "cool_tundra": [68, 92, 84],
            "pale_highland": [104, 106, 96],
            "iron_oxide": [104, 44, 34],
            "basalt": [22, 24, 26],
            "salt_flat": [194, 190, 166],
            "clay": [118, 76, 60],
            "solid_ice": [240, 246, 246],
        },
    },
    "pale_sedimentary": {
        "colors": {
            "beach": [222, 204, 144],
            "dark_forest": [34, 70, 32],
            "forest": [76, 126, 58],
            "grass": [136, 166, 86],
            "dry_plain": [170, 148, 92],
            "desert": [206, 168, 104],
            "rock": [138, 130, 108],
            "snow": [240, 244, 238],
            "ice": [202, 230, 236],
        },
        "region_tints": [
            [196, 164, 94],
            [148, 92, 54],
            [76, 72, 62],
            [88, 132, 70],
            [224, 202, 136],
            [112, 132, 118],
        ],
        "tints": {
            "ochre": [166, 138, 78],
            "rust": [116, 72, 46],
            "dark_wet": [44, 72, 36],
            "cool_tundra": [102, 126, 94],
            "pale_highland": [168, 160, 128],
            "iron_oxide": [132, 62, 38],
            "basalt": [70, 68, 64],
            "salt_flat": [232, 222, 188],
            "clay": [172, 116, 72],
            "solid_ice": [246, 250, 248],
        },
    },
    "cold_tundra": {
        "colors": {
            "beach": [176, 166, 124],
            "dark_forest": [18, 54, 42],
            "forest": [42, 96, 66],
            "grass": [92, 132, 88],
            "dry_plain": [100, 106, 80],
            "desert": [130, 116, 82],
            "rock": [82, 88, 86],
            "snow": [238, 244, 242],
            "ice": [186, 224, 238],
        },
        "region_tints": [
            [124, 118, 76],
            [108, 68, 48],
            [42, 48, 50],
            [44, 96, 76],
            [174, 164, 120],
            [76, 112, 112],
        ],
        "tints": {
            "ochre": [116, 106, 70],
            "rust": [88, 58, 44],
            "dark_wet": [20, 58, 48],
            "cool_tundra": [72, 112, 104],
            "pale_highland": [118, 124, 116],
            "iron_oxide": [104, 54, 40],
            "basalt": [40, 44, 46],
            "salt_flat": [210, 210, 188],
            "clay": [130, 96, 76],
            "solid_ice": [246, 250, 250],
        },
    },
    "alien_mineral": {
        "colors": {
            "beach": [188, 180, 126],
            "dark_forest": [16, 44, 56],
            "forest": [26, 104, 92],
            "grass": [90, 152, 96],
            "dry_plain": [112, 88, 118],
            "desert": [154, 96, 126],
            "rock": [78, 76, 100],
            "snow": [234, 240, 242],
            "ice": [184, 226, 238],
        },
        "region_tints": [
            [108, 150, 92],
            [142, 70, 112],
            [42, 52, 72],
            [36, 116, 104],
            [188, 170, 116],
            [82, 110, 132],
        ],
        "tints": {
            "ochre": [118, 102, 70],
            "rust": [112, 56, 82],
            "dark_wet": [18, 54, 58],
            "cool_tundra": [74, 112, 116],
            "pale_highland": [126, 118, 132],
            "iron_oxide": [132, 52, 84],
            "basalt": [34, 38, 54],
            "salt_flat": [218, 214, 184],
            "clay": [148, 86, 112],
            "solid_ice": [244, 248, 250],
        },
    },
}


LAND_PALETTES = {
    name: {
        "colors": {
            key: np.array(value, dtype=np.float32)
            for key, value in palette["colors"].items()
        },
        "region_tints": np.array(palette["region_tints"], dtype=np.float32),
        "tints": {
            key: np.array(value, dtype=np.float32)
            for key, value in palette["tints"].items()
        },
    }
    for name, palette in LAND_PALETTE_DATA.items()
}


COLORS = {**OCEAN_COLORS, **LAND_PALETTES["natural_earth"]["colors"]}


def normalize_land_palette(name):
    key = str(name or "natural_earth")
    if key not in LAND_PALETTES:
        choices = ", ".join(sorted(LAND_PALETTES))
        raise ValueError(f"Unknown land palette: {key}. Choices: {choices}")
    return key


def land_palette_values(name):
    return LAND_PALETTES[normalize_land_palette(name)]


def source_colors_for_land_palette(name):
    palette = land_palette_values(name)
    return {**OCEAN_COLORS, **palette["colors"]}


def vary_palette(seed, preset, land_palette="natural_earth"):
    land_palette = normalize_land_palette(land_palette)
    rng = np.random.default_rng(seed * 1009 + sum(ord(c) for c in preset))
    global_hue = rng.uniform(-0.035, 0.035)
    global_sat = rng.uniform(0.88, 1.18)
    global_val = rng.uniform(0.90, 1.10)
    source_colors = source_colors_for_land_palette(land_palette)
    category_hue = {
        "deep_ocean": rng.uniform(-0.045, 0.045),
        "ocean_mid": rng.uniform(-0.045, 0.045),
        "shallow_ocean": rng.uniform(-0.055, 0.055),
        "beach": rng.uniform(-0.035, 0.035),
        "dark_forest": rng.uniform(-0.030, 0.030),
        "forest": rng.uniform(-0.030, 0.030),
        "grass": rng.uniform(-0.040, 0.040),
        "dry_plain": rng.uniform(-0.045, 0.045),
        "desert": rng.uniform(-0.050, 0.050),
        "rock": rng.uniform(-0.025, 0.025),
        "snow": rng.uniform(-0.012, 0.012),
        "ice": rng.uniform(-0.025, 0.025),
    }
    category_sat = {
        "deep_ocean": rng.uniform(0.90, 1.22),
        "ocean_mid": rng.uniform(0.90, 1.22),
        "shallow_ocean": rng.uniform(0.88, 1.25),
        "beach": rng.uniform(0.82, 1.18),
        "dark_forest": rng.uniform(0.82, 1.20),
        "forest": rng.uniform(0.82, 1.20),
        "grass": rng.uniform(0.82, 1.18),
        "dry_plain": rng.uniform(0.78, 1.18),
        "desert": rng.uniform(0.82, 1.24),
        "rock": rng.uniform(0.72, 1.12),
        "snow": rng.uniform(0.82, 1.04),
        "ice": rng.uniform(0.86, 1.12),
    }
    category_val = {
        "deep_ocean": rng.uniform(0.82, 1.12),
        "ocean_mid": rng.uniform(0.86, 1.14),
        "shallow_ocean": rng.uniform(0.88, 1.18),
        "beach": rng.uniform(0.86, 1.15),
        "dark_forest": rng.uniform(0.78, 1.12),
        "forest": rng.uniform(0.82, 1.14),
        "grass": rng.uniform(0.82, 1.15),
        "dry_plain": rng.uniform(0.84, 1.16),
        "desert": rng.uniform(0.86, 1.18),
        "rock": rng.uniform(0.78, 1.16),
        "snow": rng.uniform(0.92, 1.08),
        "ice": rng.uniform(0.90, 1.12),
    }

    palette = {}
    for name, rgb in source_colors.items():
        r, g, b = (rgb / 255.0).tolist()
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        h = (h + global_hue + category_hue[name]) % 1.0
        s = np.clip(s * global_sat * category_sat[name], 0.0, 1.0)
        v = np.clip(v * global_val * category_val[name], 0.0, 1.0)
        varied = colorsys.hsv_to_rgb(h, s, v)
        palette[name] = np.array(varied, dtype=np.float32) * 255.0
    return palette


@dataclass
class PlanetConfig:
    preset: str
    seed: int
    width: int
    height: int
    land_coverage: float
    continent_scale: float
    continent_detail: int
    continent_roughness: float
    continent_contrast: float
    shoreline_complexity: float
    shoreline_noise_scale: float
    shoreline_detail: int
    shoreline_erosion: float
    beach_width: float
    shelf_width: float
    island_density: float
    island_scale: float
    island_threshold: float
    island_chain_strength: float
    island_min_continent_distance: float
    island_max_continent_distance: float
    island_min_area: float
    island_max_area: float
    biome_scale: float
    biome_complexity: int
    desert_coverage: float
    forest_coverage: float
    mountain_density: float
    mountain_scale: float
    mountain_sharpness: float
    mountain_height: float
    polar_ice_size: float
    polar_ice_scale: float
    polar_ice_complexity: float
    polar_ice_fragmentation: float
    polar_ice_shelf_strength: float
    polar_ice_solidity: float
    snow_threshold: float
    ocean_current_strength: float
    land_palette: str
    land_color_variation: float
    continent_color_variation: float
    continent_color_scale: float
    continent_color_diversity: float
    continent_color_blend_smoothness: float
    ocean_base_color: str
    ocean_flat_color_strength: float
    ocean_shelf_color: str
    ocean_shelf_color_strength: float
    ocean_color_variation: float
    ocean_shallow_tint_strength: float
    ocean_shelf_brightness: float
    ocean_shelf_contrast: float
    ocean_depth_tint_strength: float
    ocean_latitude_tint_strength: float
    ocean_productivity_strength: float
    ocean_sediment_strength: float
    ocean_brightness: float
    ocean_contrast: float
    ocean_hue_shift: float
    ocean_saturation: float
    ocean_colorizer_hue: float
    ocean_colorizer_strength: float
    land_brightness: float
    land_contrast: float
    mineral_tint_strength: float
    wetland_tint_strength: float
    iron_oxide_tint_strength: float
    basalt_tint_strength: float
    salt_flat_tint_strength: float
    clay_tint_strength: float
    cloud_coverage: float
    cloud_scale: float
    cloud_detail: int
    cloud_roughness: float
    cloud_softness: float
    cloud_land_correlation: float
    cloud_opacity: float
    city_lights_strength: float
    city_density: float
    megacity_count: int
    coastal_city_bias: float
    inland_city_bias: float
    city_sprawl: float
    road_network_strength: float
    light_temperature: float


def smoothstep(edge0, edge1, x):
    x = np.clip((x - edge0) / max(edge1 - edge0, 1e-6), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def lerp(a, b, t):
    return a * (1.0 - t) + b * t


def normalize01(a, value_range=None):
    if value_range is None:
        amin = float(np.min(a))
        amax = float(np.max(a))
    else:
        amin, amax = value_range
    if amax - amin < 1e-9:
        return np.zeros_like(a)
    return (a - amin) / (amax - amin)


def build_cloud_field(cfg, x, y, z, lat, land_field, land_threshold):
    land_correlation = float(np.clip(cfg.cloud_land_correlation, 0.0, 1.0))
    scale = max(0.20, float(cfg.cloud_scale))
    detail = max(1, int(cfg.cloud_detail))
    roughness = float(np.clip(cfg.cloud_roughness, 0.10, 0.95))

    broad = fbm_3d(x, y, z, scale, detail, roughness, cfg.seed + 9011)
    weather = fbm_3d(x, y, z, scale * 3.4 + 1.0, max(2, min(6, detail + 1)), 0.56, cfg.seed + 9029)
    wisps = fbm_3d(x, y, z, scale * 8.5 + 3.0, 3, 0.58, cfg.seed + 9043)

    land_width = max(float(cfg.continent_contrast) * 3.5, 0.12)
    soft_land_form = smoothstep(land_threshold - land_width, land_threshold + land_width, land_field)
    lat_band = 1.0 - np.abs(np.sin(lat)) * 0.30

    field = broad * 0.58 + weather * 0.28 + wisps * 0.14
    field = lerp(field, field * 0.55 + soft_land_form * 0.45, land_correlation)
    field = field * (0.86 + lat_band * 0.14)
    return field.astype(np.float32)


def cloud_mask_from_field(cfg, cloud_field, cloud_threshold):
    coverage = float(np.clip(cfg.cloud_coverage, 0.0, 1.0))
    opacity = float(np.clip(cfg.cloud_opacity, 0.0, 1.0))
    if coverage <= 0.0 or opacity <= 0.0:
        return np.zeros_like(cloud_field, dtype=np.float32)
    if coverage >= 1.0:
        return np.full_like(cloud_field, opacity, dtype=np.float32)

    softness = max(0.005, float(cfg.cloud_softness))
    mask = smoothstep(cloud_threshold - softness, cloud_threshold + softness, cloud_field)
    texture = 0.72 + normalize01(cloud_field) * 0.28
    return np.clip(mask * texture * opacity, 0.0, 1.0).astype(np.float32)


def build_city_lights_map(
    cfg,
    x,
    y,
    z,
    lat,
    land,
    shoreline,
    moisture,
    mountain_mask,
    polar_ice,
):
    strength = float(np.clip(cfg.city_lights_strength, 0.0, 1.0))
    density = float(np.clip(cfg.city_density, 0.0, 1.0))
    if strength <= 0.0 or density <= 0.0:
        return np.zeros((*x.shape, 3), dtype=np.float32)

    coastal_bias = float(np.clip(cfg.coastal_city_bias, 0.0, 1.0))
    inland_bias = float(np.clip(cfg.inland_city_bias, 0.0, 1.0))
    sprawl = float(np.clip(cfg.city_sprawl, 0.0, 1.0))
    road_strength = float(np.clip(cfg.road_network_strength, 0.0, 1.0))
    temperature = float(np.clip(cfg.light_temperature, 0.0, 1.0))

    cold_lat = smoothstep(0.70, 0.96, np.abs(np.sin(lat)))
    low_relief = 1.0 - smoothstep(0.18, 0.82, mountain_mask)
    temperate = 1.0 - cold_lat * 0.72
    not_ice = 1.0 - np.clip(polar_ice, 0.0, 1.0)
    wet_lowland = np.clip(moisture * 0.55 + low_relief * 0.45, 0.0, 1.0)
    coastal = np.clip(shoreline, 0.0, 1.0)
    inland_development = np.clip((1.0 - coastal * 0.65) * wet_lowland, 0.0, 1.0)

    suitability = (
        0.10
        + coastal * coastal_bias * 1.25
        + inland_development * inland_bias * 0.85
        + wet_lowland * 0.28
    )
    suitability = np.clip(suitability * land.astype(np.float32) * low_relief * temperate * not_ice, 0.0, 1.0)

    city_count = int(np.clip(round(cfg.megacity_count * (0.45 + density * 1.25)), 1, 80))
    rng = np.random.default_rng(int(cfg.seed) * 3253 + 24091)
    anchors = rng.normal(size=(city_count, 3)).astype(np.float32)
    anchors /= np.linalg.norm(anchors, axis=1, keepdims=True)
    anchor_power = rng.uniform(0.55, 1.0, city_count).astype(np.float32)
    boosted_count = max(1, min(city_count, int(cfg.megacity_count)))
    anchor_power[:boosted_count] *= rng.uniform(1.25, 1.85, boosted_count).astype(np.float32)
    core_width = 0.006 + sprawl * 0.030
    halo_width = 0.024 + sprawl * 0.095

    urban_core = np.zeros_like(x, dtype=np.float32)
    urban_halo = np.zeros_like(x, dtype=np.float32)
    nearest = np.full_like(x, 10.0, dtype=np.float32)
    second = np.full_like(x, 10.0, dtype=np.float32)

    for anchor, power in zip(anchors, anchor_power):
        dot = np.clip(x * anchor[0] + y * anchor[1] + z * anchor[2], -1.0, 1.0)
        dist = 1.0 - dot
        urban_core = np.maximum(urban_core, np.exp(-dist / core_width) * power)
        urban_halo = np.maximum(urban_halo, np.exp(-dist / halo_width) * power)

        closer = dist < nearest
        second = np.where(closer, nearest, np.minimum(second, dist))
        nearest = np.where(closer, dist, nearest)

    network_noise = fbm_3d(x, y, z, 72.0, 4, 0.58, cfg.seed + 24203)
    fine_noise = fbm_3d(x, y, z, 210.0, 3, 0.54, cfg.seed + 24329)
    corridor = 1.0 - smoothstep(0.0, 0.0009 + sprawl * 0.0016, second - nearest)
    corridor *= smoothstep(0.018, 0.17 + sprawl * 0.08, nearest)
    roads = corridor * smoothstep(0.50, 0.82, network_noise) * road_strength

    town_field = fbm_3d(x, y, z, 34.0 + density * 40.0, 5, 0.56, cfg.seed + 24473)
    towns = smoothstep(0.70 - density * 0.16, 0.94, town_field) * (0.28 + sprawl * 0.40)
    urban_envelope = urban_core * 1.15 + urban_halo * (0.34 + sprawl * 0.68) + roads * 0.52 + towns * 0.52
    urban_envelope = np.clip(urban_envelope * suitability * (0.70 + fine_noise * 0.48), 0.0, 1.0)
    settlement_field = np.clip(np.maximum(urban_envelope, suitability * towns * (0.75 + density * 0.85)), 0.0, 1.0)

    dot_scale = float(np.clip(max(x.shape) * (1.35 + density * 2.80), 160.0, 2600.0))
    dot_noise = hash_noise(
        np.floor((x + 1.37) * dot_scale).astype(np.int64),
        np.floor((y + 1.91) * dot_scale).astype(np.int64),
        np.floor((z + 1.53) * dot_scale).astype(np.int64),
        cfg.seed + 24571,
    )
    local_max = dot_noise >= ndimage.maximum_filter(dot_noise, size=3, mode="wrap")
    dot_probability = np.clip(settlement_field * (0.30 + density * 1.18), 0.0, 0.98)
    dots = local_max & (dot_noise > (1.0 - dot_probability))

    extra_dot_noise = hash_noise(
        np.floor((x + 4.19) * dot_scale * 2.35).astype(np.int64),
        np.floor((y + 3.73) * dot_scale * 2.35).astype(np.int64),
        np.floor((z + 4.61) * dot_scale * 2.35).astype(np.int64),
        cfg.seed + 24631,
    )
    extra_local_max = extra_dot_noise >= ndimage.maximum_filter(extra_dot_noise, size=3, mode="wrap")
    extra_probability = np.clip(
        (settlement_field * 0.55 + suitability * towns * 0.85 + roads * 0.22) * (0.26 + density * 1.05),
        0.0,
        0.94,
    )
    extra_dots = extra_local_max & (extra_dot_noise > (1.0 - extra_probability))
    extra_dots &= ~ndimage.maximum_filter(dots, size=3, mode="nearest").astype(bool)

    rows, cols = np.indices(x.shape)
    pin_grid = ((rows + cols + int(cfg.seed)) % 2) == 0
    micro_dot_noise = hash_noise(
        np.floor((x + 5.43) * dot_scale * 3.15).astype(np.int64),
        np.floor((y + 5.97) * dot_scale * 3.15).astype(np.int64),
        np.floor((z + 5.21) * dot_scale * 3.15).astype(np.int64),
        cfg.seed + 24781,
    )
    micro_probability = np.clip(
        (settlement_field * 0.72 + suitability * towns * 1.15 + roads * 0.34) * (0.42 + density * 1.65),
        0.0,
        0.98,
    )
    micro_dots = pin_grid & (micro_dot_noise > (1.0 - micro_probability))

    road_dot_noise = hash_noise(
        np.floor((x + 3.11) * dot_scale * 1.75).astype(np.int64),
        np.floor((y + 2.37) * dot_scale * 1.75).astype(np.int64),
        np.floor((z + 2.83) * dot_scale * 1.75).astype(np.int64),
        cfg.seed + 24697,
    )
    road_dots = (roads > 0.010) & (road_dot_noise > 0.78 - road_strength * 0.16)

    dot_mask = (dots | extra_dots | micro_dots | road_dots) & pin_grid
    light_variation = np.maximum(np.maximum(dot_noise, extra_dot_noise), micro_dot_noise)
    dot_energy = np.where(
        dot_mask,
        np.clip((0.24 + settlement_field * 1.18 + light_variation * 0.34) * strength * (0.82 + density * 0.92), 0.0, 1.0),
        0.0,
    )
    city_intensity = np.clip(dot_energy, 0.0, 1.0)

    warm = np.array([255, 186, 86], dtype=np.float32)
    neutral = np.array([255, 232, 178], dtype=np.float32)
    cool = np.array([198, 220, 255], dtype=np.float32)
    light_color = lerp(warm, neutral, min(temperature * 1.6, 1.0))
    if temperature > 0.62:
        light_color = lerp(neutral, cool, (temperature - 0.62) / 0.38)
    return np.clip(city_intensity[..., None] * light_color, 0.0, 255.0).astype(np.float32)


def distance_from_mask(mask, wrap_x=False):
    if not np.any(mask):
        return np.full(mask.shape, np.inf, dtype=np.float32)
    if wrap_x:
        tiled = np.concatenate([mask, mask, mask], axis=1)
        distances = ndimage.distance_transform_edt(~tiled)
        width = mask.shape[1]
        return distances[:, width : width * 2].astype(np.float32)
    return ndimage.distance_transform_edt(~mask).astype(np.float32)


def filter_land_components(mask, min_area_fraction, max_area_fraction):
    if not np.any(mask):
        return mask
    structure = np.ones((3, 3), dtype=np.uint8)
    labels, label_count = ndimage.label(mask, structure=structure)
    if label_count == 0:
        return np.zeros_like(mask, dtype=bool)

    counts = np.bincount(labels.ravel())
    total = float(mask.size)
    min_pixels = max(1, int(math.ceil(max(0.0, min_area_fraction) * total)))
    max_pixels = math.inf if max_area_fraction <= 0.0 else max(1, int(math.floor(max_area_fraction * total)))
    keep = (counts >= min_pixels) & (counts <= max_pixels)
    keep[0] = False
    return keep[labels]


def hash_noise(ix, iy, iz, seed):
    x = ix.astype(np.uint64)
    y = iy.astype(np.uint64)
    z = iz.astype(np.uint64)
    n = x * np.uint64(374761393) + y * np.uint64(668265263) + z * np.uint64(2147483647)
    n += np.uint64(seed * 1442695040888963407 & 0xFFFFFFFFFFFFFFFF)
    n = (n ^ (n >> np.uint64(13))) * np.uint64(1274126177)
    n = n ^ (n >> np.uint64(16))
    return (n & np.uint64(0xFFFFFFFF)).astype(np.float32) / np.float32(0xFFFFFFFF)


def value_noise_3d(x, y, z, scale, seed):
    sx = x * scale + 100.0
    sy = y * scale + 100.0
    sz = z * scale + 100.0
    x0 = np.floor(sx).astype(np.int64)
    y0 = np.floor(sy).astype(np.int64)
    z0 = np.floor(sz).astype(np.int64)
    xf = sx - x0
    yf = sy - y0
    zf = sz - z0
    u = xf * xf * xf * (xf * (xf * 6.0 - 15.0) + 10.0)
    v = yf * yf * yf * (yf * (yf * 6.0 - 15.0) + 10.0)
    w = zf * zf * zf * (zf * (zf * 6.0 - 15.0) + 10.0)

    c000 = hash_noise(x0, y0, z0, seed)
    c100 = hash_noise(x0 + 1, y0, z0, seed)
    c010 = hash_noise(x0, y0 + 1, z0, seed)
    c110 = hash_noise(x0 + 1, y0 + 1, z0, seed)
    c001 = hash_noise(x0, y0, z0 + 1, seed)
    c101 = hash_noise(x0 + 1, y0, z0 + 1, seed)
    c011 = hash_noise(x0, y0 + 1, z0 + 1, seed)
    c111 = hash_noise(x0 + 1, y0 + 1, z0 + 1, seed)

    x00 = lerp(c000, c100, u)
    x10 = lerp(c010, c110, u)
    x01 = lerp(c001, c101, u)
    x11 = lerp(c011, c111, u)
    y0v = lerp(x00, x10, v)
    y1v = lerp(x01, x11, v)
    return lerp(y0v, y1v, w)


def fbm_3d(x, y, z, scale, octaves, roughness, seed, lacunarity=2.03):
    total = np.zeros_like(x, dtype=np.float32)
    amp = 1.0
    amp_sum = 0.0
    freq = scale
    for octave in range(max(1, int(octaves))):
        total += value_noise_3d(x, y, z, freq, seed + octave * 1013) * amp
        amp_sum += amp
        amp *= roughness
        freq *= lacunarity
    return total / max(amp_sum, 1e-6)


def build_polar_ice_formation(cfg, x, y, z, lat, lon):
    if cfg.polar_ice_size <= 0.0:
        empty = np.zeros_like(x, dtype=np.float32)
        return empty, empty

    lat_abs = np.abs(np.sin(lat))
    ice_start = max(0.02, 1.0 - cfg.polar_ice_size)
    complexity = np.clip(cfg.polar_ice_complexity, 0.0, 1.0)
    fragmentation = np.clip(cfg.polar_ice_fragmentation, 0.0, 1.0)
    solidity = np.clip(cfg.polar_ice_solidity, 0.0, 1.0)
    sheet_scale = max(0.35, cfg.polar_ice_scale)

    sheet_field = fbm_3d(
        x,
        y,
        z,
        sheet_scale,
        cfg.continent_detail,
        cfg.continent_roughness,
        cfg.seed + 7111,
    )
    edge_detail = fbm_3d(
        x,
        y,
        z,
        max(2.0, cfg.shoreline_noise_scale * (0.28 + complexity * 0.55)),
        cfg.shoreline_detail,
        0.62,
        cfg.seed + 7221,
    )
    cap_edge_noise = fbm_3d(
        x,
        y,
        z,
        max(0.85, sheet_scale * (0.72 + complexity * 0.36)),
        max(3, min(6, int(cfg.continent_detail))),
        0.58,
        cfg.seed + 7551,
    )
    cap_edge_detail = fbm_3d(
        x,
        y,
        z,
        max(2.2, sheet_scale * (2.8 + fragmentation * 2.4)),
        4,
        0.60,
        cfg.seed + 7661,
    )
    edge_distortion = min(0.22, cfg.polar_ice_size * (0.42 + complexity * 0.42 + fragmentation * 0.26))
    ragged_lat = np.clip(
        lat_abs
        + (cap_edge_noise - 0.5) * edge_distortion
        + (cap_edge_detail - 0.5) * edge_distortion * 0.34
        + (edge_detail - 0.5) * complexity * 0.035,
        0.0,
        1.0,
    )
    ragged_lat = np.maximum(ragged_lat, smoothstep(0.985, 1.0, lat_abs))
    ice_field = sheet_field + (edge_detail - 0.5) * complexity * 0.42
    sheet_cut = 0.48 + (1.0 - complexity) * 0.10
    sheet_mask = smoothstep(sheet_cut - 0.12, sheet_cut + 0.16, ice_field)

    floe_noise = fbm_3d(x, y, z, max(5.0, sheet_scale * 13.0), 5, 0.66, cfg.seed + 7331)
    floe_chain = 0.5 + 0.5 * np.sin(
        lon * (2.0 + sheet_scale * 1.8)
        + y * (13.0 + sheet_scale * 1.4)
        + cfg.seed * 0.017
    )
    floe_field = lerp(floe_noise, floe_noise * 0.72 + floe_chain * 0.28, fragmentation)
    floe_gate = fbm_3d(x, y, z, max(1.5, sheet_scale * 2.7), 3, 0.54, cfg.seed + 7441)
    floe_cut = 0.76 - fragmentation * 0.20
    floes = smoothstep(floe_cut, min(0.99, floe_cut + 0.10), floe_field)
    floes *= smoothstep(0.38, 0.58, floe_gate)

    edge_width = 0.08 + complexity * 0.06
    outer_gate = smoothstep(max(0.0, ice_start - fragmentation * 0.20), ice_start + edge_width, ragged_lat)
    core_gate = smoothstep(min(0.99, ice_start + edge_width * 0.95), 1.0, ragged_lat)
    sheet_gate = smoothstep(max(0.0, ice_start - complexity * 0.10), ice_start + edge_width * 1.25, ragged_lat)
    floe_gate_lat = smoothstep(max(0.0, ice_start - fragmentation * 0.28), ice_start + edge_width * 0.50, ragged_lat)

    sheet_ice = np.maximum(core_gate, sheet_mask * sheet_gate)
    fragmented_ice = floes * floe_gate_lat * fragmentation
    polar_ice = np.clip(np.maximum(sheet_ice, fragmented_ice) * outer_gate, 0.0, 1.0)
    hard_edge_width = 0.42 - solidity * 0.32
    solid_ice = smoothstep(0.025, max(0.08, hard_edge_width), polar_ice)
    fill_boost = smoothstep(0.02, 0.18, polar_ice) * solidity * 0.36
    polar_ice = np.clip(lerp(polar_ice, solid_ice, solidity) + fill_boost, 0.0, 1.0)
    ice_texture = np.clip(edge_detail * 0.65 + floe_noise * 0.35, 0.0, 1.0)
    return polar_ice.astype(np.float32), ice_texture.astype(np.float32)


def sphere_vectors(width, height):
    lon = np.linspace(-math.pi, math.pi, width, endpoint=False, dtype=np.float32)
    lat = np.linspace(math.pi / 2.0, -math.pi / 2.0, height, dtype=np.float32)
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    cos_lat = np.cos(lat_grid)
    x = cos_lat * np.cos(lon_grid)
    y = np.sin(lat_grid)
    z = cos_lat * np.sin(lon_grid)
    return x, y, z, lat_grid, lon_grid


def quad_sphere_face_vectors(face, size):
    axis = ((np.arange(size, dtype=np.float32) + 0.5) / size) * 2.0 - 1.0
    u_axis = axis
    v_axis = axis
    u, v = np.meshgrid(u_axis, v_axis[::-1])

    if face == "px":
        x, y, z = np.ones_like(u), v, -u
    elif face == "nx":
        x, y, z = -np.ones_like(u), v, u
    elif face == "py":
        x, y, z = u, np.ones_like(u), -v
    elif face == "ny":
        x, y, z = u, -np.ones_like(u), v
    elif face == "pz":
        x, y, z = u, v, np.ones_like(u)
    elif face == "nz":
        x, y, z = -u, v, -np.ones_like(u)
    else:
        raise ValueError(f"Unknown quad-sphere face: {face}")

    length = np.sqrt(x * x + y * y + z * z)
    x = x / length
    y = y / length
    z = z / length
    lat = np.arcsin(np.clip(y, -1.0, 1.0))
    lon = np.arctan2(z, x)
    return x, y, z, lat, lon


def color_blend(a, b, t):
    return a * (1.0 - t[..., None]) + b * t[..., None]


def rgb_to_hsv_pixels(rgb):
    rgb01 = np.clip(rgb, 0.0, 255.0) / 255.0
    r = rgb01[..., 0]
    g = rgb01[..., 1]
    b = rgb01[..., 2]
    maxc = np.max(rgb01, axis=-1)
    minc = np.min(rgb01, axis=-1)
    delta = maxc - minc
    safe_delta = np.where(delta == 0.0, 1.0, delta)

    h = np.zeros_like(maxc)
    h = np.where(maxc == r, ((g - b) / safe_delta) % 6.0, h)
    h = np.where(maxc == g, ((b - r) / safe_delta) + 2.0, h)
    h = np.where(maxc == b, ((r - g) / safe_delta) + 4.0, h)
    h = np.where(delta == 0.0, 0.0, h / 6.0)
    s = np.where(maxc == 0.0, 0.0, delta / np.maximum(maxc, 1e-6))
    return np.stack((h, s, maxc), axis=-1)


def hsv_to_rgb_pixels(hsv):
    h = (hsv[..., 0] % 1.0) * 6.0
    s = np.clip(hsv[..., 1], 0.0, 1.0)
    v = np.clip(hsv[..., 2], 0.0, 1.0)
    c = v * s
    x = c * (1.0 - np.abs((h % 2.0) - 1.0))
    m = v - c

    z = np.zeros_like(h)
    rp = np.select(
        [h < 1.0, h < 2.0, h < 3.0, h < 4.0, h < 5.0],
        [c, x, z, z, x],
        default=c,
    )
    gp = np.select(
        [h < 1.0, h < 2.0, h < 3.0, h < 4.0, h < 5.0],
        [x, c, c, x, z],
        default=z,
    )
    bp = np.select(
        [h < 1.0, h < 2.0, h < 3.0, h < 4.0, h < 5.0],
        [z, z, x, c, c],
        default=x,
    )
    return np.stack((rp + m, gp + m, bp + m), axis=-1) * 255.0


def adjust_ocean_hsv_color(ocean_color, cfg):
    hue_shift = float(np.clip(cfg.ocean_hue_shift, -0.5, 0.5))
    saturation = float(np.clip(cfg.ocean_saturation, 0.0, 3.0))
    colorizer_strength = float(np.clip(cfg.ocean_colorizer_strength, 0.0, 1.0))
    if hue_shift == 0.0 and saturation == 1.0 and colorizer_strength == 0.0:
        return ocean_color

    hsv = rgb_to_hsv_pixels(ocean_color)
    hsv[..., 0] = (hsv[..., 0] + hue_shift) % 1.0
    hsv[..., 1] = np.clip(hsv[..., 1] * saturation, 0.0, 1.0)
    adjusted = hsv_to_rgb_pixels(hsv)

    if colorizer_strength > 0.0:
        colorized_hsv = hsv.copy()
        colorized_hsv[..., 0] = float(cfg.ocean_colorizer_hue) % 1.0
        colorized_hsv[..., 1] = np.clip(colorized_hsv[..., 1] * 1.15 + 0.08, 0.0, 1.0)
        colorized = hsv_to_rgb_pixels(colorized_hsv)
        adjusted = adjusted * (1.0 - colorizer_strength) + colorized * colorizer_strength

    return np.clip(adjusted, 0.0, 255.0)


def build_continent_color_provinces(
    cfg,
    x,
    y,
    z,
    land,
    arid,
    moisture,
    mountain_mask,
    lowland,
    shoreline,
    mineral_noise,
    cold_lat,
    non_ice_land,
):
    map_height, map_width = x.shape
    blank_weight = np.zeros((map_height, map_width), dtype=np.float32)
    blank_color = np.zeros((map_height, map_width, 3), dtype=np.float32)
    strength = float(np.clip(cfg.continent_color_variation, 0.0, 1.0))
    if strength <= 0.0:
        return blank_color, blank_weight, blank_weight

    scale = max(0.25, float(cfg.continent_color_scale))
    diversity = float(np.clip(cfg.continent_color_diversity, 0.0, 1.0))
    blend_smoothness = float(np.clip(cfg.continent_color_blend_smoothness, 0.0, 1.0))
    region_tints = land_palette_values(cfg.land_palette)["region_tints"]
    province_count = int(np.clip(round(7.0 + scale * 4.2), 6, 38))
    rng = np.random.default_rng(int(cfg.seed) * 1709 + 9176)

    anchors = rng.normal(size=(province_count, 3)).astype(np.float32)
    anchors /= np.linalg.norm(anchors, axis=1, keepdims=True)
    styles = (np.arange(province_count, dtype=np.int32) % len(region_tints)).astype(np.int32)
    rng.shuffle(styles)
    province_bias = rng.uniform(0.82, 1.24, province_count).astype(np.float32)

    warp_strength = 0.06 + diversity * 0.16
    warp_scale = max(0.50, scale * 0.92)
    wx = x + (fbm_3d(x, y, z, warp_scale, 3, 0.52, cfg.seed + 6581) - 0.5) * warp_strength
    wy = y + (fbm_3d(x, y, z, warp_scale * 1.13, 3, 0.52, cfg.seed + 6599) - 0.5) * warp_strength
    wz = z + (fbm_3d(x, y, z, warp_scale * 0.87, 3, 0.52, cfg.seed + 6619) - 0.5) * warp_strength
    warp_len = np.sqrt(wx * wx + wy * wy + wz * wz)
    wx = wx / np.maximum(warp_len, 1e-6)
    wy = wy / np.maximum(warp_len, 1e-6)
    wz = wz / np.maximum(warp_len, 1e-6)

    best_score = np.full_like(x, -2.0, dtype=np.float32)
    second_score = np.full_like(x, -2.0, dtype=np.float32)
    province_id = np.zeros_like(x, dtype=np.int32)
    second_province_id = np.zeros_like(x, dtype=np.int32)
    for index, anchor in enumerate(anchors):
        score = wx * anchor[0] + wy * anchor[1] + wz * anchor[2]
        better = score > best_score
        between = (~better) & (score > second_score)
        second_province_id = np.where(better, province_id, np.where(between, index, second_province_id))
        second_score = np.where(better, best_score, np.where(between, score, second_score))
        best_score = np.where(better, score, best_score)
        province_id = np.where(better, index, province_id)

    style_map = styles[province_id]
    second_style_map = styles[second_province_id]
    best_color = region_tints[style_map]
    second_color = region_tints[second_style_map]
    bias_map = province_bias[province_id]
    boundary_margin = best_score - second_score
    blend_width = 0.045 + blend_smoothness * 0.360 + (1.0 - diversity) * 0.060
    boundary_soft = smoothstep(0.006, blend_width, boundary_margin)
    neighbor_mix = (1.0 - boundary_soft) * (0.16 + blend_smoothness * 0.84)
    target_color = color_blend(best_color, second_color, neighbor_mix)
    province_texture = 0.82 + fbm_3d(x, y, z, scale * 5.2 + 3.0, 3, 0.50, cfg.seed + 6637) * 0.34

    warm_gate = np.clip(0.46 + arid * 0.40 + lowland * 0.22, 0.0, 1.0)
    red_gate = np.clip(0.34 + arid * 0.48 + mineral_noise * 0.28 + mountain_mask * 0.16, 0.0, 1.0)
    dark_gate = np.clip(0.34 + mineral_noise * 0.38 + mountain_mask * 0.38, 0.0, 1.0)
    humid_gate = np.clip(0.24 + moisture * 0.74 + lowland * 0.14 - mountain_mask * 0.18, 0.0, 1.0)
    pale_gate = np.clip(0.34 + lowland * 0.38 + shoreline * 0.20 + (1.0 - arid) * 0.16, 0.0, 1.0)
    cool_gate = np.clip(0.30 + cold_lat * 0.64 + moisture * 0.12 - arid * 0.16, 0.0, 1.0)

    best_style_gate = np.zeros_like(x, dtype=np.float32)
    second_style_gate = np.zeros_like(x, dtype=np.float32)
    for style_index, gate in enumerate((warm_gate, red_gate, dark_gate, humid_gate, pale_gate, cool_gate)):
        best_style_gate = np.where(style_map == style_index, gate, best_style_gate)
        second_style_gate = np.where(second_style_map == style_index, gate, second_style_gate)
    style_gate = best_style_gate * (1.0 - neighbor_mix) + second_style_gate * neighbor_mix

    land_region = land.astype(np.float32) * non_ice_land
    gain = strength * (1.35 + diversity * 1.05)
    region_weight = (
        (0.48 + boundary_soft * (0.52 - blend_smoothness * 0.16))
        * gain
        * style_gate
        * bias_map
        * province_texture
        * land_region
    )
    region_weight = np.clip(region_weight, 0.0, 0.58 + diversity * 0.22)
    debug = ((province_id.astype(np.float32) + 1.0) / float(province_count)) * land.astype(np.float32)
    return target_color, region_weight, debug


def save_rgb(path, arr):
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "RGB").save(path)


def save_gray(path, arr):
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "L").save(path)


def save_rgba(path, arr):
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "RGBA").save(path)


def save_luminance_alpha(path, arr):
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "LA").save(path)


def normal_from_height(height, strength=5.0, wrap_x=True):
    if wrap_x:
        dx = np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)
    else:
        padded_x = np.pad(height, ((0, 0), (1, 1)), mode="edge")
        dx = padded_x[:, 2:] - padded_x[:, :-2]

    padded_y = np.pad(height, ((1, 1), (0, 0)), mode="edge")
    dy = padded_y[2:, :] - padded_y[:-2, :]
    nx = -dx * strength
    ny = -dy * strength
    nz = np.ones_like(height)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack((nx / length, ny / length, nz / length), axis=2)
    return (normal * 0.5 + 0.5) * 255.0


def render_globe_preview(color, height_map, out_path, size=900):
    img = np.zeros((size, size, 3), dtype=np.float32)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    sx = (xx / (size - 1)) * 2.0 - 1.0
    sy = 1.0 - (yy / (size - 1)) * 2.0
    r2 = sx * sx + sy * sy
    mask = r2 <= 1.0
    sz = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0))

    lon = np.arctan2(sx, sz)
    lat = np.arcsin(np.clip(sy, -1.0, 1.0))
    u = ((lon + math.pi) / (2.0 * math.pi) * color.shape[1]).astype(np.int32) % color.shape[1]
    v = ((math.pi / 2.0 - lat) / math.pi * (color.shape[0] - 1)).astype(np.int32)
    sampled = color[v, u].astype(np.float32)

    normals = np.stack((sx, sy, sz), axis=2)
    light = np.array([-0.45, 0.35, 0.82], dtype=np.float32)
    light /= np.linalg.norm(light)
    shade = np.clip(np.sum(normals * light, axis=2), 0.0, 1.0)
    shade = 0.18 + shade * 0.95
    rim = np.clip((1.0 - sz) * 1.4, 0.0, 1.0)
    atmosphere = np.array([72, 122, 176], dtype=np.float32)
    sampled = color_blend(sampled, atmosphere, rim * 0.18)

    h = height_map[v, u]
    sampled *= shade[..., None] * (0.92 + h[..., None] * 0.12)
    img[mask] = sampled[mask]

    alpha_edge = 1.0 - smoothstep(0.88, 1.0, r2)
    img *= alpha_edge[..., None]
    save_rgb(out_path, img)


def build_maps_from_vectors(
    cfg,
    x,
    y,
    z,
    lat,
    lon,
    normal_wrap_x=True,
    land_threshold=None,
    cloud_threshold=None,
    moisture_range=None,
    height_range=None,
    return_raw_stats=False,
):
    lat_abs = np.abs(np.sin(lat))
    colors = vary_palette(cfg.seed, cfg.preset, cfg.land_palette)
    colors.update(ocean_colors_from_base(cfg.ocean_base_color))

    continent = fbm_3d(
        x,
        y,
        z,
        cfg.continent_scale,
        cfg.continent_detail,
        cfg.continent_roughness,
        cfg.seed,
    )
    coast_detail = fbm_3d(
        x,
        y,
        z,
        cfg.shoreline_noise_scale,
        cfg.shoreline_detail,
        0.62,
        cfg.seed + 811,
    )
    coast_detail = (coast_detail - 0.5) * cfg.shoreline_complexity * 0.38
    land_field = continent + coast_detail - cfg.shoreline_erosion * 0.12

    threshold = (
        float(np.quantile(land_field, 1.0 - cfg.land_coverage))
        if land_threshold is None
        else float(land_threshold)
    )
    continent_land = land_field >= threshold

    map_height, map_width = x.shape
    island_land = np.zeros_like(continent_land, dtype=bool)
    land = continent_land
    cloud_field = build_cloud_field(cfg, x, y, z, lat, land_field, threshold)
    if cloud_threshold is None:
        cloud_threshold = (
            float(np.quantile(cloud_field, 1.0 - float(np.clip(cfg.cloud_coverage, 0.0, 1.0))))
            if 0.0 < cfg.cloud_coverage < 1.0
            else 1.0
        )
    cloud_mask = cloud_mask_from_field(cfg, cloud_field, float(cloud_threshold))

    continent_shoreline_distance = np.abs(land_field - threshold)
    continent_shoreline = 1.0 - smoothstep(0.0, max(cfg.beach_width, 0.005), continent_shoreline_distance)
    shoreline = np.where(land, continent_shoreline, continent_shoreline * 0.55)

    continent_shelf = 1.0 - smoothstep(0.0, max(cfg.shelf_width, 0.005), np.clip(threshold - land_field, 0.0, 10.0))
    shelf = np.where(~land, continent_shelf, 0.0)
    ocean_depth = np.where(land, 0.0, 1.0 - shelf * 0.75)

    biome = fbm_3d(x, y, z, cfg.biome_scale, cfg.biome_complexity, 0.57, cfg.seed + 2333)
    moisture_input = (
        fbm_3d(x, y, z, cfg.biome_scale * 0.7, 4, 0.55, cfg.seed + 3441)
        + shelf * 0.28
        + (1.0 - lat_abs) * 0.16
    )
    moisture = normalize01(moisture_input, moisture_range)
    desert_bias = cfg.desert_coverage * (0.45 + (1.0 - moisture) * 0.75)
    forest_bias = cfg.forest_coverage * (0.35 + moisture * 0.85)

    ridge = 1.0 - np.abs(fbm_3d(x, y, z, cfg.mountain_scale, 6, 0.67, cfg.seed + 4111) * 2.0 - 1.0)
    ridge = np.power(np.clip(ridge, 0.0, 1.0), 1.0 + cfg.mountain_sharpness * 3.0)
    mountain_gate = fbm_3d(x, y, z, max(1.0, cfg.mountain_scale * 0.32), 4, 0.56, cfg.seed + 4229)
    mountain_cut = np.clip(1.0 - cfg.mountain_density, 0.05, 0.95)
    mountain_mask = smoothstep(mountain_cut, min(1.0, mountain_cut + 0.28), ridge)
    mountain_mask *= smoothstep(0.45, 0.76, mountain_gate)

    color = np.zeros((map_height, map_width, 3), dtype=np.float32)
    ocean_variation = fbm_3d(x, y, z, 18.0, 4, 0.5, cfg.seed + 5111)
    ocean_color = color_blend(
        colors["deep_ocean"],
        colors["ocean_mid"],
        np.clip(ocean_variation * cfg.ocean_current_strength * 1.8, 0.0, 0.72),
    )
    ocean_color = color_blend(ocean_color, colors["shallow_ocean"], shelf)
    ocean_texture = fbm_3d(x, y, z, 32.0, 4, 0.52, cfg.seed + 5221)
    equator = 1.0 - lat_abs

    warm_shallow = np.array([68, 205, 190], dtype=np.float32)
    warm_shallow = (warm_shallow - 127.5) * cfg.ocean_shelf_contrast + 127.5
    warm_shallow = warm_shallow + cfg.ocean_shelf_brightness * 255.0
    warm_shallow = np.clip(warm_shallow, 0.0, 255.0)
    depth_blue = np.array([0, 8, 38], dtype=np.float32)
    cold_deep = np.array([42, 72, 102], dtype=np.float32)
    productive_teal = np.array([18, 154, 96], dtype=np.float32)
    sediment_tint = np.array([172, 154, 82], dtype=np.float32)
    legacy_ocean_variation = np.clip(cfg.ocean_color_variation, 0.0, 1.0)
    shallow_tint_weight = np.power(np.clip(shelf, 0.0, 1.0), 0.65)
    deep_tint_weight = smoothstep(0.22, 1.0, ocean_depth)

    ocean_color = color_blend(
        ocean_color,
        warm_shallow,
        np.clip(
            shallow_tint_weight
            * (0.65 + equator * 0.45)
            * (0.65 + ocean_texture * 0.60)
            * (cfg.ocean_shallow_tint_strength + legacy_ocean_variation * 0.65),
            0.0,
            0.72,
        ),
    )
    ocean_color = color_blend(
        ocean_color,
        depth_blue,
        np.clip(
            deep_tint_weight
            * (0.70 + ocean_texture * 0.55)
            * (cfg.ocean_depth_tint_strength + legacy_ocean_variation * 0.45),
            0.0,
            0.58,
        ),
    )
    ocean_color = color_blend(
        ocean_color,
        cold_deep,
        np.clip(
            deep_tint_weight
            * smoothstep(0.30, 0.92, lat_abs)
            * (cfg.ocean_latitude_tint_strength + legacy_ocean_variation * 0.50),
            0.0,
            0.58,
        ),
    )
    productivity_noise = fbm_3d(x, y, z, 7.0, 4, 0.56, cfg.seed + 5331)
    upwelling = np.clip(
        shallow_tint_weight * 0.80
        + smoothstep(0.38, 0.78, lat_abs) * 0.28
        + equator * ocean_variation * 0.38,
        0.0,
        1.0,
    )
    ocean_color = color_blend(
        ocean_color,
        productive_teal,
        np.clip(
            smoothstep(0.30, 0.78, productivity_noise)
            * upwelling
            * cfg.ocean_productivity_strength
            * 1.8,
            0.0,
            0.56,
        ),
    )
    sediment_noise = fbm_3d(x, y, z, 45.0, 3, 0.52, cfg.seed + 5441)
    coastal_sediment = np.clip(shoreline * 0.85 + shallow_tint_weight * 0.58, 0.0, 1.0)
    ocean_color = color_blend(
        ocean_color,
        sediment_tint,
        np.clip(
            coastal_sediment
            * smoothstep(0.24, 0.72, sediment_noise)
            * cfg.ocean_sediment_strength
            * 2.2,
            0.0,
            0.62,
        ),
    )
    shelf_color_control_mask = np.clip(
        shallow_tint_weight
        * (0.70 + cfg.ocean_shallow_tint_strength * 0.55 + legacy_ocean_variation * 0.25),
        0.0,
        1.0,
    )
    shelf_adjusted_ocean = (ocean_color - 127.5) * cfg.ocean_shelf_contrast + 127.5
    shelf_adjusted_ocean = shelf_adjusted_ocean + cfg.ocean_shelf_brightness * 255.0
    shelf_adjusted_ocean = np.clip(shelf_adjusted_ocean, 0.0, 255.0)
    ocean_color = color_blend(ocean_color, shelf_adjusted_ocean, shelf_color_control_mask)
    ocean_color = adjust_ocean_hsv_color(ocean_color, cfg)
    ocean_color = (ocean_color - 127.5) * cfg.ocean_contrast + 127.5
    ocean_color = ocean_color + cfg.ocean_brightness * 255.0
    ocean_color = np.clip(ocean_color, 0.0, 255.0)
    color[:] = ocean_color

    land_color = color_blend(colors["grass"], colors["dry_plain"], np.clip(biome + desert_bias - 0.45, 0.0, 1.0))
    land_color = color_blend(land_color, colors["desert"], np.clip(desert_bias + biome * 0.35 - 0.28, 0.0, 1.0))
    forest_mix = np.clip(forest_bias + moisture * 0.35 - biome * 0.35, 0.0, 1.0)
    land_color = color_blend(land_color, colors["forest"], forest_mix)
    land_color = color_blend(land_color, colors["dark_forest"], np.clip(forest_mix * moisture - 0.15, 0.0, 0.65))
    land_color = color_blend(land_color, colors["rock"], mountain_mask * 0.74)
    land_color = color_blend(land_color, colors["beach"], shoreline * 0.78)

    snow_mask = smoothstep(cfg.snow_threshold, 1.0, mountain_mask * 0.72 + lat_abs * 0.38)
    polar_ice, ice_texture = build_polar_ice_formation(cfg, x, y, z, lat, lon)
    ice_mask = np.maximum(snow_mask, polar_ice)

    soil_noise = fbm_3d(x, y, z, cfg.biome_scale * 2.4, 4, 0.52, cfg.seed + 6221)
    mineral_noise = fbm_3d(x, y, z, cfg.mountain_scale * 1.7, 4, 0.58, cfg.seed + 6331)
    cold_lat = smoothstep(0.42, 0.88, lat_abs)
    arid = np.clip(desert_bias + (1.0 - moisture) * 0.45, 0.0, 1.0)
    non_ice_land = 1.0 - np.clip(ice_mask, 0.0, 1.0)
    continent_lowland = 1.0 - smoothstep(threshold, threshold + cfg.continent_contrast * 1.8, land_field)
    lowland = continent_lowland
    land_tints = land_palette_values(cfg.land_palette)["tints"]
    ochre_tint = land_tints["ochre"]
    rust_tint = land_tints["rust"]
    dark_wet_tint = land_tints["dark_wet"]
    cool_tundra_tint = land_tints["cool_tundra"]
    pale_highland_tint = land_tints["pale_highland"]
    iron_oxide_tint = land_tints["iron_oxide"]
    basalt_tint = land_tints["basalt"]
    salt_flat_tint = land_tints["salt_flat"]
    clay_tint = land_tints["clay"]

    regional_tint, regional_weight, regional_debug = build_continent_color_provinces(
        cfg,
        x,
        y,
        z,
        land,
        arid,
        moisture,
        mountain_mask,
        lowland,
        shoreline,
        mineral_noise,
        cold_lat,
        non_ice_land,
    )
    land_color = color_blend(land_color, regional_tint, regional_weight)

    land_color = color_blend(
        land_color,
        ochre_tint,
        np.clip(arid * soil_noise * cfg.land_color_variation * non_ice_land, 0.0, 0.28),
    )
    land_color = color_blend(
        land_color,
        dark_wet_tint,
        np.clip(moisture * (1.0 - mountain_mask) * soil_noise * cfg.wetland_tint_strength * non_ice_land, 0.0, 0.22),
    )
    land_color = color_blend(
        land_color,
        cool_tundra_tint,
        np.clip(cold_lat * cfg.land_color_variation * 0.72 * non_ice_land, 0.0, 0.20),
    )
    land_color = color_blend(
        land_color,
        pale_highland_tint,
        np.clip(mountain_mask * mineral_noise * cfg.land_color_variation * 0.72 * non_ice_land, 0.0, 0.22),
    )
    mineral_exposure = np.clip(mountain_mask * 0.80 + arid * 0.30 + soil_noise * 0.12, 0.0, 1.0)
    land_color = color_blend(
        land_color,
        rust_tint,
        np.clip(mineral_noise * mineral_exposure * cfg.mineral_tint_strength * non_ice_land, 0.0, 0.58),
    )
    exposed_dry = np.clip(arid * (0.65 + mountain_mask * 0.35) * (0.45 + soil_noise * 0.55), 0.0, 1.0)
    basalt_exposure = np.clip((mountain_mask * 0.65 + mineral_noise * 0.35) * smoothstep(0.48, 0.90, mineral_noise), 0.0, 1.0)
    salt_basin = np.clip(arid * lowland * smoothstep(0.45, 0.95, soil_noise) * (1.0 - moisture * 0.55), 0.0, 1.0)
    clay_basin = np.clip((moisture * 0.55 + shoreline * 0.45) * lowland * (1.0 - mountain_mask * 0.70), 0.0, 1.0)
    land_color = color_blend(
        land_color,
        iron_oxide_tint,
        np.clip(exposed_dry * cfg.iron_oxide_tint_strength * non_ice_land, 0.0, 0.50),
    )
    land_color = color_blend(
        land_color,
        basalt_tint,
        np.clip(basalt_exposure * cfg.basalt_tint_strength * non_ice_land, 0.0, 0.54),
    )
    land_color = color_blend(
        land_color,
        clay_tint,
        np.clip(clay_basin * cfg.clay_tint_strength * non_ice_land, 0.0, 0.42),
    )
    land_color = color_blend(
        land_color,
        salt_flat_tint,
        np.clip(salt_basin * cfg.salt_flat_tint_strength * non_ice_land, 0.0, 0.48),
    )
    land_color = (land_color - 127.5) * cfg.land_contrast + 127.5
    land_color = land_color + cfg.land_brightness * 255.0
    land_color = np.clip(land_color, 0.0, 255.0)
    ice_solidity = np.clip(cfg.polar_ice_solidity, 0.0, 1.0)
    solid_ice_tint = land_tints["solid_ice"]
    ice_highlight = color_blend(
        colors["ice"],
        colors["snow"],
        np.clip(ice_texture * 0.20 + ice_solidity * 0.54, 0.0, 0.76),
    )
    ice_highlight = color_blend(ice_highlight, solid_ice_tint, ice_solidity * 0.35)
    land_color = color_blend(land_color, colors["snow"], snow_mask)
    land_ice_strength = np.clip(polar_ice * (0.70 + ice_solidity * 0.42), 0.0, 1.0)
    land_color = color_blend(land_color, ice_highlight, land_ice_strength)
    ocean_ice_strength = np.clip(
        polar_ice * (0.30 + cfg.polar_ice_shelf_strength * 0.45 + ice_solidity * 0.46),
        0.0,
        1.0,
    )
    ocean_color_with_ice = color_blend(color, ice_highlight, np.where(~land, ocean_ice_strength, 0.0))
    color = np.where(land[..., None], land_color, ocean_color_with_ice)
    flat_ocean_strength = float(np.clip(cfg.ocean_flat_color_strength, 0.0, 1.0))
    if flat_ocean_strength > 0.0:
        flat_ocean_color = rgb_from_hex(cfg.ocean_base_color)
        flat_ocean_mask = np.where(~land, flat_ocean_strength, 0.0)
        color = color_blend(color, flat_ocean_color, flat_ocean_mask)
    shelf_color_strength = float(np.clip(cfg.ocean_shelf_color_strength, 0.0, 1.0))
    if shelf_color_strength > 0.0:
        shelf_layer_color = rgb_from_hex(cfg.ocean_shelf_color)
        shelf_layer_color = (shelf_layer_color - 127.5) * cfg.ocean_shelf_contrast + 127.5
        shelf_layer_color = shelf_layer_color + cfg.ocean_shelf_brightness * 255.0
        shelf_layer_color = np.clip(shelf_layer_color, 0.0, 255.0)
        shelf_layer_mask = np.clip(shallow_tint_weight * shelf_color_strength, 0.0, 1.0)
        shelf_layer_mask = np.where(~land, shelf_layer_mask, 0.0)
        color = color_blend(color, shelf_layer_color, shelf_layer_mask)

    continent_base_land_height = smoothstep(threshold - cfg.continent_contrast, threshold + cfg.continent_contrast, land_field)
    base_land_height = continent_base_land_height
    height = np.where(land, 0.38 + base_land_height * 0.20, 0.18 - ocean_depth * 0.18)
    height += np.where(land, mountain_mask * cfg.mountain_height * 0.36, 0.0)
    height += np.where(land, shoreline * 0.025, 0.0)
    height += np.where(
        land,
        polar_ice * (0.018 + ice_solidity * 0.034 + ice_texture * 0.026),
        polar_ice * cfg.polar_ice_shelf_strength * (0.008 + ice_solidity * 0.014),
    )
    raw_height = height
    height = normalize01(raw_height, height_range)

    roughness = np.where(land, 0.72, 0.24)
    roughness = roughness + mountain_mask * 0.12 - shelf * 0.07
    roughness = roughness + polar_ice * (0.06 + ice_solidity * 0.12 + ice_texture * 0.16)
    roughness = np.clip(roughness, 0.0, 1.0)
    city_lights = build_city_lights_map(
        cfg,
        x,
        y,
        z,
        lat,
        land,
        shoreline,
        moisture,
        mountain_mask,
        polar_ice,
    )

    maps = {
        "color": color,
        "height": height,
        "normal": normal_from_height(height, wrap_x=normal_wrap_x),
        "roughness": roughness,
        "land_mask": land.astype(np.float32),
        "shoreline_mask": shoreline,
        "ocean_depth": ocean_depth,
        "cloud_mask": cloud_mask,
        "city_lights": city_lights,
    }
    if return_raw_stats:
        maps["_land_field"] = land_field
        maps["_cloud_field"] = cloud_field
        maps["_moisture_input"] = moisture_input
        maps["_raw_height"] = raw_height
        maps["_continent_land"] = continent_land.astype(np.float32)
        maps["_island_land"] = island_land.astype(np.float32)
        maps["_continent_color_region"] = regional_debug
    return maps


def build_maps(cfg):
    x, y, z, lat, lon = sphere_vectors(cfg.width, cfg.height)
    return build_maps_from_vectors(cfg, x, y, z, lat, lon, normal_wrap_x=True)


def build_quad_sphere_maps(cfg, face_size):
    vectors = {}
    probe_maps = {}
    for face in ("px", "nx", "py", "ny", "pz", "nz"):
        x, y, z, lat, lon = quad_sphere_face_vectors(face, face_size)
        vectors[face] = (x, y, z, lat, lon)
        probe_maps[face] = build_maps_from_vectors(
            cfg,
            x,
            y,
            z,
            lat,
            lon,
            normal_wrap_x=False,
            return_raw_stats=True,
        )

    all_land = np.concatenate([maps["_land_field"].ravel() for maps in probe_maps.values()])
    land_threshold = float(np.quantile(all_land, 1.0 - cfg.land_coverage))

    probe_maps = {}
    for face, (x, y, z, lat, lon) in vectors.items():
        probe_maps[face] = build_maps_from_vectors(
            cfg,
            x,
            y,
            z,
            lat,
            lon,
            normal_wrap_x=False,
            land_threshold=land_threshold,
            return_raw_stats=True,
        )

    all_moisture = np.concatenate([maps["_moisture_input"].ravel() for maps in probe_maps.values()])
    all_height = np.concatenate([maps["_raw_height"].ravel() for maps in probe_maps.values()])
    all_cloud = np.concatenate([maps["_cloud_field"].ravel() for maps in probe_maps.values()])
    moisture_range = (float(np.min(all_moisture)), float(np.max(all_moisture)))
    height_range = (float(np.min(all_height)), float(np.max(all_height)))
    cloud_coverage = float(np.clip(cfg.cloud_coverage, 0.0, 1.0))
    cloud_threshold = float(np.quantile(all_cloud, 1.0 - cloud_coverage)) if 0.0 < cloud_coverage < 1.0 else 1.0

    faces = {}
    for face, (x, y, z, lat, lon) in vectors.items():
        faces[face] = build_maps_from_vectors(
            cfg,
            x,
            y,
            z,
            lat,
            lon,
            normal_wrap_x=False,
            land_threshold=land_threshold,
            cloud_threshold=cloud_threshold,
            moisture_range=moisture_range,
            height_range=height_range,
        )
    return faces


TEXTURE_MAP_NAMES = (
    "color",
    "height",
    "normal",
    "roughness",
    "land_mask",
    "shoreline_mask",
    "ocean_depth",
    "cloud_mask",
    "city_lights",
)

QUAD_SPHERE_MAP_NAMES = TEXTURE_MAP_NAMES


def selected_texture_maps(map_names=None):
    if map_names is None:
        return TEXTURE_MAP_NAMES
    selected = tuple(name for name in TEXTURE_MAP_NAMES if name in set(map_names))
    if not selected:
        raise ValueError("Choose at least one texture map to save.")
    return selected


def save_map_set(out_dir, maps, map_names=None):
    selected = selected_texture_maps(map_names)
    if "color" in selected:
        save_rgb(out_dir / "color.png", maps["color"])
    if "height" in selected:
        save_gray(out_dir / "height.png", maps["height"])
    if "normal" in selected:
        save_rgb(out_dir / "normal.png", maps["normal"])
    if "roughness" in selected:
        save_gray(out_dir / "roughness.png", maps["roughness"])
    if "land_mask" in selected:
        save_gray(out_dir / "land_mask.png", maps["land_mask"])
    if "shoreline_mask" in selected:
        save_gray(out_dir / "shoreline_mask.png", maps["shoreline_mask"])
    if "ocean_depth" in selected:
        save_gray(out_dir / "ocean_depth.png", maps["ocean_depth"])
    if "cloud_mask" in selected:
        save_gray(out_dir / "cloud_mask.png", maps["cloud_mask"])
    if "city_lights" in selected:
        save_rgb(out_dir / "city_lights.png", maps["city_lights"])


CUBEMAP_CROSS_LAYOUT = {
    "py": (1, 0),
    "nx": (0, 1),
    "pz": (1, 1),
    "px": (2, 1),
    "nz": (3, 1),
    "ny": (1, 2),
}


def build_cubemap_cross(faces, map_name, face_size):
    sample = faces["px"][map_name]
    if sample.ndim == 3:
        cross = np.zeros((face_size * 3, face_size * 4, sample.shape[2] + 1), dtype=sample.dtype)
        if map_name == "normal":
            cross[:, :, :3] = np.array([128.0, 128.0, 255.0], dtype=sample.dtype)
    else:
        cross = np.zeros((face_size * 3, face_size * 4, 2), dtype=sample.dtype)

    for face, (col, row) in CUBEMAP_CROSS_LAYOUT.items():
        y0 = row * face_size
        x0 = col * face_size
        if sample.ndim == 3:
            cross[y0 : y0 + face_size, x0 : x0 + face_size, :3] = faces[face][map_name]
            cross[y0 : y0 + face_size, x0 : x0 + face_size, 3] = 255.0
        else:
            cross[y0 : y0 + face_size, x0 : x0 + face_size, 0] = faces[face][map_name]
            cross[y0 : y0 + face_size, x0 : x0 + face_size, 1] = 1.0
    return np.rot90(cross, k=3)


def save_quad_sphere_cubemap_crosses(out_dir, faces, face_size, map_names=None):
    for map_name in selected_texture_maps(map_names):
        cross = build_cubemap_cross(faces, map_name, face_size)
        path = out_dir / f"{map_name}_cubemap_cross.png"
        if cross.shape[2] == 4:
            save_rgba(path, cross)
        else:
            save_luminance_alpha(path, cross)


def write_quad_sphere_manifest(out_dir, face_size, map_names=None):
    selected = selected_texture_maps(map_names)
    manifest = {
        "layout": "quad_sphere_cubemap_faces",
        "face_size": face_size,
        "faces": ["px", "nx", "py", "ny", "pz", "nz"],
        "maps": [f"{name}.png" for name in selected],
        "cubemap_cross": {
            "layout": "horizontal_cross_4x3_rotated_clockwise",
            "size": {
                "width": face_size * 3,
                "height": face_size * 4,
            },
            "face_cells": {
                "py": {"column": 2, "row": 1},
                "nx": {"column": 1, "row": 0},
                "pz": {"column": 1, "row": 1},
                "px": {"column": 1, "row": 2},
                "nz": {"column": 1, "row": 3},
                "ny": {"column": 0, "row": 1},
            },
            "maps": [f"quad_sphere/{name}_cubemap_cross.png" for name in selected],
            "empty_cells": {
                "all_maps": "transparent alpha 0",
            },
        },
        "face_vectors": {
            "px": "normalize(vec3( 1,  v, -u))",
            "nx": "normalize(vec3(-1,  v,  u))",
            "py": "normalize(vec3( u,  1, -v))",
            "ny": "normalize(vec3( u, -1,  v))",
            "pz": "normalize(vec3( u,  v,  1))",
            "nz": "normalize(vec3(-u,  v, -1))",
        },
        "uv_range": {
            "u": "left to right, -1 to 1, sampled at pixel centers",
            "v": "bottom to top, -1 to 1, sampled at pixel centers; image row 0 is near v=1",
        },
        "normal_map": {
            "space": "per-face tangent space",
            "channels": "RGB = XYZ remapped from -1..1 to 0..255",
            "green_channel": "positive Y points toward lower image rows",
        },
    }
    (out_dir / "quad_sphere_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def write_html_preview(out_dir, title, map_names=None):
    map_figures = "\n".join(
        f'    <figure><img src="{name}.png"><figcaption>{name}.png</figcaption></figure>'
        for name in selected_texture_maps(map_names)
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body {{ margin: 0; background: #101116; color: #e8e8e8; font: 14px system-ui, sans-serif; }}
main {{ display: grid; grid-template-columns: minmax(320px, 520px) 1fr; gap: 24px; padding: 24px; align-items: start; }}
canvas {{ width: 100%; max-width: 520px; aspect-ratio: 1; background: #05070b; }}
img {{ max-width: 100%; height: auto; background: #05070b; }}
.maps {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }}
figure {{ margin: 0; }}
figcaption {{ margin: 6px 0 14px; color: #b9bcc6; }}
</style>
</head>
<body>
<main>
  <section>
    <canvas id="globe" width="720" height="720"></canvas>
    <figcaption>Interactive rotating globe preview from color.png</figcaption>
  </section>
  <section class="maps">
    <figure><img src="preview.png"><figcaption>preview.png</figcaption></figure>
{map_figures}
  </section>
</main>
<script>
const canvas = document.getElementById('globe');
const ctx = canvas.getContext('2d');
const texture = new Image();
texture.src = 'color.png';
let texCanvas = document.createElement('canvas');
let texCtx = texCanvas.getContext('2d');
let texData = null;
let angle = 0;
texture.onload = () => {{
  texCanvas.width = texture.width;
  texCanvas.height = texture.height;
  texCtx.drawImage(texture, 0, 0);
  texData = texCtx.getImageData(0, 0, texture.width, texture.height).data;
  requestAnimationFrame(draw);
}};
function sample(u, v) {{
  const x = ((u % texture.width) + texture.width) % texture.width;
  const y = Math.max(0, Math.min(texture.height - 1, v));
  const i = (y * texture.width + x) * 4;
  return [texData[i], texData[i+1], texData[i+2]];
}}
function draw() {{
  if (!texData) return;
  const w = canvas.width, h = canvas.height, r = w * 0.43;
  const image = ctx.createImageData(w, h);
  const light = [-0.48, 0.36, 0.80];
  for (let py = 0; py < h; py++) {{
    const sy = 1 - (py / (h - 1)) * 2;
    for (let px = 0; px < w; px++) {{
      const sx = (px / (w - 1)) * 2 - 1;
      const rr = sx*sx + sy*sy;
      const idx = (py*w + px) * 4;
      if (rr > 0.76) {{
        image.data[idx+3] = 255;
        continue;
      }}
      const z = Math.sqrt(0.76 - rr) / Math.sqrt(0.76);
      const nx = sx / Math.sqrt(0.76), ny = sy / Math.sqrt(0.76), nz = z;
      const lon = Math.atan2(nx, nz) + angle;
      const lat = Math.asin(Math.max(-1, Math.min(1, ny)));
      const u = Math.floor((lon + Math.PI) / (Math.PI * 2) * texture.width);
      const v = Math.floor((Math.PI / 2 - lat) / Math.PI * texture.height);
      const c = sample(u, v);
      const shade = Math.max(0, nx*light[0] + ny*light[1] + nz*light[2]) * 0.95 + 0.16;
      const rim = Math.max(0, Math.min(1, (1 - z) * 1.6));
      image.data[idx] = Math.min(255, c[0] * shade + 50 * rim);
      image.data[idx+1] = Math.min(255, c[1] * shade + 90 * rim);
      image.data[idx+2] = Math.min(255, c[2] * shade + 135 * rim);
      image.data[idx+3] = 255;
    }}
  }}
  ctx.putImageData(image, 0, 0);
  angle += 0.004;
  requestAnimationFrame(draw);
}}
</script>
</body>
</html>
"""
    (out_dir / "preview.html").write_text(html, encoding="utf-8")


def config_from_args(args):
    data = dict(PRESETS[args.preset])
    for key in list(data):
        value = getattr(args, key, None)
        if value is not None:
            data[key] = value
    return PlanetConfig(
        preset=args.preset,
        seed=args.seed,
        width=args.width,
        height=args.height,
        **data,
    )


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Generate standalone rocky/ocean planet texture maps.")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="earthlike")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--width", type=int, default=2048)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--quad-sphere", action="store_true", help="Write six quad-sphere face folders instead of equirectangular maps.")
    parser.add_argument("--face-size", type=int, default=None, help="Quad-sphere face size in pixels. Defaults to min(width, height).")
    parser.add_argument("--out", type=Path, default=Path("planet_output"))
    for key, value in PRESETS["earthlike"].items():
        if key == "land_palette":
            parser.add_argument(
                f"--{key.replace('_', '-')}",
                dest=key,
                choices=sorted(LAND_PALETTES),
                default=None,
            )
            continue
        if isinstance(value, str):
            parser.add_argument(f"--{key.replace('_', '-')}", dest=key, type=str, default=None)
            continue
        arg_type = int if isinstance(value, int) else float
        parser.add_argument(f"--{key.replace('_', '-')}", dest=key, type=arg_type, default=None)
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    cfg = config_from_args(args)
    if cfg.width < 64 or cfg.height < 32:
        raise SystemExit("Width must be at least 64 and height must be at least 32.")
    face_size = args.face_size if args.face_size is not None else min(cfg.width, cfg.height)
    if args.quad_sphere and face_size < 32:
        raise SystemExit("Quad-sphere face size must be at least 32.")

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.quad_sphere:
        quad_dir = out_dir / "quad_sphere"
        quad_dir.mkdir(parents=True, exist_ok=True)
        quad_faces = build_quad_sphere_maps(cfg, face_size)
        for face, maps in quad_faces.items():
            face_dir = quad_dir / face
            face_dir.mkdir(parents=True, exist_ok=True)
            save_map_set(face_dir, maps)
        save_quad_sphere_cubemap_crosses(quad_dir, quad_faces, face_size)
        write_quad_sphere_manifest(out_dir, face_size)
    else:
        maps = build_maps(cfg)
        save_map_set(out_dir, maps)
        render_globe_preview(maps["color"], maps["height"], out_dir / "preview.png")
        write_html_preview(out_dir, f"{cfg.preset} planet preview")

    metadata = asdict(cfg)
    metadata["output_projection"] = "quad_sphere" if args.quad_sphere else "equirectangular"
    if args.quad_sphere:
        metadata["quad_sphere_face_size"] = face_size
    resolved_palette = vary_palette(cfg.seed, cfg.preset, cfg.land_palette)
    resolved_palette.update(ocean_colors_from_base(cfg.ocean_base_color))
    metadata["resolved_palette_rgb"] = {
        name: [int(round(channel)) for channel in color]
        for name, color in resolved_palette.items()
    }
    (out_dir / "preset.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote planet maps to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
