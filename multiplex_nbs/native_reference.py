"""Reference pages drawn with desktop widgets: one layout, short sections and explanatory figures."""
import tkinter as tk
from tkinter import ttk

from . import __version__
from .native_figures import METHODS, draw_data_sketch, draw_method_figure, draw_null_sketch, follow_width


TOPICS = {
    "method": "Choose a method",
    "interpret": "Interpret a result",
    "inputs": "Prepare inputs",
    "cite": "Citations and credits",
}

LEADS = {
    "method": ("All three methods threshold the edge statistics, group the edges that pass into connected components, "
               "and give each component one family-wise corrected p-value by permutation. They differ in what counts "
               "as connected."),
    "interpret": "The corrected p-value belongs to the whole component, not to any single region, edge or layer.",
    "inputs": ("One undirected connectivity matrix per participant, or one matrix per layer, with the same regions "
               "in the same order for everyone."),
    "cite": f"Multiplex-NBS {__version__}. Record the version and your settings (shown with every result) when you report an analysis.",
}


def paragraph(parent, text, style="TLabel", pady=(0, 12)):
    label = ttk.Label(parent, text=text, style=style, justify="left", anchor="w", wraplength=650)
    label.pack(anchor="w", fill="x", pady=pady)
    return follow_width(label, 140, 760)


def section(parent, title, text=None, bullets=()):
    ttk.Label(parent, text=title, style="Heading.TLabel").pack(anchor="w", pady=(30, 10))
    if text:
        paragraph(parent, text)
    for item in bullets:
        paragraph(parent, "•  " + item, pady=(0, 8))


def _figure(app, parent, draw, height, **options):
    """A canvas sketch that follows the window width and the colour mode."""
    canvas = tk.Canvas(parent, height=height, width=1, bd=0, highlightthickness=0)
    canvas.pack(fill="x", pady=(18, 6))
    redraw = lambda _event=None: draw(canvas, app.colors, app.family, **options)
    canvas.bind("<Configure>", redraw)
    canvas.bind("<<ThemeChanged>>", redraw)
    return canvas


def _method_cards(app, parent):
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(18, 0))
    details = {
        "classic": ("Use for one network, or one layer chosen in advance.",
                    "Component size: edges (extent) or summed excess over the threshold (intensity)."),
        "layerwise": ("Use to find which layers show an effect, with one correction across all of them.",
                      "Component size: region–layer sites (extent) or summed statistics (mass), within a layer."),
        "multiplex": ("Use when an effect may continue across neighbouring frequencies or time points.",
                      "Component size: region–layer sites (extent) or summed statistics (mass), across layers."),
    }
    cards = []
    for key, name in METHODS.items():
        card = ttk.Frame(row, style="Card.TFrame", padding=(18, 16, 18, 18))
        cards.append(card)
        ttk.Label(card, text=name, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))
        canvas = tk.Canvas(card, height=150, width=1, bd=0, highlightthickness=0)
        canvas.pack(fill="x", pady=(0, 12))
        redraw = lambda _event=None, c=canvas, k=key: draw_method_figure(c, app.colors, app.family, k, legend=False, labels=False)
        canvas.bind("<Configure>", redraw)
        canvas.bind("<<ThemeChanged>>", redraw)
        use, size = details[key]
        for text, style in ((use, "Card.TLabel"), (size, "CardMuted.TLabel")):
            label = ttk.Label(card, text=text, style=style, wraplength=240, justify="left")
            label.pack(anchor="w", fill="x", pady=(0, 6))
            follow_width(label, 160, 600)

    def arrange(event):
        columns = 3 if event.width >= 840 else 1
        for index, card in enumerate(cards):
            card.grid(row=index // columns, column=index % columns, sticky="nsew",
                      padx=(0, 14 if columns == 3 and index < 2 else 0), pady=(0, 0 if columns == 3 else 14))
        for index in range(3):
            row.columnconfigure(index, weight=1 if columns == 3 else 0, uniform="method" if columns == 3 else "")
        row.columnconfigure(0, weight=1)
    row.bind("<Configure>", arrange)


