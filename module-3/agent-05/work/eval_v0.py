"""Baseline V0 score across all Ford segments."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
sys.path.insert(0, str(ROOT / "_shared"))

import os
os.chdir(ROOT)

from score import score
from split import split
import pandas as pd
import numpy as np


def v0_predict(sim_df, platform):
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].values},
        index=sim_df.index,
    )


def main():
    result = score(v0_predict)
    print("V0 baseline (all FORD segments):")
    print(f"  yaw_rate_rmse: {result['yaw_rate_rmse']:.6f}")
    print(f"  cte_rmse:      {result['cte_rmse']:.3f}")
    print(f"  n_segments:    {result['n_segments']}")
    print("  per_platform:")
    for pl, v in result["per_platform"].items():
        print(f"    {pl}: yr={v['yaw_rate_rmse']:.6f} cte={v['cte_rmse']:.3f} n={v['n_segments']}")
    print("  per_regime:")
    for r, v in result["per_regime"].items():
        print(f"    {r}: yr={v['yaw_rate_rmse']:.6f} n={v['n_samples']}")

    # Also make a train/dev split for fitting
    train, dev = split(dev_fraction=0.25, seed=42)
    print(f"\nTrain segs: {len(train)}, Dev segs: {len(dev)}")
    # Per platform
    from collections import Counter
    def plat(p):
        return Path(p).parts[-5]
    print("Train per platform:", Counter(plat(p) for p in train))
    print("Dev   per platform:", Counter(plat(p) for p in dev))


if __name__ == "__main__":
    main()
