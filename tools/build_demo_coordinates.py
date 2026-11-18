"""Compute MNI centroids for the 32 AAL regions of the open example dataset.

Run from the repository root with nilearn installed (build time only):

    python tools/build_demo_coordinates.py [--data-dir DIR]

nilearn downloads the AAL atlas for SPM12 (Tzourio-Mazoyer et al., 2002) on
first use. Each region's centroid is the mean MNI position (mm) of its voxels.
Only the 32 × 3 centroids are written, to
multiplex_nbs/data/aal_centroids_mni.json; the atlas itself is not stored.
"""
import argparse
import json
from pathlib import Path

import nibabel
import numpy as np
from nilearn import datasets

root = Path(__file__).resolve().parents[1]
data = root / "multiplex_nbs" / "data"
parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", default=None)
args = parser.parse_args()

with np.load(data / "skoch2022_mean32.npz", allow_pickle=False) as source:
    region_ids = source["source_region_ids"].tolist()
    node_labels = source["node_labels"].tolist()
atlas = datasets.fetch_atlas_aal(version="SPM12", data_dir=args.data_dir, verbose=0)
image = nibabel.load(atlas.maps)
volume = np.asarray(image.dataobj)
names, centroids = [], []
for region in region_ids:  # AAL90 numbering; labels[0] is Background
    name, code = atlas.labels[region], int(atlas.indices[region])
    voxels = np.argwhere(volume == code)
    if not len(voxels):
        raise SystemExit(f"No voxels for AAL region {region} ({name}).")
    mm = nibabel.affines.apply_affine(image.affine, voxels)
    names.append(name)
    centroids.append(np.round(mm.mean(axis=0), 1).tolist())
for node, aal in zip(node_labels, names):
    side = "L" if aal.endswith("_L") else "R"
    if not node.startswith(side + " "):
        raise SystemExit(f"Hemisphere mismatch: {node} vs {aal}")
out = {
    "description": "Centroids (mean voxel position, MNI mm) of the AAL regions used by the open example dataset, in node order.",
    "atlas": "AAL for SPM12 (automated anatomical labelling), via nilearn.datasets.fetch_atlas_aal",
    "citation": "Tzourio-Mazoyer N, et al. Automated anatomical labeling of activations in SPM using a macroscopic anatomical parcellation of the MNI MRI single-subject brain. NeuroImage 15, 273–289 (2002). doi:10.1006/nimg.2001.0978.",
    "aal_names": names,
    "coordinates_mm": centroids,
}
(data / "aal_centroids_mni.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
for node, aal, c in zip(node_labels, names, centroids):
    print(f"{node:28s} {aal:22s} {c}")
