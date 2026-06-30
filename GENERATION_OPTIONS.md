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
| `--preset` | `earthlike` | Starting planet recipe. Choices include the original recipes plus V2 non-Earth families: `archipelago`, `carbon_world`, `clouded_greenhouse`, `dry_rocky`, `earthlike`, `frozen_ocean`, `icy_moon`, `iron_desert`, `marslike_desert`, `moon`, `supercontinent`, `tidally_locked_rocky`, `volcanic_moon`. |
| `--land-palette` | preset default | Land-source color palette. Choices: `alien_mineral`, `basaltic_dark`, `cold_tundra`, `dry_savanna`, `lunar_gray`, `lush_green`, `natural_earth`, `pale_sedimentary`, `red_desert`. |
| `--seed` | `42` | Random seed. Same seed and same options produce the same maps. |
| `--width` | `2048` | Equirectangular output width in pixels. Minimum `64`. |
| `--height` | `1024` | Equirectangular output height in pixels. Minimum `32`. |
| `--out` | `planet_output` | Output directory. Created if it does not exist. |
| `--quad-sphere` | off | Writes six cube/quad-sphere face folders instead of only equirectangular maps. |
| `--face-size` | `min(width, height)` | Quad-sphere face size in pixels. Minimum `32` when `--quad-sphere` is used. |
| `--quad-workers` | `PLANET_QUAD_WORKERS` or `auto` | Worker processes for quad-sphere face generation. Auto uses up to the six quad-sphere faces; use `1` for serial generation. |
| `--texture-maps` | all maps | One or more texture maps to save: `color`, `height`, `normal`, `roughness`, `land_mask`, `shoreline_mask`, `ocean_depth`, `cloud_mask`, `cloud_shadow`, `nebula_color`, `nebula_alpha`, `nebula_stars`, `city_lights`, `atmosphere_haze`, `emissive_heat`. |
| `--profile` | off | Prints `cProfile` timing for generation, saving, preview, and metadata writes. |
| `--profile-limit` | `40` | Number of timing rows to print when `--profile` is enabled. |
| `--profile-out` | unset | Optional raw `.prof` output path for external profile viewers. |

Save only the color map:

```powershell
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --width 2048 --height 1024 --out output/color_only --texture-maps color
```

Save a specific Blender-oriented set:

```powershell
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --width 2048 --height 1024 --out output/blender_maps --texture-maps color height normal roughness cloud_mask cloud_shadow
```

Generate a realistic airless moon texture:

```powershell
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset moon --seed 42 --width 2048 --height 1024 --out output/moon
```

The selected texture maps also reduce avoidable computation where possible. For example, omitting `city_lights`, `cloud_mask`, `cloud_shadow`, `normal`, or `roughness` skips those final build steps instead of only skipping the saved PNG files.

Save only Photoshop-oriented nebula compositing layers:

```powershell
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --width 2048 --height 1024 --out output/nebula_layers --texture-maps nebula_color nebula_alpha nebula_stars
```

Parallel quad-sphere generation:

```powershell
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --quad-sphere --face-size 512 --out output/color_quad_parallel --texture-maps color --quad-workers 6
```

For large faces, each worker holds its own arrays and temporary noise fields. If RAM usage is too high, set `--quad-workers 2`, `--quad-workers 3`, or `--quad-workers 1`. The browser UI uses the same setting through the `PLANET_QUAD_WORKERS` environment variable, and defaults to auto when the variable is unset.

## Profiling

Use profiling when a large texture run is slow and you want to see where time is going before optimizing.

```powershell
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --width 4096 --height 2048 --out output/profile_earthlike --profile
```

For quad-sphere output:

```powershell
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --quad-sphere --face-size 2048 --out output/profile_quad --profile
```

To save raw profile data for a viewer such as SnakeViz:

```powershell
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --width 4096 --height 2048 --out output/profile_earthlike --profile --profile-out output/profile_earthlike/generation.prof
```

## Outputs

For normal equirectangular output:

| File | Description |
| --- | --- |
| `color.png` | Main color/albedo texture. |
| `height.png` | 16-bit grayscale normalized height map. |
| `normal.png` | 16-bit RGB normal map derived from height. |
| `roughness.png` | Roughness map. Land is rougher; water is smoother. |
| `land_mask.png` | White land, black ocean. |
| `shoreline_mask.png` | Shoreline/beach influence mask. |
| `ocean_depth.png` | Ocean depth mask. |
| `cloud_mask.png` | Separate 16-bit grayscale cloud opacity mask based on softened land-form-style weather math. |
| `cloud_shadow.png` | Separate 16-bit grayscale surface-darkening mask derived from the cloud layer for Blender cloud shadows. |
| `nebula_color.png` | Separate RGB emission-color layer for nebula compositing. |
| `nebula_alpha.png` | Separate 16-bit grayscale nebula density/opacity mask for soft Photoshop compositing. |
| `nebula_stars.png` | Separate 16-bit grayscale star/speckle layer. |
| `city_lights.png` | Separate RGB emission texture for night-side artificial lights. |
| `atmosphere_haze.png` | Separate 16-bit grayscale atmosphere/haze influence map, strongest for dense-atmosphere families. |
| `emissive_heat.png` | Separate 16-bit grayscale lava/geologic heat map for volcanic worlds. |
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

