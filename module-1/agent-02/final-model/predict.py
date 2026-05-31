"""Lateral fidelity V1: linear bicycle / understeer model.

V0 baseline (in sim-only as `yaw_rate_pred_rads`):

    yaw_pred = (v / L) * tan(delta_road)

V1 (this module): per-platform linear bicycle with steering bias:

    yaw_pred = v * (delta_road - bias) / (L + K_us * v^2)

Coefficients in coeffs.json were fit by `out/fit_v1.py` on data/sim/segments/.

Returns a DataFrame indexed to match sim_df, with columns:
    yaw_rate_pred_rads  (required)
    x_m, y_m            (optional, integrated from yaw rate + measured v)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).parent / 'coeffs.json'

with open(_COEFFS_PATH) as _f:
    _COEFFS = json.load(_f)


def _coeffs_for(platform: str):
    if platform in _COEFFS:
        return _COEFFS[platform]
    # graceful fallback to Tesla KS-equivalent coeffs
    return _COEFFS.get('TESLA_MODEL_3', {'L': 2.9, 'K_us': 0.0, 'bias_rad': 0.0})


def _integrate_trajectory(t: np.ndarray, v: np.ndarray,
                          yaw_rate: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Trapezoid-integrate heading from yaw_rate, then (x,y) from v*cos/sin(psi)."""
    psi = np.zeros_like(t)
    if len(t) > 1:
        dt = np.diff(t)
        # trapezoid for psi
        psi_inc = 0.5 * (yaw_rate[:-1] + yaw_rate[1:]) * dt
        psi[1:] = np.cumsum(psi_inc)
    vx = v * np.cos(psi)
    vy = v * np.sin(psi)
    x = np.zeros_like(t)
    y = np.zeros_like(t)
    if len(t) > 1:
        dt = np.diff(t)
        x[1:] = np.cumsum(0.5 * (vx[:-1] + vx[1:]) * dt)
        y[1:] = np.cumsum(0.5 * (vy[:-1] + vy[1:]) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Lateral predictor. See module docstring.

    Inputs (sim_df columns required):
        t_s, delta_road_rad, v_mps
    """
    c = _coeffs_for(platform)
    L = float(c['L'])
    K_us = float(c['K_us'])
    bias = float(c['bias_rad'])

    delta = sim_df['delta_road_rad'].to_numpy(dtype=float)
    v = sim_df['v_mps'].to_numpy(dtype=float)
    t = sim_df['t_s'].to_numpy(dtype=float)

    # Linear bicycle with bias
    yaw = v * (delta - bias) / (L + K_us * v ** 2)

    x, y = _integrate_trajectory(t, v, yaw)

    out = pd.DataFrame({
        'yaw_rate_pred_rads': yaw,
        'x_m': x,
        'y_m': y,
    }, index=sim_df.index)
    return out