def reference_page(app, parent, topic):
    ttk.Label(parent, text="REFERENCE", style="Kicker.TLabel").pack(anchor="w")
    ttk.Label(parent, text=TOPICS[topic], style="PageTitle.TLabel").pack(anchor="w", pady=(6, 14))
    paragraph(parent, LEADS[topic], "Lead2.TLabel", pady=(0, 6))

    if topic == "method":
        _method_cards(app, parent)
        section(parent, "How the correction works", bullets=(
            "Compute a test statistic for every edge in every layer, such as Welch's t for two groups.",
            "Keep the edges above the primary threshold and find the connected components.",
            "Repeat with shuffled labels many times and record the largest component each time. A component's "
            "corrected p is the share of permutations with a component at least as large.",
        ))
        toggle = ttk.Button(parent, text="If you used the original NBS toolbox")
        toggle.pack(anchor="w", pady=(20, 0))
        details = ttk.Frame(parent)

        def show_details():
            if details.winfo_manager():
                details.pack_forget()
            else:
                details.pack(fill="x", after=toggle)
        toggle.configure(command=show_details)
        section(details, "Differences from NBS Connectome v1.2", bullets=(
            "A design matrix and contrast give the same GLM t or F test. The two-group shortcut uses Welch's t.",
            "Classic one-sample tests threshold the signed mean, as in v1.2. Multiplex one-sample tests use a t statistic.",
            "Corrected p uses (1 + exceedances) / (1 + permutations); v1.2 uses exceedances / permutations.",
        ))
    elif topic == "interpret":
        _figure(app, parent, draw_null_sketch, 230)
        section(parent, "What you can say", "The network differed between conditions across this set of regions "
                "and layers, with the corrected p-value for the component.")
        section(parent, "What you cannot say", bullets=(
            "That any one edge, region or layer inside the component is significant on its own.",
            "That the first and last layers mark where the effect starts or stops. The span is descriptive.",
        ))
        section(parent, "Decide in advance", "Choose the method, threshold, tail and component measure before "
                "looking at results. Trying several settings and keeping the best one adds comparisons that the "
                "correction does not cover.")
        section(parent, "Assumptions", bullets=(
            "Shuffling group labels assumes participants are exchangeable when there is no effect.",
            "Sign flips (paired and one-sample tests) assume differences are symmetric around zero under the null.",
            "Residual permutation with covariates (Freedman–Lane) is approximate.",
        ))
        section(parent, "Example", "In the demo, Classic NBS at 100 ms found a component of 3 edges joining 4 "
                "regions (intensity 8.36, corrected p = .010; threshold 3, 99 permutations, seed 1).")
    elif topic == "inputs":
        _figure(app, parent, draw_data_sketch, 210)
        section(parent, "One combined file", bullets=(
            "Python .npz: W with shape participants × regions × regions × layers, for example (40, 32, 32, 8).",
            "MATLAB v7 .mat: W as regions × regions × layers × participants, or a cell array with one entry per participant.",
            "Leave out the layer dimension for one network per participant. Matrices must be real, finite and symmetric.",
        ))
        section(parent, "One ZIP per group", "Put each participant's .mat or .npy file (or .csv, .tsv, .txt for one "
                "network) in a folder for its group and zip each folder. Participants are ordered by file name.")
        section(parent, "Study design", bullets=(
            "Two groups: one group label per participant.",
            "Paired conditions: each pair ID appears twice; the first observation is compared with the second.",
            "One sample: signed maps tested against zero.",
            "GLM: a design matrix X (one row per participant) and a contrast C.",
        ))
        section(parent, "Layers and coordinates", bullets=(
            "axis_name, axis_unit and axis_values label the layers, for example Frequency, Hz, 1–100.",
            "node_coordinates (regions × 3, MNI mm) enable the brain view; node_labels name the regions.",
        ))
    else:
        section(parent, "Original method", "Zalesky A, Fornito A, Bullmore ET. Network-based statistic: identifying "
                "differences in brain networks. NeuroImage (2010) 53: 1197–1207. doi:10.1016/j.neuroimage.2010.06.041")
        ttk.Button(parent, text="Copy DOI link",
                   command=lambda: app.copy("https://doi.org/10.1016/j.neuroimage.2010.06.041")).pack(anchor="w")
        section(parent, "Software contributors", "Minarose M. Ismail¹˒² · Brady J. Williamson³ · Darren S. Kadis¹˒²")
        paragraph(parent, "¹ Department of Physiology, University of Toronto, Toronto, Canada\n"
                          "² Neurosciences & Mental Health, The Hospital for Sick Children, Toronto, Canada\n"
                          "³ Department of Radiology, College of Medicine, University of Cincinnati, Cincinnati, USA",
                  "Muted.TLabel")
        section(parent, "Example data", "The brain demo uses 32 regions of the openly licensed structural connectome "
                "of Škoch et al. (2022), with AAL centroids (Tzourio-Mazoyer et al., 2002). Participants, groups, "
                "layers and effects are simulated.")
        section(parent, "Licence and source code", "Multiplex-NBS is free software under the GNU General Public "
                "License v3 or later. The Python package, MATLAB toolbox, documentation and downloads are at "
                "github.com/Minarose/multiplex-nbs.")
        ttk.Button(parent, text="Copy project link",
                   command=lambda: app.copy("https://github.com/Minarose/multiplex-nbs")).pack(anchor="w")
        section(parent, "Further reading", "Sassenhagen J, Draschkow D. Cluster-based permutation tests of MEG/EEG "
                "data do not establish significance of effect latency or location. Psychophysiology (2019) 56: e13335.")
    ttk.Separator(parent).pack(fill="x", pady=(36, 22))
    ttk.Button(parent, text="Return to " + app.page_title(app.return_page), command=lambda: app.show(app.return_page)).pack(anchor="w")
