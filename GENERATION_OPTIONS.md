# Rocky Planet Generator Options

This file documents the command-line options for `rocky_planet_gen.py`.

Basic usage:

```powershell
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --width 2048 --height 1024 --out output/earthlike
```

The generator writes baked texture maps and preview files. All preset options can be overridden from the command line by using the option name with hyphens instead of underscores.

Example:

```powershell
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset dry_rocky --land-coverage 0.72 --mineral-tint-strength 0.50 --out output/dry_custom
```

## Core Options

| Option | Default | Description |
| --- | ---: | --- |
| `--preset` | `earthlike` | Starting planet recipe. Choices: `archipelago`, `dry_rocky`, `earthlike`, `frozen_ocean`, `supercontinent`. |
| `--land-palette` | preset default | Land-source color palette. Choices: `alien_mineral`, `basaltic_dark`, `cold_tundra`, `dry_savanna`, `lush_green`, `natural_earth`, `pale_sedimentary`, `red_desert`. |
| `--seed` | `42` | Random seed. Same seed and same options produce the same maps. |
| `--width` | `2048` | Equirectangular output width in pixels. Minimum `64`. |
| `--height` | `1024` | Equirectangular output height in pixels. Minimum `32`. |
| `--out` | `planet_output` | Output directory. Created if it does not exist. |
| `--quad-sphere` | off | Writes six cube/quad-sphere face folders instead of only equirectangular maps. |
| `--face-size` | `min(width, height)` | Quad-sphere face size in pixels. Minimum `32` when `--quad-sphere` is used. |

## Outputs

For normal equirectangular output:

| File | Description |
| --- | --- |
| `color.png` | Main color/albedo texture. |
| `height.png` | Normalized height map. |
| `normal.png` | Normal map derived from height. |
| `roughness.png` | Roughness map. Land is rougher; water is smoother. |
| `land_mask.png` | White land, black ocean. |
| `shoreline_mask.png` | Shoreline/beach influence mask. |
| `ocean_depth.png` | Ocean depth mask. |
| `cloud_mask.png` | Separate grayscale cloud opacity mask based on softened land-form-style weather math. |
| `city_lights.png` | Separate RGB emission texture for night-side artificial lights. |
| `preview.png` | Rendered globe preview. |
| `preview.html` | Interactive rotating globe preview using `color.png`. |
| `preset.json` | Resolved config, output projection, and seed-varied palette. |

For quad-sphere output, the generator writes face folders under `quad_sphere/`:

```text
quad_sphere/px
quad_sphere/nx
quad_sphere/py
quad_sphere/ny
quad_sphere/pz
quad_sphere/nz
```

It also writes cubemap-cross atlases such as `quad_sphere/color_cubemap_cross.png`.

## Presets

| Preset | Best For |
| --- | --- |
| `earthlike` | Balanced continents, oceans, forests, deserts, mountains, and ice. |
| `archipelago` | Many islands, complex shorelines, shallow-water color variation. |
| `supercontinent` | Large landmass, fewer islands, more dry interior terrain. |
| `dry_rocky` | High land coverage, strong deserts, exposed rock, minimal ice and wetland tinting. |
| `frozen_ocean` | Low land coverage, large polar ice, cold terrain, subdued land color variation. |

