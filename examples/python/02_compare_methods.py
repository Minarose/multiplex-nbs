"""Classic, layer-wise and multiplex NBS on the same data.

- Classic NBS tests one layer chosen in advance (here 100 ms).
- Layer-wise NBS tests every layer; components stay in their layer, and one
  permutation correction covers all layers.
- Multiplex-NBS links a region to itself in neighbouring layers, so an effect that
  persists over time forms one component.

Choose the method before seeing results; running all three and keeping the best one
is a multiple comparison that the correction does not cover.
"""
from multiplex_nbs import classic_nbs, components, layerwise_nbs, load_demo, multiplex_nbs

data = load_demo("brain-network")
settings = dict(threshold=3.0, n_perm=999, seed=1)

results = {
    "Classic NBS (100 ms)": classic_nbs(data, layer=3, **settings),
    "Layer-wise NBS": layerwise_nbs(data, **settings),
    "Multiplex-NBS": multiplex_nbs(data, **settings),
}
for name, result in results.items():
    significant = components(result, significant_only=True)
    print(f"\n{name}: {len(significant)} of {len(result['clusters'])} components significant")
    for c in significant:
        span = c["axis_values"]
        when = f"{span[0]:g} ms" if len(span) == 1 else f"{span[0]:g}–{span[-1]:g} ms"
        print(f"  #{c['id']}: p = {c['p_fwe']:.3g}, extent {c['extent']}, {c['n_regions']} regions, {when}")
