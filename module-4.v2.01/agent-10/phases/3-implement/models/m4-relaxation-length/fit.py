"""Fit M4 (relaxation-length on V1 kinematic core) on the frozen train split.

Fits one parameter per platform — `sigma` (meters, the relaxation length) —
against pooled yaw RMSE on train, evaluates on dev for the gap report,
merges into coeffs.json (never overwrites other platforms).

V1's per-platform constants (`g`, `L_eff`, `K_us`, δ₀ policy) are NOT
fitted — this is what makes M4 orthogonal to V1.

Usage:
    python fit.py                   # fits all platforms with truth
    python fit.py --platforms FORD_F_150_LIGHTNING_MK1 HYUNDAI_IONIQ_5
    python fit.py --objective cte   # CTE-aware fit
    python fit.py --with-bounds     # L-BFGS-B with σ ∈ [0.05, 2.0]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Resolve template root + skill imports
HERE = Path(__file__).resolve().parent
TPL  = HERE.parents[3]
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "fit-model"))

from _shared.frozen_split import train_paths, dev_paths  # noqa: E402
from fit import fit, format_fit_summary  # noqa: E402

from model import predict_factory  # noqa: E402

PLATFORMS_WITH_TRUTH = [
    "FORD_F_150_LIGHTNING_MK1",
    "FORD_MUSTANG_MACH_E_MK1",
    "HYUNDAI_IONIQ_5",
]

# Sensible automotive prior — relaxation length is typically 0.3–1.2 m.
SIGMA_PRIOR = 0.5


def initial_coeffs(platforms) -> dict[str, dict[str, float]]:
    return {plat: {"sigma": SIGMA_PRIOR} for plat in platforms}


def default_bounds(platforms) -> dict[str, dict[str, tuple[float, float]]]:
    return {plat: {"sigma": (0.05, 2.0)} for plat in platforms}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--platforms", nargs="+", default=PLATFORMS_WITH_TRUTH)
    p.add_argument("--objective", default="yaw",
                   choices=["yaw", "cte", "yaw_plus_cte"])
    p.add_argument("--max-iter", type=int, default=30)
    p.add_argument("--with-bounds", action="store_true",
                   help="Use L-BFGS-B with σ ∈ [0.05, 2.0] m (default: Nelder-Mead).")
    args = p.parse_args()

    train = train_paths()
    dev   = dev_paths()
    init  = initial_coeffs(args.platforms)
    bounds = default_bounds(args.platforms) if args.with_bounds else None

    print(f"M4 fit — {len(train)} train segments, {len(dev)} dev, "
          f"objective={args.objective}, platforms={args.platforms}")

    result = fit(
        predict_factory,
        initial_coeffs=init,
        train_segments=train,
        dev_segments=dev,
        objective=args.objective,
        bounds=bounds,
        max_iter=args.max_iter,
        verbose=True,
    )

    print(format_fit_summary(result))

    out_path = HERE / "coeffs.json"
    existing = {}
    if out_path.is_file():
        try:
            with out_path.open() as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            pass
    existing.update(result["coeffs"])  # merge — keeps untouched platforms
    with out_path.open("w") as f:
        json.dump(existing, f, indent=2)
    print(f"\nwrote {out_path.relative_to(TPL.parent)} ({list(result['coeffs'])} updated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