## Land And Ocean Shape

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--land-coverage` | `0.46` | Approximate fraction of the planet covered by land. Higher values create more land. |
| `--continent-scale` | `1.55` | Size of major continent forms. Lower values create broader continents; higher values create smaller, busier continents. |
| `--continent-detail` | `7` | Number of noise octaves used for continent shape. Higher values add finer detail. |
| `--continent-roughness` | `0.58` | How strongly continent detail persists across octaves. Higher values make more rugged coastlines. |
| `--continent-contrast` | `0.19` | Height transition range around land. Higher values broaden elevation variation. |
| `--island-density` | `0.38` | Amount of island land outside the main continents. |
| `--island-scale` | `34.0` | Island pattern scale. Higher values create smaller, more frequent island features. |
| `--island-threshold` | `0.73` | Noise cutoff for detached island candidates. Lower values create more candidates before distance and size filtering. |
| `--island-chain-strength` | `0.35` | Strength of chain-like island alignment. |
| `--island-min-continent-distance` | `0.012` | Minimum normalized map distance from continent land. Higher values keep islands farther from mainland coastlines. |
| `--island-max-continent-distance` | `0.0` | Optional maximum normalized map distance from continent land. `0.0` disables the limit; positive values form coastal island belts. |
| `--island-min-area` | `0.00001` | Minimum island component area as a fraction of the map. Smaller detached specks are discarded. |
| `--island-max-area` | `0.006` | Maximum island component area as a fraction of the map. Larger detached masses are suppressed instead of becoming continents. |

## Shorelines And Shelves

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--shoreline-complexity` | `0.62` | How much extra noise distorts coastlines. |
| `--shoreline-noise-scale` | `18.0` | Scale of shoreline detail. Higher values create smaller coastal features. |
| `--shoreline-detail` | `5` | Number of noise octaves used for coast detail. |
| `--shoreline-erosion` | `0.18` | Pulls back land around shorelines. Higher values can reduce land and roughen coast shape. |
| `--beach-width` | `0.045` | Width of the beach/shoreline color band on land. |
| `--shelf-width` | `0.14` | Width of shallow ocean shelves around land. Affects shallow-water color and ocean depth. |

## Biomes And Climate

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--biome-scale` | `8.0` | Scale of biome patches. Higher values create smaller, more frequent climate regions. |
| `--biome-complexity` | `6` | Noise octaves for biome variation. |
| `--desert-coverage` | `0.27` | Desert/dry terrain bias. Higher values increase tan and ochre regions. |
| `--forest-coverage` | `0.56` | Forest/wet terrain bias. Higher values increase green and dark wet regions. |
| `--polar-ice-size` | `0.16` | Overall reach of polar ice formations. Higher values allow ice farther from the poles. |
| `--polar-ice-scale` | `2.15` | Scale of the broad continent-like ice sheet forms. Lower values create larger sheets; higher values create smaller fields. |
| `--polar-ice-complexity` | `0.62` | Amount of shoreline-style breakup along polar ice edges. |
| `--polar-ice-fragmentation` | `0.42` | Amount of detached island/floe formation around the outer ice edge. |
| `--polar-ice-shelf-strength` | `0.62` | Strength of ocean ice shelves and pack ice color/height contribution. |
| `--polar-ice-solidity` | `0.62` | Opacity and edge hardness for polar ice. Higher values make caps read as solid white ice sheets instead of translucent haze. |
| `--snow-threshold` | `0.74` | Threshold for mountain/high-latitude snow. Lower values create more snow. |

## Mountains And Height

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--mountain-density` | `0.42` | Amount of mountainous terrain. Higher values create more mountains. |
| `--mountain-scale` | `16.0` | Scale of mountain ridge patterns. Higher values create smaller, more frequent ridges. |
| `--mountain-sharpness` | `0.68` | Ridge sharpness. Higher values make tighter, sharper mountain features. |
| `--mountain-height` | `0.62` | Height contribution from mountains. Higher values make stronger height-map relief. |

## Cloud Layer

