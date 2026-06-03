"""Test V1 variants:
 - V1A: F150 uses per-segment delta0 (currently fixed at 0.00133).
 - V1B: also tune yaw_bias subtraction per-platform from train statistics.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary
from _shared.frozen_split import dev_paths, train_paths
from v1_baseline import PLATFORM_PARAMS_V1, _per_segment_delta0


def predict_v1a(sim_df, platform):
    """V1 but F150 also uses per-segment delta0."""
    if platform not in PLATFORM_PARAMS_V1:
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                            index=sim_df.index)
    p = dict(PLATFORM_PARAMS_V1[platform])
    if platform == "FORD_F_150_LIGHTNING_MK1":
        # Use per-segment with fallback to current fixed delta0
        p["use_per_segment_delta0"] = True
        p["delta0_fallback"] = 0.00133

    delta0 = (_per_segment_delta0(sim_df, fallback=p.get("delta0_fallback", 0.0))
              if p["use_per_segment_delta0"]
              else p["delta0"])
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)


if __name__ == "__main__":
    dev = dev_paths()
    print(f"V1A on {len(dev)} dev segments")
    r = score(predict_v1a, segment_paths=dev)
    print(f"yaw_rate_rmse = {r['yaw_rate_rmse']:.6f}")
    print(f"cte_rmse       = {r['cte_rmse']:.4f}")
    print("per platform:")
    for plat, st in r["per_platform"].items():
        print(f"  {plat:30s}  yaw={st['yaw_rate_rmse']:.5f}  cte={st['cte_rmse']:8.3f}  yaw_bias={st['yaw_residual_mean']:+.5f}")
