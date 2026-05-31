"""Per-platform coefficient fitter for the KS + understeer + tau + δ₀ model.

Objective: yaw RMSE (sample-pooled) on training segments.

Uses the same predict shape as predict_v1.py but with platform-specific
fit on (g, L_eff, K_us, tau, delta0_global). For Mach-E we still apply
per-segment δ₀ from input channels at inference (predict_v1 logic).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-10")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_rmse_segment  # noqa: E402


def find_segments(plat: str):
    sim_root = ROOT / "data" / "sim" / "segments" / plat
    for p in sorted(sim_root.rglob("sim.csv")):
        yield p


def load_segment_full(p: Path):
    """Load a segment with truth available (for fitting)."""
    df = pd.read_csv(p)
    needed = ["t_s", "delta_road_rad", "v_mps", "yaw_rate_meas_rads", "yaw_rate_pred_rads"]
    if any(c not in df.columns for c in needed):
        return None
    return df


def predict_yaw(df, g, L_eff, K_us, tau, delta0):
    delta = (df["delta_road_rad"].to_numpy() - delta0) * g
    v = df["v_mps"].to_numpy()
    yr_ss = v * delta / (L_eff + K_us * v * v)
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def per_seg_delta0_from_truth_proxy(df, ax_thresh=0.3, v_thresh=5.0, min_rows=50):
    """Per-segment δ₀ at FIT time uses the same input-only proxy."""
    v = df["v_mps"].to_numpy()
    yr0 = df["yaw_rate_pred_rads"].to_numpy()
    a_lat = v * yr0
    mask = (np.abs(a_lat) < ax_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return None
    return float(np.median(df["delta_road_rad"].to_numpy()[mask]))


def fit_platform(plat: str, use_per_seg_delta0: bool, x0=None):
    segs = [load_segment_full(p) for p in find_segments(plat)]
    segs = [s for s in segs if s is not None]
    print(f"[{plat}] {len(segs)} segs")
    if not segs:
        return None

    if x0 is None:
        x0 = np.array([0.88, 2.85, 0.0025, 0.065, 0.0005])

    def loss(x):
        g, L_eff, K_us, tau, delta0_glob = x
        if L_eff < 1.5 or tau < 0.01 or K_us < 0:
            return 1e9
        sum_sq = 0.0
        n = 0
        for df in segs:
            if use_per_seg_delta0:
                d0 = per_seg_delta0_from_truth_proxy(df)
                if d0 is None:
                    d0 = delta0_glob
            else:
                d0 = delta0_glob
            yr = predict_yaw(df, g, L_eff, K_us, tau, d0)
            yr_truth = df["yaw_rate_meas_rads"].to_numpy()
            r = yr - yr_truth
            sum_sq += float((r * r).sum())
            n += len(r)
        return sum_sq / n  # MSE

    res = minimize(loss, x0, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-10, "maxiter": 2000})
    g, L_eff, K_us, tau, delta0_glob = res.x
    rmse = math.sqrt(res.fun)
    print(f"  fit: g={g:.4f} L_eff={L_eff:.3f} K_us={K_us:.5f} tau={tau:.4f} delta0={delta0_glob:.5f}")
    print(f"  train yaw RMSE = {rmse:.6f}")
    return {
        "g": float(g), "L_eff": float(L_eff), "K_us": float(K_us),
        "tau": float(tau), "delta0_glob": float(delta0_glob),
        "train_yaw_rmse": rmse,
    }


if __name__ == "__main__":
    import json
    plat_cfg = {
        "FORD_F_150_LIGHTNING_MK1": False,   # global δ₀
        "FORD_MUSTANG_MACH_E_MK1": True,     # per-segment
        "HYUNDAI_IONIQ_5": False,            # try global; later test per-seg too
    }
    results = {}
    for plat, use_per_seg in plat_cfg.items():
        r = fit_platform(plat, use_per_seg)
        if r:
            r["use_per_segment_delta0"] = use_per_seg
            results[plat] = r
    out_path = ROOT / "out" / "coeffs_fit.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote {out_path}")