These controls write `cloud_mask.png` only. They do not bake clouds into `color.png`, height, normal, roughness, land, shoreline, or ocean-depth maps.

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--cloud-coverage` | `0.46` | Approximate fraction of the map covered by cloud opacity. `0.0` disables the layer. |
| `--cloud-scale` | `1.25` | Size of broad cloud systems. Lower values create larger, softer formations; higher values create smaller systems. |
| `--cloud-detail` | `5` | Number of noise octaves used in the cloud weather field. |
| `--cloud-roughness` | `0.48` | Persistence of cloud detail across octaves. Higher values add more ragged breakup. |
| `--cloud-softness` | `0.22` | Width of the soft threshold around cloud edges. Higher values make broader, hazier transitions. |
| `--cloud-land-correlation` | `0.55` | How strongly clouds echo the softened continent/land-form field. `0.0` is independent weather noise; `1.0` follows broad land forms more closely. |
| `--cloud-opacity` | `0.78` | Maximum grayscale opacity written into `cloud_mask.png`. |

## City Lights

These controls write `city_lights.png` only. They do not bake artificial lights into `color.png`; use the map as a separate emission texture in Blender. The map is built from many individual point lights; city and road patterns control where dots appear rather than painting broad glowing patches.

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--city-lights-strength` | `0.72` | Overall brightness of the generated emission map. `0.0` disables city lights. |
| `--city-density` | `0.46` | Amount of developed settlement detail, from sparse lights to denser town fields. |
| `--megacity-count` | `14` | Number of major urban anchors used to seed bright city clusters. |
| `--coastal-city-bias` | `0.74` | Preference for cities near coastlines and shore-adjacent lowlands. |
| `--inland-city-bias` | `0.38` | Preference for inland lowland settlement away from immediate coastlines. |
| `--city-sprawl` | `0.42` | Width of urban halos around bright cores. Higher values create larger metropolitan areas. |
| `--road-network-strength` | `0.46` | Strength of thin developed corridors and road-like light networks between regions. |
| `--light-temperature` | `0.58` | Emission color from warm amber at `0.0` through pale neutral to cooler white-blue near `1.0`. |

Blender usage:

1. Use `color.png` for the planet material base color, and keep `city_lights.png` separate.
2. Add `city_lights.png` to an Image Texture node and feed it into an Emission shader.
3. Multiply the emission strength by a night-side mask, usually based on the surface normal facing away from the sun/light direction.
4. Add or mix that Emission shader with the planet's normal Principled BSDF surface.
5. Keep clouds above the surface so `cloud_mask.png` can partially obscure city emission when desired.

Practical node intent:

```text
city_lights.png * night_side_mask * emission_strength -> Emission Strength
```

Use `city_lights.png` as an emission/light map, not as base color. For realistic renders, start with emission strength around `2` to `6`; use higher values only for stylized orbital shots.

## Color Variation