It also writes cubemap-cross atlases such as `quad_sphere/color_cubemap_cross.png`. Large stitched atlases are streamed from the saved face PNGs instead of assembled as one giant in-memory array. Cloud cubemap-cross atlases include copied edge bleed in otherwise empty cells so filtered sampling does not blend face borders into transparent black. Color-only quad-sphere saves are tiled internally to reduce peak memory. Set `PLANET_QUAD_TILE_ROWS` to a smaller value such as `64` if the computer still runs out of memory. Set `PLANET_WRITE_STITCHED_CROSSES=0` before running the CLI or web UI only if you want to skip stitched atlas output.

## Presets

| Preset | Best For |
| --- | --- |
| `earthlike` | Balanced continents, oceans, forests, deserts, mountains, and ice. |
| `archipelago` | Many islands, complex shorelines, shallow-water color variation. |
| `supercontinent` | Large landmass, fewer islands, more dry interior terrain. |
| `dry_rocky` | High land coverage, strong deserts, exposed rock, minimal ice and wetland tinting. |
| `frozen_ocean` | Low land coverage, large polar ice, cold terrain, subdued land color variation. |
| `moon` | Airless all-land rocky moon with gray regolith, dark maria-like basins, dense impact craters, no oceans, no clouds, and no city lights. |
| `marslike_desert` | All-land oxidized desert world with old cratered terrain, dry basins, thin haze, and no artificial lights. |
| `icy_moon` | Airless all-land ice-rich moon with cryogenic surface tinting, worn impacts, and no clouds or lights. |
| `volcanic_moon` | Airless volcanic moon with dark basaltic terrain, young geologic relief, and a separate lava heat map. |
| `iron_desert` | Iron-rich arid all-land planet with strong red mineral staining and thin atmosphere. |
| `carbon_world` | Dark carbon/basalt all-land world with subdued minerals and minimal atmosphere. |
| `clouded_greenhouse` | Dense-atmosphere cloudy planet with muted surface colors, high haze, and no biosphere/city defaults. |
| `tidally_locked_rocky` | All-land exoplanet with day/night color asymmetry, night-side volatile ice bias, and thin atmosphere. |

## Planet Type Controls

These V2 controls bias the generator toward broader rocky-body families without replacing the detailed sliders. They are saved in `preset.json`, exposed as CLI options, and visible in the browser UI.

| Option | Earthlike default | Description |
| --- | ---: | --- |
| `--planet-family` | `wet_terrestrial` | High-level family. Choices: `wet_terrestrial`, `arid_terrestrial`, `frozen_world`, `airless_rocky`, `icy_moon`, `volcanic_world`, `iron_rich`, `carbon_world`, `clouded_greenhouse`, `tidally_locked`. |
| `--biosphere-strength` | `1.0` | Strength of vegetation, wetland, productivity, and life-friendly color cues. Use `0.0` for lifeless rocky bodies. |
| `--atmosphere-density` | `0.72` | Strength of the standalone `atmosphere_haze.png` map and dense-atmosphere visual bias. Use `0.0` for airless bodies. |
| `--surface-age` | `0.42` | Age/wear bias used by regolith and mature surface texture effects. Higher values look older and more weathered. |
| `--geologic-activity` | `0.48` | Activity bias for fresh geology, volcanic relief, and heat-map generation. |
| `--volatile-ice-strength` | `0.0` | Non-ocean volatile ice strength for icy moons, night-side ice, and frozen rocky bodies. |
| `--tidal-lock-strength` | `0.0` | Day/night asymmetry for tidally locked exoplanets. |
| `--lava-activity` | `0.0` | Lava/fissure activity. Higher values darken cooled lava in `color.png`, affect height/roughness, and write nonzero `emissive_heat.png`. |

