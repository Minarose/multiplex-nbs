# Multiplex-NBS

**Network-based statistics for one network or a stack of networks** measured at
successive time points, frequency bins or other ordered layers — as a desktop app, a
Python package and a MATLAB toolbox.

[![Tests](https://github.com/Minarose/multiplex-nbs/actions/workflows/tests.yml/badge.svg)](https://github.com/Minarose/multiplex-nbs/actions/workflows/tests.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![MATLAB R2021a+](https://img.shields.io/badge/MATLAB-R2021a%2B-blue)

The network-based statistic (NBS; Zalesky et al., 2010) finds connected sets of edges
that differ between groups or conditions and controls the family-wise error rate with
permutations. Multiplex-NBS keeps that logic and adds the layer axis:

| Method | What counts as connected | Use when |
|---|---|---|
| **Classic NBS** | Edges sharing regions, in one network (or one layer chosen in advance) | You test a single network |
| **Layer-wise NBS** | As classic, separately in every layer; one correction across all layers | You want to know which layers show an effect |
| **Multiplex-NBS** | Also a region with itself in the next layer, so a component can span layers | An effect may persist across time or frequency |

![Layer profile and permutation distribution of the demo component](docs/images/demo-results.png)

## Desktop app (no programming)

Download the ZIP for your computer from the
[latest release](https://github.com/Minarose/multiplex-nbs/releases/latest):

| Computer | File |
|---|---|
| Mac with Apple silicon (macOS 14+) | `Multiplex-NBS-<version>-macOS-arm64.zip` |
| Mac with an Intel processor (macOS 11+) | `Multiplex-NBS-<version>-macOS-x86_64.zip` |
| Windows 10 or 11 (64-bit) | `Multiplex-NBS-<version>-Windows-x86_64.zip` |

Extract it and open **MultiplexNBS**. The app is not yet signed, so confirm the first
launch: on macOS Control-click → **Open**; on Windows **More info → Run anyway**.
Everything runs on your computer. See the [app guide](docs/app-guide.md).

## Python

```bash
pip install "multiplex-nbs[plot] @ git+https://github.com/Minarose/multiplex-nbs"
```

```python
from multiplex_nbs import load_demo, multiplex_nbs, components, report

data = load_demo("brain-network")              # or load_dataset("study.npz") / make_dataset(W, group, ...)
result = multiplex_nbs(data, threshold=3.0, n_perm=5000, seed=1)

for c in components(result, significant_only=True):
    print(c["id"], c["p_fwe"], c["regions"], c["axis_values"])
print(result["methods"])                         # a methods paragraph to adapt for a paper
```

Also `layerwise_nbs`, `classic_nbs`, `save_results` (`.json`, `.csv`, `.mat`, `.txt`)
and figures (`plot_layer_profile`, `plot_membership`, `plot_null_distribution`). From a
terminal: `multiplex-nbs run study.npz --output result.json`, or `multiplex-nbs` to open
the app. Every function is documented: `help(multiplex_nbs.nbs)` or the
[Python API](docs/python-api.md). Worked [examples](examples/python).

## MATLAB

Download or clone the repository, then:

```matlab
addpath('multiplex-nbs/matlab')
mnbs_selftest                                    % check the installation once

d = mnbs_load_demo('brain-network');
opts = struct('t0', 3, 'nPerm', 5000, 'axisName', d.axisName, ...
              'axisUnit', d.axisUnit, 'axisValues', d.axisValues);
result = mnbs_analyze(d.W, d.group, opts);       % Multiplex-NBS
disp(result.significant)
```

`opts.layerAdjacency = 'independent'` gives layer-wise NBS; pass `model` (`X`, `C`,
`statType`) instead of `group` for a GLM. `help Contents` lists every function and
`mnbs_gui` opens an interactive window. See the [MATLAB API](docs/matlab-api.md) and
[examples](examples/matlab). Base MATLAB R2021a or newer; no other toolbox needed.

## Your data

One undirected connectivity matrix per participant (regions × regions), or one per
layer, with the same regions in the same order for everyone, plus group labels, pair
IDs or a design matrix. Load a single `.npz`/`.mat` file, or one ZIP of participant
files per group. See [Data format](docs/data-format.md).

## Documentation

[App guide](docs/app-guide.md) · [Data format](docs/data-format.md) ·
[Interpreting results](docs/interpreting-results.md) · [Python API](docs/python-api.md) ·
[MATLAB API](docs/matlab-api.md) · [Method](docs/method.md) ·
[Classic NBS parity](docs/classic-nbs-parity.md) · [Validation](docs/validation.md) ·
[Limitations](docs/limitations.md) · [Security and privacy](docs/security-and-privacy.md)

A corrected p-value applies to a **component as a whole**, not to its individual edges,
regions or layers. Choose the method, threshold and component measure before looking at
results. See [Interpreting results](docs/interpreting-results.md).

## Citing

If you use Multiplex-NBS, please cite the software ([CITATION.cff](CITATION.cff); GitHub's
**Cite this repository** button gives APA and BibTeX) and the original method:

> Zalesky A, Fornito A, Bullmore ET (2010). Network-based statistic: identifying
> differences in brain networks. *NeuroImage* 53:1197–1207.
> doi:10.1016/j.neuroimage.2010.06.041

## Authors

Minarose M. Ismail, Brady J. Williamson and Darren S. Kadis. Multiplex-NBS develops
Darren S. Kadis's March 2026 MATLAB prototype; see [Contributors](docs/contributors.md).

## Licence

Multiplex-NBS is free software under the [GNU General Public License v3](LICENSE) or
later. The brain demo uses an openly licensed (CC BY 4.0) structural connectome; see
[Demo data](docs/demo-data.md). Questions and bug reports:
[issues](https://github.com/Minarose/multiplex-nbs/issues). Contributions welcome — see
[CONTRIBUTING](CONTRIBUTING.md).
