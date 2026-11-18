"""Native component results, figures, and researcher exports."""
from functools import lru_cache
import json
import math
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET

import numpy as np
from tkinter import font

from .io import refresh_report, result_csv, result_mat, result_text, validate_alpha
from .native_figures import mix as _mix


# Figures use neutral backgrounds so coloured data stand out. The yellow-green-blue ramp
# (ColorBrewer YlGnBu) orders counts and edge strengths; it is reversed in dark mode so
# larger values are always the most visible.
FIGURE = {
    # Light: the app's deep teal for the component, the YlGnBu ramp for strength,
    # neutral greys for context, and a dark dotted line for the critical value.
    "light": dict(bg="#ffffff", ink="#132523", muted="#4f6460", grid="#e3eceb", axis="#97aaa7",
                  context="#c3cfcd", component="#00695c", band="#e7f3f1", node="#b7c6c3",
                  outline="#7d918d", fine="#cbd8d6", critical="#132523", empty="#f0f5f4",
                  ramp=("#c7e9b4", "#7fcdbb", "#41b6c4", "#1d91c0", "#225ea8", "#253494")),
    # Dark: figures sit on the card surface. Pastel teal for the component, quiet greys for
    # context, a dim-to-bright teal ramp, and glass-brain outlines dimmed so they do not glare.
    "dark": dict(bg="#1b1f1f", ink="#e2e6e5", muted="#9aa2a0", grid="#262c2c", axis="#4a5352",
                 context="#66706e", component="#80cbc4", band="#1f2b2a", node="#5f6a68",
                 outline="#68726f", fine="#30393a", critical="#d9dedc", empty="#212626",
                 ramp=("#253494", "#225ea8", "#1d91c0", "#41b6c4", "#7fcdbb", "#c7e9b4")),
    # Mono: black and white. The component is white; everything else is a step of grey.
    "mono": dict(bg="#1c1c1c", ink="#e6e6e6", muted="#9c9c9c", grid="#282828", axis="#555555",
                 context="#6c6c6c", component="#ececec", band="#262626", node="#626262",
                 outline="#6e6e6e", fine="#333333", critical="#9c9c9c", empty="#222222",
                 ramp=("#3a3a3a", "#585858", "#7a7a7a", "#a0a0a0", "#c8c8c8", "#ececec")),
}

# The same palette is used for the live Canvas and its exported figure.
DEFAULT_COLORS = {"plot": "#10251f", "fg": "#f1faf6", "muted": "#c1d4cb",
                  "accent": "#78e6b7", "other": "#536c60"}


@lru_cache(maxsize=1)
def _mni_outlines():
    """Convert our bundled nilearn MNI schematic paths to native Canvas polylines."""
    resource = Path(__file__).parent / "static" / "glass-brain.json"
    if not resource.is_file():
        return {}
    views = json.loads(resource.read_text(encoding="utf-8"))["views"]
    result = {}
    steps = np.linspace(0, 1, 7)[1:, None]
    for name, view in views.items():
        paths = []
        for path in view["paths"]:
            # Commands in this local asset are absolute M, L and cubic C.
            line = []
            for op, numbers in re.findall(r"([MLC])([^MLC]*)", path["d"]):
                points = np.asarray([float(x) for x in numbers.split()]).reshape(-1, 2)
                if op == "M":
                    if len(line) > 1:
                        paths.append((path["k"], np.asarray(line)))
                    line = list(points)
                elif op == "L":
                    line.extend(points)
                elif op == "C":
                    for p1, p2, p3 in points.reshape(-1, 3, 2):
                        p0 = line[-1]
                        line.extend((1-steps)**3*p0 + 3*(1-steps)**2*steps*p1
                                    + 3*(1-steps)*steps**2*p2 + steps**3*p3)
            if len(line) > 1:
                paths.append((path["k"], np.asarray(line)))
        result[name] = (view["box"], paths)
    return result


def _axis_value(axis, layer):
    return f"{axis['values'][layer - 1]:g} {axis['unit']}".strip()


def _direction(config, tail):
    if config["stat_type"] == "f":
        return "joint F contrast"
    positive = tail == "right"
    if config["test"] == "two-sample":
        a, b = config["group_values"]
        return f"{a} {'>' if positive else '<'} {b}"
    if config["test"] == "paired":
        return "first > second within pairs" if positive else "first < second within pairs"
    if config["test"] == "one-sample":
        return "mean above zero" if positive else "mean below zero"
    return "positive GLM contrast" if positive else "negative GLM contrast"


def component_summary(result, component):
    cfg, data = result["config"], result["dataset"]
    axis = data["axis"]
    classic = cfg["inference_mode"] == "classic"
    bins = component["layer_bins"]
    if classic:
        location = f"in input layer {cfg['classic_layer']} ({axis['name']} = {_axis_value(axis, 1)})"
        unit = "edge" if component["extent"] == 1 else "edges"
    else:
        location = f"in {len(bins)} layer{'s' if len(bins) != 1 else ''}"
        if len(bins) > 1:
            location += f" ({axis['name']} from {_axis_value(axis, bins[0])} to {_axis_value(axis, bins[-1])})"
        else:
            location += f" ({axis['name']} = {_axis_value(axis, bins[0])})"
        unit = "node–layer site" if component["extent"] == 1 else "node–layer sites"
    alpha, p = result["reporting"]["alpha"], component["p_fwe"]
    status = "significant" if p <= alpha else "nonsignificant"
    return (f"Component {component['id']} contains {component['extent']} {unit} and "
            f"{component['n_nodes']} regions {location}. The component was {status} at α = {alpha:g} "
            f"(corrected p = {p:.4g}, {_direction(cfg, component['tail'])}).")


def _write_file(destination, content):
    """A cancelled or failed export leaves any previous result file intact."""
    temp = None
    try:
        with NamedTemporaryFile(dir=Path(destination).parent, delete=False) as stream:
            temp = Path(stream.name)
            stream.write(content)
        os.replace(temp, destination)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def figure_svg(canvas, title, description=""):
    """Serialize the rendered Canvas primitives at their plot coordinates."""
    region = [float(x) for x in str(canvas.cget("scrollregion")).split()]
    width, height = region[2], region[3]
    svg = ET.Element("svg", xmlns="http://www.w3.org/2000/svg",
                     viewBox=f"0 0 {width:g} {height:g}", width=f"{width:g}", height=f"{height:g}")
    ET.SubElement(svg, "title").text = title
    if description:
        ET.SubElement(svg, "desc").text = description
    ET.SubElement(svg, "rect", width="100%", height="100%", fill=canvas.cget("background"))
    for item in canvas.find_all():
        kind = canvas.type(item)
        coords = canvas.coords(item)
        get = lambda option: canvas.itemcget(item, option)
        if kind in ("rectangle", "oval"):
            x, y, x2, y2 = coords
            attrs = (dict(x=x, y=y, width=x2-x, height=y2-y) if kind == "rectangle"
                     else dict(cx=(x+x2)/2, cy=(y+y2)/2, rx=(x2-x)/2, ry=(y2-y)/2))
            node = ET.SubElement(svg, "rect" if kind == "rectangle" else "ellipse",
                                 {k: f"{v:g}" for k, v in attrs.items()})
            node.set("fill", get("fill") or "none")
            node.set("stroke", get("outline") or "none")
            node.set("stroke-width", get("width"))
        elif kind in ("line", "polygon"):
            points = " ".join(f"{x:g},{y:g}" for x, y in zip(coords[::2], coords[1::2]))
            if kind == "polygon":
                node = ET.SubElement(svg, "polygon", points=points, fill=get("fill") or "none",
                                     stroke=get("outline") or "none", attrib={"stroke-width": get("width")})
            else:
                node = ET.SubElement(svg, "polyline", points=points, fill="none", stroke=get("fill"),
                                     attrib={"stroke-width": get("width"), "stroke-linejoin": "round",
                                             "stroke-linecap": "round"})
            if get("dash"):
                node.set("stroke-dasharray", " ".join(canvas.tk.splitlist(get("dash"))))
        elif kind == "text":
            anchor = {"w": "start", "e": "end", "center": "middle", "nw": "start", "sw": "start",
                      "ne": "end", "se": "end", "n": "middle", "s": "middle"}[get("anchor")]
            font = canvas.tk.splitlist(get("font"))
            weight = "bold" if any(str(part) == "bold" for part in font[2:]) else "normal"
            node = ET.SubElement(svg, "text", x=f"{coords[0]:g}", y=f"{coords[1]:g}", fill=get("fill"),
                                 attrib={"font-family": "Helvetica Neue, Helvetica, Arial, sans-serif",
                                         "font-size": str(abs(int(font[1]))), "font-weight": weight,
                                         "text-anchor": anchor, "dominant-baseline": "central"})
            node.text = get("text")
            angle = float(get("angle") or 0)
            if angle:
                # Tk rotates counter-clockwise; SVG rotates clockwise.
                node.set("transform", f"rotate({-angle:g} {coords[0]:g} {coords[1]:g})")
    return ET.tostring(svg, encoding="utf-8", xml_declaration=True)


