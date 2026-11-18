"""Schematic figures drawn on Tk canvases: the method diagram and small explanatory sketches."""
from tkinter import font

METHODS = {
    "classic": "Classic NBS",
    "layerwise": "Layer-wise NBS",
    "multiplex": "Multiplex-NBS",
}

CAPTIONS = {
    "classic": ("Classic NBS tests the network at one time point or frequency chosen in advance. Edges above "
                "the threshold that share regions form a component (here A–B–C), and its size is compared with "
                "the largest component found by chance."),
    "layerwise": ("Layer-wise NBS runs classic NBS at every time point or frequency. Each component stays at its "
                  "own point, and one permutation correction covers all of them together."),
    "multiplex": ("Multiplex-NBS links a region to itself at the next time point or frequency while it stays "
                  "active (dashed lines), so an effect that persists forms one component and is tested once."),
}


def follow_width(label, smallest=140, largest=760, slack=6):
    """Wrap a label to its own width. The slack and the 4 px dead band stop a label and its
    container from resizing each other forever (a 1 px oscillation in grid layouts)."""
    state = {"at": None}

    def reflow(event):
        width = max(smallest, min(largest, event.width))
        if state["at"] is None or abs(width - state["at"]) > 4:
            state["at"] = width
            label.configure(wraplength=width - slack)
    label.bind("<Configure>", reflow, add=True)
    return label


def mix(color, background, amount):
    """`color` drawn at `amount` opacity over `background` (Tk has no alpha)."""
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(background[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * amount + y * (1 - amount)):02x}" for x, y in zip(a, b))


def _edge_arc(canvas, P, x, ya, yb, color, width, tag):
    """An edge between two regions in the same panel: a true half-ellipse bulging to the right.
    Native arcs render as clean curves; splined polylines can look wobbly at small sizes."""
    (x0, y0), (x1, y1) = P(x - 22.5, ya), P(x + 22.5, yb)
    canvas.create_arc(x0, y0, x1, y1, start=-90, extent=180, style="arc", outline=color, width=width, tags=tag)


def draw_method_figure(canvas, c, family, mode, legend=True, labels=True):
    """Regions A–F in four tilted panels: one network at successive time points or frequencies.

    The drawing is the original overview figure; the panels sit along a time or frequency axis."""
    canvas.configure(bg=c["field"])
    canvas.delete("all")
    width, height = canvas.winfo_width(), canvas.winfo_height()
    if width < 120 or height < 100:
        return
    classic, linked = mode == "classic", mode == "multiplex"
    legend_h = 44 if legend else 6
    top, bottom = 30, (346 if labels else 284)  # drawing extent in figure units
    scale = min(width / 640, (height - legend_h) / (bottom - top))
    ox = (width - 630 * scale) / 2
    oy = max(0, (height - legend_h - (bottom - top) * scale) / 2) - top * scale

    def P(x, y):
        return ox + x * scale, oy + y * scale

    label_px = -max(11, round(23 * scale))
    small_px = -max(10, round(17 * scale))
    points = (103, 251, 399, 547)
    rows = (72, 108, 144, 180, 216, 252)
    component = {0: ((0, 1), (1, 2)), 1: ((2, 3),), 2: ((3, 4),), 3: ((4, 5),)}

    def dim(color, point):
        return mix(color, c["field"], .21) if classic and point else color

    if labels:
        for row, y in enumerate(rows):
            canvas.create_text(*P(27, y), text=chr(65 + row), font=(family, label_px, "bold"), fill=c["paper_muted"])
    for point, x in enumerate(points):
        plate = [v for px, py in ((-30, 60), (40, 36), (40, 248), (-30, 272)) for v in P(x + px, py)]
        canvas.create_polygon(*plate, fill=dim(c["plate"], point), outline=dim(c["plate_edge"], point),
                              width=max(1, scale * 1.1), tags="plane")
        grid = dim(c["grid"], point)
        canvas.create_line(*P(x, 50), *P(x, 262), fill=grid)
        for y in (115, 185, 255):
            canvas.create_line(*P(x - 30, y), *P(x + 40, y - 24), fill=grid)
        if point and linked:
            # The same region at the previous point.
            y = rows[component[point][0][0]]
            canvas.create_line(*P(points[point - 1] + 6, y), *P(x - 6, y), fill=c["wire"],
                               width=max(1.5, 2 * scale), dash=(7, 6), tags="coupling")
        edges = component[point]
        for a, b in edges:
            _edge_arc(canvas, P, x, rows[a], rows[b], dim(c["wire"], point), max(2, 3 * scale), "retained")
        if point == 3:
            # A second, separate component at the last point.
            _edge_arc(canvas, P, x, rows[0], rows[1], dim(c["paper_muted"], point), max(1.5, 2 * scale), "context")
        members = {n for edge in edges for n in edge}
        for row, y in enumerate(rows):
            cx, cy = P(x, y)
            if row in members or (point == 3 and row in (0, 1)):
                fill = c["wire"] if row in members else c["paper_muted"]
                r = 5.7 * scale
                canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=dim(fill, point),
                                   outline=c["field"], width=max(1, 1.5 * scale), tags="region")
            else:
                r = 2.8 * scale
                canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=dim(c["node"], point), outline="")
    if labels:
        # The ordered axis: the same network measured at successive time points or frequencies.
        axis = c["paper_muted"]
        canvas.create_line(*P(60, 292), *P(608, 292), fill=axis, width=max(1, 1.2 * scale), arrow="last",
                           arrowshape=(9 * scale, 11 * scale, 4 * scale))
        for point, x in enumerate(points):
            canvas.create_line(*P(x + 5, 287), *P(x + 5, 297), fill=axis, width=max(1, 1.2 * scale))
            canvas.create_text(*P(x + 5, 310), text=str(point + 1), font=(family, small_px), fill=dim(axis, point))
        canvas.create_text(*P(334, 334), text="Time or frequency", font=(family, small_px, "bold"), fill=axis)
    if not legend:
        return
    text_px = -max(12, round(16 * scale))
    y = height - legend_h / 2
    items = [("Edge above threshold", ())]
    if linked:
        items.append(("Same region at the next point", (5, 4)))
    measure = font.Font(family=family, size=text_px)
    total = sum(24 + measure.measure(label) for label, _ in items) + 30 * (len(items) - 1)
    x = (width - total) / 2
    for label, dash in items:
        if dash:
            canvas.create_line(x, y, x + 18, y, fill=c["wire"], width=2, dash=dash)
        else:
            # The same curved mark as the edges in the figure.
            canvas.create_arc(x - 2, y - 8, x + 16, y + 8, start=-90, extent=180, style="arc", outline=c["wire"], width=2)
        canvas.create_text(x + 26, y, text=label, anchor="w", font=(family, text_px), fill=c["paper_muted"])
        x += 24 + measure.measure(label) + 30


