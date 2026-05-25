"""Compute baseline lateral residual per Ford platform. See SKILL.md."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT = Path(__file__).resolve().parents[2] / "data" / "sim" / "segments"


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
        rmses_yaw_deg, rmses_ay, corrs = [], [], []
        for c in csvs:
            df = pd.read_csv(c)
            if "yaw_rate_resid_rads" not in df.columns:
                continue
            rmses_yaw_deg.append(rmse(df["yaw_rate_resid_rads"].values * (180.0 / math.pi)))
            if "a_y_resid_mps2" in df.columns:
                rmses_ay.append(rmse(df["a_y_resid_mps2"].values))
            if df["yaw_rate_pred_rads"].std() > 0 and df["yaw_rate_meas_rads"].std() > 0:
                corrs.append(np.corrcoef(df["yaw_rate_pred_rads"], df["yaw_rate_meas_rads"])[0, 1])
        if not rmses_yaw_deg:
            continue
        rows.append({
            "platform": plat_dir.name,
            "n_segments": len(rmses_yaw_deg),
            "RMSE_yaw_degs_mean": float(np.mean(rmses_yaw_deg)),
            "RMSE_a_y_mps2_mean": float(np.mean(rmses_ay)) if rmses_ay else float("nan"),
            "corr_yaw_mean": float(np.mean(corrs)) if corrs else float("nan"),
        })
    if not rows:
        print("no Ford CSVs found", file=sys.stderr)
        sys.exit(1)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
