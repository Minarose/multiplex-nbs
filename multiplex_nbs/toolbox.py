"""Researcher-facing functions for Multiplex-NBS.

These functions wrap the inference engine (:func:`multiplex_nbs.analyze`) and the
input/report helpers used by the desktop app, so a script, the command line and the
app produce identical results, methods text and exports.

All indices in results are 1-based (region 1 is the first row of ``W``), so results
match the MATLAB toolbox. Every function returns plain Python/NumPy objects.
"""
from pathlib import Path
import json

import numpy as np

from . import io as _io

METHODS = ("multiplex", "layerwise", "classic")
DESIGNS = ("two-sample", "paired", "one-sample", "glm-t", "glm-f")
_DEMOS = ("brain-network", "two-sample", "paired", "glm")


# ----------------------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------------------
def make_dataset(W, group=None, *, X=None, C=None, stat_type=None, axis_values=None, axis_name="Layer",
                 axis_unit="", node_labels=None, node_coordinates=None, coordinate_space="MNI (mm)",
                 exchange_blocks=None, observation_ids=None):
    """Bundle arrays into a validated Multiplex-NBS dataset.

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
    """
    data = {"W": np.asarray(W), "axis_name": axis_name, "axis_unit": axis_unit}
    if axis_values is not None:
        data["axis_values"] = np.asarray(axis_values, dtype=float)
    optional = {"group": group, "X": X, "C": C, "node_labels": node_labels, "exchange_blocks": exchange_blocks,
                "observation_ids": observation_ids}
    data.update({key: value for key, value in optional.items() if value is not None})
    if node_coordinates is not None:
        data["node_coordinates"] = np.asarray(node_coordinates, dtype=float)
        data["coordinate_space"] = coordinate_space
    if X is not None and stat_type is None:
        stat_type = "t" if np.atleast_2d(np.asarray(C, dtype=float)).shape[0] == 1 else "F"
    if stat_type is not None:
        data["stat_type"] = stat_type
    return _io.validate_dataset(data)


def load_dataset(path):
    """Load a dataset from a NumPy ``.npz`` or MATLAB v7 ``.mat`` file.

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
    """
    return _io.load_dataset(Path(path))


def save_dataset(data, path):
    """Save a dataset to a ``.npz`` file that :func:`load_dataset` and the app can open.

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
    """
    path = Path(path)
    if path.suffix.lower() != ".npz":
        path = path.with_suffix(".npz")
    path.write_bytes(_io.dataset_npz(data))
    return path


def build_dataset(groups, *, variable=None, axis_name="Layer", axis_unit="", first_value=1.0, step=1.0):
    """Assemble a dataset from one ZIP archive of participant files per group.

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
    """
    axis = {"name": axis_name, "unit": axis_unit, "start": float(first_value), "step": float(step)}
    return _io.build_dataset([(label, Path(path).read_bytes()) for label, path in groups], variable, axis)


def load_demo(name="brain-network", seed=7):
    """Load one of the bundled practice datasets. All observations and effects are simulated.

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
    """
    if name not in _DEMOS:
        raise ValueError(f"name must be one of {', '.join(_DEMOS)}.")
    if name == "brain-network":
        from .demo import make_brain_demo
        data = _io.validate_dataset(make_brain_demo(seed))
    else:
        data = _io.validate_dataset(_io.make_demo(name, seed))
        data["demo_info"] = {"title": f"Simulated {name} study",
                             "simulation_note": "All measurements, observations and effects are simulated."}
    return data


def describe(data):
    """Summarise a dataset: sizes, groups, layer axis and which designs it supports.

    Returns
    -------
    dict
        Includes ``subjects``, ``nodes``, ``layer_count``, ``axis``, ``group_counts``,
        ``designs`` (readiness of each design) and ``suggested_design``.
    """
    return _io.describe(data)


