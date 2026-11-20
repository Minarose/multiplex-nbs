// Runs the Python engine (Pyodide) off the page's main thread so the interface stays responsive.
// Python, NumPy and SciPy are downloaded from the jsDelivr CDN once and then cached by the browser.
// Data files are written to this worker's in-memory file system; nothing is sent over the network.
// A module worker: Pyodide is imported like any ES module (a CORS request, as fetch makes).
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";

const API = new Set(["open_demo", "open_file", "open_archives", "set_coordinates", "run", "set_alpha", "export",
                     "dataset_fields", "labels_from_table", "edit_groups", "edit_glm", "edit_axis", "save_dataset"]);
const FILES = new Set(["export", "save_dataset"]);
const started = performance.now();
let pyodide, bridge;

const say = (text) => postMessage({ type: "status", text });

async function boot() {
  say("Downloading Python");
  pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  say("Loading NumPy and SciPy");
  await pyodide.loadPackage(["numpy", "scipy"]);
  say("Loading the Multiplex-NBS engine");
  const engine = await fetch("engine.zip", { cache: "no-cache" });
  if (!engine.ok) throw new Error("engine.zip is missing. Run web/build.py first.");
  pyodide.unpackArchive(await engine.arrayBuffer(), "zip", { extractDir: "/home/pyodide/engine" });
  pyodide.runPython("import sys; sys.path.insert(0, '/home/pyodide/engine')");
  bridge = pyodide.pyimport("bridge");
  postMessage({ type: "ready", versions: JSON.parse(bridge.versions("null")),
                seconds: (performance.now() - started) / 1000 });
}

const booted = boot().catch((error) => {
  postMessage({ type: "fatal", text: String((error && error.message) || error) });
  throw error;
});

function lastLine(error) {
  const lines = String((error && error.message) || error).trim().split("\n");
  return lines[lines.length - 1];
}

onmessage = async ({ data: { id, fn, args, files } }) => {
  try {
    await booted;
  } catch {
    postMessage({ type: "error", id, text: "The Python engine did not start." });
    return;
  }
  try {
    if (!API.has(fn)) throw new Error("Unknown request " + fn);
    for (const file of files || []) {
      pyodide.FS.mkdirTree(file.path.slice(0, file.path.lastIndexOf("/")));
      pyodide.FS.writeFile(file.path, new Uint8Array(file.bytes));
    }
    const argument = JSON.stringify(args ?? null);
    const text = fn === "run"
      ? bridge.run(argument, (done, total) => postMessage({ type: "progress", done, total }))
      : bridge[fn](argument);
    const value = JSON.parse(text);
    if (value && typeof value === "object" && "error" in value && Object.keys(value).length === 1) {
      postMessage({ type: "error", id, text: value.error });
      return;
    }
    const message = { type: "result", id, value };
    const transfer = [];
    if (FILES.has(fn)) {
      message.bytes = pyodide.FS.readFile(value.path);
      pyodide.FS.unlink(value.path);
      transfer.push(message.bytes.buffer);
    }
    postMessage(message, transfer);
  } catch (error) {
    postMessage({ type: "error", id, text: "Unexpected error: " + lastLine(error), detail: String(error) });
  }
};
