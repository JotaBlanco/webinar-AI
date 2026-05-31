"""Fit per-platform {L_eff, g, delta0, K_us, tau} for calibrated single-track + lag.

Model (the V0-as-documented in references/dynamics-formulations.md rung 0):

    delta_eff[i] = (delta_road_rad[i] - delta0) * g
    yr_ss[i]     = v[i] * delta_eff[i] / (L_eff + K_us * v[i]**2)
    yr[i+1]      = yr[i] + alpha[i] * (yr_ss[i] - yr[i])
    alpha[i]     = dt[i] / (tau + dt[i])
    yr[0]        = yr_ss[0]   # warm start

Loss: pooled yaw-rate MSE (v > 2 m/s).

For Mach-E only, per the anti-patterns note (per-segment bias is fine for
Mach-E, global for Lightning), we still fit global params here for simplicity.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09")
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]

# Defaults from code/parameters.py (carParams wheelbases)
L_DEFAULT = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "HYUNDAI_IONIQ_5":           3.00,  # rough; will be re-fit
    "TESLA_MODEL_3":             2.875,
}


def load_segments(platform: str, max_segs: int | None = None) -> list[dict]:
    seg_root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    if max_segs is not None:
        paths = paths[:max_segs]
    out = []
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy(dtype=float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            continue
        out.append({
            "path": str(p),
            "t": t,
            "v": df["v_mps"].to_numpy(dtype=float),
            "delta": df["delta_road_rad"].to_numpy(dtype=float),
            "yr_truth": df["yaw_rate_meas_rads"].to_numpy(dtype=float),
        })
    return out


def model_yaw_rate(t, v, delta, L_eff, g, delta0, K_us, tau):
    """First-order-lag steady-state understeer single-track."""
    delta_eff = (delta - delta0) * g
    yr_ss = v * delta_eff / (L_eff + K_us * v * v)
    dt = np.diff(t)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    if tau <= 0:
        # No lag — just steady-state
        yr[:] = yr_ss
        return yr
    for i in range(len(dt)):
        a = dt[i] / (tau + dt[i])
        yr[i + 1] = yr[i] + a * (yr_ss[i] - yr[i])
    return yr


def loss_for_platform(params, segs):
    L_eff, g, delta0, K_us, tau = params
    # Bound check
    if L_eff <= 0.5 or tau < 0 or K_us < -0.01 or K_us > 0.02:
        return 1e9
    sum_sq = 0.0
    n = 0
    for s in segs:
        yr = model_yaw_rate(s["t"], s["v"], s["delta"], L_eff, g, delta0, K_us, tau)
        mask = s["v"] > 2.0
        if not mask.any():
            continue
        r = yr[mask] - s["yr_truth"][mask]
        sum_sq += float(np.sum(r * r))
        n += int(mask.sum())
    if n == 0:
        return 1e9
    return sum_sq / n


def fit_platform(platform: str, max_segs: int | None = None):
    print(f"\n=== {platform} ===")
    segs = load_segments(platform, max_segs=max_segs)
    print(f"  loaded {len(segs)} segments")
    if not segs:
        return None

    L0 = L_DEFAULT.get(platform, 3.0)
    # Initial guess from references
    x0 = np.array([L0, 0.88, 0.0, 0.0025, 0.06])

    res = minimize(
        loss_for_platform,
        x0,
        args=(segs,),
        method="Nelder-Mead",
        options={"xatol": 1e-6, "fatol": 1e-10, "maxiter": 3000, "disp": False},
    )
    L_eff, g, delta0, K_us, tau = res.x
    rmse = float(np.sqrt(res.fun))
    print(f"  fitted: L_eff={L_eff:.4f}, g={g:.5f}, delta0={delta0:+.6f}, K_us={K_us:.5f}, tau={tau:.5f}")
    print(f"  yaw rmse (train pool): {rmse:.6f} rad/s")
    return {
        "L_eff": float(L_eff),
        "g": float(g),
        "delta0": float(delta0),
        "K_us": float(K_us),
        "tau": float(tau),
        "train_yaw_rmse": rmse,
        "n_segments": len(segs),
    }


if __name__ == "__main__":
    coeffs = {}
    for plat in PLATFORMS:
        # For Ioniq, we have 800 segments — sample down to keep fit fast
        max_segs = 80 if plat == "HYUNDAI_IONIQ_5" else None
        c = fit_platform(plat, max_segs=max_segs)
        if c is not None:
            coeffs[plat] = c

    # Tesla: leave at V0 identity (no truth channel).
    out_path = ROOT / "out" / "coeffs.json"
    with out_path.open("w") as f:
        json.dump(coeffs, f, indent=2)
    print(f"\nwrote {out_path}")
