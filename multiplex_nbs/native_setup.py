"""Native forms for importing connectivity data and configuring NBS inference."""

import csv
import io
import math
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np

from .native_figures import follow_width
from .io import (axis_metadata, build_dataset, dataset_npz, load_dataset,
                 set_coordinates, update_axis, validate_alpha, validate_dataset)


MODES = {"multiplex": "Multiplex-NBS", "layerwise": "Layer-wise NBS", "classic": "Classic NBS"}
MODE_NOTES = {
    "classic": "Tests one layer you choose in advance. A component is a set of connected edges in that layer.",
    "layerwise": "Runs classic NBS in every layer. Components stay within their layer, and one correction covers all layers.",
    "multiplex": "Links a region to itself in neighbouring layers, so a component can span layers. One correction covers all layers.",
}


def _method(config, layers):
    """The method shown to researchers; layer-wise NBS is the multiplex engine with separate layers."""
    if config.get("inference_mode") == "classic":
        return "classic"
    if layers > 1 and config.get("layer_adjacency") == "independent":
        return "layerwise"
    return "multiplex"
DESIGNS = {"two-sample": "Independent groups", "paired": "Paired observations",
           "one-sample": "One sample", "glm-t": "GLM · t contrast", "glm-f": "GLM · F contrast"}
TAILS = {"right": "Positive", "left": "Negative", "both": "Both signs"}
ADJACENCY = {"consecutive": "Connect adjacent layers", "independent": "Keep layers separate"}
RESAMPLING = {"auto": "Automatic", "freedman-lane": "Freedman–Lane residuals",
              "rowshuffle": "Shuffle observation rows"}
DEMOS = {"brain-network": "Brain network over time",
         "two-sample": "Two independent groups", "paired": "Paired conditions",
         "glm": "Groups with a covariate (GLM)"}
DEMO_NOTES = {
    "brain-network": ("32 regions from an open human structural connectome, with MNI coordinates so the brain "
                      "view works. 40 simulated participants in two groups, 8 time windows from 0 to 350 ms. "
                      "Group A is higher along a left sensorimotor–parietal chain at 100–200 ms."),
    "two-sample": ("12 nodes, 40 synthetic participants in two groups of 20, 8 frequency bins from 4 to 18 Hz. "
                   "The first group is higher along a chain of nodes 1–4 at 8–12 Hz."),
    "paired": ("20 synthetic participants measured in two conditions (40 observations), 12 nodes, 8 frequency "
               "bins. The first condition is higher along nodes 1–4 at 8–12 Hz."),
    "glm": ("40 synthetic participants, 12 nodes, 8 frequency bins, with a design matrix (intercept, group, "
            "covariate) and a contrast that tests the group difference adjusted for the covariate."),
}
TABLE_FILES = [("Text tables", ("*.csv", "*.tsv", "*.txt")), ("All files", "*")]
DATA_FILES = [("Connectivity datasets", ("*.npz", "*.mat")), ("All files", "*")]


def _heading(parent, title):
    ttk.Label(parent, text=title, style="Heading.TLabel").pack(anchor="w", pady=(24, 8))


def _note(parent, text):
    label = ttk.Label(parent, text=text, style="Muted.TLabel", wraplength=650, justify="left")
    label.pack(anchor="w", fill="x", pady=(0, 13))
    return follow_width(label, 120, 680)


def _text(parent, text, style="TLabel", limit=760, pady=(0, 10)):
    label = ttk.Label(parent, text=text, style=style, wraplength=520, justify="left")
    label.pack(anchor="w", fill="x", pady=pady)
    return follow_width(label, 160, limit)


def _bar(parent):
    row = ttk.Frame(parent, style=str(parent.cget("style")) or "TFrame")
    row.pack(anchor="w", fill="x", pady=(4, 16))
    # Wrap native buttons at their natural sizes on smaller laptop windows.
    def arrange(event):
        buttons = row.winfo_children()
        stack = sum(widget.winfo_reqwidth() + 12 for widget in buttons) > event.width
        for index, widget in enumerate(buttons):
            widget.grid(row=index if stack else 0, column=0 if stack else index,
                        sticky="w", padx=(0, 12), pady=4)
    row.bind("<Configure>", arrange)
    return row


