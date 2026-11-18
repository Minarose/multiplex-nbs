"""Test and zip the bundle on its target platform; does not publish a release."""
import argparse
import hashlib
import json
import os
from importlib.metadata import distribution, version
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--native", action="store_true", help="Accepted for compatibility; the desktop app is always native")
parser.parse_args()
native = True
root = Path(__file__).resolve().parents[1]
dist = root / "dist"
if native:
    dist = dist / "native"
mac = sys.platform == "darwin"
bundle = dist / ("MultiplexNBS.app" if mac else "MultiplexNBS")
executable = bundle / ("Contents/MacOS/MultiplexNBS" if mac else ("MultiplexNBS.exe" if sys.platform == "win32" else "MultiplexNBS"))
report = dist / "desktop-self-test.json"
report.unlink(missing_ok=True)
trace = report.with_suffix(".trace.txt")
trace.unlink(missing_ok=True)
with tempfile.TemporaryDirectory() as isolated:
    try:
        subprocess.run([str(executable), "--self-test", str(report)], cwd=isolated, timeout=180, check=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        for diagnostic in (trace, report):
            if diagnostic.exists():
                print(diagnostic.read_text(encoding="utf-8"), flush=True)
        raise
self_test = json.loads(report.read_text(encoding="utf-8"))
if not self_test.get("ok"):
    raise SystemExit("Compiled application self-test did not pass.")


def native_inventory():
    from PyInstaller.archive.readers import CArchiveReader

    archive_reader = CArchiveReader(str(executable))
    pyz_name, = [name for name in archive_reader.toc if name.endswith(".pyz")]
    modules = set(archive_reader.open_embedded_archive(pyz_name).toc)
    forbidden = {"multiplex_nbs.server", "multiplex_nbs.window", "http.server", "webview", "webbrowser"}
    unexpected = modules.intersection(forbidden)
    missing = {"tkinter", "multiplex_nbs.native_app", "multiplex_nbs.core", "multiplex_nbs.io"} - modules
    if unexpected or missing:
        raise SystemExit(f"Unexpected frozen modules: {sorted(unexpected)}. Missing modules: {sorted(missing)}.")
    files = [p for p in bundle.rglob("*") if p.is_file()]
    web_assets = [p for p in files if p.suffix.lower() in {".htm", ".html", ".js", ".mjs"}]
    if web_assets:
        raise SystemExit(f"Unexpected web asset in the native distribution: {web_assets[0]}")
    if set(self_test.get("toolkit_scripts", {})) != {"init.tcl", "tk.tcl"}:
        raise SystemExit("The compiled native GUI did not resolve both Tcl/Tk startup scripts.")
    toolkit_binaries = {p.name for p in files if p.name.lower() in {"tcl", "tk"} or
                        (p.suffix.lower() in {".dll", ".dylib"} and
                         p.name.lower().startswith(("tcl", "tk", "libtcl", "libtk")))}
    if not all(any(toolkit in name.lower() for name in toolkit_binaries) for toolkit in ("tk", "tcl")):
        raise SystemExit("The native distribution lacks its Tcl/Tk dynamic libraries.")
    if self_test["ui"] != "tkinter" or self_test["web_modules_loaded"] or self_test["network_or_browser_events"]:
        raise SystemExit("The self-test did not verify a standalone native GUI.")
    if not all(self_test["observed_components"].get(mode, 0) for mode in ("classic", "multiplex")):
        raise SystemExit("The compiled app must produce Classic and Multiplex demo components.")
    return {"tcl": self_test["tcl"], "tk": self_test["tk"], "toolkit_binaries": sorted(toolkit_binaries),
            "toolkit_scripts": self_test["toolkit_scripts"],
            "python_modules": len(modules),
            "application_modules": sorted(name for name in modules if name.startswith("multiplex_nbs.")),
            "excluded_modules_checked": sorted(forbidden), "web_assets": len(web_assets)}


def macos_minimum(app):
    """Highest minimum macOS version declared by any Mach-O file in the bundle."""
    highest, source = (0,), None
    for path in app.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as handle:
            magic = handle.read(4)
        if magic not in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"):
            continue
        lines = subprocess.run(["otool", "-l", str(path)], capture_output=True, text=True, check=True).stdout.splitlines()
        for number, line in enumerate(lines):
            line = line.strip()
            if line.startswith("minos ") or (line.startswith("version ") and "LC_VERSION_MIN_MACOSX" in "".join(lines[max(0, number - 3):number])):
                version = tuple(int(part) for part in line.split()[1].split("."))
                if version > highest:
                    highest, source = version, path.relative_to(app)
    return ".".join(map(str, highest[:2] if len(highest) > 1 else highest + (0,))), source


minimum_macos = None
if mac:
    minimum_macos, needs_it = macos_minimum(bundle)
    print(f"Minimum macOS: {minimum_macos} (set by {needs_it})")
    limit = os.environ.get("MNBS_MACOS_MIN")
    if limit and tuple(map(int, minimum_macos.split("."))) > tuple(map(int, limit.split("."))):
        raise SystemExit(f"{needs_it} requires macOS {minimum_macos}, newer than the {limit} target.")
system = "macOS" if mac else platform.system()
architecture = platform.machine().lower().replace("amd64", "x86_64")
archive = dist / f"Multiplex-NBS-{self_test['version']}-{system}-{architecture}.zip"
archive.unlink(missing_ok=True)
if mac:
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(bundle), str(archive)], check=True)
else:
    shutil.make_archive(str(archive.with_suffix("")), "zip", dist, bundle.name)


