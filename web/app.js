// Multiplex-NBS in the browser. Pages, wording and layout follow the desktop app
// (native_app.py, native_setup.py, native_results.py, native_reference.py); the analysis runs in
// the same Python package, loaded by worker.js.
import { dataSketch, drawResult, esc, fmt, FONT, geometry, methodFigure, nullSketch, rangeLabel } from "./figures.js";

/* ---------- wording shared with the desktop app ---------- */
const VERSION = "0.1.0";
const METHODS = { classic: "Classic NBS", layerwise: "Layer-wise NBS", multiplex: "Multiplex-NBS" };
const MODES = { multiplex: "Multiplex-NBS", layerwise: "Layer-wise NBS", classic: "Classic NBS" };
const MODE_NOTES = {
  classic: "Tests one layer you choose in advance. A component is a set of connected edges in that layer.",
  layerwise: "Runs classic NBS in every layer. Components stay within their layer, and one correction covers all layers.",
  multiplex: "Links a region to itself in neighbouring layers, so a component can span layers. One correction covers all layers.",
};
const CAPTIONS = {
  classic: "Classic NBS tests the network at one time point or frequency chosen in advance. Edges above the threshold "
    + "that share regions form a component (here A–B–C), and its size is compared with the largest component found by chance.",
  layerwise: "Layer-wise NBS runs classic NBS at every time point or frequency. Each component stays at its own point, "
    + "and one permutation correction covers all of them together.",
  multiplex: "Multiplex-NBS links a region to itself at the next time point or frequency while it stays active "
    + "(dashed lines), so an effect that persists forms one component and is tested once.",
};
const DESIGNS = { "two-sample": "Independent groups", paired: "Paired observations", "one-sample": "One sample",
                  "glm-t": "GLM · t contrast", "glm-f": "GLM · F contrast" };
const TAILS = { right: "Positive", left: "Negative", both: "Both signs" };
const ADJACENCY = { consecutive: "Connect adjacent layers", independent: "Keep layers separate" };
const RESAMPLING = { auto: "Automatic", "freedman-lane": "Freedman–Lane residuals", rowshuffle: "Shuffle observation rows" };
const DEMOS = { "brain-network": "Brain network over time", "two-sample": "Two independent groups",
                paired: "Paired conditions", glm: "Groups with a covariate (GLM)" };
const DEMO_NOTES = {
  "brain-network": "32 regions from an open human structural connectome, with MNI coordinates so the brain view works. "
    + "40 simulated participants in two groups, 8 time windows from 0 to 350 ms. Group A is higher along a left "
    + "sensorimotor–parietal chain at 100–200 ms.",
  "two-sample": "12 nodes, 40 synthetic participants in two groups of 20, 8 frequency bins from 4 to 18 Hz. "
    + "The first group is higher along a chain of nodes 1–4 at 8–12 Hz.",
  paired: "20 synthetic participants measured in two conditions (40 observations), 12 nodes, 8 frequency bins. "
    + "The first condition is higher along nodes 1–4 at 8–12 Hz.",
  glm: "40 synthetic participants, 12 nodes, 8 frequency bins, with a design matrix (intercept, group, covariate) "
    + "and a contrast that tests the group difference adjusted for the covariate.",
};
const DEMO_FACTS = {
  "brain-network": "32 brain regions · 40 participants in two groups · 8 time windows · brain coordinates",
  "two-sample": "12 nodes · 40 participants in two groups · 8 frequency bins",
  paired: "12 nodes · 20 participants × 2 conditions · 8 frequency bins",
  glm: "12 nodes · 40 participants · 8 frequency bins · design matrix with a covariate",
};
const TOPICS = { method: "Choose a method", interpret: "Interpret a result", inputs: "Prepare inputs", cite: "Citations and credits" };
const PAGES = { home: "Overview", data: "Data", model: "Statistical model", results: "Results", ...TOPICS };
const LEADS = {
  method: "All three methods threshold the edge statistics, group the edges that pass into connected components, and give "
    + "each component one family-wise corrected p-value by permutation. They differ in what counts as connected.",
  interpret: "The corrected p-value belongs to the whole component, not to any single region, edge or layer.",
  inputs: "One undirected connectivity matrix per participant, or one matrix per layer, with the same regions in the "
    + "same order for everyone.",
  cite: `Multiplex-NBS ${VERSION}. Record the version and your settings (shown with every result) when you report an analysis.`,
};
const TABS_STACK = [["profile", "Layer profile"], ["membership", "Node × layer"], ["brain", "Brain"],
                    ["layers", "All layers"], ["null", "Null distribution"]];
const TABS_SINGLE = [["brain", "Brain"], ["null", "Null distribution"]];
const TAB_HINTS = {
  profile: "How much of the network passes the threshold in each layer, and how much of it belongs to this component.",
  membership: "Which regions belong to the component, and in which layers.",
  brain: "The component on a glass brain, one layer at a time. Press Play to step through the layers, or drag the slider.",
  network: "The component one layer at a time. Press Play to step through the layers, or drag the slider.",
  layers: "Every layer the component spans, side by side. Click a panel to open that layer in the Brain tab.",
  null: "How this component's size compares with the largest component found by chance in each permutation.",
};
const SPEEDS = [[1500, "1.5 s per layer"], [1000, "1 s per layer"], [500, "0.5 s per layer"],
                [250, "0.25 s per layer"], [100, "0.1 s per layer"]];
const EXPORTS = [
  ["Report", "txt", "Summary, interpretation notes, every component with its regions and layers, a methods paragraph and all settings."],
  ["Component table", "csv", "One row per component: sign, extent, mass, corrected p, member regions and layers. Opens in Excel, R or Python."],
  ["Full results", "json", "Everything needed to reproduce or re-plot the analysis: settings, each component's region–layer membership, the edge statistic for every layer and all permutation maxima."],
  ["MATLAB results", "mat", "The full results for MATLAB, with the edge statistics, edges, permutation maxima and p-values as arrays."],
];

/* ---------- state ---------- */
const S = {
  page: "home", returnPage: "home",
  theme: (() => { try { return localStorage.getItem("mnbs-theme") || "light"; } catch { return "light"; } })(),
  engine: { state: "loading", text: "Starting Python" },
  overviewMode: "multiplex", dataSource: "open", demoKind: "brain-network",
  source: null, edits: [], name: null, desc: null, config: null, unit: null, advanced: false,
  result: null, view: null, running: null, error: null, busy: null, details: false,
};
let outlines = null;
fetch("glass-brain.json").then((r) => (r.ok ? r.json() : null)).then((json) => { outlines = json && json.views; })
  .catch(() => { outlines = null; });

/* ---------- the Python engine (worker.js) ---------- */
let worker, ready, calls = new Map(), nextId = 1, onProgress = null;

function startWorker() {
  worker = new Worker("worker.js", { type: "module" });
  S.engine = { state: "loading", text: "Starting Python" };
  let resolveReady, rejectReady;
  ready = new Promise((resolve, reject) => { resolveReady = resolve; rejectReady = reject; });
  ready.catch(() => {});
  worker.onmessage = ({ data: msg }) => {
    if (msg.type === "status") {
      S.engine.text = msg.text;
      renderEngine();
    } else if (msg.type === "ready") {
      S.engine = { state: "ready", versions: msg.versions, seconds: msg.seconds };
      renderEngine();
      resolveReady();
    } else if (msg.type === "fatal") {
      S.engine = { state: "failed", text: msg.text };
      renderEngine();
      rejectReady(new Error(msg.text));
    } else if (msg.type === "progress") {
      if (onProgress) onProgress(msg.done, msg.total);
    } else {
      const pending = calls.get(msg.id);
      calls.delete(msg.id);
      if (!pending) return;
      if (msg.type === "result") pending.resolve(msg);
      else {
        if (msg.detail) console.error(msg.detail);
        pending.reject(new Error(msg.text));
      }
    }
  };
  worker.onerror = (event) => {
    S.engine = { state: "failed", text: event.message || "The engine stopped." };
    renderEngine();
    rejectReady(new Error(S.engine.text));
  };
}

async function call(fn, args = null, files = []) {
  const waiting = S.engine.state !== "ready";
  if (waiting) busy("Waiting for Python to finish loading…");
  try {
    await ready;
  } catch (error) {
    throw new Error("Python could not start in this browser: " + error.message);
  } finally {
    if (waiting) busy(null);
  }
  const id = nextId++;
  return new Promise((resolve, reject) => {
    calls.set(id, { resolve, reject });
    worker.postMessage({ id, fn, args, files });
  });
}

/** Stop a running analysis: the worker is replaced and the dataset (with its edits) is reloaded. */
async function restartEngine() {
  worker.terminate();
  for (const pending of calls.values()) {
    const error = new Error("cancelled");
    error.cancelled = true;
    pending.reject(error);
  }
  calls.clear();
  startWorker();
  renderEngine();
  if (S.source) {
    await applySource(S.source);
    for (const edit of S.edits) await call(edit.fn, edit.args, edit.files);
  }
}

