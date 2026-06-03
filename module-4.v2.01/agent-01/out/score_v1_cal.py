"""Score V1 + gain/bias calibration on dev."""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary
from _shared.frozen_split import dev_paths
from v1_baseline import predict_v1

with (HERE / "v1_calibration.json").open() as f:
    CAL = json.load(f)


def predict_v1_cal(sim_df, platform):
    base = predict_v1(sim_df, platform)
    if platform not in CAL:
        return base
    g = CAL[platform]["gain"]
    b = CAL[platform]["bias"]
    yhat = base["yaw_rate_pred_rads"].to_numpy()
    return pd.DataFrame({"yaw_rate_pred_rads": g * yhat + b}, index=sim_df.index)


def predict_v1_biasonly(sim_df, platform):
    base = predict_v1(sim_df, platform)
    if platform not in CAL:
        return base
    b = CAL[platform]["bias_only"]
    yhat = base["yaw_rate_pred_rads"].to_numpy()
    return pd.DataFrame({"yaw_rate_pred_rads": yhat + b}, index=sim_df.index)


if __name__ == "__main__":
    dev = dev_paths()
    for name, fn in [("V1+gain+bias", predict_v1_cal), ("V1+bias_only", predict_v1_biasonly)]:
        r = score(fn, segment_paths=dev)
        print(f"\n=== {name} ===")
        print(f"yaw_rate_rmse = {r['yaw_rate_rmse']:.6f}")
        print(f"cte_rmse       = {r['cte_rmse']:.4f}")
        for plat, st in r["per_platform"].items():
            print(f"  {plat:30s}  yaw={st['yaw_rate_rmse']:.5f}  cte={st['cte_rmse']:8.3f}  bias={st['yaw_residual_mean']:+.5f}")
