"""Final-model predict for module-2/agent-06.

Approach
--------
Baseline V0 is the kinematic single-track (KS) yaw rate:
    yr = (v / L) * tan(delta_road)

V1 augments this with a per-platform linear-tyre understeer term and a
small DOF for steering-channel scale and bias:
    yr = v * (s * delta_road - d0) / (L + K * v^2)

Coefficients (K, s, d0, L) are fitted offline on data/sim/segments/ via
out/fit_understeer.py and stored in coefs.json (next to this file).

For TESLA_MODEL_3 the simulator truth IS the V0 formula (synthetic),
so V1 cannot improve on it — we passthrough the V0 baseline that already
ships in `yaw_rate_pred_rads`.

For platforms not seen during fitting we fall back to V0 passthrough.

Trajectory (x_m, y_m) is integrated from (yaw_rate, v_meas) starting at
(0, 0, psi=0), matching the convention in _shared/traj_metrics.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFS_PATH = Path(__file__).resolve().parent / "coefs.json"
with open(_COEFS_PATH) as f:
    COEFS = json.load(f)

# Platforms where the simulator truth matches V0 (KS) exactly — keep V0.
_V0_PASSTHROUGH = {"TESLA_MODEL_3"}


def _v1_yaw(delta_road: np.ndarray, v: np.ndarray, c: dict) -> np.ndarray:
    L = c["L"]
    K = c["K"]
    s = c["s"]
    d0 = c["d0"]
    return v * (s * delta_road - d0) / (L + K * v * v)


def _v0_yaw(delta_road: np.ndarray, v: np.ndarray, L: float) -> np.ndarray:
    return (v / L) * np.tan(delta_road)


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(t)
    if n < 2:
        return np.zeros(n), np.zeros(n)
    dt = np.diff(t)
    psi = np.empty(n)
    psi[0] = 0.0
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x = np.empty(n)
    y = np.empty(n)
    x[0] = 0.0
    y[0] = 0.0
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    if platform in _V0_PASSTHROUGH and "yaw_rate_pred_rads" in sim_df.columns:
        # Use the baseline already in the input — matches truth exactly on Tesla.
        yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    elif platform in COEFS:
        yr = _v1_yaw(delta, v, COEFS[platform])
    elif "yaw_rate_pred_rads" in sim_df.columns:
        yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    else:
        # Last-ditch: KS with a generic L (passenger-car average).
        yr = _v0_yaw(delta, v, 2.9)

    x, y = _integrate_xy(t, v, yr)
    out = pd.DataFrame(
        {
            "yaw_rate_pred_rads": yr,
            "x_m": x,
            "y_m": y,
        },
        index=sim_df.index,
    )
    return out