/* ---------- helpers ---------- */
const $ = (selector, root = document) => root.querySelector(selector);
const plural = (n, word, many = word + "s") => `${n.toLocaleString("en")} ${n === 1 ? word : many}`;
const context2d = document.createElement("canvas").getContext("2d");
const textWidth = (text, px, bold = true) => { context2d.font = `${bold ? 700 : 400} ${px}px ${FONT}`; return context2d.measureText(text).width; };
let toastTimer;
function toast(text) {
  const box = $("#toast");
  box.textContent = text;
  box.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.add("hidden"), 2600);
}
function busy(text) {
  S.busy = text;
  const box = $("#busy");
  if (box) {
    box.textContent = text || "";
    box.classList.toggle("hidden", !text);
  }
}
function showError(message, title = "Check this") {
  S.error = { message, title };
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function download(bytes, filename, mime) {
  const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied");
  } catch {
    toast("Copying is blocked in this browser; select the text instead.");
  }
}
function setTheme(theme) {
  S.theme = theme;
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("mnbs-theme", theme); } catch { /* private browsing */ }
  render();
}
const suffix = (name) => { const match = /\.[^.\/]+$/.exec(name); return match ? match[0].toLowerCase() : ""; };
const stem = (name) => name.replace(/\.[^.\/]+$/, "");

/* ---------- dialogs (the desktop app's dialog windows) ---------- */
function dialogShell(html) {
  const dialog = document.createElement("dialog");
  dialog.innerHTML = html;
  document.body.append(dialog);
  dialog.addEventListener("close", () => dialog.remove());
  dialog.showModal();
  return dialog;
}

/** Rows are {label, value, options: [[value, label]] or null, importable: "labels" | "matrix" | null}. */
function openDialog({ title, help, rows, submit = "Apply", apply }) {
  const dialog = dialogShell(`
    <div class="heading">${esc(title)}</div>
    <p class="note">${esc(help)}</p>
    <div class="fields dialog-fields">${rows.map((row, i) => `
      <label for="dialog-${i}">${esc(row.label)}</label>
      ${row.options
        ? `<select id="dialog-${i}">${row.options.map(([value, label]) =>
            `<option value="${esc(value)}" ${String(value) === String(row.value) ? "selected" : ""}>${esc(label)}</option>`).join("")}</select>`
        : `<input type="text" id="dialog-${i}" value="${esc(row.value ?? "")}">`}
      ${row.importable ? `<span class="btn file-pick">Read file…<input type="file" data-import="${i}" accept=".csv,.tsv,.txt"></span>` : "<span></span>"}`).join("")}
    </div>
    <div class="alert hidden" role="alert"></div>
    <div class="bar"><button class="btn primary" data-dialog="submit">${esc(submit)}</button>
      <button class="btn" data-dialog="cancel">Cancel</button></div>`);
  const problem = (message) => {
    const box = $(".alert", dialog);
    box.innerHTML = `<div><div class="title">${esc(title)}</div>${esc(message)}</div>`;
    box.classList.remove("hidden");
  };
  dialog.addEventListener("change", async (event) => {
    const index = event.target.dataset.import;
    if (index === undefined || !event.target.files[0]) return;
    try {
      const raw = (await event.target.files[0].text()).replace(/^﻿/, "").trim();
      const text = rows[index].importable === "labels"
        ? (await call("labels_from_table", { text: raw })).value.text
        : raw.split(/\r?\n/).join("; ");
      $(`#dialog-${index}`, dialog).value = text;
    } catch (error) {
      problem(error.message);
    }
  });
  dialog.addEventListener("click", async (event) => {
    const action = event.target.closest("[data-dialog]");
    if (!action) return;
    if (action.dataset.dialog === "cancel") { dialog.close(); return; }
    action.disabled = true;
    try {
      await apply(rows.map((_, i) => $(`#dialog-${i}`, dialog).value.trim()));
      dialog.close();
    } catch (error) {
      action.disabled = false;
      problem(error.message);
    }
  });
}

function textDialog(title, body) {
  const dialog = dialogShell(`
    <div class="heading">${esc(title)}</div>
    <textarea readonly>${esc(body)}</textarea>
    <div class="bar" style="justify-content: space-between; margin: 13px 0 0">
      <button class="btn" data-dialog="copy">Copy text</button><button class="btn" data-dialog="close">Close</button></div>`);
  dialog.addEventListener("click", (event) => {
    const action = event.target.closest("[data-dialog]");
    if (action && action.dataset.dialog === "copy") copy(body);
    else if (action) dialog.close();
  });
}

/* ---------- data ---------- */
async function applySource(source) {
  if (source.kind === "demo") return (await call("open_demo", { kind: source.demo })).value;
  if (source.kind === "file") {
    const path = "/uploads/data" + suffix(source.name);
    return (await call("open_file", { name: source.name, path }, [{ path, bytes: source.bytes }])).value;
  }
  const groups = source.groups.map((g, i) => ({ label: g.label, path: `/uploads/group-${i}.zip` }));
  const files = source.groups.map((g, i) => ({ path: `/uploads/group-${i}.zip`, bytes: g.bytes }));
  return (await call("open_archives", { groups, variable: source.variable, axis: source.axis }, files)).value;
}

async function load(source, next = "data") {
  S.error = null;
  busy(source.kind === "demo" ? "Creating the demo dataset…" : "Reading your data…");
  try {
    const out = await applySource(source);
    Object.assign(S, { source, edits: [], name: out.name, desc: out.description, result: null, view: null });
    S.config = defaultConfig(out.description, source.kind === "demo" ? source.demo : null);
    S.unit = thresholdUnit(S.config.mode, S.config.design);
    busy(null);
    go(next);
  } catch (error) {
    busy(null);
    showError(error.message, source.kind === "demo" ? "Could not open the demo" : "Could not open dataset");
  }
}

/** A dataset editor changed the data: keep the model settings, as the desktop app does. */
async function edit(fn, args, files = []) {
  const { value } = await call(fn, args, files);
  S.edits.push({ fn, args, files });
  S.desc = value.description;
  S.result = null;
  S.view = null;
  const count = S.desc.layer_count;
  if (S.config.mode === "layerwise" && count === 1) S.config.mode = "classic";
  S.config.classic_layer = Math.min(Number(S.config.classic_layer) || 1, count);
  if (!S.config.design) S.config.design = S.desc.suggested_design || "";
  S.unit = thresholdUnit(S.config.mode, S.config.design);
  S.error = null;
  render();
}

function defaultConfig(desc, demo) {
  const layered = desc.layer_count > 1;
  const config = { mode: layered ? "multiplex" : "classic", design: desc.suggested_design || "", threshold: "3",
                   tail: "right", metric: "extent", n_perm: "999", seed: "1", alpha: "0.05", method: "auto",
                   use_abs: false, classic_layer: 1 };
  if (demo) config.n_perm = "99";
  if (demo === "paired") config.design = "paired";
  if (config.mode === "classic" && config.design === "one-sample") config.threshold = "";
  return config;
}

/* ---------- model ---------- */
function thresholdUnit(mode, design) {
  if (design === "glm-f") return "F";
  if (mode === "classic" && design === "one-sample") return "mean weight";
  return "t";
}
const metricOptions = (mode) => (mode === "classic"
  ? { extent: "Extent · number of edges", intensity: "Intensity · excess above threshold" }
  : { extent: "Extent · number of node–layer sites", mass: "Mass · summed statistic magnitudes" });

function modelState() {
  const c = S.config, desc = S.desc, count = desc.layer_count;
  const classic = c.mode === "classic";
  let issue = "", details = "";
  if (!c.design) issue = "Choose the study design that matches your observations.";
  else if (!desc.designs[c.design].ready) issue = desc.designs[c.design].issue;
  else if (c.design === "two-sample") details = `Positive tests ${desc.groups[0]} > ${desc.groups[1]}. The edge statistic is Welch’s t.`;
  else if (c.design === "paired") details = "Positive tests the first observation minus the second within each pair.";
  else if (c.design === "one-sample" && classic) details = "Classic one-sample NBS thresholds the signed mean in your connectivity units. Enter a threshold on that scale.";
  else if (c.design === "one-sample") details = "Multiplex one-sample NBS uses a t statistic to test signed connectivity against zero.";
  else if (c.design === "glm-f") details = "The F statistic tests the contrast rows jointly with a positive tail.";
  else if (c.design === "glm-t") details = "The sign of your contrast C determines the direction of the t statistic.";
  let scope;
  if (classic) scope = "Component p-values cover this one prespecified layer.";
  else if (count > 1 && c.mode === "multiplex") scope = "Shared nodes link neighboring layers. Component p-values account for the search across all layers.";
  else if (count > 1) scope = "Components stay within each layer. Component p-values still account for the search across all layers.";
  else scope = "Multiplex extent counts participating node–layer sites, including on a single input layer.";
  if (classic && !c.classic_layer && !issue) issue = `Choose a prespecified ${desc.axis.name.toLowerCase()} layer for Classic NBS.`;
  if (!String(c.threshold).trim() && !issue) issue = `Enter a primary threshold in ${S.unit} units.`;
  return { issue, details: details || "Set the design using the group labels, pair IDs or GLM in your dataset.", scope };
}