## Land And Ocean Shape

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--land-coverage` | `0.46` | Approximate fraction of the planet covered by land. Higher values create more land. Set to `1.0` for an all-land planet with no oceans, lakes, shelves, shoreline mask, or ocean-depth mask. |
| `--continent-scale` | `1.55` | Size of major continent forms. Lower values create broader continents; higher values create smaller, busier continents. |
| `--continent-domain-warp` | `0.20` | Distorts continent sampling coordinates to make landmasses less mechanically smooth. `0.0` uses the faster unwarped continent path. |
| `--continent-macro-shape` | `0.20` | Blends broad continent-scale forms back into the land field. Higher values make large land blobs more dominant; `0.0` skips this extra macro layer. |
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
| `--polar-ice-size` | `0.16` | Overall reach of polar ice formations. Higher values allow ice farther from the poles. Set to `0.0` to completely disable polar caps, polar shelf ice, and snowcap tinting. |
| `--polar-ice-scale` | `2.15` | Scale of the broad continent-like ice sheet forms. Lower values create larger sheets; higher values create smaller fields. |
| `--polar-ice-complexity` | `0.62` | Amount of shoreline-style breakup along polar ice edges. |
| `--polar-ice-fragmentation` | `0.42` | Amount of detached island/floe formation around the outer ice edge. |
| `--polar-ice-shelf-strength` | `0.62` | Strength of ocean ice shelves and pack ice color/height contribution. |
| `--polar-ice-solidity` | `0.62` | Opacity and edge hardness for polar ice. Higher values make caps read as solid white ice sheets instead of translucent haze. |
| `--snow-threshold` | `0.74` | Threshold for mountain/high-latitude snow. Lower values create more snow. |

## Mountains And Height

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--mountain-density` | `0.52` | Amount of mountainous terrain. Higher values create more connected mountain ranges. |
| `--mountain-scale` | `16.0` | Scale of mountain ridge patterns. Higher values create smaller, more frequent ridges. |
| `--mountain-sharpness` | `0.76` | Ridge sharpness. Higher values make tighter, sharper range crests. |
| `--mountain-height` | `0.84` | Height contribution from mountains. Higher values make stronger height-map relief. |
| `--mountain-boundary-alignment` | `0.55` | Biases mountain ranges toward continent color-province borders. Higher values make ranges follow visible continental color transitions. |
| `--plate-boundary-strength` | `0.78` | Adds warped plate-margin uplift belts that constrain where mountain ranges form. Higher values make tectonic ranges more visible. |
| `--peak-prominence` | `0.70` | Strength of clustered alpine summit peaks inside broad uplift belts. Higher values make individual peaks stand out in color, height, and normal maps. |
| `--erosion-strength` | `0.42` | Carves valley-like breaks and darker exposed faces through highlands. Higher values make ranges look more eroded and less like smooth bands. |

## Meteor Impact Craters

These controls bake crater bowls, raised rims, ejecta, rays, basin sag, micro-pitting, and crater albedo into `height.png`, `normal.png`, `roughness.png`, `color.png`, and previews. They do not change land, shoreline, ocean-depth, cloud, or city-light masks. Crater centers are generated on the sphere, so the same seed produces matching equirectangular and quad-sphere crater placement.

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--crater-density` | `0.0` | Amount of visible impact craters. `0.0` disables crater generation; higher values add more crater centers. |
| `--crater-min-radius` | `0.010` | Smallest crater angular radius in radians. Lower values create finer pitting. |
| `--crater-max-radius` | `0.085` | Largest crater angular radius in radians. Higher values allow broader basins. |
| `--crater-depth` | `0.65` | Strength of crater floor depression in the height map. Higher values make bowls deeper and normal-map shading stronger. |
| `--crater-rim-height` | `0.55` | Strength of raised rims and ejecta relief. Higher values make ring edges stand out. |
| `--crater-rim-width` | `0.14` | Width of the raised crater rim band. Lower values make a thin sharp lip; higher values make broader raised rings. |
| `--crater-rim-vault` | `0.65` | Sharpness and vaulted relief of the raised rim crest. Higher values make a more pointed rim with stronger sloped shoulders. |
| `--crater-rim-color-shift` | `0.0` | Rim highlight color. Negative values cool rims toward gray-blue; positive values warm them toward ochre. |
| `--crater-rim-color-variation` | `0.22` | Per-crater rim color variation. Higher values keep nearby crater rims from sharing the same color. |
| `--crater-ancient-bombardment` | `0.0` | Adds an old impact era with large worn basins and softened medium craters. |
| `--crater-middle-bombardment` | `0.0` | Adds a mid-age impact era with partly eroded medium and small craters. |
| `--crater-fresh-bombardment` | `0.0` | Adds a young impact era with sharper small and medium craters. |
| `--crater-ancient-erosion` | `0.82` | Erosion strength for the ancient bombardment era. Higher values soften and partially bury older rims. |
| `--crater-middle-erosion` | `0.48` | Erosion strength for the middle bombardment era. |
| `--crater-fresh-erosion` | `0.14` | Erosion strength for the fresh bombardment era. Lower values preserve crisp rims and wall shadows. |
| `--crater-erosion-cycles` | `2` | Number of mask-softening passes used by era erosion. Higher values make old crater generations more worn and blended. |
| `--crater-rim-breakup` | `0.32` | Irregularity applied to crater rim outlines. Higher values make broken, scalloped, less circular rims. |
| `--crater-wall-terracing` | `0.35` | Strength of ledged and slumped wall terraces in medium and large craters. |
| `--crater-central-peak-strength` | `0.35` | Strength of central uplift peaks and rough central mounds in larger craters. |
| `--crater-shadow-strength` | `0.45` | Extra color-map cavity shadowing inside crater bowls and walls. |
| `--crater-floor-dust-fill` | `0.45` | Dust fill applied to crater floors, especially older eras. Higher values flatten and warm old floors. |
| `--crater-erosion` | `0.25` | Wear and softening applied to craters. Lower values create crisp fresh impacts; higher values make older, subdued craters. |
| `--crater-land-bias` | `0.85` | Bias toward land surfaces. `1.0` restricts crater visibility to land; `0.0` allows all surfaces equally. |
| `--crater-color-strength` | `0.45` | Amount of crater darkening/highlighting baked into `color.png`. Set to `0.0` for height-only craters. |
| `--crater-small-density` | `0.0` | Adds dense small crater pitting. The `moon` preset uses this heavily for a worn regolith surface. |
| `--crater-medium-density` | `0.0` | Adds medium craters with stronger bowls, rims, ejecta blankets, and optional rays. |
| `--crater-large-basin-density` | `0.0` | Adds sparse large impact basins with broad floor darkening and shallow height sag. |
| `--crater-ray-strength` | `0.0` | Bright radial ray strength on a subset of fresher medium impacts. |
| `--crater-floor-darkening` | `0.0` | Extra color darkening for crater floors and large basin floors. |
| `--crater-micro-pitting` | `0.0` | Fine high-frequency pitting that affects albedo, height, and roughness. |

## Moon Surface

These controls are neutral at `0.0` for non-moon presets. The `moon` preset enables them to create broad dark maria-like plains and fine gray regolith variation below the crater layer.

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--moon-basin-strength` | `0.0` | Strength of broad dark maria-like basin plains. Also subtly lowers basin height. |
| `--moon-basin-scale` | `1.0` | Size of procedural maria basin regions. Lower values make broader plains; higher values make smaller patches. |
| `--moon-regolith-variation` | `0.0` | Fine gray/tan albedo mottling plus subtle height and roughness variation. |

