// SVG figures for the browser app. They follow the desktop app's figures (native_results.py and
// native_figures.py): the same layouts, palettes and wording, drawn as SVG so they can be saved.

// The desktop app uses Helvetica Neue on macOS and Segoe UI on Windows.
export const FONT = '"Helvetica Neue", "Segoe UI", Helvetica, Arial, sans-serif';

// Figure palettes. YlGnBu (ColorBrewer) orders counts and edge strengths; reversed on dark backgrounds.
export const FIGURE = {
  light: { bg: "#ffffff", ink: "#132523", muted: "#4f6460", grid: "#e3eceb", axis: "#97aaa7",
           context: "#c3cfcd", component: "#00695c", band: "#e7f3f1", node: "#b7c6c3",
           outline: "#7d918d", fine: "#cbd8d6", critical: "#132523", empty: "#f0f5f4",
           ramp: ["#c7e9b4", "#7fcdbb", "#41b6c4", "#1d91c0", "#225ea8", "#253494"] },
  dark: { bg: "#1b1f1f", ink: "#e2e6e5", muted: "#9aa2a0", grid: "#262c2c", axis: "#4a5352",
          context: "#66706e", component: "#80cbc4", band: "#1f2b2a", node: "#5f6a68",
          outline: "#68726f", fine: "#30393a", critical: "#d9dedc", empty: "#212626",
          ramp: ["#253494", "#225ea8", "#1d91c0", "#41b6c4", "#7fcdbb", "#c7e9b4"] },
  mono: { bg: "#1c1c1c", ink: "#e6e6e6", muted: "#9c9c9c", grid: "#282828", axis: "#555555",
          context: "#6c6c6c", component: "#ececec", band: "#262626", node: "#626262",
          outline: "#6e6e6e", fine: "#333333", critical: "#9c9c9c", empty: "#222222",
          ramp: ["#3a3a3a", "#585858", "#7a7a7a", "#a0a0a0", "#c8c8c8", "#ececec"] },
};

// Interface colours used by the Overview schematic (native_app LIGHT / DARK / MONO).
export const TOKENS = {
  light: { field: "#e7f1f0", plate: "#d0e5e2", plate_edge: "#4f8f87", grid: "#bad4d0", node: "#6f918c",
           wire: "#00695c", paper: "#10302c", paper_muted: "#3f5e59" },
  dark: { field: "#1b1f1f", plate: "#232b2a", plate_edge: "#4a6b66", grid: "#2c3636", node: "#56625f",
          wire: "#80cbc4", paper: "#e2e6e5", paper_muted: "#9aa2a0" },
  mono: { field: "#1c1c1c", plate: "#262626", plate_edge: "#6a6a6a", grid: "#303030", node: "#5a5a5a",
          wire: "#e6e6e6", paper: "#e6e6e6", paper_muted: "#9c9c9c" },
};

export const esc = (value) => String(value).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/** Python-style %g formatting with the given number of significant digits. */
export function fmt(x, digits = 6) {
  if (x === null || x === undefined) return "";
  if (!Number.isFinite(x)) return String(x);
  if (x === 0) return "0";
  let s = Number(x).toPrecision(digits);
  if (s.includes("e")) {
    let [mantissa, exponent] = s.split("e");
    if (mantissa.includes(".")) mantissa = mantissa.replace(/\.?0+$/, "");
    const e = parseInt(exponent, 10);
    return `${mantissa}e${e < 0 ? "-" : "+"}${String(Math.abs(e)).padStart(2, "0")}`;
  }
  return s.includes(".") ? s.replace(/\.?0+$/, "") : s;
}

/** `color` drawn at `amount` opacity over `background`. */
export function mix(color, background, amount) {
  const a = [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16));
  const b = [1, 3, 5].map((i) => parseInt(background.slice(i, i + 2), 16));
  return "#" + a.map((x, k) => Math.round(x * amount + b[k] * (1 - amount)).toString(16).padStart(2, "0")).join("");
}

const r = (v) => Math.round(v * 100) / 100;
const context2d = document.createElement("canvas").getContext("2d");
export const fontPx = (size) => Math.max(10, Math.round(size * 1.2));
export function measure(text, size = 11, bold = false) {
  context2d.font = `${bold ? 600 : 400} ${fontPx(size)}px ${FONT}`;
  return context2d.measureText(String(text)).width;
}

function niceTicks(high, most = 6) {
  if (high <= 0) return [0, 1];
  const raw = high / (most - 1);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  let step = magnitude;
  for (const multiple of [1, 2, 5, 10]) {
    step = multiple * magnitude;
    if (high / step <= most - 1) break;
  }
  if (Number.isInteger(high)) step = Math.max(1, Math.round(step));
  const count = Math.ceil(high / step - 1e-9);
  return Array.from({ length: count + 1 }, (_, i) => Math.round(i * step * 1e10) / 1e10);
}

function tickIndices(count, most = 8) {
  if (count <= most) return Array.from({ length: count }, (_, i) => i);
  return [...new Set(Array.from({ length: most }, (_, i) => Math.round(i * (count - 1) / (most - 1))))].sort((a, b) => a - b);
}

export function rangeLabel(values, unit) {
  const text = values.length === 1 ? fmt(values[0]) : `${fmt(values[0])}–${fmt(values[values.length - 1])}`;
  return `${text} ${unit}`.trim();
}

