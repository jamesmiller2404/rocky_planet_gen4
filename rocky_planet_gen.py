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
        "biome_scale": 8.0,
        "biome_complexity": 6,
        "desert_coverage": 0.27,
        "forest_coverage": 0.56,
        "mountain_density": 0.42,
        "mountain_scale": 16.0,
        "mountain_sharpness": 0.68,
        "mountain_height": 0.62,
        "polar_ice_size": 0.16,
        "snow_threshold": 0.74,
        "ocean_current_strength": 0.18,
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
        "biome_scale": 12.0,
        "biome_complexity": 7,
        "desert_coverage": 0.18,
        "forest_coverage": 0.66,
        "mountain_density": 0.34,
        "mountain_scale": 20.0,
        "mountain_sharpness": 0.55,
        "mountain_height": 0.42,
        "polar_ice_size": 0.08,
        "snow_threshold": 0.82,
        "ocean_current_strength": 0.24,
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
        "biome_scale": 6.5,
        "biome_complexity": 6,
        "desert_coverage": 0.46,
        "forest_coverage": 0.36,
        "mountain_density": 0.55,
        "mountain_scale": 11.0,
        "mountain_sharpness": 0.78,
        "mountain_height": 0.78,
        "polar_ice_size": 0.20,
        "snow_threshold": 0.70,
        "ocean_current_strength": 0.12,
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
        "biome_scale": 10.0,
        "biome_complexity": 7,
        "desert_coverage": 0.72,
        "forest_coverage": 0.12,
        "mountain_density": 0.62,
        "mountain_scale": 18.0,
        "mountain_sharpness": 0.86,
        "mountain_height": 0.86,
        "polar_ice_size": 0.04,
        "snow_threshold": 0.88,
        "ocean_current_strength": 0.08,
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
        "biome_scale": 7.0,
        "biome_complexity": 5,
        "desert_coverage": 0.10,
        "forest_coverage": 0.18,
        "mountain_density": 0.38,
        "mountain_scale": 13.0,
        "mountain_sharpness": 0.60,
        "mountain_height": 0.38,
        "polar_ice_size": 0.48,
        "snow_threshold": 0.48,
        "ocean_current_strength": 0.10,
    },
}


