"""Score V1 + per-platform linear residual head against the dev pool."""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-04")
sys.path.insert(0, str(ROOT / "out"))
sys.path.insert(0, str(ROOT / "code"))
from quick_score import score
from v1_baseline import predict_v1
from fit_residual import build_features

COEFFS = json.loads((ROOT / "out" / "residual_coeffs.json").read_text())


def predict_v1_plus_resid(sim_df, platform):
    yr_v1 = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy()
    if platform in COEFFS:
        beta = np.array(COEFFS[platform]["beta"])
        X = build_features(sim_df, yr_v1)
        yr = yr_v1 + X @ beta
    else:
        yr = yr_v1
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)


if __name__ == "__main__":
    r = score(predict_v1_plus_resid)
    print("V1 + residual head pooled:")
    print(f"  yaw_rate_rmse = {r['yaw_rate_rmse']:.6f}")
    print(f"  cte_rmse      = {r['cte_rmse']:.4f}")
    for plat, pp in r["per_platform"].items():
        print(f"  {plat}: yaw={pp['yaw_rmse']:.6f} bias={pp['yaw_bias']:+.6f} cte={pp['cte_rmse']:.3f}")
