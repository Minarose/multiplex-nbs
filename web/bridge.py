"""Bridge between the browser page and the Multiplex-NBS engine. It runs inside Pyodide.

Each function takes one JSON string and returns one JSON string, so the page never handles
Python objects. Problems with the data or the settings come back as {"error": message};
anything else raises and is reported as an unexpected error.

Uploaded files are written by the page into the in-memory file system of this browser tab
(under /uploads) and read from there. Nothing is sent anywhere.
"""
import csv
import io
import json
import re
import sys
import time
from pathlib import PurePosixPath

import numpy as np
import scipy

from multiplex_nbs import __build__, __version__
from multiplex_nbs import io as mio
from multiplex_nbs.demo import make_brain_demo

_state = {"data": None, "name": None, "result": None}

DEMO_NAMES = {
    "brain-network": "Structural brain network · simulated study",
    "two-sample": "Simulated two-sample study",
    "paired": "Simulated paired study",
    "glm": "Simulated GLM study",
}


def _dump(value):
    return json.dumps(value, allow_nan=False, ensure_ascii=False)


def _api(function):
    def wrapper(argument="null"):
        try:
            value = function(json.loads(argument))
        except ValueError as exc:
            value = {"error": str(exc)}
        return _dump(value)
    wrapper.__name__ = function.__name__
    wrapper.__doc__ = function.__doc__
    return wrapper


def _data():
    if _state["data"] is None:
        raise ValueError("Open a dataset first.")
    return _state["data"]


def _loaded(data, name):
    _state.update(data=data, name=name, result=None)
    return {"name": name, "description": mio.describe(data)}


@_api
def versions(_):
    return {"multiplex_nbs": __version__, "build": __build__, "python": sys.version.split()[0],
            "numpy": np.__version__, "scipy": scipy.__version__}


@_api
def open_demo(args):
    kind = args.get("kind")
    if kind == "brain-network":
        data = mio.validate_dataset(make_brain_demo())
    elif kind in ("two-sample", "paired", "glm"):
        data = mio.validate_dataset(mio.make_demo(kind))
        data["demo_info"] = {"title": f"Simulated {kind} study",
                             "simulation_note": "All measurements, observations and effects are simulated."}
    else:
        raise ValueError("Unknown demo dataset.")
    return _loaded(data, DEMO_NAMES[kind])


@_api
def open_file(args):
    """One combined .npz or MATLAB v7 .mat file."""
    name = str(args["name"])
    data = mio.load_dataset(args["path"], suffix=PurePosixPath(name).suffix)
    return _loaded(data, name)


@_api
def open_archives(args):
    """One ZIP per group, each holding one file per participant."""
    groups = [(str(group["label"]).strip(), group["path"]) for group in args["groups"]]
    data = mio.build_dataset(groups, args.get("variable") or None, axis=args.get("axis") or {})
    return _loaded(data, " + ".join(label for label, _ in groups))


# ----- dataset editors (the desktop app's Data page dialogs) ------------------------------
def _matrix(source, field):
    """Read a headerless numeric matrix. Semicolons or newlines separate rows."""
    try:
        rows = []
        for line in re.split(r"[;\n]", source):
            if line.strip():
                cells = re.split(r"[,\t]", line.strip()) if "," in line or "\t" in line else line.split()
                rows.append([float(value) for value in cells])
        matrix = np.asarray(rows, dtype=float)
        if matrix.ndim != 2 or not np.isfinite(matrix).all():
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"{field} needs a rectangular table of finite numbers. Separate rows with semicolons "
                         "or import a headerless text table.") from exc
    return matrix


def _labels_text(labels):
    output = io.StringIO()
    csv.writer(output, lineterminator="").writerow([str(label) for label in np.asarray(labels).ravel()])
    return output.getvalue()


def _label_vector(text):
    """Allow quoted labels, with one CSV row or one label per source row."""
    values = []
    delimiter = "\t" if "\t" in text and "," not in text else ","
    try:
        for row in csv.reader(io.StringIO(text), delimiter=delimiter, strict=True):
            values.extend(item.strip() for item in row)
    except csv.Error as exc:
        raise ValueError("Check the comma-separated labels and paired quotation marks.") from exc
    return values


def _matrix_text(value):
    return "; ".join(", ".join(str(float(v)) for v in row) for row in np.atleast_2d(value))


def _edited(candidate):
    data = _data()
    clean = mio.validate_dataset(candidate)
    if "demo_info" in data:
        clean["demo_info"] = data["demo_info"]
    _state.update(data=clean, result=None)
    return {"name": _state["name"], "description": mio.describe(clean)}


