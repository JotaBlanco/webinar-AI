"""Computational sensor — baseline RMSE numbers per platform.

Reproducible spot-check. If your REPORT.md's baseline numbers don't match what
this script prints (within rounding), one of you is wrong — investigate before
proposing improvements.

Usage:
    python evals/baseline_rmse.py [<sim-dir>]
    # default sim-dir is data/sim/segments/
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT = Path(__file__).resolve().parents[1] / "data" / "sim" / "segments"


def rmse(x):
    return float(np.sqrt(np.mean(np.square(x))))


def main():
    sim_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not sim_dir.exists():
        print(f"no such dir: {sim_dir}", file=sys.stderr)
        sys.exit(2)
    rows = []
    for plat_dir in sorted(sim_dir.iterdir()):
        if not plat_dir.is_dir() or not plat_dir.name.startswith("FORD_"):
            continue
        csvs = sorted(plat_dir.rglob("*.csv"))
        if not csvs:
            continue
        rmses_yaw_deg = []
        rmses_ay = []
        corrs_yaw = []
        for c in csvs:
            df = pd.read_csv(c)
            if "yaw_rate_resid_rads" not in df.columns:
                continue
            yaw_resid_degs = df["yaw_rate_resid_rads"].values * (180.0 / math.pi)
            rmses_yaw_deg.append(rmse(yaw_resid_degs))
            if "a_y_resid_mps2" in df.columns:
                rmses_ay.append(rmse(df["a_y_resid_mps2"].values))
            if df["yaw_rate_pred_rads"].std() > 0 and df["yaw_rate_meas_rads"].std() > 0:
                corrs_yaw.append(np.corrcoef(df["yaw_rate_pred_rads"], df["yaw_rate_meas_rads"])[0, 1])
        if not rmses_yaw_deg:
            continue
        rows.append({
            "platform": plat_dir.name,
            "n_segments": len(rmses_yaw_deg),
            "RMSE_yaw_degs_mean": float(np.mean(rmses_yaw_deg)),
            "RMSE_a_y_mps2_mean": float(np.mean(rmses_ay)) if rmses_ay else float("nan"),
            "corr_yaw_mean": float(np.mean(corrs_yaw)) if corrs_yaw else float("nan"),
        })
    if not rows:
        print("no Ford CSVs with the expected schema found", file=sys.stderr)
        sys.exit(1)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