function number(raw, label, { integer = false, minimum = 0 } = {}) {
  const text = String(raw).trim();
  const value = Number(text);
  if (!text || !Number.isFinite(value) || value < minimum || (integer && !Number.isInteger(value))) {
    throw new Error(`${label} must be ${integer ? `an integer of at least ${minimum}` : `a finite number of at least ${minimum}`}.`);
  }
  return value;
}

function engineConfig() {
  const c = S.config, desc = S.desc;
  const mode = c.mode === "layerwise" ? "multiplex" : c.mode;
  const threshold = number(c.threshold, "Primary threshold");
  if (threshold === 0) throw new Error("Primary threshold must be greater than zero.");
  const alpha = number(c.alpha, "Reporting alpha");
  if (!(alpha > 0 && alpha < 1)) throw new Error("The significance cutoff (alpha) must be a number between 0 and 1.");
  const config = {
    inference_mode: mode, design: c.design, threshold, tail: c.design === "glm-f" ? "right" : c.tail, metric: c.metric,
    n_perm: number(c.n_perm, "Permutations", { integer: true, minimum: 1 }),
    seed: String(c.seed).trim() ? number(c.seed, "Random seed", { integer: true }) : null,
    alpha, method: c.design.startsWith("glm") ? c.method : "auto",
    use_abs: c.design === "one-sample" ? false : !!c.use_abs,
    layer_adjacency: c.mode === "layerwise" ? "independent"
      : (desc.layer_count > 1 && mode === "multiplex" ? "consecutive" : desc.axis.adjacency),
  };
  if (mode === "classic") config.classic_layer = Number(c.classic_layer);
  return config;
}

async function run() {
  let config;
  try {
    config = engineConfig();
  } catch (error) {
    showError(error.message, "Review model settings");
    return;
  }
  S.error = null;
  S.running = { done: 0, total: config.n_perm };
  go("progress");
  onProgress = (done, total) => {
    if (!S.running) return;
    S.running.done = done;
    S.running.total = total;
    updateProgress();
  };
  try {
    const { value } = await call("run", config);
    S.result = value;
    S.view = freshView(value);
    S.running = null;
    go("results");
  } catch (error) {
    S.running = null;
    if (!error.cancelled) {
      S.page = "model";
      showError(error.message, "Review model settings");
    }
  } finally {
    onProgress = null;
  }
}

async function cancel() {
  if (!S.running) return;
  S.running = null;
  go("model");
  try {
    await restartEngine();
  } catch (error) {
    showError(error.message);
  }
}

/* ---------- results view state ---------- */
const components = (result) => [...result.clusters].sort((a, b) => a.p_fwe - b.p_fwe || b.test_stat - a.test_stat || a.id - b.id);
function visibleComponents() {
  const rows = components(S.result);
  return S.view.scope === "significant" ? rows.filter((c) => c.p_fwe <= S.result.reporting.alpha) : rows;
}
function freshView(result) {
  const view = { scope: "significant", comp: null, tab: result.dimensions.n_layers > 1 ? "profile" : "brain", layer: 1,
                 view: "Four views", only: true, speed: 500, loop: true, timer: null, methods: false,
                 opts: { edges: true, other: false, numbers: result.dimensions.n_nodes <= 40, sulci: true } };
  const first = components(result).find((c) => c.p_fwe <= result.reporting.alpha);
  selectComponent(view, result, first || null);
  return view;
}
function selectComponent(view, result, comp) {
  view.comp = comp ? comp.id : null;
  view.geo = comp ? geometry(result, comp) : null;
  if (comp) view.layer = Math.min(...comp.layer_bins);
}
const currentComponent = () => S.result && S.result.clusters.find((c) => c.id === S.view.comp);

/* ---------- navigation and rendering ---------- */
function go(page) {
  stopPlayer();
  if (page === "model" && !S.desc) page = "data";
  if (page === "results" && !S.result) return;
  if (TOPICS[page] && !TOPICS[S.page] && S.page !== "progress") S.returnPage = S.page;
  S.page = page;
  render();
  window.scrollTo({ top: 0 });
}
function render() {
  document.documentElement.dataset.theme = S.theme;
  renderRail();
  const page = TOPICS[S.page] ? referencePage
    : { home: overviewPage, data: dataPage, model: modelPage, progress: progressPage, results: resultsPage }[S.page];
  $("#page").innerHTML = alertHtml() + `<div class="busy hidden" id="busy"></div>` + page();
  busy(S.busy);
  (TOPICS[S.page] ? drawSketches : after[S.page])?.();
}
function alertHtml() {
  return S.error ? `<div class="alert" role="alert"><div><div class="title">${esc(S.error.title)}</div>${esc(S.error.message)}</div>`
    + `<button class="btn compact" data-action="dismiss">Dismiss</button></div>` : "";
}

function renderRail() {
  const runningNow = !!S.running;
  const item = (key) => {
    const disabled = runningNow || (key === "model" && !S.desc) || (key === "results" && !S.result);
    const current = (S.page === "progress" ? "model" : S.page) === key;
    return `<button data-go="${key}" ${disabled ? "disabled" : ""} ${current ? 'aria-current="page"' : ""}>${PAGES[key]}</button>`;
  };
  $("#rail").innerHTML = `
    <div class="brand">Multiplex-NBS</div>
    <div class="version">Version ${VERSION}</div>
    <nav class="nav" aria-label="Pages">
      ${item("home")}
      <div class="kicker">ANALYSIS</div>${["data", "model", "results"].map(item).join("")}
      <div class="kicker">REFERENCE</div>${Object.keys(TOPICS).map(item).join("")}
    </nav>
    <div class="rail-foot">
      <div class="segment" role="group" aria-label="Colour mode">
        ${[["light", "Light"], ["dark", "Dark"], ["mono", "Mono"]].map(([key, label]) =>
          `<button data-theme-set="${key}" aria-pressed="${S.theme === key}">${label}</button>`).join("")}
      </div>
      <div class="side-note engine" id="engine"></div>
      <div class="side-note">All analysis runs locally.</div>
    </div>`;
  renderEngine();
}
function renderEngine() {
  const box = $("#engine");
  if (!box) return;
  const e = S.engine;
  box.dataset.state = e.state;
  const text = e.state === "ready" ? `Python ${esc(e.versions.python)} ready in this browser`
    : e.state === "failed" ? `Python did not start: ${esc(e.text)}` : `${esc(e.text)}…`;
  box.innerHTML = `<span class="dot"></span><span>${text}</span>`;
  box.title = e.state === "ready" ? `NumPy ${e.versions.numpy} · SciPy ${e.versions.scipy} · loaded in ${e.seconds.toFixed(1)} s` : "";
}

/* ---------- Overview ---------- */
function overviewPage() {
  return `
    <section class="home-head" id="home-head">
      <div>
        <h1 id="brand-title">Multiplex-NBS</h1>
        <div class="subtitle">Classic, layer-wise and multiplex network-based statistics in one place</div>
      </div>
      <div>
        <p class="lead">Compare connectivity between groups or conditions. Edges above a threshold are grouped into
          connected components, and each component receives a family-wise corrected p-value, in one network or across
          time points or frequency bands.</p>
        <div class="home-actions">
          <button class="btn primary" data-go="data">Start analysis &nbsp;›</button>
          <button class="btn" data-action="try-demo">Try the demo</button>
        </div>
      </div>
    </section>
    <section class="plate" id="plate">
      <div class="plate-top">
        <h2>Connected components</h2>
        <div class="segment hero" role="group" aria-label="Method">
          ${Object.entries(METHODS).map(([key, label]) =>
            `<button data-action="overview-mode" data-mode="${key}" aria-pressed="${S.overviewMode === key}">${label}</button>`).join("")}
        </div>
      </div>
      <div class="plate-body" id="plate-body">
        <p class="caption" id="overview-caption">${esc(CAPTIONS[S.overviewMode])}</p>
        <div class="method-figure" id="method-figure"></div>
      </div>
    </section>`;
}
function drawOverview() {
  const figure = $("#method-figure");
  if (!figure) return;
  figure.innerHTML = methodFigure(S.theme, S.overviewMode);
  $("#overview-caption").textContent = CAPTIONS[S.overviewMode];
  fitOverview();
}
/** The desktop app's title fitting: the largest size at which the title fits beside the introduction. */
function fitOverview() {
  const head = $("#home-head"), title = $("#brand-title");
  if (!head || !title) return;
  const width = head.clientWidth;
  const leadWidth = Math.max(280, Math.min(430, width * 0.34));
  const fits = (px, room) => textWidth("Multiplex-NBS", px) <= room;
  let size = 101;
  while (size > 40 && !fits(size, width - leadWidth - 56)) size -= 2.67;
  const wide = size >= 66.7 && width > 700;
  if (!wide) {
    size = 93;
    while (size > 32 && !fits(size, width - 8)) size -= 2.67;
  }
  head.style.gridTemplateColumns = wide ? `minmax(0, 1fr) ${Math.round(leadWidth)}px` : "minmax(0, 1fr)";
  head.style.gap = wide ? "48px" : "24px";
  title.style.fontSize = `${Math.round(size)}px`;
  const plate = $("#plate"), body = $("#plate-body");
  const sideBySide = plate.clientWidth - 88 >= 760;
  body.style.gridTemplateColumns = sideBySide ? "280px minmax(0, 1fr)" : "minmax(0, 1fr)";
  body.style.gap = sideBySide ? "40px" : "20px";
}

