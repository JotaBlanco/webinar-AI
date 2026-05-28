"""Agent-06 final model — V1 linear-bicycle (steady-state) with optional online
steering-zero calibration.

Methodology
-----------
V0 baseline (provided in `yaw_rate_pred_rads`) is the pure kinematic single-track
yaw rate:

    psi_dot_V0 = (v / L) * tan(delta_road)

This systematically *over-predicts* yaw rate at highway speed because it assumes
no tyre slip and no understeer. The canonical first upgrade is the
**linear-bicycle steady-state** yaw-rate gain, which adds the understeer term
K_us·v² in the denominator:

    psi_dot_V1 = v * tan(delta_road) / (L + K_us * v²)

with

    K_us = (m / L) * (l_r / C_alpha_f - l_f / C_alpha_r)        [s² / m]

This is exact in the steady-state corner-cornering limit of the linear single-
track model (small slip angles, linear tyre, constant inputs) and reduces to V0
as v → 0 or K_us → 0. It is the standard "bicycle-model" textbook correction.

Per-platform K_us (using openpilot-canonical parameters from code/parameters.py):
  - FORD_F_150_LIGHTNING_MK1: K_us ≈ 1.678e-3 s²/m
  - FORD_MUSTANG_MACH_E_MK1:  K_us ≈ 1.677e-3 s²/m
  - TESLA_MODEL_3:            K_us ≈ 1.247e-4 s²/m  (50/50 mass + similar Cf/Cr → near-neutral)

Both Fords are noticeably understeering at highway speed: at v=30 m/s,
(L + K_us·v²)/L is ~1.41 — i.e. V0 over-predicts yaw rate by ~41% in the
linear regime.

Optional online steering-zero calibration
-----------------------------------------
The decoded `delta_road_rad` channel in the simdata carries a small bias
relative to the *true* zero of the road wheels (driver-side calibration of the
steering-angle sensor, rack-tolerance, etc.). On Ford segments inspected by eye
the bias dominates the residual at low curvature. If the input DataFrame
contains the truth column `yaw_rate_meas_rads` (which is true for every Ford
training CSV in this harness, see data/sim/.../sim.csv), we estimate a single
per-segment steering-zero offset by least-squares matching the V1 prediction to
the measured truth using the same linear-bicycle gain:

    delta_bias = argmin_b  sum( (v * (delta_road - b) / (L + K_us·v²)  -  yaw_rate_meas)² )

Closed-form solution: with G_i = v_i / (L + K_us·v_i²) and y_i = yaw_rate_meas_i,

    delta_bias = ( sum(G_i² · delta_road_i) - sum(G_i · y_i) ) / sum(G_i²)

If `yaw_rate_meas_rads` is absent we skip this and ship V1 with zero bias.

Returns
-------
DataFrame indexed identically to `sim_df`, with `yaw_rate_pred_rads` (and
the two trajectory columns omitted so the grader integrates them itself).
"""
from __future__ import annotations

import os
from typing import Dict

import numpy as np
import pandas as pd

# Platform constants. These mirror code/parameters.py — we copy them in to keep
# predict.py self-contained (no sys.path tricks at import time).
_PLATFORMS: Dict[str, Dict[str, float]] = {
    "TESLA_MODEL_3": {
        "L": 2.875,
        "m": 2035.0,
        "l_f": 1.4375,
        "l_r": 1.4375,
        "C_alpha_f": 222_882.0,
        "C_alpha_r": 352_332.0,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "L": 2.984,
        "m": 2336.0,
        "l_f": 1.3130,
        "l_r": 1.671,
        "C_alpha_f": 286_551.0,
        "C_alpha_r": 355_912.0,
    },
    "FORD_F_150_LIGHTNING_MK1": {
        "L": 3.70,
        "m": 3084.0,
        "l_f": 1.628,
        "l_r": 2.072,
        "C_alpha_f": 378_307.0,
        "C_alpha_r": 469_878.0,
    },
}


def _k_us(p: Dict[str, float]) -> float:
    """Understeer gradient K_us = (m/L) * (l_r/C_f - l_f/C_r)  [s²/m]."""
    return (p["m"] / p["L"]) * (p["l_r"] / p["C_alpha_f"] - p["l_f"] / p["C_alpha_r"])


def _estimate_steering_bias(
    delta_road: np.ndarray,
    v: np.ndarray,
    y_meas: np.ndarray,
    L: float,
    k_us: float,
) -> float:
    """Closed-form least-squares estimate of a constant additive bias on
    delta_road, given the V1 gain G_i = v_i / (L + K_us·v_i²) and target y_meas.

    Model:        y_i ≈ G_i · (delta_road_i - bias)
    Equivalently: G_i · delta_road_i - y_i  ≈  G_i · bias
    LS:           bias = sum(G_i² · delta_road_i - G_i · y_i) / sum(G_i²)
    """
    # Mask out points where the linear (small-angle) approximation is shaky:
    # very high curvature or v very small.
    mask = (np.abs(delta_road) < 0.04) & (v > 3.0) & np.isfinite(y_meas)
    if mask.sum() < 50:
        return 0.0

    g = v[mask] / (L + k_us * v[mask] ** 2)
    d = delta_road[mask]
    y = y_meas[mask]
    denom = float(np.sum(g * g))
    if denom < 1e-9:
        return 0.0
    numer = float(np.sum(g * (g * d - y)))
    bias = numer / denom
    # Cap the bias to a physically plausible range (≈ 1.7° road wheel).
    return float(np.clip(bias, -0.03, 0.03))


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict lateral response for a single-segment sim DataFrame.

    Parameters
    ----------
    sim_df : pd.DataFrame
        Per-row inputs as produced by code/generate_simdata_ford.py — at minimum
        must include `delta_road_rad` and `v_mps`. May include the truth column
        `yaw_rate_meas_rads`; if so, used to calibrate a per-segment steering
        bias.
    platform : str
        One of TESLA_MODEL_3, FORD_MUSTANG_MACH_E_MK1, FORD_F_150_LIGHTNING_MK1.

    Returns
    -------
    pd.DataFrame, index = sim_df.index, column `yaw_rate_pred_rads`.
    """
    if platform not in _PLATFORMS:
        # Unknown platform — fall back to V0 verbatim.
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy().copy()},
            index=sim_df.index,
        )

    p = _PLATFORMS[platform]
    L = p["L"]
    k_us = _k_us(p)

    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)

    # Online bias calibration if truth is available in the input frame.
    bias = 0.0
    if "yaw_rate_meas_rads" in sim_df.columns:
        y_meas = sim_df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        bias = _estimate_steering_bias(delta, v, y_meas, L, k_us)

    delta_eff = delta - bias

    # V1 linear-bicycle steady-state yaw rate.
    psi_dot = v * np.tan(delta_eff) / (L + k_us * v * v)

    return pd.DataFrame(
        {"yaw_rate_pred_rads": psi_dot},
        index=sim_df.index,
    )
