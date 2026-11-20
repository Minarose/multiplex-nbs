"""Prepare the browser app: pack the engine into web/engine.zip and copy the glass-brain outlines.

Run from anywhere:  python web/build.py
Then serve the web folder, for example:  python -m http.server 8800 --directory web
"""
import shutil
import zipfile
from pathlib import Path

web = Path(__file__).resolve().parent
root = web.parent
package = root / "multiplex_nbs"


def wanted(path):
    # The browser needs the engine, its data files and the glass-brain outlines, not the Tk app.
    return (path.is_file() and "__pycache__" not in path.parts
            and not path.name.startswith("native_") and path.name != "__main__.py")


with zipfile.ZipFile(web / "engine.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(package.rglob("*")):
        if wanted(path):
            archive.write(path, path.relative_to(root).as_posix())
    archive.write(web / "bridge.py", "bridge.py")
shutil.copyfile(package / "static" / "glass-brain.json", web / "glass-brain.json")
print(f"Wrote {web / 'engine.zip'} ({(web / 'engine.zip').stat().st_size / 1024:.0f} KB) and glass-brain.json")
