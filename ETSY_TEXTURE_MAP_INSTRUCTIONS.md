# Rocky Planet Texture Map Pack - Customer Guide

Thank you for purchasing this rocky planet texture map pack. These maps are designed for 3D artists using Blender, Unreal Engine, Unity, and other tools that support image textures, UV-mapped spheres, cube maps, or cube-sphere planet meshes.

This guide assumes beginner to intermediate experience with materials. The short version is:

- Use the equirectangular maps on a normal UV sphere.
- Use the cube/quad-sphere maps on a cube-sphere mesh, a six-face cube map workflow, or a tool that can import cubemap faces.
- Use color maps as color textures.
- Use height, normal, roughness, and mask maps as data textures, not color-corrected images.

## What Is Included

The package includes the same planet texture set in multiple projection formats and resolutions.

### Equirectangular Maps

Equirectangular maps are the standard 2:1 planet textures used on UV spheres.

Included sizes:

| Resolution | Best Use |
| --- | --- |
| 2048 x 1024 px | Fast previews, games, background planets, distant shots |
| 4096 x 2048 px | Higher quality renders, closer camera views, larger planets |

These maps wrap left-to-right around a sphere. The top edge is the north pole and the bottom edge is the south pole.

### Cube/Quad-Sphere Face Maps

Cube/quad-sphere maps are six square textures, one for each side of a cube-sphere planet.

Included face sizes:

| Face Size | Total Face Set |
| --- | --- |
| 512 x 512 px per face | Lightweight game or preview use |
| 1024 x 1024 px per face | General-purpose game and render use |
| 2048 x 2048 px per face | Higher quality close-up work |

The six face folders/files use these names:

| Face Name | Direction |
| --- | --- |
| `px` | Positive X, right side |
| `nx` | Negative X, left side |
| `py` | Positive Y, top |
| `ny` | Negative Y, bottom |
| `pz` | Positive Z, front |
| `nz` | Negative Z, back |

Use these when you want less stretching near the poles than a normal equirectangular sphere texture.

### Stitched T-Shape Cubemap Atlases

The package also includes stitched cubemap atlases, sometimes called cubemap crosses or T-shape cubemaps.

Included atlas sizes:

| Atlas Resolution | Face Size |
| --- | --- |
| 1536 x 2048 px | 512 x 512 px faces |
| 3072 x 4096 px | 1024 x 1024 px faces |
| 6144 x 8192 px | 2048 x 2048 px faces |

These files contain all six cube faces in one image. They are useful for tools that can import a cubemap-cross image, for conversion utilities, or for artists who prefer to keep the six faces in one file.

Do not apply a stitched T-shape cubemap directly to a normal UV sphere as if it were an equirectangular map. It will not line up correctly unless your shader or tool specifically understands cubemap layout.

## Texture Map Types

Depending on the exact product variation, the following maps may be included.

| File | What It Contains | Typical Use | Color/Data Setting |
| --- | --- | --- | --- |
| `color.png` | Main visible planet surface color | Base Color / Albedo | sRGB / Color |
| `height.png` | Grayscale elevation | Bump, displacement, parallax | Non-Color / Linear |
| `normal.png` | RGB normal map derived from terrain | Surface detail normals | Non-Color / Normal Map |
| `roughness.png` | Grayscale material roughness | Controls shine/gloss | Non-Color / Linear |
| `land_mask.png` | White land, black ocean | Land/ocean material blending | Non-Color / Linear |
| `shoreline_mask.png` | Shoreline and beach influence | Beach tint, wet sand, foam, coastal detail | Non-Color / Linear |
| `ocean_depth.png` | Grayscale ocean depth | Water color, transparency, shallow/deep blending | Non-Color / Linear |
| `cloud_mask.png` | 16-bit grayscale cloud opacity | Separate cloud sphere alpha/opacity | Non-Color / Linear |
| `cloud_shadow.png` | 16-bit grayscale fake cloud shadow mask | Darken surface below clouds | Non-Color / Linear |
| `city_lights.png` | RGB night-side artificial lights | Emission/light map | sRGB / Color |
| `nebula_color.png` | RGB nebula color layer | Background/compositing emission color | sRGB / Color |
| `nebula_alpha.png` | 16-bit grayscale nebula opacity | Nebula transparency/density | Non-Color / Linear |
| `nebula_stars.png` | 16-bit grayscale star/speckle layer | Background star compositing | Non-Color / Linear |
| `atmosphere_haze.png` | 16-bit grayscale haze influence | Atmosphere rim/haze blending | Non-Color / Linear |
| `emissive_heat.png` | 16-bit grayscale lava/geologic heat | Lava or volcanic emission | Non-Color / Linear |

