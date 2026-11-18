# Data format

Multiplex-NBS analyses undirected (symmetric) connectivity matrices. Each observation
(usually a participant) contributes one regions × regions matrix, or a stack of
matrices measured at successive **layers**: time windows, frequency bins or another
ordered measurement of the same network. Every observation must use the same regions
in the same order.

## The connectivity array `W`

| Where | Layout |
|---|---|
| Python, `.npz` files | `W[observation, region, region, layer]`, e.g. shape `(40, 32, 32, 8)`; leave out the last axis for one network |
| MATLAB, `.mat` files | a cell array with one `N × N × L` matrix per observation (recommended), or numeric `N × N × L × S` |
| MATLAB functions | the cell array above, or numeric `S × N × N × L` |

Values must be real and finite. Missing values must be resolved before analysis.

## Study design

| Design | Provide | Tested |
|---|---|---|
| Two groups | `group`: one label per observation (numbers, or text in Python) | Welch t, first sorted label minus the second |
| Paired conditions | `group`: pair IDs, each appearing twice | First observation of each pair minus the second (sign flips) |
| One sample (Python, app) | nothing extra | Signed values against zero (sign flips) |
| GLM | `X`: observations × regressors, with an intercept column; `C`: 1 × regressors (t) or k × regressors (F); `stat_type`: `"t"` or `"F"` | The contrast, with Freedman–Lane permutation by default |

`exchange_blocks` (optional, one label per observation) restricts permutations to
within blocks, e.g. scanner site.

## Layer axis and regions (optional)

| Field (Python / file) | MATLAB option | Meaning |
|---|---|---|
| `axis_values` | `opts.axisValues` | Strictly increasing value of each layer, e.g. `[4, 6, 8]` |
| `axis_name`, `axis_unit` | `opts.axisName`, `opts.axisUnit` | e.g. `Frequency`, `Hz` |
| `node_labels` | `nodeLabels` | Region names |
| `node_coordinates` | `nodeCoordinates` | Regions × 3 centres; MNI mm for glass-brain figures |

## Three ways to provide data

**1. One combined file.** A NumPy `.npz` with `W` and the fields above, or a MATLAB
`.mat` saved with `-v7`:

```matlab
% W: one N x N x L matrix per participant
save('study.mat', 'W', 'group', 'axisValues', 'axisName', 'axisUnit', 'nodeLabels', '-v7');
```

```python
import numpy as np
np.savez("study.npz", W=W, group=group, axis_values=[4, 6, 8], axis_name="Frequency", axis_unit="Hz")
```

**2. One ZIP per group.** Put each participant's file in a folder for its group and zip
each folder. Use `.mat` or `.npy` files holding regions × regions × layers, or
`.csv`/`.tsv`/`.txt` for one network. The ZIP becomes the group; participants are
ordered by file name (natural order, so `sub-2` comes before `sub-10`).

```
control.zip          patient.zip
  sub-01.mat           sub-31.mat
  sub-02.mat           sub-32.mat
  ...                  ...
```

In Python: `build_dataset([("control", "control.zip"), ("patient", "patient.zip")])`.
In the app: **Data → Open my data → One ZIP per group**.

**3. Arrays in a script.** Python: `make_dataset(W, group, axis_values=..., ...)`.
MATLAB: pass `W` and `group` (or `model`) straight to `mnbs_analyze`.

A dataset saved from Python (`save_dataset`) or the app (**Save dataset**) is a `.npz`
that opens in both. The bundled demos in `data/` are `.mat` files readable from
MATLAB (`mnbs_load_demo`) and Python (`load_dataset`).
