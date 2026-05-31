"""Final model — per-platform understeer-augmented KS with first-order lag.

Steady-state form (steady-state bicycle understeer):
    y_ss = kk * v * tan(delta - d0) / (L + KK * v^2)

First-order lag on yaw rate to capture steering-compliance / actuator dynamics:
    y[k] = (1 - alpha_k) * y[k-1] + alpha_k * y_ss[k],
    alpha_k = dt_k / (tau + dt_k)

Coefficients fitted per platform on data/sim/segments (truth = yaw_rate_meas_rads).
Tesla returns V0 verbatim — its truth IS V0. Unknown platforms fall back to V0.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).parent / "coeffs.json"
with _COEFFS_PATH.open() as _f:
    COEFFS = json.load(_f)


def _first_order_lag(y_ss: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 0:
        return y_ss.copy()
    n = len(y_ss)
    y = np.empty(n)
    y[0] = y_ss[0]
    for i in range(1, n):
        dt = t[i] - t[i - 1]
        if dt <= 0:
            y[i] = y[i - 1]
            continue
        alpha = dt / (tau + dt)
        y[i] = (1.0 - alpha) * y[i - 1] + alpha * y_ss[i]
    return y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform == "TESLA_MODEL_3" or platform not in COEFFS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()},
            index=sim_df.index,
        )

    c = COEFFS[platform]
    L = float(c["L"])
    d0 = float(c["d0"])
    kk = float(c["kk"])
    KK = float(c["KK"])
    tau = float(c.get("tau", 0.0))

    v = sim_df["v_mps"].astype(float).to_numpy()
    d = sim_df["delta_road_rad"].astype(float).to_numpy()
    t = sim_df["t_s"].astype(float).to_numpy()

    y_ss = kk * v * np.tan(d - d0) / (L + KK * v * v)
    y = _first_order_lag(y_ss, t, tau)

    return pd.DataFrame({"yaw_rate_pred_rads": y}, index=sim_df.index)