def method_name(config, layers):
    if config.get("inference_mode") == "classic":
        return "Classic NBS"
    if layers > 1 and config.get("layer_adjacency") == "independent":
        return "Layer-wise NBS"
    return "Multiplex-NBS"


def _ticks(count, most=8):
    if count <= most:
        return list(range(count))
    return sorted({round(i * (count - 1) / (most - 1)) for i in range(most)})


def _range_label(values, unit):
    text = f"{values[0]:g}" if len(values) == 1 else f"{values[0]:g}–{values[-1]:g}"
    return f"{text} {unit}".strip()


TABS_STACK = (("profile", "Layer profile"), ("membership", "Node × layer"), ("brain", "Brain"),
              ("layers", "All layers"), ("null", "Null distribution"))
TABS_SINGLE = (("brain", "Brain"), ("null", "Null distribution"))
TAB_HINTS = {
    "profile": "How much of the network passes the threshold in each layer, and how much of it belongs to this component.",
    "membership": "Which regions belong to the component, and in which layers.",
    "brain": "The component on a glass brain, one layer at a time. Press Play to step through the layers, or drag the slider.",
    "network": "The component one layer at a time. Press Play to step through the layers, or drag the slider.",
    "layers": "Every layer the component spans, side by side. Click a panel to open that layer in the Brain tab.",
    "null": "How this component's size compares with the largest component found by chance in each permutation.",
}


