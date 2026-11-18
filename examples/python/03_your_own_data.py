"""Three ways to bring your own connectivity data.

Every participant needs the same regions in the same order. W is
observations × regions × regions × layers (leave out layers for one network).
"""
import numpy as np

from multiplex_nbs import build_dataset, load_dataset, make_dataset, multiplex_nbs, save_dataset

# 1. Arrays you already have in Python ---------------------------------------------
rng = np.random.default_rng(1)
W = rng.normal(size=(30, 20, 20, 6))
W = (W + W.transpose(0, 2, 1, 3)) / 2                 # matrices must be symmetric
group = np.array(["control"] * 15 + ["patient"] * 15)
data = make_dataset(W, group,
                    axis_values=[4, 8, 13, 20, 30, 45], axis_name="Frequency", axis_unit="Hz",
                    node_labels=[f"Region {i + 1}" for i in range(20)])
save_dataset(data, "my_study.npz")                    # reopen later, or in the desktop app

# 2. A file saved from Python or MATLAB ---------------------------------------------
#    .npz with W (and group, axis_values, ...), or a MATLAB v7 .mat with a cell array W
#    holding one regions × regions × layers matrix per participant.
data = load_dataset("my_study.npz")

# 3. One ZIP of participant files per group ------------------------------------------
#    control.zip holds sub-01.mat, sub-02.mat, ...; patient.zip likewise.
#    Each file is regions × regions × layers (.mat or .npy), or a .csv for one network.
# data = build_dataset([("control", "control.zip"), ("patient", "patient.zip")],
#                      axis_name="Frequency", axis_unit="Hz", first_value=1, step=1)

# Optional: brain coordinates for figures (regions × 3, MNI mm)
# data = make_dataset(W, group, node_coordinates=coords, coordinate_space="MNI (mm)")

result = multiplex_nbs(data, threshold=3.0, n_perm=499, name="My study")
print(result["interpretation"]["headline"])
