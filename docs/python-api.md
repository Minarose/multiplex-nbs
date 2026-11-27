# Python API

Generated from the docstrings by `tools/build_api_docs.py`; the same text is shown by `help(multiplex_nbs.<function>)`. Install with `pip install multiplex-nbs` and import with `import multiplex_nbs`.

- **Run an analysis:** [`nbs`](#nbs), [`multiplex_nbs`](#multiplex_nbs), [`layerwise_nbs`](#layerwise_nbs), [`classic_nbs`](#classic_nbs)
- **Prepare data:** [`make_dataset`](#make_dataset), [`load_dataset`](#load_dataset), [`save_dataset`](#save_dataset), [`build_dataset`](#build_dataset), [`load_demo`](#load_demo), [`describe`](#describe)
- **Read and save results:** [`components`](#components), [`report`](#report), [`set_alpha`](#set_alpha), [`save_results`](#save_results), [`load_results`](#load_results)
- **Figures (optional matplotlib):** [`plot_layer_profile`](#plot_layer_profile), [`plot_membership`](#plot_membership), [`plot_null_distribution`](#plot_null_distribution)
- **Lower-level engine:** [`analyze`](#analyze), [`build_clusters`](#build_clusters)
- **Desktop app:** [`open_app`](#open_app)

## Run an analysis

### nbs

```python
nbs(data, group=None, *, method='multiplex', design=None, threshold=3.0, tail='right', metric='extent', n_perm=9999, seed=1, alpha=0.05, layer=None, permutation='auto', use_abs=False, progress=None, name=None, **dataset)
```

```text
Network-based statistic for one network or a stack of networks.

Tests an effect at every edge (and layer), keeps edges whose statistic exceeds
``threshold``, groups them into connected components, and gives each component a
family-wise corrected p-value from the permutation distribution of the largest
component.

Parameters
----------
data : dict or array_like
    A dataset (:func:`make_dataset`, :func:`load_dataset`, :func:`load_demo`) or the
    connectivity array ``W`` itself, in which case ``group`` and any keyword accepted
    by :func:`make_dataset` (``X``, ``C``, ``axis_values``, ...) may be given here.
group : array_like, optional
    Group labels or pair IDs when ``data`` is an array.
method : {"multiplex", "layerwise", "classic"}
    ``"multiplex"`` (default): a region stays linked to itself in the next layer
    while active, so a component can span layers. ``"layerwise"``: components stay
    within each layer; one correction covers all layers. ``"classic"``: the
    original NBS on one network (or one prespecified ``layer`` of a stack).
design : {"two-sample", "paired", "one-sample", "glm-t", "glm-f"}, optional
    Defaults to the design the dataset supports (GLM if ``X`` and ``C`` are present,
    otherwise two-sample or paired from ``group``).
threshold : float
    Primary threshold on the edge statistic (t or F; signed mean for a classic
    one-sample test). Choose it before looking at results.
tail : {"right", "left", "both"}
    Direction tested. ``"both"`` forms positive and negative components separately
    and corrects over both with one maximum.
metric : {"extent", "mass", "intensity"}
    Component statistic, available for every method. ``"extent"``: region–layer
    sites (multiplex/layer-wise) or edges (classic). ``"mass"``: the summed
    statistic of the component's suprathreshold edges. ``"intensity"``: mass with the
    threshold subtracted from each edge, i.e. the summed excess over the threshold
    (intensity in NBS Connectome v1.2).
n_perm : int
    Number of random permutations (default 9999). The smallest attainable p is
    1/(n_perm + 1); use at least 5000 for reported results.
seed : int or None
    Random seed, for reproducibility.
alpha : float
    Reporting cutoff used for the summary and the ``significant`` flags; inference
    itself does not depend on it.
layer : int, optional
    For ``method="classic"`` on a stack, the 1-based layer chosen in advance.
permutation : {"auto", "freedman-lane", "rowshuffle"}
    GLM resampling. ``"auto"`` uses label shuffles (two-sample), sign flips
    (paired, one-sample) or Freedman–Lane (GLM).
use_abs : bool
    Use absolute connectivity values.
progress : callable, optional
    Called as ``progress(done, total)`` during permutations.
name : str, optional
    A name for the dataset, used in reports (defaults to the demo title or "Dataset").

Returns
-------
dict
    JSON-compatible result. Key fields:

    - ``clusters``: one dict per observed component with ``id``, ``p_fwe``,
      ``extent``, ``mass``, ``tail``, ``nodes`` (1-based regions), ``layer_bins``
      (1-based layers) and ``sites`` ([region, layer] pairs).
    - ``statistic`` (edges × layers) and ``edges`` (1-based region pairs).
    - ``null_max``: the largest component in each permutation.
    - ``config``, ``dataset``, ``software``: everything needed to reproduce the run.
    - ``methods``: a methods paragraph to adapt for a paper.
    - ``interpretation``: a plain-language summary and caveats.

See Also
--------
multiplex_nbs, layerwise_nbs, classic_nbs, components, report, save_results

Notes
-----
The corrected p-value applies to a component as a whole: it does not make any
single edge, region or layer significant, and the first and last layers of a
component are not corrected estimates of where an effect starts or stops.

References
----------
Zalesky A, Fornito A, Bullmore ET (2010). Network-based statistic: identifying
differences in brain networks. NeuroImage 53:1197–1207.

Examples
--------
>>> from multiplex_nbs import load_demo, nbs, components
>>> result = nbs(load_demo(), method="multiplex", n_perm=999)
>>> for c in components(result, significant_only=True):
...     print(c["id"], c["p_fwe"], c["extent"], c["regions"])
```

### multiplex_nbs

```python
multiplex_nbs(data, group=None, **options)
```

```text
Multiplex-NBS: components that can continue across neighbouring layers.

A region active in two adjacent layers (time points, frequency bins, ...) is
linked to itself, so an effect that persists across layers forms one component
and is tested once. Equivalent to ``nbs(data, group, method="multiplex", ...)``;
see :func:`nbs` for every option and the returned fields.

Examples
--------
>>> from multiplex_nbs import load_demo, multiplex_nbs
>>> result = multiplex_nbs(load_demo(), threshold=3, n_perm=999)
>>> print(result["interpretation"]["summary"])
```

### layerwise_nbs

```python
layerwise_nbs(data, group=None, **options)
```

```text
Layer-wise NBS: classic NBS in every layer with one correction across layers.

Components stay within their own layer; the permutation maximum is taken over all
layers, so the family-wise error rate is controlled across the whole stack.
Equivalent to ``nbs(data, group, method="layerwise", ...)``; see :func:`nbs`.
```

### classic_nbs

```python
classic_nbs(data, group=None, *, layer=None, metric='extent', **options)
```

```text
Classic NBS (Zalesky et al., 2010) on one network per observation.

For a stack of networks, choose one ``layer`` (1-based) in advance. ``metric`` is
``"extent"`` (number of edges), ``"mass"`` (summed edge statistics) or
``"intensity"`` (summed excess over the threshold, as in NBS Connectome). Equivalent to ``nbs(data, group, method="classic", ...)``; see
:func:`nbs`. See ``docs/classic-nbs-parity.md`` for agreement with NBS v1.2.
```

## Prepare data

### make_dataset

```python
make_dataset(W, group=None, *, X=None, C=None, stat_type=None, axis_values=None, axis_name='Layer', axis_unit='', node_labels=None, node_coordinates=None, coordinate_space='MNI (mm)', exchange_blocks=None, observation_ids=None)
```

```text
Bundle arrays into a validated Multiplex-NBS dataset.

Parameters
----------
W : array_like, shape (observations, regions, regions[, layers])
    One undirected (symmetric) connectivity matrix per observation, or one stack of
    matrices per observation along an ordered axis such as time or frequency.
    Every observation must use the same regions in the same order.
group : array_like, shape (observations,), optional
    Group labels (two-sample design) or pair IDs, each appearing twice
    (paired design). Labels may be numbers or text.
X : array_like, shape (observations, regressors), optional
    GLM design matrix. Include an intercept column yourself.
C : array_like, shape (regressors,) or (contrasts, regressors), optional
    GLM contrast: one row for a t contrast, several independent rows for an F test.
stat_type : {"t", "F"}, optional
    GLM statistic. Defaults to "t" for one contrast row and "F" otherwise.
axis_values : array_like, shape (layers,), optional
    Strictly increasing value of each layer, e.g. ``[4, 6, 8]`` Hz.
    Defaults to ``1, 2, ...``.
axis_name, axis_unit : str
    Label and unit of the layer axis, e.g. ``"Frequency"`` and ``"Hz"``.
node_labels : sequence of str, optional
    Region names, in the order of ``W``'s rows.
node_coordinates : array_like, shape (regions, 3), optional
    Region centres, used only for brain figures. MNI millimetres are expected for
    glass-brain outlines.
coordinate_space : str
    Description of the coordinate space, e.g. ``"MNI (mm)"``.
exchange_blocks : array_like, shape (observations,), optional
    Restrict permutations to within these blocks (e.g. scanner site).
observation_ids : sequence of str, optional
    Participant identifiers, kept with the dataset for reference.

Returns
-------
dict
    A validated dataset accepted by :func:`nbs`, :func:`multiplex_nbs`,
    :func:`layerwise_nbs`, :func:`classic_nbs` and :func:`save_dataset`.

Examples
--------
>>> import numpy as np
>>> from multiplex_nbs import make_dataset
>>> W = np.random.default_rng(0).normal(size=(20, 10, 10, 5))
>>> W = (W + W.transpose(0, 2, 1, 3)) / 2          # symmetric
>>> data = make_dataset(W, group=[0] * 10 + [1] * 10,
...                     axis_values=[8, 10, 12, 14, 16], axis_name="Frequency", axis_unit="Hz")
```

### load_dataset

```python
load_dataset(path)
```

```text
Load a dataset from a NumPy ``.npz`` or MATLAB v7 ``.mat`` file.

Parameters
----------
path : str or pathlib.Path
    ``.npz``: ``W`` shaped (observations, regions, regions[, layers]).
    ``.mat``: ``W`` as a cell array with one regions × regions × layers matrix per
    observation, or numeric regions × regions × layers × observations.
    Optional fields in either format: ``group``, ``X``, ``C``, ``stat_type``,
    ``exchange_blocks``, ``axis_values``, ``axis_name``, ``axis_unit``,
    ``node_labels``, ``node_coordinates``. MATLAB ``-v7.3`` (HDF5) files are not
    supported; save with ``save(file, ..., '-v7')``.

Returns
-------
dict
    A validated dataset (see :func:`make_dataset`).

See Also
--------
save_dataset, build_dataset, load_demo
```

### save_dataset

```python
save_dataset(data, path)
```

```text
Save a dataset to a ``.npz`` file that :func:`load_dataset` and the app can open.

Parameters
----------
data : dict
    A dataset from :func:`make_dataset`, :func:`load_dataset`, :func:`build_dataset`
    or :func:`load_demo`.
path : str or pathlib.Path
    Destination; ``.npz`` is appended if missing.

Returns
-------
pathlib.Path
    The file written.
```

### build_dataset

```python
build_dataset(groups, *, variable=None, axis_name='Layer', axis_unit='', first_value=1.0, step=1.0)
```

```text
Assemble a dataset from one ZIP archive of participant files per group.

Each ZIP holds one file per participant: ``.mat`` or ``.npy`` (regions × regions ×
layers), or ``.csv``/``.tsv``/``.txt`` for a single network. Participants are
ordered by file name within each archive (natural order: 2 before 10).

Parameters
----------
groups : sequence of (label, path) pairs
    For example ``[("Control", "control.zip"), ("Patient", "patient.zip")]``.
variable : str, optional
    Name of the variable to read from each ``.mat`` file when it holds several.
axis_name, axis_unit : str
    Label and unit of the layer axis.
first_value, step : float
    Axis value of the first layer and the spacing between layers.

Returns
-------
dict
    A validated dataset with ``group`` labels taken from the archive labels and
    ``observation_ids`` of the form ``group/file``.
```

### load_demo

```python
load_demo(name='brain-network', seed=7)
```

```text
Load one of the bundled practice datasets. All observations and effects are simulated.

Parameters
----------
name : {"brain-network", "two-sample", "paired", "glm"}
    ``"brain-network"``: 32 regions of an open human structural connectome
    (Škoch et al., 2022) with MNI coordinates; 40 simulated participants in two
    groups; 8 time windows (0–350 ms). Group A is higher along a left
    sensorimotor–parietal chain at 100–200 ms.
    ``"two-sample"``, ``"paired"``, ``"glm"``: 12 abstract nodes, 8 frequency bins
    (4–18 Hz), with a planted effect on nodes 1–4 at 8–12 Hz, illustrating each
    study design.
seed : int
    Random seed of the simulation.

Returns
-------
dict
    A validated dataset.
```

### describe

```python
describe(data)
```

```text
Summarise a dataset: sizes, groups, layer axis and which designs it supports.

Returns
-------
dict
    Includes ``subjects``, ``nodes``, ``layer_count``, ``axis``, ``group_counts``,
    ``designs`` (readiness of each design) and ``suggested_design``.
```

## Read and save results

### components

```python
components(result, significant_only=False)
```

```text
List the observed components in a readable form, most significant first.

Parameters
----------
result : dict
    A result from :func:`nbs` or its variants.
significant_only : bool
    Keep only components with corrected p at or below the reporting alpha.

Returns
-------
list of dict
    Each with ``id``, ``p_fwe``, ``significant``, ``direction`` ("positive",
    "negative" or "F"), ``extent``, ``mass``, ``intensity``,
    ``n_regions``, ``regions`` (labels), ``region_indices`` (1-based),
    ``layers`` (1-based indices) and ``axis_values`` (values of those layers).
```

### report

```python
report(result)
```

```text
Return a plain-text report: summary, notes, every component, methods draft and settings.
```

### set_alpha

```python
set_alpha(result, alpha)
```

```text
Change the reporting cutoff of a result in place (no new permutations are run).

Updates the ``significant`` summary, the interpretation and the methods text.
Returns the same result for convenience.
```

### save_results

```python
save_results(result, path)
```

```text
Save a result; the format follows the file extension.

``.json``: the complete result (settings, memberships, edge statistics, permutation
maxima) — reload with ``json.load``. ``.mat``: the same for MATLAB, with the main
arrays as variables. ``.csv``: one row per component. ``.txt``: the text report.

Returns
-------
pathlib.Path
    The file written.
```

### load_results

```python
load_results(path)
```

```text
Load a result saved with ``save_results(result, "file.json")``.
```

## Figures (optional matplotlib)

### plot_layer_profile

```python
plot_layer_profile(result, component=None, ax=None)
```

```text
Bar chart of the component's regions in each layer, against everything above threshold.

Parameters
----------
result : dict
component : int, optional
    Component id; defaults to the most significant.
ax : matplotlib.axes.Axes, optional

Returns
-------
matplotlib.axes.Axes
```

### plot_membership

```python
plot_membership(result, component=None, ax=None)
```

```text
Region × layer grid of the component's sites; shading counts its edges at each site.

Returns
-------
matplotlib.axes.Axes
```

### plot_null_distribution

```python
plot_null_distribution(result, component=None, ax=None)
```

```text
Histogram of the largest component in each permutation, with the observed size.

Returns
-------
matplotlib.axes.Axes
```

## Lower-level engine

### analyze

```python
analyze(W, group=None, X=None, C=None, stat_type='t', test='two-sample', threshold=3.0, tail='right', metric='extent', n_perm=9999, seed=1, exchange_blocks=None, method='auto', use_abs=False, progress=None, layer_adjacency='consecutive', inference_mode='multiplex', classic_layer=None)
```

```text
Fit and permute complete networks shaped subjects × nodes × nodes × bins.

Independent tests use Welch t, sorted first group minus sorted second.
Paired tests use pair IDs in ``group``; the first encountered observation
minus the second defines each difference. GLMs require full-rank ``X``
and ``C`` (one row for t, independent rows for F). Supply intercepts in X.

``auto`` resolves to label-shuffle, sign-flip, or Freedman-Lane. Explicit
GLM ``rowshuffle`` permutes whole design rows, including nuisance columns;
use it only when this matches the experimental randomization. For either
GLM method, exchange_blocks restricts shuffles within blocks. A GLM whose
tested contrast cannot vary under the allowed shuffles is rejected.

Random permutations are drawn with replacement. P-values include the
observed statistic: (1 + number of null maxima >= observed) / (B + 1).
Both-tail tests share one maximum over separately formed signed clusters.
Results are JSON-compatible; all reported indices are one-based.
``progress(completed, total)`` is called initially and after every draw.
``layer_adjacency='consecutive'`` joins active copies of a node in adjacent
array slices. ``'independent'`` never joins slices; the null maximum still
spans every slice. This option must be chosen before viewing results.

Classic NBS accepts one matrix per observation (S,N,N). For a stack
(S,N,N,L), choose one prespecified 1-based classic_layer. Extent counts
retained edges in classic mode and active node-layer sites otherwise. In
every mode, mass sums the retained tail-adjusted edge statistics and
intensity sums each of them minus the threshold (NBS Connectome intensity).
Result layer indices address the analyzed slice. config.classic_layer
records its index in the original data.
A one-sample design independently flips the sign of each observation's
complete map. The classic implementation uses the unstandardized edge
mean as in NBS Connectome v1.2. Multiplex uses the one-sample t statistic.
The joint distribution of each observation's map must be sign-symmetric
under the null, with independent observations.
```

### build_clusters

```python
build_clusters(statistic, edges, n_nodes, threshold=3.0, tail='right', metric='extent', layer_adjacency='consecutive', inference_mode='multiplex')
```

```text
Build clusters from an edge-by-bin map and zero-based edge pairs.

Returned node, bin, and site indices are one-based for MATLAB agreement.
``tail='both'`` keeps the two signs separate. No inference occurs here.
Edges must be unique upper-triangle pairs; the diagonal is not an edge.
```

## Desktop app

### open_app

```python
open_app()
```

```text
Open the Multiplex-NBS desktop app from Python (requires Tk).
```