If your software has a color-space option, the rule is simple:

- Photographic/color-looking maps use sRGB or Color.
- Masks, height, roughness, normal, and grayscale control maps use Non-Color, Linear, Masks, or Data.

## Using Equirectangular Maps

Use the equirectangular maps when you want the easiest setup. They work on a normal UV sphere in almost every 3D package.

### Blender Equirectangular Setup

1. Add a UV Sphere.
2. Shade it smooth.
3. Create a new material.
4. Add `color.png` with an Image Texture node.
5. Set `color.png` to `sRGB`.
6. Connect `color.png` to the Principled BSDF `Base Color`.
7. Add `roughness.png`.
8. Set `roughness.png` to `Non-Color`.
9. Connect `roughness.png` to the Principled BSDF `Roughness`.
10. Add `normal.png`.
11. Set `normal.png` to `Non-Color`.
12. Connect `normal.png` to a `Normal Map` node, then connect that node to the Principled BSDF `Normal`.
13. Add `height.png`.
14. Set `height.png` to `Non-Color`.
15. For simple surface relief, connect it to a `Bump` node, then connect the Bump node to the material normal.

Good starting values in Blender:

| Setting | Starting Value |
| --- | --- |
| Normal Map Strength | 0.5 to 1.0 |
| Bump Strength | 0.03 to 0.10 |
| Bump Distance | 0.02 to 0.08 |
| Roughness Strength | Use the map directly first |

For true displacement in Blender, use Cycles, add enough mesh subdivision, set the material displacement mode to support displacement, and connect `height.png` through a Displacement node. Keep displacement strength low at first.

### Blender Clouds

Clouds are not baked into `color.png`. This gives you more control.

1. Duplicate the planet sphere.
2. Scale the duplicate slightly larger, for example `1.005` to `1.02`.
3. Give the duplicate a cloud material.
4. Load `cloud_mask.png` as `Non-Color`.
5. Use `cloud_mask.png` as the Alpha or transparency mask.
6. Set the cloud material color to white, light gray, or a slightly warm cloud color.
7. Enable transparency/blending for the material if needed.

For Blender Eevee, set the material blend mode to Alpha Blend or Alpha Hashed. For Cycles, normal material alpha usually works well.

### Blender Cloud Shadows

`cloud_shadow.png` is a helper map for darkening the surface below the cloud layer.

Basic method:

1. Load `cloud_shadow.png` in the planet surface material.
2. Set it to `Non-Color`.
3. Use a ColorRamp or Map Range node to control the strength.
4. Multiply or mix the planet `color.png` toward a darker version of itself using `cloud_shadow.png` as the factor.

Use this map when real shadow casting from a transparent cloud sphere is too slow, too weak, or too noisy.

### Blender City Lights

`city_lights.png` is separate from the surface color. Use it as emission.

1. Load `city_lights.png` as an Image Texture.
2. Set it to `sRGB`.
3. Connect it to an Emission shader or to the Emission Color input of a Principled BSDF.
4. Start with a low emission strength, such as `1` to `3`.
5. Increase the strength for stylized orbital shots.

For the most realistic result, city lights should only be visible on the night side of the planet. Beginners can use the emission map directly. Intermediate users can multiply the city lights by a day/night mask based on the direction of the main light.

## Unreal Engine Notes

