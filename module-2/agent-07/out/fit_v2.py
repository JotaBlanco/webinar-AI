"""V2 — V1 + first-order lag on the steering channel.

Model:
    delta_filt[k] = (1-a) * delta_filt[k-1] + a * delta_meas[k]      (a = dt/(tau+dt))
    yr_pred = v * (delta_filt + b) / (L_eff + K * v^2)

We fix L_eff, K, b from V1 and grid-search tau per platform.
Also try a richer fit: refit (L_eff,K,b) WITH lag for each tau.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07")


def collect_segments(platform: str):
    segs = sorted((ROOT / "data" / "sim" / "segments" / platform).rglob("sim.csv"))
    out = []
    for p in segs:
        try:
            df = pd.read_csv(p, usecols=lambda c: c in {"t_s","v_mps","delta_road_rad","yaw_rate_meas_rads"})
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns or len(df) < 50:
            continue
        out.append(df)
    return out


def lag_filter(delta: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 1e-6:
        return delta.copy()
    dt = np.diff(t, prepend=t[0])
    out = np.empty_like(delta)
    out[0] = delta[0]
    for i in range(1, len(delta)):
        a = dt[i] / (tau + dt[i])
        out[i] = (1 - a) * out[i-1] + a * delta[i]
    return out


def fit_per_platform(platform: str, taus=(0.0, 0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30, 0.40)):
    segs = collect_segments(platform)
    print(f"{platform}: {len(segs)} segments")
    best = None
    # Concatenate per-tau arrays
    # We need to lag PER SEGMENT (state resets), then concat for LS.
    for tau in taus:
        Y_list, V_list, D_list = [], [], []
        for df in segs:
            t = df["t_s"].to_numpy(float)
            v = df["v_mps"].to_numpy(float)
            d = df["delta_road_rad"].to_numpy(float)
            y = df["yaw_rate_meas_rads"].to_numpy(float)
            mask = (v > 3)
            if mask.sum() < 5:
                continue
            d_lag = lag_filter(d, t, tau)
            Y_list.append(y[mask])
            V_list.append(v[mask])
            D_list.append(d_lag[mask])
        if not Y_list:
            continue
        y = np.concatenate(Y_list)
        v = np.concatenate(V_list)
        d = np.concatenate(D_list)
        A = np.column_stack([y, y * v**2, -v])
        c = v * d
        sol, *_ = np.linalg.lstsq(A, c, rcond=None)
        L_eff, K, b = sol
        y_pred = v * (d + b) / (L_eff + K * v**2)
        rmse = float(np.sqrt(np.mean((y_pred - y)**2)))
        print(f"  tau={tau:.3f}: L_eff={L_eff:.3f} K={K:.5f} b={b:.5f}  rmse={rmse:.5f}")
        if best is None or rmse < best["rmse"]:
            best = {"tau": tau, "L_eff": float(L_eff), "K_u": float(K), "delta_bias_rad": float(b), "rmse": rmse}
    return best


if __name__ == "__main__":
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1","FORD_MUSTANG_MACH_E_MK1","HYUNDAI_IONIQ_5"]:
        out[plat] = fit_per_platform(plat)
    (ROOT / "out" / "coeffs_v2.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