def _nice_ticks(high, most=6):
    """Round tick values from 0 to at least high (1, 2 or 5 times a power of ten)."""
    if high <= 0:
        return [0, 1]
    raw = high / (most - 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    for multiple in (1, 2, 5, 10):
        step = multiple * magnitude
        if high / step <= most - 1:
            break
    if float(high).is_integer():
        step = max(1, round(step))
    count = math.ceil(high / step - 1e-9)
    return [round(i * step, 10) for i in range(count + 1)]
SPEEDS = {"1.5 s per layer": 1500, "1 s per layer": 1000, "0.5 s per layer": 500, "0.25 s per layer": 250, "0.1 s per layer": 100}
EXPORTS = (
    ("Report", "txt", result_text,
     "Summary, interpretation notes, every component with its regions and layers, a methods paragraph and all settings."),
    ("Component table", "csv", result_csv,
     "One row per component: sign, extent, mass, corrected p, member regions and layers. Opens in Excel, R or Python."),
    ("Full results", "json", lambda r: json.dumps(r, allow_nan=False, ensure_ascii=False).encode("utf-8"),
     "Everything needed to reproduce or re-plot the analysis: settings, each component's region–layer membership, "
     "the edge statistic for every layer and all permutation maxima."),
    ("MATLAB results", "mat", result_mat,
     "The full results for MATLAB, with the edge statistics, edges, permutation maxima and p-values as arrays."),
)


def _flow(widgets, width, gap=12, row_gap=0):
    """Place widgets left to right, starting a new row when the next one would not fit."""
    x = row = 0
    for widget in widgets:
        need = widget.winfo_reqwidth()
        if x and x + need > width:
            x, row = 0, row + 1
        widget.grid(row=row, column=0, sticky="w", padx=(x, 0), pady=(row_gap if row else 0, 0))
        x += need + gap


def _flowing(frame, gap=12, row_gap=8):
    """A frame whose children wrap onto new rows as its width changes."""
    frame.bind("<Configure>", lambda event: _flow(frame.winfo_children(), event.width, gap, row_gap), add=True)
    return frame


def results_page(app, parent):
    panel = ResultsView(app, parent)
    panel.pack(fill="both", expand=True)
    return panel


class ResultsView(ttk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent)
        self.app, self.result = app, app.result
        self.columnconfigure(0, weight=1)
        self.family = getattr(app, "family", "Helvetica")
        if not self.result:
            ttk.Label(self, text="Results", style="PageTitle.TLabel").grid(sticky="w")
            ttk.Label(self, text="Run a model to see the components and their corrected p-values.").grid(sticky="w", pady=13)
            return
        self.cfg, self.data = self.result["config"], self.result["dataset"]
        self.classic = self.cfg["inference_mode"] == "classic"
        self.axis = self.data["axis"]
        self.layers = len(self.axis["values"])
        self.edges = np.asarray(self.result["edges"], dtype=int).reshape(-1, 2) - 1
        self.statistic = np.asarray(self.result["statistic"], dtype=float).reshape(len(self.edges), -1)
        self.components = {c["id"]: c for c in self.result["clusters"]}
        self.coords = self.data.get("node_coordinates")
        self.component = None
        self.timer = self.redraw = None
        self.last_width = 0
        self.wrapped = []
        self.scope = tk.StringVar(self, "Significant")
        self.alpha = tk.StringVar(self, str(self.result["reporting"]["alpha"]))
        self.tab = tk.StringVar(self, "profile" if self.layers > 1 else "brain")
        self.view = tk.StringVar(self, "Four views")
        self.hover = None
        self.panels = []
        self.layer = tk.IntVar(self, 1)
        self.span_index = 0
        self.syncing = False
        self.speed = tk.StringVar(self, "0.5 s per layer")
        self.loop = tk.BooleanVar(self, True)
        self.only_members = tk.BooleanVar(self, True)
        self.brain_options = {key: tk.BooleanVar(self, value) for key, value in
                              (("edges", True), ("other", False), ("numbers", self.data["nodes"] <= 40), ("sulci", True))}
        self.title, self.headline, self.meta = tk.StringVar(self), tk.StringVar(self), tk.StringVar(self)
        self.note, self.layer_text, self.report = tk.StringVar(self), tk.StringVar(self), tk.StringVar(self)
        self.notes = tk.StringVar(self)
        self._build()
        self.bind("<Configure>", self._resize)
        self.bind("<Destroy>", self._destroyed)
        self.bind("<Unmap>", lambda event: self.stop() if event.widget is self else None)
        self.refresh()

    # ----- layout -------------------------------------------------------------------------
    def _label(self, parent, variable=None, text="", style="TLabel", share=1.0):
        options = {"textvariable": variable} if variable is not None else {"text": text}
        label = ttk.Label(parent, style=style, wraplength=600, justify="left", **options)
        self.wrapped.append((label, share))
        return label

    def _build(self):
        head = ttk.Frame(self)
        head.grid(row=0, sticky="ew")
        ttk.Label(head, textvariable=self.title, style="PageTitle.TLabel").pack(anchor="w")
        self._label(head, self.headline, style="Lead2.TLabel").pack(anchor="w", pady=(8, 4))
        self._label(head, self.meta, style="Muted.TLabel").pack(anchor="w")

        self.kpis = ttk.Frame(self)
        self.kpis.grid(row=1, sticky="ew", pady=(24, 0))
        self.kpi_values = {}
        self.kpi_tiles = []
        for index, name in enumerate(("Components", "Significant", "Smallest corrected p", "Permutations")):
            tile = ttk.Frame(self.kpis)
            self.kpi_tiles.append(tile)
            card = ttk.Frame(tile, style="Kpi.TFrame", padding=(18, 12, 18, 14))
            card.pack(fill="both", expand=True)
            ttk.Frame(tile, style="Accent.TFrame", height=2).pack(fill="x")
            ttk.Label(card, text=name, style="KpiLabel.TLabel").pack(anchor="w")
            self.kpi_values[name] = ttk.Label(card, style="KpiValue.TLabel")
            self.kpi_values[name].pack(anchor="w", pady=(4, 0))

        row = 2
        info = self.data.get("demo_info")
        if info:
            notice = ttk.Frame(self, style="Notice.TFrame", padding=(16, 10))
            notice.grid(row=row, sticky="ew", pady=(16, 0))
            self._label(notice, text="Simulated data. " + info.get("simulation_note", ""), style="Notice.TLabel").pack(anchor="w")
        row += 1

        bar = ttk.Frame(self)
        bar.grid(row=row, sticky="ew", pady=(36, 12))
        bar.columnconfigure(0, weight=1)
        ttk.Label(bar, text="Components", style="Heading.TLabel").grid(row=0, column=0, sticky="w")
        self._label(bar, text="Click a component in the table to show it in the figures and details below. "
                              "Significant lists the components at or below the cutoff; All adds the rest.",
                    style="Muted.TLabel", share=.55).grid(row=1, column=0, sticky="w", pady=(6, 0))
        filters = ttk.Frame(bar)
        self.filters = filters
        segment = ttk.Frame(filters, style="Segment.TFrame", padding=1)
        self.scope_buttons = {}
        for value in ("Significant", "All observed"):
            button = ttk.Radiobutton(segment, value=value, variable=self.scope, style="SideSegment.Toolbutton",
                                     command=self.refresh)
            button.pack(side="left")
            self.scope_buttons[value] = button
        cutoff = ttk.Frame(filters)
        ttk.Label(cutoff, text="Corrected p ≤").pack(side="left", padx=(0, 8))
        entry = ttk.Entry(cutoff, textvariable=self.alpha, width=8)
        entry.pack(side="left")
        entry.bind("<Return>", lambda event: self.apply_cutoff())
        ttk.Button(cutoff, text="Apply", command=self.apply_cutoff).pack(side="left", padx=(8, 0))
        row += 1

        table = ttk.Frame(self)
        table.grid(row=row, sticky="ew")
        table.columnconfigure(0, weight=1)
        cols = ("id", "sign", "p", "extent", "weight", "nodes", "layers", "members")
        headings = ("Component", "Sign", "Corrected p", "Extent (edges)" if self.classic else "Extent (sites)",
                    "Intensity" if self.classic else "Mass", "Regions",
                    "Input layer" if self.classic else f"{self.axis['name']}", "Member regions")
        self.tree = ttk.Treeview(table, columns=cols, show="headings", selectmode="browse", height=5)
        for key, heading, width in zip(cols, headings, (100, 60, 110, 120, 90, 80, 150, 320)):
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, minwidth=50, stretch=key == "members",
                             anchor="w" if key == "members" else "center")
        self.tree.grid(row=0, column=0, sticky="ew")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", lambda event: self.select())
        row += 1
        self.empty = self._label(self, style="Muted.TLabel")
        self.empty.grid(row=row, sticky="ew", pady=(14, 0))
        row += 1

        self.explorer = ttk.Frame(self)
        self.explorer.grid(row=row, sticky="ew", pady=(36, 0))
        self.explorer.columnconfigure(0, weight=1)
        self.component_title = ttk.Label(self.explorer, style="Heading.TLabel")
        self.component_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.tab_bar = ttk.Frame(self.explorer)
        self.tab_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.tab_buttons = []
        for key, label in (TABS_STACK if self.layers > 1 else TABS_SINGLE):
            if key == "brain" and not self.coords:
                label = "Network"
            self.tab_buttons.append(ttk.Radiobutton(self.tab_bar, text=label, value=key, variable=self.tab,
                                                    style="Tab.Toolbutton", command=self.change_tab))
        ttk.Separator(self.explorer).grid(row=2, column=0, columnspan=2, sticky="ew")
        self.tab_hint = self._label(self.explorer, style="Lead3.TLabel")
        self.tab_hint.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(14, 12))
        self.figure_area = ttk.Frame(self.explorer)
        self.figure_area.columnconfigure(0, weight=1)
        self.plot = tk.Canvas(self.figure_area, height=320, width=1, highlightthickness=0, bd=0)
        self.plot.grid(row=1, sticky="ew")
        # Controls sit where they act: view choice over the figure's top-right corner, playback
        # directly under the figure, and display options under that.
        self.overlay = ttk.Frame(self.figure_area)
        self.player = ttk.Frame(self.figure_area)
        self.player.grid(row=2, sticky="ew", pady=(14, 0))
        self.display = ttk.Frame(self.figure_area)
        self.display.grid(row=3, sticky="ew", pady=(10, 0))
        self.plot.bind("<Configure>", self._queue_draw)
        self.plot.bind("<Button-1>", self._plot_click)
        self.plot.bind("<Motion>", self._plot_motion)
        self.plot.bind("<Leave>", lambda event: self.plot.delete("tooltip"))
        self._label(self.figure_area, self.note, "Muted.TLabel", share=.7).grid(row=4, sticky="ew", pady=(12, 0))
        tools = ttk.Frame(self.figure_area)
        tools.grid(row=5, sticky="w", pady=(14, 0))
        ttk.Button(tools, text="Save figure (SVG)…", command=self.save_figure).pack(side="left")
        ttk.Button(tools, text="Member regions", command=self.members).pack(side="left", padx=(10, 0))
        self.detail = ttk.Frame(self.explorer, style="Card.TFrame", padding=(20, 16, 20, 18))
        row += 1

        summary = ttk.Frame(self)
        summary.grid(row=row, sticky="ew", pady=(40, 0))
        self.summary_block = summary
        line = ttk.Frame(summary)
        line.pack(fill="x")
        ttk.Label(line, text="Summary", style="Heading.TLabel").pack(side="left")
        ttk.Button(line, text="Copy", command=lambda: self.app.copy(self.report.get())).pack(side="right")
        self._label(summary, self.report).pack(anchor="w", fill="x", pady=(10, 14))
        ttk.Label(summary, text="Notes", font=(self.family, 12, "bold")).pack(anchor="w")
        self._label(summary, self.notes, "Muted.TLabel").pack(anchor="w", fill="x", pady=(6, 0))
        row += 1

        save = ttk.Frame(self)
        save.grid(row=row, sticky="ew", pady=(40, 0))
        save.columnconfigure(1, weight=1)
        ttk.Label(save, text="Save results", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        self._label(save, text="Each file includes every observed component, not only the significant ones. "
                               "Save the figure in the current tab with Save figure above.",
                    style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 14))
        for index, (label, ext, encode, text) in enumerate(EXPORTS, 2):
            ttk.Button(save, text=f"{label} (.{ext})…",
                       command=lambda l=label, e=ext, f=encode: self.save(l, e, f)).grid(row=index, column=0, sticky="new", pady=5)
            self._label(save, text=text, share=.62).grid(row=index, column=1, sticky="w", padx=(18, 0), pady=(9, 5))
        self._label(save, text="The dataset itself (matrices, groups, axis and coordinates) is saved from the Data page "
                               "with Save dataset.", style="Muted.TLabel").grid(row=len(EXPORTS) + 2, column=0, columnspan=2,
                                                                                sticky="ew", pady=(12, 0))
        row += 1

        methods = ttk.Frame(self)
        methods.grid(row=row, sticky="ew", pady=(36, 0))
        methods.columnconfigure(0, weight=1)
        self.methods_box = ttk.Frame(methods)
        self.methods_box.columnconfigure(0, weight=1)
        toggle = ttk.Button(methods, text="Show methods text and settings")
        toggle.grid(row=0, column=0, sticky="w")

        def show_methods():
            if self.methods_box.winfo_manager():
                self.methods_box.grid_remove()
                toggle.configure(text="Show methods text and settings")
            else:
                self.methods_box.grid(row=1, column=0, sticky="ew", pady=(12, 0))
                toggle.configure(text="Hide methods text and settings")
        toggle.configure(command=show_methods)
        self._label(self.methods_box, text=self.result["methods"]).grid(row=0, sticky="ew")
        extra = {"settings": self.cfg, "reporting": self.result["reporting"], "axis": self.axis, "software": self.result["software"]}
        self.settings_text = json.dumps(extra, indent=2, ensure_ascii=False)
        buttons = ttk.Frame(self.methods_box)
        buttons.grid(row=1, sticky="w", pady=(12, 0))
        ttk.Button(buttons, text="Copy methods text", command=lambda: self.app.copy(self.result["methods"])).pack(side="left")
        ttk.Button(buttons, text="Complete settings", command=lambda: self.dialog_text("Complete settings", self.settings_text)).pack(side="left", padx=(10, 0))
        row += 1
        ttk.Button(self, text="Edit statistical model", command=lambda: self.app.show("model")).grid(row=row, sticky="w", pady=(28, 0))

    def _resize(self, event):
        if event.widget is not self:
            return
        for label, share in self.wrapped:
            if label.winfo_exists():
                label.configure(wraplength=max(200, int(event.width * share) - 12))
        wide = event.width >= 1080
        self.figure_area.grid(row=4, column=0, sticky="nsew", padx=(0, 24 if wide else 0))
        self.detail.grid(row=4 if wide else 5, column=1 if wide else 0, sticky="new", pady=(0 if wide else 20, 0))
        self._arrange_tabs(event.width)
        # Number tiles: four in a row, or two by two when narrow.
        columns = 4 if event.width >= 860 else 2
        for index, tile in enumerate(self.kpi_tiles):
            tile.grid(row=index // columns, column=index % columns, sticky="ew",
                      padx=(0, 12 if index % columns < columns - 1 else 0), pady=(0, 12 if index < columns and columns == 2 else 0))
        for index in range(4):
            self.kpis.columnconfigure(index, weight=1 if index < columns else 0, uniform="kpi" if index < columns else "")
        # Filters beside the Components heading, or below it when there is not enough room.
        if event.width >= 980:
            self.filters.grid(row=0, column=1, rowspan=2, sticky="se", pady=0)
            _flow(self.filters.winfo_children(), 10 ** 6, gap=18)
        else:
            self.filters.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
            _flow(self.filters.winfo_children(), event.width, gap=18, row_gap=10)
        self.explorer.columnconfigure(1, weight=0, minsize=270 if wide else 0)

    def _arrange_tabs(self, width):
        _flow(self.tab_buttons, width, gap=0)

    def _destroyed(self, event):
        if event.widget is self:
            self.stop()
            if self.redraw:
                self.after_cancel(self.redraw)
                self.redraw = None

    def _queue_draw(self, event):
        if event.width != self.last_width and not self.redraw:
            self.redraw = self.after_idle(self._draw_now)

    def _draw_now(self):
        self.redraw = None
        self.draw()

    # ----- data ---------------------------------------------------------------------------
    def apply_cutoff(self):
        try:
            alpha = validate_alpha(float(self.alpha.get()))
        except (ValueError, TypeError):
            messagebox.showerror("Reporting cutoff", "Enter a number greater than zero and less than one.", parent=self)
            return
        self.result["reporting"]["alpha"] = alpha
        refresh_report(self.result)
        self.refresh()

    def refresh(self):
        rows = sorted(self.components.values(), key=lambda c: (c["p_fwe"], -c["test_stat"], c["id"]))
        alpha = self.result["reporting"]["alpha"]
        passed = [c for c in rows if c["p_fwe"] <= alpha]
        n = len(passed)
        name = self.result.get("dataset_name") or getattr(self.app, "name", "")
        self.title.set(f"{n} significant component{'s' if n != 1 else ''}" if n else "No significant components")
        floor = 1 / (1 + self.cfg["n_perm"])
        line = (f"{n} of {len(rows)} observed components reached corrected p ≤ {alpha:g}." if n else
                f"No component reached corrected p ≤ {alpha:g} ({len(rows)} observed). This does not show that there is no effect.")
        if alpha < floor:
            line += f" With {self.cfg['n_perm']:,} permutations the smallest possible p is {floor:.4g}."
        self.headline.set(line)
        elapsed = self.result.get("elapsed_seconds")
        self.meta.set(" · ".join(part for part in (
            method_name(self.cfg, self.layers), name, f"{self.cfg['n_perm']:,} permutations",
            f"{self.axis['name']} {_range_label(self.axis['values'], self.axis['unit'])}" if self.layers > 1 else "",
            f"{elapsed:.1f} s" if isinstance(elapsed, (int, float)) else "") if part))
        self.kpi_values["Components"].configure(text=str(len(rows)))
        self.kpi_values["Significant"].configure(text=str(n))
        self.kpi_values["Smallest corrected p"].configure(text=f"{min(c['p_fwe'] for c in rows):.3g}" if rows else "–")
        self.kpi_values["Permutations"].configure(text=f"{self.cfg['n_perm']:,}")
        self.scope_buttons["Significant"].configure(text=f"Significant ({n})")
        self.scope_buttons["All observed"].configure(text=f"All ({len(rows)})")
        old = str(self.component["id"]) if self.component else None
        if self.tree.get_children():
            self.tree.delete(*self.tree.get_children())
        visible = passed if self.scope.get() == "Significant" else rows
        labels = self.data["node_labels"]
        for c in visible:
            values = [self.axis["values"][b - 1] for b in c["layer_bins"]]
            members = ", ".join(labels[i - 1] for i in c["nodes"][:4]) + (" …" if len(c["nodes"]) > 4 else "")
            self.tree.insert("", "end", iid=str(c["id"]), values=(
                c["id"], self._sign(c), f"{c['p_fwe']:.4g}", c["extent"],
                f"{c['intensity' if self.classic else 'mass']:.4g}", c["n_nodes"],
                self.cfg["classic_layer"] if self.classic else
                f"{_range_label(values, self.axis['unit'])} ({len(values)})", members))
        self.tree.configure(height=max(3, min(8, len(visible))))
        if visible:
            item = old if old and self.tree.exists(old) else str(visible[0]["id"])
            self.tree.selection_set(item)
            self.tree.focus(item)
            self.tree.see(item)
            self.empty.grid_remove()
        else:
            self.empty.grid()
            if self.components:
                text = (f"No component meets corrected p ≤ {alpha:g}. Choose All to explore the components that were observed.")
            else:
                text = "No edges exceeded the primary threshold, so no components were formed."
            self.empty.configure(text=text)
        self.select(force=True)

    def _sign(self, component):
        if self.cfg["stat_type"] == "f":
            return "F"
        return "+" if component["tail"] == "right" else "−"

    def select(self, force=False):
        selected = self.tree.selection()
        component = self.components[int(selected[0])] if selected else None
        if component is self.component and not force:
            return
        self.stop()
        self.component = component
        if not component:
            self.explorer.grid_remove()
            self.summary_block.grid_remove()
            return
        self.explorer.grid()
        self.summary_block.grid()
        self.geo = self._geometry(component)
        self.span = sorted(component["layer_bins"])
        self.span_index = 0
        self.layer.set(self.span[0])
        alpha = self.result["reporting"]["alpha"]
        self.component_title.configure(text=f"Component {component['id']}"
                                       + ("" if component["p_fwe"] <= alpha else "  (not significant)"))
        self._detail(component)
        self._report(component)
        self.change_tab()

    def _keep(self, tail):
        threshold = self.cfg["threshold"]
        return (self.statistic > threshold) if tail != "left" else (self.statistic < -threshold)

    def _geometry(self, component):
        keep = self._keep(component["tail"])
        layers, nodes = self.layers, self.data["nodes"]
        active = [set() for _ in range(layers)]
        for node, layer in component["sites"]:
            active[layer - 1].add(node - 1)
        degree = np.zeros((nodes, layers), dtype=int)
        comp_edges = [[] for _ in range(layers)]
        per = []
        for layer in range(layers):
            kept = np.flatnonzero(keep[:, layer])
            on = active[layer]
            all_nodes = set(self.edges[kept].ravel().tolist())
            inside = [k for k in kept if self.edges[k, 0] in on and self.edges[k, 1] in on]
            for k in inside:
                i, j = self.edges[k]
                degree[i, layer] += 1
                degree[j, layer] += 1
            comp_edges[layer] = inside
            per.append({"edges": len(inside), "nodes": len(on), "all_edges": len(kept), "all_nodes": len(all_nodes)})
        return {"keep": keep, "active": active, "degree": degree, "edges": comp_edges, "per": per}

    def _detail(self, c):
        for child in self.detail.winfo_children():
            child.destroy()
        alpha = self.result["reporting"]["alpha"]
        values = [self.axis["values"][b - 1] for b in c["layer_bins"]]
        labels = self.data["node_labels"]
        rows = [("Corrected p", f"{c['p_fwe']:.4g}" + ("" if c["p_fwe"] <= alpha else " (not significant)")),
                ("Effect", self._direction(c)),
                ("Extent", f"{c['extent']} {'edges' if self.classic else 'region–layer sites'}"),
                ("Intensity" if self.classic else "Mass", f"{c['intensity' if self.classic else 'mass']:.4g}"),
                ("Regions", str(c["n_nodes"]))]
        if self.classic:
            rows.append(("Input layer", f"{self.cfg['classic_layer']}"))
        else:
            rows += [("Layers", str(len(values))), (self.axis["name"], _range_label(values, self.axis["unit"]))]
        names = ", ".join(labels[i - 1] for i in c["nodes"][:8]) + (f" and {len(c['nodes']) - 8} more" if len(c["nodes"]) > 8 else "")
        rows.append(("Members", names))
        ttk.Label(self.detail, text=f"Component {c['id']}", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        for index, (key, value) in enumerate(rows, 1):
            ttk.Label(self.detail, text=key, style="CardMuted.TLabel").grid(row=index, column=0, sticky="nw", padx=(0, 14), pady=3)
            ttk.Label(self.detail, text=value, style="Card.TLabel", wraplength=170, justify="left").grid(row=index, column=1, sticky="nw", pady=3)

    def _direction(self, c):
        cfg = self.cfg
        if cfg["stat_type"] == "f":
            return "F contrast (no direction)"
        higher = c["tail"] != "left"
        if cfg["test"] == "two-sample":
            a, b = cfg["group_values"]
            return f"{a} {'>' if higher else '<'} {b}"
        if cfg["test"] == "paired":
            return f"First {'>' if higher else '<'} second within pairs"
        if cfg["test"] == "one-sample":
            return "Mean above zero" if higher else "Mean below zero"
        return "Positive GLM contrast" if higher else "Negative GLM contrast"

    def _report(self, c):
        cfg, axis = self.cfg, self.axis
        alpha = self.result["reporting"]["alpha"]
        values = [axis["values"][b - 1] for b in c["layer_bins"]]
        symbol = "F" if cfg["stat_type"] == "f" else ("mean" if cfg["stat_type"] == "mean" else "t")
        threshold = f"{symbol} {'< −' if cfg['tail'] == 'left' else '> '}{cfg['threshold']:g}" + (", two-sided" if cfg["tail"] == "both" else "")
        size = (f"extent = {c['extent']} {'edges' if self.classic else 'region–layer sites'}" if cfg["metric"] == "extent"
                else f"{cfg['metric']} = {c[cfg['metric']]:.3g}")
        n_edges = sum(len(e) for e in self.geo["edges"])
        where = (f"input layer {cfg['classic_layer']}" if self.classic else
                 f"{axis['name'].lower()} {_range_label(values, axis['unit'])}")
        self.report.set(
            f"A component showing {self._direction(c)} {'was identified' if c['p_fwe'] <= alpha else 'did not reach significance'} "
            f"(corrected p = {c['p_fwe']:.3g}; {size}; {c['n_nodes']} regions, {n_edges} edge{'s' if n_edges != 1 else ''}; "
            f"{where}; primary threshold {threshold}; {cfg['n_perm']:,} permutations; {method_name(cfg, self.layers)}).")
        notes = ["The corrected p-value applies to the component as a whole, not to individual regions, edges or layers."]
        null = np.asarray(self.result["null_max"], dtype=float)
        if cfg["metric"] == "extent" and len(null):
            sites = self.data["nodes"] * self.layers
            median = float(np.median(null))
            if not self.classic and median / sites > .05:
                notes.append(f"Chance components are large here (median {median:g} of {sites:,} sites), so components chain "
                             "readily at this threshold; consider a higher threshold.")
        if not self.classic and self.layers > 2 and (len(c["layer_bins"]) == self.layers or c["n_nodes"] >= .5 * self.data["nodes"]):
            notes.append(f"The component covers {c['n_nodes']} of {self.data['nodes']} regions and {len(c['layer_bins'])} of "
                         f"{self.layers} layers, so it is best described as a distributed effect.")
        if not self.classic:
            notes.append(f"The {axis['name'].lower()} span is descriptive. It is not a corrected estimate of where the effect "
                         "starts or stops.")
        if c["p_fwe"] <= 1 / (cfg["n_perm"] + 1) + 1e-12:
            notes.append(f"This p-value is the smallest possible with {cfg['n_perm']:,} permutations.")
        notes += self.result.get("interpretation", {}).get("warnings", [])
        self.notes.set("\n".join("•  " + note for note in notes))

    # ----- figures ------------------------------------------------------------------------
    def change_tab(self):
        self.stop()
        for frame in (self.overlay, self.player, self.display):
            for child in frame.winfo_children():
                child.destroy()
        self.overlay.place_forget()
        tab = self.tab.get()
        self.tab_hint.configure(text=TAB_HINTS["network" if tab == "brain" and not self.coords else tab])
        if tab == "membership":
            self._show_row([("Component regions only", self.only_members)])
        elif tab == "brain":
            if self.layers > 1:
                self._transport(self.player)
            if self.coords:
                segment = ttk.Frame(self.overlay, style="Segment.TFrame", padding=1)
                segment.pack()
                for value in ("Four views", "Left", "Right", "Axial", "Coronal"):
                    ttk.Radiobutton(segment, text=value, value=value, variable=self.view, style="SideSegment.Toolbutton",
                                    command=self.draw).pack(side="left")
                self.overlay.place(in_=self.plot, relx=1, x=-8, y=8, anchor="ne")
                self.overlay.lift()
                self._show_row([("Component edges", self.brain_options["edges"]),
                                ("Other edges above threshold", self.brain_options["other"]),
                                ("Region numbers", self.brain_options["numbers"]),
                                ("Sulci", self.brain_options["sulci"])])
        for frame in (self.player, self.display):
            (frame.grid if frame.winfo_children() else frame.grid_remove)()
        self.draw()

    def _show_row(self, options):
        """Display options, under the figure: a short label, then checkboxes that wrap when narrow."""
        self.display.columnconfigure(1, weight=1)
        ttk.Label(self.display, text="Show", style="Muted.TLabel").grid(row=0, column=0, sticky="nw", padx=(0, 16), pady=(2, 0))
        toggles = _flowing(ttk.Frame(self.display), gap=24, row_gap=6)
        toggles.grid(row=0, column=1, sticky="ew")
        for label, variable in options:
            ttk.Checkbutton(toggles, text=label, variable=variable, command=self.draw)

    def _transport(self, bar):
        """A player bar under the figure: step, play, a slider over the layers, the current value,
        then speed and loop (moved to a second line when the figure is narrow)."""
        bar.columnconfigure(3, weight=1)
        ttk.Button(bar, text="◀", style="Compact.TButton", command=lambda: self.step(-1)).grid(row=0, column=0)
        self.play = ttk.Button(bar, text="Play", width=5, style="Compact.TButton", command=self.toggle_play)
        self.play.grid(row=0, column=1, padx=6)
        ttk.Button(bar, text="▶", style="Compact.TButton", command=lambda: self.step(1)).grid(row=0, column=2, padx=(0, 16))
        self.slider = ttk.Scale(bar, from_=0, to=max(1, self.layers - 1), style="Player.Horizontal.TScale",
                                command=lambda value: self._slide(int(round(float(value)))))
        self.slider.grid(row=0, column=3, sticky="ew")
        ttk.Label(bar, textvariable=self.layer_text, width=10, anchor="e").grid(row=0, column=4, padx=(12, 0))
        options = ttk.Frame(bar)
        ttk.Label(options, text="Speed", style="Muted.TLabel").pack(side="left", padx=(0, 10))
        ttk.Combobox(options, textvariable=self.speed, values=list(SPEEDS), state="readonly",
                     width=max(len(value) for value in SPEEDS) + 2).pack(side="left", padx=(0, 20))
        ttk.Checkbutton(options, text="Loop", variable=self.loop).pack(side="left")

        options.grid(row=1, column=0, columnspan=5, sticky="w", pady=(10, 0))

    def _set_slider(self, index):
        if hasattr(self, "slider") and self.slider.winfo_exists() and round(float(self.slider.get())) != index:
            self.syncing = True
            try:
                self.slider.set(index)
            finally:
                self.syncing = False

    def _slide(self, index):
        if self.syncing:
            return
        self.layer.set(max(1, min(self.layers, index + 1)))
        self.draw()

    def step(self, increment):
        index = self.layer.get() - 1 + increment
        if index >= self.layers or index < 0:
            if not self.loop.get() and self.timer:
                self.stop()
                return
            index %= self.layers
        self._set_slider(index)
        self._slide(index)

    def toggle_play(self):
        if self.timer:
            self.stop()
            return
        self.play.configure(text="Pause")

        def tick():
            self.timer = self.after(SPEEDS.get(self.speed.get(), 500), tick)
            self.step(1)
        self.timer = self.after(SPEEDS.get(self.speed.get(), 500), tick)

    def stop(self):
        if self.timer:
            self.after_cancel(self.timer)
            self.timer = None
        if getattr(self, "play", None) is not None and self.play.winfo_exists():
            self.play.configure(text="Play")

    def draw(self, reset=False):
        if not self.component or not self.plot.winfo_exists():
            return
        self.pal = FIGURE.get(getattr(self.app, "theme", "light"), FIGURE["light"])
        p = self.pal
        self.bg, self.ink, self.muted, self.grid = p["bg"], p["ink"], p["muted"], p["grid"]
        self.axis_line, self.context, self.comp, self.node = p["axis"], p["context"], p["component"], p["node"]
        self.pt = float(self.tk.call("tk", "scaling"))
        width = max(420, self.plot.winfo_width())
        self.last_width = self.plot.winfo_width()
        c = self.plot
        c.configure(background=self.bg)
        c.delete("all")
        self.hover = None
        self.panels = []
        tab = self.tab.get()
        if tab == "brain":
            self._set_slider(self.layer.get() - 1)
        value = self.axis["values"][self.layer.get() - 1]
        self.layer_text.set(f"{value:g} {self.axis['unit']}".strip())
        height = {"profile": self.profile, "membership": self.membership, "brain": self.brain,
                  "layers": self.all_layers, "null": self.null_histogram}[tab](width)
        c.configure(height=height, scrollregion=(0, 0, width, height))

    # Text sizes are in points, like the rest of the interface, and drawn in pixels so exports match.
    def font(self, size=11, bold=False):
        px = -max(9, round(size * self.pt * .9))
        return (self.family, px, "bold") if bold else (self.family, px)

    def measure(self, text, size=11, bold=False):
        return font.Font(family=self.family, size=self.font(size)[1], weight="bold" if bold else "normal").measure(text)

    def text(self, x, y, text, anchor="w", size=11, color=None, bold=False, angle=0, tags=()):
        self.plot.create_text(x, y, text=text, anchor=anchor, fill=color or self.ink, angle=angle, tags=tags,
                              font=self.font(size, bold))

    def legend(self, x, y, items, align="left", size=11):
        """Items are (kind, colour, label, dash); kind is box or line. Laid out from measured text widths."""
        widths = [26 + self.measure(label, size) for _, _, label, _ in items]
        total = sum(widths) + 24 * (len(items) - 1)
        x = x - total if align == "right" else (x - total / 2 if align == "center" else x)
        for (kind, color, label, dash), width in zip(items, widths):
            if kind == "box":
                self.plot.create_rectangle(x, y - 7, x + 16, y + 7, fill=color, outline="")
            else:
                self.plot.create_line(x, y, x + 18, y, fill=color, width=3, dash=dash)
            self.text(x + 24, y, label, size=size, color=self.muted)
            x += width + 24
        return total

    def _y_axis(self, left, right, top, height, high, title):
        """Gridlines and labelled ticks for a count axis; returns the top value of the axis."""
        ticks = _nice_ticks(high)
        top_value = ticks[-1]
        label_width = max(self.measure(f"{tick:g}") for tick in ticks)
        for tick in ticks:
            y = top + height - height * tick / top_value
            self.plot.create_line(left, y, right, y, fill=self.grid if tick else self.axis_line)
            self.text(left - 10, y, f"{tick:g}", anchor="e", color=self.muted)
        self.text(left - 24 - label_width, top + height / 2, title, anchor="center", size=12, color=self.muted, angle=90)
        return top_value

    def _x_ticks(self, left, step, bottom, most=9, center=True):
        """Axis values under a layer axis, thinned so labels never touch."""
        labels = [f"{value:g}" for value in self.axis["values"]]
        widest = max(self.measure(label) for label in labels) + 16
        most = max(2, min(most, int(step * self.layers // widest)))
        for index in _ticks(self.layers, most):
            x = left + (index + (.5 if center else 0)) * step
            self.plot.create_line(x, bottom, x, bottom + 6, fill=self.axis_line)
            self.text(x, bottom + 20, labels[index], anchor="center", color=self.muted)
        unit = self.axis["unit"]
        self.text(left + step * self.layers / 2, bottom + 50, f"{self.axis['name']}{f' ({unit})' if unit else ''}",
                  anchor="center", size=12, color=self.muted)

    def _layout(self, box):
        """Circular region positions inside box = (x0, y0, x1, y1)."""
        n = self.data["nodes"]
        theta = np.arange(n) * (2 * math.pi / n) - math.pi / 2
        x0, y0, x1, y1 = box
        radius = min(x1 - x0, y1 - y0) / 2
        return np.column_stack(((x0 + x1) / 2 + radius * np.cos(theta), (y0 + y1) / 2 + radius * np.sin(theta)))

    def _projection(self, layout, box, sulci=False):
        """Region positions in box, with the MNI glass-brain outline drawn behind them when available."""
        if not self.coords:
            return self._layout(box)
        dims = {"Axial": (0, 1), "Coronal": (0, 2), "Sagittal": (1, 2)}[layout]
        coords = np.asarray(self.coords, dtype=float)[:, dims].copy()
        coords[:, 1] *= -1
        paths = []
        lo, hi = coords.min(axis=0), coords.max(axis=0)
        if str(self.data.get("coordinate_space") or "").lower().startswith("mni") and _mni_outlines():
            outline_box, paths = _mni_outlines()[{"Axial": "top", "Coronal": "back", "Sagittal": "side"}[layout]]
            lo = np.minimum(lo, outline_box[:2])
            hi = np.maximum(hi, np.add(outline_box[:2], outline_box[2:]))
        span = np.maximum(hi - lo, 1e-9)
        scale = min((box[2] - box[0]) / span[0], (box[3] - box[1]) / span[1])
        offset = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]) - (hi + lo) * scale / 2
        for kind, line in paths:
            if kind != "s" or sulci:
                self.plot.create_line(*(line * scale + offset).ravel(), fill=self.pal["outline"] if kind == "o" else self.pal["fine"],
                                      width=1.2 if kind == "o" else .7)
        return coords * scale + offset

    def _ramp_color(self, share):
        """A colour from the strength scale, interpolated smoothly; share runs from 0 (weakest) to 1."""
        ramp = self.pal["ramp"][1:]  # skip the faintest step so weak edges stay visible
        share = min(1.0, max(0.0, share)) * (len(ramp) - 1)
        low = int(share)
        high = min(low + 1, len(ramp) - 1)
        return _mix(ramp[high], ramp[low], share - low)

    def _edge_color(self, stat, threshold, strongest):
        return self._ramp_color(0 if strongest <= threshold else (stat - threshold) / (strongest - threshold))

    def _colour_bar(self, x, y, width, low, high, label):
        """A smooth colour bar with its label and the values at each end and the middle."""
        self.text(x, y, label, color=self.muted)
        x += self.measure(label) + 14
        steps = 64
        for i in range(steps):
            self.plot.create_rectangle(x + width * i / steps, y - 7, x + width * (i + 1) / steps + 1, y + 7,
                                       fill=self._ramp_color(i / (steps - 1)), outline="")
        for share, value in ((0, low), (.5, (low + high) / 2), (1, high)):
            tx = x + width * share
            self.plot.create_line(tx, y + 7, tx, y + 11, fill=self.pal["axis"])
            self.text(tx, y + 22, f"{value:.3g}", anchor="center", size=10, color=self.muted)
        return x + width

    def _draw_network(self, layer, pos, numbers=True, edge_width=2.2, radius=5.5, small=2.4):
        active = self.geo["active"][layer - 1]
        for k in self.geo["edges"][layer - 1]:
            i, j = self.edges[k]
            self.plot.create_line(*pos[i], *pos[j], fill=self.comp, width=edge_width)
        for i, (x, y) in enumerate(pos):
            on = i in active
            r = radius if on else small
            self.plot.create_oval(x - r, y - r, x + r, y + r, fill=self.comp if on else self.node,
                                  outline=self.bg if on else "")
            if on and numbers:
                self.text(x + radius + 3, y - radius - 4, str(i + 1), size=10, color=self.ink)

    def profile(self, w):
        per, span = self.geo["per"], self.span
        left, right = 112, w - 28
        step = (right - left) / self.layers
        title_y = 22
        panels = ((80, 230, "edges", "Edges above threshold", "Edges"),
                  (80 + 230 + 96, 170, "nodes", "Active regions", "Regions"))
        x0, x1 = left + (span[0] - 1) * step, left + span[-1] * step
        self.plot.create_rectangle(x0, panels[0][0] - 8, x1, panels[1][0] + panels[1][1], fill=self.pal["band"], outline="")
        self.legend(right, title_y, [("box", self.comp, f"Component {self.component['id']}", ()),
                                     ("box", self.context, "All edges above threshold, same sign", ()),
                                     ("box", self.pal["band"], "Layers the component spans", ())], align="right")
        for top, h, key, title, unit in panels:
            self.text(left, top - 30, title, size=13, bold=True)
            high = self._y_axis(left, right, top, h, max(1, max(p["all_" + key] for p in per)), unit)
            gap = max(1, min(6, step * .16))
            for index, p in enumerate(per):
                x = left + index * step
                for value, color in ((p["all_" + key], self.context), (p[key], self.comp)):
                    if value:
                        self.plot.create_rectangle(x + gap, top + h - h * value / high, x + step - gap, top + h, fill=color, outline="")
        bottom = panels[1][0] + panels[1][1]
        self._x_ticks(left, step, bottom)
        self.hover = ("profile", left, step, panels[0][0], bottom)
        self.note.set("Grey bars count everything above the threshold in each layer with the same sign as this component; "
                      "blue bars count the part that belongs to it. Point at a layer to read its values.")
        return bottom + 74

    def membership(self, w):
        c, geo = self.component, self.geo
        labels = self.data["node_labels"]
        first = {}
        for node, layer in c["sites"]:
            first[node] = min(layer, first.get(node, layer))
        totals = geo["degree"].sum(axis=1)
        if self.only_members.get():
            rows = sorted(c["nodes"], key=lambda n: (first[n], -totals[n - 1], n))
        else:
            rows = list(range(1, self.data["nodes"] + 1))
        ch = 40 if len(rows) <= 12 else (32 if len(rows) <= 20 else (26 if len(rows) <= 36 else 21))
        size = 12 if ch >= 26 else 11
        names = [labels[n - 1] if len(labels[n - 1]) <= 34 else labels[n - 1][:32] + "…" for n in rows]
        left = min(340, 28 + max(self.measure(name, size) for name in names))
        cw = max(8, min(110, (w - left - 24) / self.layers))
        top = 64
        high = max(1, int(geo["degree"].max()))
        ramp = self.pal["ramp"][1:]
        level = lambda d: min(len(ramp) - 1, int(round((d - 1) / max(1, high - 1) * (len(ramp) - 1)))) if high > 1 else 3
        empty = self.pal["empty"]
        members = set(c["nodes"])
        key = "Component edges at the region in that layer"
        start = 12
        self.text(start, 20, key, color=self.muted)
        x = start + self.measure(key) + 16
        for value in sorted({1, high} | set(range(1, high + 1, max(1, high // 5)))):
            self.plot.create_rectangle(x, 12, x + 24, 28, fill=ramp[level(value)], outline="")
            self.text(x + 12, 42, str(value), anchor="center", size=10, color=self.muted)
            x += 28
        other_x, other_y = x + 18, 20
        if other_x + 32 + self.measure("Not in the component") > w - 8:
            other_x, other_y = start, 62
            top += 30
        self.plot.create_rectangle(other_x, other_y - 8, other_x + 24, other_y + 8, fill=empty, outline=self.grid)
        self.text(other_x + 32, other_y, "Not in the component", color=self.muted)
        for r, (node, name) in enumerate(zip(rows, names)):
            self.text(left - 12, top + r * ch + ch / 2, name, anchor="e", size=size,
                      color=self.ink if node in members else self.muted)
            for layer in range(self.layers):
                d = geo["degree"][node - 1, layer]
                on = (node - 1) in geo["active"][layer]
                x = left + layer * cw
                self.plot.create_rectangle(x + 1, top + r * ch + 1, x + cw - 1, top + (r + 1) * ch - 1,
                                           fill=ramp[level(d)] if on else empty, outline="")
                if on and cw >= 24 and ch >= 24:
                    self.text(x + cw / 2, top + r * ch + ch / 2, str(d), anchor="center", size=11,
                              color=self.bg if level(d) >= 3 else self.ink)
        bottom = top + len(rows) * ch
        self._x_ticks(left, cw, bottom, most=10)
        self.hover = ("membership", left, cw, top, ch, rows)
        self.note.set("Each row is a region and each column a layer. A coloured cell means the region belongs to the "
                      "component in that layer; darker cells have more component edges. Extent counts the coloured cells. "
                      "Point at a cell to read it.")
        return bottom + 74

    def brain(self, w):
        layer = self.layer.get() - 1
        per = self.geo["per"][layer]
        value = f"{self.axis['values'][layer]:g} {self.axis['unit']}".strip()
        self.text(4, 18, f"{self.axis['name']} {value}", size=15, bold=True)
        self.text(4, 46, f"{per['nodes']} component regions · {per['edges']} component edges in this layer", color=self.muted)
        if not self.coords:
            h = int(max(400, min(620, w * .6)))
            pos = self._layout((w * .25, 84, w * .75, h - 24))
            self._draw_network(layer + 1, pos, numbers=self.data["nodes"] <= 40)
            self.note.set("Circular layout: positions are schematic. Add node coordinates on the Data page to see the "
                          "component on a brain.")
            return h
        coords = np.asarray(self.coords, dtype=float)
        mni = str(self.data.get("coordinate_space") or "").lower().startswith("mni") and bool(_mni_outlines())
        views = {"Left": ("side", lambda p: (-p[1], -p[2]), True, lambda p: p[0] <= 10),
                 "Right": ("side", lambda p: (p[1], -p[2]), False, lambda p: p[0] >= -10),
                 "Axial": ("top", lambda p: (p[0], -p[1]), False, lambda p: True),
                 "Coronal": ("back", lambda p: (p[0], -p[2]), False, lambda p: True)}
        top = 72
        single = self.view.get() != "Four views"
        if single:
            # One large view, centred.
            cell_h = int(min(620, w * .62))
            cells = [(self.view.get(), (w * .1, top, w * .9, top + cell_h))]
            bottom = top + cell_h
        else:
            # A boxed 2 x 2 grid: Left and Right on top, Axial and Coronal below.
            cell_w = (w - 8) / 2
            cell_h = int(min(380, cell_w * .74))
            x0, x1 = 4, w - 4
            cells = [("Left", (x0, top, x0 + cell_w, top + cell_h)),
                     ("Right", (x0 + cell_w, top, x1, top + cell_h)),
                     ("Axial", (x0, top + cell_h, x0 + cell_w, top + 2 * cell_h)),
                     ("Coronal", (x0 + cell_w, top + cell_h, x1, top + 2 * cell_h))]
            bottom = top + 2 * cell_h
            self.plot.create_rectangle(x0, top, x1, bottom, outline=self.pal["axis"], width=1)
            self.plot.create_line(x0 + cell_w, top, x0 + cell_w, bottom, fill=self.grid, width=1)
            self.plot.create_line(x0, top + cell_h, x1, top + cell_h, fill=self.grid, width=1)
        keep = self.geo["keep"][:, layer]
        active = self.geo["active"][layer]
        show_edges, show_other = self.brain_options["edges"].get(), self.brain_options["other"].get()
        numbers, sulci = self.brain_options["numbers"].get(), self.brain_options["sulci"].get()
        stats = np.abs(self.statistic[:, layer])
        threshold = float(self.cfg["threshold"])
        inside_stats = [stats[k] for k in self.geo["edges"][layer]]
        strongest = max(inside_stats) if inside_stats else threshold
        for name, (bx0, by0, bx1, by1) in cells:
            outline, project, mirror, side = views[name]
            title_y = by0 + 20
            self.text((bx0 + bx1) / 2, title_y, name, anchor="center", size=12, bold=True, color=self.muted)
            if name in ("Coronal", "Axial"):
                half = self.measure(name, 12, True) / 2 + 18
                self.text((bx0 + bx1) / 2 - half, title_y, "L", anchor="e", color=self.muted)
                self.text((bx0 + bx1) / 2 + half, title_y, "R", anchor="w", color=self.muted)
            points = np.array([project(p) for p in coords])
            paths = []
            if mni:
                box, paths = _mni_outlines()[outline]
                ox0, oy0, ow, oh = box
                if mirror:
                    ox0 = -(ox0 + ow)
                lo = np.minimum(points.min(axis=0), (ox0, oy0))
                hi = np.maximum(points.max(axis=0), (ox0 + ow, oy0 + oh))
            else:
                lo, hi = points.min(axis=0) - 5, points.max(axis=0) + 5
            span = np.maximum(hi - lo, 1e-9)
            inner = (bx0 + 16, by0 + 40, bx1 - 16, by1 - 14)
            scale = min((inner[2] - inner[0]) / span[0], (inner[3] - inner[1]) / span[1])
            offset = np.array([(inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2]) - (hi + lo) * scale / 2
            for kind, line in paths:
                if kind == "s" and not sulci:
                    continue
                pts = line.copy()
                if mirror:
                    pts[:, 0] *= -1
                self.plot.create_line(*(pts * scale + offset).ravel(), fill=self.pal["outline"] if kind == "o" else self.pal["fine"],
                                      width=1.4 if kind == "o" else (.8 if kind == "i" else .5))
            xy = points * scale + offset
            visible = [side(p) for p in coords]
            order = []
            for k in np.flatnonzero(keep):
                i, j = self.edges[k]
                if not (visible[i] and visible[j]):
                    continue
                inside = i in active and j in active
                if (inside and show_edges) or (not inside and show_other):
                    order.append((inside, stats[k], i, j))
            for inside, stat, i, j in sorted(order):
                if inside:
                    weight = (1.6 + 2.6 * (stat - threshold) / max(1e-9, strongest - threshold)) * (1.3 if single else 1)
                    self.plot.create_line(*xy[i], *xy[j], fill=self._edge_color(stat, threshold, strongest), width=weight)
                else:
                    self.plot.create_line(*xy[i], *xy[j], fill=self.context, width=.8)
            for i in range(len(xy)):
                if not visible[i]:
                    continue
                x, y = xy[i]
                on = i in active
                r = (7 if single else 5) if on else (2.8 if single else 2)
                self.plot.create_oval(x - r, y - r, x + r, y + r, fill=self.comp if on else self.node,
                                      outline=self.bg if on else "", width=1.5 if on else 1)
                if on and numbers:
                    self.text(x + r + 2, y - r - 4, str(i + 1), size=11 if single else 10, color=self.ink)
        bottom = int(bottom + 10)
        label = f"Component edge |{'F' if self.cfg['stat_type'] == 'f' else 't'}|"
        x = self._colour_bar(4, bottom + 14, 180, threshold, max(strongest, threshold), label) + 36
        self.legend(x, bottom + 14, [("box", self.comp, "Component region", ()), ("box", self.node, "Other region", ())]
                    + ([("line", self.context, "Other edge above threshold", ())] if show_other else []))
        self.note.set(("Glass-brain outlines from nilearn (MNI152). " if mni else
                       "No brain outline: the coordinates are not in MNI space. ")
                      + "Edge colour and thickness show the size of the edge statistic. Left and Right show regions on "
                        "that side or within 10 mm of the midline. Numbers match the member list.")
        return bottom + 50

    def all_layers(self, w):
        shown = self.span[:24]
        cols = max(1, min(len(shown), int((w - 16) // 240)))
        size = min(300, (w - 16) / cols)
        heading = (f"The {len(self.span)} layer{'s' if len(self.span) != 1 else ''} component {self.component['id']} spans"
                   + (" (first 24 shown)" if len(self.span) > 24 else ""))
        self.text(8, 18, heading, size=13, bold=True)
        top = 46
        current = self.layer.get()
        for index, l in enumerate(shown):
            x0 = 8 + (index % cols) * size
            y0 = top + (index // cols) * (size + 40)
            selected = l == current
            self.plot.create_rectangle(x0 + 4, y0, x0 + size - 4, y0 + size + 32,
                                       outline=self.comp if selected else self.grid, width=2.5 if selected else 1, fill="")
            p = self.geo["per"][l - 1]
            self.text(x0 + 16, y0 + 20, f"{self.axis['values'][l - 1]:g} {self.axis['unit']}".strip(), size=12, bold=True)
            counts = f"{p['nodes']} regions · {p['edges']} edges"
            self.text(x0 + size - 16, y0 + 20, counts, anchor="e", size=10, color=self.muted)
            pos = self._projection("Axial", (x0 + 22, y0 + 44, x0 + size - 22, y0 + size + 20))
            self._draw_network(l, pos, numbers=False, edge_width=1.8, radius=3.8, small=1.7)
            self.panels.append((x0 + 4, y0, x0 + size - 4, y0 + size + 32, l))
        rows = math.ceil(len(shown) / cols)
        self.note.set("Each panel is one layer of the component" + (" on an axial glass brain. " if self.coords else ", on a circular layout. ")
                      + "The outlined panel is the layer shown in the Brain tab. Click a panel to open it there.")
        return top + rows * (size + 40) + 6

    def null_histogram(self, w):
        draws = np.asarray(self.result["null_max"], dtype=float)
        observed = float(self.component["test_stat"])
        end = max(1.0, observed, float(draws.max()) if len(draws) else 1.0) * 1.1
        counts, limits = np.histogram(draws, bins=24, range=(0, end))
        left, right, top, bottom = 112, w - 30, 96, 386
        self.text(left, 22, "Largest component in each permutation", size=13, bold=True)
        high = self._y_axis(left, right, top, bottom - top, max(1, int(counts.max())), "Permutations")
        for i, count in enumerate(counts):
            if count:
                x1, x2 = left + (right - left) * limits[i:i + 2] / end
                self.plot.create_rectangle(x1 + 1, bottom - (bottom - top) * count / high, x2 - 1, bottom, fill=self.context, outline="")
        alpha = self.result["reporting"]["alpha"]
        ordered = np.sort(draws)[::-1]
        k = int(math.floor(alpha * (len(draws) + 1) + 1e-9)) - 1
        critical = None if k < 0 else (0.0 if k >= len(ordered) else float(ordered[k]))
        if critical is not None:
            x = left + (right - left) * critical / end
            self.plot.create_line(x, top - 10, x, bottom, fill=self.pal["critical"], width=2, dash=(3, 4))
        x = left + (right - left) * observed / end
        self.plot.create_line(x, top - 10, x, bottom, fill=self.comp, width=3)
        ticks = [t for t in _nice_ticks(end, 7) if t <= end]
        for tick in ticks:
            tx = left + (right - left) * tick / end
            self.plot.create_line(tx, bottom, tx, bottom + 6, fill=self.axis_line)
            self.text(tx, bottom + 20, f"{tick:g}", anchor="center", color=self.muted)
        self.text((left + right) / 2, bottom + 50, f"Size of the largest component ({self.cfg['metric']})", anchor="center",
                  size=12, color=self.muted)
        items = [("box", self.context, "Permutation maxima", ()),
                 ("line", self.comp, f"Component {self.component['id']} ({observed:g})", ())]
        if critical is not None:
            items.append(("line", self.pal["critical"], f"Critical value at α = {alpha:g} ({critical:g})", (3, 4)))
        self.legend(left, 54, items)
        exceed = int(np.count_nonzero(draws >= observed))
        self.note.set(f"Corrected p = (1 + {exceed} permutation maxima ≥ {observed:g}) / ({len(draws):,} + 1) = "
                      f"{self.component['p_fwe']:.4g}."
                      + (f" Components larger than {critical:g} are significant at α = {alpha:g}." if critical is not None else ""))
        return bottom + 74

    def _plot_click(self, event):
        if self.tab.get() != "layers":
            return
        for x0, y0, x1, y1, layer in self.panels:
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                self.layer.set(layer)
                self.tab.set("brain")
                self.change_tab()
                return

    def _tooltip(self, x, y, lines):
        c = self.plot
        c.delete("tooltip")
        width = c.winfo_width()
        box_w = max(self.measure(line, 11, index == 0) for index, line in enumerate(lines)) + 24
        line_h = round(11 * self.pt * .9) + 6
        box_h = line_h * len(lines) + 14
        left = x + 16 if x + 16 + box_w < width else x - 16 - box_w
        top = max(4, y - box_h - 10)
        c.create_rectangle(left, top, left + box_w, top + box_h, fill=self.ink, outline="", tags="tooltip")
        for index, line in enumerate(lines):
            c.create_text(left + 12, top + 7 + line_h * (index + .5), text=line, anchor="w", fill=self.bg,
                          font=self.font(11, index == 0), tags="tooltip")

    def _plot_motion(self, event):
        info = getattr(self, "hover", None)
        self.plot.delete("tooltip")
        if not info:
            return
        unit = self.axis["unit"]
        if info[0] == "profile":
            _, left, step, top, bottom = info
            index = int((event.x - left) // step)
            if 0 <= index < self.layers and event.x >= left and top - 10 <= event.y <= bottom:
                p = self.geo["per"][index]
                self._tooltip(event.x, event.y, [f"{self.axis['name']} {self.axis['values'][index]:g} {unit}".strip(),
                                                 f"Component: {p['edges']} edges, {p['nodes']} regions",
                                                 f"All above threshold: {p['all_edges']} edges, {p['all_nodes']} regions"])
        elif info[0] == "membership":
            _, left, cw, top, ch, rows = info
            col, row = int((event.x - left) // cw), int((event.y - top) // ch)
            if 0 <= col < self.layers and 0 <= row < len(rows) and event.x >= left and event.y >= top:
                node = rows[row]
                on = (node - 1) in self.geo["active"][col]
                d = self.geo["degree"][node - 1, col]
                self._tooltip(event.x, event.y, [self.data["node_labels"][node - 1],
                                                 f"{self.axis['name']} {self.axis['values'][col]:g} {unit}".strip(),
                                                 f"In the component, {d} edge{'s' if d != 1 else ''}" if on else "Not in the component"])

    # ----- dialogs and files --------------------------------------------------------------
    def dialog_text(self, title, body):
        win = tk.Toplevel(self)
        win.title(title)
        win.transient(self.winfo_toplevel())
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)
        colors = getattr(self.app, "colors", DEFAULT_COLORS)
        text = tk.Text(win, width=78, height=21, wrap="word", padx=17, pady=16,
                       font="TkTextFont", background=colors["plot"], foreground=colors["fg"],
                       insertbackground=colors["fg"], relief="flat")
        text.insert("1.0", body)
        text.configure(state="disabled")
        text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(win, orient="vertical", command=text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scroll.set)

        def copy():
            self.clipboard_clear()
            self.clipboard_append(body)
        ttk.Button(win, text="Copy text", command=copy).grid(row=1, column=0, sticky="w", padx=12, pady=13)
        ttk.Button(win, text="Close", command=win.destroy).grid(row=1, column=0, sticky="e", padx=12, pady=13)

    def methods(self):
        self.dialog_text("Methods and settings", self.result["methods"] + "\n\n" + self.settings_text)

    def members(self):
        labels = self.data["node_labels"]
        text = "\n".join(f"{n}. {labels[n - 1]}" for n in self.component["nodes"])
        self.dialog_text(f"Member regions · component {self.component['id']}", text)

    def save_figure(self):
        if not self.component:
            return
        tab = dict(TABS_STACK + TABS_SINGLE)[self.tab.get()]
        filename = filedialog.asksaveasfilename(parent=self, title="Save current figure", defaultextension=".svg",
            initialfile=f"component-{self.component['id']}-{tab.lower().replace(' ', '-').replace('×', 'x')}.svg",
            filetypes=[("SVG figure", "*.svg")])
        if filename:
            try:
                _write_file(filename, figure_svg(self.plot, f"{tab} · {component_summary(self.result, self.component)}", self.note.get()))
            except (OSError, ValueError, tk.TclError) as error:
                messagebox.showerror("Figure export", str(error), parent=self)

    def save(self, label, ext, encode):
        filename = filedialog.asksaveasfilename(parent=self, title=f"Save {label.lower()}", defaultextension="." + ext,
                                                filetypes=[(label, "*." + ext)], initialfile=f"multiplex-nbs-results.{ext}")
        if filename:
            try:
                _write_file(filename, encode(self.result))
            except (OSError, ValueError) as error:
                messagebox.showerror("Result export", str(error), parent=self)