def _button(row, label, command, primary=False):
    inside_card = str(row.cget("style")) == "Card.TFrame"
    item = ttk.Button(row, text=label, command=command,
                      style="Primary.TButton" if primary else ("Card.TButton" if inside_card else "TButton"))
    item.grid(row=0, column=len(row.winfo_children()) - 1, sticky="w", padx=(0, 12), pady=4)
    return item


def _fields(parent):
    frame = ttk.Frame(parent)
    frame.pack(anchor="w", expand=False, fill="x", pady=(0, 13))
    frame.columnconfigure(1, weight=1)
    return frame


def _field(frame, row, label, widget):
    caption = ttk.Label(frame, text=label)
    caption.grid(row=row, column=0, sticky="w", padx=(0, 26), pady=6)
    widget.grid(row=row, column=1, sticky="ew", pady=6)
    return caption


def _combo(parent, variable, choices):
    values = list(choices)
    # Wide enough for the longest choice, so no option is cut off.
    return ttk.Combobox(parent, textvariable=variable, values=values, state="readonly",
                        width=max([27] + [len(str(value)) + 3 for value in values]))


def _key(mapping, value):
    return next((key for key, label in mapping.items() if label == value), "")


def _dataset_edit(app, candidate):
    # The shared validator accepts demo metadata through its NPZ representation.
    # Already validated in-memory provenance can be retained without re-serializing W.
    clean = validate_dataset(candidate)
    if "demo_info" in candidate:
        clean["demo_info"] = candidate["demo_info"]
    _install_edit(app, clean)


def _install_edit(app, data):
    # Editing node coordinates or labels should not reset a prespecified analysis.
    original_axis = axis_metadata(app.data)
    settings = (app.remember_model() if "model" in getattr(app, "pages", {}) else app.config).copy()
    app.load_data(data, app.name, mode=settings.get("inference_mode"))
    if not settings.get("design"):
        settings.pop("design", None)
    if original_axis["adjacency"] != axis_metadata(data)["adjacency"]:
        settings.pop("layer_adjacency", None)
    app.config.update(settings)


def _dialog(app, title, help_text, rows, apply, submit="Apply"):
    """A local editor. Rows are (label, initial value, options or None, importable)."""
    win = tk.Toplevel(app.root)
    win.withdraw()
    win.title(title)
    win.transient(app.root)
    body = ttk.Frame(win, padding=29)
    body.pack(fill="both", expand=True)
    _heading(body, title)
    _note(body, help_text)
    fields = _fields(body)
    variables = []

    def import_table(var, reader):
        name = filedialog.askopenfilename(parent=win, title="Import text table", filetypes=TABLE_FILES)
        if name:
            try:
                raw = Path(name).read_text(encoding="utf-8-sig").strip()
                var.set(reader(raw) if callable(reader) else "; ".join(raw.splitlines()))
            except (OSError, UnicodeError, ValueError, csv.Error) as exc:
                messagebox.showerror("Could not read table", str(exc), parent=win)

    for index, (label, initial, options, importable) in enumerate(rows):
        var = tk.StringVar(win, value=initial)
        variables.append(var)
        widget = (_combo(fields, var, options) if options else
                  ttk.Entry(fields, width=42, textvariable=var))
        _field(fields, index, label, widget)
        if importable:
            ttk.Button(fields, text="Read file…", command=lambda v=var, r=importable: import_table(v, r)).grid(
                row=index, column=2, padx=(12, 0), pady=6)

    def accept():
        try:
            apply([var.get().strip() for var in variables])
        except (ValueError, OSError, OverflowError) as exc:
            messagebox.showerror(title, str(exc), parent=win)
            return
        win.destroy()

    actions = _bar(body)
    _button(actions, submit, accept, True)
    _button(actions, "Cancel", win.destroy)
    win.bind("<Escape>", lambda _event: win.destroy())
    win.deiconify()
    win.grab_set()
    return win


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
        raise ValueError(f"{field} needs a rectangular table of finite numbers. Separate rows with semicolons or import a headerless text table.") from exc
    return matrix


def _labels_text(labels):
    output = io.StringIO()
    csv.writer(output, lineterminator="").writerow(labels)
    return output.getvalue()


def _label_vector(text):
    """Allow quoted labels, with one CSV row or one label per source row."""
    values = []
    delimiter = "\t" if "\t" in text and "," not in text else ","
    for row in csv.reader(io.StringIO(text), delimiter=delimiter, strict=True):
        values.extend(item.strip() for item in row)
    return values


def _matrix_text(value):
    return "; ".join(", ".join(str(float(v)) for v in row) for row in np.atleast_2d(value))


