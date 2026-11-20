# Multiplex-NBS in the browser (prototype)

The full app as a web page. The analysis is the same `multiplex_nbs` Python package, run in the
browser with [Pyodide](https://pyodide.org) (Python, NumPy and SciPy compiled to WebAssembly).
There is no server-side code: files are read by the browser tab and never uploaded.

## Run it locally

```bash
python web/build.py                                   # packs the engine into web/engine.zip
python -m http.server 8800 --directory web            # then open http://localhost:8800
```

`build.py` must be re-run after changing anything in `multiplex_nbs/` or `web/bridge.py`.

## How it fits together

| File | Role |
| --- | --- |
| `index.html`, `app.css` | Page shell and styles (Light, Dark and Mono, as in the desktop app). |
| `app.js` | Pages, state, and messages to the engine. |
| `figures.js` | Overview schematic and results figures, drawn as SVG (ports of the desktop figures). |
| `worker.js` | Loads Pyodide 314.0.7 (Python 3.14) from jsDelivr in a module worker and calls `bridge.py`. |
| `bridge.py` | JSON-in, JSON-out wrappers around `multiplex_nbs.io` (load, describe, run, export). |
| `build.py` | Writes `engine.zip` (the package without the Tk app, plus `bridge.py`) and `glass-brain.json`. |

The first visit downloads about 30 MB (Python, NumPy, SciPy), which the browser then caches.
The page's Content Security Policy allows code only from this site and the pinned Pyodide
release; nothing in the page sends data anywhere. Cancelling a run replaces the worker and
reloads the dataset into the new one.

## Publishing

`.github/workflows/web.yml` builds the site on every push to `web/prototype` and publishes it to the
`gh-pages` branch, which GitHub Pages serves at https://minarose.github.io/multiplex-nbs/.

## Not done yet

- Self-hosting the Pyodide files instead of loading them from jsDelivr.
- Larger studies: a browser tab has a few GB of memory and runs on one core.
