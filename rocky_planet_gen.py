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
import cProfile
import colorsys
import json
import math
import os
import pstats
import struct
import zlib
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None


PLANET_FAMILIES = {
    "wet_terrestrial": "Wet Terrestrial",
    "arid_terrestrial": "Arid Terrestrial",
    "frozen_world": "Frozen World",
    "airless_rocky": "Airless Rocky",
    "icy_moon": "Icy Moon",
    "volcanic_world": "Volcanic World",
    "iron_rich": "Iron Rich",
    "carbon_world": "Carbon World",
    "clouded_greenhouse": "Clouded Greenhouse",
    "tidally_locked": "Tidally Locked",
}


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
        "mountain_density": 0.52,
        "mountain_scale": 16.0,
        "mountain_sharpness": 0.76,
        "mountain_height": 0.84,
        "mountain_boundary_alignment": 0.55,
        "crater_density": 0.0,
        "crater_min_radius": 0.010,
        "crater_max_radius": 0.085,
        "crater_depth": 0.65,
        "crater_rim_height": 0.55,
        "crater_rim_width": 0.14,
        "crater_erosion": 0.25,
        "crater_land_bias": 0.85,
        "crater_color_strength": 0.45,
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
        "mountain_density": 0.44,
        "mountain_scale": 20.0,
        "mountain_sharpness": 0.64,
        "mountain_height": 0.58,
        "mountain_boundary_alignment": 0.45,
        "crater_density": 0.0,
        "crater_min_radius": 0.008,
        "crater_max_radius": 0.060,
        "crater_depth": 0.48,
        "crater_rim_height": 0.40,
        "crater_rim_width": 0.12,
        "crater_erosion": 0.38,
        "crater_land_bias": 0.88,
        "crater_color_strength": 0.32,
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
        "cloud_shadow_strength": 0.40,
        "cloud_shadow_softness": 0.30,
        "cloud_latitude_bias": 0.26,
        "cloud_band_strength": 0.30,
        "cloud_latitude_warp": 1.00,
        "cloud_hemisphere_imbalance": 1.00,
        "cloud_wind_stretch": 0.44,
        "cloud_breakup": 0.28,
        "storm_density": 0.34,
        "spiral_storm_strength": 0.20,
        "polar_cloud_strength": 0.06,
        "polar_cloud_asymmetry": 1.00,
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
        "mountain_density": 0.64,
        "mountain_scale": 11.0,
        "mountain_sharpness": 0.86,
        "mountain_height": 0.98,
        "mountain_boundary_alignment": 0.68,
        "crater_density": 0.0,
        "crater_min_radius": 0.010,
        "crater_max_radius": 0.095,
        "crater_depth": 0.68,
        "crater_rim_height": 0.58,
        "crater_rim_width": 0.16,
        "crater_erosion": 0.22,
        "crater_land_bias": 0.92,
        "crater_color_strength": 0.50,
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
        "cloud_shadow_strength": 0.30,
        "cloud_shadow_softness": 0.38,
        "cloud_latitude_bias": 0.08,
        "cloud_band_strength": 0.18,
        "cloud_latitude_warp": 1.00,
        "cloud_hemisphere_imbalance": 1.00,
        "cloud_wind_stretch": 0.28,
        "cloud_breakup": 0.42,
        "storm_density": 0.16,
        "spiral_storm_strength": 0.10,
        "polar_cloud_strength": 0.08,
        "polar_cloud_asymmetry": 1.00,
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
        "mountain_density": 0.70,
        "mountain_scale": 18.0,
        "mountain_sharpness": 0.92,
        "mountain_height": 1.05,
        "mountain_boundary_alignment": 0.60,
        "crater_density": 0.0,
        "crater_min_radius": 0.008,
        "crater_max_radius": 0.095,
        "crater_depth": 0.78,
        "crater_rim_height": 0.68,
        "crater_rim_width": 0.13,
        "crater_erosion": 0.18,
        "crater_land_bias": 0.96,
        "crater_color_strength": 0.66,
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
        "cloud_shadow_strength": 0.22,
        "cloud_shadow_softness": 0.44,
        "cloud_latitude_bias": -0.10,
        "cloud_band_strength": 0.12,
        "cloud_latitude_warp": 1.00,
        "cloud_hemisphere_imbalance": 1.00,
        "cloud_wind_stretch": 0.22,
        "cloud_breakup": 0.58,
        "storm_density": 0.08,
        "spiral_storm_strength": 0.04,
        "polar_cloud_strength": 0.02,
        "polar_cloud_asymmetry": 1.00,
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
        "mountain_density": 0.48,
        "mountain_scale": 13.0,
        "mountain_sharpness": 0.70,
        "mountain_height": 0.56,
        "mountain_boundary_alignment": 0.50,
        "crater_density": 0.0,
        "crater_min_radius": 0.010,
        "crater_max_radius": 0.070,
        "crater_depth": 0.52,
        "crater_rim_height": 0.44,
        "crater_rim_width": 0.12,
        "crater_erosion": 0.36,
        "crater_land_bias": 0.82,
        "crater_color_strength": 0.32,
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
        "cloud_shadow_strength": 0.34,
        "cloud_shadow_softness": 0.52,
        "cloud_latitude_bias": -0.32,
        "cloud_band_strength": 0.16,
        "cloud_latitude_warp": 1.00,
        "cloud_hemisphere_imbalance": 1.00,
        "cloud_wind_stretch": 0.30,
        "cloud_breakup": 0.20,
        "storm_density": 0.18,
        "spiral_storm_strength": 0.08,
        "polar_cloud_strength": 0.62,
        "polar_cloud_asymmetry": 1.00,
        "city_lights_strength": 0.30,
        "city_density": 0.16,
        "megacity_count": 4,
        "coastal_city_bias": 0.46,
        "inland_city_bias": 0.12,
        "city_sprawl": 0.20,
        "road_network_strength": 0.14,
        "light_temperature": 0.50,
    },
    "moon": {
        "land_coverage": 1.0,
        "continent_scale": 1.10,
        "continent_detail": 7,
        "continent_roughness": 0.56,
        "continent_contrast": 0.15,
        "shoreline_complexity": 0.0,
        "shoreline_noise_scale": 18.0,
        "shoreline_detail": 4,
        "shoreline_erosion": 0.0,
        "beach_width": 0.0,
        "shelf_width": 0.0,
        "island_density": 0.0,
        "island_scale": 34.0,
        "island_threshold": 0.90,
        "island_chain_strength": 0.0,
        "island_min_continent_distance": 0.0,
        "island_max_continent_distance": 0.0,
        "island_min_area": 0.0,
        "island_max_area": 0.0,
        "biome_scale": 9.0,
        "biome_complexity": 6,
        "desert_coverage": 0.62,
        "forest_coverage": 0.0,
        "mountain_density": 0.36,
        "mountain_scale": 13.0,
        "mountain_sharpness": 0.50,
        "mountain_height": 0.42,
        "mountain_boundary_alignment": 0.12,
        "crater_density": 0.78,
        "crater_min_radius": 0.004,
        "crater_max_radius": 0.115,
        "crater_depth": 0.86,
        "crater_rim_height": 0.80,
        "crater_rim_width": 0.18,
        "crater_erosion": 0.18,
        "crater_land_bias": 0.0,
        "crater_color_strength": 0.92,
        "crater_small_density": 0.88,
        "crater_medium_density": 0.78,
        "crater_large_basin_density": 0.58,
        "crater_ray_strength": 0.48,
        "crater_floor_darkening": 0.70,
        "crater_micro_pitting": 0.82,
        "moon_basin_strength": 0.62,
        "moon_basin_scale": 1.35,
        "moon_regolith_variation": 0.58,
        "polar_ice_size": 0.0,
        "polar_ice_scale": 2.15,
        "polar_ice_complexity": 0.0,
        "polar_ice_fragmentation": 0.0,
        "polar_ice_shelf_strength": 0.0,
        "polar_ice_solidity": 0.0,
        "snow_threshold": 1.0,
        "ocean_current_strength": 0.0,
        "land_palette": "lunar_gray",
        "land_color_variation": 0.18,
        "continent_color_variation": 0.30,
        "continent_color_scale": 1.80,
        "continent_color_diversity": 0.45,
        "continent_color_blend_smoothness": 0.78,
        "ocean_base_color": "#101010",
        "ocean_flat_color_strength": 0.0,
        "ocean_shelf_color": "#202020",
        "ocean_shelf_color_strength": 0.0,
        "ocean_color_variation": 0.0,
        "ocean_shallow_tint_strength": 0.0,
        "ocean_shelf_brightness": 0.0,
        "ocean_shelf_contrast": 1.0,
        "ocean_depth_tint_strength": 0.0,
        "ocean_latitude_tint_strength": 0.0,
        "ocean_productivity_strength": 0.0,
        "ocean_sediment_strength": 0.0,
        "ocean_brightness": 0.0,
        "ocean_contrast": 1.0,
        "ocean_hue_shift": 0.0,
        "ocean_saturation": 0.0,
        "ocean_colorizer_hue": 0.0,
        "ocean_colorizer_strength": 0.0,
        "land_brightness": -0.02,
        "land_contrast": 1.18,
        "mineral_tint_strength": 0.16,
        "wetland_tint_strength": 0.0,
        "iron_oxide_tint_strength": 0.0,
        "basalt_tint_strength": 0.36,
        "salt_flat_tint_strength": 0.0,
        "clay_tint_strength": 0.0,
        "cloud_coverage": 0.0,
        "cloud_scale": 1.0,
        "cloud_detail": 4,
        "cloud_roughness": 0.45,
        "cloud_softness": 0.20,
        "cloud_land_correlation": 0.0,
        "cloud_opacity": 0.0,
        "cloud_shadow_strength": 0.0,
        "cloud_shadow_softness": 0.0,
        "cloud_latitude_bias": 0.0,
        "cloud_band_strength": 0.0,
        "cloud_latitude_warp": 0.0,
        "cloud_hemisphere_imbalance": 0.0,
        "cloud_wind_stretch": 0.0,
        "cloud_breakup": 0.0,
        "storm_density": 0.0,
        "spiral_storm_strength": 0.0,
        "polar_cloud_strength": 0.0,
        "polar_cloud_asymmetry": 0.0,
        "city_lights_strength": 0.0,
        "city_density": 0.0,
        "megacity_count": 0,
        "coastal_city_bias": 0.0,
        "inland_city_bias": 0.0,
        "city_sprawl": 0.0,
        "road_network_strength": 0.0,
        "light_temperature": 0.50,
    },
}

PRESETS.update(
    {
        "marslike_desert": {
            **PRESETS["dry_rocky"],
            "land_coverage": 1.0,
            "continent_scale": 1.05,
            "continent_contrast": 0.16,
            "shoreline_complexity": 0.0,
            "beach_width": 0.0,
            "shelf_width": 0.0,
            "desert_coverage": 0.86,
            "forest_coverage": 0.0,
            "mountain_density": 0.48,
            "mountain_height": 0.52,
            "crater_density": 0.34,
            "crater_small_density": 0.28,
            "crater_medium_density": 0.18,
            "crater_large_basin_density": 0.08,
            "crater_erosion": 0.58,
            "crater_floor_darkening": 0.32,
            "polar_ice_size": 0.025,
            "polar_ice_shelf_strength": 0.0,
            "snow_threshold": 0.99,
            "land_palette": "red_desert",
            "land_lowland_color": "#9b4a22",
            "land_vegetation_color": "#7c3b22",
            "land_forest_color": "#4a2d26",
            "land_dry_color": "#b35d2d",
            "land_desert_color": "#c47035",
            "land_rock_color": "#6f5145",
            "land_beach_color": "#b98255",
            "land_snow_color": "#e8dfd0",
            "land_ice_color": "#d8d8ce",
            "land_color_variation": 0.42,
            "continent_color_variation": 0.62,
            "iron_oxide_tint_strength": 0.58,
            "basalt_tint_strength": 0.22,
            "salt_flat_tint_strength": 0.24,
            "clay_tint_strength": 0.24,
            "cloud_coverage": 0.05,
            "cloud_opacity": 0.18,
            "cloud_shadow_strength": 0.04,
            "city_lights_strength": 0.0,
            "city_density": 0.0,
            "megacity_count": 0,
            "road_network_strength": 0.0,
            "planet_family": "arid_terrestrial",
            "biosphere_strength": 0.0,
            "atmosphere_density": 0.28,
            "surface_age": 0.72,
            "geologic_activity": 0.24,
            "volatile_ice_strength": 0.08,
            "tidal_lock_strength": 0.0,
            "lava_activity": 0.0,
        },
        "icy_moon": {
            **PRESETS["moon"],
            "land_coverage": 1.0,
            "continent_scale": 1.40,
            "continent_detail": 6,
            "continent_contrast": 0.12,
            "mountain_density": 0.28,
            "mountain_height": 0.28,
            "crater_density": 0.48,
            "crater_small_density": 0.42,
            "crater_medium_density": 0.30,
            "crater_large_basin_density": 0.16,
            "crater_erosion": 0.42,
            "crater_color_strength": 0.38,
            "moon_basin_strength": 0.18,
            "moon_regolith_variation": 0.24,
            "polar_ice_size": 0.0,
            "land_palette": "cold_tundra",
            "land_lowland_color": "#aeb7b4",
            "land_vegetation_color": "#9caeb4",
            "land_forest_color": "#76888f",
            "land_dry_color": "#b7b4aa",
            "land_desert_color": "#c8c4b8",
            "land_rock_color": "#8b9292",
            "land_beach_color": "#c9d4d8",
            "land_snow_color": "#edf2ef",
            "land_ice_color": "#c7e4ec",
            "land_ochre_tint_color": "#b8b4a8",
            "land_rust_tint_color": "#928b82",
            "land_wet_tint_color": "#9eb8c0",
            "land_tundra_tint_color": "#b8d0d8",
            "land_highland_tint_color": "#d8d8ce",
            "land_iron_oxide_tint_color": "#aaa096",
            "land_basalt_tint_color": "#606a70",
            "land_salt_flat_tint_color": "#ecf0e8",
            "land_clay_tint_color": "#b4ada0",
            "land_solid_ice_tint_color": "#f4fbfb",
            "land_color_variation": 0.10,
            "continent_color_variation": 0.26,
            "land_brightness": 0.08,
            "land_contrast": 0.86,
            "mineral_tint_strength": 0.04,
            "basalt_tint_strength": 0.06,
            "cloud_coverage": 0.0,
            "city_lights_strength": 0.0,
            "planet_family": "icy_moon",
            "biosphere_strength": 0.0,
            "atmosphere_density": 0.0,
            "surface_age": 0.64,
            "geologic_activity": 0.18,
            "volatile_ice_strength": 0.92,
            "tidal_lock_strength": 0.0,
            "lava_activity": 0.0,
        },
        "volcanic_moon": {
            **PRESETS["moon"],
            "land_coverage": 1.0,
            "continent_scale": 0.90,
            "continent_detail": 8,
            "continent_roughness": 0.70,
            "continent_contrast": 0.18,
            "mountain_density": 0.78,
            "mountain_scale": 18.0,
            "mountain_sharpness": 0.86,
            "mountain_height": 0.82,
            "crater_density": 0.22,
            "crater_small_density": 0.16,
            "crater_medium_density": 0.10,
            "crater_large_basin_density": 0.04,
            "crater_erosion": 0.62,
            "crater_color_strength": 0.42,
            "moon_basin_strength": 0.10,
            "moon_regolith_variation": 0.18,
            "land_palette": "basaltic_dark",
            "land_lowland_color": "#2e2d27",
            "land_vegetation_color": "#463c24",
            "land_forest_color": "#1c1d1d",
            "land_dry_color": "#5a4626",
            "land_desert_color": "#8c6028",
            "land_rock_color": "#27292a",
            "land_beach_color": "#6b5f3a",
            "land_snow_color": "#d8d2bf",
            "land_ice_color": "#777b78",
            "land_ochre_tint_color": "#9a6c2c",
            "land_rust_tint_color": "#7a2c20",
            "land_wet_tint_color": "#343128",
            "land_tundra_tint_color": "#575141",
            "land_highland_tint_color": "#8d7f5a",
            "land_iron_oxide_tint_color": "#a33b1f",
            "land_basalt_tint_color": "#121416",
            "land_salt_flat_tint_color": "#c7ba88",
            "land_clay_tint_color": "#8e5632",
            "land_solid_ice_tint_color": "#cfcab8",
            "land_color_variation": 0.34,
            "continent_color_variation": 0.50,
            "land_brightness": -0.04,
            "land_contrast": 1.28,
            "mineral_tint_strength": 0.18,
            "iron_oxide_tint_strength": 0.34,
            "basalt_tint_strength": 0.78,
            "salt_flat_tint_strength": 0.10,
            "clay_tint_strength": 0.06,
            "cloud_coverage": 0.0,
            "city_lights_strength": 0.0,
            "planet_family": "volcanic_world",
            "biosphere_strength": 0.0,
            "atmosphere_density": 0.08,
            "surface_age": 0.34,
            "geologic_activity": 0.92,
            "volatile_ice_strength": 0.0,
            "tidal_lock_strength": 0.0,
            "lava_activity": 0.74,
        },
        "iron_desert": {
            **PRESETS["dry_rocky"],
            "land_coverage": 1.0,
            "desert_coverage": 0.78,
            "forest_coverage": 0.0,
            "polar_ice_size": 0.0,
            "snow_threshold": 1.0,
            "land_palette": "red_desert",
            "land_lowland_color": "#92351f",
            "land_vegetation_color": "#7a2d1d",
            "land_forest_color": "#4a241c",
            "land_dry_color": "#aa4624",
            "land_desert_color": "#c85b2d",
            "land_rock_color": "#5d3f37",
            "land_beach_color": "#9a6648",
            "land_snow_color": "#ddd4c8",
            "land_ice_color": "#c8c4bc",
            "iron_oxide_tint_strength": 0.72,
            "basalt_tint_strength": 0.28,
            "cloud_coverage": 0.0,
            "city_lights_strength": 0.0,
            "planet_family": "iron_rich",
            "biosphere_strength": 0.0,
            "atmosphere_density": 0.10,
            "surface_age": 0.58,
            "geologic_activity": 0.34,
            "volatile_ice_strength": 0.0,
            "tidal_lock_strength": 0.0,
            "lava_activity": 0.02,
        },
        "carbon_world": {
            **PRESETS["dry_rocky"],
            "land_coverage": 1.0,
            "desert_coverage": 0.58,
            "forest_coverage": 0.0,
            "polar_ice_size": 0.0,
            "snow_threshold": 1.0,
            "land_palette": "basaltic_dark",
            "land_lowland_color": "#242626",
            "land_vegetation_color": "#2d3433",
            "land_forest_color": "#111414",
            "land_dry_color": "#34302c",
            "land_desert_color": "#4a4038",
            "land_rock_color": "#171819",
            "land_beach_color": "#56524a",
            "land_snow_color": "#9a9a92",
            "land_ice_color": "#6a7070",
            "land_ochre_tint_color": "#4c473e",
            "land_rust_tint_color": "#3e302c",
            "land_wet_tint_color": "#182020",
            "land_tundra_tint_color": "#3c4646",
            "land_highland_tint_color": "#5d5c56",
            "land_iron_oxide_tint_color": "#493028",
            "land_basalt_tint_color": "#08090a",
            "land_salt_flat_tint_color": "#8a8678",
            "land_clay_tint_color": "#504038",
            "land_solid_ice_tint_color": "#aaa8a0",
            "land_brightness": -0.10,
            "land_contrast": 1.30,
            "mineral_tint_strength": 0.08,
            "basalt_tint_strength": 0.62,
            "cloud_coverage": 0.0,
            "city_lights_strength": 0.0,
            "planet_family": "carbon_world",
            "biosphere_strength": 0.0,
            "atmosphere_density": 0.18,
            "surface_age": 0.52,
            "geologic_activity": 0.32,
            "volatile_ice_strength": 0.0,
            "tidal_lock_strength": 0.0,
            "lava_activity": 0.04,
        },
        "clouded_greenhouse": {
            **PRESETS["frozen_ocean"],
            "land_coverage": 0.24,
            "desert_coverage": 0.62,
            "forest_coverage": 0.0,
            "polar_ice_size": 0.0,
            "land_palette": "pale_sedimentary",
            "ocean_base_color": "#263439",
            "ocean_saturation": 0.44,
            "ocean_brightness": -0.06,
            "ocean_contrast": 0.78,
            "wetland_tint_strength": 0.0,
            "cloud_coverage": 0.92,
            "cloud_scale": 0.82,
            "cloud_detail": 6,
            "cloud_softness": 0.42,
            "cloud_land_correlation": 0.08,
            "cloud_opacity": 0.96,
            "cloud_shadow_strength": 0.58,
            "cloud_band_strength": 0.52,
            "cloud_breakup": 0.10,
            "storm_density": 0.10,
            "polar_cloud_strength": 0.28,
            "city_lights_strength": 0.0,
            "planet_family": "clouded_greenhouse",
            "biosphere_strength": 0.0,
            "atmosphere_density": 1.0,
            "surface_age": 0.40,
            "geologic_activity": 0.36,
            "volatile_ice_strength": 0.0,
            "tidal_lock_strength": 0.0,
            "lava_activity": 0.0,
        },
        "tidally_locked_rocky": {
            **PRESETS["dry_rocky"],
            "land_coverage": 1.0,
            "desert_coverage": 0.72,
            "forest_coverage": 0.0,
            "polar_ice_size": 0.0,
            "land_palette": "alien_mineral",
            "cloud_coverage": 0.18,
            "cloud_opacity": 0.42,
            "cloud_shadow_strength": 0.10,
            "city_lights_strength": 0.0,
            "planet_family": "tidally_locked",
            "biosphere_strength": 0.0,
            "atmosphere_density": 0.36,
            "surface_age": 0.46,
            "geologic_activity": 0.30,
            "volatile_ice_strength": 0.20,
            "tidal_lock_strength": 0.86,
            "lava_activity": 0.0,
        },
    }
)

