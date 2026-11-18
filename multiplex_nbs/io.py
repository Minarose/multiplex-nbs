"""Safe NPZ/MAT interchange, axis metadata, and researcher-facing reports."""
import csv
import io
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

import numpy as np
from scipy.io import loadmat, savemat
from scipy.io.matlab import MatReadError


def make_demo(kind="two-sample", seed=7):
    """A synthetic chain on nodes 1–4, bins 3–5; not empirical connectivity."""
    if kind not in {"two-sample", "paired", "glm"}:
        raise ValueError("Unknown demo design.")
    rng = np.random.default_rng(seed)
    s, n, f = 40, 12, 8
    a = rng.normal(0, 0.7, (s, n, n, f))
    w = (a + a.transpose(0, 2, 1, 3)) / np.sqrt(2)
    w[:, np.arange(n), np.arange(n), :] = 0
    group = np.repeat([0, 1], s // 2)
    out = {"W": w, "group": group, "frequencies": np.arange(4, 20, 2),
           "axis_name": "Frequency", "axis_unit": "Hz",
           "node_labels": np.array([f"Node {i + 1:02d}" for i in range(n)])}
    effect = (group == 0).astype(float) * 1.2
    if kind == "paired":
        out["group"] = np.tile(np.arange(s // 2), 2)
        w[s // 2:] = w[:s // 2] + rng.normal(0, 0.45, w[:s // 2].shape)
        w[s // 2:] = (w[s // 2:] + w[s // 2:].transpose(0, 2, 1, 3)) / 2
        w[:, np.arange(n), np.arange(n), :] = 0
    if kind == "glm":
        covariate = rng.normal(size=s)
        out["X"] = np.column_stack([np.ones(s), group, covariate])
        out["C"] = np.array([0., -1., 0.])
        w += covariate[:, None, None, None] * 0.2
        w[:, np.arange(n), np.arange(n), :] = 0
    for i, j in [(0, 1), (1, 2), (2, 3)]:
        w[:, i, j, 2:5] += effect[:, None]
        w[:, j, i, 2:5] = w[:, i, j, 2:5]
    return out


def _numeric(value, name):
    raw = np.asarray(value)
    if not np.issubdtype(raw.dtype, np.number) or not np.isrealobj(raw):
        raise ValueError(f"{name} must contain real numbers.")
    if not np.isfinite(raw).all():
        raise ValueError(f"{name} contains missing or infinite values.")
    return raw.astype(float)


def _labels(value, count, name, text=False):
    """Normalize NumPy vectors, MATLAB cell strings, and MATLAB char rows."""
    raw = np.asarray(value)
    if raw.dtype.kind in "US" and raw.ndim == 2 and raw.shape[0] == count and raw.size != count:
        labels = ["".join(row.astype(str)).strip() for row in raw]
    elif raw.size == count:
        labels = []
        for item in raw.ravel(order="F"):
            item = np.asarray(item)
            if item.dtype.kind in "US":
                labels.append("".join(item.ravel().astype(str)).strip())
            elif item.size == 1 and item.dtype.kind in "biuf" and np.isfinite(item).all():
                labels.append(item.item())
            else:
                raise ValueError(f"{name} must contain simple numeric or text labels.")
    else:
        raise ValueError(f"{name} must contain exactly {count} labels.")
    if any(isinstance(label, str) and not label for label in labels):
        raise ValueError(f"{name} cannot contain empty labels.")
    return np.asarray(labels, dtype=str if text else None)


def _text(value, name, limit=80, allow_empty=False):
    raw = np.asarray(value)
    if raw.dtype.kind not in "US":
        raise ValueError(f"{name} must be text.")
    text = "".join(raw.ravel().astype(str)).strip()
    if (not text and not allow_empty) or len(text) > limit or any(ord(c) < 32 for c in text):
        raise ValueError(f"{name} must contain {'0' if allow_empty else '1'}–{limit} printable characters.")
    return text


def axis_metadata(data):
    """Describe the layer axis without assigning physical meaning to its spacing."""
    count = data["W"].shape[3]
    values = _numeric(data.get("axis_values", data.get("frequencies", np.arange(1, count + 1))), "axis_values").ravel()
    if len(values) != count or np.any(np.diff(values) <= 0):
        raise ValueError("axis_values must contain one finite, strictly increasing value per layer.")
    default_name = "Frequency" if "frequencies" in data and "axis_values" not in data else "Layer"
    name = _text(data.get("axis_name", default_name), "axis_name", 60)
    unit = _text(data.get("axis_unit", ""), "axis_unit", 20, allow_empty=True)
    adjacency = _text(data.get("layer_adjacency", "consecutive"), "layer_adjacency")
    if adjacency not in {"consecutive", "independent"}:
        raise ValueError("layer_adjacency must be 'consecutive' or 'independent'.")
    return {"name": name, "unit": unit, "values": values.tolist(), "adjacency": adjacency}


def update_axis(data, settings):
    """Set display labels and graph topology; numeric values stay unchanged."""
    if not isinstance(settings, dict) or set(settings) - {"name", "unit", "adjacency"}:
        raise ValueError("Axis settings accept name, unit and adjacency only.")
    candidate = data.copy()
    for key, value in settings.items():
        candidate[{"name": "axis_name", "unit": "axis_unit", "adjacency": "layer_adjacency"}[key]] = value
    axis = axis_metadata(candidate)
    data.update(axis_name=axis["name"], axis_unit=axis["unit"], layer_adjacency=axis["adjacency"])
    return axis


def load_dataset(source, suffix=None, max_uncompressed_bytes=512 * 1024 * 1024):
    """NPZ W: S,N,N,F or S,N,N. MAT W: cell of N,N,F or numeric N,N,F,S or N,N,S.

    MAT files may instead use `connectivity` with Python's S,N,N,F layout.
    Optional fields: group, X, C, stat_type, exchange_blocks, axis_values,
    axis_name, axis_unit, layer_adjacency, node_labels, node_coordinates.
    `frequencies` is a legacy alias for axis_values. MATLAB model.X/model.C/model.statType, nodeLabels and
    exchangeBlocks are also accepted. Use one design representation per file.
    MAT v7.3 (HDF5) is not supported; save with MATLAB '-v7'.
    NPZ expanded size is limited to 512 MiB by default. API callers processing
    trusted larger files may explicitly increase max_uncompressed_bytes.
    """
    suffix = (suffix or Path(source).suffix).lower()
    try:
        if suffix == ".npz":
            with zipfile.ZipFile(source) as archive:
                sizes = [item.file_size for item in archive.infolist()]
                if max_uncompressed_bytes is not None and sum(sizes) > max_uncompressed_bytes:
                    raise ValueError("Expanded NPZ exceeds the 512 MiB import limit; use the API with an explicit larger limit for trusted data.")
            if hasattr(source, "seek"):
                source.seek(0)
            with np.load(source, allow_pickle=False) as raw:
                data = {k: raw[k] for k in raw.files}
        elif suffix == ".mat":
            data = loadmat(source, squeeze_me=False, struct_as_record=False)
            if "model" in data:
                if "X" in data or "C" in data:
                    raise ValueError("Supply either model or top-level X/C arrays, not both.")
                model = data["model"]
                if model.size != 1 or not all(hasattr(model.item(), key) for key in ("X", "C", "statType")):
                    raise ValueError("model must be one MATLAB struct containing X, C and statType.")
                model = model.item()
                data.update(X=model.X, C=model.C, stat_type=model.statType)
            if "W" in data:
                w = data["W"]
                if w.dtype == object:
                    if w.size == 0:
                        raise ValueError("W cannot be an empty MATLAB cell array.")
                    cells = [_numeric(v, "W cell") for v in w.ravel(order="F")]
                    data["W"] = np.stack([v[..., None] if v.ndim == 2 else v for v in cells])
                else:
                    if w.ndim not in (3, 4):
                        raise ValueError("Numeric MATLAB W must have layout N × N × observations or N × N × layers × observations.")
                    data["W"] = np.moveaxis(w, -1, 0)
        else:
            raise ValueError("Choose a .npz or MATLAB .mat (v7) file.")
    except NotImplementedError as exc:
        raise ValueError("MAT v7.3 is not supported. In MATLAB save the input with '-v7'.") from exc
    except (OSError, EOFError, TypeError, IndexError, MatReadError, zipfile.BadZipFile) as exc:
        raise ValueError("Unable to read this file as NPZ or MATLAB v7 data; check the file format.") from exc
    return validate_dataset(data)


def validate_dataset(data):
    """Check and normalize an input dictionary (see load_dataset for the fields)."""
    if "W" not in data and "connectivity" in data:
        data["W"] = data["connectivity"]
    if "W" not in data:
        raise ValueError("The file needs a W array (see the input format guide).")
    w = np.asarray(data["W"])
    if w.ndim == 3:
        w = w[..., None]
    if w.ndim != 4 or w.shape[1] != w.shape[2] or min(w.shape) < 1 or w.shape[1] < 2:
        raise ValueError("Connectivity must have shape observations × nodes × nodes × layers.")
    if not np.issubdtype(w.dtype, np.number) or not np.isrealobj(w):
        raise ValueError("Connectivity must contain real numbers.")
    if not np.isfinite(w).all():
        raise ValueError("Connectivity contains missing or infinite values. Resolve them before analysis.")
    if not np.allclose(w, w.transpose(0, 2, 1, 3), rtol=1e-7, atol=1e-10):
        raise ValueError("Connectivity matrices must be symmetric (undirected networks).")
    clean = {"W": w.astype(float)}
    if "exchange_blocks" not in data and "exchangeBlocks" in data:
        data["exchange_blocks"] = data["exchangeBlocks"]
    for key in ["group", "exchange_blocks"]:
        if key in data:
            clean[key] = _labels(data[key], w.shape[0], key)
    if ("X" in data) != ("C" in data):
        raise ValueError("A GLM input must contain both X and C.")
    if "X" in data:
        x, c = _numeric(data["X"], "X"), _numeric(data["C"], "C")
        if c.ndim == 1 or (c.ndim == 2 and c.shape[1] == 1 and x.ndim == 2 and c.shape[0] == x.shape[1]):
            c = c.reshape(1, -1)
        if x.ndim != 2 or x.shape[0] != w.shape[0] or x.shape[1] < 1:
            raise ValueError("X must have one row per subject and at least one regressor.")
        if c.ndim != 2 or c.shape[1] != x.shape[1] or c.shape[0] < 1:
            raise ValueError("C must have one column per regressor.")
        clean.update(X=x, C=c)
    stat_type = data.get("stat_type", data.get("statType"))
    if stat_type is not None:
        stat_type = str(_labels(stat_type, 1, "stat_type", text=True)[0]).lower()
        if stat_type not in {"t", "f"}:
            raise ValueError("stat_type must be 't' or 'F'.")
        clean["stat_type"] = stat_type
    if "frequencies" in data and "axis_values" in data:
        legacy = _numeric(data["frequencies"], "frequencies").ravel()
        current = _numeric(data["axis_values"], "axis_values").ravel()
        if not np.array_equal(legacy, current):
            raise ValueError("frequencies and axis_values disagree. Supply one axis or matching aliases.")
    axis = axis_metadata(dict(data, W=w))
    clean.update(axis_values=np.array(axis["values"]), frequencies=np.array(axis["values"]),
                 axis_name=axis["name"], axis_unit=axis["unit"], layer_adjacency=axis["adjacency"])
    raw_labels = data.get("node_labels", data.get("nodeLabels"))
    labels = [f"Node {i+1:02d}" for i in range(w.shape[1])]
    if raw_labels is not None:
        labels = _labels(raw_labels, w.shape[1], "node_labels", text=True)
    clean["node_labels"] = np.array(labels)
    if "observation_ids" in data:
        clean["observation_ids"] = _labels(data["observation_ids"], w.shape[0], "observation_ids", text=True)
    if "node_coordinates" in data:
        coordinates = _numeric(data["node_coordinates"], "node_coordinates")
        if coordinates.shape != (w.shape[1], 3):
            raise ValueError("node_coordinates must have shape nodes × 3.")
        clean["node_coordinates"] = coordinates
        clean["coordinate_space"] = _text(data.get("coordinate_space", "Unspecified"), "coordinate_space")
    if "demo_info_json" in data:
        raw = np.asarray(data["demo_info_json"])
        if raw.dtype.kind not in "US":
            raise ValueError("demo_info_json must contain JSON text.")
        encoded = "".join(raw.ravel().astype(str))
        if len(encoded) > 16000:
            raise ValueError("Demo metadata exceeds 16 KB.")
        try:
            info = json.loads(encoded)
            if not isinstance(info, dict):
                raise ValueError("Demo metadata must be an object.")
            json.dumps(info, allow_nan=False)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError("demo_info_json must contain a finite JSON object.") from exc
        clean["demo_info"] = info
    return clean


PARTICIPANT_SUFFIXES = (".mat", ".npy", ".csv", ".tsv", ".txt")


def _natural_key(name):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def _table(text, name):
    """Rows of a delimited text file (comma, tab, semicolon or spaces)."""
    rows = []
    for line in text.splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith(("#", "%")):
            continue
        delimiter = next((d for d in (",", "\t", ";") if d in line), None)
        rows.append([cell.strip().strip('"') for cell in (line.split(delimiter) if delimiter else line.split())])
    if not rows:
        raise ValueError(f"{name} is empty.")
    return rows


def _is_number(text):
    try:
        float(text)
        return True
    except ValueError:
        return False


def _mat_array(raw, name, variable=None):
    try:
        content = loadmat(io.BytesIO(raw), squeeze_me=False)
    except NotImplementedError as exc:
        raise ValueError(f"{name} is MAT v7.3, which is not supported. In MATLAB save it with '-v7'.") from exc
    arrays = {k: v for k, v in content.items() if not k.startswith("__") and isinstance(v, np.ndarray)
              and v.dtype.kind in "biuf"}
    if variable:
        if variable not in arrays:
            raise ValueError(f"{name} has no numeric variable named '{variable}'. It contains: {', '.join(sorted(arrays)) or 'no numeric variables'}.")
        return arrays[variable]
    if len(arrays) != 1:
        raise ValueError(f"{name} contains {len(arrays)} numeric variables ({', '.join(sorted(arrays))}). Enter the variable to use under 'MAT variable'.")
    return next(iter(arrays.values()))


def _participant_matrix(name, raw, variable=None):
    suffix = PurePosixPath(name).suffix.lower()
    try:
        if suffix == ".mat":
            array = _mat_array(raw, name, variable)
        elif suffix == ".npy":
            array = np.load(io.BytesIO(raw), allow_pickle=False)
        else:
            rows = _table(raw.decode("utf-8-sig"), name)
            if not all(_is_number(cell) for cell in rows[0]):
                rows = rows[1:]
            array = np.array([[float(cell) for cell in row] for row in rows])
    except (OSError, EOFError, TypeError, IndexError, MatReadError, UnicodeDecodeError) as exc:
        raise ValueError(f"{name} could not be read; check its format.") from exc
    except ValueError as exc:
        if str(exc).startswith(name):
            raise
        raise ValueError(f"{name} could not be read as a numeric matrix; check its format.") from exc
    array = _numeric(array, name)
    if array.ndim not in (2, 3) or array.shape[0] != array.shape[1]:
        raise ValueError(f"{name} has shape {' × '.join(map(str, array.shape))}; each participant file must be nodes × nodes or nodes × nodes × layers.")
    return array if array.ndim == 3 else array[..., None]


def read_group_archives(groups, variable=None, max_uncompressed_bytes=512 * 1024 * 1024, max_files=5000):
    """Stack one ZIP archive per group into W (participants × nodes × nodes × layers).

    groups is a sequence of (group label, archive) where archive is a path,
    bytes or file object. Each archive holds one file per participant
    (.mat v7, .npy, or delimited text for a single layer). Group membership
    comes only from the archive, never from file names. Within an archive
    participants are ordered by file name (natural order, so 2 precedes 10);
    folders, hidden files and other file types are ignored.
    """
    if len(groups) < 1:
        raise ValueError("Add at least one group archive.")
    labels = [_text(label, "Group name") for label, _ in groups]
    if len(set(labels)) != len(labels):
        raise ValueError("Each group needs a different name.")
    matrices, membership, ids, expanded = [], [], [], 0
    for label, source in groups:
        if isinstance(source, (bytes, bytearray)):
            source = io.BytesIO(source)
        try:
            archive = zipfile.ZipFile(source)
        except (zipfile.BadZipFile, OSError) as exc:
            raise ValueError(f"The {label} archive is not a readable ZIP file.") from exc
        with archive:
            members = [item for item in archive.infolist() if not item.is_dir()
                       and not any(part.startswith((".", "__MACOSX")) for part in PurePosixPath(item.filename).parts)]
            usable = sorted((item for item in members if item.filename.lower().endswith(PARTICIPANT_SUFFIXES)),
                            key=lambda item: _natural_key(item.filename))
            if not usable:
                raise ValueError(f"No participant files (.mat, .npy, .csv, .tsv or .txt) were found in the {label} archive.")
            # Finder's Compress wraps everything in one folder; leave it out of the participant IDs.
            tops = {PurePosixPath(item.filename).parts[0] for item in usable}
            strip = len(tops) == 1 and all(len(PurePosixPath(item.filename).parts) > 1 for item in usable)
            expanded += sum(item.file_size for item in usable)
            if expanded > max_uncompressed_bytes or len(matrices) + len(usable) > max_files:
                raise ValueError("The archives exceed the import limit (512 MiB expanded or 5,000 files). Use the Python API for larger studies.")
            for item in usable:
                matrix = _participant_matrix(item.filename, archive.read(item), variable)
                if matrices and matrix.shape != matrices[0].shape:
                    raise ValueError(f"{label}/{item.filename} is {' × '.join(map(str, matrix.shape))}, but {ids[0]} is {' × '.join(map(str, matrices[0].shape))}. All participant files must have the same dimensions.")
                matrices.append(matrix)
                membership.append(label)
                ids.append(f"{label}/{PurePosixPath(*PurePosixPath(item.filename).parts[strip:])}")
    return {"W": np.stack(matrices), "group": np.array(membership), "observation_ids": np.array(ids)}


def build_dataset(groups, variable=None, axis=None):
    """Assemble and validate a dataset from per-group archives (see read_group_archives).

    axis may hold name, unit, start, step and adjacency; layer values are
    start + step × (0, 1, ...).
    """
    data = read_group_archives(groups, variable)
    axis = axis or {}
    if set(axis) - {"name", "unit", "start", "step", "adjacency"}:
        raise ValueError("Axis settings accept name, unit, start, step and adjacency only.")
    start, step = axis.get("start", 1), axis.get("step", 1)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v) for v in (start, step)) or step <= 0:
        raise ValueError("The first layer value must be a number and the step a positive number.")
    data["axis_values"] = start + step * np.arange(data["W"].shape[3])
    data["axis_name"] = axis.get("name") or "Layer"
    data["axis_unit"] = axis.get("unit") or ""
    data["layer_adjacency"] = axis.get("adjacency") or "consecutive"
    return validate_dataset(data)


def read_coordinates(raw, name, nodes, units="mm"):
    """Read node coordinates (nodes × 3) from text, .npy or .mat.

    Text files may have a header row and a leading label column
    (label, x, y, z). Returns (coordinates in mm, labels or None).
    """
    if units not in {"mm", "cm"}:
        raise ValueError("Coordinate units must be mm or cm.")
    suffix = PurePosixPath(name).suffix.lower()
    labels = None
    try:
        if suffix == ".npy":
            coordinates = np.load(io.BytesIO(raw), allow_pickle=False)
        elif suffix == ".mat":
            coordinates = _mat_array(raw, name)
        elif suffix in {".csv", ".tsv", ".txt"}:
            rows = _table(raw.decode("utf-8-sig"), name)
            if not any(_is_number(cell) for cell in rows[0][-3:]):
                rows = rows[1:]
            if rows and all(len(row) == 4 and not _is_number(row[0]) for row in rows):
                labels = [row[0] for row in rows]
                rows = [row[1:] for row in rows]
            coordinates = np.array([[float(cell) for cell in row] for row in rows])
        else:
            raise ValueError("Choose coordinates as .csv, .tsv, .txt, .npy or .mat.")
    except (OSError, EOFError, TypeError, IndexError, MatReadError, UnicodeDecodeError) as exc:
        raise ValueError("The coordinates file could not be read; check its format.") from exc
    except ValueError as exc:
        if "Choose coordinates" in str(exc) or str(exc).startswith(name):
            raise
        raise ValueError("The coordinates file must contain numbers in three columns (x, y, z), optionally after a label column and a header row.") from exc
    coordinates = _numeric(coordinates, "node coordinates")
    if coordinates.shape != (nodes, 3):
        shape = " × ".join(map(str, coordinates.shape))
        raise ValueError(f"The coordinates file is {shape}; this dataset needs {nodes} rows (one per node, in node order) × 3 columns (x, y, z).")
    if units == "cm":
        coordinates = np.round(coordinates * 10, 6)
    return coordinates, labels


def set_coordinates(data, raw, name, units="mm", space="MNI"):
    space = _text(space, "Coordinate space", 40)
    coordinates, labels = read_coordinates(raw, name, data["W"].shape[1], units)
    data["node_coordinates"] = coordinates
    data["coordinate_space"] = f"{space} (mm)"
    if labels is not None:
        data["node_labels"] = _labels(labels, data["W"].shape[1], "node labels", text=True)


def dataset_npz(data):
    """Serialize a validated dataset for re-use (inverse of load_dataset)."""
    keep = {k: v for k, v in data.items() if k not in {"frequencies", "demo_info"}}
    if "demo_info" in data:
        keep["demo_info_json"] = json.dumps(data["demo_info"], allow_nan=False)
    output = io.BytesIO()
    np.savez_compressed(output, **keep)
    return output.getvalue()


def describe(data):
    s, n, _, f = data["W"].shape
    axis = axis_metadata(data)
    group = data.get("group")
    values, counts = np.unique(group, return_counts=True) if group is not None else (np.array([]), np.array([]))
    designs = {}
    def status(name, issue):
        designs[name] = {"ready": issue is None, "issue": issue}
    issue = None
    if len(values) != 2 or np.any(counts < 2):
        issue = "Independent groups need two group labels with at least two observations each. Include a group vector with one label per observation."
    elif "exchange_blocks" in data and not any(len(np.unique(group[data["exchange_blocks"] == b])) > 1 for b in np.unique(data["exchange_blocks"])):
        issue = "Group labels cannot exchange within the supplied blocks. Review the blocks or use an appropriate model."
    status("two-sample", issue)
    issue = None
    if len(values) < 2 or np.any(counts != 2):
        issue = "Paired analysis needs at least two pair IDs, each appearing exactly twice in group. The first row for each ID is compared with the second."
    elif "exchange_blocks" in data:
        issue = "Pair IDs define paired resampling. Remove the additional exchange_blocks for a paired analysis."
    status("paired", issue)
    issue = None
    if s < 2 or "exchange_blocks" in data:
        issue = "One-sample sign flips require at least two independent observations without exchange blocks."
    status("one-sample", issue)
    issue = None
    if "X" not in data or "C" not in data:
        issue = "A GLM needs a design matrix X and contrast C in the data file."
    else:
        x, c = data["X"], np.atleast_2d(data["C"])
        if not 0 < x.shape[1] < s or np.linalg.matrix_rank(x) != x.shape[1]:
            issue = "The design needs independent columns and fewer regressors than observations. Remove redundant regressors."
        elif np.linalg.matrix_rank(c) != c.shape[0]:
            issue = "The contrast needs nonzero, independent rows. Review C in the input file."
    status("glm-f", issue)
    status("glm-t", issue or ("A t contrast must contain exactly one row. Choose a GLM F test for multiple contrast rows." if np.atleast_2d(data.get("C", [])).shape[0] != 1 else None))
    preferred = "glm-f" if data.get("stat_type") == "f" else "glm-t"
    suggested = next((d for d in (preferred, "two-sample", "paired", "glm-f") if designs[d]["ready"]), None)
    issues = []
    if "X" in data and not designs["glm-f"]["ready"]:
        issues.append("The supplied GLM is not ready: " + designs["glm-f"]["issue"])
    if suggested is None and not designs["one-sample"]["ready"]:
        issues.append("No supported study design is ready. Add group labels or pair IDs below, or include valid X and C arrays in the input file.")
    info = data.get("demo_info")
    if info is None and "demo_info_json" in data:
        info = json.loads(str(np.asarray(data["demo_info_json"]).item()))
    return {"subjects": s, "nodes": n, "frequencies_count": f, "layer_count": f,
            "frequencies": axis["values"], "axis": axis,
            "node_labels": data["node_labels"].tolist(),
            "node_coordinates": data["node_coordinates"].tolist() if "node_coordinates" in data else None,
            "coordinate_space": data.get("coordinate_space"), "demo_info": info,
            "observation_ids": data["observation_ids"].tolist() if "observation_ids" in data else None,
            "groups": None if group is None else np.unique(group).tolist(),
            "has_group": group is not None,
            "has_glm": "X" in data and "C" in data,
            "stat_type": data.get("stat_type"),
            "design_shape": list(data["X"].shape) if "X" in data else None,
            "contrast": data["C"].tolist() if "C" in data else None,
            "has_blocks": "exchange_blocks" in data,
            "group_counts": [{"label": v.item(), "count": int(c)} for v, c in zip(values, counts)],
            "designs": designs, "suggested_design": suggested, "issues": issues}


def run_dataset(data, config, progress=None):
    import sys
    import scipy
    from .core import analyze
    from . import __build__, __version__
    if not isinstance(config, dict):
        raise ValueError("Analysis settings must be a JSON object.")
    config = config.copy()
    allowed = {"design", "threshold", "tail", "metric", "n_perm", "seed", "method",
               "use_abs", "alpha", "layer_adjacency", "inference_mode", "classic_layer"}
    if set(config) - allowed:
        raise ValueError("Unknown analysis setting.")
    alpha = validate_alpha(config.pop("alpha", .05))
    config.setdefault("layer_adjacency", axis_metadata(data)["adjacency"])
    design = config.pop("design", "two-sample")
    if design not in {"two-sample", "one-sample", "paired", "glm-t", "glm-f"}:
        raise ValueError("Unknown analysis design.")
    keys = {k: data[k] for k in ["exchange_blocks"] if k in data}
    if design.startswith("glm"):
        if "X" not in data or "C" not in data:
            raise ValueError("GLM requires X and C arrays in your input file.")
        keys.update(X=data["X"], C=data["C"], stat_type=design[-1])
    elif design == "one-sample":
        keys.update(test=design)
    else:
        if "group" not in data:
            raise ValueError("The selected design requires a group vector in your input file.")
        keys.update(test=design, group=data["group"])
    result = analyze(data["W"], progress=progress, **keys, **config)
    description = describe(data)
    if result["config"]["inference_mode"] == "classic":
        layer = result["config"]["classic_layer"]
        selected_value = description["axis"]["values"][layer - 1]
        description["frequencies_count"] = description["layer_count"] = 1
        description["frequencies"] = description["axis"]["values"] = [selected_value]
    result["dataset"] = description
    result["dataset"]["axis"]["adjacency"] = result["config"]["layer_adjacency"]
    result["software"] = {"name": "multiplex-nbs", "version": __version__, "build": __build__,
                          "python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__}
    result["reporting"] = {"alpha": alpha}
    refresh_report(result)
    return result


def validate_alpha(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or not 0 < value < 1:
        raise ValueError("The significance cutoff (alpha) must be a number between 0 and 1.")
    return float(value)


def refresh_report(result):
    """Update descriptive reporting after changing alpha; never rerun inference."""
    config, dataset = result["config"], result["dataset"]
    axis = dataset["axis"]
    alpha = result.get("reporting", {}).get("alpha", .05)
    significant = [c for c in result["clusters"] if c["p_fwe"] <= alpha]
    count = len(significant)
    headline = f"{count} significant cluster{'s' if count != 1 else ''}" if count else "No significant clusters"
    if config["stat_type"] == "f":
        direction = "An F test assesses the specified joint contrast; it does not assign an increase or decrease."
    elif config["test"] == "two-sample":
        first, second = config["group_values"]
        direction = f"Positive statistics mean group {first} exceeds group {second}; negative statistics mean the reverse."
    elif config["test"] == "paired":
        direction = "Positive statistics mean the first encountered observation for each pair exceeds the second."
    elif config["test"] == "one-sample":
        direction = "Positive statistics indicate an observed mean above zero. Negative statistics indicate a mean below zero."
    else:
        direction = "The sign follows the supplied GLM contrast C; inspect C before assigning a biological direction."
    summary = (f"{count} of {len(result['clusters'])} observed clusters meet corrected p ≤ {alpha:g}. "
               + ("Extent counts retained edges in the selected matrix."
                  if config.get("inference_mode") == "classic" else
                  "Extent counts node–layer sites, so one node in three layers contributes three sites."))
    if not count:
        summary += " This analysis did not detect a cluster at this cutoff."
    caveat = ("Inference applies to each connected cluster as a whole, not to individual edges, nodes, or layers. "
              "Correction covers this configured analysis, not additional thresholds or models explored afterwards.")
    warnings = []
    minimum_p = 1 / (config["n_perm"] + 1)
    if minimum_p > alpha:
        warnings.append(f"With {config['n_perm']} permutations, the smallest possible p is {minimum_p:g}, above alpha {alpha:g}.")
    classic = config.get("inference_mode") == "classic"
    if classic:
        warnings.append(f"Correction covers the prespecified layer {config['classic_layer']} only.")
    elif config["layer_adjacency"] == "consecutive":
        warnings.append("Adjacent array slices are linked regardless of the numerical gap between axis values; spacing is not a distance weight.")
    else:
        warnings.append("Slices are disconnected, but one maximum-cluster null distribution corrects across all slices and selected tails.")
    if dataset.get("demo_info"):
        warnings.append("This demonstration contains simulated observations and effects; its significance is not an empirical brain finding.")
    if config["test"] == "one-sample":
        warnings.append("One-sample sign flips assume independent observations and joint symmetry of the signed network values about zero under the null.")
    result["interpretation"] = {"headline": headline, "summary": summary, "caveat": caveat,
                                "direction": direction, "significant_count": count,
                                "total_clusters": len(result["clusters"]), "minimum_p": minimum_p,
                                "warnings": warnings}
    metric = ("the number of node–layer sites" if config["metric"] == "extent" else
              "raw tail-adjusted statistic mass, split equally between edge endpoints")
    topology = ("Active copies of the same node were joined across consecutive array slices. "
                "Axis spacing did not weight adjacency." if config["layer_adjacency"] == "consecutive" else
                "No links were formed between slices; the correction family included clusters from every slice.")
    if classic:
        value = f"{axis['values'][0]:g} {axis['unit']}".strip()
        topology = f"Classic NBS formed connected components in input layer {config['classic_layer']} ({axis['name']} = {value})."
        metric = ("the number of retained edges" if config["metric"] == "extent" else
                  "the sum of each retained tail-adjusted edge statistic minus the primary threshold")
    statistic = ("mean connectivity in input units" if config["stat_type"] == "mean" else
                 f"{config['stat_type'].upper()} statistics")
    result["methods"] = (
        f"Multiplex-NBS {result['software']['version']} analyzed {dataset['subjects']} observations, "
        f"{dataset['nodes']} nodes and {dataset['layer_count']} layer{'s' if dataset['layer_count'] != 1 else ''} ({axis['name']}"
        f"{', ' + axis['unit'] if axis['unit'] else ''}). "
        f"The design was {config['test']} with {statistic} and {config['method']} resampling. "
        f"The primary threshold was {config['threshold']:g} (strict inequality), tail={config['tail']}. "
        f"Retained edges connected their endpoints within each layer. {topology} "
        f"Cluster {config['metric']} was defined as {metric}. "
        f"For {config['n_perm']} random permutations (seed={config['seed']}), each null value was the largest cluster statistic "
        f"{'within the selected layer' if classic else 'across all layers'}"
        f"{' and both separately formed signs' if config['tail'] == 'both' else ''}. "
        "Corrected p-values used (1 + number of null maxima ≥ observed)/(permutations + 1). "
        f"The reporting cutoff was alpha={alpha:g}. "
        f"Absolute connectivity values were {'used' if config['use_abs'] else 'not used'}. "
        f"Exchangeability blocks were {'supplied' if config['exchange_blocks'] is not None else 'not supplied'}. "
        "Exchangeability/symmetric-difference assumptions must be justified by the study design. "
        "Freedman–Lane inference with nuisance regressors is generally approximate. " + caveat)


def result_text(result):
    """A self-contained plain-text summary and methods draft for researcher review."""
    report = result["interpretation"]
    dataset = result["dataset"]
    axis = dataset["axis"]
    classic = result["config"].get("inference_mode") == "classic"
    score = "intensity" if classic else "mass"
    extent_unit = "edges" if classic else "node–layer sites"
    rows = ["MULTIPLEX-NBS — ANALYSIS REPORT", result.get("dataset_name", "Dataset"), "",
            report["headline"], report["summary"], report["direction"], report["caveat"], "",
            "INTERPRETATION NOTES", *report["warnings"], "", "CLUSTERS (ALL OBSERVED)",
            f"ID | tail | extent ({extent_unit}) | {score} | corrected p | significant | nodes | analyzed layer indices | axis values"]
    alpha = result["reporting"]["alpha"]
    for c in result["clusters"]:
        bins = c["layer_bins"]
        values = ", ".join(f"{axis['values'][b-1]:g}" for b in bins)
        rows.append(f"{c['id']} | {c['tail']} | {c['extent']} | {c[score]:.6g} | {c['p_fwe']:.6g} | "
                    f"{c['p_fwe'] <= alpha} | {', '.join(dataset['node_labels'][n-1] for n in c['nodes'])} | "
                    f"{', '.join(map(str, bins))} | {values} {axis['unit']}")
    if not result["clusters"]:
        rows.append("No edges exceeded the primary threshold; no clusters were formed.")
    if dataset.get("demo_info"):
        rows += ["", "DEMO PROVENANCE", json.dumps(dataset["demo_info"], indent=2, ensure_ascii=False)]
    rows += ["", "METHODS DRAFT — REVIEW BEFORE PUBLICATION", result["methods"], "",
             "REPRODUCIBILITY SETTINGS", json.dumps(result["config"], indent=2, ensure_ascii=False),
             json.dumps(result["software"], indent=2, ensure_ascii=False),
             "", "AXIS VALUES", json.dumps(axis, ensure_ascii=False), "",
             "Retain the original input file and full JSON/MAT export to reproduce this analysis."]
    return ("\n".join(rows) + "\n").encode("utf-8")


def result_csv(result):
    output = io.StringIO()
    writer = csv.writer(output)
    alpha = result.get("reporting", {}).get("alpha", .05)
    writer.writerow(["cluster", "tail", "extent", "mass", "test_stat", "p_fwe", "nodes_1based", "frequency_bins_1based", "alpha", "significant", "layer_bins_1based", "axis_name", "axis_unit", "axis_values", "layer_adjacency", "inference_mode", "metric", "extent_unit", "intensity", "classic_input_layer_1based"])
    config = result["config"]
    mode = config.get("inference_mode", "multiplex")
    axis = result["dataset"]["axis"]
    # Text metadata may come from an imported file. Prevent spreadsheet formula
    # execution when a researcher opens the CSV in Excel or similar software.
    def csv_text(value):
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
    for c in result["clusters"]:
        writer.writerow([c["id"], c["tail"], c["extent"], c["mass"], c["test_stat"], c["p_fwe"],
                         " ".join(map(str, c["nodes"])), " ".join(map(str, c["freq_bins"])), alpha, c["p_fwe"] <= alpha,
                         " ".join(map(str, c["layer_bins"])), csv_text(axis["name"]), csv_text(axis["unit"]),
                         " ".join(f"{axis['values'][i-1]:g}" for i in c["layer_bins"]), axis["adjacency"],
                         mode, config["metric"], "edges" if mode == "classic" else "node-layer sites",
                         c.get("intensity"), config.get("classic_layer")])
    return output.getvalue().encode()


def result_mat(result):
    output = io.BytesIO()
    # Full schema is losslessly available as JSON; arrays also have direct MATLAB fields.
    savemat(output, {"result_json": json.dumps(result, allow_nan=False),
                     "statistic": np.array(result["statistic"]), "edges": np.array(result["edges"]),
                     "null_max": np.array(result["null_max"]),
                     "axis_values": result["dataset"]["axis"]["values"],
                     "axis_name": result["dataset"]["axis"]["name"],
                     "axis_unit": result["dataset"]["axis"]["unit"],
                     "p_fwe": np.array([c["p_fwe"] for c in result["clusters"]])})
    return output.getvalue()
