"""Final-model predict: per-platform understeer + steer-scale correction.

Model (variant V2):

    yaw_rate_pred = v * (a * delta_road + b) / (L + K_us * v^2)

where (L, a, b, K_us) are platform-specific coefficients fitted on the
training segments. Falls back to V0 (KS: (v/L)*tan(delta)) for any platform
not in the coefficient table.

The trajectory (x_m, y_m) is integrated from yaw_rate_pred + measured v_mps
using the same Euler-style integrator the grader's CTE metric uses.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
_COEFFS = json.loads(_COEFFS_PATH.read_text())


def _yaw_rate_v2(v: np.ndarray, delta: np.ndarray, L: float, K: float, a: float, b: float) -> np.ndarray:
    denom = L + K * v * v
    return v * (a * delta + b) / denom


def _yaw_rate_v0(v: np.ndarray, delta: np.ndarray, L: float) -> np.ndarray:
    return (v / L) * np.tan(delta)


def _integrate_traj(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Match _shared/traj_metrics.integrate_trajectory: psi[0]=0, x[0]=0, y[0]=0."""
    n = len(v)
    psi = np.zeros(n)
    x = np.zeros(n)
    y = np.zeros(n)
    if n < 2:
        return x, y
    dt = np.diff(t)
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y


_FALLBACK_L = {
    "TESLA_MODEL_3":            2.875,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5":          3.00,
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    coeffs = _COEFFS.get(platform)
    if coeffs is not None:
        L = float(coeffs["L"])
        K = float(coeffs["K_v2"])
        a = float(coeffs["a_v2"])
        b = float(coeffs["b_v2"])
        yr = _yaw_rate_v2(v, delta, L, K, a, b)
    else:
        # Fallback: V0 KS using a reasonable L.
        L = _FALLBACK_L.get(platform, 2.9)
        yr = _yaw_rate_v0(v, delta, L)

    x, y = _integrate_traj(t, v, yr)

    out = pd.DataFrame({
        "yaw_rate_pred_rads": yr,
        "x_m": x,
        "y_m": y,
    }, index=sim_df.index)
    return out
