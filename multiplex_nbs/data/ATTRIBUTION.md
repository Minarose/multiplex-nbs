# Open-connectome teaching template

The derived `skoch2022_mean32.npz` dataset is adapted from:

Antonín Škoch, Barbora Rehák Bučková, Jan Mareš, Jaroslav Tintěra, Pavel Sanda,
Lucia Jajcay, Jiří Horáček, Filip Španiel and Jaroslav Hlinka (2022).
*Human brain structural connectivity matrices–ready for modelling*.
Scientific Data 9, 486. [doi:10.1038/s41597-022-01596-9](https://doi.org/10.1038/s41597-022-01596-9).

Source dataset: [OSF YW5VF](https://osf.io/yw5vf/),
[doi:10.17605/OSF.IO/YW5VF](https://doi.org/10.17605/OSF.IO/YW5VF).
Copyright © The Author(s) 2022.
Licensed under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
The license text is included in `LICENSE-CC-BY-4.0.txt`; its canonical legal code
is <https://creativecommons.org/licenses/by/4.0/legalcode>.

Changes: averaged the 88 source matrices, symmetrized the mean, zeroed the
diagonal, and selected 32 bilateral sensorimotor, occipital and parietal regions.
Source region IDs, file URLs and SHA-256 hashes are in `skoch2022_provenance.json`.
The generator adds simulated observations, noise, groups, layers and effects;
those are not original participant measurements. No individual source matrices
or demographics are redistributed here.

Node coordinates in `aal_centroids_mni.json` are centroids (mean voxel
position, MNI mm) of the same 32 regions in the AAL atlas for SPM12:
Tzourio-Mazoyer N, et al. Automated anatomical labeling of activations in SPM
using a macroscopic anatomical parcellation of the MNI MRI single-subject brain.
NeuroImage 15, 273–289 (2002). [doi:10.1006/nimg.2001.0978](https://doi.org/10.1006/nimg.2001.0978).
They are regenerated with `tools/build_demo_coordinates.py`; the atlas itself is
not redistributed.

This material is provided as-is without warranties. Attribution does not imply
endorsement by the source authors. The dataset license is separate from the
toolbox's software licensing and continues to apply to this derived template.
