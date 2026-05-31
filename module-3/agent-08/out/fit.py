"""Fit per-platform coefficients for the lateral-fidelity model.

Model (per platform):
    delta_eff = (delta_road_rad - delta0) * g
    yr_ss     = v * delta_eff / (L_eff + K_us * v^2)
    yr[i]     = yr[i-1] + alpha * (yr_ss[i] - yr[i-1])    with alpha = dt/(tau+dt)

Fit objective: pooled yaw-rate sum_sq (v-filtered) — yaw and CTE are
strongly coupled via signed bias, so minimising yaw with correct sign
also lowers CTE.

Tesla -> V0 passthrough (no truth).
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-08")
os.chdir(ROOT)

PLATFORMS_TO_FIT = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]

L_BY_PLATFORM = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "HYUNDAI_IONIQ_5":          2.90,  # reasonable estimate
    "TESLA_MODEL_3":            2.875,
}


def load_segments_for_platform(platform: str, max_segments: int | None = None):
    """Load (t, v, delta, yr_truth) per segment for fitting."""
    base = ROOT / "data/sim/segments" / platform
    paths = sorted(base.glob("**/sim.csv"))
    if max_segments:
        paths = paths[:max_segments]
    segs = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy(dtype=float)
        v = df["v_mps"].to_numpy(dtype=float)
        d = df["delta_road_rad"].to_numpy(dtype=float)
        yr_t = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        if len(t) < 10 or np.any(np.diff(t) <= 0):
            continue
        segs.append({"t": t, "v": v, "delta": d, "yr_truth": yr_t,
                     "path": str(p)})
    return segs


def _apply_lag_uniform(yr_ss, alpha):
    """Vectorised first-order lag for uniform alpha using scipy.signal.lfilter."""
    from scipy.signal import lfilter
    # y[i] = (1-alpha)*y[i-1] + alpha * x[i]
    # H(z) = alpha / (1 - (1-alpha) z^-1) on signal x.
    b = [alpha]
    a = [1.0, -(1.0 - alpha)]
    # zi for steady start so y[0]==x[0]
    y = lfilter(b, a, yr_ss, zi=[(1.0 - alpha) * yr_ss[0]])[0]
    return y


def model_predict(t, v, delta, g, delta0, K_us, tau, L_eff):
    delta_eff = (delta - delta0) * g
    yr_ss = v * delta_eff / (L_eff + K_us * v * v)
    if tau <= 0:
        return yr_ss
    # Assume nearly-uniform dt (~0.02s for 50Hz). Use mean dt for vectorised lag.
    dt_mean = float(np.mean(np.diff(t)))
    alpha = dt_mean / (tau + dt_mean)
    return _apply_lag_uniform(yr_ss, alpha)


def loss_for_platform(params, segs, L_nominal, v_filter=2.0):
    g, delta0, K_us, tau, L_eff = params
    if tau < 1e-4: tau = 1e-4
    if L_eff < 0.5 * L_nominal: L_eff = 0.5 * L_nominal
    if L_eff > 2.0 * L_nominal: L_eff = 2.0 * L_nominal
    if K_us < 0: K_us = 0.0
    total_sq = 0.0
    total_n = 0
    for s in segs:
        yr_pred = model_predict(s["t"], s["v"], s["delta"], g, delta0, K_us, tau, L_eff)
        mask = s["v"] > v_filter
        if not mask.any(): continue
        r = yr_pred[mask] - s["yr_truth"][mask]
        total_sq += float(np.sum(r * r))
        total_n += int(mask.sum())
    if total_n == 0:
        return 1e9
    return math.sqrt(total_sq / total_n)


def fit_platform(platform: str, max_segments: int | None = None):
    L_nom = L_BY_PLATFORM[platform]
    print(f"\n=== Fitting {platform} (L_nom={L_nom}) ===")
    segs = load_segments_for_platform(platform, max_segments=max_segments)
    print(f"  loaded {len(segs)} segments")
    if not segs:
        return None

    # Initial guess based on V0 (no understeer, g=1, delta0=0, tau=0.05)
    x0 = [1.0, 0.0, 0.002, 0.06, L_nom]
    bounds = [(0.5, 1.5), (-0.02, 0.02), (0.0, 0.02), (0.001, 0.3),
              (0.5 * L_nom, 2.0 * L_nom)]

    result = minimize(
        loss_for_platform, x0, args=(segs, L_nom),
        method="Nelder-Mead",
        options={"xatol": 1e-6, "fatol": 1e-7, "maxiter": 3000, "disp": True},
    )
    g, delta0, K_us, tau, L_eff = result.x
    print(f"  fitted: g={g:.4f} delta0={delta0:.6f} K_us={K_us:.5f} tau={tau:.4f} L_eff={L_eff:.3f}")
    print(f"  pooled yaw RMSE: {result.fun:.6f}")
    return {
        "g": float(g),
        "delta0": float(delta0),
        "K_us": float(K_us),
        "tau": float(tau),
        "L_eff": float(L_eff),
        "loss": float(result.fun),
        "n_segments_fit": len(segs),
    }


if __name__ == "__main__":
    # Cap segments per platform for speed; Hyundai 800 is too many for full fit
    max_seg = {"HYUNDAI_IONIQ_5": 200, "FORD_F_150_LIGHTNING_MK1": None,
               "FORD_MUSTANG_MACH_E_MK1": None}
    coeffs = {}
    for platform in PLATFORMS_TO_FIT:
        res = fit_platform(platform, max_segments=max_seg.get(platform))
        if res:
            coeffs[platform] = res
    out_path = ROOT / "out/coeffs.json"
    with open(out_path, "w") as f:
        json.dump(coeffs, f, indent=2)
    print(f"\nWrote {out_path}")
