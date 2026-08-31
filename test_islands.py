import numpy as np
from rocky_planet_gen import build_maps, PRESETS, PlanetConfig
base = PRESETS["earthlike"].copy()
base.update(land_coverage=0.65)
c0 = PlanetConfig(preset="earthlike", seed=7, width=64, height=32, **base)
m0 = build_maps(c0, map_names=["land_ocean_mask"])["land_ocean_mask"]
print("no-island shape dtype min max:", m0.shape, m0.dtype, m0.min(), m0.max())
print("no-island land frac:", float(np.mean(m0 > 0.5)))
base2 = base.copy()
base2.update(island_density=0.9, island_scale=16.0, island_threshold=0.62, island_min_area=0.00002, island_max_area=0.004)
c1 = PlanetConfig(preset="earthlike", seed=7, width=64, height=32, **base2)
m1 = build_maps(c1, map_names=["land_ocean_mask"])["land_ocean_mask"]
print("with-island land frac:", float(np.mean(m1 > 0.5)))
print("masks differ:", not np.array_equal(m0, m1))
print("added frac:", float(np.mean( (m1 > 0.5) & (m0 <= 0.5) )))
print("SUCCESS")
