"""Improved lateral predictor (V2b).

Model:
    yaw_rate = (v / L) * tan(k * (delta - b)) / (1 + Ku * v^2)

This is the linear-bicycle steady-state response: a steering bias `b`, a
steering gain `k` (compliance / ratio scaling), and an understeer gradient
`Ku`. Coefficients are fit per platform on the training data
(yaw_rate_meas_rads where available; for Tesla, on a wheel-speed-derived
proxy of yaw rate).

Trajectory (x_m, y_m) is integrated from the predicted yaw rate together
with the measured forward speed v_mps using a simple Euler integration
of the kinematic point-mass equations:
    psi(k+1) = psi(k) + yaw(k) * dt
    x(k+1)   = x(k) + v(k) * cos(psi(k)) * dt
    y(k+1)   = y(k) + v(k) * sin(psi(k)) * dt
"""
from __future__ import annotations

import json
import os
from typing import Optional

import numpy as np
import pandas as pd

_COEFFS_PATH = os.path.join(os.path.dirname(__file__), "coeffs.json")
with open(_COEFFS_PATH) as _f:
    _COEFFS = json.load(_f)


def _get_params(platform: str) -> dict:
    plats = _COEFFS["platforms"]
    if platform in plats:
        return plats[platform]
    return _COEFFS["default"]


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate and trajectory aligned to sim_df.index.

    Required columns in sim_df: t_s, delta_road_rad, v_mps.

    Returns a DataFrame with same index containing:
        yaw_rate_pred_rads, x_m, y_m
    """
    p = _get_params(platform)
    L = float(p["L"])
    b = float(p.get("b", 0.0))
    Ku = float(p.get("Ku", 0.0))
    k = float(p.get("k", 1.0))

    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    # V2b yaw-rate model
    yaw = (v / L) * np.tan(k * (delta - b)) / (1.0 + Ku * v * v)

    # Integrate trajectory in (x, y) from yaw + v.
    n = len(t)
    x = np.zeros(n)
    y = np.zeros(n)
    psi = np.zeros(n)
    for i in range(n - 1):
        dt = t[i + 1] - t[i]
        # midpoint speed for slight stability
        v_mid = 0.5 * (v[i] + v[i + 1])
        psi_next = psi[i] + yaw[i] * dt
        psi_mid = 0.5 * (psi[i] + psi_next)
        x[i + 1] = x[i] + v_mid * np.cos(psi_mid) * dt
        y[i + 1] = y[i] + v_mid * np.sin(psi_mid) * dt
        psi[i + 1] = psi_next

    out = pd.DataFrame(
        {
            "yaw_rate_pred_rads": yaw,
            "x_m": x,
            "y_m": y,
        },
        index=sim_df.index,
    )
    return out


if __name__ == "__main__":
    # Smoke test on one sim-only segment if available.
    import glob

    pattern = (
        "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/"
        "data/sim-only/segments/*/*/*/*/sim.csv"
    )
    paths = glob.glob(pattern)
    if paths:
        p0 = paths[0]
        plat = p0.split("segments/")[1].split("/")[0]
        df = pd.read_csv(p0)
        pred = predict(df, plat)
        print(f"OK platform={plat} n={len(df)}")
        print(pred.head())
