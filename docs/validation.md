# Validation

This page records what has been tested and what has not. Please treat Multiplex-NBS as
research software and check that its assumptions suit your study.

## Automated tests

Every change runs the test suite on Linux, macOS and Windows with several Python versions
(see `.github/workflows/tests.yml`). The suite checks:

- Welch and paired t against SciPy; GLM t against ordinary least squares; F against t²
  and a nested-model F; a reconstructed Freedman–Lane draw and blocked row permutations.
- Component building: layer links, disconnected layers, strict thresholds, separate
  signs with a joint two-tailed maximum, and the plus-one p-value rule.
- Classic extent and intensity on small graphs against hand-computed permutation maxima.
- Reproducibility with a seed, input validation, file import (NPZ, MAT cells, MATLAB
  `model` structs, ZIP archives) and every export format.
- The public Python functions and the command line.

Each desktop app is built by GitHub Actions on its own operating system and starts
itself in a test mode that runs all three methods on the demo, draws every results
figure and checks the exports, before its ZIP is published.

## Agreement with NBS Connectome

Classic mode reproduces the 40-edge component of the official NBS v1.2 schizophrenia
example (intensity 11.5400132708); see [Classic NBS parity](classic-nbs-parity.md).

## Error rate under the null

A small simulation (`validation/validate_null.py`) generated 100 datasets per scenario
with no effect (24 observations, 8 regions, 6 correlated layers, two-sided threshold 3,
extent, 199 permutations). Exact binomial 95% intervals:

| Design | Layers | Any component rejected / 100 | Family-wise error | 95% interval |
|---|---|---:|---:|---:|
| Two groups | linked (multiplex) | 0 | 0.00 | 0.000–0.036 |
| Two groups | separate (layer-wise) | 4 | 0.04 | 0.011–0.099 |
| Paired | linked (multiplex) | 3 | 0.03 | 0.006–0.085 |
| Paired | separate (layer-wise) | 0 | 0.00 | 0.000–0.036 |

These small, Gaussian checks are consistent with error control at α = .05 and are
sometimes conservative because extent is discrete. They do not establish performance
for large networks, unequal variances, GLMs with nuisance covariates, complex
dependence or partial alternatives. Settings and results: [null-calibration.json](null-calibration.json).

## Demo recovery

On the brain demo (threshold 3, seed 1), multiplex NBS finds one component of 15
region–time sites spanning 100–250 ms around the planted 100–200 ms chain; classic
NBS at 100 ms finds a 3-edge component. This shows the pipeline recovers a strong planted
effect; it is not an estimate of power. The extra time point illustrates why component
membership does not give a precise effect boundary.

## MATLAB

The MATLAB toolbox shares a golden fixture with the Python package (`mnbs_selftest`).
It has not yet been executed in this project's automated tests; the workflow runs it
once the repository is public (MathWorks provides MATLAB for public GitHub projects).
Run `mnbs_selftest` before relying on MATLAB results. Seeded permutations are not
expected to match between languages; statistics and component structure should.

## Not yet established

- Calibration across sample sizes, variance imbalance, dependence structures,
  nuisance covariates and exchangeability blocks.
- Power relative to classic NBS and other cluster or multilayer methods.
- Usability testing with researchers new to the tool.
