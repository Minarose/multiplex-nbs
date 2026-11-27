"""Offline teaching example based on an attributed, openly licensed connectome.

Only the baseline template is empirical. All observations, groups, ordered
layers, noise, and planted group effects are simulated by this module.
"""
import json
from pathlib import Path

import numpy as np


def make_brain_demo(seed=7):
    """Return NPZ-safe arrays: 40 simulated observations, 32 regions, 8 layers."""
    folder = Path(__file__).parent / "data"
    with np.load(folder / "skoch2022_mean32.npz", allow_pickle=False) as source:
        baseline = source["adjacency"].copy()
        labels = source["node_labels"].copy()
        region_ids = source["source_region_ids"].copy()
    provenance = json.loads((folder / "skoch2022_provenance.json").read_text(encoding="utf-8"))
    centroids = json.loads((folder / "aal_centroids_mni.json").read_text(encoding="utf-8"))
    rng = np.random.default_rng(seed)
    n = len(labels)
    subjects, layers = 40, 8
    # Scale is deliberately arbitrary: these are not tractography probabilities.
    template = baseline / baseline.max()
    noise_scale = .06 + .12 * template
    random = rng.normal(size=(subjects, n, n, layers))
    noise = (random + random.transpose(0, 2, 1, 3)) / np.sqrt(2)
    weights = template[None, :, :, None] + noise * noise_scale[None, :, :, None]
    weights[:, np.arange(n), np.arange(n), :] = 0
    group = np.repeat(["Simulated A", "Simulated B"], subjects // 2)
    # A left sensorimotor/parietal chain on known positive template connections.
    source_edges = [(1, 57), (57, 59), (59, 67)]
    edges = [(int(np.flatnonzero(region_ids == a)[0]), int(np.flatnonzero(region_ids == b)[0]))
             for a, b in source_edges]
    for a, b in edges:
        weights[:subjects // 2, a, b, 2:5] += 1.6 * noise_scale[a, b]
        weights[:, b, a, :] = weights[:, a, b, :]
    info = {
        "title": "Open connectome · simulated time-course study",
        "source_url": provenance["source_url"],
        "paper_url": provenance["paper_url"],
        "citation": provenance["citation"],
        "license": provenance["license"],
        "license_url": provenance["license_url"],
        "simulation_note": "The 32-region baseline is derived from an openly licensed human structural connectome. All 40 observations, group labels, time layers and group effects are simulated; this is not an empirical group comparison.",
        "template_modifications": provenance["modifications"],
        "node_coordinates": "AAL region centroids in MNI mm (Tzourio-Mazoyer et al., 2002); see aal_centroids_mni.json. They locate each region for display and are not part of the source connectome.",
        "seed": int(seed),
        "ground_truth": {
            "group_direction": "Simulated A > Simulated B",
            "nodes_1based": sorted({i + 1 for edge in edges for i in edge}),
            "edges_1based": [[a + 1, b + 1] for a, b in edges],
            "source_aal_edges_1based": [list(edge) for edge in source_edges],
            "layer_bins_1based": [3, 4, 5],
            "axis_values": [100, 150, 200],
            "axis_unit": "ms",
            "note": "The recovered component may include noise sites. Component significance does not establish significance at every displayed node, edge, or layer.",
        },
        "suggested_config": {"design": "two-sample", "threshold": 3, "tail": "right", "metric": "extent", "n_perm": 9999, "seed": 1, "alpha": .05},
    }
    return {
        "W": weights,
        "group": group,
        "node_labels": labels,
        "node_coordinates": np.array(centroids["coordinates_mm"]),
        "coordinate_space": "MNI (mm)",
        "axis_name": np.array("Time"),
        "axis_unit": np.array("ms"),
        "axis_values": np.arange(layers) * 50,
        "demo_info_json": np.array(json.dumps(info, ensure_ascii=False)),
    }
