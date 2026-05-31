"""Lateral-fidelity model — steady-state single-track with per-platform fit.

Model (per platform):
    yaw_rate = v * tan(gain * delta_road + delta0) / (L_eff + K * v^2)

Coefficients learned offline on route-grouped train split of data/sim/segments;
see out/fit_coeffs.py for the fit code and out/coeffs.json for the full result.

Contract:
    predict(sim_df, platform) -> DataFrame indexed like sim_df with at least
        yaw_rate_pred_rads column. We do not emit x_m/y_m — the grader will
        integrate from yaw_rate + measured v.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFFS_PATH.open() as fh:
    _COEFFS_BLOB = json.load(fh)
_COEFFS = _COEFFS_BLOB["coeffs"]


# Fallback (kinematic single-track with workshop wheelbases) for any unknown
# platform — keeps us at V0 quality rather than crashing.
_FALLBACK_L = {
    "TESLA_MODEL_3": 2.875,
    "HYUNDAI_IONIQ_5": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}


def _predict_yaw(delta_road: np.ndarray, v: np.ndarray, platform: str) -> np.ndarray:
    c = _COEFFS.get(platform)
    if c is None:
        L = _FALLBACK_L.get(platform, 2.875)
        return (v / L) * np.tan(delta_road)
    L, K, d0, g = c["L"], c["K"], c["delta0"], c["gain"]
    denom = np.maximum(L + K * v * v, 0.1)
    return (v * np.tan(g * delta_road + d0)) / denom


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return yaw_rate_pred_rads aligned with sim_df.index.

    Reads only sim-only-contract columns: delta_road_rad, v_mps.
    """
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    yr = _predict_yaw(delta, v, platform)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
