"""Multiplex-NBS: network-based statistics for one network or a stack of networks.

Classic, layer-wise and multiplex NBS for connectivity measured at successive time
points, frequencies or other ordered layers. Quick start::

    from multiplex_nbs import load_demo, multiplex_nbs, components, report
    result = multiplex_nbs(load_demo(), threshold=3, n_perm=999)
    for c in components(result, significant_only=True):
        print(c["id"], c["p_fwe"], c["regions"], c["axis_values"])
    print(report(result))

Main functions
--------------
nbs, multiplex_nbs, layerwise_nbs, classic_nbs   Run an analysis.
make_dataset, load_dataset, save_dataset,
build_dataset, load_demo, describe               Prepare data.
components, report, set_alpha, save_results,
load_results                                     Read and save results.
plot_layer_profile, plot_membership,
plot_null_distribution                           Figures (needs matplotlib).
analyze, build_clusters                          Lower-level engine.
open_app                                         Open the desktop app.

See ``help(multiplex_nbs.nbs)`` and docs/python-api.md for details.
"""

from .core import analyze, build_clusters
from .toolbox import (METHODS, DESIGNS, build_dataset, classic_nbs, components, describe, layerwise_nbs,
                      load_dataset, load_demo, load_results, make_dataset, multiplex_nbs, nbs, open_app,
                      plot_layer_profile, plot_membership, plot_null_distribution, report, save_dataset,
                      save_results, set_alpha)

__all__ = ["nbs", "multiplex_nbs", "layerwise_nbs", "classic_nbs",
           "make_dataset", "load_dataset", "save_dataset", "build_dataset", "load_demo", "describe",
           "components", "report", "set_alpha", "save_results", "load_results",
           "plot_layer_profile", "plot_membership", "plot_null_distribution",
           "analyze", "build_clusters", "open_app", "METHODS", "DESIGNS"]

# Publication version. It stays 0.1.0 for the paper and citations; internal
# pre-release iterations are tracked by __build__ and recorded with every result.
__version__ = "0.1.0"
__build__ = "0.4.0"
