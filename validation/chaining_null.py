"""How large do chance clusters get? Null cluster size versus network size and threshold.

Simulates edge-wise t maps with no true effect (df=38, 10 layers) and reports the
median largest cluster extent under consecutive and independent layer adjacency.
It isolates the clustering step: no resampling, so it shows the null maximum that
the permutation distribution would contain, not a calibration result.

    python validation/chaining_null.py
"""
import numpy as np
from scipy import stats

from multiplex_nbs.core import build_clusters

DF, LAYERS, REPS = 38, 10, 20


def null_maps(n_edges, rho, rng):
    """Gaussian null with AR(1) correlation rho between neighbouring layers, mapped to t(DF)."""
    z = rng.standard_normal((n_edges, LAYERS))
    for layer in range(1, LAYERS):
        z[:, layer] = rho * z[:, layer - 1] + np.sqrt(1 - rho ** 2) * z[:, layer]
    return stats.t.ppf(stats.norm.cdf(z), DF)


def main():
    rng = np.random.default_rng(0)
    print("nodes  t>   p_edge  P(node active)  rho  median max extent: consecutive / independent  (of sites)")
    for n in (32, 100, 200, 400):
        j, i = np.tril_indices(n, -1)
        edges = np.column_stack((i, j))
        for threshold in (3.0, 3.5, 4.0):
            p_edge = stats.t.sf(threshold, DF)
            p_node = 1 - (1 - p_edge) ** (n - 1)
            for rho in (0.0, 0.7):
                maxima = {"consecutive": [], "independent": []}
                for _ in range(REPS):
                    t = null_maps(len(edges), rho, rng)
                    for adjacency in maxima:
                        clusters = build_clusters(t, edges, n, threshold, "right", "extent", adjacency)
                        maxima[adjacency].append(max((c["extent"] for c in clusters), default=0))
                print(f"{n:5d}  {threshold:3.1f}  {p_edge:.4f}  {p_node:14.2f}  {rho:3.1f}  "
                      f"{np.median(maxima['consecutive']):8.1f} / {np.median(maxima['independent']):6.1f}"
                      f"  ({n * LAYERS})")


if __name__ == "__main__":
    main()