PRESETS["earthlike"].update(
    planet_family="wet_terrestrial",
    biosphere_strength=1.0,
    atmosphere_density=0.72,
    surface_age=0.42,
    geologic_activity=0.48,
    plate_boundary_strength=0.78,
    peak_prominence=0.70,
    erosion_strength=0.42,
    volatile_ice_strength=0.0,
    tidal_lock_strength=0.0,
    lava_activity=0.0,
)
PRESETS["archipelago"].update(
    planet_family="wet_terrestrial",
    biosphere_strength=1.0,
    atmosphere_density=0.78,
    surface_age=0.36,
    geologic_activity=0.50,
    plate_boundary_strength=0.66,
    peak_prominence=0.58,
    erosion_strength=0.50,
    volatile_ice_strength=0.0,
    tidal_lock_strength=0.0,
    lava_activity=0.0,
)
PRESETS["supercontinent"].update(
    planet_family="arid_terrestrial",
    biosphere_strength=0.56,
    atmosphere_density=0.64,
    surface_age=0.48,
    geologic_activity=0.46,
    plate_boundary_strength=0.90,
    peak_prominence=0.84,
    erosion_strength=0.36,
    volatile_ice_strength=0.0,
    tidal_lock_strength=0.0,
    lava_activity=0.0,
)
PRESETS["dry_rocky"].update(
    planet_family="arid_terrestrial",
    biosphere_strength=0.18,
    atmosphere_density=0.46,
    surface_age=0.54,
    geologic_activity=0.42,
    plate_boundary_strength=0.92,
    peak_prominence=0.86,
    erosion_strength=0.28,
    volatile_ice_strength=0.0,
    tidal_lock_strength=0.0,
    lava_activity=0.0,
)
PRESETS["frozen_ocean"].update(
    planet_family="frozen_world",
    biosphere_strength=0.08,
    atmosphere_density=0.62,
    surface_age=0.40,
    geologic_activity=0.26,
    plate_boundary_strength=0.58,
    peak_prominence=0.48,
    erosion_strength=0.58,
    volatile_ice_strength=0.70,
    tidal_lock_strength=0.0,
    lava_activity=0.0,
)
PRESETS["moon"].update(
    planet_family="airless_rocky",
    biosphere_strength=0.0,
    atmosphere_density=0.0,
    surface_age=0.86,
    geologic_activity=0.06,
    plate_boundary_strength=0.18,
    peak_prominence=0.26,
    erosion_strength=0.10,
    volatile_ice_strength=0.0,
    tidal_lock_strength=0.0,
    lava_activity=0.0,
)
PRESETS["marslike_desert"].update(plate_boundary_strength=0.70, peak_prominence=0.56, erosion_strength=0.54)
PRESETS["icy_moon"].update(plate_boundary_strength=0.12, peak_prominence=0.18, erosion_strength=0.16)
PRESETS["volcanic_moon"].update(plate_boundary_strength=0.74, peak_prominence=0.74, erosion_strength=0.18)
PRESETS["iron_desert"].update(plate_boundary_strength=0.88, peak_prominence=0.82, erosion_strength=0.26)
PRESETS["carbon_world"].update(plate_boundary_strength=0.84, peak_prominence=0.76, erosion_strength=0.22)
PRESETS["clouded_greenhouse"].update(plate_boundary_strength=0.52, peak_prominence=0.46, erosion_strength=0.60)
PRESETS["tidally_locked_rocky"].update(plate_boundary_strength=0.78, peak_prominence=0.68, erosion_strength=0.30)


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


def hex_from_rgb(value) -> str:
    rgb = np.clip(np.array(value, dtype=np.float32), 0.0, 255.0).astype(np.uint8)
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