/* ---------- Data ---------- */
function datasetCard() {
  const d = S.desc, axis = d.axis, count = d.layer_count;
  const facts = [`${d.subjects} observations`, `${d.nodes} regions`,
                 `${count} ${count === 1 ? "layer" : "layers"} (${axis.name}${axis.unit ? ", " + axis.unit : ""})`];
  const groups = d.group_counts;
  const groupLine = !groups.length ? ""
    : groups.length <= 4 ? "Groups: " + groups.map((g) => `${g.label} (${g.count})`).join(",  ")
      : `${groups.length} group labels or pair IDs. Open Observation order for the full list.`;
  const designLine = [d.has_glm ? `Design matrix ${d.design_shape[0]} × ${d.design_shape[1]}` : "No design matrix",
                      d.coordinate_space ? `Coordinates: ${d.coordinate_space}` : "No node coordinates (the brain view needs them)"];
  return `
    <div class="card" style="margin-bottom: 30px">
      <div class="card-kicker">LOADED</div>
      <div class="card-title" style="margin: 4px 0 8px">${esc(S.name)}</div>
      <p class="text" style="margin-bottom: 6px">${esc(facts.join("   ·   "))}</p>
      ${groupLine ? `<p class="text muted" style="margin-bottom: 4px">${esc(groupLine)}</p>` : ""}
      <p class="text muted" style="margin-bottom: 6px">${esc(designLine.join("   ·   "))}</p>
      ${d.issues.map((issue) => `<p class="text warn" style="margin-bottom: 6px">${esc(issue)}</p>`).join("")}
      <div class="bar">
        <button class="btn primary" data-go="model">Set up the model &nbsp;›</button>
        <button class="btn" data-action="observations">Observation order</button>
        <button class="btn" data-action="save-dataset">Save dataset…</button>
      </div>
      <div class="card-small" style="margin: 12px 0 6px">Adjust</div>
      <div class="bar">
        <button class="btn" data-action="edit-groups">Groups and blocks…</button>
        <button class="btn" data-action="edit-glm">Design and contrast…</button>
        <button class="btn" data-action="edit-axis">Layer axis…</button>
        <span class="btn file-pick">Node coordinates…<input type="file" id="coords-file" accept=".csv,.tsv,.txt,.npy,.mat"></span>
      </div>
      <p class="text muted" style="margin: 4px 0 0">Save dataset writes the combined matrices, groups, layer axis, labels and
        coordinates to one .npz file that opens directly next time.</p>
    </div>`;
}
function dataPage() {
  return `
    <div class="page-title">Data</div>
    <p class="lead2">Each participant contributes one connectivity matrix (regions × regions), or a stack of matrices across
      time points or frequency bins. Every participant needs the same regions in the same order, plus a group label.</p>
    ${S.desc ? datasetCard() : ""}
    <div class="heading" style="margin: 0 0 12px">${S.desc ? "Use different data" : "Choose your data"}</div>
    <div class="segment choice" role="group" aria-label="Data source" style="margin-bottom: 20px">
      <button data-action="data-source" data-value="open" aria-pressed="${S.dataSource === "open"}">Open my data</button>
      <button data-action="data-source" data-value="demo" aria-pressed="${S.dataSource === "demo"}">Try a demo dataset</button>
    </div>
    ${S.dataSource === "open" ? openPanel() : demoPanel()}`;
}
function openPanel() {
  return `
    <div class="cards">
      <div class="card">
        <div class="card-title">One combined file</div>
        <p class="text">A NumPy .npz or MATLAB v7 .mat file that holds every participant. Store the matrices as W and one
          group label per participant as group.</p>
        <div class="code">W       participants × regions × regions × layers
group   one label per participant
optional: axis_values, node_labels, node_coordinates</div>
        <p class="text muted">For one network per participant, leave out the layer dimension. MATLAB arrays use
          regions × regions × layers × participants.</p>
        <div class="bar"><span class="btn primary file-pick">Choose file…<input type="file" id="combined-file" accept=".npz,.mat"></span></div>
      </div>
      <div class="card">
        <div class="card-title">One ZIP per group</div>
        <p class="text">Put each participant's matrix file in a folder for its group, zip each folder, then choose all the
          ZIPs together. Each ZIP becomes one group.</p>
        <div class="code">Control.zip
   sub-01.mat
   sub-02.mat   …
Patient.zip
   sub-31.mat   …</div>
        <p class="text muted">Use .mat or .npy files (regions × regions × layers), or .csv, .tsv or .txt for one network.
          Participants are ordered by file name.</p>
        <div class="bar"><span class="btn primary file-pick">Choose group ZIPs…<input type="file" id="group-zips" accept=".zip" multiple></span></div>
      </div>
    </div>
    <p class="muted" style="margin-top: 16px; max-width: 760px">Brain coordinates are optional and can be added after loading
      with Node coordinates. The Prepare inputs page has full format details.</p>`;
}
function demoPanel() {
  const option = (key) => `
    <label class="demo-option">
      <input type="radio" name="demo" value="${key}" ${S.demoKind === key ? "checked" : ""}>
      <span class="name">${DEMOS[key]}</span>
      <span class="facts">${DEMO_FACTS[key]}</span>
      <span class="about">${DEMO_NOTES[key]}</span>
    </label>`;
  return `
    <p class="text" style="margin-bottom: 16px">These are four separate practice datasets. All of them are simulated, so you
      can learn the app without your own data. Start with the brain example; the other three show how different study
      designs are set up.</p>
    <div class="cards">
      <div class="card"><div class="card-title" style="margin-bottom: 2px">Brain example</div>
        <p class="muted">A realistic brain network, closest to a real study.</p>${option("brain-network")}</div>
      <div class="card"><div class="card-title" style="margin-bottom: 2px">Study design examples</div>
        <p class="muted">Small abstract networks with no brain coordinates. Each one shows a different design.</p>
        ${["two-sample", "paired", "glm"].map(option).join("")}</div>
    </div>
    <div class="bar" style="margin-top: 22px"><button class="btn primary" data-action="open-demo">Open selected demo</button></div>`;
}

