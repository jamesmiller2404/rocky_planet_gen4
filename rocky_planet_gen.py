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
        "land_color_variation": 0.22,
        "ocean_color_variation": 0.18,
        "ocean_shallow_tint_strength": 0.38,
        "ocean_depth_tint_strength": 0.34,
        "ocean_latitude_tint_strength": 0.30,
        "ocean_productivity_strength": 0.28,
        "ocean_sediment_strength": 0.22,
        "ocean_brightness": 0.00,
        "ocean_contrast": 1.00,
        "mineral_tint_strength": 0.26,
        "wetland_tint_strength": 0.16,
        "iron_oxide_tint_strength": 0.12,
        "basalt_tint_strength": 0.08,
        "salt_flat_tint_strength": 0.05,
        "clay_tint_strength": 0.10,
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
        "land_color_variation": 0.26,
        "ocean_color_variation": 0.24,
        "ocean_shallow_tint_strength": 0.56,
        "ocean_depth_tint_strength": 0.26,
        "ocean_latitude_tint_strength": 0.18,
        "ocean_productivity_strength": 0.42,
        "ocean_sediment_strength": 0.34,
        "ocean_brightness": 0.04,
        "ocean_contrast": 1.08,
        "mineral_tint_strength": 0.18,
        "wetland_tint_strength": 0.20,
        "iron_oxide_tint_strength": 0.08,
        "basalt_tint_strength": 0.10,
        "salt_flat_tint_strength": 0.03,
        "clay_tint_strength": 0.12,
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
        "land_color_variation": 0.24,
        "ocean_color_variation": 0.14,
        "ocean_shallow_tint_strength": 0.24,
        "ocean_depth_tint_strength": 0.32,
        "ocean_latitude_tint_strength": 0.28,
        "ocean_productivity_strength": 0.18,
        "ocean_sediment_strength": 0.30,
        "ocean_brightness": -0.03,
        "ocean_contrast": 1.10,
        "mineral_tint_strength": 0.28,
        "wetland_tint_strength": 0.12,
        "iron_oxide_tint_strength": 0.18,
        "basalt_tint_strength": 0.12,
        "salt_flat_tint_strength": 0.08,
        "clay_tint_strength": 0.16,
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
        "land_color_variation": 0.34,
        "ocean_color_variation": 0.08,
        "ocean_shallow_tint_strength": 0.16,
        "ocean_depth_tint_strength": 0.20,
        "ocean_latitude_tint_strength": 0.16,
        "ocean_productivity_strength": 0.08,
        "ocean_sediment_strength": 0.12,
        "ocean_brightness": -0.02,
        "ocean_contrast": 1.06,
        "mineral_tint_strength": 0.38,
        "wetland_tint_strength": 0.06,
        "iron_oxide_tint_strength": 0.30,
        "basalt_tint_strength": 0.18,
        "salt_flat_tint_strength": 0.14,
        "clay_tint_strength": 0.12,
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
        "land_color_variation": 0.16,
        "ocean_color_variation": 0.16,
        "ocean_shallow_tint_strength": 0.18,
        "ocean_depth_tint_strength": 0.42,
        "ocean_latitude_tint_strength": 0.62,
        "ocean_productivity_strength": 0.10,
        "ocean_sediment_strength": 0.06,
        "ocean_brightness": 0.06,
        "ocean_contrast": 0.88,
        "mineral_tint_strength": 0.14,
        "wetland_tint_strength": 0.08,
        "iron_oxide_tint_strength": 0.05,
        "basalt_tint_strength": 0.08,
        "salt_flat_tint_strength": 0.03,
        "clay_tint_strength": 0.06,
    },
}


COLORS = {
    "deep_ocean": np.array([4, 20, 66], dtype=np.float32),
    "ocean_mid": np.array([7, 72, 118], dtype=np.float32),
    "shallow_ocean": np.array([35, 154, 166], dtype=np.float32),
    "beach": np.array([196, 178, 119], dtype=np.float32),
    "dark_forest": np.array([6, 54, 18], dtype=np.float32),
    "forest": np.array([18, 125, 34], dtype=np.float32),
    "grass": np.array([70, 155, 38], dtype=np.float32),
    "dry_plain": np.array([94, 76, 42], dtype=np.float32),
    "desert": np.array([128, 86, 45], dtype=np.float32),
    "rock": np.array([88, 84, 76], dtype=np.float32),
    "snow": np.array([235, 242, 238], dtype=np.float32),
    "ice": np.array([194, 228, 240], dtype=np.float32),
}


def vary_palette(seed, preset):
    rng = np.random.default_rng(seed * 1009 + sum(ord(c) for c in preset))
    global_hue = rng.uniform(-0.035, 0.035)
    global_sat = rng.uniform(0.88, 1.18)
    global_val = rng.uniform(0.90, 1.10)
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
    for name, rgb in COLORS.items():
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
    land_color_variation: float
    ocean_color_variation: float
    ocean_shallow_tint_strength: float
    ocean_depth_tint_strength: float
    ocean_latitude_tint_strength: float
    ocean_productivity_strength: float
    ocean_sediment_strength: float
    ocean_brightness: float
    ocean_contrast: float
    mineral_tint_strength: float
    wetland_tint_strength: float
    iron_oxide_tint_strength: float
    basalt_tint_strength: float
    salt_flat_tint_strength: float
    clay_tint_strength: float


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
    moisture_range=None,
    height_range=None,
    return_raw_stats=False,
):
    lat_abs = np.abs(np.sin(lat))
    colors = vary_palette(cfg.seed, cfg.preset)

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
    ochre_tint = np.array([126, 98, 50], dtype=np.float32)
    rust_tint = np.array([98, 50, 30], dtype=np.float32)
    dark_wet_tint = np.array([24, 58, 28], dtype=np.float32)
    cool_tundra_tint = np.array([70, 100, 70], dtype=np.float32)
    pale_highland_tint = np.array([118, 112, 94], dtype=np.float32)
    iron_oxide_tint = np.array([122, 48, 28], dtype=np.float32)
    basalt_tint = np.array([36, 38, 40], dtype=np.float32)
    salt_flat_tint = np.array([218, 210, 178], dtype=np.float32)
    clay_tint = np.array([146, 92, 58], dtype=np.float32)
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
    continent_lowland = 1.0 - smoothstep(threshold, threshold + cfg.continent_contrast * 1.8, land_field)
    lowland = continent_lowland
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
    ice_solidity = np.clip(cfg.polar_ice_solidity, 0.0, 1.0)
    solid_ice_tint = np.array([244, 248, 248], dtype=np.float32)
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

    maps = {
        "color": color,
        "height": height,
        "normal": normal_from_height(height, wrap_x=normal_wrap_x),
        "roughness": roughness,
        "land_mask": land.astype(np.float32),
        "shoreline_mask": shoreline,
        "ocean_depth": ocean_depth,
    }
    if return_raw_stats:
        maps["_land_field"] = land_field
        maps["_moisture_input"] = moisture_input
        maps["_raw_height"] = raw_height
        maps["_continent_land"] = continent_land.astype(np.float32)
        maps["_island_land"] = island_land.astype(np.float32)
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
    moisture_range = (float(np.min(all_moisture)), float(np.max(all_moisture)))
    height_range = (float(np.min(all_height)), float(np.max(all_height)))

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
    metadata["resolved_palette_rgb"] = {
        name: [int(round(channel)) for channel in color]
        for name, color in vary_palette(cfg.seed, cfg.preset).items()
    }
    (out_dir / "preset.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote planet maps to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
