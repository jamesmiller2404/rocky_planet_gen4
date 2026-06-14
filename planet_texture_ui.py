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
    PRESETS,
    PlanetConfig,
    TEXTURE_MAP_NAMES,
    build_maps,
    build_quad_sphere_maps,
    render_globe_preview,
    selected_texture_maps,
    save_map_set,
    save_quad_sphere_cubemap_crosses,
    vary_palette,
    write_html_preview,
    write_quad_sphere_manifest,
)


HOST = "127.0.0.1"
PORT = int(os.environ.get("PLANET_TEXTURE_UI_PORT", "8765"))
OUTPUT_ROOT = Path("output")


PARAM_GROUPS = [
    {
        "name": "Land And Ocean Shape",
        "params": [
            ("land_coverage", 0.05, 0.90, 0.01),
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
        ],
    },
    {
        "name": "Color Variation",
        "params": [
            ("ocean_current_strength", 0.00, 0.60, 0.01),
            ("land_color_variation", 0.00, 0.70, 0.01),
            ("ocean_color_variation", 0.00, 0.70, 0.01),
            ("ocean_shallow_tint_strength", 0.00, 1.00, 0.01),
            ("ocean_depth_tint_strength", 0.00, 1.00, 0.01),
            ("ocean_latitude_tint_strength", 0.00, 1.00, 0.01),
            ("ocean_productivity_strength", 0.00, 0.70, 0.01),
            ("ocean_sediment_strength", 0.00, 0.70, 0.01),
            ("mineral_tint_strength", 0.00, 0.80, 0.01),
            ("wetland_tint_strength", 0.00, 0.60, 0.01),
            ("iron_oxide_tint_strength", 0.00, 0.80, 0.01),
            ("basalt_tint_strength", 0.00, 0.80, 0.01),
            ("salt_flat_tint_strength", 0.00, 0.80, 0.01),
            ("clay_tint_strength", 0.00, 0.80, 0.01),
        ],
    },
]

INT_PARAMS = {
    key
    for group in PARAM_GROUPS
    for key, _minimum, _maximum, step in group["params"]
    if isinstance(step, int)
}

UI_DEFAULT_OVERRIDES = {
    key: 0.0
    for group in PARAM_GROUPS
    for key, _minimum, _maximum, _step in group["params"]
    if key.startswith("island_")
}
UI_DEFAULT_OVERRIDES["shelf_width"] = 0.08


def ui_preset_defaults() -> dict:
    return {
        name: {**values, **UI_DEFAULT_OVERRIDES}
        for name, values in PRESETS.items()
    }


def image_data_url(arr: np.ndarray) -> str:
    image = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


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
) -> dict:
    metadata = asdict(cfg)
    metadata["output_projection"] = projection
    metadata["output_texture_maps"] = list(texture_maps or TEXTURE_MAP_NAMES)
    if face_size is not None:
        metadata["quad_sphere_face_size"] = face_size
    metadata["resolved_palette_rgb"] = {
        name: [int(round(channel)) for channel in color]
        for name, color in vary_palette(cfg.seed, cfg.preset).items()
    }
    return metadata


