"""Render the app's Overview schematic (classic, layer-wise and multiplex NBS) as SVG for the README.

    python tools/render_overview_figure.py

Writes docs/images/methods-overview.svg (light) and methods-overview-dark.svg (dark).
The drawing is produced by the same function the desktop app uses
(multiplex_nbs.native_figures.draw_method_figure), so the README matches the app.
Needs Tk and a display.
"""
import html
import math
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font

root_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root_dir))
from multiplex_nbs.native_app import DARK, LIGHT  # noqa: E402
from multiplex_nbs.native_figures import CAPTIONS, METHODS, draw_method_figure  # noqa: E402

FIG_W, FIG_H = 780, 370      # one figure, as drawn in the app
TEXT_W = 330                 # caption column
PAD, GAP = 36, 18
FAMILY = "Helvetica Neue, Helvetica, Arial, sans-serif"


def wrap(text, measure, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if measure(trial) > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def items_to_svg(canvas, dx, dy):
    """Convert the canvas drawing to SVG elements, offset by (dx, dy)."""
    out = []
    for item in canvas.find_all():
        kind, coords = canvas.type(item), canvas.coords(item)
        get = lambda option: canvas.itemcget(item, option)  # noqa: E731
        pts = [(x + dx, y + dy) for x, y in zip(coords[::2], coords[1::2])]
        if kind == "polygon":
            points = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            out.append(f'<polygon points="{points}" fill="{get("fill")}" stroke="{get("outline")}" '
                       f'stroke-width="{get("width")}"/>')
        elif kind == "oval":
            (x0, y0), (x1, y1) = pts
            fill, stroke = get("fill") or "none", get("outline") or "none"
            out.append(f'<ellipse cx="{(x0 + x1) / 2:.1f}" cy="{(y0 + y1) / 2:.1f}" rx="{(x1 - x0) / 2:.1f}" '
                       f'ry="{(y1 - y0) / 2:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{get("width")}"/>')
        elif kind == "arc":
            (x0, y0), (x1, y1) = pts
            cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
            start, extent = math.radians(float(get("start"))), math.radians(float(get("extent")))
            steps = 40
            path = " ".join(f"{'M' if i == 0 else 'L'}{cx + rx * math.cos(start + extent * i / steps):.2f} "
                            f"{cy - ry * math.sin(start + extent * i / steps):.2f}" for i in range(steps + 1))
            out.append(f'<path d="{path}" fill="none" stroke="{get("outline")}" stroke-width="{get("width")}" '
                       f'stroke-linecap="round"/>')
        elif kind == "line":
            path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
            dash = get("dash")
            extra = f' stroke-dasharray="{" ".join(canvas.tk.splitlist(dash))}"' if dash else ""
            if get("arrow") == "last":
                extra += f' marker-end="url(#arrow-{get("fill").lstrip("#")})"'
            out.append(f'<path d="{path}" fill="none" stroke="{get("fill")}" stroke-width="{get("width")}" '
                       f'stroke-linecap="round"{extra}/>')
        elif kind == "text":
            parts = canvas.tk.splitlist(get("font"))
            weight = "600" if any(str(p) == "bold" for p in parts[2:]) else "400"
            anchor = {"w": "start", "e": "end"}.get(get("anchor"), "middle")
            (x, y), = pts
            out.append(f'<text x="{x:.1f}" y="{y:.1f}" fill="{get("fill")}" font-family="{FAMILY}" '
                       f'font-size="{abs(int(parts[1]))}" font-weight="{weight}" text-anchor="{anchor}" '
                       f'dominant-baseline="central">{html.escape(get("text"))}</text>')
    return out


def render(window, canvas, colors, target):
    heading = font.Font(family="Helvetica Neue", size=-26, weight="bold")
    body = font.Font(family="Helvetica Neue", size=-16)
    row_h = FIG_H + GAP
    width = PAD * 2 + TEXT_W + FIG_W
    height = PAD * 2 + row_h * len(METHODS) - GAP
    defs = set()
    elements = [f'<rect width="100%" height="100%" rx="10" fill="{colors["field"]}"/>']
    for row, (mode, name) in enumerate(METHODS.items()):
        top = PAD + row * row_h
        draw_method_figure(canvas, colors, "Helvetica Neue", mode)
        window.update()
        for item in canvas.find_all():
            if canvas.type(item) == "line" and canvas.itemcget(item, "arrow") == "last":
                defs.add(canvas.itemcget(item, "fill"))
        elements += items_to_svg(canvas, PAD + TEXT_W, top)
        elements.append(f'<text x="{PAD}" y="{top + 54}" fill="{colors["paper"]}" font-family="{FAMILY}" '
                        f'font-size="26" font-weight="600">{html.escape(name)}</text>')
        for index, line in enumerate(wrap(CAPTIONS[mode], body.measure, TEXT_W - 30)):
            elements.append(f'<text x="{PAD}" y="{top + 94 + index * 24}" fill="{colors["paper_muted"]}" '
                            f'font-family="{FAMILY}" font-size="16">{html.escape(line)}</text>')
        if row < len(METHODS) - 1:
            y = top + FIG_H + GAP / 2
            elements.append(f'<line x1="{PAD}" y1="{y}" x2="{width - PAD}" y2="{y}" stroke="{colors["grid"]}"/>')
    markers = "".join(f'<marker id="arrow-{c.lstrip("#")}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" '
                      f'markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{c}"/></marker>'
                      for c in sorted(defs))
    title = "Classic, layer-wise and multiplex NBS on one network measured at four time points or frequencies"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height:.0f}" '
           f'viewBox="0 0 {width} {height:.0f}" role="img" aria-label="{title}"><title>{title}</title>'
           f'<defs>{markers}</defs>{"".join(elements)}</svg>\n')
    target.write_text(svg, encoding="utf-8")
    print("wrote", target.relative_to(root_dir), f"{target.stat().st_size / 1e3:.0f} kB")


images = root_dir / "docs" / "images"
images.mkdir(parents=True, exist_ok=True)
window = tk.Tk()
canvas = tk.Canvas(window, width=FIG_W, height=FIG_H, highlightthickness=0)
canvas.pack()
window.update()
render(window, canvas, LIGHT, images / "methods-overview.svg")
render(window, canvas, DARK, images / "methods-overview-dark.svg")
window.destroy()