@_api
def dataset_fields(_):
    """Current values for the editors, as text."""
    data = _data()
    axis = mio.axis_metadata(data)
    count = data["W"].shape[0]
    rows = [[index + 1] + [str(data[key][index]) if key in data else "—"
                           for key in ("observation_ids", "group", "exchange_blocks")] for index in range(count)]
    return {"group": _labels_text(data["group"]) if "group" in data else "",
            "blocks": _labels_text(data["exchange_blocks"]) if "exchange_blocks" in data else "",
            "X": _matrix_text(data["X"]) if "X" in data else "", "C": _matrix_text(data["C"]) if "C" in data else "",
            "stat": str(data.get("stat_type", "t")).upper(),
            "axis_name": axis["name"], "axis_unit": axis["unit"], "adjacency": axis["adjacency"],
            "axis_values": ", ".join(f"{v:g}" for v in axis["values"]), "observations": rows}


@_api
def labels_from_table(args):
    return {"text": _labels_text(_label_vector(str(args["text"]).strip()))}


@_api
def edit_groups(args):
    data = _data()
    candidate = data.copy()
    for key, value in (("group", args.get("group", "")), ("exchange_blocks", args.get("blocks", ""))):
        value = str(value).strip()
        if not value:
            candidate.pop(key, None)
        elif key not in data or value != _labels_text(data[key]):
            labels = _label_vector(value)
            # Preserve numeric sorting for an existing numeric group contrast.
            if key in data and np.asarray(data[key]).dtype.kind in "iuf":
                try:
                    labels = [float(label) for label in labels]
                except ValueError:
                    pass
            candidate[key] = labels
    return _edited(candidate)


@_api
def edit_glm(args):
    candidate = _data().copy()
    x, c = str(args.get("X", "")).strip(), str(args.get("C", "")).strip()
    if x or c:
        candidate.update(X=_matrix(x, "X"), C=_matrix(c, "C"), stat_type=str(args.get("stat", "t")).lower())
    else:
        for key in ("X", "C", "stat_type"):
            candidate.pop(key, None)
    return _edited(candidate)


@_api
def edit_axis(args):
    candidate = _data().copy()
    numeric = _matrix(str(args.get("values", "")), "Layer values")
    if min(numeric.shape) != 1:
        raise ValueError("Enter one ordered vector of layer values.")
    candidate["axis_values"] = candidate["frequencies"] = numeric.ravel()
    mio.update_axis(candidate, {"name": args.get("name", ""), "unit": args.get("unit", ""),
                                "adjacency": args.get("adjacency", "consecutive")})
    return _edited(candidate)


@_api
def save_dataset(_):
    data = _data()
    path = "/tmp/multiplex-nbs-dataset.npz"
    with open(path, "wb") as handle:
        handle.write(mio.dataset_npz(data))
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", str(_state["name"] or "dataset"))
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-") or "dataset"
    return {"path": path, "filename": f"{stem}.npz", "mime": "application/octet-stream"}


@_api
def set_coordinates(args):
    data = _data()
    with open(args["path"], "rb") as handle:
        raw = handle.read()
    candidate = data.copy()
    mio.set_coordinates(candidate, raw, str(args["name"]), args.get("units", "mm"), args.get("space") or "MNI")
    return _edited(candidate)


def run(argument, progress=None):
    """Run the analysis. progress(done, total) is called at most every 0.1 s."""
    try:
        data = _data()
        config = json.loads(argument)
        last = [0.0]

        def report(done, total):
            now = time.monotonic()
            if progress is not None and (done in (0, total) or now - last[0] >= .1):
                last[0] = now
                progress(done, total)
        start = time.monotonic()
        result = mio.run_dataset(data, config, report)
        result["dataset_name"] = _state["name"]
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)
        result["software"]["interface"] = "browser (Pyodide)"
        _state["result"] = result
        value = result
    except ValueError as exc:
        value = {"error": str(exc)}
    return _dump(value)


@_api
def set_alpha(args):
    result = _state["result"]
    if result is None:
        raise ValueError("Run an analysis first.")
    result["reporting"]["alpha"] = mio.validate_alpha(args.get("alpha"))
    mio.refresh_report(result)
    return {key: result[key] for key in ("reporting", "interpretation", "methods")}


EXPORTS = {
    "txt": ("report", mio.result_text, "text/plain"),
    "csv": ("components", mio.result_csv, "text/csv"),
    "json": ("results", lambda r: _dump(r).encode("utf-8"), "application/json"),
    "mat": ("results", mio.result_mat, "application/octet-stream"),
}


@_api
def export(args):
    result = _state["result"]
    if result is None:
        raise ValueError("Run an analysis first.")
    kind = args.get("kind")
    if kind not in EXPORTS:
        raise ValueError("Unknown export format.")
    label, encode, mime = EXPORTS[kind]
    path = f"/tmp/multiplex-nbs-export.{kind}"
    with open(path, "wb") as handle:
        handle.write(encode(result))
    stem = re.sub(r"[^A-Za-z0-9]+", "-", str(result.get("dataset_name") or "analysis")).strip("-").lower()[:48]
    return {"path": path, "filename": f"multiplex-nbs-{label}-{stem or 'analysis'}.{kind}", "mime": mime}
