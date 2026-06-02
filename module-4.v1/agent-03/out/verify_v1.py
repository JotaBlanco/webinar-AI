"""Pooled V1 vs final on the same in-sample set used by verify_final.py."""
from __future__ import annotations
import math, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-03")
sys.path.insert(0, str(ROOT / "_shared")); sys.path.insert(0, str(ROOT / "code"))
from traj_metrics import cte_rmse_segment  # type: ignore
from v1_baseline import predict_v1  # type: ignore

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
INPUT_COLS = ["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
              "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]

def main():
    total_yaw_sq = total_yaw_n = 0; total_cte_sq = total_cte_n = 0
    for plat in PLATFORMS:
        base_truth = ROOT / "data" / "sim" / "segments" / plat
        base_only = ROOT / "data" / "sim-only" / "segments" / plat
        p_sq = p_n = 0; p_csq = p_cn = 0; n = 0
        for tp in sorted(base_truth.rglob("sim.csv")):
            op = base_only / tp.relative_to(base_truth)
            if not op.exists(): continue
            df_truth = pd.read_csv(tp)
            df_only = pd.read_csv(op)
            if "yaw_rate_meas_rads" not in df_truth.columns: continue
            for c in INPUT_COLS:
                if c not in df_only.columns: df_only[c] = 0.0
            sim_df = df_only[INPUT_COLS].copy()
            yr_v1 = predict_v1(sim_df, plat)["yaw_rate_pred_rads"].to_numpy()
            yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
            yr_truth = df_truth["yaw_rate_meas_rads"].to_numpy()
            p_sq += float(np.sum((yr_v1 - yr_truth)**2)); p_n += len(yr_v1)
            sq, nb, _ = cte_rmse_segment(df_truth["t_s"].to_numpy(),
                                          df_truth["v_mps"].to_numpy(),
                                          yr_truth, yr_v1)
            p_csq += sq; p_cn += nb; n += 1
        if p_n:
            print(f"V1 {plat}: yaw={math.sqrt(p_sq/p_n):.6f}  cte={math.sqrt(p_csq/p_cn):.2f}  segs={n}")
            total_yaw_sq += p_sq; total_yaw_n += p_n
            total_cte_sq += p_csq; total_cte_n += p_cn
    print(f"V1 POOLED yaw={math.sqrt(total_yaw_sq/total_yaw_n):.6f}  cte={math.sqrt(total_cte_sq/total_cte_n):.2f}")

if __name__ == "__main__":
    main()
