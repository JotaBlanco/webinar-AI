"""Calibrated single-track lateral predictor.

Model:
    yr(t) = v(t) * (s * delta(t + lag) + off) / (L + K * v(t)^2)

Per-platform coefficients (K, s, off, lag, L) fit by least-squares on
sim/segments truth (yaw_rate_meas_rads). For platforms without truth in
sim (TESLA_MODEL_3), we fall back to identity steering scale, zero offset,
median understeer K, and median lag observed across the other platforms.

Trajectory (x, y) is integrated from the predicted yaw rate and the measured
longitudinal speed, starting from the origin with heading 0.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with open(_COEFFS_PATH) as _fh:
    _COEFFS = json.load(_fh)

# Default fallback (median over fitted platforms)
_DEFAULT = {
    "L": 3.0,
    "K": 0.0034,
    "s": 1.0,
    "off": 0.0,
    "lag": 3,
}


def _shift_lag(arr: np.ndarray, lag: int) -> np.ndarray:
    """Shift arr by `lag` timesteps so that index t holds value at t+lag.
    Positive lag => look 'lag' steps into the future (steering leads yaw).
    """
    if lag == 0:
        return arr.copy()
    out = np.empty_like(arr)
    if lag > 0:
        out[:-lag] = arr[lag:]
        out[-lag:] = arr[-1]
    else:
        l = -lag
        out[l:] = arr[:-l]
        out[:l] = arr[0]
    return out


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate and trajectory.

    Required input columns: t_s, delta_road_rad, v_mps.
    Returns DataFrame indexed identically to sim_df with:
        yaw_rate_pred_rads, x_m, y_m, psi_rad
    """
    c = _COEFFS.get(platform, _DEFAULT)
    L = float(c["L"])
    K = float(c["K"])
    s = float(c["s"])
    off = float(c["off"])
    lag = int(c["lag"])

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)

    # Handle NaNs robustly (forward/back-fill)
    if np.isnan(delta).any():
        delta = pd.Series(delta).bfill().ffill().to_numpy()
    if np.isnan(v).any():
        v = pd.Series(v).bfill().ffill().to_numpy()

    delta_lag = _shift_lag(delta, lag)

    # Calibrated bicycle understeer model
    denom = L + K * v * v
    yr = v * (s * delta_lag + off) / denom
    yr = np.nan_to_num(yr, nan=0.0, posinf=0.0, neginf=0.0)

    # Trajectory: integrate heading + position using trapezoidal scheme
    N = len(t)
    if N == 0:
        return pd.DataFrame({"yaw_rate_pred_rads": [], "x_m": [], "y_m": [], "psi_rad": []},
                            index=sim_df.index)
    psi = np.zeros(N)
    x = np.zeros(N)
    y = np.zeros(N)
    for k in range(N - 1):
        dt = t[k + 1] - t[k]
        if not np.isfinite(dt) or dt <= 0:
            dt = 0.02
        # average yaw rate over interval
        yr_mid = 0.5 * (yr[k] + yr[k + 1])
        psi[k + 1] = psi[k] + yr_mid * dt
        # average heading and speed for translation
        psi_mid = 0.5 * (psi[k] + psi[k + 1])
        v_mid = 0.5 * (v[k] + v[k + 1])
        x[k + 1] = x[k] + v_mid * np.cos(psi_mid) * dt
        y[k + 1] = y[k] + v_mid * np.sin(psi_mid) * dt

    return pd.DataFrame(
        {
            "yaw_rate_pred_rads": yr,
            "x_m": x,
            "y_m": y,
            "psi_rad": psi,
        },
        index=sim_df.index,
    )


if __name__ == "__main__":
    # Smoke test
    import glob
    files = glob.glob('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/data/sim-only/segments/HYUNDAI_IONIQ_5/*/*/*/sim.csv')[:1]
    if files:
        df = pd.read_csv(files[0])
        out = predict(df, "HYUNDAI_IONIQ_5")
        print(out.head())
        print(f'yr range: [{out.yaw_rate_pred_rads.min():.3f}, {out.yaw_rate_pred_rads.max():.3f}]')
        print(f'x range: [{out.x_m.min():.1f}, {out.x_m.max():.1f}]')