COLORS = {
    "deep_ocean": np.array([4, 20, 66], dtype=np.float32),
    "ocean_mid": np.array([7, 72, 118], dtype=np.float32),
    "shallow_ocean": np.array([35, 154, 166], dtype=np.float32),
    "beach": np.array([196, 178, 119], dtype=np.float32),
    "dark_forest": np.array([9, 45, 22], dtype=np.float32),
    "forest": np.array([24, 100, 39], dtype=np.float32),
    "grass": np.array([87, 126, 47], dtype=np.float32),
    "dry_plain": np.array([133, 114, 64], dtype=np.float32),
    "desert": np.array([181, 134, 70], dtype=np.float32),
    "rock": np.array([112, 108, 98], dtype=np.float32),
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
    biome_scale: float
    biome_complexity: int
    desert_coverage: float
    forest_coverage: float
    mountain_density: float
    mountain_scale: float
    mountain_sharpness: float
    mountain_height: float
    polar_ice_size: float
    snow_threshold: float
    ocean_current_strength: float


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

    island_noise = fbm_3d(x, y, z, cfg.island_scale, 5, 0.66, cfg.seed + 1777)
    chain = 0.5 + 0.5 * np.sin(
        lon * (2.0 + cfg.island_scale * 0.06)
        + y * (12.0 + cfg.island_scale * 0.13)
        + cfg.seed * 0.017
    )
    island_field = lerp(island_noise, island_noise * 0.72 + chain * 0.28, cfg.island_chain_strength)
    island_gate = fbm_3d(x, y, z, max(2.0, cfg.island_scale * 0.18), 3, 0.54, cfg.seed + 1881)
    island_cutoff = np.clip(cfg.island_threshold - cfg.island_density * 0.22, 0.20, 0.96)
    island_land = (island_field > island_cutoff) & (island_gate > 0.42) & (~continent_land)
    land = continent_land | island_land

    shoreline_distance = np.abs(land_field - threshold)
    shoreline = 1.0 - smoothstep(0.0, max(cfg.beach_width, 0.005), shoreline_distance)
    shoreline = np.where(land, shoreline, shoreline * 0.55)
    shelf = 1.0 - smoothstep(0.0, max(cfg.shelf_width, 0.005), np.clip(threshold - land_field, 0.0, 10.0))
    shelf = np.where(~land, shelf, 0.0)
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

    map_height, map_width = x.shape
    color = np.zeros((map_height, map_width, 3), dtype=np.float32)
    ocean_variation = fbm_3d(x, y, z, 18.0, 4, 0.5, cfg.seed + 5111)
    ocean_color = color_blend(colors["deep_ocean"], colors["ocean_mid"], ocean_variation * cfg.ocean_current_strength)
    ocean_color = color_blend(ocean_color, colors["shallow_ocean"], shelf)
    color[:] = ocean_color

    land_color = color_blend(colors["grass"], colors["dry_plain"], np.clip(biome + desert_bias - 0.45, 0.0, 1.0))
    land_color = color_blend(land_color, colors["desert"], np.clip(desert_bias + biome * 0.35 - 0.28, 0.0, 1.0))
    forest_mix = np.clip(forest_bias + moisture * 0.35 - biome * 0.35, 0.0, 1.0)
    land_color = color_blend(land_color, colors["forest"], forest_mix)
    land_color = color_blend(land_color, colors["dark_forest"], np.clip(forest_mix * moisture - 0.15, 0.0, 0.65))
    land_color = color_blend(land_color, colors["rock"], mountain_mask * 0.74)
    land_color = color_blend(land_color, colors["beach"], shoreline * 0.78)

    snow_mask = smoothstep(cfg.snow_threshold, 1.0, mountain_mask * 0.72 + lat_abs * 0.38)
    ice_start = max(0.02, 1.0 - cfg.polar_ice_size)
    polar_ice = smoothstep(ice_start, min(1.0, ice_start + 0.12), lat_abs)
    ice_mask = np.maximum(snow_mask, polar_ice)
    land_color = color_blend(land_color, colors["snow"], snow_mask)
    land_color = color_blend(land_color, colors["ice"], polar_ice)
    ocean_color_with_ice = color_blend(color, colors["ice"], np.where(~land, polar_ice * 0.72, 0.0))
    color = np.where(land[..., None], land_color, ocean_color_with_ice)

    base_land_height = smoothstep(threshold - cfg.continent_contrast, threshold + cfg.continent_contrast, land_field)
    height = np.where(land, 0.38 + base_land_height * 0.20, 0.18 - ocean_depth * 0.18)
    height += np.where(land, mountain_mask * cfg.mountain_height * 0.36, 0.0)
    height += np.where(land, shoreline * 0.025, 0.0)
    raw_height = height
    height = normalize01(raw_height, height_range)

    roughness = np.where(land, 0.72, 0.24)
    roughness = roughness + mountain_mask * 0.12 - shelf * 0.07
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


def save_map_set(out_dir, maps):
    save_rgb(out_dir / "color.png", maps["color"])
    save_gray(out_dir / "height.png", maps["height"])
    save_rgb(out_dir / "normal.png", maps["normal"])
    save_gray(out_dir / "roughness.png", maps["roughness"])
    save_gray(out_dir / "land_mask.png", maps["land_mask"])
    save_gray(out_dir / "shoreline_mask.png", maps["shoreline_mask"])
    save_gray(out_dir / "ocean_depth.png", maps["ocean_depth"])


QUAD_SPHERE_MAP_NAMES = (
    "color",
    "height",
    "normal",
    "roughness",
    "land_mask",
    "shoreline_mask",
    "ocean_depth",
)

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


def save_quad_sphere_cubemap_crosses(out_dir, faces, face_size):
    for map_name in QUAD_SPHERE_MAP_NAMES:
        cross = build_cubemap_cross(faces, map_name, face_size)
        path = out_dir / f"{map_name}_cubemap_cross.png"
        if cross.shape[2] == 4:
            save_rgba(path, cross)
        else:
            save_luminance_alpha(path, cross)


def write_quad_sphere_manifest(out_dir, face_size):
    manifest = {
        "layout": "quad_sphere_cubemap_faces",
        "face_size": face_size,
        "faces": ["px", "nx", "py", "ny", "pz", "nz"],
        "maps": [
            "color.png",
            "height.png",
            "normal.png",
            "roughness.png",
            "land_mask.png",
            "shoreline_mask.png",
            "ocean_depth.png",
        ],
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
            "maps": [
                "quad_sphere/color_cubemap_cross.png",
                "quad_sphere/height_cubemap_cross.png",
                "quad_sphere/normal_cubemap_cross.png",
                "quad_sphere/roughness_cubemap_cross.png",
                "quad_sphere/land_mask_cubemap_cross.png",
                "quad_sphere/shoreline_mask_cubemap_cross.png",
                "quad_sphere/ocean_depth_cubemap_cross.png",
            ],
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


def write_html_preview(out_dir, title):
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
    <figure><img src="color.png"><figcaption>color.png</figcaption></figure>
    <figure><img src="height.png"><figcaption>height.png</figcaption></figure>
    <figure><img src="normal.png"><figcaption>normal.png</figcaption></figure>
    <figure><img src="roughness.png"><figcaption>roughness.png</figcaption></figure>
    <figure><img src="land_mask.png"><figcaption>land_mask.png</figcaption></figure>
    <figure><img src="shoreline_mask.png"><figcaption>shoreline_mask.png</figcaption></figure>
    <figure><img src="ocean_depth.png"><figcaption>ocean_depth.png</figcaption></figure>
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
