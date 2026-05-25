"""Per-platform constant-bias correction on yaw-rate residual. See SKILL.md.

Usage:
    python skills/yaw-bias-correction/apply.py <input-sim-dir> <output-dir>

Walks <input-sim-dir>/FORD_*/.../*.csv, computes per-platform bias from concatenated
yaw_rate_resid_rads, writes corrected CSVs to the matching path under <output-dir>.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def rmse(x):
    return float(np.sqrt(np.mean(np.square(x))))


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    in_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    for plat_dir in sorted(in_dir.iterdir()):
        if not plat_dir.is_dir() or not plat_dir.name.startswith("FORD_"):
            continue
        csvs = sorted(plat_dir.rglob("*.csv"))
        if not csvs:
            continue
        # Pass 1 — bias from concatenated residual.
        all_resid = []
        for c in csvs:
            df = pd.read_csv(c)
            if "yaw_rate_resid_rads" in df.columns:
                all_resid.append(df["yaw_rate_resid_rads"].values)
        if not all_resid:
            continue
        bias = float(np.mean(np.concatenate(all_resid)))
        rmse_before = rmse(np.concatenate(all_resid) * (180.0 / math.pi))
        new_resid_all = []
        # Pass 2 — apply + write.
        for c in csvs:
            df = pd.read_csv(c)
            df["yaw_rate_pred_rads"] = df["yaw_rate_pred_rads"] + bias
            df["yaw_rate_resid_rads"] = df["yaw_rate_meas_rads"] - df["yaw_rate_pred_rads"]
            new_resid_all.append(df["yaw_rate_resid_rads"].values)
            rel = c.relative_to(in_dir)
            target = out_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(target, index=False)
        rmse_after = rmse(np.concatenate(new_resid_all) * (180.0 / math.pi))
        print(f"{plat_dir.name}: bias={bias:+.5f} rad/s, RMSE ψ̇ {rmse_before:.3f} → {rmse_after:.3f} °/s")


if __name__ == "__main__":
    main()