def _import_dataset(app):
    name = filedialog.askopenfilename(parent=app.root, title="Open connectivity dataset", filetypes=DATA_FILES)
    if name:
        try:
            data = load_dataset(name)
            app.load_data(data, Path(name).name, mode="classic" if data["W"].shape[3] == 1 else "multiplex")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not open dataset", str(exc), parent=app.root)


def _archives(app):
    paths = filedialog.askopenfilenames(parent=app.root, title="Choose one ZIP per group",
                                        filetypes=[("Group archives", "*.zip")])
    if not paths:
        return
    rows = [(Path(path).name, Path(path).stem, None, False) for path in paths]
    rows += [("MAT variable (optional)", "", None, False), ("Axis name", "Layer", None, False),
             ("Axis unit (optional)", "", None, False), ("First value", "1", None, False),
             ("Step between layers", "1", None, False)]

    def build(values):
        labels = values[:len(paths)]
        variable, axis_name, unit, start, step = values[len(paths):]
        data = build_dataset(list(zip(labels, paths)), variable or None,
                             dict(name=axis_name, unit=unit, start=float(start), step=float(step)))
        app.load_data(data, " + ".join(labels), mode="classic" if data["W"].shape[3] == 1 else "multiplex")

    _dialog(app, "Combine group ZIPs",
            "Check the group name for each ZIP. Participants are ordered by file name within each ZIP. Then describe the layers: for example Frequency, Hz, first value 1, step 1.",
            rows, build, "Combine")


def _edit_axis(app):
    data = app.data
    axis = axis_metadata(data)
    rows = [("Axis name", axis["name"], None, False), ("Unit (optional)", axis["unit"], None, False),
            ("Ordered values", ", ".join(str(v) for v in axis["values"]), None, True),
            ("Default adjacency", ADJACENCY[axis["adjacency"]], ADJACENCY.values(), False)]

    def apply(values):
        name, unit, positions, adjacency = values
        candidate = data.copy()
        numeric = _matrix(positions, "Layer values")
        if min(numeric.shape) != 1:
            raise ValueError("Enter one ordered vector of layer values.")
        candidate["axis_values"] = candidate["frequencies"] = numeric.ravel()
        update_axis(candidate, {"name": name, "unit": unit, "adjacency": _key(ADJACENCY, adjacency)})
        _dataset_edit(app, candidate)

    _dialog(app, "Layer axis", "Use an ordered axis such as time, frequency or condition. Each layer needs one increasing value.", rows, apply)


def _edit_group(app):
    data = app.data
    def import_labels(text):
        return _labels_text(_label_vector(text))
    rows = [("Group labels or pair IDs", _labels_text(data.get("group", [])), None, import_labels),
            ("Exchange blocks (optional)", _labels_text(data.get("exchange_blocks", [])), None, import_labels)]

    def apply(values):
        candidate = data.copy()
        for key, value in zip(("group", "exchange_blocks"), values):
            if not value:
                candidate.pop(key, None)
            elif key not in data or value != _labels_text(data[key]):
                try:
                    labels = _label_vector(value)
                    # Preserve numeric sorting for an existing numeric group contrast.
                    if key in data and np.asarray(data[key]).dtype.kind in "iuf":
                        try:
                            labels = [float(label) for label in labels]
                        except ValueError:
                            pass  # A researcher can also replace numeric IDs with names.
                    candidate[key] = labels
                except csv.Error as exc:
                    raise ValueError("Check the comma-separated labels and paired quotation marks.") from exc
        _dataset_edit(app, candidate)

    _dialog(app, "Groups and exchange blocks",
            "Use one label per observation, in dataset order. Separate labels with commas or import a headerless table. For paired tests, repeat each pair ID twice in condition order. Clear a field to remove it.",
            rows, apply)


def _edit_glm(app):
    data = app.data
    rows = [("Design matrix X", _matrix_text(data["X"]) if "X" in data else "", None, True),
            ("Contrast C", _matrix_text(data["C"]) if "C" in data else "", None, True),
            ("Contrast statistic", str(data.get("stat_type", "t")).upper(), ("T", "F"), False)]

    def apply(values):
        x, c, stat = values
        candidate = data.copy()
        if x or c:
            candidate.update(X=_matrix(x, "X"), C=_matrix(c, "C"), stat_type=stat.lower())
        else:
            for key in ("X", "C", "stat_type"):
                candidate.pop(key, None)
        _dataset_edit(app, candidate)

    _dialog(app, "Design matrix and contrast",
            "X has one row per observation. C has one column per regressor. Separate columns with commas and rows with semicolons, or import headerless text tables. Clear both to remove the GLM.",
            rows, apply)


