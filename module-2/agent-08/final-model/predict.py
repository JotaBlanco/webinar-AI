"""V1 predict — linear bicycle (understeer-corrected KS) with steering low-pass.

Per-platform parameter fit minimizing pooled yaw-rate residual against
data/sim/segments/ truth. Parameters in coeffs.json.

Model (per row):
  d_lp = lowpass(delta_road_rad - delta_bias, tau, dt)
  yaw_rate_pred = gain * v * d_lp / (L + K * v**2)

Notes:
- L is the canonical openpilot wheelbase per platform.
- K is the equivalent understeer parameter (linear bicycle: m/L*(l_r/C_f - l_f/C_r)).
- gain absorbs steer-ratio/effective-rack-mismatch (Mach-E shows ~1.2, i.e. true
  effective ratio is closer to 14.2 than the catalogued 17).
- tau is a small (~25-30 ms) steering-to-yaw lag, modelling tire relaxation and
  CAN-to-IMU delay together.
- Tesla and any unknown platform fall back to V0 baseline (yaw_rate_pred_rads
  from sim_df when present, else (v/L)*tan(delta_road_rad)).

Trajectory (x,y) is integrated by the canonical grader from yaw_rate_pred_rads
and measured v_mps; we do not emit x_m/y_m.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# Per-platform wheelbase (openpilot-canonical, taken from carParams in rlogs).
L_BY_PLATFORM = {
    "TESLA_MODEL_3":            2.875,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5":          3.0,
}

# Per-platform fitted coefficients (K, delta_bias, gain, tau).
# See coeffs.json for the same data; embedded here so predict has no I/O fail mode.
COEFFS = {
    "FORD_MUSTANG_MACH_E_MK1": {
        "K": 0.00285523365287745,
        "delta_bias": -2.8179389874189196e-05,
        "gain": 1.196537107585879,
        "tau": 0.029808088504421782,
    },
    "FORD_F_150_LIGHTNING_MK1": {
        "K": 0.00382305725063063,
        "delta_bias": 0.0012683878792749746,
        "gain": 0.9708148708946358,
        "tau": 0.027239751977363655,
    },
    "HYUNDAI_IONIQ_5": {
        "K": 0.003388639669047626,
        "delta_bias": -0.0005212717892712406,
        "gain": 0.9689276795142663,
        "tau": 0.023325225151320253,
    },
    # Tesla has no measured truth in the training set (psi_dot_rads is the model's
    # own integrated output), so we fall back to V0 — no statistical leverage to fit.
}


def _lowpass(x: np.ndarray, dt: np.ndarray, tau: float) -> np.ndarray:
    """Single-pole IIR low-pass with per-step alpha = dt / (tau + dt)."""
    if tau <= 1e-6 or len(x) == 0:
        return x.astype(float, copy=True)
    y = np.empty_like(x, dtype=float)
    y[0] = x[0]
    alpha = dt / (tau + dt)
    for i in range(1, len(x)):
        a = alpha[i - 1]
        y[i] = y[i - 1] + a * (x[i] - y[i - 1])
    return y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame with 'yaw_rate_pred_rads' aligned to sim_df.index."""
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    L = L_BY_PLATFORM.get(platform, 2.9)

    if platform in COEFFS:
        c = COEFFS[platform]
        K, db, g, tau = c["K"], c["delta_bias"], c["gain"], c["tau"]
        if len(t) >= 2:
            dt = np.diff(t)
            # guard against any non-positive dt
            dt = np.where(dt > 0, dt, 0.01)
            d_lp = _lowpass(d - db, dt, tau)
        else:
            d_lp = d - db
        denom = L + K * v * v
        yr = g * v * d_lp / denom
    else:
        # Fallback: V0 if precomputed, else KS analytic.
        if "yaw_rate_pred_rads" in sim_df.columns and not sim_df["yaw_rate_pred_rads"].isna().all():
            yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        else:
            yr = (v / L) * np.tan(d)

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
