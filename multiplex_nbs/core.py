"""Node-layer network-based statistics for complete undirected networks.

This implements the node-frequency graph in Darren S. Kadis's March 2026
MATLAB prototype. Every retained edge joins its endpoints within a bin;
active copies of the same node join across consecutive bins. Extent counts
node-bin sites. Mass sums half of each retained statistic at both endpoints.

Inference is at cluster level, never at individual nodes, edges, or bins.
Label/row shuffles require exchangeability within the specified blocks;
Welch studentization alone does not guarantee exact inference under unequal
distributions. Paired sign flips require independent, symmetric differences.
Freedman-Lane residual permutation is generally approximate with nuisance
regressors. Blocks describe within-block shuffling only, not nested designs.
The layer axis may represent time, frequency, or another ordered dimension.
Consecutive adjacency follows array order, not physical distance. Independent
adjacency leaves slices disconnected while correcting across all slices.
"""

import numpy as np
from scipy.linalg import null_space
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def _real_array(value, name):
    raw = np.asarray(value)
    if np.iscomplexobj(raw):
        raise ValueError(f"{name} must be real-valued.")
    try:
        arr = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain numbers.") from exc
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains NaN or infinity; complete finite data are required.")
    return arr


def _positive_integer(value, name, minimum=1):
    if isinstance(value, (bool, np.bool_)) or not np.isscalar(value):
        raise ValueError(f"{name} must be an integer >= {minimum}.")
    try:
        integer = int(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{name} must be an integer >= {minimum}.") from exc
    if integer != value or integer < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")
    return integer


def _labels(value, n, name):
    arr = np.asarray(value)
    if arr.ndim != 1 or len(arr) != n:
        raise ValueError(f"{name} must be a one-dimensional vector with {n} entries.")
    if arr.dtype.kind in "biuf":
        if not np.all(np.isfinite(arr)):
            raise ValueError(f"{name} cannot contain missing or infinite labels.")
    elif arr.dtype.kind in "US":
        if np.any(np.char.strip(arr.astype(str)) == ""):
            raise ValueError(f"{name} cannot contain empty labels.")
    else:
        raise ValueError(f"{name} must contain numeric or string labels.")
    return arr


def build_clusters(statistic, edges, n_nodes, threshold=3.0, tail="right", metric="extent",
                   layer_adjacency="consecutive", inference_mode="multiplex"):
    """Build clusters from an edge-by-bin map and zero-based edge pairs.

    Returned node, bin, and site indices are one-based for MATLAB agreement.
    ``tail='both'`` keeps the two signs separate. No inference occurs here.
    Edges must be unique upper-triangle pairs; the diagonal is not an edge.
    """
    statistic = _real_array(statistic, "statistic")
    if statistic.ndim != 2 or statistic.shape[1] < 1:
        raise ValueError("statistic must have shape edges × layers.")
    n_nodes = _positive_integer(n_nodes, "n_nodes", 2)
    raw_edges = _real_array(edges, "edges")
    if raw_edges.shape != (statistic.shape[0], 2):
        raise ValueError("edges must have shape (number of statistics rows, 2).")
    if np.any(raw_edges != np.floor(raw_edges)):
        raise ValueError("edges must contain integer node indices.")
    edges = raw_edges.astype(int)
    if (np.any(edges < 0) or np.any(edges >= n_nodes)
            or np.any(edges[:, 0] >= edges[:, 1])
            or len(np.unique(edges, axis=0)) != len(edges)):
        raise ValueError("edges must be unique upper-triangle pairs within 0..n_nodes-1.")
    _check_cluster_options(threshold, tail, metric, layer_adjacency, inference_mode)
    if inference_mode == "classic" and statistic.shape[1] != 1:
        raise ValueError("Classic NBS requires a single column of edge statistics.")
    return _clusters(statistic, edges, n_nodes, float(threshold), tail, metric,
                     layer_adjacency, inference_mode)


def _check_cluster_options(threshold, tail, metric, layer_adjacency, inference_mode):
    if isinstance(threshold, (bool, np.bool_)) or not isinstance(threshold, (int, float, np.integer, np.floating)):
        raise ValueError("threshold must be a finite positive statistic threshold.")
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("threshold must be a finite positive statistic threshold.")
    if tail not in ("right", "left", "both"):
        raise ValueError("tail must be 'right', 'left', or 'both'.")
    if inference_mode not in ("classic", "multiplex"):
        raise ValueError("inference_mode must be 'classic' or 'multiplex'.")
    metrics = ("extent", "intensity") if inference_mode == "classic" else ("extent", "mass")
    if metric not in metrics:
        raise ValueError(f"{inference_mode} metric must be '{metrics[0]}' or '{metrics[1]}'.")
    if layer_adjacency not in ("consecutive", "independent"):
        raise ValueError("layer_adjacency must be 'consecutive' or 'independent'.")


def _clusters(statistic, edges, n_nodes, threshold, tail, metric, layer_adjacency, inference_mode):
    result = []
    signs = ("right", "left") if tail == "both" else (tail,)
    n_freq = statistic.shape[1]
    for sign in signs:
        effective = statistic if sign == "right" else -statistic
        edge_ids, bins = np.where(effective > threshold)
        if not len(edge_ids):
            continue
        a = bins * n_nodes + edges[edge_ids, 0]
        b = bins * n_nodes + edges[edge_ids, 1]
        mass = np.zeros(n_nodes * n_freq)
        weights = effective[edge_ids, bins] / 2
        np.add.at(mass, a, weights)
        np.add.at(mass, b, weights)
        active = mass > 0
        if layer_adjacency == "consecutive":
            shared_bin, shared_node = np.where(
                active.reshape(n_freq, n_nodes)[:-1] & active.reshape(n_freq, n_nodes)[1:])
            lower = shared_bin * n_nodes + shared_node
        else:
            lower = np.array([], dtype=int)
        rows = np.concatenate((a, lower))
        cols = np.concatenate((b, lower + n_nodes))
        adjacency = coo_matrix((np.ones(len(rows)), (rows, cols)),
                               shape=(len(active), len(active))).tocsr()
        active_ids = np.flatnonzero(active)
        count, labels = connected_components(adjacency[active_ids][:, active_ids], directed=False)
        if inference_mode == "classic":
            # Both endpoints have the same component label. Count each retained edge once.
            edge_labels = labels[np.searchsorted(active_ids, a)]
            edge_counts = np.bincount(edge_labels, minlength=count)
            intensity = np.bincount(edge_labels, weights=effective[edge_ids, bins] - threshold,
                                    minlength=count)
        for label in range(count):
            ids = active_ids[labels == label]
            nodes = ids % n_nodes + 1
            freqs = ids // n_nodes + 1
            extent = int(len(ids))
            cluster_mass = float(mass[ids].sum())
            if not np.isfinite(cluster_mass):
                raise ValueError("Cluster mass overflowed; check statistic scaling.")
            cluster = {
                "id": len(result) + 1, "tail": sign,
                "nodes": np.unique(nodes).tolist(), "freq_bins": np.unique(freqs).tolist(),
                "layer_bins": np.unique(freqs).tolist(),
                "sites": np.column_stack((nodes, freqs)).tolist(),
                "n_nodes": int(len(np.unique(nodes))), "n_frequencies": int(len(np.unique(freqs))),
                "n_layers": int(len(np.unique(freqs))),
                "extent": extent, "mass": cluster_mass,
            }
            if inference_mode == "classic":
                cluster["extent"] = int(edge_counts[label])
                cluster["intensity"] = float(intensity[label])
            cluster["test_stat"] = cluster[metric]
            result.append(cluster)
    return result


def _divide_statistic(effect, variance, zero=None):
    """Constant null features yield zero; constant nonzero effects are invalid."""
    if zero is None:
        zero = variance == 0
    if np.any(zero & (effect != 0)):
        raise ValueError("A nonzero effect has zero error variance; remove or inspect degenerate features.")
    stat = np.divide(effect, np.sqrt(variance), out=np.zeros_like(effect), where=~zero)
    if not np.all(np.isfinite(stat)):
        raise ValueError("Statistics overflowed; check scaling and degenerate features.")
    return stat


def _welch(y, group, first, second):
    a, b = y[group == first], y[group == second]
    return _divide_statistic(a.mean(axis=0) - b.mean(axis=0),
                            a.var(axis=0, ddof=1) / len(a) + b.var(axis=0, ddof=1) / len(b))


def _paired(differences):
    return _divide_statistic(differences.mean(axis=0),
                            differences.var(axis=0, ddof=1) / len(differences))


def _edge_means(observations):
    return observations.mean(axis=0)


def _glm_fitter(x, c, stat_type):
    inverse = np.linalg.pinv(x)
    contrast_fit = c @ inverse
    covariance = contrast_fit @ contrast_fit.T
    df = len(x) - x.shape[1]
    middle = np.linalg.inv(covariance)

    def fit(y):
        beta = inverse @ y
        residual = y - x @ beta
        residual_ss = np.sum(residual ** 2, axis=0)
        # Exact fits can leave rounding residuals; compare norms at data scale.
        tolerance = 64 * np.finfo(float).eps * np.maximum(np.linalg.norm(y, axis=0), np.finfo(float).tiny)
        zero = np.sqrt(residual_ss) <= tolerance
        cb = c @ beta
        effect_tolerance = tolerance * np.linalg.norm(contrast_fit, axis=1)[:, None]
        if np.any(zero & np.any(np.abs(cb) > effect_tolerance, axis=0)):
            raise ValueError("A nonzero GLM contrast has zero residual variance; inspect degenerate features.")
        if stat_type == "t":
            effect = cb[0].copy()
            effect[zero] = 0
            return _divide_statistic(effect, residual_ss / df * covariance[0, 0], zero)
        numerator = np.einsum("iv,ij,jv->v", cb, middle, cb) / len(c)
        statistic = np.divide(numerator, residual_ss / df,
                              out=np.zeros_like(numerator), where=~zero)
        if not np.all(np.isfinite(statistic)):
            raise ValueError("GLM statistics overflowed; check data scaling.")
        return np.maximum(statistic, 0)

    return fit, contrast_fit.T


def analyze(W, group=None, X=None, C=None, stat_type="t", test="two-sample",
            threshold=3.0, tail="right", metric="extent", n_perm=1000, seed=1,
            exchange_blocks=None, method="auto", use_abs=False, progress=None,
            layer_adjacency="consecutive", inference_mode="multiplex", classic_layer=None):
    """Fit and permute complete networks shaped subjects × nodes × nodes × bins.

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
    retained edges. Intensity sums the excess above the threshold over them.
    Result layer indices address the analyzed slice. config.classic_layer
    records its index in the original data.
    A one-sample design independently flips the sign of each observation's
    complete map. The classic implementation uses the unstandardized edge
    mean as in NBS Connectome v1.2. Multiplex uses the one-sample t statistic.
    The joint distribution of each observation's map must be sign-symmetric
    under the null, with independent observations.
    """
    w = _real_array(W, "W")
    if inference_mode == "classic" and w.ndim == 3:
        w = w[..., None]
    if w.ndim != 4 or w.shape[1] != w.shape[2] or w.shape[1] < 2 or w.shape[3] < 1:
        raise ValueError("W must have shape observations × nodes × nodes × layers, with >=2 nodes.")
    _check_cluster_options(threshold, tail, metric, layer_adjacency, inference_mode)
    if inference_mode == "classic":
        if classic_layer is None and w.shape[3] > 1:
            raise ValueError("Choose one classic_layer (1-based) for classic NBS on a stack.")
        classic_layer = _positive_integer(1 if classic_layer is None else classic_layer, "classic_layer")
        if classic_layer > w.shape[3]:
            raise ValueError("classic_layer exceeds the number of input layers.")
        w = w[..., classic_layer - 1:classic_layer]
        layer_adjacency = "independent"
    elif classic_layer is not None:
        raise ValueError("classic_layer is available only in classic mode.")
    n_subjects, n_nodes, _, n_freq = w.shape
    if n_subjects < 2:
        raise ValueError("At least two observations are required.")
    if not np.allclose(w, w.swapaxes(1, 2), rtol=1e-7, atol=1e-10):
        raise ValueError("W must be symmetric; directed networks are not supported.")
    n_perm = _positive_integer(n_perm, "n_perm")
    seed = None if seed is None else _positive_integer(seed, "seed", 0)
    if not isinstance(use_abs, (bool, np.bool_)):
        raise ValueError("use_abs must be a boolean.")
    stat_type = str(stat_type).lower()
    if stat_type not in ("t", "f") and not (
            stat_type == "mean" and test == "one-sample" and inference_mode == "classic"):
        raise ValueError("stat_type must be 't' or 'F'.")
    if method not in ("auto", "rowshuffle", "freedman-lane", "label-shuffle", "sign-flip"):
        raise ValueError("Unknown permutation method.")
    if test not in ("two-sample", "one-sample", "paired", "glm"):
        raise ValueError("test must be 'two-sample', 'one-sample', 'paired', or 'glm'.")
    # Match MATLAB find(triu(...)): column-major ordering of upper-triangle edges.
    j, i = np.tril_indices(n_nodes, -1)
    edges = np.column_stack((i, j))
    y = w[:, i, j, :].reshape(n_subjects, -1)
    if use_abs:
        y = np.abs(y)
    rng = np.random.default_rng(seed)
    blocks = None if exchange_blocks is None else _labels(exchange_blocks, n_subjects, "exchange_blocks")
    block_indices = [np.arange(n_subjects)] if blocks is None else [np.flatnonzero(blocks == b) for b in np.unique(blocks)]

    def permutation():
        indices = np.arange(n_subjects)
        for positions in block_indices:
            indices[positions] = rng.permutation(positions)
        return indices

    metadata = {"group_values": None, "pair_indices": None, "X": None, "C": None}
    if test == "one-sample":
        if X is not None or C is not None or group is not None:
            raise ValueError("A one-sample test uses observations without groups, design or contrast.")
        if use_abs or blocks is not None:
            raise ValueError("One-sample sign flips require signed observations and independent subjects without exchange blocks.")
        if method not in ("auto", "sign-flip") or stat_type == "f":
            raise ValueError("The one-sample test uses observation-wise sign flips.")
        stat_type = "mean" if inference_mode == "classic" else "t"
        score = _edge_means if stat_type == "mean" else _paired
        resolved = "sign-flip"
        observed = score(y)

        def permuted_statistic():
            signs = rng.choice([-1, 1], size=(n_subjects, 1))
            return score(y * signs)
    elif X is not None or C is not None or test == "glm":
        if X is None or C is None:
            raise ValueError("GLM analysis requires both X and C.")
        if group is not None:
            raise ValueError("Supply either group labels or a GLM design, not both.")
        test = "glm"
        x = _real_array(X, "X")
        c = _real_array(C, "C")
        if c.ndim == 1:
            c = c[None, :]
        if x.ndim != 2 or x.shape[0] != n_subjects or not 0 < x.shape[1] < n_subjects:
            raise ValueError("X must have one row per observation and 1..S-1 columns.")
        if np.linalg.matrix_rank(x) != x.shape[1]:
            raise ValueError("X must have full column rank; remove redundant regressors.")
        if c.ndim != 2 or c.shape[1] != x.shape[1] or c.shape[0] < 1:
            raise ValueError("C must have one column per design regressor.")
        if np.linalg.matrix_rank(c) != c.shape[0]:
            raise ValueError("C must contain nonzero, linearly independent contrast rows.")
        if stat_type == "t" and len(c) != 1:
            raise ValueError("A t-test requires exactly one contrast row.")
        if stat_type == "f" and tail != "right":
            raise ValueError("F statistics require tail='right'.")
        resolved = "freedman-lane" if method == "auto" else method
        if resolved not in ("rowshuffle", "freedman-lane"):
            raise ValueError("GLMs support 'auto', 'freedman-lane', or 'rowshuffle'.")
        fit, weights = _glm_fitter(x, c, stat_type)
        weight_scale = max(float(np.max(np.abs(weights))), np.finfo(float).tiny)
        if not any(np.max(np.ptp(weights[idx], axis=0)) > 1e-12 * weight_scale for idx in block_indices):
            raise ValueError("The tested contrast cannot vary under the permitted row shuffles. Use paired sign flips for paired differences.")
        observed = fit(y)
        if resolved == "freedman-lane":
            reduced = x @ null_space(c)
            fitted_null = reduced @ np.linalg.pinv(reduced) @ y if reduced.shape[1] else np.zeros_like(y)
            residual_null = y - fitted_null

            def permuted_statistic():
                return fit(fitted_null + residual_null[permutation()])
        else:
            # Permuting Y by inverse(P) is algebraically the same as fitting P X.
            def permuted_statistic():
                return fit(y[np.argsort(permutation())])
        metadata.update(X=x.tolist(), C=c.tolist())
    else:
        if stat_type != "t":
            raise ValueError("Group and paired tests use t statistics; supply X and C for an F-test.")
        if group is None:
            raise ValueError("group labels are required for independent or paired tests.")
        labels = _labels(group, n_subjects, "group")
        values = np.unique(labels)
        if test == "two-sample":
            if len(values) != 2 or any(np.sum(labels == v) < 2 for v in values):
                raise ValueError("Two-sample tests need exactly two groups with at least two observations each.")
            if method not in ("auto", "label-shuffle"):
                raise ValueError("Two-sample tests use 'auto' or 'label-shuffle'.")
            if not any(len(np.unique(labels[idx])) > 1 for idx in block_indices):
                raise ValueError("No group labels can exchange within the specified blocks.")
            resolved = "label-shuffle"
            observed = _welch(y, labels, *values)

            def permuted_statistic():
                return _welch(y, labels[permutation()], *values)
            metadata["group_values"] = values.tolist()
        else:
            if method not in ("auto", "sign-flip"):
                raise ValueError("Paired tests use 'auto' or 'sign-flip'.")
            if blocks is not None:
                raise ValueError("Paired tests already use pair IDs; additional exchange_blocks are not supported.")
            pairs = [np.flatnonzero(labels == v) for v in values]
            if len(pairs) < 2 or any(len(pair) != 2 for pair in pairs):
                raise ValueError("Paired tests need at least two pair IDs, each appearing exactly twice.")
            pairs = np.asarray(pairs)
            differences = y[pairs[:, 0]] - y[pairs[:, 1]]
            resolved = "sign-flip"
            observed = _paired(differences)

            def permuted_statistic():
                return _paired(differences * rng.choice([-1, 1], size=(len(pairs), 1)))
            metadata["pair_indices"] = (pairs + 1).tolist()

    def cluster(statistic):
        return _clusters(statistic.reshape(len(edges), n_freq), edges, n_nodes, float(threshold),
                         tail, metric, layer_adjacency, inference_mode)

    clusters = cluster(observed)
    null_max = np.zeros(n_perm)
    if progress:
        progress(0, n_perm)
    for p in range(n_perm):
        permuted_clusters = cluster(permuted_statistic())
        null_max[p] = max((c["test_stat"] for c in permuted_clusters), default=0)
        if progress:
            progress(p + 1, n_perm)
    for c in clusters:
        c["p_fwe"] = float((1 + np.count_nonzero(null_max >= c["test_stat"])) / (n_perm + 1))
    return {
        "clusters": clusters, "statistic": observed.reshape(len(edges), n_freq).tolist(),
        "edges": (edges + 1).tolist(), "null_max": null_max.tolist(),
        "dimensions": {"n_subjects": n_subjects, "n_nodes": n_nodes,
                       "n_frequencies": n_freq, "n_layers": n_freq, "n_edges": len(edges)},
        "config": {"test": test, "stat_type": stat_type, "threshold": float(threshold),
                   "tail": tail, "metric": metric, "n_perm": n_perm, "seed": seed,
                   "method": resolved, "use_abs": bool(use_abs),
                   "layer_adjacency": layer_adjacency, "inference_mode": inference_mode,
                   "classic_layer": classic_layer,
                   "exchange_blocks": None if blocks is None else blocks.tolist(),
                   "p_value_rule": "(1 + count(null_max >= observed)) / (n_perm + 1)",
                   "tail_correction": "joint maximum over signs" if tail == "both" else "single specified tail",
                   "index_base": 1, **metadata},
    }
