"""Score the final-model predict() on data/sim/segments (truth available) to
mimic the canonical grader's pooled scoring."""
from __future__ import annotations
import sys, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-01")
sys.path.insert(0, str(ROOT / "final-model"))
sys.path.insert(0, str(ROOT / "_shared"))
from predict import predict  # type: ignore
from traj_metrics import cte_rmse_segment  # type: ignore

SIM = ROOT / "data" / "sim" / "segments"
ALLOWLIST = ["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
             "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]

def main():
    pooled_yaw_sse = {}; pooled_yaw_n = {}
    pooled_cte_sse = {}; pooled_cte_n = {}
    pooled_v0_yaw_sse = {}; pooled_v0_cte_sse = {}
    for plat in sorted(p.name for p in SIM.iterdir() if p.is_dir()):
        pooled_yaw_sse[plat] = 0.0; pooled_yaw_n[plat] = 0
        pooled_cte_sse[plat] = 0.0; pooled_cte_n[plat] = 0
        pooled_v0_yaw_sse[plat] = 0.0; pooled_v0_cte_sse[plat] = 0.0
        n_seg = 0
        for p in (SIM/plat).rglob("sim.csv"):
            df_full = pd.read_csv(p)
            if "yaw_rate_meas_rads" not in df_full.columns:
                continue
            truth = df_full["yaw_rate_meas_rads"].to_numpy()
            t = df_full["t_s"].to_numpy()
            v = df_full["v_mps"].to_numpy()
            v0 = df_full["yaw_rate_pred_rads"].to_numpy()
            # simulate grader input
            avail = [c for c in ALLOWLIST if c in df_full.columns]
            for c in ALLOWLIST:
                if c not in df_full.columns:
                    df_full[c] = 0.0
            sim_df = df_full[ALLOWLIST].copy()
            out = predict(sim_df, plat)
            yp = out["yaw_rate_pred_rads"].to_numpy()
            d = yp - truth; pooled_yaw_sse[plat] += float(np.sum(d*d)); pooled_yaw_n[plat] += len(d)
            s, nb, _ = cte_rmse_segment(t,v,truth,yp)
            pooled_cte_sse[plat] += s; pooled_cte_n[plat] += nb
            d0 = v0 - truth; pooled_v0_yaw_sse[plat] += float(np.sum(d0*d0))
            s0,_,_ = cte_rmse_segment(t,v,truth,v0); pooled_v0_cte_sse[plat] += s0
            n_seg += 1
        if pooled_yaw_n[plat] == 0:
            print(f"{plat}: no truth (skipped)")
            continue
        ny = math.sqrt(pooled_yaw_sse[plat]/pooled_yaw_n[plat])
        nc = math.sqrt(pooled_cte_sse[plat]/pooled_cte_n[plat]) if pooled_cte_n[plat] else float("nan")
        v0y = math.sqrt(pooled_v0_yaw_sse[plat]/pooled_yaw_n[plat])
        v0c = math.sqrt(pooled_v0_cte_sse[plat]/pooled_cte_n[plat]) if pooled_cte_n[plat] else float("nan")
        print(f"{plat}: yaw {ny:.6f} (v0 {v0y:.6f}, {(v0y-ny)/v0y*100:+.1f}%)  CTE {nc:.3f} (v0 {v0c:.3f}, {(v0c-nc)/v0c*100:+.1f}%)  n_seg={n_seg}")

    # Pool platforms with truth (excludes Tesla)
    yaw_n = sum(pooled_yaw_n[p] for p in pooled_yaw_n if pooled_yaw_n[p] > 0 and p != "TESLA_MODEL_3")
    yaw_sse = sum(pooled_yaw_sse[p] for p in pooled_yaw_sse if pooled_yaw_n[p] > 0 and p != "TESLA_MODEL_3")
    cte_n = sum(pooled_cte_n[p] for p in pooled_cte_n if p != "TESLA_MODEL_3")
    cte_sse = sum(pooled_cte_sse[p] for p in pooled_cte_sse if p != "TESLA_MODEL_3")
    v0_yaw_sse = sum(pooled_v0_yaw_sse[p] for p in pooled_v0_yaw_sse if pooled_yaw_n[p] > 0 and p != "TESLA_MODEL_3")
    v0_cte_sse = sum(pooled_v0_cte_sse[p] for p in pooled_v0_cte_sse if p != "TESLA_MODEL_3")
    print()
    print(f"POOLED (excl Tesla) yaw RMSE: {math.sqrt(yaw_sse/yaw_n):.6f} (v0 {math.sqrt(v0_yaw_sse/yaw_n):.6f})")
    print(f"POOLED (excl Tesla) CTE RMSE: {math.sqrt(cte_sse/cte_n):.3f} (v0 {math.sqrt(v0_cte_sse/cte_n):.3f})")

if __name__ == "__main__":
    main()
