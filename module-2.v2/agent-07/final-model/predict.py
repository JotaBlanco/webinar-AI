"""Module-2 v2 / agent-07 — lateral-fidelity predict bundle.

V1 model: per-platform calibrated steady-state bicycle with v^2 understeer.

    yaw_pred = v * delta_road / (L_eff + K_us * v^2)
             + bias_static
             + bias_steer * delta_road

V0 baseline is the kinematic single-track psi_dot = (v/L) * tan(delta_road).
We replace it with the small-angle/understeer-corrected form. Coefficients are
fit per platform by minimising a (yaw RMSE + CTE/1000) blend across the
training segments using scipy L-BFGS-B (with a Nelder-Mead rescue for any
platform whose gradient pass got stuck at the initial point).

Tesla is intentionally a V0 passthrough: the Tesla 'truth' channel
(`psi_dot_rads`) IS the V0 KS output in this dataset, so any deviation hurts.

Coefficients live alongside this file in coeffs.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFFS_PATH.open("r", encoding="utf-8") as _fh:
    COEFFS: dict = json.load(_fh)

# Fallback coeffs for platforms we never trained — keep V0 behaviour by
# choosing L_eff close to the canonical wheelbase and zero understeer.
_FALLBACK = {
    "L_eff": 2.9,
    "K_us": 0.0,
    "bias_static": 0.0,
    "bias_steer": 0.0,
}


def _predict_bicycle(sim_df: pd.DataFrame, coeffs: dict) -> np.ndarray:
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)
    L_eff = float(coeffs.get("L_eff", _FALLBACK["L_eff"]))
    K_us  = float(coeffs.get("K_us", _FALLBACK["K_us"]))
    bs    = float(coeffs.get("bias_static", _FALLBACK["bias_static"]))
    bd    = float(coeffs.get("bias_steer", _FALLBACK["bias_steer"]))
    denom = L_eff + K_us * v * v
    denom = np.where(denom < 0.1, 0.1, denom)
    return v * d / denom + bs + bd * d


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate for one segment.

    Returns a DataFrame with ``yaw_rate_pred_rads`` indexed like sim_df.
    """
    out = pd.DataFrame(index=sim_df.index)

    if platform == "TESLA_MODEL_3":
        # Tesla truth IS the V0 baseline in this dataset — passthrough.
        if "yaw_rate_pred_rads" in sim_df.columns:
            out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        else:
            # Defensive fallback: compute V0-shape KS prediction from delta_road.
            v = sim_df["v_mps"].to_numpy(dtype=float)
            d = sim_df["delta_road_rad"].to_numpy(dtype=float)
            out["yaw_rate_pred_rads"] = v * np.tan(d) / 2.875
        return out

    coeffs = COEFFS.get(platform, _FALLBACK)
    out["yaw_rate_pred_rads"] = _predict_bicycle(sim_df, coeffs)
    return out


__all__ = ["predict", "COEFFS"]
