"""Final-model predict for the lateral-fidelity task.

Approach: per-platform linear correction of V0 yaw_rate using a hand-crafted
polynomial basis in (yaw_v0, v, delta_road, steer_rate, a_long). Coefficients
fit by closed-form least squares against truth yaw rate on all training
sim/segments with v > 2 m/s.

x, y trajectory is integrated downstream of yaw_rate (Euler-style, starts at
(0,0,0,0); matches the trajectory integration the canonical grader uses).

Tesla has no independent truth channel — its only baseline IS V0 (psi_dot_rads),
so we pass V0 through unchanged on TESLA_MODEL_3.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_COEFFS = json.loads((_HERE / "coeffs.json").read_text())

FEATURES = ["yv0", "v", "d", "vd", "v2d", "d3", "vd3", "v2d3",
            "sr", "vsr", "d_abs_d", "a_long"]


def _steer_rate(sim_df: pd.DataFrame, d: np.ndarray, t: np.ndarray) -> np.ndarray:
    if "steer_rate_dps" in sim_df.columns:
        return sim_df["steer_rate_dps"].astype(float).to_numpy() * np.pi / 180.0
    if len(t) < 2:
        return np.zeros_like(d)
    return np.gradient(d, t)


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray):
    """Match _shared/traj_metrics.integrate_trajectory (zero-order hold)."""
    n = len(v)
    if n < 2:
        z = np.zeros(n)
        return z, z
    dt = np.diff(t)
    psi = np.empty(n); psi[0] = 0.0
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x = np.empty(n); x[0] = 0.0
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y = np.empty(n); y[0] = 0.0
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict per-sample yaw_rate (and trajectory) aligned with sim_df.index."""
    out = pd.DataFrame(index=sim_df.index)
    yv0 = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()

    c = _COEFFS.get(platform)
    if c is None:
        # Unknown or passthrough platform (Tesla, or anything we never fit).
        yp = yv0
    else:
        v = sim_df["v_mps"].astype(float).to_numpy()
        d = sim_df["delta_road_rad"].astype(float).to_numpy()
        t = sim_df["t_s"].astype(float).to_numpy()
        sr = _steer_rate(sim_df, d, t)
        a_long = (sim_df["a_long_mps2"].astype(float).to_numpy()
                  if "a_long_mps2" in sim_df.columns else np.zeros_like(v))

        feats = {
            "yv0": yv0,
            "v":   v,
            "d":   d,
            "vd":  v * d,
            "v2d": v * v * d,
            "d3":  d ** 3,
            "vd3": v * (d ** 3),
            "v2d3": v * v * (d ** 3),
            "sr":  sr,
            "vsr": v * sr,
            "d_abs_d": d * np.abs(d),
            "a_long":  a_long,
        }
        yp = c["intercept"] + sum(c[name] * feats[name] for name in FEATURES)

    # Guard against NaN from upstream nulls (rare but possible)
    yp = np.nan_to_num(yp, nan=0.0, posinf=0.0, neginf=0.0)

    out["yaw_rate_pred_rads"] = yp

    # Optional trajectory integration (matches grader convention).
    try:
        t = sim_df["t_s"].astype(float).to_numpy()
        v = sim_df["v_mps"].astype(float).to_numpy()
        x, y = _integrate_xy(t, v, yp)
        out["x_m"] = x
        out["y_m"] = y
    except Exception:
        # Not fatal — the spec says x_m/y_m are optional and the grader can
        # integrate from yaw_rate_pred_rads itself.
        pass

    return out
