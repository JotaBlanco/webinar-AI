"""V2 predict — per-platform kinematic-bicycle understeer + steering bias +
first-order steering lag.

Model:
    delta_lag[k] = (1 - a) * delta_lag[k-1] + a * delta_road[k]    a = dt/(tau+dt)
    yaw_rate    = v * (delta_lag + bias) / (L_eff + K * v^2)

Per-platform coefficients (L_eff, K, bias, tau) are fitted by linear least
squares against the sim/ truth (yaw_rate_meas_rads) — see fit_v2.py in the
parent module's out/. They live in coeffs.json next to this file.

For unknown platforms (e.g. TESLA_MODEL_3, which has no truth in sim/),
falls back to V0 kinematic-bicycle: yr = v * tan(delta_road) / L_nominal.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_COEFFS_PATH = _HERE / "coeffs.json"
COEFFS = json.loads(_COEFFS_PATH.read_text())

# Nominal wheelbases (openpilot carParams source-of-record).
_WHEELBASE_M = {
    "TESLA_MODEL_3": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5": 3.00,
}


def _lag(delta: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    """Causal first-order low-pass with time-constant tau on a possibly non-uniform t grid."""
    if tau <= 1e-6 or len(delta) < 2:
        return delta.astype(float).copy()
    dt = np.diff(t, prepend=t[0])
    out = np.empty_like(delta, dtype=float)
    out[0] = delta[0]
    for i in range(1, len(delta)):
        a = dt[i] / (tau + dt[i])
        out[i] = (1.0 - a) * out[i - 1] + a * delta[i]
    return out


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate per row from (v_mps, delta_road_rad, t_s).

    Returns a DataFrame aligned with sim_df.index with column
    ``yaw_rate_pred_rads``.
    """
    v = sim_df["v_mps"].to_numpy(float)
    d = sim_df["delta_road_rad"].to_numpy(float)
    t = sim_df["t_s"].to_numpy(float)

    coef = COEFFS.get(platform)
    if coef is None:
        # Unknown platform → V0 fallback.
        L = _WHEELBASE_M.get(platform, 2.95)
        yr = (v / L) * np.tan(d)
    else:
        d_eff = _lag(d, t, float(coef["tau"]))
        denom = float(coef["L_eff"]) + float(coef["K_u"]) * v * v
        yr = v * (d_eff + float(coef["delta_bias_rad"])) / denom

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
