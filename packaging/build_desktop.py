"""Freeze the native or local-browser application on its target OS."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--native", action="store_true", help="Accepted for compatibility; the desktop app is always native")
parser.parse_args()
native = True
root = Path(__file__).resolve().parents[1]
package = root / "multiplex_nbs"
static = package / "static"
dist = root / "dist"
build = root / "build"
if native:
    dist, build = dist / "native", build / "native"
    entry = "native_entry.py"
    assets = {"glass-brain.json", "glass-brain-LICENSE.txt"}
    excluded = ["multiplex_nbs.server", "http.server", "webbrowser"]
demo_files = ("skoch2022_mean32.npz", "skoch2022_provenance.json", "aal_centroids_mni.json",
              "ATTRIBUTION.md", "LICENSE-CC-BY-4.0.txt")
data_files = [package / "data" / name for name in demo_files] + [static / name for name in sorted(assets)]
options = []
for source in data_files:
    if source.is_file():
        options += ["--add-data", f"{source}:{source.parent.relative_to(root).as_posix()}"]
    else:
        raise FileNotFoundError(source)
if sys.platform == "darwin":
    identifier = "ca.multiplexnbs.research.native" if native else "ca.multiplexnbs.research"
    options += ["--osx-bundle-identifier", identifier]
# Optional dependencies in a developer's environment must stay out of the build.
for name in ("webview", "multiplex_nbs.window", "matplotlib", "pandas", "IPython",
             "pytest", "PIL", "lxml", "openpyxl", *excluded):
    options += ["--exclude-module", name]
subprocess.run([
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
    "--onedir", "--name", "MultiplexNBS", "--paths", str(root),
    "--distpath", str(dist), "--workpath", str(build),
    "--specpath", str(build), *options, str(root / "packaging" / entry),
], check=True)