These controls affect `color.png` only. They do not change land shape, height, normal, masks, cloud mask, or roughness.

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--ocean-current-strength` | `0.18` | Existing broad ocean color variation between deep and mid ocean colors. |
| `--land-palette` | `natural_earth` | Source color set for land biomes, continent color provinces, and contextual geologic tints. |
| `--land-color-variation` | `0.22` | Overall strength of contextual land tints such as ochre soil, tundra, and pale highlands. |
| `--continent-color-variation` | `0.48` | Broad seeded color variation between continents and large parts of continents, constrained by climate, elevation, and geology. |
| `--continent-color-scale` | `2.60` | Size of continent color provinces. Lower values create broader continental identities; higher values create smaller regional patches. |
| `--continent-color-diversity` | `0.72` | How strongly neighboring continent color provinces separate from each other. |
| `--continent-color-blend-smoothness` | `0.65` | Smoothness of transitions between continent color provinces. Lower values keep sharper regional boundaries; higher values blend neighboring colors more gradually. |
| `--land-brightness` | `0.00` | Overall continent land-layer brightness offset. Negative values darken land; positive values brighten land. |
| `--land-contrast` | `1.00` | Overall continent land-layer contrast multiplier around mid gray. Values below `1.0` flatten land; values above `1.0` deepen contrast. |
| `--ocean-color-variation` | `0.18` | Legacy overall ocean tint multiplier. It still contributes to shallow, depth, and latitude tinting. |
| `--ocean-shallow-tint-strength` | `0.38` | Warm cyan/teal shallow-water tint on shelves, strongest in lower latitudes. |
| `--ocean-shelf-brightness` | `0.00` | Brightness offset applied to rendered shallow-shelf water, separate from whole-ocean brightness. |
| `--ocean-shelf-contrast` | `1.00` | Contrast multiplier applied to rendered shallow-shelf water, separate from whole-ocean contrast. |
| `--ocean-depth-tint-strength` | `0.34` | Darker blue tint for deeper open ocean basins. |
| `--ocean-latitude-tint-strength` | `0.30` | Cold blue-gray tint for deeper polar and high-latitude water. |
| `--ocean-productivity-strength` | `0.28` | Teal/green biological-productivity tint tied to shelves, broad upwelling, and latitude. |
| `--ocean-sediment-strength` | `0.22` | Muted tan-green sediment tint near coastlines and shallow shelves. |
| `--ocean-brightness` | `0.00` | Overall ocean-layer brightness offset. Negative values darken water; positive values brighten water. |
| `--ocean-contrast` | `1.00` | Overall ocean-layer contrast multiplier around mid gray. Values below `1.0` flatten water; values above `1.0` deepen contrast. |
| `--mineral-tint-strength` | `0.26` | Rust/mineral tint on dry mountainous terrain. |
| `--wetland-tint-strength` | `0.16` | Darker wet lowland tint in moist regions. |
| `--iron-oxide-tint-strength` | `0.12` | Red-brown oxidized staining on dry exposed terrain. |
| `--basalt-tint-strength` | `0.08` | Dark volcanic rock tint on rugged mineral-rich terrain. |
| `--salt-flat-tint-strength` | `0.05` | Pale evaporite/salt tint in dry lowland basins. |
| `--clay-tint-strength` | `0.10` | Warm clay/sediment tint in low wet or formerly wet basins. |

Useful color variation ranges:

| Value | Effect |
| ---: | --- |
| `0.00` | Disable that variation. |
| `0.10` | Subtle for land tints; light but visible for the stronger ocean layers. |
| `0.25` | Normal for ocean variation. |
| `0.40` | Strong and clearly visible. |
| `0.60` or higher | Stylized; may overpower the base palette. |

Examples:

```powershell
# Strong rusty dry world
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset dry_rocky --seed 77 --land-color-variation 0.45 --mineral-tint-strength 0.55 --wetland-tint-strength 0.02 --out output/dry_rusty

# Brighter high-contrast continents without changing oceans
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --land-brightness 0.10 --land-contrast 1.30 --out output/land_bright_contrast

# Lush island world with stronger shallow-water, productivity, and wetland color
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset archipelago --seed 88 --land-color-variation 0.30 --ocean-shallow-tint-strength 0.72 --ocean-productivity-strength 0.58 --ocean-sediment-strength 0.46 --wetland-tint-strength 0.28 --out output/lush_archipelago

# Ocean-focused Earthlike world with visible depth and current variation
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --land-coverage 0.18 --ocean-depth-tint-strength 0.62 --ocean-latitude-tint-strength 0.54 --ocean-productivity-strength 0.42 --ocean-sediment-strength 0.14 --out output/ocean_earthlike

# Dimmer shelf cyan without darkening the whole ocean layer
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --ocean-shelf-brightness -0.12 --ocean-shelf-contrast 0.85 --out output/shelf_cyan_balanced

# Brighter high-contrast ocean layer without changing land
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --ocean-brightness 0.12 --ocean-contrast 1.35 --out output/ocean_bright_contrast

