# Changelog

## 0.1.0 (unreleased)

First public release.

- Classic, layer-wise and multiplex network-based statistics with permutation
  family-wise error control; two-sample, paired, one-sample and GLM (t and F) designs.
- Component extent, mass or intensity in every method. Intensity (as in NBS Connectome)
  is mass with the threshold subtracted from each edge, chosen in the apps with
  "Subtract the threshold from each edge" under Mass. 9,999 permutations by default.
- Desktop app for macOS (Apple silicon and Intel) and Windows: data import (combined
  files or one ZIP per group), model set-up, results with layer profile, node × layer,
  glass-brain, all-layers and null-distribution figures, and exports. Light, Dark and
  Mono modes.
- Python package `multiplex_nbs` with documented functions, a command line
  (`multiplex-nbs`) and optional matplotlib figures.
- MATLAB toolbox (`mnbs_*` functions) with help text, a GUI and a self-test.
- Bundled practice datasets shared by the app, Python and MATLAB.