## Cloud Layer

These controls write 16-bit grayscale `cloud_mask.png` and `cloud_shadow.png` to reduce banding in soft cloud gradients. They do not bake clouds into `color.png`, height, normal, roughness, land, shoreline, or ocean-depth maps.

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--cloud-coverage` | `0.46` | Approximate fraction of the map covered by cloud opacity. `0.0` disables the layer. |
| `--cloud-scale` | `1.25` | Size of broad cloud systems. Lower values create larger, softer formations; higher values create smaller systems. |
| `--cloud-detail` | `5` | Number of noise octaves used in the cloud weather field. |
| `--cloud-roughness` | `0.48` | Persistence of cloud detail across octaves. Higher values add more ragged breakup. |
| `--cloud-softness` | `0.22` | Width of the soft threshold around cloud edges. Higher values make broader, hazier transitions. |
| `--cloud-land-correlation` | `0.55` | How strongly clouds echo the softened continent/land-form field. `0.0` is independent weather noise; `1.0` follows broad land forms more closely. |
| `--cloud-opacity` | `0.78` | Maximum grayscale opacity written into `cloud_mask.png`. |
| `--cloud-shadow-strength` | `0.36` | Maximum grayscale darkening influence written into `cloud_shadow.png`. Use `0.0` to disable the fake shadow map. |
| `--cloud-shadow-softness` | `0.34` | Blur applied to the shadow map. Higher values make broader, softer cloud shadows. |
| `--cloud-latitude-bias` | `0.18` | Shifts cloud preference by latitude. Negative values favor polar cloudiness; positive values favor tropical cloud belts. |
| `--cloud-band-strength` | `0.24` | Adds subtle east-west atmospheric banding so clouds read as planet-scale weather instead of only random noise. |
| `--cloud-latitude-warp` | `1.00` | Warps the cloud noise coordinates and latitude bands with seeded 3D noise. `0.0` keeps the weather field cleaner; higher values visibly bend and offset cloud systems. |
| `--cloud-hemisphere-imbalance` | `1.00` | Adds north/south cloud imbalance before mask thresholding so clouds do not mirror across the equator. `0.0` disables the imbalance. |
| `--cloud-wind-stretch` | `0.38` | Elongates cloud systems along prevailing flow. Higher values make formations more wind-sheared and less blob-like. |
| `--cloud-breakup` | `0.34` | Cuts holes and ragged gaps into cloud fields. Higher values create more broken, cellular cover. |
| `--storm-density` | `0.24` | Amount of embedded compact storm structure blended into the cloud field. |
| `--spiral-storm-strength` | `0.18` | Strength of diffuse cyclonic curvature inside storm systems. Keep moderate for realistic, non-stamped storms. |
| `--polar-cloud-strength` | `0.10` | Adds polar haze/cloud concentration independent of surface ice. |
| `--polar-cloud-asymmetry` | `1.00` | Modulates polar cloud shape and texture with seeded warp and hemispheric offset. `0.0` keeps polar haze more even. |

Blender usage:

1. Put `cloud_mask.png` on a slightly larger cloud sphere above the planet surface.
2. Load `cloud_mask.png` as `Non-Color` data and use it as the alpha/opacity factor for a white or slightly warm cloud material.
3. Load `cloud_shadow.png` as `Non-Color` data in the planet surface material, not the cloud material.
4. Use `cloud_shadow.png` as the factor for a Mix Color or Multiply step that blends `color.png` toward a darker version of itself before the Principled BSDF Base Color.
5. If the transparent cloud sphere does not cast useful shadows in Blender, keep its shadow casting disabled and use `cloud_shadow.png` for consistent surface darkening.

Practical shadow node intent:

```text
color.png -> Mix/Multiply with darker color.png
cloud_shadow.png -> ColorRamp/Map Range -> Mix Factor
mixed result -> Principled BSDF Base Color
```

## Nebula Compositing Layers

These controls write Photoshop-friendly standalone flat vista layers. They do not bake into `color.png`, height, normal, roughness, cloud, land, shoreline, ocean-depth, or city-light maps, and they are not treated as equirectangular planet textures.

| Option | Earthlike Default | Description |
| --- | ---: | --- |
| `--nebula-intensity` | `0.90` | Overall brightness and maximum opacity of the nebula density layer. `0.0` disables the colored gas layer. |
| `--nebula-coverage` | `0.54` | How much of the map is filled by gas. Lower values isolate smaller clouds; higher values make broad haze. |
| `--nebula-scale` | `1.10` | Size of the largest gas structures. Lower values create larger formations; higher values create smaller structures. |
| `--nebula-detail` | `6` | Number of fBM octaves used for the main gas field. |
| `--nebula-roughness` | `0.56` | Persistence of detail across octaves. Higher values make the gas more ragged. |
| `--nebula-warp` | `1.00` | Seeded flat-field domain warp strength for turbulent bends and organic drift. |
| `--nebula-filament-strength` | `0.62` | Strength of warped filament/tendril structures inside the broader gas. |
| `--nebula-star-density` | `0.34` | Density of the separate star/speckle layer. `0.0` disables stars. |
| `--nebula-color-mix` | `0.46` | Shifts the RGB nebula color balance between warmer dust/red emission and cooler cyan/violet emission. |
| `--nebula-color-softness` | `0.55` | Width of the blend boundaries between selected nebula colors. Lower values make sharper color regions; higher values make gradual transitions. |
| `--nebula-base-color` | `#5e44be` | Main diffuse gas/haze color. |
| `--nebula-core-color` | `#ff5e48` | Bright core/emission color used in denser gas. |
| `--nebula-accent-color` | `#44b4cd` | Secondary ionized/accent gas color. |

