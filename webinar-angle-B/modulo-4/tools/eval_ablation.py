"""Aggregate RMSE per platform per variant for the lateral-fidelity ablation.

Reads `sim.csv` (canonical baseline as shipped by `generate_simdata_ford.py`)
and any `sim_<variant>.csv` written by `regenerate_with_corrections.py`.
Prints a markdown-formatted table for direct paste into `REPORT.md`.
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1")
VARIANTS = ("baseline", "h1", "h3", "h1_h3")
SHORTNAME = {"FORD_MUSTANG_MACH_E_MK1": "Mach-E", "FORD_F_150_LIGHTNING_MK1": "F-150"}


def rmse(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def aggregate(platform: str, csv_name: str):
    files = sorted(glob.glob(str(ROOT / "data" / "sim" / "segments" / platform / "**" / csv_name), recursive=True))
    if not files:
        return None
    dfs = [pd.read_csv(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    return {
        "n": len(df),
        "rmse_yaw_degs": np.degrees(rmse(df["yaw_rate_resid_rads"].to_numpy())),
        "rmse_ay": rmse(df["a_y_resid_mps2"].to_numpy()),
        "bias_yaw_degs": float(np.degrees(df["yaw_rate_resid_rads"].mean())),
    }


def main():
    print("\n## Ablation — per-platform RMSE\n")
    print("| Platform | Variant | N | RMSE psi_dot (deg/s) | bias psi_dot (deg/s) | RMSE a_y (m/s^2) | delta_psi_dot abs | delta_psi_dot % |")
    print("|---|---|---|---|---|---|---|---|")
    rows = []
    base_rmse = {}
    for plat in PLATFORMS:
        # Use original sim.csv for baseline row (it IS the baseline shipped by generate_simdata_ford.py)
        base = aggregate(plat, "sim.csv")
        if base is None:
            continue
        base_rmse[plat] = base["rmse_yaw_degs"]
        rows.append((plat, "baseline", base, 0.0, 0.0))
        for v in VARIANTS:
            if v == "baseline":
                continue
            agg = aggregate(plat, f"sim_{v}.csv")
            if agg is None:
                continue
            delta = agg["rmse_yaw_degs"] - base["rmse_yaw_degs"]
            pct = 100.0 * delta / base["rmse_yaw_degs"] if base["rmse_yaw_degs"] > 0 else 0.0
            rows.append((plat, v, agg, delta, pct))

    for plat, v, agg, delta, pct in rows:
        print(
            f"| {SHORTNAME.get(plat, plat)} | {v} | {agg['n']} | "
            f"{agg['rmse_yaw_degs']:.4f} | {agg['bias_yaw_degs']:+.4f} | "
            f"{agg['rmse_ay']:.4f} | {delta:+.4f} | {pct:+.2f}% |"
        )
    print()


if __name__ == "__main__":
    main()