def git_output(*args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


commit = os.environ.get("GITHUB_SHA")
if commit:
    if commit != git_output("rev-parse", "HEAD"):
        raise SystemExit("Checkout revision differs from GitHub build revision.")
else:
    try:
        commit = git_output("rev-parse", "HEAD")
    except (FileNotFoundError, subprocess.CalledProcessError):
        commit = None
modified = None if commit is None else bool(git_output(
    "status", "--porcelain", "--", "multiplex_nbs", "packaging", "pyproject.toml", "docs", ".github/workflows"))
if os.environ.get("GITHUB_ACTIONS") and modified:
    raise SystemExit("Build inputs differ from the checked out revision.")
manifest = {
    "application": "Multiplex-NBS", "version": self_test["version"], "build": self_test.get("build"),
    "target": f"{system}-{architecture}", "git_commit": commit, "modified_build_inputs": modified,
    "python": platform.python_version(),
    "packages": {name: version(name) for name in ("numpy", "scipy", "pyinstaller", "pyinstaller-hooks-contrib")},
    "macos_minimum_from_binaries": minimum_macos,
    "frozen_self_test": self_test,
}
if native:
    manifest["interface"] = "native Tk desktop"
    manifest["native_inventory"] = native_inventory()
manifest_path = dist / "build-manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
with zipfile.ZipFile(archive, "a", compression=zipfile.ZIP_DEFLATED) as package:
    for guide in ("app-guide.md", "data-format.md", "interpreting-results.md", "method.md", "classic-nbs-parity.md",
                  "demo-data.md", "validation.md", "limitations.md", "security-and-privacy.md", "contributors.md"):
        package.write(root / "docs" / guide, f"Documentation/{guide}")
    package.write(root / "LICENSE", "LICENSE.txt")
    package.write(root / "CITATION.cff", "CITATION.cff")
    package.write(manifest_path, "build-manifest.json")
    if mac:
        first_open = (f"The bundled binaries require macOS {minimum_macos} or later. Open MultiplexNBS.app.\n"
                      "This development build has an ad-hoc signature and lacks Apple notarization.")
    elif sys.platform == "win32":
        first_open = ("Use 64-bit Windows. Open MultiplexNBS.exe inside the extracted MultiplexNBS\n"
                      "folder and keep the folder together. This development build is unsigned.")
    else:
        first_open = "Open MultiplexNBS in the extracted MultiplexNBS folder."
    package.writestr("START-HERE.txt", f"""Multiplex-NBS {manifest['version']} · desktop app · {system} {architecture}

Extract the whole archive. {first_open}
If the operating system blocks the first launch, see "Opening the app for the first
time" in Documentation/app-guide.md, and follow your institution's software policy.

Start on Overview and choose Try the demo, or open your own data on the Data page.
All analysis runs locally on your computer; no data leave it. Python is included.
Export the results you need before closing the app.

Multiplex-NBS is free software under the GNU General Public License v3 (LICENSE.txt).
Cite it using CITATION.cff. Build details are in build-manifest.json and the
licences of bundled components are in "Third-party licenses".
Source code, Python and MATLAB toolboxes: https://github.com/Minarose/multiplex-nbs
""")
    for dependency in ("numpy", "scipy", "pyinstaller"):
        installed = distribution(dependency)
        for item in installed.files or []:
            parts = Path(item).parts
            if any(part.endswith(".dist-info") for part in parts) and ("license" in str(item).lower() or "copying" in str(item).lower()):
                source = Path(installed.locate_file(item))
                if source.is_file():
                    package.write(source, f"Third-party licenses/{dependency}/{item.as_posix()}")
    python_license = Path(sys.base_prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "LICENSE.txt"
    if not python_license.exists():
        python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.exists():
        raise SystemExit("The Python runtime license is missing.")
    package.write(python_license, "Third-party licenses/Python-LICENSE.txt")
    package.write(root / "multiplex_nbs" / "static" / "glass-brain-LICENSE.txt", "Third-party licenses/nilearn-glass-brain-LICENSE.txt")
    if native:
        for toolkit in ("tcl", "tk"):
            license_file = root / "packaging" / "licenses" / f"{toolkit}-license.txt"
            package.write(license_file, f"Third-party licenses/{license_file.name}")
with zipfile.ZipFile(archive) as completed:
    bad_entry = completed.testzip()
    if bad_entry is not None:
        raise SystemExit(f"Archive verification failed at {bad_entry}.")
with archive.open("rb") as contents:
    digest = hashlib.file_digest(contents, "sha256").hexdigest()
archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
print(archive)
