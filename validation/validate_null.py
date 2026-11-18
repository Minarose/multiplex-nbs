"""Small global-null calibration, not a comprehensive methods validation.

Run from the repository: python validation/validate_null.py --output docs/null-calibration.json
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from multiplex_nbs import __version__, analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicates", type=int, default=100)
    parser.add_argument("--permutations", type=int, default=199)
    parser.add_argument("--seed", type=int, default=20261106)
    parser.add_argument("--output", type=Path, default=Path("results/null-calibration.json"))
    args = parser.parse_args()
    if args.replicates < 1 or args.permutations < 19:
        parser.error("Use at least one replicate and 19 permutations.")
    rng = np.random.default_rng(args.seed)
    scenarios = []
    # Each observation is an entire network map. Layer and edge dependence
    # within an observation is retained by the permutation/sign-flip scheme.
    for design in ("two-sample", "paired"):
        for adjacency in ("consecutive", "independent"):
            rejected = 0
            for _ in range(args.replicates):
                s, n, layers = 24, 8, 6
                i, j = np.triu_indices(n, 1)
                y = rng.normal(size=(s, len(i), layers))
                for k in range(1, layers):
                    y[:, :, k] = .5 * y[:, :, k-1] + np.sqrt(.75) * y[:, :, k]
                y += .25 * rng.normal(size=(s, 1, layers))
                w = np.zeros((s, n, n, layers))
                w[:, i, j] = y
                w[:, j, i] = y
                group = np.repeat([0, 1], 12) if design == "two-sample" else np.tile(np.arange(12), 2)
                result = analyze(w, group=group, test=design, threshold=3,
                                 tail="both", metric="extent", n_perm=args.permutations,
                                 seed=int(rng.integers(0, 2**32)), layer_adjacency=adjacency)
                rejected += any(c["p_fwe"] <= .05 for c in result["clusters"])
            interval = binomtest(rejected, args.replicates).proportion_ci(confidence_level=.95, method="exact")
            scenario = {"design": design, "adjacency": adjacency, "replicates": args.replicates,
                        "any_rejection_count": rejected, "estimated_global_null_fwer": rejected / args.replicates,
                        "binomial_95_percent_ci": [interval.low, interval.high]}
            scenarios.append(scenario)
            print(json.dumps(scenario), flush=True)
    report = {"software_version": __version__, "seed": args.seed, "permutations": args.permutations,
              "alpha": .05, "threshold": 3, "tail": "both", "metric": "extent",
              "shape": [24, 8, 8, 6], "layer_ar1_coefficient": .5,
              "edge_shared_noise_scale": .25,
              "scope": "Small complete global-null Gaussian scenarios only; not a comprehensive FWER/power validation, and not evidence of localized inference.",
              "scenarios": scenarios}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