Use the equirectangular maps on a sphere mesh with proper UVs, or use the cube/quad-sphere maps with a cube-sphere mesh or cubemap workflow.

Recommended import settings:

| Texture | Suggested Setting |
| --- | --- |
| `color.png` | sRGB on, default color texture |
| `normal.png` | Normal map compression/texture type |
| `roughness.png` | sRGB off, mask/grayscale data |
| `height.png` | sRGB off, grayscale data |
| `land_mask.png`, `shoreline_mask.png`, `ocean_depth.png` | sRGB off, mask data |
| `cloud_mask.png`, `cloud_shadow.png` | sRGB off, mask data |
| `city_lights.png` | sRGB on, emission color |

Basic material wiring:

1. Connect `color.png` to Base Color.
2. Connect `normal.png` to Normal.
3. Connect `roughness.png` to Roughness.
4. Use `height.png` for parallax, bump-style effects, or displacement if your Unreal project is set up for it.
5. Use `city_lights.png` through Emissive Color.
6. Use `cloud_mask.png` on a separate, slightly larger sphere for clouds.
7. Use `cloud_shadow.png` to multiply or darken the surface color below the clouds.

If a roughness map appears backwards, check whether the material or shader expects smoothness instead of roughness. Roughness means white is rougher and less shiny; smoothness means white is smoother and shinier.

## Unity Notes

Unity workflows vary depending on whether you use the Built-in Render Pipeline, URP, or HDRP, but the map meanings stay the same.

Basic setup:

1. Create or import a UV sphere.
2. Create a planet material.
3. Use `color.png` as the Base Map / Albedo.
4. Mark `normal.png` as a Normal Map in Unity's texture import settings.
5. Use `roughness.png` as roughness data if your shader supports roughness.
6. If your Unity shader expects Smoothness, invert `roughness.png` or use Shader Graph to calculate `1 - roughness`.
7. Use `height.png` for parallax, displacement, or shader-based height effects.
8. Put `cloud_mask.png` on a separate larger sphere with a transparent cloud material.
9. Use `city_lights.png` as emission.

Unity's default material workflows often store smoothness in an alpha channel instead of using a separate roughness slot. If you are using a custom Shader Graph material, keep the roughness map as a separate texture and invert it only where the shader needs smoothness.

## Using Cube/Quad-Sphere Maps

Cube/quad-sphere maps are best when you need cleaner detail near the poles. A normal equirectangular sphere stretches pixels heavily at the top and bottom. Cube/quad-sphere mapping spreads the detail more evenly across six square faces.

Use cube/quad-sphere maps when:

- You are building a planet that may be viewed close up.
- You want less polar stretching.
- Your game engine or shader can use six cube faces.
- You are using a cube-sphere mesh with one material or texture assignment per face.

Do not use cube/quad-sphere face maps on a normal UV sphere unless you have a shader that converts cube direction to the correct face.

### Blender Cube-Sphere Face Workflow

One practical Blender method is to create a cube-sphere with six UV islands, one per cube side.

1. Add a cube.
2. Subdivide the cube faces enough for your render or game target.
3. Use a Cast modifier set to Sphere, or another cube-to-sphere method.
4. Keep the six original cube sides as separate material slots or UV islands.
5. Assign each face direction to the matching map:

| Cube Side | Texture Face |
| --- | --- |
| +X side | `px` |
| -X side | `nx` |
| +Y/top side | `py` |
| -Y/bottom side | `ny` |
| +Z/front side | `pz` |
| -Z/back side | `nz` |

Each face texture should fill its own square UV space from 0 to 1. Do not tile the face textures unless you intentionally want repeated terrain.

For each face, use the matching files:

- `px/color.png`, `nx/color.png`, etc. for base color
- `px/height.png`, `nx/height.png`, etc. for height
- `px/normal.png`, `nx/normal.png`, etc. for normals
- `px/roughness.png`, `nx/roughness.png`, etc. for roughness
- matching mask files if you need clouds, shorelines, city lights, or other effects

### Game Engine Cube-Sphere Workflow

For Unreal or Unity, the cleanest planet mesh workflow is usually:

