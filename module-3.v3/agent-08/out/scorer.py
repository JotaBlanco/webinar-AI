"""Lightweight pooled scorer for any predict(sim_df, platform) callable.

Uses data/sim/segments/ (full, with truth) for local scoring against truth.
"""
from __future__ import annotations
import sys, glob, math, importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v3/agent-08")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_rmse_segment  # type: ignore

SIM = ROOT / "data" / "sim" / "segments"
ALLOWLIST = ["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
             "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]

def iter_segments(platform: str):
    for path in sorted((SIM / platform).rglob("sim.csv")):
        yield path

def score_predict(predict_fn, platforms=("FORD_F_150_LIGHTNING_MK1",
                                           "FORD_MUSTANG_MACH_E_MK1",
                                           "HYUNDAI_IONIQ_5")):
    per_plat = {}
    pooled_sumsq_yaw, pooled_n_yaw = 0.0, 0
    pooled_sumsq_cte, pooled_n_cte = 0.0, 0
    for plat in platforms:
        sumsq_yaw = 0.0; n_yaw = 0
        sumsq_cte = 0.0; n_cte = 0
        for p in iter_segments(plat):
            df = pd.read_csv(p)
            truth = df["yaw_rate_meas_rads"].to_numpy()
            sim_df = pd.DataFrame(index=df.index)
            for c in ALLOWLIST:
                sim_df[c] = df[c].to_numpy() if c in df.columns else 0.0
            out = predict_fn(sim_df, plat)
            pred = out["yaw_rate_pred_rads"].to_numpy()
            v_all = df["v_mps"].to_numpy()
            mask_v = v_all > 2.0
            resid = (pred - truth)[mask_v]
            sumsq_yaw += float(np.sum(resid * resid))
            n_yaw += int(mask_v.sum())
            t = df["t_s"].to_numpy()
            v = df["v_mps"].to_numpy()
            s, nb, _ = cte_rmse_segment(t, v, truth, pred)
            sumsq_cte += s; n_cte += nb
        yaw_rmse = math.sqrt(sumsq_yaw / max(n_yaw,1))
        cte_rmse = math.sqrt(sumsq_cte / max(n_cte,1))
        per_plat[plat] = {"yaw_rmse": yaw_rmse, "cte_rmse": cte_rmse,
                          "n_yaw": n_yaw, "n_cte": n_cte}
        pooled_sumsq_yaw += sumsq_yaw; pooled_n_yaw += n_yaw
        pooled_sumsq_cte += sumsq_cte; pooled_n_cte += n_cte
    pooled = {"yaw_rmse": math.sqrt(pooled_sumsq_yaw / max(pooled_n_yaw,1)),
              "cte_rmse": math.sqrt(pooled_sumsq_cte / max(pooled_n_cte,1))}
    return {"per_platform": per_plat, "pooled": pooled}

if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "code"))
    from v1_baseline import predict_v1
    res = score_predict(predict_v1)
    import json
    print(json.dumps(res, indent=2))