class Plot {
  constructor(width, pal) {
    this.w = width;
    this.pal = pal;
    this.out = [];
  }
  add(markup) { this.out.push(markup); }
  rect(x, y, w, h, fill, { stroke = "none", sw = 1, title = "", cls = "", data = "" } = {}) {
    if (w <= 0 || h <= 0) return;
    this.add(`<rect x="${r(x)}" y="${r(y)}" width="${r(w)}" height="${r(h)}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"`
      + `${cls ? ` class="${cls}"` : ""}${data}>${title ? `<title>${esc(title)}</title>` : ""}</rect>`);
  }
  line(x1, y1, x2, y2, stroke, width = 1, dash = null) {
    this.add(`<line x1="${r(x1)}" y1="${r(y1)}" x2="${r(x2)}" y2="${r(y2)}" stroke="${stroke}" stroke-width="${r(width)}"`
      + `${dash ? ` stroke-dasharray="${dash.join(" ")}"` : ` stroke-linecap="round"`}/>`);
  }
  circle(cx, cy, radius, fill, stroke = "none", sw = 1, title = "") {
    this.add(`<circle cx="${r(cx)}" cy="${r(cy)}" r="${r(radius)}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}">`
      + `${title ? `<title>${esc(title)}</title>` : ""}</circle>`);
  }
  text(x, y, text, { anchor = "w", size = 11, color = null, bold = false, angle = 0 } = {}) {
    const align = { w: "start", e: "end", center: "middle" }[anchor] || "start";
    const rotate = angle ? ` transform="rotate(${-angle} ${r(x)} ${r(y)})"` : "";
    this.add(`<text x="${r(x)}" y="${r(y)}" dy=".35em" text-anchor="${align}" font-size="${fontPx(size)}"`
      + `${bold ? ' font-weight="600"' : ""} fill="${color || this.pal.ink}"${rotate}>${esc(text)}</text>`);
  }
  svg(height) {
    const h = Math.ceil(height);
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${this.w}" height="${h}" viewBox="0 0 ${this.w} ${h}" `
      + `font-family='${FONT}'><rect width="${this.w}" height="${h}" fill="${this.pal.bg}"/>${this.out.join("")}</svg>`;
  }
}

/* --------------------------------------------------------------------------------------------
   Overview schematic: regions A–F in four tilted panels, one network at successive time points
   or frequencies (the desktop app's draw_method_figure, in figure units).
   ------------------------------------------------------------------------------------------ */
