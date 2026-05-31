"""Fit per-platform understeer + steering bias from sim/ truth.

Model V1: yr = v * (delta + b) / (L_eff + K * v^2)

Linearise (in unknowns L_eff, K, b):
    yr * (L_eff + K v^2) = v * delta + v * b
    yr*L_eff + yr*K*v^2 - v*b = v*delta

Form linear LS for [L_eff, K, b]:
    [yr, yr*v^2, -v] @ [L_eff, K, b].T = v*delta

(Note: b is the steering bias in rad.)
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07")
WHEELBASE_M = {
    "TESLA_MODEL_3": 2.875, "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70, "HYUNDAI_IONIQ_5": 3.00,
}


def collect(platform: str) -> pd.DataFrame:
    segs = sorted((ROOT / "data" / "sim" / "segments" / platform).rglob("sim.csv"))
    chunks = []
    for p in segs:
        try:
            df = pd.read_csv(p, usecols=lambda c: c in {"t_s","v_mps","delta_road_rad","yaw_rate_meas_rads","a_long_mps2","delta_wheel_deg"})
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        df = df.dropna(subset=["v_mps","delta_road_rad","yaw_rate_meas_rads"])
        # Filter rows: v>3, exclude obvious outliers
        df = df[df["v_mps"] > 3].copy()
        if len(df):
            chunks.append(df)
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()


def fit_platform(platform: str) -> dict:
    df = collect(platform)
    if len(df) < 100:
        return {"platform": platform, "fit": None, "n": len(df)}
    v = df["v_mps"].to_numpy(float)
    d = df["delta_road_rad"].to_numpy(float)
    y = df["yaw_rate_meas_rads"].to_numpy(float)
    L0 = WHEELBASE_M[platform]
    # Linear LS:  A @ [L_eff, K, b] = c
    # yr*L_eff + yr*v^2 * K - v * b = v*delta
    A = np.column_stack([y, y * v**2, -v])
    c = v * d
    # Robust: weighted to downweight noise — use larger |yr| for SNR
    w = np.minimum(np.abs(y), 0.3)  # cap weight contribution
    # But pure unweighted works fine here; add a tiny ridge for stability
    sol, *_ = np.linalg.lstsq(A, c, rcond=None)
    L_eff, K, b = sol
    # Evaluate RMSE on the same data
    y_pred = v * (d + b) / (L_eff + K * v**2)
    rmse_v1 = float(np.sqrt(np.mean((y_pred - y)**2)))
    y_v0 = v * d / L0
    rmse_v0 = float(np.sqrt(np.mean((y_v0 - y)**2)))
    print(f"{platform}: n={len(df)}  L0={L0:.3f}  L_eff={L_eff:.3f}  K={K:.6f}  b={b:.5f}  rmse_v0={rmse_v0:.5f}  rmse_v1={rmse_v1:.5f}")
    return {
        "platform": platform,
        "L_eff": float(L_eff),
        "K_u": float(K),
        "delta_bias_rad": float(b),
        "n": int(len(df)),
        "rmse_train_v0": rmse_v0,
        "rmse_train_v1": rmse_v1,
    }


if __name__ == "__main__":
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1","FORD_MUSTANG_MACH_E_MK1","HYUNDAI_IONIQ_5","TESLA_MODEL_3"]:
        out[plat] = fit_platform(plat)
    (ROOT / "out" / "coeffs_v1.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