async function datasetFields() {
  return (await call("dataset_fields")).value;
}
const dataActions = {
  observations: async () => {
    const f = await datasetFields();
    const dialog = dialogShell(`
      <div class="heading">Observation order</div>
      <p class="note">Design rows and labels follow this order. In a pair, the first observation is compared with the second.</p>
      <div class="table-dialog"><table><thead><tr><th>Row</th><th>Observation ID</th><th>Group or pair ID</th><th>Exchange block</th></tr></thead>
        <tbody>${f.observations.map((row) => `<tr>${row.map((cell) => `<td>${esc(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
      <div class="bar" style="margin: 16px 0 0"><button class="btn" data-dialog="close">Close</button></div>`);
    dialog.addEventListener("click", (event) => { if (event.target.closest("[data-dialog]")) dialog.close(); });
  },
  "save-dataset": async () => {
    const { value, bytes } = await call("save_dataset");
    download(bytes, value.filename, value.mime);
  },
  "edit-groups": async () => {
    const f = await datasetFields();
    openDialog({ title: "Groups and exchange blocks",
      help: "Use one label per observation, in dataset order. Separate labels with commas or import a headerless table. "
        + "For paired tests, repeat each pair ID twice in condition order. Clear a field to remove it.",
      rows: [{ label: "Group labels or pair IDs", value: f.group, importable: "labels" },
             { label: "Exchange blocks (optional)", value: f.blocks, importable: "labels" }],
      apply: ([group, blocks]) => edit("edit_groups", { group, blocks }) });
  },
  "edit-glm": async () => {
    const f = await datasetFields();
    openDialog({ title: "Design matrix and contrast",
      help: "X has one row per observation. C has one column per regressor. Separate columns with commas and rows with "
        + "semicolons, or import headerless text tables. Clear both to remove the GLM.",
      rows: [{ label: "Design matrix X", value: f.X, importable: "matrix" },
             { label: "Contrast C", value: f.C, importable: "matrix" },
             { label: "Contrast statistic", value: f.stat, options: [["T", "T"], ["F", "F"]] }],
      apply: ([X, C, stat]) => edit("edit_glm", { X, C, stat }) });
  },
  "edit-axis": async () => {
    const f = await datasetFields();
    openDialog({ title: "Layer axis",
      help: "Use an ordered axis such as time, frequency or condition. Each layer needs one increasing value.",
      rows: [{ label: "Axis name", value: f.axis_name }, { label: "Unit (optional)", value: f.axis_unit },
             { label: "Ordered values", value: f.axis_values, importable: "matrix" },
             { label: "Default adjacency", value: f.adjacency, options: Object.entries(ADJACENCY) }],
      apply: ([name, unit, values, adjacency]) => edit("edit_axis", { name, unit, values, adjacency }) });
  },
};

function chooseCoordinates(file) {
  openDialog({ title: "Node coordinates",
    help: `${file.name} · One x, y, z row per node in input order. Text files may start with a label column.`,
    rows: [{ label: "Input units", value: "mm", options: [["mm", "mm"], ["cm", "cm"]] }, { label: "Coordinate space", value: "MNI" }],
    apply: async ([units, space]) => {
      const path = "/uploads/coordinates" + suffix(file.name);
      await edit("set_coordinates", { path, name: file.name, units, space }, [{ path, bytes: await file.arrayBuffer() }]);
      toast("Coordinates added");
    } });
}

function chooseArchives(files) {
  const rows = files.map((file) => ({ label: file.name, value: stem(file.name) }))
    .concat([{ label: "MAT variable (optional)", value: "" }, { label: "Axis name", value: "Layer" },
             { label: "Axis unit (optional)", value: "" }, { label: "First value", value: "1" },
             { label: "Step between layers", value: "1" }]);
  openDialog({ title: "Combine group ZIPs", submit: "Combine",
    help: "Check the group name for each ZIP. Participants are ordered by file name within each ZIP. Then describe the "
      + "layers: for example Frequency, Hz, first value 1, step 1.",
    rows,
    apply: async (values) => {
      const labels = values.slice(0, files.length);
      const [variable, name, unit, start, step] = values.slice(files.length);
      const first = Number(start), gap = Number(step);
      if (!start || !step || !Number.isFinite(first) || !Number.isFinite(gap) || gap <= 0) {
        throw new Error("The first layer value must be a number and the step a positive number.");
      }
      const groups = await Promise.all(files.map(async (file, i) => ({ label: labels[i], bytes: await file.arrayBuffer() })));
      const source = { kind: "zips", groups, variable: variable || null, axis: { name, unit, start: first, step: gap } };
      const out = await applySource(source);
      Object.assign(S, { source, edits: [], name: out.name, desc: out.description, result: null, view: null, error: null });
      S.config = defaultConfig(out.description, null);
      S.unit = thresholdUnit(S.config.mode, S.config.design);
      render();
    } });
}

/* ---------- Model ---------- */
function select(id, options, selected, { disabled = false } = {}) {
  return `<select id="${id}" ${disabled ? "disabled" : ""}>${Object.entries(options).map(([key, label]) =>
    `<option value="${esc(key)}" ${String(selected) === String(key) ? "selected" : ""}>${esc(label)}</option>`).join("")}</select>`;
}
function modelPage() {
  const c = S.config, d = S.desc, axis = d.axis, count = d.layer_count;
  const methods = Object.fromEntries(Object.entries(MODES).filter(([key]) => count > 1 || key !== "layerwise"));
  const layers = Object.fromEntries(axis.values.map((v, i) => [i + 1, `${i + 1} · ${fmt(v)}${axis.unit ? " " + axis.unit : ""}`]));
  const designs = { "": "Choose a design", ...DESIGNS };
  const { issue, details, scope } = modelState();
  return `
    <div class="page-title">Statistical model</div>
    <p class="note">${esc(`${S.name}   ·   ${d.subjects} observations   ·   ${d.nodes} nodes   ·   ${count} ${count === 1 ? "layer" : "layers"}`)}</p>
    <div class="fields">
      <label for="m-mode">Method</label>${select("m-mode", methods, c.mode)}
      <div class="hint">${esc(MODE_NOTES[c.mode])}</div>
      ${c.mode === "classic" ? `<label for="m-layer">${esc(axis.name)} layer</label>${select("m-layer", layers, c.classic_layer)}` : ""}
      <label for="m-design">Study design</label>${select("m-design", designs, c.design)}
    </div>
    <p class="note">${esc(details)}</p>
    <div class="fields">
      <label for="m-threshold">Primary threshold (${esc(S.unit)})</label><input type="text" inputmode="decimal" id="m-threshold" value="${esc(c.threshold)}">
      <label for="m-tail">Tail</label>${select("m-tail", TAILS, c.design === "glm-f" ? "right" : c.tail, { disabled: c.design === "glm-f" })}
      <label for="m-metric">Component statistic</label>${select("m-metric", metricOptions(c.mode), c.metric)}
      <label for="m-perm">Permutations</label><input type="text" inputmode="numeric" id="m-perm" value="${esc(c.n_perm)}">
    </div>
    <label class="check" style="margin-bottom: 13px"><input type="checkbox" id="m-advanced" ${S.advanced ? "checked" : ""}> Advanced settings</label>
    ${S.advanced ? `
    <div class="fields">
      <label for="m-alpha">Reporting alpha</label><input type="text" inputmode="decimal" id="m-alpha" value="${esc(c.alpha)}">
      <label for="m-seed">Random seed</label><input type="text" inputmode="numeric" id="m-seed" value="${esc(c.seed)}">
      ${c.design.startsWith("glm") ? `<label for="m-method">GLM permutation</label>${select("m-method", RESAMPLING, c.method)}` : ""}
    </div>
    <label class="check" style="margin-bottom: 10px"><input type="checkbox" id="m-abs" ${c.use_abs ? "checked" : ""}
      ${c.design === "one-sample" ? "disabled" : ""}> Use absolute connectivity weights</label>` : ""}
    <p class="note" id="model-notice" style="margin-top: 6px">${esc(issue || scope)}</p>
    <div class="bar">
      <button class="btn primary" data-action="run" ${issue ? "disabled" : ""}>Run permutations</button>
      <button class="btn" data-go="data">Review data</button>
    </div>`;
}
function modelChanged(id, value) {
  const c = S.config;
  if (id === "m-advanced") { S.advanced = value; return true; }
  const key = { "m-mode": "mode", "m-layer": "classic_layer", "m-design": "design", "m-threshold": "threshold",
                "m-tail": "tail", "m-metric": "metric", "m-perm": "n_perm", "m-alpha": "alpha", "m-seed": "seed",
                "m-method": "method", "m-abs": "use_abs" }[id];
  if (!key) return false;
  c[key] = value;
  if (key === "mode" || key === "design") {
    const options = metricOptions(c.mode);
    if (!(c.metric in options)) c.metric = "extent";
    const unit = thresholdUnit(c.mode, c.design);
    if (unit !== S.unit) {
      c.threshold = "";
      S.unit = unit;
    }
    if (c.design === "glm-f") c.tail = "right";
    if (c.design === "one-sample") c.use_abs = false;
    return true;
  }
  return false;
}
function refreshModelNotice() {
  const { issue, scope } = modelState();
  const notice = $("#model-notice");
  if (notice) notice.textContent = issue || scope;
  const button = $('[data-action="run"]');
  if (button) button.disabled = !!issue;
}

/* ---------- Progress ---------- */
function progressPage() {
  return `
    <div class="page-title">Running permutations</div>
    <p class="text">${esc(S.name)}</p>
    <p id="progress-text" style="margin: 16px 0">Starting…</p>
    <div class="progress"><div id="progress-bar"></div></div>
    <button class="btn" data-action="cancel">Cancel analysis</button>`;
}
function updateProgress() {
  const run = S.running;
  if (!run || S.page !== "progress") return;
  $("#progress-bar").style.width = `${(run.total ? 100 * run.done / run.total : 0).toFixed(1)}%`;
  $("#progress-text").textContent = `${run.done.toLocaleString("en")} of ${run.total.toLocaleString("en")} permutations`;
}

/* ---------- Results ---------- */
function methodName(cfg, layers) {
  if (cfg.inference_mode === "classic") return "Classic NBS";
  if (layers > 1 && cfg.layer_adjacency === "independent") return "Layer-wise NBS";
  return "Multiplex-NBS";
}
function direction(cfg, comp) {
  if (cfg.stat_type === "f") return "F contrast (no direction)";
  const higher = comp.tail !== "left";
  if (cfg.test === "two-sample") return `${cfg.group_values[0]} ${higher ? ">" : "<"} ${cfg.group_values[1]}`;
  if (cfg.test === "paired") return `First ${higher ? ">" : "<"} second within pairs`;
  if (cfg.test === "one-sample") return higher ? "Mean above zero" : "Mean below zero";
  return higher ? "Positive GLM contrast" : "Negative GLM contrast";
}
function resultsPage() {
  const result = S.result, cfg = result.config, v = S.view;
  const layers = result.dimensions.n_layers, axis = result.dataset.axis;
  const classic = cfg.inference_mode === "classic";
  const rows = components(result);
  const alpha = result.reporting.alpha;
  const n = rows.filter((c) => c.p_fwe <= alpha).length;
  const floor = 1 / (1 + cfg.n_perm);
  let line = n ? `${n} of ${rows.length} observed components reached corrected p ≤ ${fmt(alpha)}.`
    : `No component reached corrected p ≤ ${fmt(alpha)} (${rows.length} observed). This does not show that there is no effect.`;
  if (alpha < floor) line += ` With ${cfg.n_perm.toLocaleString("en")} permutations the smallest possible p is ${fmt(floor, 4)}.`;
  const meta = [methodName(cfg, layers), result.dataset_name || S.name, `${cfg.n_perm.toLocaleString("en")} permutations`,
                layers > 1 ? `${axis.name} ${rangeLabel(axis.values, axis.unit)}` : "",
                `${result.elapsed_seconds.toFixed(1)} s`].filter(Boolean).join(" · ");
  const visible = visibleComponents();
  const comp = currentComponent();
  const shown = comp && visible.some((c) => c.id === comp.id);
  const labels = result.dataset.node_labels;
  const demo = result.dataset.demo_info;
  return `
    <div class="page-title">${n ? plural(n, "significant component") : "No significant components"}</div>
    <p class="headline">${esc(line)}</p>
    <p class="muted">${esc(meta)}</p>
    <div class="kpis">
      ${[["Components", rows.length], ["Significant", n], ["Smallest corrected p", rows.length ? fmt(Math.min(...rows.map((c) => c.p_fwe)), 3) : "–"],
         ["Permutations", cfg.n_perm.toLocaleString("en")]].map(([label, value]) =>
        `<div class="kpi"><div class="label">${label}</div><div class="value">${value}</div></div>`).join("")}
    </div>
    ${demo ? `<div class="notice">${esc("Simulated data. " + (demo.simulation_note || ""))}</div>` : ""}
    <div class="components-bar">
      <div><div class="heading">Components</div>
        <p class="muted">Click a component in the table to show it in the figures and details below. Significant lists the
          components at or below the cutoff; All adds the rest.</p></div>
      <div class="filters">
        <div class="segment" role="group" aria-label="Components shown">
          <button data-action="scope" data-value="significant" aria-pressed="${v.scope === "significant"}">Significant (${n})</button>
          <button data-action="scope" data-value="all" aria-pressed="${v.scope === "all"}">All (${rows.length})</button>
        </div>
        <div class="cutoff"><label for="alpha">Corrected p ≤</label><input type="text" inputmode="decimal" id="alpha" value="${fmt(alpha)}">
          <button class="btn" data-action="apply-alpha">Apply</button></div>
      </div>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>Component</th><th>Sign</th><th>Corrected p</th><th>${classic ? "Extent (edges)" : "Extent (sites)"}</th>
        <th>${classic ? "Intensity" : "Mass"}</th><th>Regions</th><th>${classic ? "Input layer" : esc(axis.name)}</th>
        <th class="members">Member regions</th></tr></thead>
      <tbody>${visible.map((c) => {
        const values = c.layer_bins.map((b) => axis.values[b - 1]);
        const members = c.nodes.slice(0, 4).map((i) => labels[i - 1]).join(", ") + (c.nodes.length > 4 ? " …" : "");
        return `<tr data-comp="${c.id}" aria-selected="${c.id === v.comp}" tabindex="0">
          <td>${c.id}</td><td>${cfg.stat_type === "f" ? "F" : c.tail === "right" ? "+" : "−"}</td><td>${fmt(c.p_fwe, 4)}</td>
          <td>${c.extent}</td><td>${fmt(classic ? c.intensity : c.mass, 4)}</td><td>${c.n_nodes}</td>
          <td>${classic ? cfg.classic_layer : `${esc(rangeLabel(values, axis.unit))} (${values.length})`}</td>
          <td class="members">${esc(members)}</td></tr>`;
      }).join("")}</tbody></table></div>
    ${visible.length ? "" : `<p class="empty">${rows.length
      ? `No component meets corrected p ≤ ${fmt(alpha)}. Choose All to explore the components that were observed.`
      : "No edges exceeded the primary threshold, so no components were formed."}</p>`}
    ${shown ? explorer(comp) + summaryBlock(comp) : ""}
    <section class="save">
      <div class="heading">Save results</div>
      <p class="muted" style="margin: 8px 0 0">Each file includes every observed component, not only the significant ones.
        Save the figure in the current tab with Save figure above.</p>
      <div class="save-grid">${EXPORTS.map(([label, kind, text]) => `
        <button class="btn" data-action="export" data-kind="${kind}">${label} (.${kind})…</button><p>${esc(text)}</p>`).join("")}
      </div>
      <p class="muted" style="margin-top: 12px">The dataset itself (matrices, groups, axis and coordinates) is saved from the
        Data page with Save dataset.</p>
    </section>
    <section class="methods">
      <button class="btn" data-action="toggle-methods">${v.methods ? "Hide" : "Show"} methods text and settings</button>
      ${v.methods ? `<div class="box"><p style="max-width: 1000px">${esc(result.methods)}</p>
        <div class="bar" style="margin-top: 12px"><button class="btn" data-action="copy-methods">Copy methods text</button>
          <button class="btn" data-action="settings">Complete settings</button></div></div>` : ""}
    </section>
    <div style="margin-top: 28px"><button class="btn" data-go="model">Edit statistical model</button></div>`;
}

function explorer(comp) {
  const v = S.view, result = S.result, cfg = result.config;
  const layers = result.dimensions.n_layers, axis = result.dataset.axis;
  const coords = !!result.dataset.node_coordinates;
  const classic = cfg.inference_mode === "classic";
  const alpha = result.reporting.alpha;
  const values = comp.layer_bins.map((b) => axis.values[b - 1]);
  const labels = result.dataset.node_labels;
  const rows = [["Corrected p", fmt(comp.p_fwe, 4) + (comp.p_fwe <= alpha ? "" : " (not significant)")],
                ["Effect", direction(cfg, comp)],
                ["Extent", `${comp.extent} ${classic ? "edges" : "region–layer sites"}`],
                [classic ? "Intensity" : "Mass", fmt(classic ? comp.intensity : comp.mass, 4)],
                ["Regions", String(comp.n_nodes)]];
  if (classic) rows.push(["Input layer", String(cfg.classic_layer)]);
  else rows.push(["Layers", String(values.length)], [axis.name, rangeLabel(values, axis.unit)]);
  rows.push(["Members", comp.nodes.slice(0, 8).map((i) => labels[i - 1]).join(", ")
    + (comp.nodes.length > 8 ? ` and ${comp.nodes.length - 8} more` : "")]);
  const tabs = (layers > 1 ? TABS_STACK : TABS_SINGLE).map(([key, label]) => [key, key === "brain" && !coords ? "Network" : label]);
  const brainTab = v.tab === "brain";
  return `
    <section class="explorer">
      <div class="heading">Component ${comp.id}${comp.p_fwe <= alpha ? "" : "  (not significant)"}</div>
      <div class="tabs" role="tablist">${tabs.map(([key, label]) =>
        `<button role="tab" data-action="tab" data-tab="${key}" aria-selected="${v.tab === key}">${label}</button>`).join("")}</div>
      <p class="tab-hint">${esc(TAB_HINTS[brainTab && !coords ? "network" : v.tab])}</p>
      <div class="explore-grid">
        <div class="figure-area">
          ${brainTab && coords ? `<div class="segment view-switch" role="group" aria-label="Brain view">${["Four views", "Left", "Right", "Axial", "Coronal"].map((name) =>
            `<button data-action="view" data-value="${name}" aria-pressed="${v.view === name}">${name}</button>`).join("")}</div>` : ""}
          <div class="figure" id="figure"></div>
          ${brainTab && layers > 1 ? `
          <div class="player">
            <button class="btn compact" data-action="step" data-value="-1" aria-label="Previous layer">◀</button>
            <button class="btn compact" data-action="play" id="play" style="min-width: 70px">${v.timer ? "Pause" : "Play"}</button>
            <button class="btn compact step-next" data-action="step" data-value="1" aria-label="Next layer">▶</button>
            <input type="range" id="layer-slider" min="1" max="${layers}" step="1" value="${v.layer}" aria-label="Layer">
            <span class="value" id="layer-value"></span>
          </div>
          <div class="player-options">
            <span class="muted">Speed</span>
            <select id="speed">${SPEEDS.map(([ms, label]) => `<option value="${ms}" ${v.speed === ms ? "selected" : ""}>${label}</option>`).join("")}</select>
            <label class="check"><input type="checkbox" id="loop" ${v.loop ? "checked" : ""}> Loop</label>
          </div>` : ""}
          ${v.tab === "membership" ? showRow([["only", "Component regions only", v.only]]) : ""}
          ${brainTab && coords ? showRow([["edges", "Component edges", v.opts.edges], ["other", "Other edges above threshold", v.opts.other],
                                          ["numbers", "Region numbers", v.opts.numbers], ["sulci", "Sulci", v.opts.sulci]]) : ""}
          <p class="figure-note" id="figure-note"></p>
          <div class="figure-tools">
            <button class="btn" data-action="save-figure">Save figure (SVG)…</button>
            <button class="btn" data-action="members">Member regions</button>
          </div>
        </div>
        <div class="card detail">
          <div class="card-title" style="margin-bottom: 10px">Component ${comp.id}</div>
          <dl>${rows.map(([k, val]) => `<dt>${esc(k)}</dt><dd>${esc(val)}</dd>`).join("")}</dl>
        </div>
      </div>
    </section>`;
}
function showRow(options) {
  return `<div class="show-row"><span class="muted">Show</span><div class="toggles">${options.map(([key, label, checked]) =>
    `<label class="check"><input type="checkbox" data-show="${key}" ${checked ? "checked" : ""}> ${esc(label)}</label>`).join("")}</div></div>`;
}
function summaryBlock(comp) {
  const { summary, notes } = report(comp);
  return `
    <section class="summary">
      <div class="summary-head"><div class="heading">Summary</div><button class="btn" data-action="copy-summary">Copy</button></div>
      <p>${esc(summary)}</p>
      <div class="notes-title">Notes</div>
      <ul class="notes">${notes.map((note) => `<li>${esc(note)}</li>`).join("")}</ul>
    </section>`;
}

function report(comp) {
  const result = S.result, cfg = result.config, axis = result.dataset.axis, geo = S.view.geo;
  const layers = result.dimensions.n_layers, nodes = result.dimensions.n_nodes;
  const classic = cfg.inference_mode === "classic";
  const alpha = result.reporting.alpha;
  const values = comp.layer_bins.map((b) => axis.values[b - 1]);
  const symbol = cfg.stat_type === "f" ? "F" : cfg.stat_type === "mean" ? "mean" : "t";
  const threshold = `${symbol} ${cfg.tail === "left" ? "< −" : "> "}${fmt(cfg.threshold)}` + (cfg.tail === "both" ? ", two-sided" : "");
  const size = cfg.metric === "extent" ? `extent = ${comp.extent} ${classic ? "edges" : "region–layer sites"}`
    : `${cfg.metric} = ${fmt(comp[cfg.metric], 3)}`;
  const edges = geo.compEdges.reduce((total, list) => total + list.length, 0);
  const where = classic ? `input layer ${cfg.classic_layer}` : `${axis.name.toLowerCase()} ${rangeLabel(values, axis.unit)}`;
  const summary = `A component showing ${direction(cfg, comp)} ${comp.p_fwe <= alpha ? "was identified" : "did not reach significance"} `
    + `(corrected p = ${fmt(comp.p_fwe, 3)}; ${size}; ${comp.n_nodes} regions, ${edges} edge${edges !== 1 ? "s" : ""}; `
    + `${where}; primary threshold ${threshold}; ${cfg.n_perm.toLocaleString("en")} permutations; ${methodName(cfg, layers)}).`;
  const notes = ["The corrected p-value applies to the component as a whole, not to individual regions, edges or layers."];
  const nulls = [...result.null_max].sort((a, b) => a - b);
  if (cfg.metric === "extent" && nulls.length) {
    const sites = nodes * layers;
    const median = nulls.length % 2 ? nulls[(nulls.length - 1) / 2] : (nulls[nulls.length / 2 - 1] + nulls[nulls.length / 2]) / 2;
    if (!classic && median / sites > 0.05) {
      notes.push(`Chance components are large here (median ${fmt(median)} of ${sites.toLocaleString("en")} sites), so components `
        + "chain readily at this threshold; consider a higher threshold.");
    }
  }
  if (!classic && layers > 2 && (comp.layer_bins.length === layers || comp.n_nodes >= 0.5 * nodes)) {
    notes.push(`The component covers ${comp.n_nodes} of ${nodes} regions and ${comp.layer_bins.length} of ${layers} layers, `
      + "so it is best described as a distributed effect.");
  }
  if (!classic) notes.push(`The ${axis.name.toLowerCase()} span is descriptive. It is not a corrected estimate of where the effect starts or stops.`);
  if (comp.p_fwe <= 1 / (cfg.n_perm + 1) + 1e-12) notes.push(`This p-value is the smallest possible with ${cfg.n_perm.toLocaleString("en")} permutations.`);
  notes.push(...(result.interpretation.warnings || []));
  return { summary, notes };
}

let lastWidth = 0;
function drawFigure() {
  const box = $("#figure");
  const comp = currentComponent();
  if (!box || !comp) return;
  const v = S.view, result = S.result;
  const width = Math.floor(box.clientWidth);
  lastWidth = width;
  const out = drawResult({ tab: v.tab, width, theme: S.theme, result, comp, geo: v.geo, layer: v.layer, view: v.view,
                           only: v.only, opts: v.opts, outlines });
  box.innerHTML = out.svg;
  $("#figure-note").textContent = out.note;
  const slider = $("#layer-slider");
  if (slider) {
    slider.value = v.layer;
    const axis = result.dataset.axis;
    $("#layer-value").textContent = `${fmt(axis.values[v.layer - 1])} ${axis.unit}`.trim();
  }
}
function stepLayer(increment) {
  const v = S.view, layers = S.result.dimensions.n_layers;
  let index = v.layer - 1 + increment;
  if (index >= layers || index < 0) {
    if (!v.loop && v.timer) {
      stopPlayer();
      return;
    }
    index = (index + layers) % layers;
  }
  v.layer = index + 1;
  drawFigure();
}
function stopPlayer() {
  if (S.view && S.view.timer) {
    clearInterval(S.view.timer);
    S.view.timer = null;
    const button = $("#play");
    if (button) button.textContent = "Play";
  }
}
function togglePlay() {
  const v = S.view;
  if (v.timer) {
    stopPlayer();
    return;
  }
  v.timer = setInterval(() => stepLayer(1), v.speed);
  $("#play").textContent = "Pause";
}

/* ---------- Reference pages (native_reference.py) ---------- */
function section(title, text = "", bullets = []) {
  return `<div class="section">${esc(title)}</div>${text ? `<p>${esc(text)}</p>` : ""}`
    + (bullets.length ? `<ul>${bullets.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>` : "");
}
function referencePage() {
  const topic = S.page;
  let body = "";
  if (topic === "method") {
    const details = {
      classic: ["Use for one network, or one layer chosen in advance.", "Component size: edges (extent) or summed excess over the threshold (intensity)."],
      layerwise: ["Use to find which layers show an effect, with one correction across all of them.", "Component size: region–layer sites (extent) or summed statistics (mass), within a layer."],
      multiplex: ["Use when an effect may continue across neighbouring frequencies or time points.", "Component size: region–layer sites (extent) or summed statistics (mass), across layers."],
    };
    body = `<div class="method-cards">${Object.entries(METHODS).map(([key, name]) => `
        <div class="card"><div class="card-title" style="margin-bottom: 10px">${name}</div>
          ${methodFigure(S.theme, key, { labels: false, legend: false })}
          <p>${esc(details[key][0])}</p><p class="muted">${esc(details[key][1])}</p></div>`).join("")}</div>`
      + section("How the correction works", "", [
        "Compute a test statistic for every edge in every layer, such as Welch's t for two groups.",
        "Keep the edges above the primary threshold and find the connected components.",
        "Repeat with shuffled labels many times and record the largest component each time. A component's corrected p "
          + "is the share of permutations with a component at least as large."])
      + `<div style="margin-top: 20px"><button class="btn" data-action="toggle-details">If you used the original NBS toolbox</button></div>`
      + (S.details ? section("Differences from NBS Connectome v1.2", "", [
        "A design matrix and contrast give the same GLM t or F test. The two-group shortcut uses Welch's t.",
        "Classic one-sample tests threshold the signed mean, as in v1.2. Multiplex one-sample tests use a t statistic.",
        "Corrected p uses (1 + exceedances) / (1 + permutations); v1.2 uses exceedances / permutations."]) : "");
  } else if (topic === "interpret") {
    body = `<div class="sketch" data-sketch="null"></div>`
      + section("What you can say", "The network differed between conditions across this set of regions and layers, with "
        + "the corrected p-value for the component.")
      + section("What you cannot say", "", [
        "That any one edge, region or layer inside the component is significant on its own.",
        "That the first and last layers mark where the effect starts or stops. The span is descriptive."])
      + section("Decide in advance", "Choose the method, threshold, tail and component measure before looking at results. "
        + "Trying several settings and keeping the best one adds comparisons that the correction does not cover.")
      + section("Assumptions", "", [
        "Shuffling group labels assumes participants are exchangeable when there is no effect.",
        "Sign flips (paired and one-sample tests) assume differences are symmetric around zero under the null.",
        "Residual permutation with covariates (Freedman–Lane) is approximate."])
      + section("Example", "In the demo, Classic NBS at 100 ms found a component of 3 edges joining 4 regions "
        + "(intensity 8.36, corrected p = .010; threshold 3, 99 permutations, seed 1).");
  } else if (topic === "inputs") {
    body = `<div class="sketch" data-sketch="data"></div>`
      + section("One combined file", "", [
        "Python .npz: W with shape participants × regions × regions × layers, for example (40, 32, 32, 8).",
        "MATLAB v7 .mat: W as regions × regions × layers × participants, or a cell array with one entry per participant.",
        "Leave out the layer dimension for one network per participant. Matrices must be real, finite and symmetric."])
      + section("One ZIP per group", "Put each participant's .mat or .npy file (or .csv, .tsv, .txt for one network) in a "
        + "folder for its group and zip each folder. Participants are ordered by file name.")
      + section("Study design", "", [
        "Two groups: one group label per participant.",
        "Paired conditions: each pair ID appears twice; the first observation is compared with the second.",
        "One sample: signed maps tested against zero.",
        "GLM: a design matrix X (one row per participant) and a contrast C."])
      + section("Layers and coordinates", "", [
        "axis_name, axis_unit and axis_values label the layers, for example Frequency, Hz, 1–100.",
        "node_coordinates (regions × 3, MNI mm) enable the brain view; node_labels name the regions."]);
  } else {
    body = section("Original method", "Zalesky A, Fornito A, Bullmore ET. Network-based statistic: identifying differences "
        + "in brain networks. NeuroImage (2010) 53: 1197–1207. doi:10.1016/j.neuroimage.2010.06.041")
      + `<button class="btn" data-action="copy-link" data-link="https://doi.org/10.1016/j.neuroimage.2010.06.041">Copy DOI link</button>`
      + section("Software contributors", "Minarose M. Ismail¹˒² · Brady J. Williamson³ · Darren S. Kadis¹˒²")
      + `<p class="muted">¹ Department of Physiology, University of Toronto, Toronto, Canada<br>
          ² Neurosciences &amp; Mental Health, The Hospital for Sick Children, Toronto, Canada<br>
          ³ Department of Radiology, College of Medicine, University of Cincinnati, Cincinnati, USA</p>`
      + section("Licence and source code", "Multiplex-NBS is free software under the GNU General Public License v3 or later. "
        + "The Python package, MATLAB toolbox, documentation and downloads are at github.com/Minarose/multiplex-nbs.")
      + `<button class="btn" data-action="copy-link" data-link="https://github.com/Minarose/multiplex-nbs">Copy project link</button>`
      + section("Example data", "The brain demo uses 32 regions of the openly licensed structural connectome of Škoch et al. "
        + "(2022), with AAL centroids (Tzourio-Mazoyer et al., 2002). Participants, groups, layers and effects are simulated.")
      + section("Further reading", "Sassenhagen J, Draschkow D. Cluster-based permutation tests of MEG/EEG data do not "
        + "establish significance of effect latency or location. Psychophysiology (2019) 56: e13335.");
  }
  return `
    <div class="reference">
      <div class="kicker">REFERENCE</div>
      <div class="page-title" style="margin-top: 6px">${esc(TOPICS[topic])}</div>
      <p class="lead2" style="margin-bottom: 6px">${esc(LEADS[topic])}</p>
      ${body}
      <hr>
      <button class="btn" data-go="${S.returnPage}">Return to ${esc(PAGES[S.returnPage] || "Overview")}</button>
    </div>`;
}
function drawSketches() {
  for (const box of document.querySelectorAll("[data-sketch]")) {
    const width = Math.max(320, Math.floor(box.clientWidth));
    box.innerHTML = box.dataset.sketch === "null" ? nullSketch(S.theme, width) : dataSketch(S.theme, width);
  }
}

const after = {
  home: drawOverview,
  results: () => {
    drawFigure();
    observer.disconnect();
    const area = $("#figure");
    if (area) observer.observe(area);
  },
};
const observer = new ResizeObserver(() => {
  const box = $("#figure");
  if (box && Math.abs(Math.floor(box.clientWidth) - lastWidth) > 2) drawFigure();
});
let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (S.page === "home") fitOverview();
    else if (TOPICS[S.page]) drawSketches();
  }, 80);
});