# ----------------------------------------------------------------------------------------
# Inference
# ----------------------------------------------------------------------------------------
def nbs(data, group=None, *, method="multiplex", design=None, threshold=3.0, tail="right", metric="extent",
        n_perm=9999, seed=1, alpha=0.05, layer=None, permutation="auto", use_abs=False, progress=None, name=None,
        **dataset):
    """Network-based statistic for one network or a stack of networks.

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
    """
    if not isinstance(data, dict):
        data = make_dataset(data, group, **dataset)
    elif group is not None or dataset:
        raise ValueError("Give group and other arrays to make_dataset, or pass the array W as data.")
    if method not in METHODS:
        raise ValueError(f"method must be one of {', '.join(METHODS)}.")
    layered = np.asarray(data["W"]).shape[3] > 1
    if design is None:
        design = _io.describe(data)["suggested_design"]
        if not design:
            raise ValueError("Choose a design: the dataset has no group labels or design matrix.")
    if design not in DESIGNS:
        raise ValueError(f"design must be one of {', '.join(DESIGNS)}.")
    config = {"design": design, "threshold": float(threshold), "tail": tail, "metric": metric,
              "n_perm": int(n_perm), "seed": seed, "method": permutation, "use_abs": bool(use_abs),
              "alpha": float(alpha)}
    if method == "classic":
        if layered and layer is None:
            raise ValueError("Classic NBS on a stack needs the layer chosen in advance (1-based).")
        config.update(inference_mode="classic", classic_layer=1 if layer is None else int(layer))
    else:
        if layer is not None:
            raise ValueError("layer is only used with method='classic'.")
        config.update(inference_mode="multiplex",
                      layer_adjacency="independent" if method == "layerwise" else "consecutive")
    result = _io.run_dataset(data, config, progress)
    result["dataset_name"] = name or data.get("demo_info", {}).get("title") or "Dataset"
    _io.refresh_report(result)
    return result


def multiplex_nbs(data, group=None, **options):
    """Multiplex-NBS: components that can continue across neighbouring layers.

    A region active in two adjacent layers (time points, frequency bins, ...) is
    linked to itself, so an effect that persists across layers forms one component
    and is tested once. Equivalent to ``nbs(data, group, method="multiplex", ...)``;
    see :func:`nbs` for every option and the returned fields.

    Examples
    --------
    >>> from multiplex_nbs import load_demo, multiplex_nbs
    >>> result = multiplex_nbs(load_demo(), threshold=3, n_perm=999)
    >>> print(result["interpretation"]["summary"])
    """
    return nbs(data, group, method="multiplex", **options)


def layerwise_nbs(data, group=None, **options):
    """Layer-wise NBS: classic NBS in every layer with one correction across layers.

    Components stay within their own layer; the permutation maximum is taken over all
    layers, so the family-wise error rate is controlled across the whole stack.
    Equivalent to ``nbs(data, group, method="layerwise", ...)``; see :func:`nbs`.
    """
    return nbs(data, group, method="layerwise", **options)


def classic_nbs(data, group=None, *, layer=None, metric="extent", **options):
    """Classic NBS (Zalesky et al., 2010) on one network per observation.

    For a stack of networks, choose one ``layer`` (1-based) in advance. ``metric`` is
    ``"extent"`` (number of edges), ``"mass"`` (summed edge statistics) or
    ``"intensity"`` (summed excess over the threshold, as in NBS Connectome). Equivalent to ``nbs(data, group, method="classic", ...)``; see
    :func:`nbs`. See ``docs/classic-nbs-parity.md`` for agreement with NBS v1.2.
    """
    return nbs(data, group, method="classic", layer=layer, metric=metric, **options)


