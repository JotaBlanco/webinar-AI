"""Lateral-fidelity predict() — V2: per-platform KS + nonlinear steering scale +
speed-dependent understeer + first-order yaw lag.

Model
-----
For each Ford platform we fit per-platform parameters on whole-route train
splits (Mach-E, F-150 Lightning). The steady-state yaw rate is

    delta_eff = g0 * delta + g2 * delta * |delta| + delta0
    K_eff     = K0 + K1 * v
    yr_ss     = v * delta_eff / (L_eff + K_eff * v^2)

then low-passed by a first-order IIR with time constant `tau` to model
yaw-rate lag. Tesla has no truth channel, so we fall back to the supplied
V0 `yaw_rate_pred_rads`.

Returns a DataFrame indexed like sim_df with column `yaw_rate_pred_rads`.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFFS_PATH.open("r", encoding="utf-8") as _fh:
    COEFFS = json.load(_fh)


def _first_order_lag(yr_ss: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    """Single-pole IIR low-pass at variable dt. y[k+1] = a*y[k] + (1-a)*x[k+1], a=exp(-dt/tau)."""
    if tau <= 1e-6 or len(yr_ss) < 2:
        return yr_ss.copy()
    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    dt = np.diff(t)
    # Guard against pathological dt
    dt = np.clip(dt, 1e-6, None)
    a = np.exp(-dt / tau)
    for k in range(len(dt)):
        y[k + 1] = a[k] * y[k] + (1.0 - a[k]) * yr_ss[k + 1]
    return y


def _physics_yaw_rate(delta: np.ndarray, v: np.ndarray, t: np.ndarray, p: dict) -> np.ndarray:
    delta_eff = p["g0"] * delta + p["g2"] * delta * np.abs(delta) + p["delta0"]
    K_eff = p["K0"] + p["K1"] * v
    L = p["L_eff"]
    yr_ss = v * delta_eff / (L + K_eff * v * v)
    return _first_order_lag(yr_ss, t, p["tau"])


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate for one segment.

    Parameters
    ----------
    sim_df : pandas.DataFrame
        Must contain columns `t_s`, `v_mps`, `delta_road_rad`. For Tesla (no fit),
        must also contain `yaw_rate_pred_rads` (the V0 channel).
    platform : str
        Platform tag, one of FORD_F_150_LIGHTNING_MK1, FORD_MUSTANG_MACH_E_MK1,
        TESLA_MODEL_3.

    Returns
    -------
    pandas.DataFrame with the same index as `sim_df` and column
    `yaw_rate_pred_rads` (float).
    """
    if platform in COEFFS:
        t = sim_df["t_s"].to_numpy(dtype=float)
        v = sim_df["v_mps"].to_numpy(dtype=float)
        delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
        yr = _physics_yaw_rate(delta, v, t, COEFFS[platform])
    else:
        # Tesla / unknown: fall back to V0 passthrough if available.
        if "yaw_rate_pred_rads" in sim_df.columns:
            yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        else:
            # Last-ditch: kinematic single-track with default L=3.0
            t = sim_df["t_s"].to_numpy(dtype=float)
            v = sim_df["v_mps"].to_numpy(dtype=float)
            delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
            yr = v * delta / 3.0

    # Make sure no NaN sneaks out — fill with zeros if anything went wrong.
    yr = np.asarray(yr, dtype=float)
    if np.any(~np.isfinite(yr)):
        yr = np.nan_to_num(yr, nan=0.0, posinf=0.0, neginf=0.0)

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