Photoshop usage:

1. Put `nebula_color.png` above the planet render and set the blend mode to Screen, Linear Dodge, or Color Dodge.
2. Use `nebula_alpha.png` as a layer mask on `nebula_color.png`; it is 16-bit grayscale to keep soft gradients smooth.
3. Place `nebula_stars.png` on top as Screen/Linear Dodge, or use it as a mask for a white or tinted star layer.
4. Blur or levels-adjust duplicate nebula layers for glow without changing the generated base maps.

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
| `--land-color-count` | `9` | Number of base land color roles allowed into `color.png`. Lower values remap disabled biome colors to the nearest active colors for a simpler texture. |
| `--region-tint-count` | `6` | Number of broad continent/province tint colors layered over land. Use `0` to disable those broad regional tint colors. |
| `--land-lowland-color` | `#469b26` | Direct hex color for the lowland/grass base land role. |
| `--land-vegetation-color` | `#127d22` | Direct hex color for the normal vegetation role. |
| `--land-forest-color` | `#063612` | Direct hex color for the dark forest/wet vegetation role. |
| `--land-dry-color` | `#5e4c2a` | Direct hex color for dry plains. |
| `--land-desert-color` | `#80562d` | Direct hex color for desert terrain. |
| `--land-rock-color` | `#58544c` | Direct hex color for exposed rock and mountain terrain. |
| `--land-beach-color` | `#c4b277` | Direct hex color for the beach/shoreline land band. |
| `--land-snow-color` | `#ebf2ee` | Direct hex color for snow. |
| `--land-ice-color` | `#c2e4f0` | Direct hex color for ice. |
| `--land-color-variation` | `0.22` | Overall strength of contextual land tints such as ochre soil, tundra, and pale highlands. |
| `--continent-color-variation` | `0.48` | Broad seeded color variation between continents and large parts of continents, constrained by climate, elevation, and geology. |
| `--continent-color-scale` | `2.60` | Size of continent color provinces. Lower values create broader continental identities; higher values create smaller regional patches. |
| `--continent-color-diversity` | `0.72` | How strongly neighboring continent color provinces separate from each other. |
| `--continent-color-blend-smoothness` | `0.65` | Smoothness of transitions between continent color provinces. Lower values keep sharper regional boundaries; higher values blend neighboring colors more gradually. |
| `--land-brightness` | `0.00` | Overall continent land-layer brightness offset. Negative values darken land; positive values brighten land. |
| `--land-contrast` | `1.00` | Overall continent land-layer contrast multiplier around mid gray. Values below `1.0` flatten land; values above `1.0` deepen contrast. |
| `--ocean-base-color` | `#074876` | Base hex color for the ocean layer. The generator derives deep and shallow water shades from this color before applying shelf, depth, latitude, productivity, brightness, contrast, and final hue controls. |
| `--ocean-flat-color-strength` | `0.00` | Final blend strength toward `--ocean-base-color` for every ocean color pixel. `0.0` keeps procedural ocean modeling; `1.0` forces a single flat ocean color after shelf, depth, current, tint, and ocean-ice color effects. |
| `--ocean-shelf-color` | `#44cdbc` | Hex color for the separate final shelf overlay. Use with `--ocean-shelf-color-strength` to keep a visible shelf band while flattening the open ocean. |
| `--ocean-shelf-color-strength` | `0.00` | Final shelf overlay strength. `0.0` disables the separate overlay; `1.0` paints the shelf band with `--ocean-shelf-color` using the `--shelf-width` mask. |
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
| `--ocean-hue-shift` | `0.00` | Final hue rotation for rendered ocean pixels. `-0.50` and `0.50` represent a half color-wheel turn. |
| `--ocean-saturation` | `1.00` | Final ocean saturation multiplier. `0.0` removes ocean color; values above `1.0` intensify it. |
| `--ocean-colorizer-hue` | `0.55` | Target hue used by the ocean colorizer. `0.0` is red, about `0.33` green, about `0.55` cyan-blue, and about `0.66` blue. |
| `--ocean-colorizer-strength` | `0.00` | Blend strength toward the colorizer hue after normal ocean tinting. |
| `--mineral-tint-strength` | `0.26` | Rust/mineral tint on dry mountainous terrain. |
| `--wetland-tint-strength` | `0.16` | Darker wet lowland tint in moist regions. |
| `--iron-oxide-tint-strength` | `0.12` | Red-brown oxidized staining on dry exposed terrain. |
| `--basalt-tint-strength` | `0.08` | Dark volcanic rock tint on rugged mineral-rich terrain. |
| `--salt-flat-tint-strength` | `0.05` | Pale evaporite/salt tint in dry lowland basins. |
| `--clay-tint-strength` | `0.10` | Warm clay/sediment tint in low wet or formerly wet basins. |

