"""Rebuild the small attributed connectome template from the two OSF source files.

Run: python tools/prepare_open_demo.py --source-dir /path/to/downloads
Source URLs and hashes are recorded below. No network access is made by this script.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.io import loadmat


SOURCES = {
    "SCmatrices88healthy.mat": {
        "url": "https://osf.io/download/6823g/",
        "sha256": "6e68a62517490abdb63e451bfb48f3256abc31ed4d7591f7a85d0f566b9f2f64",
    },
    "AAL_regions.csv": {
        "url": "https://osf.io/download/6a8jx/",
        "sha256": "c26dd24d785a88534186db280eff83f4a206743f1797a5282252b99e38fe3a0b",
    },
}
# Bilateral sensorimotor, occipital, and parietal regions; original 1-based ROI IDs.
REGION_IDS = [1, 2, 19, 20, *range(43, 71)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    for name, source in SOURCES.items():
        digest = hashlib.sha256((args.source_dir / name).read_bytes()).hexdigest()
        if digest != source["sha256"]:
            raise ValueError(f"Source checksum mismatch: {name}; review the upstream version before proceeding.")
    matrices = loadmat(args.source_dir / "SCmatrices88healthy.mat")["SCmatrices"]
    if matrices.shape != (88, 90, 90) or not np.isfinite(matrices).all():
        raise ValueError("Unexpected source matrix dimensions or non-finite values.")
    mean = matrices.mean(axis=0)
    mean = (mean + mean.T) / 2
    np.fill_diagonal(mean, 0)
    indices = np.array(REGION_IDS) - 1
    with (args.source_dir / "AAL_regions.csv").open() as handle:
        labels = {int(row["ROI number"]): row["ROI name"] for row in csv.DictReader(handle, delimiter=";")}
    output = Path(__file__).resolve().parents[1] / "multiplex_nbs" / "data"
    output.mkdir(exist_ok=True)
    np.savez_compressed(output / "skoch2022_mean32.npz",
                        adjacency=mean[np.ix_(indices, indices)],
                        node_labels=np.array([labels[i] for i in REGION_IDS]),
                        source_region_ids=np.array(REGION_IDS))
    provenance = {
        "title": "Human brain structural connectivity matrices—ready for modelling",
        "authors": "Antonín Škoch, Barbora Rehák Bučková, Jan Mareš, Jaroslav Tintěra, Pavel Sanda, Lucia Jajcay, Jiří Horáček, Filip Španiel and Jaroslav Hlinka",
        "citation": "Škoch A, et al. Human brain structural connectivity matrices–ready for modelling. Scientific Data 9, 486 (2022). doi:10.1038/s41597-022-01596-9.",
        "source_url": "https://osf.io/yw5vf/",
        "paper_url": "https://doi.org/10.1038/s41597-022-01596-9",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "copyright": "© The Author(s) 2022",
        "retrieved": "2026-11-06",
        "source_files": SOURCES,
        "source_shape": [88, 90, 90],
        "source_region_ids_1based": REGION_IDS,
        "modifications": "Averaged 88 matrices; symmetrized with (A + A.T)/2; set the diagonal to zero; retained 32 bilateral sensorimotor, occipital and parietal regions in source order. No individual records or demographics are bundled.",
        "coordinates": "Not supplied. Layouts of this template are schematic, not anatomical coordinates.",
        "disclaimer": "Provided as-is, without warranties. The original authors do not endorse Multiplex-NBS or its simulated demonstration.",
    }
    (output / "skoch2022_provenance.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n")
    print(f"Prepared {len(REGION_IDS)}-region template in {output}")


if __name__ == "__main__":
    main()