/* ---------- events ---------- */
const actions = {
  dismiss: () => { S.error = null; render(); },
  "try-demo": () => load({ kind: "demo", demo: "brain-network" }, "model"),
  "overview-mode": (el) => {
    S.overviewMode = el.dataset.mode;
    document.querySelectorAll('[data-action="overview-mode"]').forEach((b) => b.setAttribute("aria-pressed", b === el));
    drawOverview();
  },
  "data-source": (el) => { S.dataSource = el.dataset.value; render(); },
  "open-demo": () => load({ kind: "demo", demo: S.demoKind }, "model"),
  ...Object.fromEntries(Object.entries(dataActions).map(([key, fn]) => [key, async () => {
    try { await fn(); } catch (error) { showError(error.message); }
  }])),
  run,
  cancel,
  scope: (el) => {
    S.view.scope = el.dataset.value;
    const visible = visibleComponents();
    if (!visible.some((c) => c.id === S.view.comp)) selectComponent(S.view, S.result, visible[0] || null);
    stopPlayer();
    render();
  },
  "apply-alpha": async () => {
    try {
      const alpha = Number($("#alpha").value);
      if (!(alpha > 0 && alpha < 1)) throw new Error("Enter a number greater than zero and less than one.");
      const { value } = await call("set_alpha", { alpha });
      Object.assign(S.result, value);
      S.error = null;
      const visible = visibleComponents();
      if (!visible.some((c) => c.id === S.view.comp)) selectComponent(S.view, S.result, visible[0] || null);
      render();
    } catch (error) {
      showError(error.message, "Reporting cutoff");
    }
  },
  tab: (el) => { stopPlayer(); S.view.tab = el.dataset.tab; render(); },
  view: (el) => { S.view.view = el.dataset.value; render(); },
  step: (el) => stepLayer(Number(el.dataset.value)),
  play: togglePlay,
  "toggle-methods": () => { S.view.methods = !S.view.methods; render(); },
  "copy-methods": () => copy(S.result.methods),
  settings: () => {
    const r = S.result;
    textDialog("Complete settings", JSON.stringify({ settings: r.config, reporting: r.reporting, axis: r.dataset.axis,
                                                     software: r.software }, null, 2));
  },
  members: () => {
    const comp = currentComponent(), labels = S.result.dataset.node_labels;
    textDialog(`Member regions · component ${comp.id}`, comp.nodes.map((n) => `${n}. ${labels[n - 1]}`).join("\n"));
  },
  "copy-summary": () => copy(report(currentComponent()).summary),
  export: async (el) => {
    try {
      const { value, bytes } = await call("export", { kind: el.dataset.kind });
      download(bytes, value.filename, value.mime);
    } catch (error) {
      showError(error.message, "Could not save results");
    }
  },
  "save-figure": () => {
    const svg = $("#figure svg");
    if (!svg) return;
    download(new TextEncoder().encode(svg.outerHTML), `multiplex-nbs-component-${S.view.comp}-${S.view.tab}.svg`, "image/svg+xml");
  },
  "toggle-details": () => { S.details = !S.details; render(); },
  "copy-link": (el) => copy(el.dataset.link),
};