def draw_null_sketch(canvas, c, family):
    """A schematic permutation distribution with the observed and critical component sizes."""
    canvas.configure(bg=c["field"])
    canvas.delete("all")
    width, height = canvas.winfo_width(), canvas.winfo_height()
    if width < 200 or height < 120:
        return
    left, right, top, bottom = 40, width - 30, 26, height - 58
    counts = (2, 9, 16, 21, 18, 13, 9, 6, 4, 3, 2, 1, 1, 0, 0, 0, 0, 0)
    step = (right - left) / len(counts)
    canvas.create_line(left, bottom, right, bottom, fill=c["paper_muted"])
    for index, count in enumerate(counts):
        if count:
            x = left + index * step
            canvas.create_rectangle(x + 2, bottom - (bottom - top) * count / 21, x + step - 2, bottom,
                                    fill=mix(c["paper_muted"], c["field"], .45), outline="")
    critical = left + 10.5 * step
    observed = left + 15.5 * step
    canvas.create_line(critical, top - 6, critical, bottom, fill=c["paper"], width=1.5, dash=(2, 4))
    canvas.create_line(observed, top - 6, observed, bottom, fill=c["wire"], width=3, dash=(6, 4))
    canvas.create_text(critical - 6, top, text="critical value", anchor="e", fill=c["paper_muted"], font=(family, -12))
    canvas.create_text(observed - 6, top, text="observed", anchor="e", fill=c["wire"], font=(family, -12, "bold"))
    canvas.create_text((left + right) / 2, bottom + 18, text="Size of the largest component in each permutation",
                       fill=c["paper_muted"], font=(family, -13))
    canvas.create_text((left + right) / 2, bottom + 40, text="p = (1 + permutations at least as large) / (1 + permutations)",
                       fill=c["paper"], font=(family, -13, "bold"))


def draw_data_sketch(canvas, c, family):
    """Participants × regions × regions × layers, drawn as a stack of matrices per participant."""
    canvas.configure(bg=c["field"])
    canvas.delete("all")
    width, height = canvas.winfo_width(), canvas.winfo_height()
    if width < 260 or height < 140:
        return
    size = min(96, height - 74)
    people = 3
    gap = (width - 40) / people
    for person in range(people):
        x0 = 20 + person * gap + (gap - size - 36) / 2
        y0 = 22
        for layer in range(3, -1, -1):
            dx, dy = layer * 12, layer * 9
            fill = mix(c["plate"], c["field"], 1 - layer * .18)
            canvas.create_rectangle(x0 + dx, y0 + dy, x0 + dx + size, y0 + dy + size, fill=fill,
                                    outline=mix(c["plate_edge"], c["field"], 1 - layer * .2))
        cells = 6
        cell = size / cells
        for i in range(cells):
            for j in range(cells):
                if i != j and (min(i, j) * 5 + max(i, j) * 3 + person) % 4 == 0:  # symmetric, like connectivity
                    canvas.create_rectangle(x0 + j * cell + 2, y0 + i * cell + 2, x0 + (j + 1) * cell - 2,
                                            y0 + (i + 1) * cell - 2, fill=c["wire"], outline="")
        label = ("Participant 1", "Participant 2", "…  Participant n")[person]
        canvas.create_text(x0 + size / 2 + 18, y0 + size + 44, text=label, fill=c["paper_muted"], font=(family, -13))
    canvas.create_text(width / 2, height - 12, text="Each participant: regions × regions, one matrix per layer "
                       "(time point or frequency bin)", fill=c["paper"], font=(family, -13))