export function methodFigure(theme, mode, { labels = true, legend = true } = {}) {
  const c = TOKENS[theme] || TOKENS.light;
  const classic = mode === "classic", linked = mode === "multiplex";
  const points = [103, 251, 399, 547];
  const rows = [72, 108, 144, 180, 216, 252];
  const component = { 0: [[0, 1], [1, 2]], 1: [[2, 3]], 2: [[3, 4]], 3: [[4, 5]] };
  const dim = (color, point) => (classic && point ? mix(color, c.field, 0.21) : color);
  const out = [];
  const arc = (x, ya, yb, color, width) =>
    out.push(`<path d="M${x} ${ya}A22.5 ${(yb - ya) / 2} 0 0 1 ${x} ${yb}" fill="none" stroke="${color}" stroke-width="${width}"/>`);
  if (labels) rows.forEach((y, row) => out.push(`<text x="27" y="${y}" dy=".35em" text-anchor="middle" font-size="21" font-weight="600" fill="${c.paper_muted}">${String.fromCharCode(65 + row)}</text>`));
  points.forEach((x, point) => {
    const plate = [[-30, 60], [40, 36], [40, 248], [-30, 272]].map(([dx, y]) => `${x + dx},${y}`).join(" ");
    out.push(`<polygon points="${plate}" fill="${dim(c.plate, point)}" stroke="${dim(c.plate_edge, point)}" stroke-width="1.1"/>`);
    const grid = dim(c.grid, point);
    out.push(`<line x1="${x}" y1="50" x2="${x}" y2="262" stroke="${grid}"/>`);
    for (const y of [115, 185, 255]) out.push(`<line x1="${x - 30}" y1="${y}" x2="${x + 40}" y2="${y - 24}" stroke="${grid}"/>`);
    if (point && linked) {
      const y = rows[component[point][0][0]];
      out.push(`<line x1="${points[point - 1] + 6}" y1="${y}" x2="${x - 6}" y2="${y}" stroke="${c.wire}" stroke-width="2" stroke-dasharray="7 6"/>`);
    }
    const edges = component[point];
    for (const [a, b] of edges) arc(x, rows[a], rows[b], dim(c.wire, point), 3);
    if (point === 3) arc(x, rows[0], rows[1], dim(c.paper_muted, point), 2);
    const members = new Set(edges.flat());
    rows.forEach((y, row) => {
      if (members.has(row) || (point === 3 && row < 2)) {
        const fill = members.has(row) ? c.wire : c.paper_muted;
        out.push(`<circle cx="${x}" cy="${y}" r="5.7" fill="${dim(fill, point)}" stroke="${c.field}" stroke-width="1.5"/>`);
      } else {
        out.push(`<circle cx="${x}" cy="${y}" r="2.8" fill="${dim(c.node, point)}"/>`);
      }
    });
  });
  const axis = c.paper_muted;
  let bottom = 284;
  if (labels) {
    // The ordered axis: the same network measured at successive time points or frequencies.
    out.push(`<line x1="60" y1="292" x2="599" y2="292" stroke="${axis}" stroke-width="1.2"/>`);
    out.push(`<polygon points="608,292 597,288 599,292 597,296" fill="${axis}"/>`);
    points.forEach((x, point) => {
      out.push(`<line x1="${x + 5}" y1="287" x2="${x + 5}" y2="297" stroke="${axis}" stroke-width="1.2"/>`);
      out.push(`<text x="${x + 5}" y="310" dy=".35em" text-anchor="middle" font-size="16" fill="${dim(axis, point)}">${point + 1}</text>`);
    });
    out.push(`<text x="334" y="334" dy=".35em" text-anchor="middle" font-size="16" font-weight="600" fill="${axis}">Time or frequency</text>`);
    bottom = 346;
  }
  if (legend) {
    // The legend, drawn under the figure as in the desktop app.
    const y = bottom + 26;
    const items = [["Edge above threshold", false]].concat(linked ? [["Same region at the next point", true]] : []);
    const widths = items.map(([label]) => 24 + measure(label, 16 / 1.2));
    let x = (630 - (widths.reduce((a, b) => a + b, 0) + 30 * (items.length - 1))) / 2;
    items.forEach(([label, dashed], index) => {
      out.push(dashed
        ? `<line x1="${x}" y1="${y}" x2="${x + 18}" y2="${y}" stroke="${c.wire}" stroke-width="2" stroke-dasharray="5 4"/>`
        : `<path d="M${x + 7} ${y - 8}A9 8 0 0 1 ${x + 7} ${y + 8}" fill="none" stroke="${c.wire}" stroke-width="2"/>`);
      out.push(`<text x="${x + 26}" y="${y}" dy=".35em" font-size="16" fill="${c.paper_muted}">${esc(label)}</text>`);
      x += widths[index] + 30;
    });
    bottom = y + 18;
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 26 640 ${bottom - 22}" font-family='${FONT}' role="img" `
    + `aria-label="Schematic of connected components across four time points or frequencies">${out.join("")}</svg>`;
}

/** A schematic permutation distribution with the observed and critical component sizes (reference page). */
export function nullSketch(theme, width) {
  const c = TOKENS[theme] || TOKENS.light;
  const height = 230;
  const left = 40, right = width - 30, top = 26, bottom = height - 58;
  const counts = [2, 9, 16, 21, 18, 13, 9, 6, 4, 3, 2, 1, 1, 0, 0, 0, 0, 0];
  const step = (right - left) / counts.length;
  const out = [`<rect width="${width}" height="${height}" fill="${c.field}"/>`,
               `<line x1="${left}" y1="${bottom}" x2="${right}" y2="${bottom}" stroke="${c.paper_muted}"/>`];
  counts.forEach((count, index) => {
    if (!count) return;
    const x = left + index * step;
    const h = (bottom - top) * count / 21;
    out.push(`<rect x="${r(x + 2)}" y="${r(bottom - h)}" width="${r(step - 4)}" height="${r(h)}" fill="${mix(c.paper_muted, c.field, 0.45)}"/>`);
  });
  const critical = left + 10.5 * step, observed = left + 15.5 * step;
  out.push(`<line x1="${r(critical)}" y1="${top - 6}" x2="${r(critical)}" y2="${bottom}" stroke="${c.paper}" stroke-width="1.5" stroke-dasharray="2 4"/>`);
  out.push(`<line x1="${r(observed)}" y1="${top - 6}" x2="${r(observed)}" y2="${bottom}" stroke="${c.wire}" stroke-width="3" stroke-dasharray="6 4"/>`);
  out.push(`<text x="${r(critical - 6)}" y="${top}" dy=".35em" text-anchor="end" font-size="12" fill="${c.paper_muted}">critical value</text>`);
  out.push(`<text x="${r(observed - 6)}" y="${top}" dy=".35em" text-anchor="end" font-size="12" font-weight="600" fill="${c.wire}">observed</text>`);
  out.push(`<text x="${(left + right) / 2}" y="${bottom + 18}" dy=".35em" text-anchor="middle" font-size="13" fill="${c.paper_muted}">Maximum component statistic in each permutation</text>`);
  out.push(`<text x="${(left + right) / 2}" y="${bottom + 40}" dy=".35em" text-anchor="middle" font-size="13" font-weight="600" fill="${c.paper}">p = (1 + permutations at least as large) / (1 + permutations)</text>`);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family='${FONT}'>${out.join("")}</svg>`;
}

/** Participants × regions × regions × layers, drawn as a stack of matrices per participant (reference page). */
export function dataSketch(theme, width) {
  const c = TOKENS[theme] || TOKENS.light;
  const height = 210;
  const size = Math.min(96, height - 74);
  const people = 3, gap = (width - 40) / people;
  const out = [`<rect width="${width}" height="${height}" fill="${c.field}"/>`];
  for (let person = 0; person < people; person++) {
    const x0 = 20 + person * gap + (gap - size - 36) / 2, y0 = 22;
    for (let layer = 3; layer >= 0; layer--) {
      const dx = layer * 12, dy = layer * 9;
      out.push(`<rect x="${r(x0 + dx)}" y="${y0 + dy}" width="${size}" height="${size}" fill="${mix(c.plate, c.field, 1 - layer * 0.18)}" stroke="${mix(c.plate_edge, c.field, 1 - layer * 0.2)}"/>`);
    }
    const cells = 6, cell = size / cells;
    for (let i = 0; i < cells; i++) {
      for (let j = 0; j < cells; j++) {
        if (i !== j && (Math.min(i, j) * 5 + Math.max(i, j) * 3 + person) % 4 === 0) {
          out.push(`<rect x="${r(x0 + j * cell + 2)}" y="${r(y0 + i * cell + 2)}" width="${r(cell - 4)}" height="${r(cell - 4)}" fill="${c.wire}"/>`);
        }
      }
    }
    const label = ["Participant 1", "Participant 2", "…  Participant n"][person];
    out.push(`<text x="${r(x0 + size / 2 + 18)}" y="${y0 + size + 44}" dy=".35em" text-anchor="middle" font-size="13" fill="${c.paper_muted}">${label}</text>`);
  }
  out.push(`<text x="${width / 2}" y="${height - 12}" dy=".35em" text-anchor="middle" font-size="13" fill="${c.paper}">Each participant: regions × regions, one matrix per layer (time point or frequency bin)</text>`);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family='${FONT}'>${out.join("")}</svg>`;
}

/* --------------------------------------------------------------------------------------------
   Results figures
   ------------------------------------------------------------------------------------------ */

/** Per-layer membership, degrees and counts for one component (native _geometry). */
export function geometry(result, comp) {
  const layers = result.dimensions.n_layers, nodes = result.dimensions.n_nodes;
  const statistic = result.statistic, threshold = result.config.threshold;
  const edges = result.edges.map(([a, b]) => [a - 1, b - 1]);
  const negative = comp.tail === "left";
  const active = Array.from({ length: layers }, () => new Set());
  for (const [node, layer] of comp.sites) active[layer - 1].add(node - 1);
  const degree = Array.from({ length: nodes }, () => new Array(layers).fill(0));
  const kept = [], compEdges = [], per = [];
  for (let l = 0; l < layers; l++) {
    const keep = [], inside = [], touched = new Set();
    for (let k = 0; k < edges.length; k++) {
      const value = statistic[k][l];
      if (negative ? value < -threshold : value > threshold) {
        keep.push(k);
        const [i, j] = edges[k];
        touched.add(i);
        touched.add(j);
        if (active[l].has(i) && active[l].has(j)) {
          inside.push(k);
          degree[i][l] += 1;
          degree[j][l] += 1;
        }
      }
    }
    kept.push(keep);
    compEdges.push(inside);
    per.push({ edges: inside.length, nodes: active[l].size, all_edges: keep.length, all_nodes: touched.size });
  }
  return { edges, kept, active, degree, compEdges, per, layers, nodes };
}

/**
 * Draw one results tab. f = {tab, width, theme, result, comp, geo, layer, view, only, opts, outlines}.
 * Returns {svg, note, panels}.
 */
export function drawResult(f) {
  const pal = FIGURE[f.theme] || FIGURE.light;
  const P = new Plot(Math.max(420, Math.floor(f.width)), pal);
  const ctx = {
    ...f, P, pal, w: P.w,
    axis: f.result.dataset.axis,
    cfg: f.result.config,
    layers: f.result.dimensions.n_layers,
    labels: f.result.dataset.node_labels,
    coords: f.result.dataset.node_coordinates,
    mni: String(f.result.dataset.coordinate_space || "").toLowerCase().startsWith("mni") && !!f.outlines,
    span: [...f.comp.layer_bins].sort((a, b) => a - b),
    panels: [], note: "",
  };
  const height = { profile, membership, brain, layers: allLayers, null: nullHistogram }[f.tab](ctx);
  return { svg: P.svg(height), note: ctx.note, panels: ctx.panels };
}

function legend(ctx, x, y, items, align = "left", size = 11) {
  const { P, pal } = ctx;
  const widths = items.map(([, , label]) => 26 + measure(label, size));
  const total = widths.reduce((a, b) => a + b, 0) + 24 * (items.length - 1);
  x = align === "right" ? x - total : align === "center" ? x - total / 2 : x;
  items.forEach(([kind, color, label, dash], index) => {
    if (kind === "box") P.rect(x, y - 7, 16, 14, color);
    else P.line(x, y, x + 18, y, color, 3, dash);
    P.text(x + 24, y, label, { size, color: pal.muted });
    x += widths[index] + 24;
  });
  return total;
}

function yAxis(ctx, left, right, top, height, high, title) {
  const { P, pal } = ctx;
  const ticks = niceTicks(high);
  const topValue = ticks[ticks.length - 1];
  const labelWidth = Math.max(...ticks.map((t) => measure(fmt(t))));
  for (const tick of ticks) {
    const y = top + height - height * tick / topValue;
    P.line(left, y, right, y, tick ? pal.grid : pal.axis);
    P.text(left - 10, y, fmt(tick), { anchor: "e", color: pal.muted });
  }
  P.text(left - 24 - labelWidth, top + height / 2, title, { anchor: "center", size: 12, color: pal.muted, angle: 90 });
  return topValue;
}

function xTicks(ctx, left, step, bottom, most = 9, center = true) {
  const { P, pal, axis, layers } = ctx;
  const labels = axis.values.map((v) => fmt(v));
  const widest = Math.max(...labels.map((label) => measure(label))) + 16;
  most = Math.max(2, Math.min(most, Math.floor(step * layers / widest)));
  for (const index of tickIndices(layers, most)) {
    const x = left + (index + (center ? 0.5 : 0)) * step;
    P.line(x, bottom, x, bottom + 6, pal.axis);
    P.text(x, bottom + 20, labels[index], { anchor: "center", color: pal.muted });
  }
  const unit = axis.unit;
  P.text(left + step * layers / 2, bottom + 50, `${axis.name}${unit ? ` (${unit})` : ""}`,
         { anchor: "center", size: 12, color: pal.muted });
}

const value = (ctx, layer) => `${fmt(ctx.axis.values[layer - 1])} ${ctx.axis.unit}`.trim();

function profile(ctx) {
  const { P, pal, w, geo, span, layers, comp } = ctx;
  const per = geo.per;
  const left = 112, right = w - 28;
  const step = (right - left) / layers;
  const panels = [[80, 230, "edges", "Number of suprathreshold edges", "Edges"],
                  [80 + 230 + 96, 170, "nodes", "Number of participating regions", "Regions"]];
  const x0 = left + (span[0] - 1) * step, x1 = left + span[span.length - 1] * step;
  P.rect(x0, panels[0][0] - 8, x1 - x0, panels[1][0] + panels[1][1] - panels[0][0] + 8, pal.band);
  legend(ctx, right, 22, [["box", pal.component, `Component ${comp.id}`],
                          ["box", pal.context, "All suprathreshold edges, same sign"],
                          ["box", pal.band, "Layers the component spans"]], "right");
  for (const [top, h, key, title, unit] of panels) {
    P.text(left, top - 30, title, { size: 13, bold: true });
    const high = yAxis(ctx, left, right, top, h, Math.max(1, ...per.map((p) => p["all_" + key])), unit);
    const gap = Math.max(1, Math.min(6, step * 0.16));
    per.forEach((p, index) => {
      const x = left + index * step;
      for (const [count, color] of [[p["all_" + key], pal.context], [p[key], pal.component]]) {
        if (count) P.rect(x + gap, top + h - h * count / high, step - 2 * gap, h * count / high, color);
      }
    });
  }
  const bottom = panels[1][0] + panels[1][1];
  // Invisible columns carry the per-layer values as tooltips.
  per.forEach((p, index) => {
    P.rect(left + index * step, panels[0][0] - 8, step, bottom - panels[0][0] + 8, "transparent", {
      title: `${ctx.axis.name} ${value(ctx, index + 1)}\n${p.all_edges} edges above threshold, ${p.edges} in component ${comp.id}`
        + `\n${p.all_nodes} active regions, ${p.nodes} in component ${comp.id}` });
  });
  xTicks(ctx, left, step, bottom);
  ctx.note = "Grey bars count everything above the threshold in each layer with the same sign as this component; "
    + "coloured bars count the part that belongs to it. Point at a layer to read its values.";
  return bottom + 74;
}

function membership(ctx) {
  const { P, pal, w, geo, comp, layers, labels } = ctx;
  const first = {};
  for (const [node, layer] of comp.sites) first[node] = Math.min(layer, first[node] ?? layer);
  const totals = geo.degree.map((row) => row.reduce((a, b) => a + b, 0));
  const rows = ctx.only
    ? [...comp.nodes].sort((a, b) => first[a] - first[b] || totals[b - 1] - totals[a - 1] || a - b)
    : Array.from({ length: geo.nodes }, (_, i) => i + 1);
  const ch = rows.length <= 12 ? 40 : rows.length <= 20 ? 32 : rows.length <= 36 ? 26 : 21;
  const size = ch >= 26 ? 12 : 11;
  const names = rows.map((n) => { const name = String(labels[n - 1]); return name.length <= 34 ? name : name.slice(0, 32) + "…"; });
  const left = Math.min(340, 28 + Math.max(...names.map((name) => measure(name, size))));
  const cw = Math.max(8, Math.min(110, (w - left - 24) / layers));
  let top = 64;
  const high = Math.max(1, ...geo.degree.flat());
  const ramp = pal.ramp.slice(1);
  const level = (d) => (high > 1 ? Math.min(ramp.length - 1, Math.round((d - 1) / Math.max(1, high - 1) * (ramp.length - 1))) : 3);
  const members = new Set(comp.nodes);
  const key = "Component edges at the region in that layer";
  P.text(12, 20, key, { color: pal.muted });
  let x = 12 + measure(key) + 16;
  const steps = new Set([1, high]);
  for (let v = 1; v <= high; v += Math.max(1, Math.floor(high / 5))) steps.add(v);
  for (const v of [...steps].sort((a, b) => a - b)) {
    P.rect(x, 12, 24, 16, ramp[level(v)]);
    P.text(x + 12, 42, String(v), { anchor: "center", size: 10, color: pal.muted });
    x += 28;
  }
  let otherX = x + 18, otherY = 20;
  if (otherX + 32 + measure("Not in the component") > w - 8) {
    otherX = 12;
    otherY = 62;
    top += 30;
  }
  P.rect(otherX, otherY - 8, 24, 16, pal.empty, { stroke: pal.grid });
  P.text(otherX + 32, otherY, "Not in the component", { color: pal.muted });
  rows.forEach((node, row) => {
    P.text(left - 12, top + row * ch + ch / 2, names[row], { anchor: "e", size, color: members.has(node) ? pal.ink : pal.muted });
    for (let layer = 0; layer < layers; layer++) {
      const d = geo.degree[node - 1][layer];
      const on = geo.active[layer].has(node - 1);
      const x0 = left + layer * cw;
      P.rect(x0 + 1, top + row * ch + 1, cw - 2, ch - 2, on ? ramp[level(d)] : pal.empty, {
        title: `${labels[node - 1]} · ${ctx.axis.name} ${value(ctx, layer + 1)}\n`
          + (on ? `${d} component edge${d === 1 ? "" : "s"}` : "Not in the component") });
      if (on && cw >= 24 && ch >= 24) {
        P.text(x0 + cw / 2, top + row * ch + ch / 2, String(d), { anchor: "center", size: 11, color: level(d) >= 3 ? pal.bg : pal.ink });
      }
    }
  });
  const bottom = top + rows.length * ch;
  xTicks(ctx, left, cw, bottom, 10);
  ctx.note = "Each row is a region and each column a layer. A coloured cell means the region belongs to the component in "
    + "that layer; darker cells have more component edges. Extent counts the coloured cells. Point at a cell to read it.";
  return bottom + 74;
}

function rampColor(pal, share) {
  const ramp = pal.ramp.slice(1);
  const s = Math.min(1, Math.max(0, share)) * (ramp.length - 1);
  const low = Math.floor(s), high = Math.min(low + 1, ramp.length - 1);
  return mix(ramp[high], ramp[low], s - low);
}

function colourBar(ctx, x, y, width, low, high, label) {
  const { P, pal } = ctx;
  P.text(x, y, label, { color: pal.muted });
  x += measure(label) + 14;
  const steps = 64;
  for (let i = 0; i < steps; i++) {
    P.rect(x + width * i / steps, y - 7, width / steps + 1, 14, rampColor(pal, i / (steps - 1)));
  }
  for (const [share, v] of [[0, low], [0.5, (low + high) / 2], [1, high]]) {
    const tx = x + width * share;
    P.line(tx, y + 7, tx, y + 11, pal.axis);
    P.text(tx, y + 22, fmt(v, 3), { anchor: "center", size: 10, color: pal.muted });
  }
  return x + width;
}

function circleLayout(n, [x0, y0, x1, y1]) {
  const radius = Math.min(x1 - x0, y1 - y0) / 2;
  return Array.from({ length: n }, (_, i) => {
    const theta = i * (2 * Math.PI / n) - Math.PI / 2;
    return [(x0 + x1) / 2 + radius * Math.cos(theta), (y0 + y1) / 2 + radius * Math.sin(theta)];
  });
}

function outlinePaths(ctx, view, scale, offset, mirror, { sulci = false, widths = [1.4, 0.8, 0.5] } = {}) {
  const { P, pal } = ctx;
  const parts = [`<g transform="translate(${r(offset[0])} ${r(offset[1])}) scale(${r(mirror ? -scale : scale * 1)} ${r(scale)})" fill="none">`];
  for (const path of ctx.outlines[view].paths) {
    if (path.k === "s" && !sulci) continue;
    const width = path.k === "o" ? widths[0] : path.k === "i" ? widths[1] : widths[2];
    parts.push(`<path d="${path.d}" stroke="${path.k === "o" ? pal.outline : pal.fine}" stroke-width="${width}" vector-effect="non-scaling-stroke"/>`);
  }
  parts.push("</g>");
  P.add(parts.join(""));
}

/** Fit projected points (and the outline box) into a screen box; returns [scale, offset]. */
function fit(points, box, outlineBox) {
  let lo = [Infinity, Infinity], hi = [-Infinity, -Infinity];
  for (const [x, y] of points) {
    lo = [Math.min(lo[0], x), Math.min(lo[1], y)];
    hi = [Math.max(hi[0], x), Math.max(hi[1], y)];
  }
  if (outlineBox) {
    const [ox, oy, ow, oh] = outlineBox;
    lo = [Math.min(lo[0], ox), Math.min(lo[1], oy)];
    hi = [Math.max(hi[0], ox + ow), Math.max(hi[1], oy + oh)];
  } else {
    lo = [lo[0] - 5, lo[1] - 5];
    hi = [hi[0] + 5, hi[1] + 5];
  }
  const span = [Math.max(hi[0] - lo[0], 1e-9), Math.max(hi[1] - lo[1], 1e-9)];
  const scale = Math.min((box[2] - box[0]) / span[0], (box[3] - box[1]) / span[1]);
  const offset = [(box[0] + box[2]) / 2 - (hi[0] + lo[0]) * scale / 2, (box[1] + box[3]) / 2 - (hi[1] + lo[1]) * scale / 2];
  return [scale, offset];
}

/** Axial positions in box, with the glass-brain outline behind them (native _projection). */
function axialPositions(ctx, box) {
  if (!ctx.coords) return circleLayout(ctx.geo.nodes, box);
  const points = ctx.coords.map((p) => [p[0], -p[1]]);
  const [scale, offset] = fit(points, box, ctx.mni ? ctx.outlines.top.box : null);
  if (ctx.mni) outlinePaths(ctx, "top", scale, offset, false, { widths: [1.2, 0.7, 0.7] });
  return points.map(([x, y]) => [x * scale + offset[0], y * scale + offset[1]]);
}

function drawNetwork(ctx, layer, pos, { numbers = true, edgeWidth = 2.2, radius = 5.5, small = 2.4 } = {}) {
  const { P, pal, geo } = ctx;
  const active = geo.active[layer - 1];
  for (const k of geo.compEdges[layer - 1]) {
    const [i, j] = geo.edges[k];
    P.line(...pos[i], ...pos[j], pal.component, edgeWidth);
  }
  pos.forEach(([x, y], i) => {
    const on = active.has(i);
    P.circle(x, y, on ? radius : small, on ? pal.component : pal.node, on ? pal.bg : "none", 1, ctx.labels[i]);
    if (on && numbers) P.text(x + radius + 3, y - radius - 4, String(i + 1), { size: 10 });
  });
}

function brain(ctx) {
  const { P, pal, w, geo, cfg } = ctx;
  const layer = ctx.layer - 1;
  const per = geo.per[layer];
  P.text(4, 18, `${ctx.axis.name} ${value(ctx, layer + 1)}`, { size: 15, bold: true });
  P.text(4, 46, `${per.nodes} component regions · ${per.edges} component edges in this layer`, { color: pal.muted });
  if (!ctx.coords) {
    const h = Math.floor(Math.max(400, Math.min(620, w * 0.6)));
    drawNetwork(ctx, layer + 1, circleLayout(geo.nodes, [w * 0.25, 84, w * 0.75, h - 24]), { numbers: geo.nodes <= 40 });
    ctx.note = "Circular layout: positions are schematic. Add node coordinates on the Data page to see the component on a brain.";
    return h;
  }
  const coords = ctx.coords;
  const views = {
    Left: ["side", (p) => [-p[1], -p[2]], true, (p) => p[0] <= 10],
    Right: ["side", (p) => [p[1], -p[2]], false, (p) => p[0] >= -10],
    Axial: ["top", (p) => [p[0], -p[1]], false, () => true],
    Coronal: ["back", (p) => [p[0], -p[2]], false, () => true],
  };
  const top = 72;
  const single = ctx.view !== "Four views";
  let cells, bottom;
  if (single) {
    const cellH = Math.floor(Math.min(620, w * 0.62));
    cells = [[ctx.view, [w * 0.1, top, w * 0.9, top + cellH]]];
    bottom = top + cellH;
  } else {
    const cellW = (w - 8) / 2;
    const cellH = Math.floor(Math.min(380, cellW * 0.74));
    const x0 = 4, x1 = w - 4;
    cells = [["Left", [x0, top, x0 + cellW, top + cellH]], ["Right", [x0 + cellW, top, x1, top + cellH]],
             ["Axial", [x0, top + cellH, x0 + cellW, top + 2 * cellH]], ["Coronal", [x0 + cellW, top + cellH, x1, top + 2 * cellH]]];
    bottom = top + 2 * cellH;
    P.rect(x0, top, x1 - x0, bottom - top, "none", { stroke: pal.axis });
    P.line(x0 + cellW, top, x0 + cellW, bottom, pal.grid);
    P.line(x0, top + cellH, x1, top + cellH, pal.grid);
  }
  const active = geo.active[layer];
  const { edges: showEdges, other: showOther, numbers, sulci } = ctx.opts;
  const stats = geo.edges.map((_, k) => Math.abs(ctx.result.statistic[k][layer]));
  const threshold = Number(cfg.threshold);
  const inside = geo.compEdges[layer].map((k) => stats[k]);
  const strongest = inside.length ? Math.max(...inside) : threshold;
  for (const [name, [bx0, by0, bx1, by1]] of cells) {
    const [outline, project, mirror, side] = views[name];
    const titleY = by0 + 20;
    P.text((bx0 + bx1) / 2, titleY, name, { anchor: "center", size: 12, bold: true, color: pal.muted });
    if (name === "Coronal" || name === "Axial") {
      const half = measure(name, 12, true) / 2 + 18;
      P.text((bx0 + bx1) / 2 - half, titleY, "L", { anchor: "e", color: pal.muted });
      P.text((bx0 + bx1) / 2 + half, titleY, "R", { color: pal.muted });
    }
    const points = coords.map(project);
    let outlineBox = null;
    if (ctx.mni) {
      const [ox, oy, ow, oh] = ctx.outlines[outline].box;
      outlineBox = [mirror ? -(ox + ow) : ox, oy, ow, oh];
    }
    const [scale, offset] = fit(points, [bx0 + 16, by0 + 40, bx1 - 16, by1 - 14], outlineBox);
    if (ctx.mni) outlinePaths(ctx, outline, scale, offset, mirror, { sulci });
    const xy = points.map(([x, y]) => [x * scale + offset[0], y * scale + offset[1]]);
    const visible = coords.map(side);
    const order = [];
    for (const k of geo.kept[layer]) {
      const [i, j] = geo.edges[k];
      if (!(visible[i] && visible[j])) continue;
      const within = active.has(i) && active.has(j);
      if ((within && showEdges) || (!within && showOther)) order.push([within, stats[k], i, j]);
    }
    order.sort((a, b) => (a[0] - b[0]) || (a[1] - b[1]));
    for (const [within, stat, i, j] of order) {
      if (within) {
        const weight = (1.6 + 2.6 * (stat - threshold) / Math.max(1e-9, strongest - threshold)) * (single ? 1.3 : 1);
        const share = strongest <= threshold ? 0 : (stat - threshold) / (strongest - threshold);
        P.line(...xy[i], ...xy[j], rampColor(pal, share), weight);
      } else {
        P.line(...xy[i], ...xy[j], pal.context, 0.8);
      }
    }
    xy.forEach(([x, y], i) => {
      if (!visible[i]) return;
      const on = active.has(i);
      const rad = on ? (single ? 7 : 5) : (single ? 2.8 : 2);
      P.circle(x, y, rad, on ? pal.component : pal.node, on ? pal.bg : "none", on ? 1.5 : 1, `${i + 1} · ${ctx.labels[i]}`);
      if (on && numbers) P.text(x + rad + 2, y - rad - 4, String(i + 1), { size: single ? 11 : 10 });
    });
  }
  bottom = Math.floor(bottom + 10);
  const label = `Component edge |${cfg.stat_type === "f" ? "F" : "t"}|`;
  const x = colourBar(ctx, 4, bottom + 14, 180, threshold, Math.max(strongest, threshold), label) + 36;
  legend(ctx, x, bottom + 14, [["box", pal.component, "Component region"], ["box", pal.node, "Other region"]]
    .concat(showOther ? [["line", pal.context, "Other edge above threshold"]] : []));
  ctx.note = (ctx.mni ? "Glass-brain outlines from nilearn (MNI152). " : "No brain outline: the coordinates are not in MNI space. ")
    + "Edge colour and thickness show the size of the edge statistic. Left and Right show regions on that side or "
    + "within 10 mm of the midline. Numbers match the member list.";
  return bottom + 50;
}

function allLayers(ctx) {
  const { P, pal, w, geo, span, comp } = ctx;
  const shown = span.slice(0, 24);
  const cols = Math.max(1, Math.min(shown.length, Math.floor((w - 16) / 240)));
  const size = Math.min(300, (w - 16) / cols);
  P.text(8, 18, `The ${span.length} layer${span.length !== 1 ? "s" : ""} component ${comp.id} spans`
    + (span.length > 24 ? " (first 24 shown)" : ""), { size: 13, bold: true });
  const top = 46;
  shown.forEach((l, index) => {
    const x0 = 8 + (index % cols) * size;
    const y0 = top + Math.floor(index / cols) * (size + 40);
    const selected = l === ctx.layer;
    P.rect(x0 + 4, y0, size - 8, size + 32, "none", { stroke: selected ? pal.component : pal.grid, sw: selected ? 2.5 : 1 });
    const p = geo.per[l - 1];
    P.text(x0 + 16, y0 + 20, value(ctx, l), { size: 12, bold: true });
    P.text(x0 + size - 16, y0 + 20, `${p.nodes} regions · ${p.edges} edges`, { anchor: "e", size: 10, color: pal.muted });
    const pos = axialPositions(ctx, [x0 + 22, y0 + 44, x0 + size - 22, y0 + size + 20]);
    drawNetwork(ctx, l, pos, { numbers: false, edgeWidth: 1.8, radius: 3.8, small: 1.7 });
    P.rect(x0 + 4, y0, size - 8, size + 32, "transparent", { cls: "hit", data: ` data-layer="${l}"`,
      title: `Open ${value(ctx, l)} in the Brain tab` });
  });
  const rows = Math.ceil(shown.length / cols);
  ctx.note = "Each panel is one layer of the component" + (ctx.coords ? " on an axial glass brain. " : ", on a circular layout. ")
    + "The outlined panel is the layer shown in the Brain tab. Click a panel to open it there.";
  return top + rows * (size + 40) + 6;
}

/** Critical value of the permutation maxima at alpha (null when alpha is below the smallest p). */
export function criticalValue(draws, alpha) {
  const ordered = [...draws].sort((a, b) => b - a);
  const k = Math.floor(alpha * (draws.length + 1) + 1e-9) - 1;
  return k < 0 ? null : (k >= ordered.length ? 0 : ordered[k]);
}

/** The smallest width of 1, 2, 2.5 or 5 times a power of ten that is at least raw (whole numbers if integer). */
function niceWidth(raw, integer) {
  raw = Math.max(raw, 1e-12);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  let width = raw;
  for (const multiple of [1, 2, 2.5, 5, 10]) {
    width = multiple * magnitude;
    if (width >= raw * (1 - 1e-9) && (!integer || Number.isInteger(width))) break;
  }
  return integer ? Math.max(1, Math.round(width)) : width;
}

function quantile(sorted, q) {
  const position = (sorted.length - 1) * q, low = Math.floor(position), high = Math.ceil(position);
  return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

/** Histogram edges for the permutation maxima (a port of null_bins in native_results.py). The width follows the
 *  Freedman–Diaconis rule rounded up to a round number, kept between about 8 and 60 bins. Extent bins are whole
 *  numbers wide and start on whole numbers, so every bar from the observed value rightwards counts toward p. */
export function nullBins(draws, observed, integer) {
  const n = draws.length;
  const high = Math.max(1, observed, draws.reduce((a, b) => Math.max(a, b), 0));
  const sorted = [...draws].sort((a, b) => a - b);
  const spread = n > 1 ? quantile(sorted, 0.75) - quantile(sorted, 0.25) : 0;
  const raw = spread > 0 ? 2 * spread / Math.cbrt(n) : high / 30;
  const width = niceWidth(Math.min(Math.max(raw, high / 60), high / 8), integer);
  const count = integer ? Math.floor(high / width) + 1 : Math.max(1, Math.ceil(high * 1.04 / width - 1e-9));
  return Array.from({ length: count + 1 }, (_, i) => i * width);
}

/** Plain-language account of a component's corrected p-value (as p_value_sentence in native_results.py). */
export function pValueSentence(draws, observed, metric, p, alpha) {
  const n = draws.length.toLocaleString("en");
  const exceed = draws.filter((d) => d >= observed).length;
  const value = Number.isInteger(observed) ? String(observed) : fmt(observed, 4);
  const count = exceed === 0 ? `None of the ${n}` : `${p <= alpha ? "Only " : ""}${exceed.toLocaleString("en")} of ${n}`;
  return `${count} permutations produced a component at least as large as the observed component (${metric} = ${value}), `
    + `yielding a family-wise corrected p = ${fmt(p, 4)}. One is added to both the numerator and denominator to account `
    + "for the observed result when estimating the permutation p-value.";
}

function nullHistogram(ctx) {
  const { P, pal, w, comp, cfg, result } = ctx;
  const draws = result.null_max;
  const observed = Number(comp.test_stat);
  const integer = cfg.metric === "extent";
  const limits = nullBins(draws, observed, integer);
  const width = limits[1] - limits[0], bins = limits.length - 1, end = limits[bins];
  const counts = new Array(bins).fill(0);
  for (const d of draws) counts[Math.min(bins - 1, Math.max(0, Math.floor(d / width)))] += 1;
  const left = 112, right = w - 30, top = 96, bottom = 386;
  P.text(left, 22, "Maximum component statistic in each permutation", { size: 13, bold: true });
  const high = yAxis(ctx, left, right, top, bottom - top, Math.max(1, ...counts), "Permutations");
  counts.forEach((count, i) => {
    if (!count) return;
    const x1 = left + (right - left) * limits[i] / end, x2 = left + (right - left) * limits[i + 1] / end;
    const range = integer ? (width === 1 ? `${limits[i]}` : `${limits[i]}–${limits[i + 1] - 1}`)
      : `${fmt(limits[i], 3)}–${fmt(limits[i + 1], 3)}`;
    P.rect(x1 + 1, bottom - (bottom - top) * count / high, x2 - x1 - 2, (bottom - top) * count / high, pal.context,
           { title: `${count} permutation${count === 1 ? "" : "s"} with a maximum component ${cfg.metric} of ${range}` });
  });
  const alpha = result.reporting.alpha;
  const critical = criticalValue(draws, alpha);
  if (critical !== null) {
    const x = left + (right - left) * critical / end;
    P.line(x, top - 10, x, bottom, pal.critical, 2, [3, 4]);
  }
  const ox = left + (right - left) * observed / end;
  P.line(ox, top - 10, ox, bottom, pal.component, 3);
  for (const tick of niceTicks(end, 7).filter((t) => t <= end)) {
    const tx = left + (right - left) * tick / end;
    P.line(tx, bottom, tx, bottom + 6, pal.axis);
    P.text(tx, bottom + 20, fmt(tick), { anchor: "center", color: pal.muted });
  }
  P.text((left + right) / 2, bottom + 50, `Maximum component ${cfg.metric}`, { anchor: "center", size: 12, color: pal.muted });
  const items = [["box", pal.context, "Permutation maxima"], ["line", pal.component, `Component ${comp.id} (${fmt(observed)})`]];
  if (critical !== null) items.push(["line", pal.critical, `Critical value at α = ${fmt(alpha)} (${fmt(critical)})`, [3, 4]]);
  legend(ctx, left, 54, items);
  ctx.note = pValueSentence(draws, observed, cfg.metric, comp.p_fwe, alpha);
  return bottom + 74;
}