Advanced tint color overrides are also available for the contextual land tint layers: `--land-ochre-tint-color`, `--land-rust-tint-color`, `--land-wet-tint-color`, `--land-tundra-tint-color`, `--land-highland-tint-color`, `--land-iron-oxide-tint-color`, `--land-basalt-tint-color`, `--land-salt-flat-tint-color`, `--land-clay-tint-color`, and `--land-solid-ice-tint-color`.

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

# Direct custom land colors with fewer color layers
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --land-color-count 4 --region-tint-count 2 --land-lowland-color "#4bbf4f" --land-desert-color "#b15d32" --land-rock-color "#242424" --land-beach-color "#ead18a" --out output/custom_palette_simple

# Lush island world with stronger shallow-water, productivity, and wetland color
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset archipelago --seed 88 --land-color-variation 0.30 --ocean-shallow-tint-strength 0.72 --ocean-productivity-strength 0.58 --ocean-sediment-strength 0.46 --wetland-tint-strength 0.28 --out output/lush_archipelago

# Ocean-focused Earthlike world with visible depth and current variation
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --land-coverage 0.18 --ocean-depth-tint-strength 0.62 --ocean-latitude-tint-strength 0.54 --ocean-productivity-strength 0.42 --ocean-sediment-strength 0.14 --out output/ocean_earthlike

# Darker navy ocean base shade
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --ocean-base-color "#03294f" --out output/navy_ocean

# Single flat ocean color, no visible ocean color modeling
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --ocean-base-color "#e8f0ee" --ocean-flat-color-strength 1 --out output/flat_ocean

# Flat open ocean with an independently colored shelf band
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --ocean-base-color "#17242d" --ocean-flat-color-strength 1 --shelf-width 0.16 --ocean-shelf-color "#65d6c8" --ocean-shelf-color-strength 1 --out output/flat_ocean_colored_shelf

# All land, no ocean, lakes, shelves, or water masks
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset dry_rocky --seed 42 --land-coverage 1 --out output/no_water_rocky