def save_planet_output(payload: dict) -> Path:
    cfg = config_from_payload(payload, preview=False)
    projection = str(payload.get("projection", "equirectangular"))
    texture_maps = texture_maps_from_payload(payload)
    output_name = sanitized_name(
        str(payload.get("output_name", "")),
        f"{cfg.preset}_{cfg.seed}_{time.strftime('%Y%m%d_%H%M%S')}",
    )
    out_dir = unique_output_dir(output_name)
    out_dir.mkdir(parents=True, exist_ok=False)

    if projection == "quad_sphere":
        face_size = int(payload.get("face_size") or min(cfg.width, cfg.height))
        if face_size < 32:
            raise ValueError("Quad-sphere face size must be at least 32.")
        quad_dir = out_dir / "quad_sphere"
        quad_dir.mkdir(parents=True, exist_ok=True)
        quad_faces = build_quad_sphere_maps(cfg, face_size)
        for face, maps in quad_faces.items():
            face_dir = quad_dir / face
            face_dir.mkdir(parents=True, exist_ok=True)
            save_map_set(face_dir, maps, texture_maps)
        save_quad_sphere_cubemap_crosses(quad_dir, quad_faces, face_size, texture_maps)
        write_quad_sphere_manifest(out_dir, face_size, texture_maps)
        metadata = metadata_for_config(cfg, "quad_sphere", face_size, texture_maps)
    else:
        maps = build_maps(cfg)
        save_map_set(out_dir, maps, texture_maps)
        render_globe_preview(maps["color"], maps["height"], out_dir / "preview.png")
        if "color" in texture_maps:
            write_html_preview(out_dir, f"{cfg.preset} planet preview", texture_maps)
        metadata = metadata_for_config(cfg, "equirectangular", texture_maps=texture_maps)

    (out_dir / "preset.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return out_dir


def output_summary(out_dir: Path) -> dict:
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
    return {
        "output_dir": str(out_dir.resolve()),
        "quad_sphere_faces": face_dirs,
        "stitched_quad_sphere_maps": stitched,
        "generated_maps": generated_maps,
    }


def load_preset_json(path_text: str) -> dict:
    path = Path(path_text)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists() or path.name != "preset.json":
        raise ValueError("Choose an existing preset.json file.")

    data = json.loads(path.read_text(encoding="utf-8"))
    preset = str(data.get("preset", "earthlike"))
    if preset not in PRESETS:
        preset = "earthlike"
    params = {key: data[key] for key in PRESETS[preset] if key in data}
    return {
        "preset": preset,
        "seed": int(data.get("seed", 42)),
        "width": int(data.get("width", 2048)),
        "height": int(data.get("height", 1024)),
        "projection": data.get("output_projection", "equirectangular"),
        "face_size": int(data.get("quad_sphere_face_size", min(int(data.get("width", 2048)), int(data.get("height", 1024))))),
        "params": params,
    }


def default_payload() -> dict:
    return {
        "presets": sorted(PRESETS),
        "defaults": ui_preset_defaults(),
        "param_groups": [
            {
                "name": group["name"],
                "params": [
                    {
                        "key": key,
                        "label": key.replace("_", " ").title(),
                        "min": minimum,
                        "max": maximum,
                        "step": step,
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
    }


class PlanetUiHandler(BaseHTTPRequestHandler):
    server_version = "PlanetTextureUI/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.write_text(UI_HTML, "text/html")
        elif parsed.path == "/api/defaults":
            self.write_json(default_payload())
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
                        "color": image_data_url(maps["color"]),
                        "summary": {
                            "preset": cfg.preset,
                            "seed": cfg.seed,
                            "preview_size": f"{cfg.width}x{cfg.height}",
                        },
                    }
                )
            elif parsed.path == "/api/save":
                out_dir = save_planet_output(payload)
                self.write_json(output_summary(out_dir))
            elif parsed.path == "/api/load":
                self.write_json(load_preset_json(str(payload.get("path", ""))))
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
.globe-figure {
  display: grid;
  grid-template-rows: auto minmax(260px, 1fr) auto;
}
.globe-toolbar {
  display: grid;
  grid-template-columns: 74px auto minmax(110px, 1fr) 48px;
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
@media (max-width: 900px) {
  main { grid-template-columns: 1fr; }
  aside { max-height: none; border-right: 0; border-bottom: 1px solid var(--line); }
  .image-grid { grid-template-columns: 1fr; }
  .map-options { grid-template-columns: 1fr; }
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
    <div id="paramGroups"></div>
    <details open>
      <summary>Save Output</summary>
      <div class="row">
        <label for="projection">Projection</label>
        <select id="projection">
          <option value="equirectangular">Equirectangular</option>
          <option value="quad_sphere">Quad-sphere faces + stitched crosses</option>
        </select>
      </div>
      <p class="hint" id="projectionHint">Quad-sphere saves six face folders and stitched *_cubemap_cross.png atlases, matching the CLI --quad-sphere output.</p>
      <label>Texture maps</label>
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
        <button id="saveBtn" class="primary">Save Texture Output</button>
      </div>
      <div class="load-row">
        <input id="loadPath" type="text" placeholder="output/example/preset.json">
        <button id="loadBtn">Load</button>
      </div>
    </details>
  </aside>
  <section class="preview">
    <div class="status" id="status">Loading controls...</div>
    <div class="image-grid">
      <figure>
        <img id="colorPreview" alt="Color texture preview">
        <figcaption>color texture preview</figcaption>
      </figure>
      <figure class="globe-figure">
        <div class="globe-toolbar">
          <button id="globePlayPause" type="button">Pause</button>
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
<script>
let schema = null;
let debounceTimer = null;
let inFlight = false;

const els = {
  preset: document.getElementById("preset"),
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
  globeCanvas: document.getElementById("globeCanvas"),
  globePlayPause: document.getElementById("globePlayPause"),
  globeSpeed: document.getElementById("globeSpeed"),
  globeSpeedValue: document.getElementById("globeSpeedValue"),
  paramGroups: document.getElementById("paramGroups"),
  textureMapOptions: document.getElementById("textureMapOptions"),
  loadPath: document.getElementById("loadPath"),
};

const globe = {
  ctx: els.globeCanvas.getContext("2d", {willReadFrequently: true}),
  textureCanvas: document.createElement("canvas"),
  textureData: null,
  textureWidth: 0,
  textureHeight: 0,
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

function sliderId(key) {
  return `param_${key}`;
}

function valueId(key) {
  return `value_${key}`;
}

function getDefaults() {
  return schema.defaults[els.preset.value];
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

  els.paramGroups.innerHTML = "";
  for (const group of schema.param_groups) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = group.name;
    details.appendChild(summary);

    for (const param of group.params) {
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
    els.paramGroups.appendChild(details);
  }
  applyPresetDefaults();
}

function renderTextureMapOptions() {
  els.textureMapOptions.innerHTML = "";
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
  }
}

function syncValue(key) {
  const slider = document.getElementById(sliderId(key));
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
  els.outputName.value = "";
  schedulePreview(0);
}

function getParams() {
  const params = {};
  for (const group of schema.param_groups) {
    for (const param of group.params) {
      const slider = document.getElementById(sliderId(param.key));
      params[param.key] = param.integer ? parseInt(slider.value, 10) : parseFloat(slider.value);
    }
  }
  return params;
}

function getSelectedTextureMaps() {
  return Array.from(els.textureMapOptions.querySelectorAll("input[data-texture-map='1']:checked"))
    .map(input => input.value);
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

function setGlobeTexture(src) {
  const image = new Image();
  image.onload = () => {
    globe.textureWidth = image.naturalWidth;
    globe.textureHeight = image.naturalHeight;
    globe.textureCanvas.width = globe.textureWidth;
    globe.textureCanvas.height = globe.textureHeight;
    globe.textureCtx.clearRect(0, 0, globe.textureWidth, globe.textureHeight);
    globe.textureCtx.drawImage(image, 0, 0);
    globe.textureData = globe.textureCtx.getImageData(0, 0, globe.textureWidth, globe.textureHeight).data;
    drawGlobe();
  };
  image.src = src;
}

function syncGlobeSpeed() {
  globe.speed = parseFloat(els.globeSpeed.value);
  els.globeSpeedValue.textContent = `${globe.speed.toFixed(2).replace(/0$/, "").replace(/\.$/, "")}x`;
}

function setGlobePlaying(playing) {
  globe.playing = playing;
  els.globePlayPause.textContent = playing ? "Pause" : "Play";
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

      const shade = 0.18 + Math.max(0, sx * light[0] + sy * light[1] + sz * light[2]) * 0.95;
      const rim = Math.max(0, Math.min(1, (1 - sz) * 1.4));
      const atmosphere = [72, 122, 176];
      const edgeAlpha = 1 - Math.max(0, Math.min(1, (r2 - 0.88) / 0.12));
      const blend = rim * 0.18;
      data[i] = Math.min(255, ((globe.textureData[ti] * (1 - blend)) + atmosphere[0] * blend) * shade);
      data[i + 1] = Math.min(255, ((globe.textureData[ti + 1] * (1 - blend)) + atmosphere[1] * blend) * shade);
      data[i + 2] = Math.min(255, ((globe.textureData[ti + 2] * (1 - blend)) + atmosphere[2] * blend) * shade);
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
    els.colorPreview.src = data.color;
    setGlobeTexture(data.color);
    setStatus(`Preview ready: ${data.summary.preset}, seed ${data.summary.seed}, ${data.summary.preview_size}`, "ok");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    inFlight = false;
    setButtons(false);
  }
}

function setButtons(disabled) {
  for (const id of ["previewBtn", "saveBtn", "resetBtn", "randomSeedBtn", "loadBtn"]) {
    document.getElementById(id).disabled = disabled;
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
    els.preset.value = data.preset;
    els.seed.value = data.seed;
    els.width.value = data.width;
    els.height.value = data.height;
    els.projection.value = data.projection === "quad_sphere" ? "quad_sphere" : "equirectangular";
    els.faceSize.value = data.face_size;
    syncResolutionPreset();
    syncFaceSizePreset();
    for (const [key, value] of Object.entries(data.params)) {
      const slider = document.getElementById(sliderId(key));
      if (slider) {
        slider.value = value;
        syncValue(key);
      }
    }
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

  els.preset.addEventListener("change", applyPresetDefaults);
  els.seed.addEventListener("change", () => schedulePreview(0));
  els.previewWidth.addEventListener("change", () => schedulePreview(0));
  els.resolutionPreset.addEventListener("change", applyResolutionPreset);
  els.width.addEventListener("change", syncResolutionPreset);
  els.height.addEventListener("change", syncResolutionPreset);
  els.faceSizePreset.addEventListener("change", applyFaceSizePreset);
  els.faceSize.addEventListener("change", syncFaceSizePreset);
  document.getElementById("previewBtn").addEventListener("click", () => schedulePreview(0));
  document.getElementById("saveBtn").addEventListener("click", saveOutput);
  document.getElementById("resetBtn").addEventListener("click", applyPresetDefaults);
  document.getElementById("randomSeedBtn").addEventListener("click", () => {
    els.seed.value = Math.floor(Math.random() * 1000000);
    schedulePreview(0);
  });
  document.getElementById("loadBtn").addEventListener("click", loadPresetJson);
}

boot().catch(error => setStatus(error.message, "error"));
</script>
</body>
</html>
"""


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), PlanetUiHandler)
    print(f"Rocky Planet Texture UI running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop the server.")
    server.serve_forever()


if __name__ == "__main__":
    main()
