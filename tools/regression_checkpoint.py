from __future__ import annotations

import argparse
import json
import py_compile
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "rocky_planet_gen.py"
UI_APP = REPO_ROOT / "planet_texture_ui.py"
PERMUTATION = REPO_ROOT / "permutation.py"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output" / "regression_checkpoint"
EXPECTED_MAPS = {
    "color",
    "height",
    "normal",
    "roughness",
    "land_ocean_mask",
    "shoreline_mask",
    "beach_mask",
    "surf_foam_mask",
    "shallow_shelf_mask",
    "ocean_depth",
    "cloud_mask",
    "cloud_shadow",
    "nebula_color",
    "nebula_alpha",
    "nebula_stars",
    "city_lights",
    "atmosphere_haze",
    "emissive_heat",
}
QUAD_FACES = ("px", "nx", "py", "ny", "pz", "nz")


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


class CheckFailure(Exception):
    pass


class Harness:
    def __init__(self, python_exe: str, output_root: Path, keep_output: bool = False):
        self.python_exe = python_exe
        self.output_root = output_root.resolve()
        self.keep_output = keep_output
        self.results: list[CheckResult] = []

    def record(self, name: str, fn):
        started = time.perf_counter()
        try:
            detail = fn() or ""
        except Exception as exc:
            elapsed = time.perf_counter() - started
            self.results.append(CheckResult(name, False, f"{exc} ({elapsed:.2f}s)"))
            print(f"FAIL {name}: {exc}")
            return False
        elapsed = time.perf_counter() - started
        suffix = f" - {detail}" if detail else ""
        self.results.append(CheckResult(name, True, f"{detail} ({elapsed:.2f}s)"))
        print(f"PASS {name}{suffix}")
        return True

    def require(self, condition: bool, message: str):
        if not condition:
            raise CheckFailure(message)

    def prepare_output_root(self):
        expected_parent = (REPO_ROOT / "output").resolve()
        self.require(
            self.output_root.parent == expected_parent and self.output_root.name == "regression_checkpoint",
            f"refusing to clean unexpected output root: {self.output_root}",
        )
        if self.output_root.exists() and not self.keep_output:
            shutil.rmtree(self.output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)

    def run_generator(self, args: list[str], timeout: int = 180):
        cmd = [self.python_exe, str(GENERATOR), *args]
        completed = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        if completed.returncode != 0:
            raise CheckFailure(
                "generator command failed:\n"
                + " ".join(cmd)
                + "\n"
                + completed.stdout[-4000:]
            )
        return completed.stdout

    def check_py_compile(self):
        for path in (GENERATOR, UI_APP, PERMUTATION):
            py_compile.compile(str(path), doraise=True)
        return "generator, UI, helper compile"

    def check_cli_help(self):
        completed = subprocess.run(
            [self.python_exe, str(GENERATOR), "--help"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
        )
        self.require(completed.returncode == 0, completed.stdout[-4000:])
        help_text = completed.stdout
        required_flags = [
            "--texture-maps",
            "--quad-sphere",
            "--quad-faces",
            "--planet-name",
            "--profile",
            "--lava-activity",
            "--crater-density",
            "--ocean-ripple-strength",
        ]
        missing = [flag for flag in required_flags if flag not in help_text]
        self.require(not missing, f"missing CLI flags: {', '.join(missing)}")
        return f"{len(required_flags)} expected flags present"

    def check_module_contracts(self):
        sys.path.insert(0, str(REPO_ROOT))
        import rocky_planet_gen as gen
        import planet_texture_ui as ui

        self.require(set(gen.TEXTURE_MAP_NAMES) == EXPECTED_MAPS, "generator TEXTURE_MAP_NAMES drifted")
        self.require(set(ui.TEXTURE_MAP_NAMES) == EXPECTED_MAPS, "UI TEXTURE_MAP_NAMES drifted")
        self.require(gen.TEXTURE_MAP_ALIASES.get("land_mask") == "land_ocean_mask", "land_mask alias missing")
        self.require(gen.selected_texture_maps(["land_mask"]) == ("land_ocean_mask",), "land_mask alias selection failed")
        defaults = ui.default_payload()
        default_maps = {item["key"] for item in defaults["texture_maps"]}
        self.require(default_maps == EXPECTED_MAPS, "/api/defaults texture map list drifted")
        param_keys = {
            param["key"]
            for group in defaults["param_groups"]
            for param in group["params"]
        }
        required_params = {
            "planet_family",
            "geologic_activity",
            "lava_activity",
            "mountain_density",
            "crater_density",
            "ocean_ripple_strength",
            "basalt_tint_strength",
        }
        missing = sorted(required_params - param_keys)
        self.require(not missing, f"/api/defaults missing params: {', '.join(missing)}")
        return f"{len(EXPECTED_MAPS)} maps and {len(required_params)} params verified"

    def check_equirect_selected_maps(self):
        out_dir = self.output_root / "eq_selected"
        self.run_generator(
            [
                "--preset",
                "earthlike",
                "--seed",
                "1234",
                "--width",
                "128",
                "--height",
                "64",
                "--texture-maps",
                "color",
                "height",
                "land_mask",
                "--out",
                str(out_dir),
            ]
        )
        expected = {"color.png", "height.png", "land_ocean_mask.png", "preview.png"}
        pngs = {path.name for path in out_dir.glob("*.png")}
        self.require(expected <= pngs, f"missing equirect PNGs: {sorted(expected - pngs)}")
        forbidden = {"normal.png", "roughness.png", "shoreline_mask.png", "ocean_depth.png"}
        self.require(not (pngs & forbidden), f"unexpected selected-map PNGs: {sorted(pngs & forbidden)}")
        self.assert_image(out_dir / "color.png", "RGB", (128, 64))
        self.assert_image(out_dir / "height.png", "I;16", (128, 64), allow_i16_alias=True)
        metadata = self.read_json(out_dir / "preset.json")
        self.require(metadata["preset"] == "earthlike", "preset metadata mismatch")
        self.require(metadata["seed"] == 1234, "seed metadata mismatch")
        self.require(metadata["output_projection"] == "equirectangular", "projection metadata mismatch")
        self.require(metadata["output_texture_maps"] == ["color", "height", "land_ocean_mask"], "selected maps metadata mismatch")
        self.require(metadata.get("peak_memory"), "peak_memory missing from preset.json")
        return "alias, selective output, metadata, image modes"

    def check_named_equirect_filenames(self):
        out_dir = self.output_root / "eq_named"
        planet_name = "Test Planet: Alpha/01"
        asset_name = "Test_Planet__Alpha_01"
        self.run_generator(
            [
                "--preset",
                "volcanic_moon",
                "--seed",
                "2222",
                "--width",
                "128",
                "--height",
                "64",
                "--planet-name",
                planet_name,
                "--texture-maps",
                "color",
                "emissive_heat",
                "--out",
                str(out_dir),
            ]
        )
        expected = {
            f"{asset_name}_color_equirect_128x64_8bit.png",
            f"{asset_name}_emissive_heat_equirect_128x64_16bit.png",
            "preview.png",
        }
        actual = {path.name for path in out_dir.glob("*.png")}
        self.require(expected <= actual, f"missing named PNGs: {sorted(expected - actual)}")
        self.require("color.png" not in actual, "legacy color.png should not be written for named exports")
        metadata = self.read_json(out_dir / "preset.json")
        self.require(metadata["planet_name"] == asset_name, "sanitized planet_name metadata mismatch")
        self.require(metadata["output_texture_maps"] == ["color", "emissive_heat"], "named selected maps metadata mismatch")
        return "sanitized named equirect filenames"

    def check_quad_sphere_contract(self):
        out_dir = self.output_root / "quad_named"
        planet_name = "Quad Smoke"
        asset_name = "Quad_Smoke"
        face_size = 32
        self.run_generator(
            [
                "--preset",
                "moon",
                "--seed",
                "3333",
                "--quad-sphere",
                "--face-size",
                str(face_size),
                "--quad-workers",
                "1",
                "--planet-name",
                planet_name,
                "--texture-maps",
                "color",
                "height",
                "--out",
                str(out_dir),
            ],
            timeout=240,
        )
        quad_dir = out_dir / "quad_sphere"
        self.require(quad_dir.exists(), "quad_sphere folder missing")
        for map_name, bit_depth in (("color", "8bit"), ("height", "16bit")):
            map_dir = quad_dir / f"{map_name}_faces"
            self.require(map_dir.is_dir(), f"{map_dir.name} folder missing")
            for face in QUAD_FACES:
                file_name = f"{asset_name}_{map_name}_cubemap_{face}_{face_size}x{face_size}_{bit_depth}.png"
                self.require((map_dir / file_name).exists(), f"missing face file {map_dir.name}/{file_name}")
        manifest = self.read_json(out_dir / "quad_sphere_manifest.json")
        self.require(manifest["layout"] == "quad_sphere_cubemap_faces", "manifest layout mismatch")
        self.require(manifest["planet_name"] == asset_name, "manifest planet_name mismatch")
        self.require(manifest["face_size"] == face_size, "manifest face_size mismatch")
        self.require(manifest["faces"] == list(QUAD_FACES), "manifest faces mismatch")
        self.require(manifest["map_roles"] == ["color", "height"], "manifest map_roles mismatch")
        self.require(manifest["cubemap_cross"]["written"] is True, "stitched cubemap crosses should be written")
        metadata = self.read_json(out_dir / "preset.json")
        self.require(metadata["output_projection"] == "quad_sphere", "quad metadata projection mismatch")
        self.require(metadata["quad_sphere_face_size"] == face_size, "quad face size metadata mismatch")
        self.require(metadata["output_quad_faces"] == list(QUAD_FACES), "quad output faces metadata mismatch")
        self.require(metadata["output_texture_maps"] == ["color", "height"], "quad selected maps metadata mismatch")
        self.require(metadata.get("peak_memory"), "quad peak_memory missing")
        return "faces, manifest, stitched crosses, metadata"

    def check_ui_save_contract(self):
        sys.path.insert(0, str(REPO_ROOT))
        import planet_texture_ui as ui

        previous_output_root = ui.OUTPUT_ROOT
        ui.OUTPUT_ROOT = self.output_root / "ui_output"
        try:
            payload = {
                "preset": "dry_rocky",
                "seed": 4444,
                "width": 128,
                "height": 64,
                "planet_name": "UI Smoke",
                "texture_maps": ["color", "roughness"],
                "projection": "equirectangular",
                "ui_state": {
                    "texture_maps": ["color", "roughness"],
                    "projection": "equirectangular",
                },
            }
            out_dir, report = ui.save_planet_output(payload)
        finally:
            ui.OUTPUT_ROOT = previous_output_root
        self.require(out_dir.exists(), "UI save output folder missing")
        self.require((out_dir / "generation_report.json").exists(), "generation_report.json missing")
        self.require(report["projection"] == "equirectangular", "UI report projection mismatch")
        self.require(report["texture_maps"] == ["color", "roughness"], "UI report selected maps mismatch")
        self.require(report.get("peak_memory"), "UI report peak_memory missing")
        self.require(report.get("equivalent_cli", {}).get("command"), "UI equivalent CLI missing")
        metadata = self.read_json(out_dir / "preset.json")
        self.require(metadata["output_texture_maps"] == ["color", "roughness"], "UI preset selected maps mismatch")
        self.require(metadata["output_kind"] == "texture_output", "UI output_kind mismatch")
        self.require("ui_state" in metadata, "UI state missing from preset.json")
        summary = ui.output_summary(out_dir, report)
        self.require("generation_report" in summary, "UI output summary missing report")
        return "generation_report, equivalent CLI, ui_state"

    def check_docs_map_names(self):
        generator_maps = EXPECTED_MAPS
        docs = [
            REPO_ROOT / "GENERATION_OPTIONS.md",
            REPO_ROOT / "ETSY_TEXTURE_MAP_INSTRUCTIONS.md",
        ]
        missing = []
        for doc in docs:
            text = doc.read_text(encoding="utf-8")
            for map_name in generator_maps:
                if map_name not in text:
                    missing.append(f"{doc.name}:{map_name}")
        self.require(not missing, "docs missing map names: " + ", ".join(missing[:20]))
        return "generator map names appear in user docs"

    def assert_image(self, path: Path, expected_mode: str, expected_size: tuple[int, int], allow_i16_alias: bool = False):
        self.require(path.exists(), f"{path.name} missing")
        with Image.open(path) as image:
            self.require(image.size == expected_size, f"{path.name} size {image.size} != {expected_size}")
            valid_modes = {expected_mode}
            if allow_i16_alias:
                valid_modes.update({"I", "I;16", "I;16B", "I;16L"})
            self.require(image.mode in valid_modes, f"{path.name} mode {image.mode} not in {sorted(valid_modes)}")

    def read_json(self, path: Path):
        self.require(path.exists(), f"{path.name} missing")
        return json.loads(path.read_text(encoding="utf-8"))

    def print_summary(self):
        failures = [result for result in self.results if not result.ok]
        print()
        print(f"Regression checkpoint: {len(self.results) - len(failures)} passed, {len(failures)} failed")
        print(f"Output root: {self.output_root}")
        if failures:
            print()
            for failure in failures:
                print(f"FAILED {failure.name}: {failure.detail}")
            raise SystemExit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run a comprehensive smoke/regression checkpoint for the rocky planet app."
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to run generator subprocesses. Defaults to the current interpreter.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Harness-owned output folder. Default: output/regression_checkpoint.",
    )
    parser.add_argument(
        "--keep-output",
        action="store_true",
        help="Keep existing output/regression_checkpoint contents instead of recreating the folder.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    harness = Harness(args.python, args.output_root, keep_output=args.keep_output)
    harness.record("prepare_output_root", harness.prepare_output_root)
    harness.record("py_compile", harness.check_py_compile)
    harness.record("cli_help", harness.check_cli_help)
    harness.record("module_contracts", harness.check_module_contracts)
    harness.record("equirect_selected_maps", harness.check_equirect_selected_maps)
    harness.record("named_equirect_filenames", harness.check_named_equirect_filenames)
    harness.record("quad_sphere_contract", harness.check_quad_sphere_contract)
    harness.record("ui_save_contract", harness.check_ui_save_contract)
    harness.record("docs_map_names", harness.check_docs_map_names)
    harness.print_summary()


if __name__ == "__main__":
    main()