document.addEventListener("click", (event) => {
  const target = event.target;
  if (target.closest("dialog")) return;
  const goTo = target.closest("[data-go]");
  if (goTo && !goTo.disabled) { S.error = null; go(goTo.dataset.go); return; }
  const theme = target.closest("[data-theme-set]");
  if (theme) { setTheme(theme.dataset.themeSet); return; }
  const action = target.closest("[data-action]");
  if (action && actions[action.dataset.action]) { actions[action.dataset.action](action, event); return; }
  const row = target.closest("tr[data-comp]");
  if (row) {
    stopPlayer();
    selectComponent(S.view, S.result, S.result.clusters.find((c) => c.id === Number(row.dataset.comp)));
    render();
    return;
  }
  const panel = target.closest("[data-layer]");
  if (panel) {
    S.view.layer = Number(panel.dataset.layer);
    S.view.tab = "brain";
    render();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.target.closest && event.target.closest("dialog")) return;
  const row = event.target.closest && event.target.closest("tr[data-comp]");
  if (row && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    row.click();
  } else if (event.target.id === "alpha" && event.key === "Enter") {
    actions["apply-alpha"]();
  }
});

document.addEventListener("input", (event) => {
  const el = event.target;
  if (el.closest("dialog")) return;
  if (el.id === "layer-slider") { stopPlayer(); S.view.layer = Number(el.value); drawFigure(); }
  else if (S.page === "model" && el.tagName === "INPUT" && el.type === "text") {
    modelChanged(el.id, el.value);
    refreshModelNotice();
  }
});

