# An open brain network, with a simulated study

The built-in brain-network demo uses a real human structural-connectivity
template with fully simulated observations. It teaches the analysis workflow;
its group difference is planted and is not a finding about the source cohort.

The template is adapted from the openly licensed
[Škoch et al. (2022) dataset](https://doi.org/10.1038/s41597-022-01596-9).
The authors provide 90-region connectivity matrices for 88 healthy adults under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Source files: [OSF repository](https://osf.io/yw5vf/),
[matrix archive](https://osf.io/download/6823g/),
[region labels](https://osf.io/download/6a8jx/).

## What is empirical and what is simulated?

| Part | Origin |
|---|---|
| Region names and baseline connections | Published structural connectome |
| 32-region template | Mean of the 88 matrices, symmetrized, zero diagonal; selected bilateral sensorimotor, occipital and parietal regions |
| Forty observations, two groups of twenty | Simulated |
| Eight time layers, 0–350 ms | Simulated; the original structural data have no time axis |
| Group difference at 100–200 ms | Planted in three connections linking left precentral, postcentral, superior parietal and precuneus regions |
| Node coordinates | AAL region centroids in MNI mm (Tzourio-Mazoyer et al., 2002), used by the Brain view |

The source matrix is divided by its largest off-diagonal entry. Independent
Gaussian edge noise is generated symmetrically, with standard deviation
`0.06 + 0.12 × normalized template weight`. The planted group-A increase is
1.6 noise standard deviations on three edges in layers 3–5. The simulation uses
seed 7 by default. Synthetic weights are arbitrary signed values, not streamline
probabilities or a biophysical model of time-resolved connectivity.

Run the demo with its default right-tailed independent-groups test, threshold 3,
extent, 9,999 permutations and permutation seed 1. The output records both the
simulation provenance and analysis settings. A significant component supports
component-level inference; its membership can extend beyond the planted sites
because of random noise. Individual nodes, edges and time points do not acquire
their own corrected significance from membership.

## Reproduce the template

Download the two small source files linked above into one folder, then run:

```sh
python tools/prepare_open_demo.py --source-dir /path/to/source-files
```

The script checks the recorded SHA-256 hashes before deriving the bundled
template. The original 1-based region IDs are `1, 2, 19, 20, 43, …, 70`.
The bundle contains only the aggregate template, labels, provenance and license.
The source does not include coordinates, so the example uses the centroids of
the same AAL regions in the AAL atlas for SPM12 (mean voxel position, MNI mm),
computed by `tools/build_demo_coordinates.py` and stored in
`multiplex_nbs/data/aal_centroids_mni.json`. See `multiplex_nbs/data/ATTRIBUTION.md` for the
full attribution and licensing notice.

## What this demo does not establish

This single planted-effect example checks usability and recovery of a known
effect. It does not estimate sensitivity, false-positive control, external
validity or clinical usefulness. Those require repeated null and alternative
simulations and suitable independent data. The subset is a teaching selection,
not a complete connectome or a canonical functional network.