def _coordinates(app):
    name = filedialog.askopenfilename(parent=app.root, title="Choose node coordinates",
        filetypes=[("Coordinates", ("*.csv", "*.tsv", "*.txt", "*.npy", "*.mat")), ("All files", "*")])
    if not name:
        return

    def apply(values):
        unit, space = values
        candidate = app.data.copy()
        set_coordinates(candidate, Path(name).read_bytes(), Path(name).name, units=unit, space=space)
        _install_edit(app, candidate)

    _dialog(app, "Node coordinates", f"{Path(name).name} · One x, y, z row per node in input order. Text files may start with a label column.",
            [("Input units", "mm", ("mm", "cm"), False), ("Coordinate space", "MNI", None, False)], apply)


def _save_data(app):
    out = filedialog.asksaveasfilename(parent=app.root, title="Save reusable dataset",
            initialfile=Path(app.name).stem + ".npz", defaultextension=".npz", filetypes=[("NumPy dataset", "*.npz")])
    if out:
        try:
            Path(out).write_bytes(dataset_npz(app.data))
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not save dataset", str(exc), parent=app.root)


def _observations(app):
    data = app.data
    win = tk.Toplevel(app.root)
    win.title("Observation order")
    win.transient(app.root)
    body = ttk.Frame(win, padding=26)
    body.pack(fill="both", expand=True)
    _heading(body, "Observation order")
    _note(body, "Design rows and labels follow this order. In a pair, the first observation is compared with the second.")
    table = ttk.Treeview(body, columns=("row", "id", "group", "block"), show="headings", height=12)
    for key, title, width in [("row", "Row", 60), ("id", "Observation ID", 240),
                              ("group", "Group or pair ID", 140), ("block", "Exchange block", 140)]:
        table.heading(key, text=title)
        table.column(key, width=width, minwidth=50)
    count = data["W"].shape[0]
    for index in range(count):
        table.insert("", "end", values=[index + 1] + [
            data[key][index] if key in data else "—" for key in ("observation_ids", "group", "exchange_blocks")])
    scroll = ttk.Scrollbar(body, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    table.pack(fill="both", expand=True)
    win.bind("<Escape>", lambda _event: win.destroy())


def _card(parent):
    return ttk.Frame(parent, style="Card.TFrame", padding=(24, 20, 24, 22))


def _two_columns(parent, cards, minimum=880):
    """Lay cards side by side on wide windows and stacked on narrow ones."""
    def arrange(event):
        wide = event.width >= minimum
        for index, card in enumerate(cards):
            card.grid(row=0 if wide else index, column=index if wide else 0, sticky="nsew",
                      padx=(0, 16 if wide and index < len(cards) - 1 else 0), pady=(0, 0 if wide else 14))
        for index in range(len(cards)):
            parent.columnconfigure(index, weight=1 if wide else 0, uniform="cards" if wide else "")
        parent.columnconfigure(0, weight=1)
    parent.bind("<Configure>", arrange)


def _current_dataset(app, parent):
    desc = app.description
    card = _card(parent)
    card.pack(fill="x", pady=(0, 30))
    ttk.Label(card, text="LOADED", style="CardKicker.TLabel").pack(anchor="w")
    _text(card, app.name, "CardTitle.TLabel", pady=(4, 8))
    axis = desc["axis"]
    count = desc["layer_count"]
    facts = [f"{desc['subjects']} observations", f"{desc['nodes']} regions",
             f"{count} {'layer' if count == 1 else 'layers'} ({axis['name']}{', ' + axis['unit'] if axis['unit'] else ''})"]
    _text(card, "   ·   ".join(facts), "Card.TLabel", pady=(0, 6))
    groups = desc["group_counts"]
    if groups and len(groups) <= 4:
        _text(card, "Groups: " + ",  ".join(f"{group['label']} ({group['count']})" for group in groups), "CardMuted.TLabel", pady=(0, 4))
    elif groups:
        _text(card, f"{len(groups)} group labels or pair IDs. Open Observation order for the full list.", "CardMuted.TLabel", pady=(0, 4))
    _text(card, "   ·   ".join([
        f"Design matrix {desc['design_shape'][0]} × {desc['design_shape'][1]}" if desc["has_glm"] else "No design matrix",
        f"Coordinates: {desc['coordinate_space']}" if desc["coordinate_space"] else "No node coordinates (the brain view needs them)"]),
        "CardMuted.TLabel", pady=(0, 6))
    for issue in desc["issues"]:
        _text(card, issue, "CardWarn.TLabel", pady=(0, 6))
    row = _bar(card)
    _button(row, "Set up the model  \u203a", lambda: app.show("model"), True)
    _button(row, "Observation order", lambda: _observations(app))
    _button(row, "Save dataset…", lambda: _save_data(app))
    ttk.Label(card, text="Adjust", style="CardSmallHeading.TLabel").pack(anchor="w", pady=(12, 6))
    row = _bar(card)
    _button(row, "Groups and blocks…", lambda: _edit_group(app))
    _button(row, "Design and contrast…", lambda: _edit_glm(app))
    _button(row, "Layer axis…", lambda: _edit_axis(app))
    _button(row, "Node coordinates…", lambda: _coordinates(app))
    _text(card, "Save dataset writes the combined matrices, groups, layer axis, labels and coordinates to one "
                ".npz file that opens directly next time.", "CardMuted.TLabel", pady=(4, 0))


def _open_panel(app, parent):
    cards = ttk.Frame(parent)
    cards.pack(fill="x")
    single, zipped = _card(cards), _card(cards)
    _two_columns(cards, [single, zipped])

    _text(single, "One combined file", "CardTitle.TLabel", pady=(0, 8))
    _text(single, "A NumPy .npz or MATLAB v7 .mat file that holds every participant. Store the matrices as W "
                  "and one group label per participant as group.", "Card.TLabel")
    _text(single, "W       participants × regions × regions × layers\n"
                  "group   one label per participant\n"
                  "optional: axis_values, node_labels, node_coordinates", "CardCode.TLabel", pady=(2, 12))
    _text(single, "For one network per participant, leave out the layer dimension. MATLAB arrays use "
                  "regions × regions × layers × participants.", "CardMuted.TLabel")
    _button(_bar(single), "Choose file…", lambda: _import_dataset(app), True)

    _text(zipped, "One ZIP per group", "CardTitle.TLabel", pady=(0, 8))
    _text(zipped, "Put each participant's matrix file in a folder for its group, zip each folder, then choose "
                  "all the ZIPs together. Each ZIP becomes one group.", "Card.TLabel")
    _text(zipped, "Control.zip\n   sub-01.mat\n   sub-02.mat   …\nPatient.zip\n   sub-31.mat   …",
          "CardCode.TLabel", pady=(2, 12))
    _text(zipped, "Use .mat or .npy files (regions × regions × layers), or .csv, .tsv or .txt for one network. "
                  "Participants are ordered by file name.", "CardMuted.TLabel")
    _button(_bar(zipped), "Choose group ZIPs…", lambda: _archives(app), True)
    _text(parent, "Brain coordinates are optional and can be added after loading with Node coordinates. "
                  "The Prepare inputs page has full format details.", "Muted.TLabel", pady=(16, 0))


DEMO_FACTS = {
    "brain-network": "32 brain regions · 40 participants in two groups · 8 time windows · brain coordinates",
    "two-sample": "12 nodes · 40 participants in two groups · 8 frequency bins",
    "paired": "12 nodes · 20 participants × 2 conditions · 8 frequency bins",
    "glm": "12 nodes · 40 participants · 8 frequency bins · design matrix with a covariate",
}


def _demo_option(app, card, key):
    ttk.Radiobutton(card, text=DEMOS[key], value=key, variable=app.demo_kind, style="Card.TRadiobutton").pack(anchor="w", pady=(12, 2))
    _text(card, DEMO_FACTS[key], "CardSmallHeading.TLabel", pady=(0, 3)).pack_configure(padx=(30, 0))
    _text(card, DEMO_NOTES[key], "CardMuted.TLabel", pady=(0, 4)).pack_configure(padx=(30, 0))


def _demo_panel(app, parent):
    _text(parent, "These are four separate practice datasets. All of them are simulated, so you can learn the app "
                  "without your own data. Start with the brain example; the other three show how different study "
                  "designs are set up.", "TLabel", pady=(0, 16))
    cards = ttk.Frame(parent)
    cards.pack(fill="x")
    brain, designs = _card(cards), _card(cards)
    _two_columns(cards, [brain, designs])
    _text(brain, "Brain example", "CardTitle.TLabel", pady=(0, 2))
    _text(brain, "A realistic brain network, closest to a real study.", "CardMuted.TLabel", pady=(0, 2))
    _demo_option(app, brain, "brain-network")
    _text(designs, "Study design examples", "CardTitle.TLabel", pady=(0, 2))
    _text(designs, "Small abstract networks with no brain coordinates. Each one shows a different design.",
          "CardMuted.TLabel", pady=(0, 2))
    for key in ("two-sample", "paired", "glm"):
        _demo_option(app, designs, key)
    row = _bar(parent)
    row.pack_configure(pady=(18, 0))
    _button(row, "Open selected demo", lambda: app.open_demo("multiplex", kind=app.demo_kind.get()), True)


def data_page(app, parent):
    """Render the data source choice, the loaded dataset and its editors."""
    ttk.Label(parent, text="Data", style="PageTitle.TLabel").pack(anchor="w", pady=(0, 14))
    _text(parent, "Each participant contributes one connectivity matrix (regions × regions), or a stack of "
                  "matrices across time points or frequency bins. Every participant needs the same regions in "
                  "the same order, plus a group label.", "Lead2.TLabel", pady=(0, 28))
    if app.description:
        _current_dataset(app, parent)
    if not hasattr(app, "data_source"):
        app.data_source = tk.StringVar(app.root, "open")
        app.demo_kind = tk.StringVar(app.root, "brain-network")
    ttk.Label(parent, text="Use different data" if app.description else "Choose your data",
              style="Heading.TLabel").pack(anchor="w", pady=(0, 12))
    choice = ttk.Frame(parent, style="Segment.TFrame", padding=1)
    choice.pack(anchor="w", pady=(0, 20))
    panel = ttk.Frame(parent)
    panel.pack(fill="x")

    def show():
        for child in panel.winfo_children():
            child.destroy()
        (_open_panel if app.data_source.get() == "open" else _demo_panel)(app, panel)

    for value, label in (("open", "Open my data"), ("demo", "Try a demo dataset")):
        ttk.Radiobutton(choice, text=label, value=value, variable=app.data_source, style="Choice.Toolbutton",
                        command=show).pack(side="left")
    show()


def _threshold_unit(mode, design):
    if design == "glm-f":
        return "F"
    if mode == "classic" and design == "one-sample":
        return "mean weight"
    return "t"


def _metric_options(mode):
    if mode == "classic":
        return {"extent": "Extent · number of edges", "intensity": "Intensity · excess above threshold"}
    return {"extent": "Extent · number of node–layer sites", "mass": "Mass · summed statistic magnitudes"}


def _number(raw, label, integer=False, minimum=0):
    try:
        value = int(raw) if integer else float(raw)
        if not math.isfinite(value) or value < minimum:
            raise ValueError
    except (ValueError, TypeError, OverflowError) as exc:
        requirement = f"an integer of at least {minimum}" if integer else f"a finite number of at least {minimum}"
        raise ValueError(f"{label} must be {requirement}.") from exc
    return value


def model_page(app, parent):
    """Render a design-aware model and call app.start with validated engine keys."""
    ttk.Label(parent, text="Statistical model", style="PageTitle.TLabel").pack(anchor="w", pady=(0, 14))
    if not app.description:
        _note(parent, "Choose a dataset or an example before setting up the model.")
        _button(_bar(parent), "Choose data →", lambda: app.show("data"), True)
        return
    description = app.description
    config = app.config
    axis = description["axis"]
    count = description["layer_count"]
    _note(parent, f"{app.name}   ·   {description['subjects']} observations   ·   {description['nodes']} nodes   ·   {count} {'layer' if count == 1 else 'layers'}")
    mode_key = _method(config, count) if config.get("inference_mode") else ("classic" if count == 1 else "multiplex")
    method_choices = [label for key, label in MODES.items() if count > 1 or key != "layerwise"]
    design_key = config.get("design", description["suggested_design"]) or ""
    mode_var = tk.StringVar(parent, MODES[mode_key])
    design_var = tk.StringVar(parent, DESIGNS.get(design_key, "Choose a design"))
    threshold = tk.StringVar(parent, config.get("threshold", "" if _threshold_unit(mode_key, design_key) == "mean weight" else 3))
    tail_var = tk.StringVar(parent, TAILS.get(config.get("tail"), "Positive"))
    metric_var = tk.StringVar(parent, _metric_options(mode_key).get(config.get("metric"), _metric_options(mode_key)["extent"]))
    perm = tk.StringVar(parent, config.get("n_perm", 9999))
    seed = tk.StringVar(parent, "" if config.get("seed", 1) is None else config.get("seed", 1))
    alpha = tk.StringVar(parent, config.get("alpha", .05))
    method = tk.StringVar(parent, RESAMPLING.get(config.get("method"), "Automatic"))
    use_abs = tk.BooleanVar(parent, config.get("use_abs", False))
    unit = _threshold_unit(mode_key, design_key)
    layer_options = [f"{index} · {value:g}{' ' + axis['unit'] if axis['unit'] else ''}"
                     for index, value in enumerate(axis["values"], 1)]
    selected = config.get("classic_layer")
    initial_layer = layer_options[0] if count == 1 else ""
    if selected is not None and str(selected).isdigit() and 1 <= int(selected) <= count:
        initial_layer = layer_options[int(selected) - 1]
    layer = tk.StringVar(parent, initial_layer)

    model = _fields(parent)
    mode_widget = _combo(model, mode_var, method_choices)
    _field(model, 0, "Method", mode_widget)
    mode_note = ttk.Label(model, style="Muted.TLabel", wraplength=520, justify="left")
    mode_note.grid(row=1, column=1, sticky="w", pady=(0, 10))
    layer_widget = _combo(model, layer, layer_options)
    layer_caption = _field(model, 2, f"{axis['name']} layer", layer_widget)
    design_widget = _combo(model, design_var, DESIGNS.values())
    _field(model, 3, "Study design", design_widget)
    direction = _note(parent, "")
    settings = _fields(parent)
    threshold_widget = ttk.Entry(settings, textvariable=threshold)
    threshold_caption = _field(settings, 0, "Primary threshold", threshold_widget)
    tail_widget = _combo(settings, tail_var, TAILS.values())
    _field(settings, 1, "Tail", tail_widget)
    metric_widget = _combo(settings, metric_var, _metric_options(mode_key).values())
    _field(settings, 2, "Component statistic", metric_widget)
    _field(settings, 3, "Permutations", ttk.Entry(settings, textvariable=perm))
    advanced_toggle = tk.BooleanVar(parent, False)
    advanced = ttk.Frame(parent)
    extra = _fields(advanced)
    _field(extra, 0, "Reporting alpha", ttk.Entry(extra, textvariable=alpha))
    _field(extra, 1, "Random seed", ttk.Entry(extra, textvariable=seed))
    method_widget = _combo(extra, method, RESAMPLING.values())
    method_caption = _field(extra, 2, "GLM permutation", method_widget)
    absolute_widget = ttk.Checkbutton(advanced, text="Use absolute connectivity weights", variable=use_abs)
    absolute_widget.pack(anchor="w", pady=(0, 10))
    toggler = ttk.Checkbutton(parent, text="Advanced settings", variable=advanced_toggle)
    toggler.pack(anchor="w", pady=(0, 13))
    container = ttk.Frame(parent)
    container.pack(anchor="w", fill="x")
    notice = _note(container, "")
    actions = _bar(container)

    def toggle_advanced():
        if advanced_toggle.get():
            advanced.pack(before=container, anchor="w", fill="x")
        else:
            advanced.pack_forget()

    toggler.configure(command=toggle_advanced)

    def selection():
        # Engine inference mode: layer-wise NBS runs the multiplex engine with separate layers.
        method = _key(MODES, mode_var.get())
        return ("multiplex" if method == "layerwise" else method), _key(DESIGNS, design_var.get())

    def draft():
        mode, design = selection()
        opts = _metric_options(mode)
        values = {"inference_mode": mode, "design": design,
                  "threshold": threshold.get(), "tail": _key(TAILS, tail_var.get()),
                  "metric": _key(opts, metric_var.get()), "n_perm": perm.get(),
                  "seed": seed.get(), "alpha": alpha.get(),
                  "method": _key(RESAMPLING, method.get()) if design.startswith("glm") else "auto",
                  "use_abs": use_abs.get(),
                  "layer_adjacency": ("independent" if _key(MODES, mode_var.get()) == "layerwise" else
                                      "consecutive" if count > 1 and mode == "multiplex" else axis["adjacency"])}
        if mode == "classic" and layer.get() in layer_options:
            values["classic_layer"] = layer_options.index(layer.get()) + 1
        return values

    def start():
        values = draft()
        try:
            values["threshold"] = _number(values["threshold"], "Primary threshold")
            if values["threshold"] == 0:
                raise ValueError("Primary threshold must be greater than zero.")
            values["n_perm"] = _number(values["n_perm"], "Permutations", integer=True, minimum=1)
            values["seed"] = _number(values["seed"], "Random seed", integer=True) if values["seed"].strip() else None
            values["alpha"] = validate_alpha(_number(values["alpha"], "Reporting alpha"))
            app.start(values)
        except (ValueError, OSError, OverflowError) as exc:
            messagebox.showerror("Review model settings", str(exc), parent=app.root)

    run_button = _button(actions, "Run permutations", start, True)
    _button(actions, "Review data", lambda: app.show("data"))

    def show_fields(row, visible):
        for widget in row:
            if visible:
                widget.grid()
            else:
                widget.grid_remove()

    def refresh(*_):
        nonlocal unit
        mode, design = selection()
        classic = mode == "classic"
        show_fields((layer_caption, layer_widget), classic)
        mode_note.configure(text=MODE_NOTES[_key(MODES, mode_var.get())])
        show_fields((method_caption, method_widget), design.startswith("glm"))
        options = _metric_options(mode)
        metric_widget.configure(values=list(options.values()))
        if metric_var.get() not in options.values():
            metric_var.set(options["extent"])
        current_unit = _threshold_unit(mode, design)
        if current_unit != unit:
            threshold.set("")
            unit = current_unit
        threshold_caption.configure(text=f"Primary threshold ({unit})")
        if design == "glm-f":
            tail_var.set(TAILS["right"])
        tail_widget.configure(state="disabled" if design == "glm-f" else "readonly")
        if design == "one-sample":
            use_abs.set(False)
        absolute_widget.state(["disabled"] if design == "one-sample" else ["!disabled"])
        issue = ""
        details = ""
        if not design:
            issue = "Choose the study design that matches your observations."
        elif not description["designs"][design]["ready"]:
            issue = description["designs"][design]["issue"]
        elif design == "two-sample":
            groups = description["groups"]
            details = f"Positive tests {groups[0]} > {groups[1]}. The edge statistic is Welch’s t."
        elif design == "paired":
            details = "Positive tests the first observation minus the second within each pair."
        elif design == "one-sample" and classic:
            details = "Classic one-sample NBS thresholds the signed mean in your connectivity units. Enter a threshold on that scale."
        elif design == "one-sample":
            details = "Multiplex one-sample NBS uses a t statistic to test signed connectivity against zero."
        elif design == "glm-f":
            details = "The F statistic tests the contrast rows jointly with a positive tail."
        elif design == "glm-t":
            details = "The sign of your contrast C determines the direction of the t statistic."
        direction.configure(text=details or "Set the design using the group labels, pair IDs or GLM in your dataset.")
        if classic:
            scope = "Component p-values cover this one prespecified layer."
        elif count > 1 and _key(MODES, mode_var.get()) == "multiplex":
            scope = "Shared nodes link neighboring layers. Component p-values account for the search across all layers."
        elif count > 1:
            scope = "Components stay within each layer. Component p-values still account for the search across all layers."
        else:
            scope = "Multiplex extent counts participating node–layer sites, including on a single input layer."
        if classic and not layer.get() and not issue:
            issue = f"Choose a prespecified {axis['name'].lower()} layer for Classic NBS."
        if not threshold.get().strip() and not issue:
            issue = f"Enter a primary threshold in {unit} units."
        notice.configure(text=issue or scope)
        run_button.state(["disabled"] if issue else ["!disabled"])

    # Native typing, keyboard selection, and .current() all change the Tcl variable.
    # A virtual selection event need not be delivered while a page is unmapped.
    traces = [(var, var.trace_add("write", refresh))
              for var in (mode_var, design_var, layer)]
    def threshold_changed(*_):
        # refresh clears the threshold while switching measurement units.
        if unit == _threshold_unit(*selection()):
            refresh()
    traces.append((threshold, threshold.trace_add("write", threshold_changed)))

    def release_traces(event):
        if event.widget is parent:
            for var, token in traces:
                var.trace_remove("write", token)
    parent.bind("<Destroy>", release_traces, add=True)
    app.remember_model = draft
    refresh()