# ----------------------------------------------------------------------------------------
# Results
# ----------------------------------------------------------------------------------------
def components(result, significant_only=False):
    """List the observed components in a readable form, most significant first.

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
    """
    alpha = result.get("reporting", {}).get("alpha", .05)
    data = result.get("dataset", {})
    labels = data.get("node_labels")
    axis_values = data.get("axis", {}).get("values")
    rows = []
    for c in sorted(result["clusters"], key=lambda c: (c["p_fwe"], -c["test_stat"], c["id"])):
        if significant_only and c["p_fwe"] > alpha:
            continue
        direction = "F" if result["config"].get("stat_type") == "f" else ("negative" if c["tail"] == "left" else "positive")
        row = {"id": c["id"], "p_fwe": c["p_fwe"], "significant": c["p_fwe"] <= alpha, "direction": direction,
               "extent": c["extent"], "n_regions": c["n_nodes"], "region_indices": list(c["nodes"]),
               "regions": [labels[n - 1] for n in c["nodes"]] if labels else list(c["nodes"]),
               "layers": list(c["layer_bins"]),
               "axis_values": [axis_values[b - 1] for b in c["layer_bins"]] if axis_values else list(c["layer_bins"])}
        row["mass"] = c["mass"]
        row["intensity"] = c.get("intensity")
        rows.append(row)
    return rows


def set_alpha(result, alpha):
    """Change the reporting cutoff of a result in place (no new permutations are run).

    Updates the ``significant`` summary, the interpretation and the methods text.
    Returns the same result for convenience.
    """
    result.setdefault("reporting", {})["alpha"] = _io.validate_alpha(float(alpha))
    _io.refresh_report(result)
    return result


def report(result):
    """Return a plain-text report: summary, notes, every component, methods draft and settings."""
    return _io.result_text(result).decode("utf-8")


def save_results(result, path):
    """Save a result; the format follows the file extension.

    ``.json``: the complete result (settings, memberships, edge statistics, permutation
    maxima) — reload with ``json.load``. ``.mat``: the same for MATLAB, with the main
    arrays as variables. ``.csv``: one row per component. ``.txt``: the text report.

    Returns
    -------
    pathlib.Path
        The file written.
    """
    path = Path(path)
    writers = {".json": lambda r: json.dumps(r, indent=2, allow_nan=False, ensure_ascii=False).encode("utf-8"),
               ".mat": _io.result_mat, ".csv": _io.result_csv, ".txt": _io.result_text}
    suffix = path.suffix.lower()
    if suffix not in writers:
        raise ValueError("Use a .json, .mat, .csv or .txt file name.")
    path.write_bytes(writers[suffix](result))
    return path


