"""End-to-end verify of final-model/predict.py against sim-only schema.

Also re-scores the model against sim/ truth for confirmation.
"""
from __future__ import annotations
import sys, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-09")
sys.path.insert(0, str(ROOT / "final-model"))
sys.path.insert(0, str(ROOT / "_shared"))
from predict import predict  # noqa
from traj_metrics import cte_rmse_segment  # noqa

SIM_ROOT = ROOT / "data" / "sim" / "segments"
SIM_ONLY_ROOT = ROOT / "data" / "sim-only" / "segments"


def load_sim_only(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path)


def load_sim(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "yaw_rate_meas_rads" not in df.columns and "psi_dot_rads" in df.columns:
        df["yaw_rate_meas_rads"] = df["psi_dot_rads"]
    return df


# 1) sanity: predict on a couple of sim-only files (contract-only)
for plat in ["TESLA_MODEL_3", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5", "FORD_MUSTANG_MACH_E_MK1"]:
    files = sorted((SIM_ONLY_ROOT / plat).rglob("sim.csv"))[:1]
    for p in files:
        df = load_sim_only(p)
        out = predict(df, plat)
        assert set(["yaw_rate_pred_rads", "x_m", "y_m"]).issubset(out.columns), out.columns
        assert (out.index == df.index).all()
        assert len(out) == len(df)
        assert np.isfinite(out["yaw_rate_pred_rads"]).all()
        print(f"OK contract: {plat} n={len(df)} cols={list(df.columns)}")
        break

# 2) re-score against full sim/ truth set
print("\n=== Full re-score ===")
for plat in ["TESLA_MODEL_3", "FORD_MUSTANG_MACH_E_MK1",
             "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5"]:
    yaw_sq = 0.0; yaw_n = 0
    cte_sq = 0.0; cte_n = 0
    n_seg = 0
    for p in sorted((SIM_ROOT / plat).rglob("sim.csv")):
        df = load_sim(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        # Build sim-only-like view to mimic the grader.
        v0_predict = None
        if "yaw_rate_pred_rads" not in df.columns:
            v0_predict = df["v_mps"].to_numpy() * df["delta_road_rad"].to_numpy() / 2.875
        cols = ["t_s", "delta_wheel_deg", "delta_road_rad", "v_mps", "a_long_mps2"]
        cols = [c for c in cols if c in df.columns]
        sim_only_df = df[cols].copy()
        if v0_predict is not None:
            sim_only_df["yaw_rate_pred_rads"] = v0_predict
        else:
            sim_only_df["yaw_rate_pred_rads"] = df["yaw_rate_pred_rads"]
        try:
            pred = predict(sim_only_df, plat)
        except Exception as e:
            print(f"  fail {p.name}: {e}")
            continue
        yp = pred["yaw_rate_pred_rads"].to_numpy()
        yt = df["yaw_rate_meas_rads"].to_numpy()
        v = df["v_mps"].to_numpy()
        t = df["t_s"].to_numpy()
        m = np.isfinite(yp) & np.isfinite(yt) & np.isfinite(v)
        if m.sum() < 10: continue
        e = yt[m] - yp[m]
        yaw_sq += float(np.sum(e * e)); yaw_n += int(m.sum())
        ss, nb, _ = cte_rmse_segment(t, v, yt, yp, grid_step_m=1.0, min_distance_m=20.0)
        cte_sq += ss; cte_n += nb
        n_seg += 1
    print(f"{plat}: n_seg={n_seg}  yaw_rmse={math.sqrt(yaw_sq/yaw_n):.5f}  "
          f"cte_rmse={math.sqrt(cte_sq/cte_n) if cte_n else float('nan'):.3f} m")
