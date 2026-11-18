"""Regenerate the glass-brain outlines used by the GUI's Brain view.

Run from the repository root with nilearn installed (build time only):

    python tools/build_glass_brain.py

nilearn ships hand-drawn schematic outlines of the MNI152 brain together with
the affine transforms that place them in MNI millimetres. This script converts
them to SVG path strings in MNI mm (SVG y = -MNI) and writes
multiplex_nbs/static/glass-brain.json plus nilearn's BSD-3-Clause licence.
nilearn is not a runtime dependency of Multiplex-NBS.
"""
import json
from importlib.metadata import distribution
from pathlib import Path

import nilearn
import nilearn.plotting

root = Path(__file__).resolve().parents[1]
static = root / "multiplex_nbs" / "static"
source = Path(nilearn.plotting.__file__).parent / "glass_brain_files"
# Same affine parameters nilearn uses in nilearn/plotting/glass_brain.py.
TRANSFORMS = {"side": [0.38, 0, 0, 0.38, -108, -70],
              "back": [0.39, 0, 0, 0.39, -73, -73],
              "top": [0.36, 0, 0, 0.37, -71, -107]}


def view(name):
    a, b, c, d, e, f = TRANSFORMS[name]
    content = json.loads((source / f"brain_schematics_{name}.json").read_text())
    paths = []
    for path in content["paths"]:
        parts = []
        for item in path["items"]:
            pts = [(a * x + c * y + e, -(b * x + d * y + f)) for x, y in item["pts"]]
            command = "C" if item["type"] == "bezier" and len(pts) == 4 else "Q" if len(pts) == 3 else "L"
            parts.append(f"M{pts[0][0]:.1f} {pts[0][1]:.1f}{command}" + " ".join(f"{x:.1f} {y:.1f}" for x, y in pts[1:]))
        grey = path["edgecolor"].lower() != "#000000"
        # o = outer contour, i = inner contour, s = sulcus
        paths.append({"k": "s" if grey else ("o" if path["linewidth"] >= 2 else "i"), "d": "".join(parts)})
    x0, x1, y0, y1 = content["metadata"]["bounds"]
    box = [a * x0 + e, -(d * y1 + f), a * (x1 - x0), d * (y1 - y0)]
    return {"box": [round(v, 1) for v in box], "paths": paths}


outlines = {
    "source": f"nilearn {nilearn.__version__} glass-brain schematics (MNI152), converted to MNI mm",
    "license": "BSD-3-Clause; see glass-brain-LICENSE.txt",
    "views": {name: view(name) for name in TRANSFORMS},
}
(static / "glass-brain.json").write_text(json.dumps(outlines, separators=(",", ":")) + "\n")
license_text = next(f for f in distribution("nilearn").files if "LICENSE" in f.name).read_text()
(static / "glass-brain-LICENSE.txt").write_text(
    "The glass-brain outlines in glass-brain.json are derived from the brain\n"
    "schematics distributed with nilearn (https://nilearn.github.io).\n\n" + license_text)
print("wrote", static / "glass-brain.json", f"{(static / 'glass-brain.json').stat().st_size / 1e3:.0f} kB")
