"""idea-01 lateral-fidelity predict.

Strategy
--------
The baseline KS yaw-rate prediction is the column `yaw_rate_pred_rads` already
present in sim-only inputs (= (v/L) * tan(delta_road)). Empirically the residual
versus measured yaw rate is dominated by an understeer-gradient + steering-gain
mismatch, captured by a simple 3-parameter per-platform linear correction:

    yaw_rate_corr = a + b * yaw_rate_pred_rads + c * yaw_rate_pred_rads * v_mps**2

The (a, b, c) coefficients were fit per platform on the truth-bearing
`data/sim/segments/{platform}/...` by ordinary least squares, with v_mps > 2 m/s
to exclude near-zero-speed noise. See out/fit_final.py for the fit.

x_m, y_m are integrated from (yaw_rate_corr, v_mps) with a simple Euler scheme
starting from the segment's first row.

Coefficients are loaded from coeffs.json sitting next to this file.
"""
from __future__ import annotations

import json
import os
from typing import Any

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "coeffs.json"), "r") as _f:
    _COEFFS = json.load(_f)


def _get_coeffs(platform: str) -> tuple[float, float, float]:
    c = _COEFFS.get(platform) or _COEFFS["_default"]
    return float(c["a"]), float(c["b"]), float(c["c"])


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return DataFrame aligned with sim_df.index containing:

      - yaw_rate_pred_rads : corrected yaw-rate prediction (rad/s)
      - x_m, y_m           : integrated trajectory from corrected yaw rate and v_mps

    Only the columns documented in the grading contract are read from sim_df:
    `t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2, accel_pedal_pct,
    brake_pressed, yaw_rate_pred_rads`. No truth columns are touched.
    """
    a, b, c = _get_coeffs(platform)

    pred_ks = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)

    yaw_rate_corr = a + b * pred_ks + c * pred_ks * (v ** 2)

    # Trajectory integration: trapezoidal heading + Euler position.
    t = sim_df["t_s"].to_numpy(dtype=float)
    N = len(t)
    psi = np.zeros(N)
    if N > 1:
        dt = np.diff(t)
        # trapezoidal integration of yaw rate to heading
        psi[1:] = np.cumsum(0.5 * (yaw_rate_corr[:-1] + yaw_rate_corr[1:]) * dt)

    x = np.zeros(N)
    y = np.zeros(N)
    if N > 1:
        # midpoint integration of velocity along heading
        vx = v * np.cos(psi)
        vy = v * np.sin(psi)
        dt = np.diff(t)
        x[1:] = np.cumsum(0.5 * (vx[:-1] + vx[1:]) * dt)
        y[1:] = np.cumsum(0.5 * (vy[:-1] + vy[1:]) * dt)

    out = pd.DataFrame(
        {
            "yaw_rate_pred_rads": yaw_rate_corr,
            "x_m": x,
            "y_m": y,
        },
        index=sim_df.index,
    )
    return out
