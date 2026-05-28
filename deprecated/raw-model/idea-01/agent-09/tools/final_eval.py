"""Apply the fully-tuned model and compute final yaw-rate + a_y RMSE/MAE."""
from __future__ import annotations
import glob, os, json
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-09/data/sim/segments"
V_MIN = 2.0

# From shapley.py output
FITS = {
    "FORD_F_150_LIGHTNING_MK1": {"L": 3.70,  "lag": -3, "k_ratio": 0.8887073, "K_us": 0.0004625, "bias": 0.003976},
    "FORD_MUSTANG_MACH_E_MK1":  {"L": 2.984, "lag": -4, "k_ratio": 1.0868655, "K_us": 0.0003665, "bias": 0.000563},
}

def apply_lag(arr, k):
    if k == 0: return arr.copy()
    if k > 0:  return np.concatenate([arr[k:], np.full(k, arr[-1])])
    kk = -k;   return np.concatenate([np.full(kk, arr[0]), arr[:-kk]])

def evaluate():
    overall_base_sse = 0.0; overall_full_sse = 0.0; overall_n = 0
    overall_base_ay_sse = 0.0; overall_full_ay_sse = 0.0
    for plat, fit in FITS.items():
        L = fit["L"]
        sse_base = sse_full = 0.0
        sse_base_ay = sse_full_ay = 0.0
        nn = 0
        for csv in sorted(glob.glob(os.path.join(ROOT, plat, "*", "*", "*", "sim.csv"))):
            try:
                df = pd.read_csv(csv, usecols=[
                    "v_mps","delta_road_rad","yaw_rate_meas_rads","a_lat_meas_mps2"
                ])
            except Exception: continue
            mm = df["v_mps"].values > V_MIN
            if mm.sum() < 10: continue
            v = df["v_mps"].values[mm]
            d = df["delta_road_rad"].values[mm]
            y = df["yaw_rate_meas_rads"].values[mm]
            a_meas = df["a_lat_meas_mps2"].values[mm]
            # baseline KS
            pred_base = (v/L) * np.tan(d)
            # full
            d_lag = apply_lag(d, fit["lag"])
            pred_full = (v/L) * np.tan(fit["k_ratio"] * d_lag)
            pred_full = pred_full / (1.0 + fit["K_us"] * v*v)
            pred_full = pred_full - fit["bias"]
            sse_base += float(np.sum((pred_base - y)**2))
            sse_full += float(np.sum((pred_full - y)**2))
            # a_y = v * yaw_pred
            ay_base = v * pred_base
            ay_full = v * pred_full
            sse_base_ay += float(np.sum((ay_base - a_meas)**2))
            sse_full_ay += float(np.sum((ay_full - a_meas)**2))
            nn += len(v)
        rmse_b = float(np.sqrt(sse_base/nn))
        rmse_f = float(np.sqrt(sse_full/nn))
        rmse_b_ay = float(np.sqrt(sse_base_ay/nn))
        rmse_f_ay = float(np.sqrt(sse_full_ay/nn))
        print(f"{plat}: N={nn}")
        print(f"  yaw RMSE   baseline {rmse_b:.5f} → tuned {rmse_f:.5f}  (-{100*(1-rmse_f/rmse_b):.1f}%)")
        print(f"  a_y RMSE   baseline {rmse_b_ay:.4f} → tuned {rmse_f_ay:.4f}  (-{100*(1-rmse_f_ay/rmse_b_ay):.1f}%)")
        overall_base_sse += sse_base; overall_full_sse += sse_full
        overall_base_ay_sse += sse_base_ay; overall_full_ay_sse += sse_full_ay
        overall_n += nn
    print()
    rmse_b = float(np.sqrt(overall_base_sse/overall_n))
    rmse_f = float(np.sqrt(overall_full_sse/overall_n))
    rmse_b_ay = float(np.sqrt(overall_base_ay_sse/overall_n))
    rmse_f_ay = float(np.sqrt(overall_full_ay_sse/overall_n))
    print(f"POOLED N={overall_n}")
    print(f"  yaw RMSE: {rmse_b:.5f} → {rmse_f:.5f}  (-{100*(1-rmse_f/rmse_b):.1f}%)")
    print(f"  a_y RMSE: {rmse_b_ay:.4f} → {rmse_f_ay:.4f}  (-{100*(1-rmse_f_ay/rmse_b_ay):.1f}%)")

if __name__ == "__main__":
    evaluate()
