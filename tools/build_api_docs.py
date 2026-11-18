"""Generate docs/python-api.md and docs/matlab-api.md from the code's own documentation.

    python tools/build_api_docs.py          # write the files
    python tools/build_api_docs.py --check  # fail if they are out of date (used in CI)
"""
import argparse
import inspect
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
import multiplex_nbs  # noqa: E402

PY_GROUPS = [
    ("Run an analysis", ["nbs", "multiplex_nbs", "layerwise_nbs", "classic_nbs"]),
    ("Prepare data", ["make_dataset", "load_dataset", "save_dataset", "build_dataset", "load_demo", "describe"]),
    ("Read and save results", ["components", "report", "set_alpha", "save_results", "load_results"]),
    ("Figures (optional matplotlib)", ["plot_layer_profile", "plot_membership", "plot_null_distribution"]),
    ("Lower-level engine", ["analyze", "build_clusters"]),
    ("Desktop app", ["open_app"]),
]
MATLAB_ORDER = ["mnbs_analyze", "mnbs_load_demo", "mnbs_gui", "mnbs_demo", "mnbs_edgestat_group",
                "mnbs_edgestat_glm", "mnbs_components", "mnbs_permute", "mnbs_permute_glm", "mnbs_summarize",
                "mnbs_selftest", "mnbs_tcdf"]


def python_api():
    lines = ["# Python API", "",
             "Generated from the docstrings by `tools/build_api_docs.py`; the same text is shown by "
             "`help(multiplex_nbs.<function>)`. Install with `pip install multiplex-nbs` and import with "
             "`import multiplex_nbs`.", ""]
    for title, names in PY_GROUPS:
        lines.append(f"- **{title}:** " + ", ".join(f"[`{n}`](#{n})" for n in names))
    lines.append("")
    for title, names in PY_GROUPS:
        lines += [f"## {title}", ""]
        for name in names:
            function = getattr(multiplex_nbs, name)
            signature = str(inspect.signature(function))
            lines += [f"### {name}", "", "```python", f"{name}{signature}", "```", "",
                      "```text", inspect.cleandoc(function.__doc__ or "No documentation."), "```", ""]
    return "\n".join(lines)


def matlab_help(path):
    lines = path.read_text(encoding="utf-8").split("\n")
    signature = lines[0].replace("function", "", 1).strip()
    body = []
    for line in lines[1:]:
        if not line.lstrip().startswith("%"):
            break
        body.append(re.sub(r"^\s*% ?", "", line))
    return signature, "\n".join(body).rstrip()


def matlab_api():
    lines = ["# MATLAB API", "",
             "Generated from each function's help text by `tools/build_api_docs.py`; the same text is shown by "
             "`help <function>` in MATLAB. Add the toolbox with `addpath('multiplex-nbs/matlab')`. "
             "Needs base MATLAB R2021a or newer; no other toolbox.", ""]
    lines += [f"- [`{n}`](#{n})" for n in MATLAB_ORDER] + [""]
    for name in MATLAB_ORDER:
        signature, text = matlab_help(root / "matlab" / f"{name}.m")
        lines += [f"## {name}", "", "```matlab", signature, "```", "", "```text", text, "```", ""]
    return "\n".join(lines)


parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
check = parser.parse_args().check
stale = []
for name, text in (("python-api.md", python_api()), ("matlab-api.md", matlab_api())):
    target = root / "docs" / name
    if check:
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            stale.append(name)
    else:
        target.write_text(text, encoding="utf-8")
        print("wrote", target.relative_to(root))
if stale:
    sys.exit(f"Out of date: {', '.join(stale)}. Run python tools/build_api_docs.py")