# Disable the new contextual color variation while keeping the base palette randomization
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --land-color-variation 0 --ocean-color-variation 0 --ocean-shallow-tint-strength 0 --ocean-depth-tint-strength 0 --ocean-latitude-tint-strength 0 --ocean-productivity-strength 0 --ocean-sediment-strength 0 --mineral-tint-strength 0 --wetland-tint-strength 0 --out output/plain_color
```

## Preset Defaults

| Option | earthlike | archipelago | supercontinent | dry_rocky | frozen_ocean |
| --- | ---: | ---: | ---: | ---: | ---: |
| `land_coverage` | `0.46` | `0.32` | `0.58` | `0.68` | `0.28` |
| `continent_scale` | `1.55` | `2.75` | `0.95` | `1.35` | `1.85` |
| `continent_detail` | `7` | `8` | `7` | `8` | `6` |
| `continent_roughness` | `0.58` | `0.66` | `0.52` | `0.64` | `0.50` |
| `continent_contrast` | `0.19` | `0.15` | `0.23` | `0.20` | `0.18` |
| `shoreline_complexity` | `0.62` | `0.86` | `0.48` | `0.55` | `0.40` |
| `shoreline_noise_scale` | `18.0` | `28.0` | `13.0` | `21.0` | `12.0` |
| `shoreline_detail` | `5` | `6` | `5` | `6` | `4` |
| `shoreline_erosion` | `0.18` | `0.34` | `0.12` | `0.22` | `0.10` |
| `beach_width` | `0.045` | `0.06` | `0.035` | `0.025` | `0.02` |
| `shelf_width` | `0.14` | `0.18` | `0.11` | `0.08` | `0.10` |
| `island_density` | `0.38` | `0.82` | `0.16` | `0.12` | `0.18` |
| `island_scale` | `34.0` | `48.0` | `26.0` | `30.0` | `22.0` |
| `island_threshold` | `0.73` | `0.64` | `0.80` | `0.82` | `0.78` |
| `island_chain_strength` | `0.35` | `0.74` | `0.22` | `0.28` | `0.24` |
| `island_min_continent_distance` | `0.012` | `0.008` | `0.018` | `0.018` | `0.014` |
| `island_max_continent_distance` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` |
| `island_min_area` | `0.00001` | `0.000005` | `0.00002` | `0.00002` | `0.00002` |
| `island_max_area` | `0.006` | `0.004` | `0.010` | `0.008` | `0.007` |
| `biome_scale` | `8.0` | `12.0` | `6.5` | `10.0` | `7.0` |
| `biome_complexity` | `6` | `7` | `6` | `7` | `5` |
| `desert_coverage` | `0.27` | `0.18` | `0.46` | `0.72` | `0.10` |
| `forest_coverage` | `0.56` | `0.66` | `0.36` | `0.12` | `0.18` |
| `mountain_density` | `0.42` | `0.34` | `0.55` | `0.62` | `0.38` |
| `mountain_scale` | `16.0` | `20.0` | `11.0` | `18.0` | `13.0` |
| `mountain_sharpness` | `0.68` | `0.55` | `0.78` | `0.86` | `0.60` |
| `mountain_height` | `0.62` | `0.42` | `0.78` | `0.86` | `0.38` |
| `cloud_coverage` | `0.46` | `0.54` | `0.34` | `0.18` | `0.56` |
| `cloud_scale` | `1.25` | `1.75` | `0.95` | `1.15` | `1.10` |
| `cloud_detail` | `5` | `5` | `4` | `4` | `5` |
| `cloud_roughness` | `0.48` | `0.50` | `0.44` | `0.46` | `0.46` |
| `cloud_softness` | `0.22` | `0.24` | `0.20` | `0.16` | `0.28` |
| `cloud_land_correlation` | `0.55` | `0.48` | `0.66` | `0.42` | `0.60` |
| `cloud_opacity` | `0.78` | `0.82` | `0.72` | `0.62` | `0.82` |
| `city_lights_strength` | `0.72` | `0.66` | `0.70` | `0.34` | `0.30` |
| `city_density` | `0.46` | `0.42` | `0.40` | `0.18` | `0.16` |
| `megacity_count` | `14` | `10` | `12` | `5` | `4` |
| `coastal_city_bias` | `0.74` | `0.88` | `0.36` | `0.24` | `0.46` |
| `inland_city_bias` | `0.38` | `0.24` | `0.72` | `0.38` | `0.12` |
| `city_sprawl` | `0.42` | `0.36` | `0.48` | `0.26` | `0.20` |
| `road_network_strength` | `0.46` | `0.38` | `0.52` | `0.18` | `0.14` |
| `light_temperature` | `0.58` | `0.60` | `0.55` | `0.62` | `0.50` |
| `polar_ice_size` | `0.16` | `0.08` | `0.20` | `0.04` | `0.48` |
| `polar_ice_scale` | `2.15` | `2.80` | `1.65` | `2.40` | `1.30` |
| `polar_ice_complexity` | `0.62` | `0.76` | `0.48` | `0.56` | `0.58` |
| `polar_ice_fragmentation` | `0.42` | `0.68` | `0.30` | `0.36` | `0.48` |
| `polar_ice_shelf_strength` | `0.62` | `0.52` | `0.70` | `0.34` | `0.88` |
| `polar_ice_solidity` | `0.62` | `0.56` | `0.74` | `0.44` | `0.82` |
| `snow_threshold` | `0.74` | `0.82` | `0.70` | `0.88` | `0.48` |
| `ocean_current_strength` | `0.18` | `0.24` | `0.12` | `0.08` | `0.10` |
| `land_palette` | `natural_earth` | `lush_green` | `dry_savanna` | `red_desert` | `cold_tundra` |
| `land_color_variation` | `0.22` | `0.26` | `0.24` | `0.34` | `0.16` |
| `continent_color_variation` | `0.48` | `0.44` | `0.52` | `0.58` | `0.34` |
| `continent_color_scale` | `2.6` | `4.2` | `2.0` | `2.7` | `2.1` |
| `continent_color_diversity` | `0.72` | `0.70` | `0.80` | `0.85` | `0.60` |
| `continent_color_blend_smoothness` | `0.65` | `0.70` | `0.55` | `0.42` | `0.75` |
| `land_brightness` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` |
| `land_contrast` | `1.0` | `1.0` | `1.0` | `1.0` | `1.0` |
| `ocean_color_variation` | `0.18` | `0.24` | `0.14` | `0.08` | `0.16` |
| `ocean_shallow_tint_strength` | `0.38` | `0.56` | `0.24` | `0.16` | `0.18` |
| `ocean_shelf_brightness` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` |
| `ocean_shelf_contrast` | `1.0` | `1.0` | `1.0` | `1.0` | `1.0` |
| `ocean_depth_tint_strength` | `0.34` | `0.26` | `0.32` | `0.20` | `0.42` |
| `ocean_latitude_tint_strength` | `0.30` | `0.18` | `0.28` | `0.16` | `0.62` |
| `ocean_productivity_strength` | `0.28` | `0.42` | `0.18` | `0.08` | `0.10` |
| `ocean_sediment_strength` | `0.22` | `0.34` | `0.30` | `0.12` | `0.06` |
| `ocean_brightness` | `0.0` | `0.04` | `-0.03` | `-0.02` | `0.06` |
| `ocean_contrast` | `1.0` | `1.08` | `1.10` | `1.06` | `0.88` |
| `mineral_tint_strength` | `0.26` | `0.18` | `0.28` | `0.38` | `0.14` |
| `wetland_tint_strength` | `0.16` | `0.20` | `0.12` | `0.06` | `0.08` |
| `iron_oxide_tint_strength` | `0.12` | `0.08` | `0.18` | `0.30` | `0.05` |
| `basalt_tint_strength` | `0.08` | `0.10` | `0.12` | `0.18` | `0.08` |
| `salt_flat_tint_strength` | `0.05` | `0.03` | `0.08` | `0.14` | `0.03` |
| `clay_tint_strength` | `0.10` | `0.12` | `0.16` | `0.12` | `0.06` |

## Tuning Notes

- Start with a preset, then change only one or two options at a time.
- Use `--seed` to explore different layouts without changing the planet recipe.
- Use `--land-coverage` and `--continent-scale` for main continent layout. Use `--island-density`, `--island-threshold`, continent-distance limits, and island area limits for detached island systems.
- Use `--biome-scale`, `--desert-coverage`, and `--forest-coverage` for climate and surface character.
- Use `--mountain-density`, `--mountain-scale`, and `--mountain-height` for relief and ruggedness.
- Use the color variation options when the shape is good but the texture feels too uniform.
- The resolved settings for each run are saved in `preset.json`, which is the easiest way to reproduce or compare outputs.
