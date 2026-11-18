"""Quick start: run Multiplex-NBS on the bundled brain demo and read the result.

    pip install multiplex-nbs        # or: pip install -e .  from a clone
    python examples/python/01_quickstart.py

The demo is an open human structural connectome (32 regions) with 40 simulated
participants in two groups and 8 time windows. Group A was simulated to be higher
along a left sensorimotor–parietal chain at 100–200 ms.
"""
from multiplex_nbs import components, load_demo, multiplex_nbs, report, save_results

data = load_demo("brain-network")
print(f"{data['W'].shape[0]} observations, {data['W'].shape[1]} regions, {data['W'].shape[3]} time windows")

# Choose the threshold, tail and component measure before looking at results.
# Use at least 5000 permutations for anything you report; 999 keeps the demo fast.
result = multiplex_nbs(data, threshold=3.0, tail="right", metric="extent", n_perm=999, seed=1)

print(result["interpretation"]["headline"])
for c in components(result, significant_only=True):
    print(f"Component {c['id']}: corrected p = {c['p_fwe']:.3g}, {c['extent']} region–time sites, "
          f"{c['n_regions']} regions, {c['axis_values'][0]:g}–{c['axis_values'][-1]:g} ms")
    print("  regions:", ", ".join(c["regions"]))

print("\nMethods paragraph to adapt for a paper:\n" + result["methods"])

save_results(result, "quickstart_result.json")   # everything, reloadable with load_results
save_results(result, "quickstart_components.csv")  # one row per component
with open("quickstart_report.txt", "w", encoding="utf-8") as handle:
    handle.write(report(result))
print("\nSaved quickstart_result.json, quickstart_components.csv and quickstart_report.txt")
