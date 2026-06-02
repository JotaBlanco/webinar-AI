"""Fit a per-platform scalar gain g and constant offset c such that
   yr_pred = g * yr_v1 + c   minimizes train pooled MSE; validate on dev.
   Splits: by segment hash mod 5 == 0 -> dev else train.
"""
from __future__ import annotations
import sys, math, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-08")
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1

SIM_ONLY = ROOT / "data" / "sim-only" / "segments"
SIM_TRUTH = ROOT / "data" / "sim" / "segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def seg_hash(path: Path) -> int:
    return int(hashlib.sha1(str(path).encode()).hexdigest()[:8], 16)


def load_segment(sim_only_csv):
    rel = sim_only_csv.relative_to(SIM_ONLY)
    truth_csv = SIM_TRUTH / rel
    if not truth_csv.exists():
        return None
    sim_df = pd.read_csv(sim_only_csv)
    truth_df = pd.read_csv(truth_csv, usecols=["yaw_rate_meas_rads"])
    if len(sim_df) != len(truth_df):
        return None
    return sim_df, truth_df["yaw_rate_meas_rads"].to_numpy(float)


out = {}
for plat in PLATFORMS:
    yr_v1_tr, yr_t_tr = [], []
    yr_v1_dv, yr_t_dv = [], []
    for sim_csv in (SIM_ONLY / plat).rglob("sim.csv"):
        loaded = load_segment(sim_csv)
        if loaded is None: continue
        sim_df, yr_truth = loaded
        try:
            yr_v1 = predict_v1(sim_df, plat)["yaw_rate_pred_rads"].to_numpy(float)
        except Exception:
            continue
        m = np.isfinite(yr_v1) & np.isfinite(yr_truth)
        is_dev = (seg_hash(sim_csv) % 5) == 0
        if is_dev:
            yr_v1_dv.append(yr_v1[m]); yr_t_dv.append(yr_truth[m])
        else:
            yr_v1_tr.append(yr_v1[m]); yr_t_tr.append(yr_truth[m])
    x_tr = np.concatenate(yr_v1_tr); y_tr = np.concatenate(yr_t_tr)
    x_dv = np.concatenate(yr_v1_dv); y_dv = np.concatenate(yr_t_dv)
    # Fit y = g*x + c
    A = np.column_stack([x_tr, np.ones_like(x_tr)])
    sol, *_ = np.linalg.lstsq(A, y_tr, rcond=None)
    g, c = float(sol[0]), float(sol[1])
    # Baseline (g=1, c=0) RMSEs vs fitted
    def rmse(p, y): return math.sqrt(((p - y) ** 2).mean())
    tr_b = rmse(x_tr, y_tr); tr_a = rmse(g*x_tr + c, y_tr)
    dv_b = rmse(x_dv, y_dv); dv_a = rmse(g*x_dv + c, y_dv)
    print(f"{plat}: g={g:.5f} c={c:+.6f}")
    print(f"  train yaw RMSE: {tr_b:.6f} -> {tr_a:.6f}")
    print(f"  dev   yaw RMSE: {dv_b:.6f} -> {dv_a:.6f}")
    out[plat] = {"gain": g, "offset": c}
# Tesla untouched
out["TESLA_MODEL_3"] = {"gain": 1.0, "offset": 0.0}
with open(ROOT / "out" / "gain_bias.json", "w") as f:
    json.dump(out, f, indent=2)
print("\nSaved ->", ROOT / "out" / "gain_bias.json")
