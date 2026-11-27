"""Command line: ``multiplex-nbs`` (or ``python -m multiplex_nbs``).

    multiplex-nbs                      open the desktop app
    multiplex-nbs app                  open the desktop app
    multiplex-nbs demo demo.npz        write a practice dataset
    multiplex-nbs run data.npz --output result.json [options]
"""
import argparse
from pathlib import Path

from . import __version__
from .toolbox import DESIGNS, METHODS, load_dataset, load_demo, nbs, save_dataset, save_results


def main(argv=None):
    parser = argparse.ArgumentParser(prog="multiplex-nbs", description="Multiplex-NBS: network-based statistics "
                                     "for one network or a stack of networks.")
    parser.add_argument("--version", action="version", version=f"multiplex-nbs {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("app", help="Open the desktop app")
    demo = sub.add_parser("demo", help="Write a practice dataset (.npz)")
    demo.add_argument("output", type=Path)
    demo.add_argument("--name", choices=["brain-network", "two-sample", "paired", "glm"], default="brain-network")
    run = sub.add_parser("run", help="Run an analysis on a .npz or .mat dataset",
                         description="Results are saved by file extension: .json, .mat, .csv or .txt.")
    run.add_argument("input", type=Path)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--method", choices=METHODS, default="multiplex")
    run.add_argument("--design", choices=DESIGNS, help="Default: the design the dataset supports.")
    run.add_argument("--threshold", type=float, default=3.0)
    run.add_argument("--tail", choices=["right", "left", "both"], default="right")
    run.add_argument("--metric", choices=["extent", "mass", "intensity"], default="extent")
    run.add_argument("--n-perm", type=int, default=9999)
    run.add_argument("--seed", type=int, default=1)
    run.add_argument("--alpha", type=float, default=0.05)
    run.add_argument("--layer", type=int, help="Classic NBS on a stack: the 1-based layer chosen in advance.")
    run.add_argument("--permutation", choices=["auto", "freedman-lane", "rowshuffle"], default="auto")
    run.add_argument("--use-abs", action="store_true")
    args = parser.parse_args(argv)
    if args.command in (None, "app"):
        from .native_app import main as open_app
        open_app()
    elif args.command == "demo":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        print(save_dataset(load_demo(args.name), args.output))
    else:
        result = nbs(load_dataset(args.input), method=args.method, design=args.design, threshold=args.threshold,
                     tail=args.tail, metric=args.metric, n_perm=args.n_perm, seed=args.seed, alpha=args.alpha,
                     layer=args.layer, permutation=args.permutation, use_abs=args.use_abs)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        save_results(result, args.output)
        print(f"{result['interpretation']['headline']}. Saved to {args.output}")


if __name__ == "__main__":
    main()