def load_results(path):
    """Load a result saved with ``save_results(result, "file.json")``."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------------------
# Figures (optional: pip install "multiplex-nbs[plot]")
# ----------------------------------------------------------------------------------------
def _pyplot():
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError('Figures need matplotlib: pip install "multiplex-nbs[plot]"') from exc
    return plt


def _component(result, component):
    clusters = {c["id"]: c for c in result["clusters"]}
    if component is None:
        if not clusters:
            raise ValueError("The result has no components.")
        return min(result["clusters"], key=lambda c: (c["p_fwe"], -c["test_stat"]))
    if component not in clusters:
        raise ValueError(f"No component {component} in this result.")
    return clusters[component]


def _axis_label(result):
    axis = result["dataset"]["axis"]
    return f"{axis['name']} ({axis['unit']})" if axis.get("unit") else axis["name"]


def plot_layer_profile(result, component=None, ax=None):
    """Bar chart of the component's regions in each layer, against everything above threshold.

    Parameters
    ----------
    result : dict
    component : int, optional
        Component id; defaults to the most significant.
    ax : matplotlib.axes.Axes, optional

    Returns
    -------
    matplotlib.axes.Axes
    """
    plt = _pyplot()
    c = _component(result, component)
    values = np.asarray(result["dataset"]["axis"]["values"], dtype=float)
    stat = np.asarray(result["statistic"], dtype=float)
    edges = np.asarray(result["edges"]) - 1
    threshold = result["config"]["threshold"]
    keep = stat > threshold if c["tail"] != "left" else stat < -threshold
    active_all = [len(set(edges[keep[:, layer]].ravel())) for layer in range(stat.shape[1])]
    in_component = np.bincount([layer for _, layer in c["sites"]], minlength=stat.shape[1] + 1)[1:]
    created = ax is None
    ax = ax or plt.subplots(figsize=(7.5, 3.8))[1]
    ticks = np.arange(len(values))
    ax.bar(ticks, active_all, color="#c3cfcd", label="All regions above threshold (same sign)")
    ax.bar(ticks, in_component, color="#00695c", label=f"Component {c['id']}")
    ax.set_xticks(ticks, [f"{v:g}" for v in values])
    ax.set_xlabel(_axis_label(result))
    ax.set_ylabel("Active regions")
    ax.set_title(f"Component {c['id']} · corrected p = {c['p_fwe']:.3g}", loc="left", pad=28)
    ax.legend(frameon=False, ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0), borderaxespad=0.2)
    ax.spines[["top", "right"]].set_visible(False)
    if created:
        ax.figure.tight_layout()
    return ax


def plot_membership(result, component=None, ax=None):
    """Region × layer grid of the component's sites; shading counts its edges at each site.

    Returns
    -------
    matplotlib.axes.Axes
    """
    plt = _pyplot()
    c = _component(result, component)
    values = result["dataset"]["axis"]["values"]
    labels = result["dataset"]["node_labels"]
    nodes = list(c["nodes"])
    stat = np.asarray(result["statistic"], dtype=float)
    edges = np.asarray(result["edges"]) - 1
    threshold = result["config"]["threshold"]
    keep = stat > threshold if c["tail"] != "left" else stat < -threshold
    sites = {(n - 1, layer - 1) for n, layer in c["sites"]}
    grid = np.full((len(nodes), len(values)), np.nan)
    for row, node in enumerate(nodes):
        for layer in range(len(values)):
            if (node - 1, layer) in sites:
                touching = [k for k in np.flatnonzero(keep[:, layer]) if node - 1 in edges[k]
                            and (edges[k][0], layer) in sites and (edges[k][1], layer) in sites]
                grid[row, layer] = len(touching)
    created = ax is None
    ax = ax or plt.subplots(figsize=(7.5, 0.45 * len(nodes) + 1.8))[1]
    image = ax.imshow(grid, aspect="auto", cmap="GnBu", vmin=0)
    ax.set_yticks(range(len(nodes)), [labels[n - 1] for n in nodes])
    ax.set_xticks(range(len(values)), [f"{v:g}" for v in values])
    ax.set_xlabel(_axis_label(result))
    ax.set_title(f"Component {c['id']}: regions by layer", loc="left")
    ax.figure.colorbar(image, ax=ax, label="Component edges at the site")
    if created:
        ax.figure.tight_layout()
    return ax


def plot_null_distribution(result, component=None, ax=None):
    """Histogram of the largest component in each permutation, with the observed size.

    Returns
    -------
    matplotlib.axes.Axes
    """
    plt = _pyplot()
    c = _component(result, component)
    null = np.asarray(result["null_max"], dtype=float)
    alpha = result.get("reporting", {}).get("alpha", .05)
    created = ax is None
    ax = ax or plt.subplots(figsize=(7.5, 3.8))[1]
    ax.hist(null, bins=24, color="#c3cfcd", label="Largest component per permutation")
    ax.axvline(c["test_stat"], color="#00695c", linewidth=2.5, label=f"Component {c['id']} ({c['test_stat']:g})")
    critical = np.sort(null)[::-1][max(0, int(np.floor(alpha * (len(null) + 1))) - 1)] if len(null) else None
    if critical is not None:
        ax.axvline(critical, color="#132523", linestyle=":", label=f"Critical value at α = {alpha:g}")
    ax.set_xlabel(f"Largest component ({result['config']['metric']})")
    ax.set_ylabel("Permutations")
    ax.legend(frameon=False, ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0), borderaxespad=0.2, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    if created:
        ax.figure.tight_layout()
    return ax


def open_app():
    """Open the Multiplex-NBS desktop app from Python (requires Tk)."""
    from .native_app import main
    main()
