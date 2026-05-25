"""Run the ablation table. See SKILL.md.

Usage:
    python skills/ablation-study/run.py <baseline-dir> <variant-1-dir> [<variant-2-dir> ...]

Each dir should mirror the data/sim/segments/<PLATFORM>/... layout and contain Ford CSVs.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def rmse(x):
    return float(np.sqrt(np.mean(np.square(x))))


def rmse_yaw_degs(d: Path):
    out = {}
    for plat_dir in sorted(d.iterdir()):
        if not plat_dir.is_dir() or not plat_dir.name.startswith("FORD_"):
            continue
        csvs = sorted(plat_dir.rglob("*.csv"))
        vals = []
        for c in csvs:
            df = pd.read_csv(c)
            if "yaw_rate_resid_rads" not in df.columns:
                continue
            vals.append(rmse(df["yaw_rate_resid_rads"].values * (180.0 / math.pi)))
        if vals:
            out[plat_dir.name] = float(np.mean(vals))
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    dirs = [Path(d) for d in sys.argv[1:]]
    names = [d.name.replace("sim_", "") for d in dirs]
    baseline = rmse_yaw_degs(dirs[0])
    rows = []
    for name, d in zip(names, dirs):
        rms = rmse_yaw_degs(d)
        for plat, v in rms.items():
            b = baseline.get(plat)
            d_abs = v - b if b is not None else float("nan")
            d_pct = 100.0 * d_abs / b if b else float("nan")
            rows.append({
                "variant": name,
                "platform": plat,
                "RMSE_yaw_degs": v,
                "Delta_vs_baseline_abs": d_abs,
                "Delta_vs_baseline_pct": d_pct,
            })
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