document.addEventListener("change", async (event) => {
  const el = event.target;
  if (el.closest("dialog")) return;
  if (el.id === "combined-file" && el.files[0]) {
    const file = el.files[0];
    load({ kind: "file", name: file.name, bytes: await file.arrayBuffer() });
  } else if (el.id === "group-zips" && el.files.length) {
    chooseArchives([...el.files]);
    el.value = "";
  } else if (el.id === "coords-file" && el.files[0]) {
    chooseCoordinates(el.files[0]);
    el.value = "";
  } else if (el.name === "demo") {
    S.demoKind = el.value;
  } else if (S.page === "model") {
    const value = el.type === "checkbox" ? el.checked : el.value;
    if (modelChanged(el.id, value)) render();
    else refreshModelNotice();
  } else if (el.id === "speed") {
    S.view.speed = Number(el.value);
    if (S.view.timer) { stopPlayer(); togglePlay(); }
  } else if (el.id === "loop") {
    S.view.loop = el.checked;
  } else if (el.dataset.show) {
    if (el.dataset.show === "only") S.view.only = el.checked;
    else S.view.opts[el.dataset.show] = el.checked;
    drawFigure();
  }
});

/* ---------- start ---------- */
document.documentElement.dataset.theme = S.theme;
startWorker();
render();
