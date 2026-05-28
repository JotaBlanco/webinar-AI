"""Evaluator for lateral fidelity.

Two KPIs:
1. Yaw-rate RMSE  (rad/s) — vs yaw_rate_meas_rads
2. Distance-resampled cross-track error RMSE (m) —
   integrate truth trajectory from (yaw_rate_meas, v_meas) and predicted
   trajectory from (yaw_rate_pred, v_meas), then resample both to uniform
   distance and compute lateral offset RMSE.

Ford platforms only (Tesla has no truth yaw rate).
"""
from __future__ import annotations
import json, sys, glob
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "sim"
FORD_PLATFORMS = ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1")


def load_segments(platform: str, limit: int | None = None) -> list[pd.DataFrame]:
    man = json.load(open(DATA / "segments" / platform / "manifest.json"))
    segs = man["segments"][: limit] if limit else man["segments"]
    dfs = []
    for s in segs:
        p = DATA / s["csv_path"]
        df = pd.read_csv(p)
        df.attrs["seg"] = f"{s['device']}/{s['route']}/{s['idx']}"
        df.attrs["platform"] = platform
        dfs.append(df)
    return dfs


def integrate_xy(t: np.ndarray, v: np.ndarray, yaw_rate: np.ndarray,
                 x0: float = 0.0, y0: float = 0.0, psi0: float = 0.0):
    """Integrate (v, yaw_rate) -> (x, y, psi). Trapezoidal."""
    dt = np.diff(t, prepend=t[0])
    psi = psi0 + np.cumsum(yaw_rate * dt) - yaw_rate[0] * dt[0]  # start from psi0
    # Use midpoint heading for x,y integration to reduce error
    psi_mid = psi.copy()
    psi_mid[1:] = 0.5 * (psi[1:] + psi[:-1])
    psi_mid[0] = psi0
    dx = v * np.cos(psi_mid) * dt
    dy = v * np.sin(psi_mid) * dt
    x = x0 + np.cumsum(dx) - dx[0]
    y = y0 + np.cumsum(dy) - dy[0]
    return x, y, psi


def distance_resample_cte(t, v, yr_truth, yr_pred):
    """Compute distance-resampled cross-track error RMSE.

    Integrate two trajectories from same (x0,y0,psi0)=(0,0,0) using measured v
    for both. Resample both at uniform arc length (based on truth path length),
    then take perpendicular distance — but the simpler & standard interpretation
    is: at each sampled distance s, compare y_pred(s) - y_truth(s) in the
    truth's path-aligned frame. We use the latter (path-aligned lateral offset).
    """
    x_t, y_t, psi_t = integrate_xy(t, v, yr_truth)
    x_p, y_p, psi_p = integrate_xy(t, v, yr_pred)

    # arc length of truth
    ds_t = np.sqrt(np.diff(x_t, prepend=x_t[0])**2 + np.diff(y_t, prepend=y_t[0])**2)
    s_t = np.cumsum(ds_t)
    if s_t[-1] < 1.0:
        return np.nan
    # Same for predicted
    ds_p = np.sqrt(np.diff(x_p, prepend=x_p[0])**2 + np.diff(y_p, prepend=y_p[0])**2)
    s_p = np.cumsum(ds_p)

    s_grid = np.arange(0, min(s_t[-1], s_p[-1]), 1.0)  # 1 m spacing
    if len(s_grid) < 2:
        return np.nan

    # Interpolate both x,y onto s_grid
    xt_s = np.interp(s_grid, s_t, x_t)
    yt_s = np.interp(s_grid, s_t, y_t)
    psit_s = np.interp(s_grid, s_t, psi_t)
    xp_s = np.interp(s_grid, s_p, x_p)
    yp_s = np.interp(s_grid, s_p, y_p)

    # Perpendicular (path-normal) offset of pred from truth.
    # Normal to truth heading: (-sin(psi_t), cos(psi_t))
    dx = xp_s - xt_s
    dy = yp_s - yt_s
    cte = -np.sin(psit_s) * dx + np.cos(psit_s) * dy
    return float(np.sqrt(np.mean(cte**2)))


def yaw_rate_rmse(yr_truth, yr_pred):
    e = yr_pred - yr_truth
    e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e**2)))


def score_v0(platform: str, limit: int | None = None):
    dfs = load_segments(platform, limit)
    yr_rmses = []
    cte_rmses = []
    for df in dfs:
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        yt = df["yaw_rate_meas_rads"].to_numpy()
        yp = df["yaw_rate_pred_rads"].to_numpy()
        mask = np.isfinite(yt) & np.isfinite(yp) & np.isfinite(v)
        if mask.sum() < 50:
            continue
        t, v, yt, yp = t[mask], v[mask], yt[mask], yp[mask]
        # re-base time
        t = t - t[0]
        yr_rmses.append(yaw_rate_rmse(yt, yp))
        cte = distance_resample_cte(t, v, yt, yp)
        if np.isfinite(cte):
            cte_rmses.append(cte)
    return {
        "n": len(yr_rmses),
        "yaw_rate_rmse_rads": float(np.mean(yr_rmses)),
        "cte_rmse_m": float(np.mean(cte_rmses)) if cte_rmses else float("nan"),
        "cte_rmses": cte_rmses,
        "yr_rmses": yr_rmses,
    }


def score_predict(predict_fn, platform: str, limit: int | None = None):
    """Score a custom predict(sim_df, platform) function."""
    dfs = load_segments(platform, limit)
    yr_rmses = []
    cte_rmses = []
    failed = 0
    for df in dfs:
        try:
            out = predict_fn(df, platform)
        except Exception as e:
            failed += 1
            continue
        yp = out["yaw_rate_pred_rads"].to_numpy()
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        yt = df["yaw_rate_meas_rads"].to_numpy()
        mask = np.isfinite(yt) & np.isfinite(yp) & np.isfinite(v)
        if mask.sum() < 50:
            continue
        t, v, yt, yp_m = t[mask], v[mask], yt[mask], yp[mask]
        t = t - t[0]
        yr_rmses.append(yaw_rate_rmse(yt, yp_m))
        cte = distance_resample_cte(t, v, yt, yp_m)
        if np.isfinite(cte):
            cte_rmses.append(cte)
    return {
        "n": len(yr_rmses),
        "failed": failed,
        "yaw_rate_rmse_rads": float(np.mean(yr_rmses)) if yr_rmses else float("nan"),
        "cte_rmse_m": float(np.mean(cte_rmses)) if cte_rmses else float("nan"),
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    for plat in FORD_PLATFORMS:
        r = score_v0(plat, limit=args.limit)
        print(f"[V0 baseline] {plat}: n={r['n']} "
              f"yaw_rate_rmse={r['yaw_rate_rmse_rads']:.4f} rad/s  "
              f"cte_rmse={r['cte_rmse_m']:.3f} m")