LAND_PALETTE_LABELS = {
    "natural_earth": "Natural Earth",
    "lush_green": "Lush Green",
    "dry_savanna": "Dry Savanna",
    "red_desert": "Red Desert",
    "basaltic_dark": "Basaltic Dark",
    "pale_sedimentary": "Pale Sedimentary",
    "cold_tundra": "Cold Tundra",
    "alien_mineral": "Alien Mineral",
    "lunar_gray": "Lunar Gray",
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
    "lunar_gray": {
        "colors": {
            "beach": [128, 124, 116],
            "dark_forest": [58, 58, 58],
            "forest": [84, 84, 80],
            "grass": [112, 110, 104],
            "dry_plain": [136, 132, 122],
            "desert": [154, 148, 134],
            "rock": [92, 90, 86],
            "snow": [188, 184, 172],
            "ice": [104, 104, 104],
        },
        "region_tints": [
            [96, 96, 92],
            [126, 122, 112],
            [70, 70, 70],
            [150, 146, 134],
            [112, 108, 100],
            [82, 82, 78],
        ],
        "tints": {
            "ochre": [128, 120, 104],
            "rust": [104, 96, 88],
            "dark_wet": [70, 70, 68],
            "cool_tundra": [118, 120, 122],
            "pale_highland": [166, 160, 146],
            "iron_oxide": [110, 94, 82],
            "basalt": [42, 42, 42],
            "salt_flat": [178, 172, 156],
            "clay": [132, 122, 110],
            "solid_ice": [194, 190, 180],
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

CUSTOM_LAND_COLOR_FIELDS = {
    "grass": "land_lowland_color",
    "forest": "land_vegetation_color",
    "dark_forest": "land_forest_color",
    "dry_plain": "land_dry_color",
    "desert": "land_desert_color",
    "rock": "land_rock_color",
    "beach": "land_beach_color",
    "snow": "land_snow_color",
    "ice": "land_ice_color",
}

CUSTOM_TINT_COLOR_FIELDS = {
    "ochre": "land_ochre_tint_color",
    "rust": "land_rust_tint_color",
    "dark_wet": "land_wet_tint_color",
    "cool_tundra": "land_tundra_tint_color",
    "pale_highland": "land_highland_tint_color",
    "iron_oxide": "land_iron_oxide_tint_color",
    "basalt": "land_basalt_tint_color",
    "salt_flat": "land_salt_flat_tint_color",
    "clay": "land_clay_tint_color",
    "solid_ice": "land_solid_ice_tint_color",
}

LAND_COLOR_ACTIVE_BY_COUNT = {
    2: ("grass", "rock"),
    3: ("grass", "desert", "rock"),
    4: ("grass", "forest", "desert", "rock"),
    5: ("grass", "forest", "dry_plain", "desert", "rock"),
    6: ("grass", "forest", "dry_plain", "desert", "rock", "beach"),
    7: ("grass", "forest", "dark_forest", "dry_plain", "desert", "rock", "beach"),
    8: ("grass", "forest", "dark_forest", "dry_plain", "desert", "rock", "beach", "snow"),
    9: ("grass", "forest", "dark_forest", "dry_plain", "desert", "rock", "beach", "snow", "ice"),
}

LAND_COLOR_FALLBACKS = {
    "grass": ("forest", "dry_plain", "desert", "rock"),
    "forest": ("grass", "dark_forest", "dry_plain", "rock"),
    "dark_forest": ("forest", "grass", "rock"),
    "dry_plain": ("desert", "grass", "rock"),
    "desert": ("dry_plain", "rock", "grass"),
    "rock": ("desert", "dry_plain", "grass"),
    "beach": ("dry_plain", "desert", "rock", "grass"),
    "snow": ("ice", "rock", "beach", "grass"),
    "ice": ("snow", "rock", "beach", "grass"),
}

DEFAULT_REGION_TINT_COUNT = 6
MAX_REGION_TINT_COUNT = 8

NEBULA_DEFAULTS = {
    "nebula_intensity": 0.90,
    "nebula_coverage": 0.54,
    "nebula_scale": 1.10,
    "nebula_detail": 6,
    "nebula_roughness": 0.56,
    "nebula_warp": 1.00,
    "nebula_filament_strength": 0.62,
    "nebula_star_density": 0.34,
    "nebula_color_mix": 0.46,
    "nebula_color_softness": 0.55,
    "nebula_base_color": "#5e44be",
    "nebula_core_color": "#ff5e48",
    "nebula_accent_color": "#44b4cd",
}

CRATER_LAYER_DEFAULTS = {
    "crater_small_density": 0.0,
    "crater_medium_density": 0.0,
    "crater_large_basin_density": 0.0,
    "crater_ray_strength": 0.0,
    "crater_floor_darkening": 0.0,
    "crater_micro_pitting": 0.0,
}

TECTONIC_DEFAULTS = {
    "plate_boundary_strength": 0.72,
    "peak_prominence": 0.62,
    "erosion_strength": 0.38,
}

MOON_SURFACE_DEFAULTS = {
    "moon_basin_strength": 0.0,
    "moon_basin_scale": 1.0,
    "moon_regolith_variation": 0.0,
}

PLANET_FAMILY_DEFAULTS = {
    "planet_family": "wet_terrestrial",
    "biosphere_strength": 1.0,
    "atmosphere_density": 1.0,
    "surface_age": 0.45,
    "geologic_activity": 0.45,
    "volatile_ice_strength": 0.0,
    "tidal_lock_strength": 0.0,
    "lava_activity": 0.0,
}


def seed_custom_palette_defaults() -> None:
    for values in PRESETS.values():
        values.setdefault("land_color_count", 9)
        values.setdefault("region_tint_count", DEFAULT_REGION_TINT_COUNT)
        for key, value in CRATER_LAYER_DEFAULTS.items():
            values.setdefault(key, value)
        for key, value in TECTONIC_DEFAULTS.items():
            values.setdefault(key, value)
        for key, value in MOON_SURFACE_DEFAULTS.items():
            values.setdefault(key, value)
        for key, value in NEBULA_DEFAULTS.items():
            values.setdefault(key, value)
        for key, value in PLANET_FAMILY_DEFAULTS.items():
            values.setdefault(key, value)
        apply_palette_defaults_to_config_values(values, values.get("land_palette", "natural_earth"), only_missing=True)


def apply_palette_defaults_to_config_values(values: dict, land_palette: str, only_missing: bool = False) -> None:
    palette = LAND_PALETTES[normalize_land_palette(land_palette)]
    for source_key, config_key in CUSTOM_LAND_COLOR_FIELDS.items():
        if not only_missing or config_key not in values:
            values[config_key] = hex_from_rgb(palette["colors"][source_key])
    for source_key, config_key in CUSTOM_TINT_COLOR_FIELDS.items():
        if not only_missing or config_key not in values:
            values[config_key] = hex_from_rgb(palette["tints"][source_key])


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


def apply_custom_land_colors(colors: dict[str, np.ndarray], cfg) -> dict[str, np.ndarray]:
    custom = dict(colors)
    for source_key, config_key in CUSTOM_LAND_COLOR_FIELDS.items():
        custom[source_key] = rgb_from_hex(getattr(cfg, config_key))
    return custom


def reduce_land_color_count(colors: dict[str, np.ndarray], cfg) -> dict[str, np.ndarray]:
    count = int(np.clip(int(getattr(cfg, "land_color_count", 9)), 2, 9))
    active = set(LAND_COLOR_ACTIVE_BY_COUNT[count])
    reduced = dict(colors)
    for source_key in CUSTOM_LAND_COLOR_FIELDS:
        if source_key in active:
            continue
        for fallback_key in LAND_COLOR_FALLBACKS[source_key]:
            if fallback_key in active:
                reduced[source_key] = reduced[fallback_key]
                break
    return reduced


def resolve_planet_colors(cfg) -> dict[str, np.ndarray]:
    colors = vary_palette(cfg.seed, cfg.preset, cfg.land_palette)
    colors.update(ocean_colors_from_base(cfg.ocean_base_color))
    colors = apply_custom_land_colors(colors, cfg)
    return reduce_land_color_count(colors, cfg)


def resolve_land_tints(cfg) -> dict[str, np.ndarray]:
    tints = {
        key: value.copy()
        for key, value in land_palette_values(cfg.land_palette)["tints"].items()
    }
    for source_key, config_key in CUSTOM_TINT_COLOR_FIELDS.items():
        tints[source_key] = rgb_from_hex(getattr(cfg, config_key))
    return tints


def resolve_region_tints(cfg) -> np.ndarray:
    base_tints = land_palette_values(cfg.land_palette)["region_tints"]
    custom_sources = [
        "land_lowland_color",
        "land_dry_color",
        "land_desert_color",
        "land_rock_color",
        "land_vegetation_color",
        "land_beach_color",
        "land_forest_color",
        "land_highland_tint_color",
    ]
    custom_tints = np.array([rgb_from_hex(getattr(cfg, key)) for key in custom_sources], dtype=np.float32)
    count = int(np.clip(int(getattr(cfg, "region_tint_count", DEFAULT_REGION_TINT_COUNT)), 0, MAX_REGION_TINT_COUNT))
    if count <= 0:
        return np.empty((0, 3), dtype=np.float32)
    if count <= len(custom_tints):
        return custom_tints[:count]
    return base_tints[: min(count, len(base_tints))]


seed_custom_palette_defaults()


@dataclass
class PlanetConfig:
    preset: str
    seed: int
    width: int
    height: int
    planet_family: str
    biosphere_strength: float
    atmosphere_density: float
    surface_age: float
    geologic_activity: float
    volatile_ice_strength: float
    tidal_lock_strength: float
    lava_activity: float
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
    mountain_boundary_alignment: float
    plate_boundary_strength: float
    peak_prominence: float
    erosion_strength: float
    crater_density: float
    crater_min_radius: float
    crater_max_radius: float
    crater_depth: float
    crater_rim_height: float
    crater_rim_width: float
    crater_erosion: float
    crater_land_bias: float
    crater_color_strength: float
    crater_small_density: float
    crater_medium_density: float
    crater_large_basin_density: float
    crater_ray_strength: float
    crater_floor_darkening: float
    crater_micro_pitting: float
    moon_basin_strength: float
    moon_basin_scale: float
    moon_regolith_variation: float
    polar_ice_size: float
    polar_ice_scale: float
    polar_ice_complexity: float
    polar_ice_fragmentation: float
    polar_ice_shelf_strength: float
    polar_ice_solidity: float
    snow_threshold: float
    ocean_current_strength: float
    land_palette: str
    land_color_count: int
    region_tint_count: int
    land_lowland_color: str
    land_vegetation_color: str
    land_forest_color: str
    land_dry_color: str
    land_desert_color: str
    land_rock_color: str
    land_beach_color: str
    land_snow_color: str
    land_ice_color: str
    land_ochre_tint_color: str
    land_rust_tint_color: str
    land_wet_tint_color: str
    land_tundra_tint_color: str
    land_highland_tint_color: str
    land_iron_oxide_tint_color: str
    land_basalt_tint_color: str
    land_salt_flat_tint_color: str
    land_clay_tint_color: str
    land_solid_ice_tint_color: str
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
    cloud_shadow_strength: float
    cloud_shadow_softness: float
    cloud_latitude_bias: float
    cloud_band_strength: float
    cloud_latitude_warp: float
    cloud_hemisphere_imbalance: float
    cloud_wind_stretch: float
    cloud_breakup: float
    storm_density: float
    spiral_storm_strength: float
    polar_cloud_strength: float
    polar_cloud_asymmetry: float
    nebula_intensity: float
    nebula_coverage: float
    nebula_scale: float
    nebula_detail: int
    nebula_roughness: float
    nebula_warp: float
    nebula_filament_strength: float
    nebula_star_density: float
    nebula_color_mix: float
    nebula_color_softness: float
    nebula_base_color: str
    nebula_core_color: str
    nebula_accent_color: str
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


def build_mountain_range_bands(x, y, z, cfg):
    density = float(np.clip(cfg.mountain_density, 0.0, 1.0))
    range_count = int(round(4 + density * 5))
    width_base = 0.018 + density * 0.042
    rng = np.random.default_rng(int(cfg.seed) + 4051)
    bands = np.zeros(x.shape, dtype=np.float32)

    for _ in range(range_count):
        normal = rng.normal(size=3).astype(np.float32)
        normal /= max(1e-6, float(np.linalg.norm(normal)))
        tangent = rng.normal(size=3).astype(np.float32)
        tangent -= normal * float(np.dot(tangent, normal))
        tangent /= max(1e-6, float(np.linalg.norm(tangent)))
        bitangent = np.cross(normal, tangent).astype(np.float32)
        bitangent /= max(1e-6, float(np.linalg.norm(bitangent)))

        plane = x * normal[0] + y * normal[1] + z * normal[2]
        arc_x = x * tangent[0] + y * tangent[1] + z * tangent[2]
        arc_y = x * bitangent[0] + y * bitangent[1] + z * bitangent[2]
        arc_angle = np.arctan2(arc_y, arc_x)
        center = float(rng.uniform(-math.pi, math.pi))
        half_length = float(rng.uniform(0.55, 1.35))
        arc_delta = np.arctan2(np.sin(arc_angle - center), np.cos(arc_angle - center))

        width = width_base * float(rng.uniform(0.72, 1.35))
        phase = float(rng.uniform(0.0, math.tau))
        meander = (
            np.sin(arc_angle * float(rng.uniform(1.4, 2.6)) + phase) * 0.62
            + np.sin(arc_angle * float(rng.uniform(3.2, 5.4)) - phase * 0.7) * 0.28
        ) * width
        distance = np.abs(plane + meander)
        core = 1.0 - smoothstep(width * 0.28, width, distance)
        length_gate = 1.0 - smoothstep(half_length, half_length + 0.45, np.abs(arc_delta))
        breakup = 0.42 + 0.58 * smoothstep(
            -0.28,
            0.72,
            np.sin(arc_angle * float(rng.uniform(4.5, 8.5)) + phase * 1.7)
            + np.sin(arc_angle * float(rng.uniform(8.0, 13.0)) - phase) * 0.35,
        )
        bands = np.maximum(bands, core * length_gate * breakup * float(rng.uniform(0.72, 1.0)))

    return np.clip(bands, 0.0, 1.0)


def build_plate_boundary_field(cfg, x, y, z, land):
    strength = float(np.clip(cfg.plate_boundary_strength, 0.0, 1.0))
    if strength <= 0.0:
        return np.zeros_like(x, dtype=np.float32)

    density = float(np.clip(cfg.mountain_density, 0.0, 1.0))
    sharpness = float(np.clip(cfg.mountain_sharpness, 0.0, 1.0))
    plate_count = int(np.clip(round(7.0 + cfg.continent_scale * 3.0 + density * 6.0), 7, 28))
    rng = np.random.default_rng(int(cfg.seed) + 4751)

    anchors = rng.normal(size=(plate_count, 3)).astype(np.float32)
    anchors /= np.linalg.norm(anchors, axis=1, keepdims=True)
    spin_axes = rng.normal(size=(plate_count, 3)).astype(np.float32)
    spin_axes /= np.linalg.norm(spin_axes, axis=1, keepdims=True)
    spin_axes *= rng.uniform(0.55, 1.35, size=(plate_count, 1)).astype(np.float32)

    warp_strength = 0.080 + strength * 0.300 + density * 0.060
    warp_scale = max(0.85, float(cfg.continent_scale) * 0.95)
    wx = x + (fbm_3d(x, y, z, warp_scale, 4, 0.54, cfg.seed + 4721) - 0.5) * warp_strength
    wy = y + (fbm_3d(x, y, z, warp_scale * 1.17, 4, 0.55, cfg.seed + 4733) - 0.5) * warp_strength
    wz = z + (fbm_3d(x, y, z, warp_scale * 0.83, 4, 0.54, cfg.seed + 4747) - 0.5) * warp_strength
    warp_len = np.sqrt(wx * wx + wy * wy + wz * wz)
    wx = wx / np.maximum(warp_len, 1e-6)
    wy = wy / np.maximum(warp_len, 1e-6)
    wz = wz / np.maximum(warp_len, 1e-6)

    best_score = np.full_like(x, -2.0, dtype=np.float32)
    second_score = np.full_like(x, -2.0, dtype=np.float32)
    best_id = np.zeros_like(x, dtype=np.int16)
    second_id = np.zeros_like(x, dtype=np.int16)
    for index, anchor in enumerate(anchors):
        score = wx * anchor[0] + wy * anchor[1] + wz * anchor[2]
        better = score > best_score
        between = (~better) & (score > second_score)
        second_score = np.where(better, best_score, np.where(between, score, second_score))
        second_id = np.where(better, best_id, np.where(between, index, second_id))
        best_score = np.where(better, score, best_score)
        best_id = np.where(better, index, best_id)

    margin = best_score - second_score
    boundary_width = 0.016 + strength * 0.028 + (1.0 - sharpness) * 0.020
    boundary = 1.0 - smoothstep(0.0025, boundary_width, margin)

    best_axis = [np.zeros_like(x, dtype=np.float32) for _ in range(3)]
    second_axis = [np.zeros_like(x, dtype=np.float32) for _ in range(3)]
    best_anchor = [np.zeros_like(x, dtype=np.float32) for _ in range(3)]
    second_anchor = [np.zeros_like(x, dtype=np.float32) for _ in range(3)]
    for index in range(plate_count):
        best_mask = best_id == index
        second_mask = second_id == index
        for component in range(3):
            best_axis[component] = np.where(best_mask, spin_axes[index, component], best_axis[component])
            second_axis[component] = np.where(second_mask, spin_axes[index, component], second_axis[component])
            best_anchor[component] = np.where(best_mask, anchors[index, component], best_anchor[component])
            second_anchor[component] = np.where(second_mask, anchors[index, component], second_anchor[component])

    best_vx = best_axis[1] * z - best_axis[2] * y
    best_vy = best_axis[2] * x - best_axis[0] * z
    best_vz = best_axis[0] * y - best_axis[1] * x
    second_vx = second_axis[1] * z - second_axis[2] * y
    second_vy = second_axis[2] * x - second_axis[0] * z
    second_vz = second_axis[0] * y - second_axis[1] * x
    rel_x = best_vx - second_vx
    rel_y = best_vy - second_vy
    rel_z = best_vz - second_vz

    sep_x = best_anchor[0] - second_anchor[0]
    sep_y = best_anchor[1] - second_anchor[1]
    sep_z = best_anchor[2] - second_anchor[2]
    sep_len = np.sqrt(sep_x * sep_x + sep_y * sep_y + sep_z * sep_z)
    compression = np.abs((rel_x * sep_x + rel_y * sep_y + rel_z * sep_z) / np.maximum(sep_len, 1e-6))
    compression = smoothstep(0.12, 0.84, normalize01(compression))

    boundary_detail = fbm_3d(
        x * 1.05 + 0.17,
        y * 0.92 - 0.11,
        z * 1.12 + 0.07,
        max(3.0, cfg.mountain_scale * 0.48),
        4,
        0.58,
        cfg.seed + 4789,
    )
    plate_boundary = boundary * (0.58 + compression * 0.42) * (0.72 + boundary_detail * 0.28)
    return np.clip(plate_boundary * strength * land.astype(np.float32), 0.0, 1.0)


def build_peak_and_erosion_fields(cfg, x, y, z, mountain_mask, plate_boundary):
    prominence = float(np.clip(cfg.peak_prominence, 0.0, 1.0))
    erosion = float(np.clip(cfg.erosion_strength, 0.0, 1.0))
    if prominence <= 0.0 and erosion <= 0.0:
        blank = np.zeros_like(x, dtype=np.float32)
        return blank, blank

    scale = max(3.0, float(cfg.mountain_scale))
    summit_spine = 1.0 - np.abs(
        fbm_3d(x * 1.09 - 0.13, y * 0.96 + 0.19, z * 1.04 + 0.05, scale * 1.75, 5, 0.64, cfg.seed + 4813) * 2.0
        - 1.0
    )
    summit_spine = np.power(np.clip(summit_spine, 0.0, 1.0), 1.55)
    summit_noise = fbm_3d(x, y, z, scale * 4.8 + 18.0, 4, 0.62, cfg.seed + 4831)
    peak_seed = mountain_mask * 0.64 + plate_boundary * 0.52 + summit_spine * 0.42 + summit_noise * 0.18
    peak_mask = smoothstep(0.66, 1.30, peak_seed) * prominence

    valley_spine = 1.0 - np.abs(
        fbm_3d(x * 0.94 + 0.31, y * 1.07 - 0.23, z * 1.02 + 0.14, scale * 2.6 + 8.0, 5, 0.60, cfg.seed + 4861) * 2.0
        - 1.0
    )
    valley_detail = fbm_3d(x, y, z, scale * 9.0 + 35.0, 3, 0.54, cfg.seed + 4877)
    valley_seed = valley_spine * 0.62 + valley_detail * 0.24 + plate_boundary * 0.24
    erosion_valleys = smoothstep(0.48, 0.92, valley_seed) * np.clip(mountain_mask + plate_boundary * 0.65, 0.0, 1.0) * erosion
    peak_mask *= 1.0 - erosion_valleys * 0.35
    return np.clip(peak_mask, 0.0, 1.0), np.clip(erosion_valleys, 0.0, 1.0)


def build_summit_spike_field(cfg, x, y, z, mountain_mask, plate_boundary):
    prominence = float(np.clip(cfg.peak_prominence, 0.0, 1.0))
    if prominence <= 0.0:
        return np.zeros_like(x, dtype=np.float32)

    density = float(np.clip(cfg.mountain_density, 0.0, 1.0))
    sharpness = float(np.clip(cfg.mountain_sharpness, 0.0, 1.0))
    map_height, map_width = x.shape
    crest_noise = fbm_3d(x * 1.17 - 0.09, y * 0.91 + 0.23, z * 1.08 + 0.11, max(22.0, cfg.mountain_scale * 5.0), 4, 0.60, cfg.seed + 4883)
    crest_micro = fbm_3d(x * 0.83 + 0.27, y * 1.19 - 0.16, z * 1.03 - 0.07, max(60.0, cfg.mountain_scale * 14.0), 3, 0.54, cfg.seed + 4887)
    ridge_source_raw = mountain_mask * 0.66 + plate_boundary * 0.48 + crest_noise * 0.22 + crest_micro * 0.14
    ridge_source = np.clip(ridge_source_raw, 0.0, 1.0)
    highland = ridge_source_raw > max(0.38, 0.64 - density * 0.18 - prominence * 0.08)

    if np.any(highland):
        crest_threshold = float(np.quantile(ridge_source_raw[highland], 0.970 - prominence * 0.020))
    else:
        crest_threshold = 0.74
    local_max = ridge_source_raw >= ndimage.maximum_filter(ridge_source_raw, size=(9, 9), mode=("nearest", "wrap"))
    summit_seeds = local_max & highland & (ridge_source_raw >= crest_threshold)
    if np.any(summit_seeds):
        distance = ndimage.distance_transform_edt(~summit_seeds).astype(np.float32)
        radius = max(1.8, min(map_height, map_width) * (0.006 + prominence * 0.006) * (1.08 - sharpness * 0.30))
        peak_cones = np.power(np.clip(1.0 - distance / radius, 0.0, 1.0), 1.9 + sharpness * 4.1)
    else:
        peak_cones = np.zeros_like(x, dtype=np.float32)

    serration = 1.0 - np.abs(fbm_3d(x * 1.07 + 0.18, y * 0.97 - 0.26, z * 1.13 + 0.09, max(75.0, cfg.mountain_scale * 18.0), 3, 0.58, cfg.seed + 4895) * 2.0 - 1.0)
    serration = np.power(np.clip(serration, 0.0, 1.0), 2.2 + sharpness * 3.8)
    crest_gate = smoothstep(crest_threshold * 0.96, min(1.0, crest_threshold + 0.18), ridge_source)
    jagged_crests = crest_gate * serration

    spike_count = int(np.clip(round(12.0 + prominence * 34.0 + density * 24.0), 8, 90))
    rng = np.random.default_rng(int(cfg.seed) + 4891)
    anchors = rng.normal(size=(spike_count, 3)).astype(np.float32)
    anchors /= np.linalg.norm(anchors, axis=1, keepdims=True)
    radii = rng.uniform(0.012, 0.034, size=spike_count).astype(np.float32)
    radii *= 1.08 - sharpness * 0.42
    strengths = rng.uniform(0.72, 1.20, size=spike_count).astype(np.float32)

    suitability = np.power(np.clip(ridge_source + plate_boundary * 0.22, 0.0, 1.0), 0.44)
    anchor_spikes = np.zeros_like(x, dtype=np.float32)
    exponent = 2.4 + sharpness * 4.6
    for anchor, radius, strength in zip(anchors, radii, strengths):
        dot = np.clip(x * anchor[0] + y * anchor[1] + z * anchor[2], -1.0, 1.0)
        shoulder = math.cos(float(radius) * 2.45)
        core = math.cos(float(radius) * 0.16)
        cone = smoothstep(shoulder, core, dot)
        cone = np.power(np.clip(cone, 0.0, 1.0), exponent)
        anchor_spikes = np.maximum(anchor_spikes, cone * suitability * float(strength))

    fracture = fbm_3d(x * 1.11 + 0.07, y * 0.93 - 0.17, z * 1.04 + 0.13, max(30.0, cfg.mountain_scale * 7.0), 3, 0.56, cfg.seed + 4909)
    cone_spikes = np.maximum(anchor_spikes * 0.66, peak_cones)
    ridge_teeth = jagged_crests * np.clip(peak_cones * 0.90 + anchor_spikes * 0.55 + plate_boundary * 0.18, 0.0, 1.0)
    spikes = np.maximum(cone_spikes, ridge_teeth * 0.74)
    spikes = np.maximum(spikes, jagged_crests * 0.46)
    spikes *= 0.78 + fracture * 0.22
    return np.clip(spikes * prominence, 0.0, 1.0)


def build_orogenic_mountain_system(cfg, x, y, z, land, plate_boundary):
    density = float(np.clip(cfg.mountain_density, 0.0, 1.0))
    prominence = float(np.clip(cfg.peak_prominence, 0.0, 1.0))
    sharpness = float(np.clip(cfg.mountain_sharpness, 0.0, 1.0))
    boundary_strength = float(np.clip(cfg.plate_boundary_strength, 0.0, 1.0))
    erosion = float(np.clip(cfg.erosion_strength, 0.0, 1.0))
    land_f = land.astype(np.float32)

    ridge_primary = 1.0 - np.abs(
        fbm_3d(x * 1.08 - 0.13, y * 0.94 + 0.17, z * 1.11 + 0.05, max(12.0, cfg.mountain_scale * 1.15), 6, 0.66, cfg.seed + 5011)
        * 2.0
        - 1.0
    )
    ridge_secondary = 1.0 - np.abs(
        fbm_3d(x * 0.91 + 0.27, y * 1.13 - 0.21, z * 1.02 + 0.19, max(28.0, cfg.mountain_scale * 3.1), 5, 0.62, cfg.seed + 5027)
        * 2.0
        - 1.0
    )
    crest_noise = fbm_3d(x * 1.21 + 0.05, y * 0.88 - 0.31, z * 1.09 + 0.16, max(60.0, cfg.mountain_scale * 8.0), 4, 0.57, cfg.seed + 5039)
    peak_train = 1.0 - np.abs(
        fbm_3d(x * 1.03 - 0.39, y * 1.17 + 0.24, z * 0.89 - 0.08, max(95.0, cfg.mountain_scale * 15.0), 3, 0.54, cfg.seed + 5051)
        * 2.0
        - 1.0
    )

    tectonic_core = smoothstep(0.12, 0.72, plate_boundary)
    range_breakup = smoothstep(0.24, 0.72, crest_noise)
    ridge_line = np.power(np.clip(ridge_primary, 0.0, 1.0), 1.3 + sharpness * 3.0)
    narrow_crest = np.power(np.clip(ridge_secondary * ridge_line, 0.0, 1.0), 1.6 + sharpness * 4.2)

    broken_core = tectonic_core * (0.34 + range_breakup * 0.66)
    uplift = broken_core * (0.56 + ridge_line * 0.34 + range_breakup * 0.22) * (0.70 + boundary_strength * 0.36)
    crest = broken_core * np.clip(narrow_crest * 1.45 + ridge_line * 0.26, 0.0, 1.0) * (0.66 + prominence * 0.42)
    peaks = crest * np.power(np.clip(peak_train, 0.0, 1.0), 4.5 + sharpness * 8.0) * smoothstep(0.30, 0.78, crest_noise)

    valley_noise = 1.0 - np.abs(
        fbm_3d(x * 0.86 + 0.19, y * 1.26 - 0.18, z * 1.07 + 0.33, max(44.0, cfg.mountain_scale * 7.0), 4, 0.59, cfg.seed + 5069)
        * 2.0
        - 1.0
    )
    valleys = tectonic_core * np.power(np.clip(valley_noise, 0.0, 1.0), 2.4) * smoothstep(0.26, 0.88, uplift) * erosion

    rng = np.random.default_rng(int(cfg.seed) + 5011)
    fragment_count = int(np.clip(round(density * 1.5 + boundary_strength * 1.5), 0, 3))
    fragment_uplift = np.zeros_like(x, dtype=np.float32)
    fragment_crest = np.zeros_like(x, dtype=np.float32)
    fragment_peaks = np.zeros_like(x, dtype=np.float32)
    for _ in range(fragment_count):
        normal = rng.normal(size=3).astype(np.float32)
        normal /= max(1e-6, float(np.linalg.norm(normal)))
        tangent = rng.normal(size=3).astype(np.float32)
        tangent -= normal * float(np.dot(tangent, normal))
        tangent /= max(1e-6, float(np.linalg.norm(tangent)))
        bitangent = np.cross(normal, tangent).astype(np.float32)
        bitangent /= max(1e-6, float(np.linalg.norm(bitangent)))

        plane = x * normal[0] + y * normal[1] + z * normal[2]
        arc_x = x * tangent[0] + y * tangent[1] + z * tangent[2]
        arc_y = x * bitangent[0] + y * bitangent[1] + z * bitangent[2]
        arc_angle = np.arctan2(arc_y, arc_x)
        center = float(rng.uniform(-math.pi, math.pi))
        arc_delta = np.arctan2(np.sin(arc_angle - center), np.cos(arc_angle - center))
        half_length = float(rng.uniform(0.55, 1.55))
        length_gate = 1.0 - smoothstep(half_length, half_length + 0.38, np.abs(arc_delta))

        width = (0.030 + density * 0.035 + boundary_strength * 0.018) * float(rng.uniform(0.70, 1.25))
        crest_width = width * (0.105 + (1.0 - sharpness) * 0.085)
        phase = float(rng.uniform(0.0, math.tau))
        meander = (
            np.sin(arc_angle * float(rng.uniform(1.3, 2.7)) + phase) * 0.58
            + np.sin(arc_angle * float(rng.uniform(3.7, 6.5)) - phase * 0.61) * 0.24
        ) * width
        signed_distance = plane + meander
        distance = np.abs(signed_distance)

        range_profile = np.exp(-np.power(distance / max(width, 1e-5), 1.5 + sharpness * 0.7))
        crest_profile = np.exp(-np.power(distance / max(crest_width, 1e-5), 1.8 + sharpness * 1.4))
        foothills = np.exp(-np.power(distance / max(width * 2.7, 1e-5), 1.05)) * 0.28

        along = arc_delta / max(half_length, 1e-5)
        peak_frequency = float(rng.uniform(9.0, 18.0) + prominence * 12.0 + density * 5.0)
        peak_train = 1.0 - np.abs(np.sin((along * peak_frequency + phase) * math.pi))
        peak_train = np.power(np.clip(peak_train, 0.0, 1.0), 5.0 + sharpness * 8.0)
        peak_breakup = fbm_3d(
            x * 1.08 + phase * 0.03,
            y * 0.91 - phase * 0.02,
            z * 1.13 + phase * 0.01,
            max(36.0, cfg.mountain_scale * 7.0),
            3,
            0.58,
            cfg.seed + int(abs(phase) * 1000.0) + 5039,
        )
        peak_chain = crest_profile * peak_train * smoothstep(0.28, 0.76, peak_breakup)

        fragment_gate = length_gate * smoothstep(0.35, 0.86, peak_breakup)
        range_strength = float(rng.uniform(0.20, 0.38)) * (0.55 + boundary_strength * 0.16)
        fragment_uplift = np.maximum(fragment_uplift, np.clip((range_profile + foothills) * fragment_gate * range_strength, 0.0, 0.34))
        fragment_crest = np.maximum(fragment_crest, np.clip(crest_profile * fragment_gate * range_strength, 0.0, 0.38))
        fragment_peaks = np.maximum(fragment_peaks, np.clip(peak_chain * fragment_gate * range_strength, 0.0, 0.48))

    uplift = np.clip(np.maximum(uplift, fragment_uplift * 0.22) * land_f, 0.0, 1.0)
    crest = np.clip(np.maximum(crest, fragment_crest * 0.28) * land_f, 0.0, 1.0)
    peaks = np.clip(np.maximum(peaks, fragment_peaks * 0.40) * land_f * prominence, 0.0, 1.0)
    valleys = np.clip(valleys * land_f, 0.0, 1.0)
    crags = fbm_3d(x * 1.31 - 0.14, y * 0.79 + 0.28, z * 1.17 + 0.09, max(95.0, cfg.mountain_scale * 21.0), 4, 0.61, cfg.seed + 5099)
    crags = (crags - 0.5) * np.clip(crest * 0.55 + peaks * 1.15, 0.0, 1.0)
    return {
        "uplift": uplift,
        "crest": crest,
        "peaks": peaks,
        "valleys": valleys,
        "crags": crags,
    }


def build_alpine_range_system(cfg, lat, lon, land):
    density = float(np.clip(cfg.mountain_density, 0.0, 1.0))
    prominence = float(np.clip(cfg.peak_prominence, 0.0, 1.0))
    sharpness = float(np.clip(cfg.mountain_sharpness, 0.0, 1.0))
    erosion = float(np.clip(cfg.erosion_strength, 0.0, 1.0))
    if density <= 0.0 or prominence <= 0.0:
        blank = np.zeros_like(lat, dtype=np.float32)
        return {"uplift": blank, "crest": blank, "peaks": blank, "valleys": blank, "crags": blank}

    rng = np.random.default_rng(int(cfg.seed) + 5311)
    range_count = int(np.clip(round(3.0 + density * 6.0), 3, 10))
    uplift = np.zeros_like(lat, dtype=np.float32)
    crest = np.zeros_like(lat, dtype=np.float32)
    peaks = np.zeros_like(lat, dtype=np.float32)
    valleys = np.zeros_like(lat, dtype=np.float32)
    crags = np.zeros_like(lat, dtype=np.float32)
    land_f = land.astype(np.float32)

    for _ in range(range_count):
        center_lon = float(rng.uniform(-math.pi, math.pi))
        center_lat = float(rng.uniform(-0.92, 0.92))
        orientation = float(rng.uniform(-math.pi, math.pi))
        half_length = float(rng.uniform(0.36, 0.86) * (0.88 + density * 0.30))
        width = float(rng.uniform(0.105, 0.225) * (1.08 - sharpness * 0.16))
        crest_width = width * float(0.38 + (1.0 - sharpness) * 0.10)
        phase = float(rng.uniform(0.0, math.tau))

        dlon = np.arctan2(np.sin(lon - center_lon), np.cos(lon - center_lon)) * max(0.20, math.cos(center_lat))
        dlat = lat - center_lat
        along = dlon * math.cos(orientation) + dlat * math.sin(orientation)
        across = -dlon * math.sin(orientation) + dlat * math.cos(orientation)

        length_gate = 1.0 - smoothstep(half_length * 0.78, half_length, np.abs(along))
        meander = (
            np.sin(along / max(half_length, 1e-5) * math.pi * float(rng.uniform(0.85, 1.85)) + phase) * 0.42
            + np.sin(along / max(half_length, 1e-5) * math.pi * float(rng.uniform(2.1, 3.8)) - phase * 0.47) * 0.18
        ) * width
        signed_dist = across - meander
        dist = np.abs(signed_dist)
        massif_profile = np.exp(-np.power(dist / max(width, 1e-5), 1.18 + sharpness * 0.24))
        foothill_profile = np.exp(-np.power(dist / max(width * 2.9, 1e-5), 1.02)) * 0.18
        crest_profile = np.exp(-np.power(dist / max(crest_width, 1e-5), 1.34 + sharpness * 0.72))
        texture_gate = smoothstep(0.22, 0.82, fbm_3d(
            np.cos(lon + phase * 0.05) * np.cos(lat),
            np.sin(lat - phase * 0.03),
            np.sin(lon - phase * 0.04) * np.cos(lat),
            max(10.0, cfg.mountain_scale * 1.8),
            4,
            0.57,
            cfg.seed + int(phase * 1000.0) + 5369,
        ))
        body_profile = np.clip(massif_profile * (0.78 + texture_gate * 0.16), 0.0, 1.0)

        cluster_noise = smoothstep(0.28, 0.84, fbm_3d(
            np.cos(lon + phase * 0.11) * np.cos(lat),
            np.sin(lat - phase * 0.05),
            np.sin(lon - phase * 0.07) * np.cos(lat),
            max(18.0, cfg.mountain_scale * 3.2),
            4,
            0.58,
            cfg.seed + int(phase * 1000.0) + 5389,
        ))
        peak_profile = np.zeros_like(lat, dtype=np.float32)
        peak_count = int(np.clip(round(5.0 + density * 11.0 + prominence * 9.0), 5, 24))
        for _peak_index in range(peak_count):
            peak_center_along = float(rng.uniform(-half_length * 0.72, half_length * 0.72))
            peak_center_across = float(rng.normal(0.0, width * 0.26))
            peak_radius_along = float(rng.uniform(0.040, 0.092) * half_length)
            peak_radius_across = float(rng.uniform(0.19, 0.36) * width)
            peak_distance = np.sqrt(
                np.square((along - peak_center_along) / max(peak_radius_along, 1e-5))
                + np.square((signed_dist - peak_center_across) / max(peak_radius_across, 1e-5))
            )
            cone = np.clip(1.0 - peak_distance, 0.0, 1.0)
            cone = np.power(cone, 1.08 + sharpness * 1.28)
            summit_gate = smoothstep(0.18, 0.70, body_profile) * (0.70 + texture_gate * 0.30)
            peak_profile = np.maximum(
                peak_profile,
                cone * summit_gate * float(rng.uniform(0.78, 1.20)),
            )

        summit_mass = np.clip(crest_profile * 0.28 + body_profile * 0.72, 0.0, 1.0)
        peak_profile = np.clip(peak_profile * cluster_noise * summit_mass, 0.0, 1.0)

        valley_noise = 1.0 - np.abs(
            fbm_3d(
                np.cos(lon - phase * 0.09) * np.cos(lat),
                np.sin(lat + phase * 0.04),
                np.sin(lon + phase * 0.06) * np.cos(lat),
                max(16.0, cfg.mountain_scale * 2.7),
                4,
                0.60,
                cfg.seed + int(phase * 1000.0) + 5333,
            )
            * 2.0
            - 1.0
        )
        flank_gate = smoothstep(width * 0.38, width * 1.42, dist)
        valley_profile = smoothstep(0.58, 0.93, valley_noise) * flank_gate * body_profile * (1.0 - peak_profile * 0.52) * length_gate * erosion

        range_strength = float(rng.uniform(0.78, 1.16))
        uplift = np.maximum(uplift, np.clip((body_profile * 0.88 + foothill_profile) * length_gate * range_strength, 0.0, 0.92))
        crest = np.maximum(crest, np.clip(crest_profile * length_gate * range_strength * 0.20, 0.0, 0.26))
        peaks = np.maximum(peaks, np.clip(peak_profile * length_gate * range_strength, 0.0, 1.0))
        valleys = np.maximum(valleys, np.clip(valley_profile * range_strength, 0.0, 1.0))

        crag_seed = fbm_3d(
            np.cos(lon + phase * 0.17) * np.cos(lat),
            np.sin(lat + phase * 0.03),
            np.sin(lon - phase * 0.13) * np.cos(lat),
            max(42.0, cfg.mountain_scale * 7.0),
            3,
            0.58,
            cfg.seed + int(phase * 1200.0) + 5351,
        )
        local_crag = (crag_seed - 0.5) * (body_profile * 0.16 + peak_profile * 0.42) * length_gate * range_strength
        crags = np.where(np.abs(local_crag) > np.abs(crags), local_crag, crags)

    return {
        "uplift": np.clip(uplift * land_f, 0.0, 1.0),
        "crest": np.clip(crest * land_f, 0.0, 1.0),
        "peaks": np.clip(peaks * land_f * prominence, 0.0, 1.0),
        "valleys": np.clip(valleys * land_f, 0.0, 1.0),
        "crags": crags * land_f,
    }


def normalize_planet_family(value: str) -> str:
    key = str(value or "wet_terrestrial")
    return key if key in PLANET_FAMILIES else "wet_terrestrial"


def build_land_water_layers(cfg, x, y, z, land_threshold=None):
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

    no_surface_water = all_land_mode(cfg)
    threshold = (
        float(np.quantile(land_field, land_threshold_quantile(cfg)))
        if land_threshold is None
        else float(land_threshold)
    )
    continent_land = np.ones_like(land_field, dtype=bool) if no_surface_water else land_field >= threshold
    land = continent_land

    if no_surface_water:
        shoreline = np.zeros_like(land_field, dtype=np.float32)
        shelf = np.zeros_like(land_field, dtype=np.float32)
        ocean_depth = np.zeros_like(land_field, dtype=np.float32)
    else:
        continent_shoreline_distance = np.abs(land_field - threshold)
        continent_shoreline = 1.0 - smoothstep(0.0, max(cfg.beach_width, 0.005), continent_shoreline_distance)
        shoreline = np.where(land, continent_shoreline, continent_shoreline * 0.55)

        continent_shelf = 1.0 - smoothstep(0.0, max(cfg.shelf_width, 0.005), np.clip(threshold - land_field, 0.0, 10.0))
        shelf = np.where(~land, continent_shelf, 0.0)
        ocean_depth = np.where(land, 0.0, 1.0 - shelf * 0.75)

    return {
        "land_field": land_field,
        "threshold": threshold,
        "land": land,
        "shoreline": shoreline.astype(np.float32),
        "shelf": shelf.astype(np.float32),
        "ocean_depth": ocean_depth.astype(np.float32),
    }


def build_climate_fields(cfg, x, y, z, lat_abs, shelf, moisture_range=None):
    biome = fbm_3d(x, y, z, cfg.biome_scale, cfg.biome_complexity, 0.57, cfg.seed + 2333)
    moisture_input = (
        fbm_3d(x, y, z, cfg.biome_scale * 0.7, 4, 0.55, cfg.seed + 3441)
        + shelf * 0.28
        + (1.0 - lat_abs) * 0.16
    )
    moisture = normalize01(moisture_input, moisture_range)
    biosphere = float(np.clip(cfg.biosphere_strength, 0.0, 1.0))
    desert_bias = cfg.desert_coverage * (0.45 + (1.0 - moisture) * 0.75)
    forest_bias = cfg.forest_coverage * biosphere * (0.35 + moisture * 0.85)
    return biome, moisture_input, moisture, desert_bias, forest_bias


def build_planet_family_masks(
    cfg,
    x,
    y,
    z,
    lat,
    lon,
    land,
    lowland,
    mountain_mask,
    moisture,
    arid,
    soil_noise,
    mineral_noise,
):
    family = normalize_planet_family(cfg.planet_family)
    lat_abs = np.abs(np.sin(lat))
    land_float = land.astype(np.float32)
    geologic_activity = float(np.clip(cfg.geologic_activity, 0.0, 1.0))
    lava_activity = float(np.clip(cfg.lava_activity, 0.0, 1.0))
    volatile_ice_strength = float(np.clip(cfg.volatile_ice_strength, 0.0, 1.0))
    tidal_lock_strength = float(np.clip(cfg.tidal_lock_strength, 0.0, 1.0))
    surface_age = float(np.clip(cfg.surface_age, 0.0, 1.0))

    fissure_noise = fbm_3d(x * 1.18 + 0.13, y * 0.92 - 0.21, z * 1.11 + 0.07, 26.0, 5, 0.60, cfg.seed + 12431)
    lava_gate = np.clip(mountain_mask * 0.45 + mineral_noise * 0.35 + geologic_activity * 0.35, 0.0, 1.0)
    lava = smoothstep(0.78 - lava_activity * 0.18, 0.98, fissure_noise * 0.70 + lava_gate * 0.30)
    lava *= land_float * lava_activity * geologic_activity

    volatile_noise = fbm_3d(x * 0.94 - 0.17, y * 1.16 + 0.22, z * 1.05, 8.5, 4, 0.54, cfg.seed + 12511)
    cold_gate = smoothstep(0.34, 0.96, lat_abs)
    if family == "tidally_locked":
        substellar = np.clip(np.cos(lon), -1.0, 1.0)
        cold_gate = np.maximum(cold_gate, smoothstep(0.10, 0.82, -substellar) * tidal_lock_strength)
    volatile_ice = smoothstep(0.44, 0.82, volatile_noise * 0.38 + cold_gate * 0.62)
    volatile_ice *= land_float * volatile_ice_strength

    dry_basin = np.clip(arid * lowland * smoothstep(0.44, 0.92, soil_noise) * (1.0 - moisture * 0.60), 0.0, 1.0)
    regolith = np.clip(
        land_float
        * surface_age
        * (0.45 + fbm_3d(x, y, z, 64.0, 4, 0.56, cfg.seed + 12613) * 0.55),
        0.0,
        1.0,
    )

    day_side = np.clip((np.cos(lon) + 1.0) * 0.5, 0.0, 1.0)
    day_night = (day_side - 0.5) * tidal_lock_strength

    return {
        "family": family,
        "lava": lava.astype(np.float32),
        "volatile_ice": volatile_ice.astype(np.float32),
        "dry_basin": dry_basin.astype(np.float32),
        "regolith": regolith.astype(np.float32),
        "day_night": day_night.astype(np.float32),
    }


def build_atmosphere_haze_map(cfg, lat, cloud_mask=None):
    density = float(np.clip(cfg.atmosphere_density, 0.0, 1.0))
    if density <= 0.0:
        shape = cloud_mask.shape if cloud_mask is not None else lat.shape
        return np.zeros(shape, dtype=np.float32)
    lat_abs = np.abs(np.sin(lat))
    limb_like_band = 0.42 + smoothstep(0.44, 0.98, lat_abs) * 0.22
    base = np.full(lat.shape, 0.20 + density * 0.34, dtype=np.float32) * limb_like_band
    if cloud_mask is not None:
        base = np.maximum(base, np.clip(cloud_mask, 0.0, 1.0) * (0.34 + density * 0.42))
    return np.clip(base * density, 0.0, 1.0).astype(np.float32)


def build_emissive_heat_map(cfg, family_masks):
    lava_activity = float(np.clip(cfg.lava_activity, 0.0, 1.0))
    geologic_activity = float(np.clip(cfg.geologic_activity, 0.0, 1.0))
    if lava_activity <= 0.0 or geologic_activity <= 0.0:
        return np.zeros_like(family_masks["lava"], dtype=np.float32)
    lava = np.clip(family_masks["lava"], 0.0, 1.0)
    glow = ndimage.gaussian_filter(lava, sigma=(0.9, 0.9), mode=("nearest", "wrap"))
    return np.clip(lava * 0.78 + glow * 0.38, 0.0, 1.0).astype(np.float32)


def build_cloud_field(cfg, x, y, z, lat, land_field, land_threshold):
    land_correlation = float(np.clip(cfg.cloud_land_correlation, 0.0, 1.0))
    scale = max(0.20, float(cfg.cloud_scale))
    detail = max(1, int(cfg.cloud_detail))
    roughness = float(np.clip(cfg.cloud_roughness, 0.10, 0.95))
    latitude_bias = float(np.clip(cfg.cloud_latitude_bias, -1.0, 1.0))
    band_strength = float(np.clip(cfg.cloud_band_strength, 0.0, 1.0))
    latitude_warp_strength = float(np.clip(cfg.cloud_latitude_warp, 0.0, 2.0))
    hemisphere_imbalance = float(np.clip(cfg.cloud_hemisphere_imbalance, 0.0, 2.0))
    wind_stretch = float(np.clip(cfg.cloud_wind_stretch, 0.0, 1.0))
    breakup_strength = float(np.clip(cfg.cloud_breakup, 0.0, 1.0))
    storm_density = float(np.clip(cfg.storm_density, 0.0, 1.0))
    spiral_strength = float(np.clip(cfg.spiral_storm_strength, 0.0, 1.0))
    polar_strength = float(np.clip(cfg.polar_cloud_strength, 0.0, 1.0))
    polar_asymmetry = float(np.clip(cfg.polar_cloud_asymmetry, 0.0, 2.0))

    sin_lat = np.sin(lat)
    abs_sin_lat = np.abs(sin_lat)
    latitude_warp = fbm_3d(
        x * 0.83 + 0.37,
        y * 1.18 - 0.24,
        z * 0.91 + 0.43,
        scale * 1.65 + 0.75,
        3,
        0.54,
        cfg.seed + 9087,
    )
    longitude_warp = fbm_3d(
        x * 1.27 - 0.31,
        y * 0.76 + 0.48,
        z * 1.11 - 0.22,
        scale * 2.45 + 1.35,
        3,
        0.56,
        cfg.seed + 9097,
    )
    vertical_warp = fbm_3d(
        x * 0.94 + 0.18,
        y * 1.34 + 0.29,
        z * 1.21 - 0.41,
        scale * 3.05 + 1.85,
        3,
        0.52,
        cfg.seed + 9103,
    )
    coordinate_warp = latitude_warp_strength * (0.22 + band_strength * 0.18 + wind_stretch * 0.10)
    cloud_x = x + (latitude_warp - 0.5) * coordinate_warp
    cloud_y = y + (vertical_warp - 0.5) * coordinate_warp * 0.82 + sin_lat * hemisphere_imbalance * 0.045
    cloud_z = z + (longitude_warp - 0.5) * coordinate_warp

    broad = fbm_3d(cloud_x, cloud_y, cloud_z, scale, detail, roughness, cfg.seed + 9011)
    weather = fbm_3d(cloud_x, cloud_y, cloud_z, scale * 3.4 + 1.0, max(2, min(6, detail + 1)), 0.56, cfg.seed + 9029)
    wisps = fbm_3d(cloud_x, cloud_y, cloud_z, scale * 8.5 + 3.0, 3, 0.58, cfg.seed + 9043)
    lon = np.arctan2(x, z)
    wind_x = x * (1.0 + wind_stretch * 3.8)
    wind_z = z * (1.0 - wind_stretch * 0.46)
    wind_flow = fbm_3d(
        wind_x,
        y * (0.78 + wind_stretch * 0.22),
        wind_z,
        scale * (2.0 + wind_stretch * 2.4) + 0.8,
        max(2, min(6, detail)),
        0.54,
        cfg.seed + 9061,
    )

    land_width = max(float(cfg.continent_contrast) * 3.5, 0.12)
    soft_land_form = smoothstep(land_threshold - land_width, land_threshold + land_width, land_field)
    warped_abs_sin_lat = np.clip(
        abs_sin_lat
        + (latitude_warp - 0.5) * (0.24 + band_strength * 0.20) * latitude_warp_strength
        + sin_lat * (0.080 + band_strength * 0.070) * hemisphere_imbalance,
        0.0,
        1.0,
    )
    tropical_band = 1.0 - smoothstep(0.18, 0.86, warped_abs_sin_lat)
    midlatitude_band = smoothstep(0.18, 0.48, warped_abs_sin_lat) * (1.0 - smoothstep(0.62, 0.92, warped_abs_sin_lat))
    polar_band = smoothstep(0.68, 0.98, warped_abs_sin_lat)
    if latitude_bias >= 0.0:
        lat_band = lerp(midlatitude_band, tropical_band, latitude_bias)
    else:
        lat_band = lerp(midlatitude_band, polar_band, -latitude_bias)
    lat_band = normalize01(lat_band)
    wave_phase = (
        lon * (3.0 + scale * 0.65)
        + np.sin(lat * 4.0 + cfg.seed * 0.013) * (1.2 + wind_stretch * 1.8)
        + (longitude_warp - 0.5) * (2.4 + wind_stretch * 2.8) * latitude_warp_strength
    )
    band_wave = np.sin(wave_phase) * 0.5 + 0.5
    banding = lerp(1.0, 0.72 + 0.56 * (lat_band * 0.66 + band_wave * 0.34), band_strength)
    breakup = smoothstep(
        0.18,
        0.86,
        fbm_3d(x * 1.08 + 0.21, y * 0.92 - 0.17, z * 1.13 + 0.09, scale * 11.0 + 6.0, 3, 0.58, cfg.seed + 9079),
    )

    field = broad * 0.48 + weather * 0.22 + wind_flow * 0.18 + wisps * 0.12
    field = lerp(field, field * 0.55 + soft_land_form * 0.45, land_correlation)
    field = field * banding
    field = field * lerp(1.0, 0.58 + breakup * 0.58, breakup_strength)
    field = field + lat_band * (0.08 + band_strength * 0.10)
    field = field * (
        1.0
        + ((latitude_warp - 0.5) * 0.46 - 0.06) * latitude_warp_strength
        + sin_lat * (0.070 + band_strength * 0.080) * hemisphere_imbalance
    )
    field = field + sin_lat * (0.060 + band_strength * 0.085) * hemisphere_imbalance
    if polar_strength > 0.0:
        polar_texture = 0.64 + 0.36 * fbm_3d(cloud_x, cloud_y, cloud_z, scale * 5.0 + 2.0, 3, 0.52, cfg.seed + 9109)
        polar_texture *= (
            1.0
            + (latitude_warp - 0.5) * 0.70 * polar_asymmetry
            + sin_lat * 0.26 * polar_asymmetry
        )
        polar_shape = np.clip(
            polar_band
            * (1.0 + (vertical_warp - 0.5) * 0.65 * polar_asymmetry + sin_lat * 0.18 * polar_asymmetry),
            0.0,
            1.0,
        )
        field = field + polar_shape * polar_texture * polar_strength * (0.36 + 0.10 * polar_asymmetry)
    if storm_density > 0.0 or spiral_strength > 0.0:
        rng = np.random.default_rng(int(cfg.seed) + 9127)
        storm_count = int(round(2 + storm_density * 18 + spiral_strength * 8))
        storm_field = np.zeros_like(field, dtype=np.float32)
        for _ in range(storm_count):
            center_lat = float(rng.uniform(-1.05, 1.05))
            center_lon = float(rng.uniform(-math.pi, math.pi))
            center = np.array(
                [
                    math.cos(center_lat) * math.sin(center_lon),
                    math.sin(center_lat),
                    math.cos(center_lat) * math.cos(center_lon),
                ],
                dtype=np.float32,
            )
            east = np.array([math.cos(center_lon), 0.0, -math.sin(center_lon)], dtype=np.float32)
            north = np.cross(center, east).astype(np.float32)
            north /= max(1e-6, float(np.linalg.norm(north)))
            turn = float(rng.uniform(-0.75, 0.75))
            along = east * math.cos(turn) + north * math.sin(turn)
            across = -east * math.sin(turn) + north * math.cos(turn)
            dx = x * along[0] + y * along[1] + z * along[2]
            dy = x * across[0] + y * across[1] + z * across[2]
            dot = np.clip(x * center[0] + y * center[1] + z * center[2], -1.0, 1.0)
            distance = np.arccos(dot)
            radius = float(rng.uniform(0.050, 0.145)) * (0.85 + storm_density * 0.55)
            aspect = float(rng.uniform(1.15, 2.45))
            ellipse_distance = np.sqrt((dx / aspect) ** 2 + (dy * aspect * 0.82) ** 2)
            broad_core = 1.0 - smoothstep(radius * 0.24, radius * 1.22, ellipse_distance)
            soft_core = 1.0 - smoothstep(radius * 0.05, radius * 0.62, distance)
            angle = np.arctan2(dy, dx)
            phase = float(rng.uniform(-math.pi, math.pi))
            twist = float(rng.uniform(1.7, 3.4)) * (1.0 if center_lat >= 0.0 else -1.0)
            arc_angle = np.arctan2(
                np.sin(angle - distance / max(radius, 1e-6) * twist - phase),
                np.cos(angle - distance / max(radius, 1e-6) * twist - phase),
            )
            arc = 1.0 - smoothstep(0.16 + spiral_strength * 0.10, 1.24, np.abs(arc_angle))
            arc *= smoothstep(radius * 0.18, radius * 0.92, distance)
            broken = smoothstep(
                0.24,
                0.92,
                fbm_3d(
                    x + center[0] * 0.31 + along[0] * 0.17,
                    y + center[1] * 0.31 + along[1] * 0.17,
                    z + center[2] * 0.31 + along[2] * 0.17,
                    scale * 13.0 + 8.0,
                    3,
                    0.54,
                    cfg.seed + 9300 + _,
                ),
            )
            lopsided = 0.82 + 0.18 * np.clip((dx / max(radius, 1e-6)) * float(rng.uniform(-1.0, 1.0)), -1.0, 1.0)
            embedded_storm = (broad_core * 0.64 + soft_core * 0.18 + arc * spiral_strength * 0.18)
            storm_field = np.maximum(
                storm_field,
                embedded_storm * broken * lopsided * float(rng.uniform(0.30, 0.62)),
            )
        field = field + storm_field * (0.14 + storm_density * 0.26 + spiral_strength * 0.12)
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


def build_cloud_shadow_map(cfg, cloud_mask):
    strength = float(np.clip(cfg.cloud_shadow_strength, 0.0, 1.0))
    if strength <= 0.0 or cloud_mask is None:
        return np.zeros_like(cloud_mask, dtype=np.float32)
    softness = float(np.clip(cfg.cloud_shadow_softness, 0.0, 1.0))
    base = np.clip(cloud_mask, 0.0, 1.0)
    sigma = max(0.15, min(base.shape) * (0.0015 + softness * 0.012))
    softened = ndimage.gaussian_filter(base, sigma=(sigma, sigma), mode=("nearest", "wrap"))
    return np.clip(softened * strength, 0.0, 1.0).astype(np.float32)


def build_nebula_maps(cfg, x, y, z):
    intensity = float(np.clip(cfg.nebula_intensity, 0.0, 2.0))
    coverage = float(np.clip(cfg.nebula_coverage, 0.0, 1.0))
    star_density = float(np.clip(cfg.nebula_star_density, 0.0, 1.0))
    if intensity <= 0.0 and star_density <= 0.0:
        empty = np.zeros_like(x, dtype=np.float32)
        return {
            "nebula_color": np.zeros((*x.shape, 3), dtype=np.float32),
            "nebula_alpha": empty,
            "nebula_stars": empty,
        }

    scale = max(0.15, float(cfg.nebula_scale))
    detail = max(1, int(cfg.nebula_detail))
    roughness = float(np.clip(cfg.nebula_roughness, 0.10, 0.95))
    warp_strength = float(np.clip(cfg.nebula_warp, 0.0, 2.0))
    filament_strength = float(np.clip(cfg.nebula_filament_strength, 0.0, 1.0))
    color_mix = float(np.clip(cfg.nebula_color_mix, 0.0, 1.0))
    color_softness = float(np.clip(cfg.nebula_color_softness, 0.0, 1.0))

    height, width = x.shape
    yy, xx = np.indices(x.shape, dtype=np.float32)
    aspect = width / max(float(height), 1.0)
    u = ((xx + 0.5) / max(float(width), 1.0) - 0.5) * aspect * 2.0
    v = ((yy + 0.5) / max(float(height), 1.0) - 0.5) * 2.0
    zero = np.zeros_like(u, dtype=np.float32)

    warp_scale = scale * 0.72 + 0.45
    warp_x = fbm_3d(u * 0.72 + 2.31, v * 0.88 - 1.67, zero + 0.19, warp_scale, 5, 0.55, cfg.seed + 28011) - 0.5
    warp_y = fbm_3d(u * 0.91 - 0.83, v * 0.69 + 2.04, zero + 0.43, warp_scale * 1.17, 5, 0.56, cfg.seed + 28037) - 0.5
    wx = u + warp_x * (0.82 * warp_strength)
    wy = v + warp_y * (0.62 * warp_strength)

    broad = fbm_3d(wx, wy, zero + 0.11, scale * 0.72 + 0.28, detail, roughness, cfg.seed + 28103)
    medium = fbm_3d(wx * 1.48 - 0.37, wy * 1.22 + 0.54, zero + 0.29, scale * 2.4 + 0.8, max(2, min(7, detail + 1)), 0.58, cfg.seed + 28129)
    fine = fbm_3d(wx * 3.4 + 1.2, wy * 2.9 - 0.8, zero + 0.61, scale * 7.5 + 3.0, 4, 0.57, cfg.seed + 28151)

    rng = np.random.default_rng(int(cfg.seed) + 28301)
    cloud_envelope = np.zeros_like(u, dtype=np.float32)
    heat = np.zeros_like(u, dtype=np.float32)
    complex_count = 4 + int(round(coverage * 4.0))
    for idx in range(complex_count):
        cx = rng.uniform(-0.92 * aspect, 0.92 * aspect)
        cy = rng.uniform(-0.72, 0.72)
        angle = rng.uniform(-math.pi, math.pi)
        ca = math.cos(angle)
        sa = math.sin(angle)
        major = rng.uniform(0.34, 0.95) * (1.10 - scale * 0.045)
        minor = major * rng.uniform(0.20, 0.46)
        dx = wx - cx
        dy = wy - cy
        along = dx * ca + dy * sa
        across = -dx * sa + dy * ca
        core = np.exp(-((along / max(major, 0.05)) ** 2 + (across / max(minor, 0.04)) ** 2))
        halo = np.exp(-((along / max(major * 1.9, 0.05)) ** 2 + (across / max(minor * 2.7, 0.04)) ** 2))
        power = rng.uniform(0.45, 1.05)
        cloud_envelope = np.maximum(cloud_envelope, halo * power)
        heat = np.maximum(heat, core * rng.uniform(0.55, 1.18))

    filament = np.zeros_like(u, dtype=np.float32)
    filament_count = 5 + int(round(filament_strength * 8.0))
    for idx in range(filament_count):
        angle = rng.uniform(-math.pi, math.pi)
        ca = math.cos(angle)
        sa = math.sin(angle)
        offset = rng.uniform(-1.4, 1.4)
        width_line = rng.uniform(0.018, 0.055)
        bend = fbm_3d(u * rng.uniform(0.8, 1.8), v * rng.uniform(0.8, 1.8), zero + idx * 0.17, scale * 1.8 + 1.4, 3, 0.58, cfg.seed + 28409 + idx * 37) - 0.5
        d = np.abs((-sa * wx + ca * wy) - offset + bend * (0.28 + warp_strength * 0.24))
        line = np.exp(-((d / width_line) ** 2))
        broken = smoothstep(0.30, 0.82, fbm_3d(wx * 1.8 + idx, wy * 2.1 - idx * 0.31, zero + 0.73, scale * 3.8 + 2.0, 4, 0.60, cfg.seed + 28511 + idx * 41))
        filament = np.maximum(filament, line * broken)

    gas = np.clip(cloud_envelope * (0.42 + broad * 0.38 + medium * 0.20) + heat * 0.36, 0.0, 1.0)
    threshold = 0.28 + (1.0 - coverage) * 0.42
    alpha = smoothstep(threshold - 0.22, threshold + 0.24, gas)
    alpha = np.clip(alpha + filament * filament_strength * (0.10 + heat * 0.22), 0.0, 1.0)
    alpha = ndimage.gaussian_filter(alpha, sigma=max(0.35, min(height, width) * 0.0014), mode="nearest")
    alpha = np.power(np.clip(alpha, 0.0, 1.0), 1.08)
    alpha = np.clip(alpha * intensity, 0.0, 1.0).astype(np.float32)

    base_color = rgb_from_hex(cfg.nebula_base_color)
    core_color = rgb_from_hex(cfg.nebula_core_color)
    accent_color = rgb_from_hex(cfg.nebula_accent_color)
    dust_color = base_color * 0.45 + core_color * 0.55
    boundary_width = 0.08 + color_softness * 0.52
    hot_signal = heat * 0.72 + fine * 0.28
    cool_signal = medium * 0.70 + warp_y * 0.30 + 0.15
    dust_signal = broad
    hot_mix = smoothstep(0.56 - boundary_width, 0.56 + boundary_width, hot_signal)
    cool_mix = smoothstep(0.55 - boundary_width, 0.55 + boundary_width, cool_signal)
    dust_mix = smoothstep(0.52 - boundary_width, 0.52 + boundary_width, dust_signal) * (1.0 - hot_mix * 0.35)
    color = color_blend(base_color, core_color, hot_mix * (0.65 + color_mix * 0.25))
    color = color_blend(color, accent_color, cool_mix * color_mix * 0.55)
    color = color_blend(color, dust_color, dust_mix * (1.0 - color_mix) * 0.50)
    color = color * (0.10 + alpha[:, :, None] * (0.82 + fine[:, :, None] * 0.22))
    color = np.clip(color, 0.0, 255.0).astype(np.float32)

    star_scale = 700.0 + star_density * 1300.0
    star_noise = hash_noise(
        np.floor((u + aspect) * star_scale).astype(np.int32),
        np.floor((v + 1.0) * star_scale).astype(np.int32),
        np.full_like(u, int(cfg.seed) & 0xFFFF, dtype=np.int32),
        cfg.seed + 28219,
    )
    star_cut = 0.99935 - star_density * 0.0048
    stars = smoothstep(star_cut, 1.0, star_noise)
    star_brightness = hash_noise(
        np.floor((u + aspect) * star_scale + 177.0).astype(np.int32),
        np.floor((v + 1.0) * star_scale - 91.0).astype(np.int32),
        np.full_like(u, (int(cfg.seed) + 37) & 0xFFFF, dtype=np.int32),
        cfg.seed + 28243,
    )
    stars *= 0.28 + star_brightness * 0.72
    stars *= 0.55 + smoothstep(0.32, 0.94, 1.0 - alpha) * 0.45
    stars = np.clip(stars * star_density, 0.0, 1.0).astype(np.float32)

    return {
        "nebula_color": color,
        "nebula_alpha": alpha,
        "nebula_stars": stars,
    }


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
        np.floor((x + 1.37) * dot_scale).astype(np.int32),
        np.floor((y + 1.91) * dot_scale).astype(np.int32),
        np.floor((z + 1.53) * dot_scale).astype(np.int32),
        cfg.seed + 24571,
    )
    local_max = dot_noise >= ndimage.maximum_filter(dot_noise, size=3, mode="wrap")
    dot_probability = np.clip(settlement_field * (0.30 + density * 1.18), 0.0, 0.98)
    dots = local_max & (dot_noise > (1.0 - dot_probability))

    extra_dot_noise = hash_noise(
        np.floor((x + 4.19) * dot_scale * 2.35).astype(np.int32),
        np.floor((y + 3.73) * dot_scale * 2.35).astype(np.int32),
        np.floor((z + 4.61) * dot_scale * 2.35).astype(np.int32),
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

    row_parity = np.arange(x.shape[0], dtype=np.int32)[:, None]
    col_parity = np.arange(x.shape[1], dtype=np.int32)[None, :]
    pin_grid = ((row_parity + col_parity + int(cfg.seed)) & 1) == 0
    micro_dot_noise = hash_noise(
        np.floor((x + 5.43) * dot_scale * 3.15).astype(np.int32),
        np.floor((y + 5.97) * dot_scale * 3.15).astype(np.int32),
        np.floor((z + 5.21) * dot_scale * 3.15).astype(np.int32),
        cfg.seed + 24781,
    )
    micro_probability = np.clip(
        (settlement_field * 0.72 + suitability * towns * 1.15 + roads * 0.34) * (0.42 + density * 1.65),
        0.0,
        0.98,
    )
    micro_dots = pin_grid & (micro_dot_noise > (1.0 - micro_probability))

    road_dot_noise = hash_noise(
        np.floor((x + 3.11) * dot_scale * 1.75).astype(np.int32),
        np.floor((y + 2.37) * dot_scale * 1.75).astype(np.int32),
        np.floor((z + 2.83) * dot_scale * 1.75).astype(np.int32),
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


def crater_generation_enabled(cfg) -> bool:
    return any(
        float(getattr(cfg, key)) > 0.0
        for key in (
            "crater_density",
            "crater_small_density",
            "crater_medium_density",
            "crater_large_basin_density",
            "crater_micro_pitting",
        )
    )


def blank_crater_layers(shape):
    return {
        "floor": np.zeros(shape, dtype=np.float32),
        "rim": np.zeros(shape, dtype=np.float32),
        "ejecta": np.zeros(shape, dtype=np.float32),
        "rays": np.zeros(shape, dtype=np.float32),
        "basin": np.zeros(shape, dtype=np.float32),
        "micro": np.zeros(shape, dtype=np.float32),
    }


def tangent_basis(center):
    up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    if abs(float(np.dot(center, up))) > 0.92:
        up = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    u = np.cross(center, up)
    u /= max(float(np.linalg.norm(u)), 1e-6)
    v = np.cross(center, u)
    v /= max(float(np.linalg.norm(v)), 1e-6)
    return u.astype(np.float32), v.astype(np.float32)


def accumulate_crater_layer(
    layers,
    cfg,
    x,
    y,
    z,
    rng,
    count,
    min_radius,
    max_radius,
    target,
    layer_kind,
    seed_offset,
):
    if count <= 0:
        return

    erosion = float(np.clip(cfg.crater_erosion, 0.0, 1.0))
    rim_width = float(np.clip(cfg.crater_rim_width, 0.0, 1.0))
    ray_strength = float(np.clip(cfg.crater_ray_strength, 0.0, 1.0))
    centers = rng.normal(size=(count, 3)).astype(np.float32)
    centers /= np.maximum(np.linalg.norm(centers, axis=1, keepdims=True), 1e-6)
    radius_mix = rng.random(count) ** (2.35 if layer_kind == "small" else 1.35)
    radii = min_radius + (max_radius - min_radius) * radius_mix
    strengths = 0.70 + rng.random(count) * 0.62

    wear_noise = fbm_3d(x, y, z, 38.0 + seed_offset, 3, 0.52, cfg.seed + 7103 + seed_offset)
    wear = lerp(1.0, 0.54 + wear_noise * 0.46, erosion)

    for index, (center, radius, strength) in enumerate(zip(centers, radii, strengths)):
        dot = np.clip(x * center[0] + y * center[1] + z * center[2], -1.0, 1.0)
        chord_radius = max(1e-6, 2.0 * math.sin(float(radius) * 0.5))
        radial = np.sqrt(np.maximum(0.0, 2.0 - 2.0 * dot)) / chord_radius
        local_wear = wear * strength * target

        if layer_kind == "basin":
            basin_floor = 1.0 - smoothstep(0.0, 1.05 + erosion * 0.30, radial)
            basin_floor *= 0.70 + 0.30 * (1.0 - smoothstep(0.0, 0.32, radial))
            basin_rim = smoothstep(0.82, 1.00, radial) * (1.0 - smoothstep(1.0, 1.22 + rim_width * 0.25, radial))
            layers["basin"] += basin_floor * local_wear * (1.0 - erosion * 0.20)
            layers["rim"] += basin_rim * local_wear * 0.42
            continue

        bowl = 1.0 - smoothstep(0.0, 1.0 + erosion * 0.14, radial)
        bowl *= 0.52 + 0.48 * (1.0 - smoothstep(0.0, 0.16 + erosion * 0.14, radial))
        rim_inner_start = 0.90 - rim_width * 0.22
        rim_inner_peak = 0.975 - rim_width * 0.04
        rim_outer_end = 1.035 + rim_width * 0.24 + erosion * 0.06
        ring = smoothstep(rim_inner_start, rim_inner_peak, radial) * (1.0 - smoothstep(1.0, rim_outer_end, radial))
        ejecta = smoothstep(0.96, 1.04, radial) * (1.0 - smoothstep(1.06, 2.20 + erosion * 0.55, radial))

        floor_scale = 0.72 if layer_kind == "small" else 1.0
        rim_scale = 1.12 if layer_kind == "medium" else 0.82
        layers["floor"] += bowl * local_wear * floor_scale * (1.0 - erosion * 0.24)
        layers["rim"] += ring * local_wear * rim_scale * (1.0 - erosion * 0.18)
        layers["ejecta"] += ejecta * local_wear * (0.45 if layer_kind == "small" else 0.90) * (1.0 - erosion * 0.18)

        if ray_strength > 0.0 and layer_kind == "medium" and index % 4 == 0:
            u, v = tangent_basis(center)
            tx = x * u[0] + y * u[1] + z * u[2]
            ty = x * v[0] + y * v[1] + z * v[2]
            angle = np.arctan2(ty, tx)
            ray_count = int(rng.integers(9, 18))
            phase = float(rng.random() * math.tau)
            spoke = np.power(np.clip(0.5 + 0.5 * np.cos(angle * ray_count + phase), 0.0, 1.0), 8.0)
            ray_falloff = smoothstep(1.02, 1.18, radial) * (1.0 - smoothstep(1.22, 3.25, radial))
            layers["rays"] += spoke * ray_falloff * local_wear * ray_strength * 0.95


def build_crater_field(cfg, x, y, z, land):
    legacy_density = float(np.clip(cfg.crater_density, 0.0, 1.0))
    small_density = float(np.clip(cfg.crater_small_density, 0.0, 1.0))
    medium_density = float(np.clip(cfg.crater_medium_density, 0.0, 1.0))
    basin_density = float(np.clip(cfg.crater_large_basin_density, 0.0, 1.0))
    micro_strength = float(np.clip(cfg.crater_micro_pitting, 0.0, 1.0))
    if max(legacy_density, small_density, medium_density, basin_density, micro_strength) <= 0.0:
        return blank_crater_layers(x.shape)

    min_radius = max(0.001, float(cfg.crater_min_radius))
    max_radius = max(min_radius, float(cfg.crater_max_radius))
    land_bias = float(np.clip(cfg.crater_land_bias, 0.0, 1.0))
    target = lerp(np.ones_like(x, dtype=np.float32), land.astype(np.float32), land_bias)

    layers = blank_crater_layers(x.shape)
    rng = np.random.default_rng(cfg.seed + 7019)
    small_count = int(round(small_density * 240.0 + legacy_density * 55.0))
    medium_count = int(round(medium_density * 120.0 + legacy_density * 120.0))
    basin_count = int(round(basin_density * 10.0 + legacy_density * 4.0))

    accumulate_crater_layer(
        layers,
        cfg,
        x,
        y,
        z,
        rng,
        basin_count,
        max(max_radius * 1.05, 0.070),
        max(max_radius * 2.35, 0.18),
        target,
        "basin",
        101,
    )
    accumulate_crater_layer(
        layers,
        cfg,
        x,
        y,
        z,
        rng,
        medium_count,
        min_radius,
        max_radius,
        target,
        "medium",
        211,
    )
    accumulate_crater_layer(
        layers,
        cfg,
        x,
        y,
        z,
        rng,
        small_count,
        max(0.0015, min_radius * 0.32),
        max(min_radius * 1.8, 0.010),
        target,
        "small",
        307,
    )

    if micro_strength > 0.0:
        fine = fbm_3d(x, y, z, 95.0, 4, 0.54, cfg.seed + 7433)
        finer = fbm_3d(x, y, z, 180.0, 3, 0.50, cfg.seed + 7529)
        pitting = smoothstep(0.52, 0.93, fine * 0.62 + finer * 0.38)
        layers["micro"] = np.clip((pitting * 0.74 + layers["floor"] * 0.35) * micro_strength * target, 0.0, 1.0)

    for key, value in layers.items():
        layers[key] = np.clip(value, 0.0, 1.0).astype(np.float32)
    return layers


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


def all_land_mode(cfg) -> bool:
    return float(cfg.land_coverage) >= 1.0


def land_threshold_quantile(cfg) -> float:
    if all_land_mode(cfg):
        return 0.05
    return 1.0 - float(np.clip(cfg.land_coverage, 0.0, 1.0))


def hash_noise(ix, iy, iz, seed):
    x = ix.astype(np.uint32, copy=False)
    y = iy.astype(np.uint32, copy=False)
    z = iz.astype(np.uint32, copy=False)
    n = x * np.uint32(374761393) + y * np.uint32(668265263) + z * np.uint32(2147483647)
    n = n + np.uint32(seed * 1442695041 & 0xFFFFFFFF)
    n = (n ^ (n >> np.uint32(13))) * np.uint32(1274126177)
    n = n ^ (n >> np.uint32(16))
    return n.astype(np.float32) / np.float32(0xFFFFFFFF)


def value_noise_3d(x, y, z, scale, seed):
    sx = x * scale + 100.0
    sy = y * scale + 100.0
    sz = z * scale + 100.0
    x0f = np.floor(sx)
    y0f = np.floor(sy)
    z0f = np.floor(sz)
    x0 = x0f.astype(np.int32)
    y0 = y0f.astype(np.int32)
    z0 = z0f.astype(np.int32)
    xf = sx - x0f
    yf = sy - y0f
    zf = sz - z0f
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


def quad_sphere_face_vectors_tile(face, size, row_start, row_stop):
    axis = ((np.arange(size, dtype=np.float32) + 0.5) / size) * 2.0 - 1.0
    u_axis = axis
    v_axis = axis[::-1][row_start:row_stop]
    u, v = np.meshgrid(u_axis, v_axis)

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


def build_continent_color_boundary_mask(cfg, x, y, z, land):
    alignment = float(np.clip(cfg.mountain_boundary_alignment, 0.0, 1.0))
    strength = float(np.clip(cfg.continent_color_variation, 0.0, 1.0))
    if alignment <= 0.0 or strength <= 0.0:
        return np.zeros_like(x, dtype=np.float32)

    scale = max(0.25, float(cfg.continent_color_scale))
    diversity = float(np.clip(cfg.continent_color_diversity, 0.0, 1.0))
    blend_smoothness = float(np.clip(cfg.continent_color_blend_smoothness, 0.0, 1.0))
    province_count = int(np.clip(round(7.0 + scale * 4.2), 6, 38))
    rng = np.random.default_rng(int(cfg.seed) * 1709 + 9176)

    anchors = rng.normal(size=(province_count, 3)).astype(np.float32)
    anchors /= np.linalg.norm(anchors, axis=1, keepdims=True)

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
    for anchor in anchors:
        score = wx * anchor[0] + wy * anchor[1] + wz * anchor[2]
        better = score > best_score
        between = (~better) & (score > second_score)
        second_score = np.where(better, best_score, np.where(between, score, second_score))
        best_score = np.where(better, score, best_score)

    boundary_margin = best_score - second_score
    blend_width = 0.045 + blend_smoothness * 0.360 + (1.0 - diversity) * 0.060
    boundary_mask = 1.0 - smoothstep(0.008, blend_width * 0.58, boundary_margin)
    boundary_mask *= land.astype(np.float32)
    return np.clip(boundary_mask * alignment, 0.0, 1.0)


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
    region_tints = resolve_region_tints(cfg)
    if len(region_tints) == 0:
        return blank_color, blank_weight, blank_weight
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
    for index, anchor in enumerate(anchors):
        score = wx * anchor[0] + wy * anchor[1] + wz * anchor[2]
        better = score > best_score
        between = (~better) & (score > second_score)
        second_score = np.where(better, best_score, np.where(between, score, second_score))
        best_score = np.where(better, score, best_score)
        province_id = np.where(better, index, province_id)

    boundary_margin = best_score - second_score
    blend_width = 0.045 + blend_smoothness * 0.360 + (1.0 - diversity) * 0.060
    boundary_soft = smoothstep(0.006, blend_width, boundary_margin)

    warm_gate = np.clip(0.46 + arid * 0.40 + lowland * 0.22, 0.0, 1.0)
    red_gate = np.clip(0.34 + arid * 0.48 + mineral_noise * 0.28 + mountain_mask * 0.16, 0.0, 1.0)
    dark_gate = np.clip(0.34 + mineral_noise * 0.38 + mountain_mask * 0.38, 0.0, 1.0)
    humid_gate = np.clip(0.24 + moisture * 0.74 + lowland * 0.14 - mountain_mask * 0.18, 0.0, 1.0)
    pale_gate = np.clip(0.34 + lowland * 0.38 + shoreline * 0.20 + (1.0 - arid) * 0.16, 0.0, 1.0)
    cool_gate = np.clip(0.30 + cold_lat * 0.64 + moisture * 0.12 - arid * 0.16, 0.0, 1.0)

    soft_temperature = 0.018 + blend_smoothness * 0.095 + (1.0 - diversity) * 0.035
    influence_span = 0.12 + blend_smoothness * 0.32 + (1.0 - diversity) * 0.08
    influence_floor = best_score - influence_span
    weight_sum = np.zeros_like(x, dtype=np.float32)
    color_sum = np.zeros((map_height, map_width, 3), dtype=np.float32)
    gate_sum = np.zeros_like(x, dtype=np.float32)
    bias_sum = np.zeros_like(x, dtype=np.float32)
    style_gates = (warm_gate, red_gate, dark_gate, humid_gate, pale_gate, cool_gate, humid_gate, pale_gate)
    for index, anchor in enumerate(anchors):
        score = wx * anchor[0] + wy * anchor[1] + wz * anchor[2]
        influence = np.exp(np.clip((score - best_score) / soft_temperature, -18.0, 0.0)).astype(np.float32)
        influence = np.where(score >= influence_floor, influence, 0.0)
        style_index = int(styles[index])
        weight_sum += influence
        color_sum += influence[..., None] * region_tints[style_index]
        gate_sum += influence * style_gates[style_index % len(style_gates)]
        bias_sum += influence * province_bias[index]
    weight_sum = np.maximum(weight_sum, 1e-6)
    blended_color = color_sum / weight_sum[..., None]
    blended_style_gate = gate_sum / weight_sum
    blended_bias = bias_sum / weight_sum
    best_style_map = styles[province_id]
    best_color = region_tints[best_style_map]
    best_style_gate = np.zeros_like(x, dtype=np.float32)
    for style_index, gate in enumerate(style_gates[: len(region_tints)]):
        best_style_gate = np.where(best_style_map == style_index, gate, best_style_gate)
    best_bias = province_bias[province_id]
    province_core = boundary_soft * (0.62 + diversity * 0.30) * (1.0 - blend_smoothness * 0.04)
    target_color = color_blend(blended_color, best_color, province_core)
    style_gate = lerp(blended_style_gate, best_style_gate, province_core)
    bias_map = lerp(blended_bias, best_bias, province_core)
    province_texture = 0.82 + fbm_3d(x, y, z, scale * 5.2 + 3.0, 3, 0.50, cfg.seed + 6637) * 0.34

    land_region = land.astype(np.float32) * non_ice_land
    gain = strength * (1.55 + diversity * 1.20)
    region_weight = (
        (0.48 + boundary_soft * (0.52 - blend_smoothness * 0.16))
        * gain
        * style_gate
        * bias_map
        * province_texture
        * land_region
    )
    region_weight = np.clip(region_weight, 0.0, 0.68 + diversity * 0.24)
    debug = ((province_id.astype(np.float32) + 1.0) / float(province_count)) * land.astype(np.float32)
    return target_color, region_weight, debug


def save_rgb(path, arr):
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "RGB").save(path)


def save_gray(path, arr):
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "L").save(path)


def save_gray16(path, arr):
    arr = np.clip(arr * 65535.0, 0, 65535).astype(np.uint16)
    Image.fromarray(arr).save(path)


def save_rgba(path, arr):
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "RGBA").save(path)


def save_luminance_alpha(path, arr):
    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "LA").save(path)


