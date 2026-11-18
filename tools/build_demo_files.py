"""Write the practice datasets in data/ as MATLAB v7 files (also readable from Python).

    python tools/build_demo_files.py

Every observation and effect is simulated. The brain example uses the openly
licensed connectome template documented in docs/demo-data.md.
"""
from pathlib import Path

import numpy as np
from scipy.io import savemat

from multiplex_nbs import load_demo

root = Path(__file__).resolve().parents[1]
DESCRIPTIONS = {
    "brain-network": "32 regions of an open human structural connectome (Skoch et al., 2022) with AAL centroids in "
                     "MNI mm; 40 simulated participants in two groups; 8 time windows (0-350 ms). Group 1 "
                     "(Simulated A) is higher along a left sensorimotor-parietal chain at 100-200 ms.",
    "two-sample": "12 nodes, 40 simulated participants in two groups, 8 frequency bins (4-18 Hz). "
                  "Group 1 is higher along nodes 1-4 at 8-12 Hz.",
    "paired": "20 simulated participants in two conditions (group holds pair IDs; the first observation of each "
              "pair is condition 1), 12 nodes, 8 frequency bins. Condition 1 is higher along nodes 1-4 at 8-12 Hz.",
    "glm": "40 simulated participants, 12 nodes, 8 frequency bins, with a design matrix "
           "[intercept, group, covariate] and a contrast testing the group effect adjusted for the covariate.",
}


def cellstr(values):
    out = np.empty((1, len(values)), dtype=object)
    out[0, :] = [str(v) for v in values]
    return out


for name, description in DESCRIPTIONS.items():
    data = load_demo(name)
    w = data["W"]
    cells = np.empty((w.shape[0], 1), dtype=object)
    for s in range(w.shape[0]):
        cells[s, 0] = w[s]  # N x N x L for each observation
    record = {"W": cells, "axisName": data["axis_name"], "axisUnit": data["axis_unit"],
              "axisValues": data["axis_values"].reshape(1, -1), "nodeLabels": cellstr(data["node_labels"]),
              "description": description,
              # Python field names, so multiplex_nbs.load_dataset reads the same file.
              "axis_name": data["axis_name"], "axis_unit": data["axis_unit"],
              "axis_values": data["axis_values"].reshape(1, -1)}
    if "X" in data:
        record["model"] = {"X": data["X"], "C": data["C"], "statType": data.get("stat_type", "t")}
    elif "group" in data:
        labels = np.asarray(data["group"])
        if labels.dtype.kind in "US":
            names = sorted(set(labels.tolist()))
            record["group"] = np.array([names.index(v) + 1 for v in labels], dtype=float).reshape(-1, 1)
            record["groupNames"] = cellstr(names)
        else:
            record["group"] = labels.astype(float).reshape(-1, 1) + (1 if name == "two-sample" else 0)
    if "node_coordinates" in data:
        record["nodeCoordinates"] = data["node_coordinates"]
        record["coordinateSpace"] = data["coordinate_space"]
        record["node_coordinates"] = data["node_coordinates"]
        record["coordinate_space"] = data["coordinate_space"]
    target = root / "data" / f"demo_{name.replace('-', '_')}.mat"
    savemat(target, record, do_compression=True, oned_as="column")
    print(target.relative_to(root), f"{target.stat().st_size / 1e6:.1f} MB")