1. Use a cube-sphere mesh with six sides.
2. Give each side a UV layout from 0 to 1.
3. Assign the matching cube face texture to each side.
4. Use the same material logic as the equirectangular setup, but sample the matching face texture for each side.

This is more work than a UV sphere, but it avoids the worst polar stretching.

### Cubemap / TextureCube Workflow

Some tools can import the six faces as a cubemap or TextureCube. This is common for skyboxes, reflections, and custom shaders.

Use the face names as direction labels:

- `px` = +X
- `nx` = -X
- `py` = +Y
- `ny` = -Y
- `pz` = +Z
- `nz` = -Z

If the cubemap appears mirrored or rotated, the issue is usually the target tool's cubemap orientation convention. Try rotating individual faces in 90-degree increments or using the stitched cubemap atlas with that tool's cubemap import/conversion utility.

## Stitched T-Shape Cubemap Layout

The stitched cubemap atlas stores all six faces in one image. In the tall T-shape version included here, the layout is:

```text
[ empty ][ nx ][ empty ]
[  ny   ][ pz ][  py   ]
[ empty ][ px ][ empty ]
[ empty ][ nz ][ empty ]
```

The center face is `pz`. The other faces are arranged around it. Empty cells are transparent or unused padding.

If your software expects a horizontal 4-by-3 cubemap cross instead, rotate or convert the atlas with a cubemap conversion tool. The important part is that the face size remains the same:

- 1536 x 2048 atlas = 512 px faces
- 3072 x 4096 atlas = 1024 px faces
- 6144 x 8192 atlas = 2048 px faces

Most artists will find the six separate face folders easier to use than the stitched atlas. The atlas is mainly included for software that imports cubemap-cross images or for conversion workflows.

## Common Problems

### The Planet Looks Inside Out Or Mirrored

Flip the sphere normals or check whether the texture is being viewed from inside the sphere. For exterior planet surfaces, normals should face outward.

### The Normal Map Looks Wrong

Make sure `normal.png` is imported as Non-Color/Linear data or as a Normal Map texture type. Do not import it as sRGB color.

If bumps look inverted, try inverting the green channel in your software's normal map settings.

### The Roughness Looks Backwards

Some shaders use smoothness instead of roughness.

- Roughness: white = rough, less shiny.
- Smoothness: white = smooth, more shiny.

If your shader expects smoothness, invert `roughness.png`.

### The Cubemap Atlas Does Not Fit A Sphere

That is expected. A stitched T-shape cubemap is not a UV sphere texture. Use the equirectangular maps for normal spheres, or use a cubemap/cube-sphere workflow for the cube maps.

### Clouds Are Not Visible

Check that `cloud_mask.png` is driving opacity/alpha and that the cloud material allows transparency. The cloud sphere should be slightly larger than the planet sphere.

### City Lights Show On The Day Side

The included `city_lights.png` is an emission map. To hide it on the day side, multiply it by a night-side mask in your shader or compositor.

## Recommended Starting Workflow

For beginners:

1. Start with the 2048 x 1024 equirectangular maps.
2. Apply `color.png`, `normal.png`, and `roughness.png`.
3. Add `height.png` through a Bump node or parallax effect.
4. Add clouds only after the surface material looks correct.
5. Add city lights as emission last.

For intermediate users:

1. Use the 4096 x 2048 equirectangular maps for hero renders.
2. Use cube/quad-sphere maps for close-up planet assets or custom game shaders.
3. Use `land_mask.png`, `shoreline_mask.png`, and `ocean_depth.png` to build more advanced ocean, beach, and terrain materials.
4. Use `cloud_shadow.png` to fake consistent surface shadows below clouds.
5. Use `emissive_heat.png` and `city_lights.png` as separate emission layers instead of baking them into the base color.

## License Reminder

Use the license terms from the product listing or included license file. In general, texture maps are meant to be used as assets in your renders, games, animations, and 3D scenes. Do not redistribute or resell the raw texture files unless the product license explicitly allows that.