def save_luminance_alpha16(path, arr):
    arr = np.clip(arr * 65535.0, 0, 65535).astype(np.uint16)
    write_streamed_png(
        path,
        arr.shape[1],
        arr.shape[0],
        4,
        (row.astype(">u2", copy=False).tobytes() for row in arr),
        bit_depth=16,
    )


def write_png_chunk(handle, chunk_type, data):
    handle.write(struct.pack(">I", len(data)))
    handle.write(chunk_type)
    handle.write(data)
    checksum = zlib.crc32(chunk_type)
    checksum = zlib.crc32(data, checksum) & 0xFFFFFFFF
    handle.write(struct.pack(">I", checksum))


def write_streamed_png(path, width, height, color_type, row_iter, bit_depth=8):
    compressor = zlib.compressobj(level=6)
    pending = bytearray()
    with Path(path).open("wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        ihdr = struct.pack(">IIBBBBB", int(width), int(height), int(bit_depth), int(color_type), 0, 0, 0)
        write_png_chunk(handle, b"IHDR", ihdr)
        for row in row_iter:
            pending.extend(compressor.compress(b"\x00" + row))
            if len(pending) >= 1_048_576:
                write_png_chunk(handle, b"IDAT", bytes(pending))
                pending.clear()
        pending.extend(compressor.flush())
        if pending:
            write_png_chunk(handle, b"IDAT", bytes(pending))
        write_png_chunk(handle, b"IEND", b"")


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
    map_names=None,
    stat_fields=None,
):
    selected_maps = selected_texture_maps(map_names)
    stats = set(stat_fields or ())
    stats_only = return_raw_stats and bool(stats)
    requested_outputs = set() if stats_only else set(selected_maps)
    needs_cloud = bool({"cloud_mask", "cloud_shadow"} & requested_outputs) or "cloud" in stats
    needs_moisture = bool({"color", "city_lights"} & requested_outputs) or "moisture" in stats
    needs_height = bool({"height", "normal"} & requested_outputs) or "height" in stats
    needs_preview_height = "color" in requested_outputs and normal_wrap_x
    needs_height = needs_height or needs_preview_height
    needs_roughness = "roughness" in requested_outputs
    needs_city_lights = "city_lights" in requested_outputs
    needs_color = "color" in requested_outputs
    needs_nebula = bool({"nebula_color", "nebula_alpha", "nebula_stars"} & requested_outputs)

    lat_abs = np.abs(np.sin(lat))
    land_layers = build_land_water_layers(cfg, x, y, z, land_threshold)
    land_field = land_layers["land_field"]
    threshold = land_layers["threshold"]
    land = land_layers["land"]
    shoreline = land_layers["shoreline"]
    shelf = land_layers["shelf"]
    ocean_depth = land_layers["ocean_depth"]
    map_height, map_width = x.shape
    if stats_only and stats <= {"land"}:
        return {"_land_field": land_field}

    cloud_field = None
    cloud_mask = None
    if needs_cloud:
        cloud_field = build_cloud_field(cfg, x, y, z, lat, land_field, threshold)
        if cloud_threshold is None:
            cloud_threshold = (
                float(np.quantile(cloud_field, 1.0 - float(np.clip(cfg.cloud_coverage, 0.0, 1.0))))
                if 0.0 < cfg.cloud_coverage < 1.0
                else 1.0
            )
        cloud_mask = cloud_mask_from_field(cfg, cloud_field, float(cloud_threshold))

    biome, moisture_input, moisture, desert_bias, forest_bias = build_climate_fields(
        cfg,
        x,
        y,
        z,
        lat_abs,
        shelf,
        moisture_range,
    )
    if stats_only and stats <= {"moisture"}:
        return {"_land_field": land_field, "_moisture_input": moisture_input}

    range_scale = max(1.0, cfg.mountain_scale * 0.38)
    range_spine = 1.0 - np.abs(fbm_3d(x, y, z, range_scale, 5, 0.62, cfg.seed + 4073) * 2.0 - 1.0)
    range_spine = np.power(np.clip(range_spine, 0.0, 1.0), 0.75 + cfg.mountain_sharpness * 1.45)
    ridge = 1.0 - np.abs(fbm_3d(x, y, z, cfg.mountain_scale, 6, 0.67, cfg.seed + 4111) * 2.0 - 1.0)
    ridge = np.power(np.clip(ridge, 0.0, 1.0), 0.85 + cfg.mountain_sharpness * 2.35)
    mountain_gate = fbm_3d(x, y, z, max(1.0, cfg.mountain_scale * 0.26), 4, 0.56, cfg.seed + 4229)
    mountain_cut = np.clip(0.92 - cfg.mountain_density * 0.58, 0.28, 0.88)
    range_mask = smoothstep(mountain_cut, min(1.0, mountain_cut + 0.20), range_spine)
    range_mask *= smoothstep(0.34, 0.72, mountain_gate)
    ridge_mask = smoothstep(max(0.0, mountain_cut - 0.16), min(1.0, mountain_cut + 0.22), ridge)
    band_mask = build_mountain_range_bands(x, y, z, cfg)
    band_mask *= 0.70 + mountain_gate * 0.30
    boundary_mask = build_continent_color_boundary_mask(cfg, x, y, z, land)
    plate_boundary = build_plate_boundary_field(cfg, x, y, z, land)
    boundary_range = np.clip(boundary_mask * (0.45 + ridge_mask * 0.55), 0.0, 1.0)
    range_mask = np.clip(range_mask + band_mask * (0.18 + ridge_mask * 0.42), 0.0, 1.0)
    range_mask = np.clip(range_mask + plate_boundary * (0.36 + ridge_mask * 0.54), 0.0, 1.0)
    range_mask = np.maximum(range_mask, boundary_range)
    mountain_mask = np.clip(range_mask * (0.48 + ridge_mask * 0.92) + ridge_mask * range_mask * 0.22, 0.0, 1.0)
    orogenic = build_orogenic_mountain_system(cfg, x, y, z, land, plate_boundary)
    alpine = build_alpine_range_system(cfg, lat, lon, land)
    range_uplift = np.maximum(orogenic["uplift"] * 0.58, alpine["uplift"])
    crest_mask = np.maximum(orogenic["crest"] * 0.52, alpine["crest"])
    peak_mask = np.maximum(orogenic["peaks"] * 0.56, alpine["peaks"])
    erosion_valleys = np.maximum(
        np.maximum(orogenic["valleys"], alpine["valleys"]),
        smoothstep(0.50, 0.88, mountain_mask) * 0.14 * float(np.clip(cfg.erosion_strength, 0.0, 1.0)),
    )
    craggy_relief = orogenic["crags"] * 0.34 + alpine["crags"] * 0.42
    mountain_mask = np.clip(np.maximum(mountain_mask * 0.42, range_uplift) + crest_mask * 0.22 + peak_mask * 0.48, 0.0, 1.0)
    orogenic_mask = np.clip(range_uplift * 0.78 + crest_mask * 0.74 + peak_mask * 0.95 + plate_boundary * 0.22, 0.0, 1.0)
    crater_layers = None
    if (needs_color or needs_height or needs_roughness) and crater_generation_enabled(cfg):
        crater_layers = build_crater_field(cfg, x, y, z, land)

    color = None
    regional_debug = None
    raw_height = None
    height = None
    normal_height = None
    roughness = None
    if needs_color:
        colors = resolve_planet_colors(cfg)
        color = np.zeros((map_height, map_width, 3), dtype=np.float32)
    else:
        colors = None

    ocean_variation = fbm_3d(x, y, z, 18.0, 4, 0.5, cfg.seed + 5111)
    if needs_color:
        ocean_color = color_blend(
            colors["deep_ocean"],
            colors["ocean_mid"],
            np.clip(ocean_variation * cfg.ocean_current_strength * 1.8, 0.0, 0.72),
        )
        ocean_color = color_blend(ocean_color, colors["shallow_ocean"], shelf)
    ocean_texture = fbm_3d(x, y, z, 32.0, 4, 0.52, cfg.seed + 5221)
    equator = 1.0 - lat_abs

    legacy_ocean_variation = np.clip(cfg.ocean_color_variation, 0.0, 1.0)
    shallow_tint_weight = np.power(np.clip(shelf, 0.0, 1.0), 0.65)
    deep_tint_weight = smoothstep(0.22, 1.0, ocean_depth)

    if needs_color:
        warm_shallow = np.array([68, 205, 190], dtype=np.float32)
        warm_shallow = (warm_shallow - 127.5) * cfg.ocean_shelf_contrast + 127.5
        warm_shallow = warm_shallow + cfg.ocean_shelf_brightness * 255.0
        warm_shallow = np.clip(warm_shallow, 0.0, 255.0)
        depth_blue = np.array([0, 8, 38], dtype=np.float32)
        cold_deep = np.array([42, 72, 102], dtype=np.float32)
        productive_teal = np.array([18, 154, 96], dtype=np.float32)
        sediment_tint = np.array([172, 154, 82], dtype=np.float32)
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
    if needs_color:
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
    if needs_color:
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
        land_color = color_blend(land_color, colors["rock"], np.clip(orogenic_mask * 1.10, 0.0, 0.96))
        land_color = color_blend(land_color, colors["beach"], shoreline * 0.78)

    if cfg.polar_ice_size <= 0.0:
        snow_mask = np.zeros_like(land_field, dtype=np.float32)
    else:
        snow_mask = smoothstep(cfg.snow_threshold, 1.0, crest_mask * 0.42 + peak_mask * 0.62 + lat_abs * 0.38)
    polar_ice, ice_texture = build_polar_ice_formation(cfg, x, y, z, lat, lon)
    ice_mask = np.maximum(snow_mask, polar_ice)

    soil_noise = fbm_3d(x, y, z, cfg.biome_scale * 2.4, 4, 0.52, cfg.seed + 6221)
    mineral_noise = fbm_3d(x, y, z, cfg.mountain_scale * 1.7, 4, 0.58, cfg.seed + 6331)
    cold_lat = smoothstep(0.42, 0.88, lat_abs)
    arid = np.clip(desert_bias + (1.0 - moisture) * 0.45, 0.0, 1.0)
    non_ice_land = 1.0 - np.clip(ice_mask, 0.0, 1.0)
    moon_basin_strength = float(np.clip(cfg.moon_basin_strength, 0.0, 1.0))
    moon_regolith_variation = float(np.clip(cfg.moon_regolith_variation, 0.0, 1.0))
    moon_basin_mask = np.zeros_like(land_field, dtype=np.float32)
    moon_regolith_noise = np.zeros_like(land_field, dtype=np.float32)
    if moon_basin_strength > 0.0 or moon_regolith_variation > 0.0:
        basin_scale = max(0.15, float(cfg.moon_basin_scale))
        basin_field = (
            fbm_3d(x, y, z, basin_scale, 4, 0.54, cfg.seed + 8123) * 0.72
            + fbm_3d(x, y, z, basin_scale * 2.2, 3, 0.55, cfg.seed + 8191) * 0.28
        )
        moon_basin_mask = smoothstep(0.58, 0.86, basin_field) * land.astype(np.float32) * moon_basin_strength
        moon_regolith_noise = fbm_3d(x, y, z, 54.0, 4, 0.56, cfg.seed + 8273)
    continent_lowland = 1.0 - smoothstep(threshold, threshold + cfg.continent_contrast * 1.8, land_field)
    lowland = continent_lowland
    ice_solidity = np.clip(cfg.polar_ice_solidity, 0.0, 1.0)
    polar_ice_color_mask = smoothstep(
        0.05 + (1.0 - ice_solidity) * 0.10,
        0.24 + (1.0 - ice_solidity) * 0.18,
        polar_ice,
    )
    polar_ice_color_mask = np.clip(
        lerp(polar_ice_color_mask, np.maximum(polar_ice_color_mask, polar_ice), ice_solidity),
        0.0,
        1.0,
    )
    family_masks = build_planet_family_masks(
        cfg,
        x,
        y,
        z,
        lat,
        lon,
        land,
        lowland,
        mountain_mask,
        moisture,
        arid,
        soil_noise,
        mineral_noise,
    )
    if needs_color:
        land_tints = resolve_land_tints(cfg)
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
            np.clip(orogenic_mask * mineral_noise * cfg.land_color_variation * 0.90 * non_ice_land, 0.0, 0.34),
        )
        mineral_exposure = np.clip(orogenic_mask * 0.88 + arid * 0.30 + soil_noise * 0.12, 0.0, 1.0)
        land_color = color_blend(
            land_color,
            rust_tint,
            np.clip(mineral_noise * mineral_exposure * cfg.mineral_tint_strength * non_ice_land, 0.0, 0.58),
        )
        exposed_dry = np.clip(arid * (0.60 + orogenic_mask * 0.48) * (0.45 + soil_noise * 0.55), 0.0, 1.0)
        basalt_exposure = np.clip((orogenic_mask * 0.70 + mineral_noise * 0.35) * smoothstep(0.48, 0.90, mineral_noise), 0.0, 1.0)
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
            np.clip(np.maximum(salt_basin, family_masks["dry_basin"] * 0.72) * cfg.salt_flat_tint_strength * non_ice_land, 0.0, 0.48),
        )
        family = family_masks["family"]
        if family in {"icy_moon", "frozen_world"} or cfg.volatile_ice_strength > 0.0:
            cryo_color = colors["ice"] * 0.58 + colors["snow"] * 0.42
            land_color = color_blend(
                land_color,
                cryo_color,
                np.clip(family_masks["volatile_ice"] * (0.54 + cfg.volatile_ice_strength * 0.36), 0.0, 0.88),
            )
        if family in {"volcanic_world", "carbon_world"} or cfg.lava_activity > 0.0:
            cooled_lava = np.array([24, 22, 20], dtype=np.float32)
            hot_lava = np.array([238, 86, 18], dtype=np.float32)
            lava_mask = np.clip(family_masks["lava"], 0.0, 1.0)
            land_color = color_blend(land_color, cooled_lava, np.clip(lava_mask * 0.72, 0.0, 0.78))
            land_color = color_blend(land_color, hot_lava, np.clip(lava_mask * cfg.lava_activity * 0.32, 0.0, 0.45))
        if family == "iron_rich":
            iron_color = np.array([146, 48, 26], dtype=np.float32)
            land_color = color_blend(land_color, iron_color, np.clip(arid * mineral_noise * 0.26 * non_ice_land, 0.0, 0.34))
        if family == "carbon_world":
            carbon_color = np.array([20, 22, 22], dtype=np.float32)
            land_color = color_blend(land_color, carbon_color, np.clip(family_masks["regolith"] * 0.32 * non_ice_land, 0.0, 0.42))
        if cfg.tidal_lock_strength > 0.0:
            day_tint = np.array([188, 116, 66], dtype=np.float32)
            night_tint = np.array([74, 96, 124], dtype=np.float32)
            day_weight = np.clip(np.maximum(family_masks["day_night"], 0.0) * 0.34 * non_ice_land, 0.0, 0.34)
            night_weight = np.clip(np.maximum(-family_masks["day_night"], 0.0) * 0.42 * non_ice_land, 0.0, 0.46)
            land_color = color_blend(land_color, day_tint, day_weight)
            land_color = color_blend(land_color, night_tint, night_weight)
        summit_highlight = np.clip((peak_mask * 1.35 + crest_mask * 0.44 + plate_boundary * 0.12) * (0.65 + mineral_noise * 0.35) * non_ice_land, 0.0, 1.0)
        light_rock = np.clip(colors["rock"] * 1.32 + 18.0, 0.0, 255.0)
        land_color = color_blend(land_color, light_rock, np.clip(summit_highlight * 0.44, 0.0, 0.44))
        eroded_face = np.clip(erosion_valleys * (0.55 + mineral_noise * 0.45) * non_ice_land, 0.0, 1.0)
        land_color = color_blend(land_color, colors["rock"] * 0.62, np.clip(eroded_face * 0.32, 0.0, 0.32))
        land_color = (land_color - 127.5) * cfg.land_contrast + 127.5
        land_color = land_color + cfg.land_brightness * 255.0
        land_color = np.clip(land_color, 0.0, 255.0)
        if moon_basin_strength > 0.0 or moon_regolith_variation > 0.0:
            maria_color = np.array([54, 54, 54], dtype=np.float32)
            highland_dust = np.array([168, 162, 146], dtype=np.float32)
            regolith_weight = np.clip((moon_regolith_noise - 0.5) * 2.0 * moon_regolith_variation, -1.0, 1.0)
            land_color = color_blend(land_color, maria_color, np.clip(moon_basin_mask * 0.82, 0.0, 0.86))
            land_color = color_blend(
                land_color,
                highland_dust,
                np.clip(np.maximum(regolith_weight, 0.0) * land.astype(np.float32) * 0.22, 0.0, 0.22),
            )
            land_color = color_blend(
                land_color,
                land_color * 0.72,
                np.clip(np.maximum(-regolith_weight, 0.0) * land.astype(np.float32) * 0.18, 0.0, 0.18),
            )
        solid_ice_tint = land_tints["solid_ice"]
        ice_highlight = color_blend(
            colors["ice"],
            colors["snow"],
            np.clip(ice_texture * 0.20 + ice_solidity * 0.54, 0.0, 0.76),
        )
        ice_highlight = color_blend(ice_highlight, solid_ice_tint, ice_solidity * 0.35)
        land_color = color_blend(land_color, colors["snow"], snow_mask)
        land_ice_strength = np.clip(polar_ice_color_mask * (0.70 + ice_solidity * 0.42), 0.0, 1.0)
        land_color = color_blend(land_color, ice_highlight, land_ice_strength)
        ocean_ice_strength = np.clip(
            polar_ice_color_mask * (0.30 + cfg.polar_ice_shelf_strength * 0.45 + ice_solidity * 0.46),
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
        if family_masks["family"] == "clouded_greenhouse":
            haze_color = np.array([222, 196, 126], dtype=np.float32)
            haze_strength = np.clip(build_atmosphere_haze_map(cfg, lat, cloud_mask) * 0.26, 0.0, 0.32)
            color = color_blend(color, haze_color, haze_strength)
        if crater_layers is not None and cfg.crater_color_strength > 0.0:
            crater_color_strength = float(np.clip(cfg.crater_color_strength, 0.0, 1.0))
            floor = crater_layers["floor"]
            rim = crater_layers["rim"]
            ejecta = crater_layers["ejecta"]
            rays = crater_layers["rays"]
            basin = crater_layers["basin"]
            micro = crater_layers["micro"]
            floor_darkening = float(np.clip(cfg.crater_floor_darkening, 0.0, 1.0))
            crater_shadow = color * 0.52
            crater_highlight = color * 0.60 + np.array([205, 190, 160], dtype=np.float32) * 0.40
            ray_highlight = color * 0.48 + np.array([225, 218, 194], dtype=np.float32) * 0.52
            basin_shadow = color * 0.42 + np.array([28, 28, 28], dtype=np.float32) * 0.58
            floor_tint = np.clip(floor * crater_color_strength * (0.62 + floor_darkening * 0.58), 0.0, 0.86)
            rim_tint = np.clip((rim * 1.08 + ejecta * 0.46) * crater_color_strength, 0.0, 0.82)
            ray_tint = np.clip(rays * crater_color_strength, 0.0, 0.84)
            basin_tint = np.clip(basin * crater_color_strength * (0.46 + floor_darkening * 0.50), 0.0, 0.82)
            micro_tint = np.clip(micro * crater_color_strength * floor_darkening * 0.20, 0.0, 0.24)
            color = color_blend(color, basin_shadow, basin_tint)
            color = color_blend(color, crater_shadow, floor_tint)
            color = color_blend(color, crater_highlight, rim_tint)
            color = color_blend(color, ray_highlight, ray_tint)
            color = color_blend(color, color * 0.82, micro_tint)

    if needs_height:
        continent_base_land_height = smoothstep(threshold - cfg.continent_contrast, threshold + cfg.continent_contrast, land_field)
        base_land_height = continent_base_land_height
        height = np.where(land, 0.38 + base_land_height * 0.20, 0.18 - ocean_depth * 0.18)
        mountain_relief = (
            np.power(np.clip(range_uplift, 0.0, 1.0), 1.18) * cfg.mountain_height * 0.28
            + np.power(np.clip(crest_mask, 0.0, 1.0), 1.70) * cfg.mountain_height * cfg.peak_prominence * 0.12
            + np.power(np.clip(peak_mask, 0.0, 1.0), 1.10) * cfg.mountain_height * cfg.peak_prominence * 2.10
            + np.power(np.clip(plate_boundary, 0.0, 1.0), 0.86) * cfg.plate_boundary_strength * 0.12
        )
        mountain_relief += craggy_relief * cfg.mountain_height * 0.12
        mountain_relief -= erosion_valleys * (0.070 + cfg.erosion_strength * 0.110)
        height += np.where(land, mountain_relief, 0.0)
        height += np.where(land, shoreline * 0.025, 0.0)
        height += np.where(
            land,
            polar_ice * (0.018 + ice_solidity * 0.034 + ice_texture * 0.026),
            polar_ice * cfg.polar_ice_shelf_strength * (0.008 + ice_solidity * 0.014),
        )
        if cfg.volatile_ice_strength > 0.0:
            height += family_masks["volatile_ice"] * (0.018 + cfg.volatile_ice_strength * 0.030)
        if cfg.lava_activity > 0.0:
            height += family_masks["lava"] * (0.018 + cfg.geologic_activity * 0.040)
        if moon_basin_strength > 0.0:
            height -= moon_basin_mask * 0.075
            height = lerp(height, height - np.clip(moon_basin_mask, 0.0, 1.0) * 0.018, moon_basin_strength * 0.35)
        if moon_regolith_variation > 0.0:
            regolith_relief = (moon_regolith_noise - 0.5) * moon_regolith_variation * 0.025
            height += np.where(land, regolith_relief, 0.0)
        if crater_layers is not None:
            crater_depth = float(np.clip(cfg.crater_depth, 0.0, 1.0))
            crater_rim_height = float(np.clip(cfg.crater_rim_height, 0.0, 1.0))
            floor = crater_layers["floor"]
            rim = crater_layers["rim"]
            ejecta = crater_layers["ejecta"]
            basin = crater_layers["basin"]
            micro = crater_layers["micro"]
            crater_floor_level = np.where(land, 0.30 + base_land_height * 0.025, height - ocean_depth * 0.06)
            crater_flatten = np.clip((floor * 0.92 + basin * 0.42) * (0.48 + crater_depth * 0.48), 0.0, 0.98)
            height = lerp(height, crater_floor_level, crater_flatten)
            height -= floor * crater_depth * 0.52
            height -= basin * crater_depth * 0.20
            height -= micro * crater_depth * 0.035
            height += rim * crater_rim_height * 0.44
            height += ejecta * crater_rim_height * 0.14
        raw_height = height
        normal_height = raw_height
        height = normalize01(raw_height, height_range)

    if stats_only and stats <= {"height"}:
        return {"_land_field": land_field, "_raw_height": raw_height}
    if stats_only and stats <= {"cloud"}:
        return {"_land_field": land_field, "_cloud_field": cloud_field}
    if stats_only:
        maps = {"_land_field": land_field}
        if "moisture" in stats:
            maps["_moisture_input"] = moisture_input
        if "height" in stats:
            maps["_raw_height"] = raw_height
        if "cloud" in stats:
            maps["_cloud_field"] = cloud_field
        return maps

    if needs_roughness:
        roughness = np.where(land, 0.72, 0.24)
        roughness = roughness + range_uplift * 0.16 + crest_mask * 0.18 + peak_mask * 0.32 + np.abs(craggy_relief) * 0.14 + plate_boundary * 0.10 + erosion_valleys * 0.12 - shelf * 0.07
        roughness = roughness + polar_ice * (0.06 + ice_solidity * 0.12 + ice_texture * 0.16)
        roughness = roughness + family_masks["regolith"] * 0.10
        roughness = roughness + family_masks["lava"] * 0.14
        roughness = roughness - family_masks["volatile_ice"] * 0.18
        if moon_regolith_variation > 0.0:
            roughness += np.where(land, (moon_regolith_noise - 0.5) * moon_regolith_variation * 0.10, 0.0)
        if crater_layers is not None:
            roughness = (
                roughness
                + crater_layers["rim"] * 0.22
                + crater_layers["ejecta"] * 0.12
                + crater_layers["rays"] * 0.08
                + crater_layers["micro"] * 0.16
                - crater_layers["floor"] * 0.05
                - crater_layers["basin"] * 0.06
            )
        roughness = np.clip(roughness, 0.0, 1.0)

    maps = {}
    if "color" in selected_maps:
        maps["color"] = color
    if needs_height:
        maps["height"] = height
    if "normal" in selected_maps:
        maps["normal"] = normal_from_height(normal_height if normal_height is not None else height, strength=7.5, wrap_x=normal_wrap_x)
    if "roughness" in selected_maps:
        maps["roughness"] = roughness
    if "land_mask" in selected_maps:
        maps["land_mask"] = land.astype(np.float32)
    if "shoreline_mask" in selected_maps:
        maps["shoreline_mask"] = shoreline
    if "ocean_depth" in selected_maps:
        maps["ocean_depth"] = ocean_depth
    if "cloud_mask" in selected_maps:
        maps["cloud_mask"] = cloud_mask
    if "cloud_shadow" in selected_maps:
        maps["cloud_shadow"] = build_cloud_shadow_map(cfg, cloud_mask)
    if needs_city_lights:
        maps["city_lights"] = build_city_lights_map(
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
    if needs_nebula:
        maps.update(build_nebula_maps(cfg, x, y, z))
    if "atmosphere_haze" in selected_maps:
        maps["atmosphere_haze"] = build_atmosphere_haze_map(cfg, lat, cloud_mask)
    if "emissive_heat" in selected_maps:
        maps["emissive_heat"] = build_emissive_heat_map(cfg, family_masks)
    if return_raw_stats:
        maps["_land_field"] = land_field
        if cloud_field is not None:
            maps["_cloud_field"] = cloud_field
        if needs_moisture:
            maps["_moisture_input"] = moisture_input
        if raw_height is not None:
            maps["_raw_height"] = raw_height
        maps["_continent_land"] = continent_land.astype(np.float32)
        maps["_island_land"] = island_land.astype(np.float32)
        if regional_debug is not None:
            maps["_continent_color_region"] = regional_debug
    return maps


def build_maps(cfg, map_names=None):
    x, y, z, lat, lon = sphere_vectors(cfg.width, cfg.height)
    return build_maps_from_vectors(cfg, x, y, z, lat, lon, normal_wrap_x=True, map_names=map_names)


QUAD_SPHERE_FACES = ("px", "nx", "py", "ny", "pz", "nz")


def build_quad_sphere_face_worker(job):
    (
        cfg,
        face,
        face_size,
        selected_maps,
        land_threshold,
        cloud_threshold,
        moisture_range,
        height_range,
        return_raw_stats,
        stat_fields,
    ) = job
    x, y, z, lat, lon = quad_sphere_face_vectors(face, face_size)
    maps = build_maps_from_vectors(
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
        return_raw_stats=return_raw_stats,
        map_names=selected_maps,
        stat_fields=stat_fields,
    )
    return face, maps


def build_quad_sphere_face_pass(
    cfg,
    face_size,
    selected_maps,
    *,
    quad_workers=1,
    land_threshold=None,
    cloud_threshold=None,
    moisture_range=None,
    height_range=None,
    return_raw_stats=False,
    stat_fields=None,
):
    worker_count = max(1, min(int(quad_workers), len(QUAD_SPHERE_FACES)))
    jobs = [
        (
            cfg,
            face,
            face_size,
            selected_maps,
            land_threshold,
            cloud_threshold,
            moisture_range,
            height_range,
            return_raw_stats,
            tuple(stat_fields or ()),
        )
        for face in QUAD_SPHERE_FACES
    ]
    if worker_count == 1:
        return dict(build_quad_sphere_face_worker(job) for job in jobs)
    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        return dict(executor.map(build_quad_sphere_face_worker, jobs))


def iter_quad_sphere_face_pass(
    cfg,
    face_size,
    selected_maps,
    *,
    quad_workers=1,
    land_threshold=None,
    cloud_threshold=None,
    moisture_range=None,
    height_range=None,
    return_raw_stats=False,
    stat_fields=None,
):
    worker_count = max(1, min(int(quad_workers), len(QUAD_SPHERE_FACES)))
    jobs = [
        (
            cfg,
            face,
            face_size,
            selected_maps,
            land_threshold,
            cloud_threshold,
            moisture_range,
            height_range,
            return_raw_stats,
            tuple(stat_fields or ()),
        )
        for face in QUAD_SPHERE_FACES
    ]
    if worker_count == 1:
        for job in jobs:
            yield build_quad_sphere_face_worker(job)
        return
    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        yield from executor.map(build_quad_sphere_face_worker, jobs)


def histogram_quantile(counts, q, value_range=(0.0, 1.0)):
    total = int(np.sum(counts))
    if total <= 0:
        return float(value_range[0])
    q = float(np.clip(q, 0.0, 1.0))
    target = q * max(total - 1, 0)
    index = int(np.searchsorted(np.cumsum(counts), target, side="left"))
    index = max(0, min(index, len(counts) - 1))
    low, high = value_range
    width = (high - low) / float(len(counts))
    return float(low + (index + 0.5) * width)


def update_histogram(counts, values, value_range=(0.0, 1.0)):
    hist, _ = np.histogram(values, bins=len(counts), range=value_range)
    counts += hist


def compute_quad_sphere_global_stats(cfg, face_size, selected_maps, quad_workers=1):
    selected_set = set(selected_maps)
    land_hist = np.zeros(4096, dtype=np.int64)
    for _, maps in iter_quad_sphere_face_pass(
        cfg,
        face_size,
        selected_maps,
        quad_workers=quad_workers,
        return_raw_stats=True,
        stat_fields=("land",),
    ):
        update_histogram(land_hist, maps["_land_field"])
    land_threshold = histogram_quantile(land_hist, land_threshold_quantile(cfg))

    stat_fields = []
    if selected_set & {"color", "city_lights"}:
        stat_fields.append("moisture")
    if selected_set & {"height", "normal"}:
        stat_fields.append("height")
    if selected_set & {"cloud_mask", "cloud_shadow"}:
        stat_fields.append("cloud")

    moisture_min = math.inf
    moisture_max = -math.inf
    height_min = math.inf
    height_max = -math.inf
    cloud_hist = np.zeros(4096, dtype=np.int64) if "cloud" in stat_fields else None

    if stat_fields:
        for _, maps in iter_quad_sphere_face_pass(
            cfg,
            face_size,
            selected_maps,
            quad_workers=quad_workers,
            land_threshold=land_threshold,
            return_raw_stats=True,
            stat_fields=stat_fields,
        ):
            if "moisture" in stat_fields:
                moisture = maps["_moisture_input"]
                moisture_min = min(moisture_min, float(np.min(moisture)))
                moisture_max = max(moisture_max, float(np.max(moisture)))
            if "height" in stat_fields:
                raw_height = maps["_raw_height"]
                height_min = min(height_min, float(np.min(raw_height)))
                height_max = max(height_max, float(np.max(raw_height)))
            if cloud_hist is not None:
                update_histogram(cloud_hist, maps["_cloud_field"])

    moisture_range = (moisture_min, moisture_max) if math.isfinite(moisture_min) else None
    height_range = (height_min, height_max) if math.isfinite(height_min) else None
    cloud_threshold = None
    if cloud_hist is not None:
        cloud_coverage = float(np.clip(cfg.cloud_coverage, 0.0, 1.0))
        cloud_threshold = histogram_quantile(cloud_hist, 1.0 - cloud_coverage) if 0.0 < cloud_coverage < 1.0 else 1.0

    return land_threshold, cloud_threshold, moisture_range, height_range


def build_quad_sphere_maps(cfg, face_size, map_names=None, quad_workers=1):
    selected_maps = selected_texture_maps(map_names)
    land_threshold, cloud_threshold, moisture_range, height_range = compute_quad_sphere_global_stats(
        cfg,
        face_size,
        selected_maps,
        quad_workers=quad_workers,
    )

    faces = build_quad_sphere_face_pass(
        cfg,
        face_size,
        selected_maps,
        quad_workers=quad_workers,
        land_threshold=land_threshold,
        cloud_threshold=cloud_threshold,
        moisture_range=moisture_range,
        height_range=height_range,
    )
    return reconcile_quad_sphere_scalar_seams(faces, selected_maps)


TEXTURE_MAP_NAMES = (
    "color",
    "height",
    "normal",
    "roughness",
    "land_mask",
    "shoreline_mask",
    "ocean_depth",
    "cloud_mask",
    "cloud_shadow",
    "nebula_color",
    "nebula_alpha",
    "nebula_stars",
    "city_lights",
    "atmosphere_haze",
    "emissive_heat",
)

QUAD_SPHERE_MAP_NAMES = TEXTURE_MAP_NAMES

CLOUD_16BIT_MAPS = {"cloud_mask", "cloud_shadow", "nebula_alpha", "nebula_stars", "atmosphere_haze", "emissive_heat"}


def selected_texture_maps(map_names=None):
    if map_names is None:
        return TEXTURE_MAP_NAMES
    selected = tuple(name for name in TEXTURE_MAP_NAMES if name in set(map_names))
    if not selected:
        raise ValueError("Choose at least one texture map to save.")
    return selected


def resolve_quad_workers(value=None):
    if value is None:
        value = os.environ.get("PLANET_QUAD_WORKERS", "auto")
    if isinstance(value, str) and value.strip().lower() in {"", "auto", "default"}:
        return max(1, min(os.cpu_count() or 1, len(QUAD_SPHERE_FACES)))
    try:
        workers = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Quad workers must be an integer or 'auto'.") from exc
    if workers < 1:
        raise ValueError("Quad workers must be at least 1.")
    return min(workers, len(QUAD_SPHERE_FACES))


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
        save_gray16(out_dir / "cloud_mask.png", maps["cloud_mask"])
    if "cloud_shadow" in selected:
        save_gray16(out_dir / "cloud_shadow.png", maps["cloud_shadow"])
    if "nebula_color" in selected:
        save_rgb(out_dir / "nebula_color.png", maps["nebula_color"])
    if "nebula_alpha" in selected:
        save_gray16(out_dir / "nebula_alpha.png", maps["nebula_alpha"])
    if "nebula_stars" in selected:
        save_gray16(out_dir / "nebula_stars.png", maps["nebula_stars"])
    if "city_lights" in selected:
        save_rgb(out_dir / "city_lights.png", maps["city_lights"])
    if "atmosphere_haze" in selected:
        save_gray16(out_dir / "atmosphere_haze.png", maps["atmosphere_haze"])
    if "emissive_heat" in selected:
        save_gray16(out_dir / "emissive_heat.png", maps["emissive_heat"])


CUBEMAP_CROSS_LAYOUT = {
    "py": (1, 0),
    "nx": (0, 1),
    "pz": (1, 1),
    "px": (2, 1),
    "nz": (3, 1),
    "ny": (1, 2),
}

QUAD_SPHERE_EDGE_PAIRS = (
    (("py", "top"), ("nz", "top"), True),
    (("py", "bottom"), ("pz", "top"), False),
    (("py", "left"), ("nx", "top"), False),
    (("py", "right"), ("px", "top"), True),
    (("nx", "bottom"), ("ny", "left"), True),
    (("nx", "left"), ("nz", "right"), False),
    (("nx", "right"), ("pz", "left"), False),
    (("pz", "bottom"), ("ny", "top"), False),
    (("pz", "right"), ("px", "left"), False),
    (("px", "bottom"), ("ny", "right"), False),
    (("px", "right"), ("nz", "left"), False),
    (("nz", "bottom"), ("ny", "bottom"), True),
)

QUAD_SPHERE_SCALAR_SEAM_MAPS = {"cloud_mask", "cloud_shadow", "nebula_alpha", "nebula_stars", "atmosphere_haze", "emissive_heat"}
CUBEMAP_CROSS_BLEED_PIXELS = 8


def quad_sphere_edge_view(arr, edge, offset=0):
    if edge == "top":
        return arr[offset, :]
    if edge == "bottom":
        return arr[-1 - offset, :]
    if edge == "left":
        return arr[:, offset]
    if edge == "right":
        return arr[:, -1 - offset]
    raise ValueError(f"Unknown quad-sphere edge: {edge}")


def set_quad_sphere_edge(arr, edge, values, offset=0):
    if edge == "top":
        arr[offset, :] = values
    elif edge == "bottom":
        arr[-1 - offset, :] = values
    elif edge == "left":
        arr[:, offset] = values
    elif edge == "right":
        arr[:, -1 - offset] = values
    else:
        raise ValueError(f"Unknown quad-sphere edge: {edge}")


def reconcile_quad_sphere_scalar_seams_from_files(out_dir, map_names, seam_width=2):
    selected = set(selected_texture_maps(map_names)) & QUAD_SPHERE_SCALAR_SEAM_MAPS
    if not selected:
        return

    for map_name in selected:
        bit_depth = 16 if map_name in CLOUD_16BIT_MAPS else 8
        face_arrays = {}
        for face in QUAD_SPHERE_FACES:
            path = out_dir / face / f"{map_name}.png"
            if not path.exists():
                face_arrays = {}
                break
            with Image.open(path) as image:
                if bit_depth == 16:
                    face_arrays[face] = np.asarray(image, dtype=np.float32).copy()
                else:
                    face_arrays[face] = np.asarray(image.convert("L"), dtype=np.float32).copy()
        if not face_arrays:
            continue

        max_width = max(1, min(int(seam_width), min(arr.shape[0] for arr in face_arrays.values()) // 2))
        for offset in range(max_width):
            blend = 1.0 if offset == 0 else 0.42 / float(offset + 1)
            for (face_a, edge_a), (face_b, edge_b), reverse_b in QUAD_SPHERE_EDGE_PAIRS:
                edge_values_a = quad_sphere_edge_view(face_arrays[face_a], edge_a, offset).copy()
                edge_values_b = quad_sphere_edge_view(face_arrays[face_b], edge_b, offset).copy()
                matched_b = edge_values_b[::-1] if reverse_b else edge_values_b
                averaged = (edge_values_a + matched_b) * 0.5
                new_a = edge_values_a * (1.0 - blend) + averaged * blend
                new_b = edge_values_b * (1.0 - blend) + (averaged[::-1] if reverse_b else averaged) * blend
                set_quad_sphere_edge(face_arrays[face_a], edge_a, new_a, offset)
                set_quad_sphere_edge(face_arrays[face_b], edge_b, new_b, offset)

        for face, arr in face_arrays.items():
            if bit_depth == 16:
                Image.fromarray(np.clip(arr, 0, 65535).astype(np.uint16)).save(out_dir / face / f"{map_name}.png")
            else:
                Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "L").save(out_dir / face / f"{map_name}.png")


def reconcile_quad_sphere_scalar_seams(faces, map_names, seam_width=2):
    selected = set(selected_texture_maps(map_names)) & QUAD_SPHERE_SCALAR_SEAM_MAPS
    if not selected:
        return faces

    for map_name in selected:
        if any(map_name not in faces.get(face, {}) for face in QUAD_SPHERE_FACES):
            continue
        max_width = max(
            1,
            min(int(seam_width), min(faces[face][map_name].shape[0] for face in QUAD_SPHERE_FACES) // 2),
        )
        for offset in range(max_width):
            blend = 1.0 if offset == 0 else 0.42 / float(offset + 1)
            for (face_a, edge_a), (face_b, edge_b), reverse_b in QUAD_SPHERE_EDGE_PAIRS:
                edge_values_a = quad_sphere_edge_view(faces[face_a][map_name], edge_a, offset).copy()
                edge_values_b = quad_sphere_edge_view(faces[face_b][map_name], edge_b, offset).copy()
                matched_b = edge_values_b[::-1] if reverse_b else edge_values_b
                averaged = (edge_values_a + matched_b) * 0.5
                new_a = edge_values_a * (1.0 - blend) + averaged * blend
                new_b = edge_values_b * (1.0 - blend) + (averaged[::-1] if reverse_b else averaged) * blend
                set_quad_sphere_edge(faces[face_a][map_name], edge_a, new_a, offset)
                set_quad_sphere_edge(faces[face_b][map_name], edge_b, new_b, offset)
    return faces


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
    if map_name in CLOUD_16BIT_MAPS:
        bleed_cubemap_cross_empty_cells(cross, face_size)
    return np.rot90(cross, k=3)


def bleed_cubemap_cross_empty_cells(cross, face_size, bleed_pixels=CUBEMAP_CROSS_BLEED_PIXELS):
    face_size = int(face_size)
    bleed_pixels = max(0, min(int(bleed_pixels), face_size // 2))
    if bleed_pixels <= 0:
        return cross

    cell_to_face = {cell: face for face, cell in CUBEMAP_CROSS_LAYOUT.items()}
    for col in range(4):
        for row in range(3):
            if (col, row) in cell_to_face:
                continue
            y0 = row * face_size
            x0 = col * face_size
            cell = cross[y0 : y0 + face_size, x0 : x0 + face_size, :]

            left_face = cell_to_face.get((col - 1, row))
            if left_face is not None:
                lx0 = (col - 1) * face_size
                ly0 = row * face_size
                source = cross[ly0 : ly0 + face_size, lx0 + face_size - bleed_pixels : lx0 + face_size, :][:, ::-1, :]
                cell[:, :bleed_pixels, :] = source

            right_face = cell_to_face.get((col + 1, row))
            if right_face is not None:
                rx0 = (col + 1) * face_size
                ry0 = row * face_size
                source = cross[ry0 : ry0 + face_size, rx0 : rx0 + bleed_pixels, :][:, ::-1, :]
                cell[:, face_size - bleed_pixels : face_size, :] = source

            top_face = cell_to_face.get((col, row - 1))
            if top_face is not None:
                tx0 = col * face_size
                ty0 = (row - 1) * face_size
                source = cross[ty0 + face_size - bleed_pixels : ty0 + face_size, tx0 : tx0 + face_size, :][::-1, :, :]
                cell[:bleed_pixels, :, :] = source

            bottom_face = cell_to_face.get((col, row + 1))
            if bottom_face is not None:
                bx0 = col * face_size
                by0 = (row + 1) * face_size
                source = cross[by0 : by0 + bleed_pixels, bx0 : bx0 + face_size, :][::-1, :, :]
                cell[face_size - bleed_pixels : face_size, :, :] = source

    return cross


def save_quad_sphere_cubemap_crosses(out_dir, faces, face_size, map_names=None):
    for map_name in selected_texture_maps(map_names):
        cross = build_cubemap_cross(faces, map_name, face_size)
        path = out_dir / f"{map_name}_cubemap_cross.png"
        if cross.shape[2] == 4:
            save_rgba(path, cross)
        elif map_name in CLOUD_16BIT_MAPS:
            save_luminance_alpha16(path, cross)
        else:
            save_luminance_alpha(path, cross)


def save_quad_sphere_cubemap_crosses_from_files(out_dir, face_size, map_names=None):
    for map_name in selected_texture_maps(map_names):
        face_path = out_dir / "px" / f"{map_name}.png"
        with Image.open(face_path) as sample_image:
            is_scalar = sample_image.mode in {"L", "I", "I;16", "I;16B", "I;16L"}
            bit_depth = 16 if map_name in CLOUD_16BIT_MAPS else 8
        save_quad_sphere_cubemap_cross_streamed(out_dir, map_name, face_size, is_scalar, bit_depth=bit_depth)


def save_quad_sphere_cubemap_cross_streamed(out_dir, map_name, face_size, is_scalar, bit_depth=8):
    face_size = int(face_size)
    cell_to_face = {cell: face for face, cell in CUBEMAP_CROSS_LAYOUT.items()}
    channels = 2 if is_scalar else 4
    color_type = 4 if is_scalar else 6
    bleed_pixels = min(CUBEMAP_CROSS_BLEED_PIXELS, max(0, face_size // 2)) if map_name in CLOUD_16BIT_MAPS else 0
    if is_scalar:
        dtype = np.uint16 if bit_depth == 16 else np.uint8
        alpha_value = 65535 if bit_depth == 16 else 255
        empty = np.zeros((face_size, channels), dtype=dtype)
        empty[:, 1] = 0
    elif map_name == "normal":
        empty = np.zeros((face_size, channels), dtype=np.uint8)
        empty[:, 0] = 128
        empty[:, 1] = 128
        empty[:, 2] = 255
    else:
        empty = np.zeros((face_size, channels), dtype=np.uint8)

    def load_face_array(face):
        path = out_dir / face / f"{map_name}.png"
        with Image.open(path) as image:
            if is_scalar:
                if bit_depth == 16:
                    lum = np.asarray(image, dtype=np.uint16)
                else:
                    lum = np.asarray(image.convert("L"), dtype=np.uint8)
                alpha = np.full(lum.shape, alpha_value, dtype=lum.dtype)
                return np.stack((lum, alpha), axis=-1)
            return np.asarray(image.convert("RGBA"), dtype=np.uint8)

    def load_bleed_edges():
        if bleed_pixels <= 0:
            return {}
        edges = {}
        for face in QUAD_SPHERE_FACES:
            arr = load_face_array(face)
            edges[face] = {
                "left_columns": arr[::-1, :bleed_pixels, :],
                "right_columns": arr[::-1, face_size - bleed_pixels : face_size, :],
                "top_rows": arr[:bleed_pixels, :, :],
                "bottom_rows": arr[face_size - bleed_pixels : face_size, :, :],
            }
        return edges

    bleed_edges = load_bleed_edges()

    def empty_cell_column(layout_col, layout_row, local_col):
        if bleed_pixels <= 0:
            return empty
        cell = np.array(empty, copy=True)

        left_face = cell_to_face.get((layout_col - 1, layout_row))
        if left_face is not None and local_col < bleed_pixels:
            source_col = bleed_edges[left_face]["right_columns"][:, bleed_pixels - 1 - local_col, :]
            cell[:, :] = source_col

        right_face = cell_to_face.get((layout_col + 1, layout_row))
        if right_face is not None and local_col >= face_size - bleed_pixels:
            offset = local_col - (face_size - bleed_pixels)
            source_col = bleed_edges[right_face]["left_columns"][:, bleed_pixels - 1 - offset, :]
            cell[:, :] = source_col

        top_face = cell_to_face.get((layout_col, layout_row - 1))
        if top_face is not None:
            for offset in range(bleed_pixels):
                cell[face_size - 1 - offset, :] = bleed_edges[top_face]["bottom_rows"][bleed_pixels - 1 - offset, local_col, :]

        bottom_face = cell_to_face.get((layout_col, layout_row + 1))
        if bottom_face is not None:
            for offset in range(bleed_pixels):
                cell[offset, :] = bleed_edges[bottom_face]["top_rows"][offset, local_col, :]

        return cell

    def load_column_faces(layout_col):
        arrays = {}
        for layout_row in range(3):
            face = cell_to_face.get((layout_col, layout_row))
            if face is None:
                continue
            arrays[face] = load_face_array(face)
        return arrays

    def rows():
        for layout_col in range(4):
            arrays = load_column_faces(layout_col)
            for local_col in range(face_size):
                chunks = []
                for layout_row in (2, 1, 0):
                    face = cell_to_face.get((layout_col, layout_row))
                    if face is None:
                        chunks.append(empty_cell_column(layout_col, layout_row, local_col))
                    else:
                        chunks.append(arrays[face][::-1, local_col, :])
                row = np.concatenate(chunks, axis=0)
                if bit_depth == 16:
                    row = row.astype(">u2", copy=False)
                yield row.tobytes()
            del arrays

    write_streamed_png(
        out_dir / f"{map_name}_cubemap_cross.png",
        face_size * 3,
        face_size * 4,
        color_type,
        rows(),
        bit_depth=bit_depth,
    )


def quad_sphere_low_memory_map_groups(selected_maps):
    selected = set(selected_maps)
    groups = []
    for group in (
        ("color",),
        ("height", "normal"),
        ("roughness",),
        ("land_mask",),
        ("shoreline_mask",),
        ("ocean_depth",),
        ("cloud_mask", "cloud_shadow"),
        ("nebula_color", "nebula_alpha", "nebula_stars"),
        ("city_lights",),
        ("atmosphere_haze",),
        ("emissive_heat",),
    ):
        present = tuple(name for name in group if name in selected)
        if present:
            groups.append(present)
    return groups


def should_write_quad_sphere_crosses(face_size):
    value = os.environ.get("PLANET_WRITE_STITCHED_CROSSES")
    if value is not None:
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return True


def resolve_quad_tile_rows(face_size):
    value = os.environ.get("PLANET_QUAD_TILE_ROWS")
    if value is None:
        return 128 if int(face_size) >= 4096 else 256
    try:
        rows = int(value)
    except ValueError as exc:
        raise ValueError("PLANET_QUAD_TILE_ROWS must be an integer.") from exc
    if rows < 16:
        raise ValueError("PLANET_QUAD_TILE_ROWS must be at least 16.")
    return min(rows, int(face_size))


def iter_quad_sphere_face_tiles(face, face_size, tile_rows):
    for row_start in range(0, int(face_size), int(tile_rows)):
        row_stop = min(int(face_size), row_start + int(tile_rows))
        x, y, z, lat, lon = quad_sphere_face_vectors_tile(face, face_size, row_start, row_stop)
        yield row_start, row_stop, x, y, z, lat, lon


def compute_quad_sphere_color_stats_tiled(cfg, face_size, tile_rows=None):
    tile_rows = resolve_quad_tile_rows(face_size) if tile_rows is None else int(tile_rows)
    land_hist = np.zeros(4096, dtype=np.int64)
    for face in QUAD_SPHERE_FACES:
        for _, _, x, y, z, lat, lon in iter_quad_sphere_face_tiles(face, face_size, tile_rows):
            maps = build_maps_from_vectors(
                cfg,
                x,
                y,
                z,
                lat,
                lon,
                normal_wrap_x=False,
                return_raw_stats=True,
                map_names=("color",),
                stat_fields=("land",),
            )
            update_histogram(land_hist, maps["_land_field"])
            del maps, x, y, z, lat, lon
    land_threshold = histogram_quantile(land_hist, land_threshold_quantile(cfg))

    moisture_min = math.inf
    moisture_max = -math.inf
    for face in QUAD_SPHERE_FACES:
        for _, _, x, y, z, lat, lon in iter_quad_sphere_face_tiles(face, face_size, tile_rows):
            maps = build_maps_from_vectors(
                cfg,
                x,
                y,
                z,
                lat,
                lon,
                normal_wrap_x=False,
                land_threshold=land_threshold,
                return_raw_stats=True,
                map_names=("color",),
                stat_fields=("moisture",),
            )
            moisture = maps["_moisture_input"]
            moisture_min = min(moisture_min, float(np.min(moisture)))
            moisture_max = max(moisture_max, float(np.max(moisture)))
            del maps, x, y, z, lat, lon
    moisture_range = (moisture_min, moisture_max) if math.isfinite(moisture_min) else None
    return land_threshold, moisture_range


def save_quad_sphere_color_faces_tiled(out_dir, cfg, face_size, tile_rows=None):
    tile_rows = resolve_quad_tile_rows(face_size) if tile_rows is None else int(tile_rows)
    land_threshold, moisture_range = compute_quad_sphere_color_stats_tiled(cfg, face_size, tile_rows)
    for face in QUAD_SPHERE_FACES:
        face_dir = out_dir / face
        face_dir.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (int(face_size), int(face_size)))
        for row_start, _, x, y, z, lat, lon in iter_quad_sphere_face_tiles(face, face_size, tile_rows):
            maps = build_maps_from_vectors(
                cfg,
                x,
                y,
                z,
                lat,
                lon,
                normal_wrap_x=False,
                land_threshold=land_threshold,
                moisture_range=moisture_range,
                map_names=("color",),
            )
            tile = Image.fromarray(np.clip(maps["color"], 0, 255).astype(np.uint8), "RGB")
            image.paste(tile, (0, row_start))
            tile.close()
            del maps, x, y, z, lat, lon
        image.save(face_dir / "color.png")
        image.close()


def save_quad_sphere_maps_low_memory(out_dir, cfg, face_size, map_names=None, quad_workers=1, write_cubemap_crosses=None):
    selected_maps = selected_texture_maps(map_names)
    resolved_quad_workers = resolve_quad_workers(quad_workers)
    if selected_maps == ("color",) and resolved_quad_workers == 1:
        save_quad_sphere_color_faces_tiled(out_dir, cfg, face_size)
        if write_cubemap_crosses is None:
            write_cubemap_crosses = should_write_quad_sphere_crosses(face_size)
        if write_cubemap_crosses:
            save_quad_sphere_cubemap_crosses_from_files(out_dir, face_size, selected_maps)
        return

    land_threshold, cloud_threshold, moisture_range, height_range = compute_quad_sphere_global_stats(
        cfg,
        face_size,
        selected_maps,
        quad_workers=resolved_quad_workers,
    )
    for group in quad_sphere_low_memory_map_groups(selected_maps):
        for face, maps in iter_quad_sphere_face_pass(
            cfg,
            face_size,
            group,
            quad_workers=resolved_quad_workers,
            land_threshold=land_threshold,
            cloud_threshold=cloud_threshold,
            moisture_range=moisture_range,
            height_range=height_range,
        ):
            face_dir = out_dir / face
            face_dir.mkdir(parents=True, exist_ok=True)
            save_map_set(face_dir, maps, group)
            del maps
    reconcile_quad_sphere_scalar_seams_from_files(out_dir, selected_maps)
    if write_cubemap_crosses is None:
        write_cubemap_crosses = should_write_quad_sphere_crosses(face_size)
    if write_cubemap_crosses:
        save_quad_sphere_cubemap_crosses_from_files(out_dir, face_size, selected_maps)


def write_quad_sphere_manifest(out_dir, face_size, map_names=None, write_cubemap_crosses=None):
    selected = selected_texture_maps(map_names)
    if write_cubemap_crosses is None:
        write_cubemap_crosses = should_write_quad_sphere_crosses(face_size)
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
            "maps": [f"quad_sphere/{name}_cubemap_cross.png" for name in selected] if write_cubemap_crosses else [],
            "written": bool(write_cubemap_crosses),
            "skip_reason": None
            if write_cubemap_crosses
            else "Skipped because PLANET_WRITE_STITCHED_CROSSES is disabled.",
            "empty_cells": {
                "default": "transparent alpha 0",
                "cloud_mask": f"{CUBEMAP_CROSS_BLEED_PIXELS}px copied edge bleed around face borders; remaining empty-cell interior stays alpha 0",
                "cloud_shadow": f"{CUBEMAP_CROSS_BLEED_PIXELS}px copied edge bleed around face borders; remaining empty-cell interior stays alpha 0",
                "nebula_alpha": f"{CUBEMAP_CROSS_BLEED_PIXELS}px copied edge bleed around face borders; remaining empty-cell interior stays alpha 0",
                "nebula_stars": f"{CUBEMAP_CROSS_BLEED_PIXELS}px copied edge bleed around face borders; remaining empty-cell interior stays alpha 0",
                "atmosphere_haze": f"{CUBEMAP_CROSS_BLEED_PIXELS}px copied edge bleed around face borders; remaining empty-cell interior stays alpha 0",
                "emissive_heat": f"{CUBEMAP_CROSS_BLEED_PIXELS}px copied edge bleed around face borders; remaining empty-cell interior stays alpha 0",
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
    if getattr(args, "land_palette", None) is not None:
        data["land_palette"] = args.land_palette
        apply_palette_defaults_to_config_values(data, args.land_palette)
    for key in list(data):
        if key == "land_palette":
            continue
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
    parser.add_argument("--quad-workers", default=None, help="Worker processes for quad-sphere face generation. Defaults to PLANET_QUAD_WORKERS or auto.")
    parser.add_argument("--out", type=Path, default=Path("planet_output"))
    parser.add_argument(
        "--texture-maps",
        nargs="+",
        choices=TEXTURE_MAP_NAMES,
        default=None,
        metavar="MAP",
        help="Texture maps to save. Omit to save all maps.",
    )
    parser.add_argument("--profile", action="store_true", help="Print cProfile timing for the generation and save path.")
    parser.add_argument("--profile-limit", type=int, default=40, help="Number of profile rows to print when --profile is enabled.")
    parser.add_argument("--profile-out", type=Path, default=None, help="Optional path to write raw .prof data for tools like snakeviz.")
    for key, value in PRESETS["earthlike"].items():
        if key == "planet_family":
            parser.add_argument(
                f"--{key.replace('_', '-')}",
                dest=key,
                choices=sorted(PLANET_FAMILIES),
                default=None,
            )
            continue
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


def generate_planet_output(cfg, out_dir, quad_sphere=False, face_size=None, texture_maps=None, quad_workers=1):
    selected_maps = selected_texture_maps(texture_maps)
    if quad_sphere:
        resolved_quad_workers = resolve_quad_workers(quad_workers)
        quad_dir = out_dir / "quad_sphere"
        quad_dir.mkdir(parents=True, exist_ok=True)
        save_quad_sphere_maps_low_memory(quad_dir, cfg, face_size, selected_maps, quad_workers=resolved_quad_workers)
        write_quad_sphere_manifest(out_dir, face_size, selected_maps)
    else:
        maps = build_maps(cfg, selected_maps)
        save_map_set(out_dir, maps, selected_maps)
        if "color" in selected_maps:
            render_globe_preview(maps["color"], maps["height"], out_dir / "preview.png")
            write_html_preview(out_dir, f"{cfg.preset} planet preview", selected_maps)

    metadata = asdict(cfg)
    metadata["output_projection"] = "quad_sphere" if quad_sphere else "equirectangular"
    metadata["output_texture_maps"] = list(selected_maps)
    if quad_sphere:
        metadata["quad_sphere_face_size"] = face_size
    resolved_palette = resolve_planet_colors(cfg)
    metadata["resolved_palette_rgb"] = {
        name: [int(round(channel)) for channel in color]
        for name, color in resolved_palette.items()
    }
    (out_dir / "preset.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def run_profiled(callable_obj, limit=40, profile_out=None):
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        callable_obj()
    finally:
        profiler.disable()
    if profile_out is not None:
        profile_out.parent.mkdir(parents=True, exist_ok=True)
        profiler.dump_stats(str(profile_out))
        print(f"Wrote raw profile data to {profile_out.resolve()}")
    stats = pstats.Stats(profiler).strip_dirs().sort_stats("cumtime")
    stats.print_stats(max(1, int(limit)))


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

    if args.profile:
        run_profiled(
            lambda: generate_planet_output(cfg, out_dir, args.quad_sphere, face_size, args.texture_maps, args.quad_workers),
            limit=args.profile_limit,
            profile_out=args.profile_out,
        )
    else:
        generate_planet_output(cfg, out_dir, args.quad_sphere, face_size, args.texture_maps, args.quad_workers)
    print(f"Wrote planet maps to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