# All land with no water and no polar ice caps
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset dry_rocky --seed 42 --land-coverage 1 --polar-ice-size 0 --out output/no_water_no_ice

# Dimmer shelf cyan without darkening the whole ocean layer
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --ocean-shelf-brightness -0.12 --ocean-shelf-contrast 0.85 --out output/shelf_cyan_balanced

# Brighter high-contrast ocean layer without changing land
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --ocean-brightness 0.12 --ocean-contrast 1.35 --out output/ocean_bright_contrast

# Greener stylized ocean using final hue/saturation/colorizer controls
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --seed 42 --ocean-hue-shift -0.08 --ocean-saturation 1.35 --ocean-colorizer-hue 0.42 --ocean-colorizer-strength 0.35 --out output/ocean_green_colorized

# Disable the new contextual color variation while keeping the base palette randomization
.\.venv\Scripts\python.exe rocky_planet_gen.py --preset earthlike --land-color-variation 0 --ocean-color-variation 0 --ocean-shallow-tint-strength 0 --ocean-depth-tint-strength 0 --ocean-latitude-tint-strength 0 --ocean-productivity-strength 0 --ocean-sediment-strength 0 --mineral-tint-strength 0 --wetland-tint-strength 0 --out output/plain_color
```

## Preset Defaults

The table below lists the original ocean/rocky presets. The `moon` preset is intentionally airless (`land_coverage=1.0`, no clouds, no city lights, no polar ice) and uses the crater and moon-surface defaults documented above.

| Option | earthlike | archipelago | supercontinent | dry_rocky | frozen_ocean |
| --- | ---: | ---: | ---: | ---: | ---: |
| `land_coverage` | `0.46` | `0.32` | `0.58` | `0.68` | `0.28` |
| `continent_scale` | `1.55` | `2.75` | `0.95` | `1.35` | `1.85` |
| `continent_domain_warp` | `0.20` | `0.20` | `0.20` | `0.20` | `0.20` |
| `continent_macro_shape` | `0.20` | `0.20` | `0.20` | `0.20` | `0.20` |
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
| `mountain_density` | `0.52` | `0.44` | `0.64` | `0.70` | `0.48` |
| `mountain_scale` | `16.0` | `20.0` | `11.0` | `18.0` | `13.0` |
| `mountain_sharpness` | `0.76` | `0.64` | `0.86` | `0.92` | `0.70` |
| `mountain_height` | `0.84` | `0.58` | `0.98` | `1.05` | `0.56` |
| `mountain_boundary_alignment` | `0.55` | `0.45` | `0.68` | `0.60` | `0.50` |
| `plate_boundary_strength` | `0.78` | `0.66` | `0.90` | `0.92` | `0.58` |
| `peak_prominence` | `0.70` | `0.58` | `0.84` | `0.86` | `0.48` |
| `erosion_strength` | `0.42` | `0.50` | `0.36` | `0.28` | `0.58` |
| `crater_density` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` |
| `crater_min_radius` | `0.010` | `0.008` | `0.010` | `0.008` | `0.010` |
| `crater_max_radius` | `0.085` | `0.060` | `0.095` | `0.095` | `0.070` |
| `crater_depth` | `0.65` | `0.48` | `0.68` | `0.78` | `0.52` |
| `crater_rim_height` | `0.55` | `0.40` | `0.58` | `0.68` | `0.44` |
| `crater_rim_width` | `0.14` | `0.12` | `0.16` | `0.13` | `0.12` |
| `crater_rim_vault` | `0.65` | `0.65` | `0.65` | `0.65` | `0.65` |
| `crater_rim_color_shift` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` |
| `crater_rim_color_variation` | `0.22` | `0.22` | `0.22` | `0.22` | `0.22` |
| `crater_ancient_bombardment` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` |
| `crater_middle_bombardment` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` |
| `crater_fresh_bombardment` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` |
| `crater_ancient_erosion` | `0.82` | `0.82` | `0.82` | `0.82` | `0.82` |
| `crater_middle_erosion` | `0.48` | `0.48` | `0.48` | `0.48` | `0.48` |
| `crater_fresh_erosion` | `0.14` | `0.14` | `0.14` | `0.14` | `0.14` |
| `crater_erosion_cycles` | `2` | `2` | `2` | `2` | `2` |
| `crater_rim_breakup` | `0.32` | `0.32` | `0.32` | `0.32` | `0.32` |
| `crater_wall_terracing` | `0.35` | `0.35` | `0.35` | `0.35` | `0.35` |
| `crater_central_peak_strength` | `0.35` | `0.35` | `0.35` | `0.35` | `0.35` |
| `crater_shadow_strength` | `0.45` | `0.45` | `0.45` | `0.45` | `0.45` |
| `crater_floor_dust_fill` | `0.45` | `0.45` | `0.45` | `0.45` | `0.45` |
| `crater_erosion` | `0.25` | `0.38` | `0.22` | `0.18` | `0.36` |
| `crater_land_bias` | `0.85` | `0.88` | `0.92` | `0.96` | `0.82` |
| `crater_color_strength` | `0.45` | `0.32` | `0.50` | `0.66` | `0.32` |
| `cloud_coverage` | `0.46` | `0.54` | `0.34` | `0.18` | `0.56` |
| `cloud_scale` | `1.25` | `1.75` | `0.95` | `1.15` | `1.10` |
| `cloud_detail` | `5` | `5` | `4` | `4` | `5` |
| `cloud_roughness` | `0.48` | `0.50` | `0.44` | `0.46` | `0.46` |
| `cloud_softness` | `0.22` | `0.24` | `0.20` | `0.16` | `0.28` |
| `cloud_land_correlation` | `0.55` | `0.48` | `0.66` | `0.42` | `0.60` |
| `cloud_opacity` | `0.78` | `0.82` | `0.72` | `0.62` | `0.82` |
| `cloud_shadow_strength` | `0.36` | `0.40` | `0.30` | `0.22` | `0.34` |
| `cloud_shadow_softness` | `0.34` | `0.30` | `0.38` | `0.44` | `0.52` |
| `cloud_latitude_bias` | `0.18` | `0.26` | `0.08` | `-0.10` | `-0.32` |
| `cloud_band_strength` | `0.24` | `0.30` | `0.18` | `0.12` | `0.16` |
| `cloud_latitude_warp` | `1.00` | `1.00` | `1.00` | `1.00` | `1.00` |
| `cloud_hemisphere_imbalance` | `1.00` | `1.00` | `1.00` | `1.00` | `1.00` |
| `cloud_wind_stretch` | `0.38` | `0.44` | `0.28` | `0.22` | `0.30` |
| `cloud_breakup` | `0.34` | `0.28` | `0.42` | `0.58` | `0.20` |
| `storm_density` | `0.24` | `0.34` | `0.16` | `0.08` | `0.18` |
| `spiral_storm_strength` | `0.18` | `0.20` | `0.10` | `0.04` | `0.08` |
| `polar_cloud_strength` | `0.10` | `0.06` | `0.08` | `0.02` | `0.62` |
| `polar_cloud_asymmetry` | `1.00` | `1.00` | `1.00` | `1.00` | `1.00` |
| `nebula_intensity` | `0.90` | `0.90` | `0.90` | `0.90` | `0.90` |
| `nebula_coverage` | `0.54` | `0.54` | `0.54` | `0.54` | `0.54` |
| `nebula_scale` | `1.10` | `1.10` | `1.10` | `1.10` | `1.10` |
| `nebula_detail` | `6` | `6` | `6` | `6` | `6` |
| `nebula_roughness` | `0.56` | `0.56` | `0.56` | `0.56` | `0.56` |
| `nebula_warp` | `1.00` | `1.00` | `1.00` | `1.00` | `1.00` |
| `nebula_filament_strength` | `0.62` | `0.62` | `0.62` | `0.62` | `0.62` |
| `nebula_star_density` | `0.34` | `0.34` | `0.34` | `0.34` | `0.34` |
| `nebula_color_mix` | `0.46` | `0.46` | `0.46` | `0.46` | `0.46` |
| `nebula_color_softness` | `0.55` | `0.55` | `0.55` | `0.55` | `0.55` |
| `nebula_base_color` | `#5e44be` | `#5e44be` | `#5e44be` | `#5e44be` | `#5e44be` |
| `nebula_core_color` | `#ff5e48` | `#ff5e48` | `#ff5e48` | `#ff5e48` | `#ff5e48` |
| `nebula_accent_color` | `#44b4cd` | `#44b4cd` | `#44b4cd` | `#44b4cd` | `#44b4cd` |
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
| `ocean_base_color` | `#074876` | `#0b6d92` | `#063f70` | `#05315e` | `#294f72` |
| `ocean_flat_color_strength` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` |
| `ocean_shelf_color` | `#44cdbc` | `#44cdbc` | `#44cdbc` | `#44cdbc` | `#44cdbc` |
| `ocean_shelf_color_strength` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` |
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
| `ocean_hue_shift` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` |
| `ocean_saturation` | `1.0` | `1.0` | `1.0` | `1.0` | `1.0` |
| `ocean_colorizer_hue` | `0.55` | `0.55` | `0.55` | `0.55` | `0.55` |
| `ocean_colorizer_strength` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` |
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
- Use `--mountain-density`, `--mountain-scale`, `--mountain-height`, `--plate-boundary-strength`, `--peak-prominence`, `--erosion-strength`, and `--mountain-boundary-alignment` for connected ranges, relief, clustered alpine summits, eroded valleys, ruggedness, and alignment with continent color transitions.
- Use the color variation options when the shape is good but the texture feels too uniform.
- The resolved settings for each run are saved in `preset.json`, which is the easiest way to reproduce or compare outputs.
