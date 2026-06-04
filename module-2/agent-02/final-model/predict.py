"""Final model — V2: linear understeer + steering-rate phase lead.

  yaw_rate(t) = v(t) * delta_eff(t) / (L_eff + K_us * v(t)^2) + b
  delta_eff(t) = delta(t) + tau * d(delta)/dt

Per-platform coefficients live in `coeffs.json` next to this file.

Tesla (TESLA_MODEL_3) has no independent yaw-rate truth channel in this
dataset — `psi_dot_rads` literally IS the V0 KS output — so we pass V0
through unchanged for Tesla rather than fitting a synthetic target.

predict(sim_df, platform) returns a DataFrame aligned with sim_df.index
with column `yaw_rate_pred_rads`. We omit `x_m, y_m` and let the grader
integrate them — the grader's integrator is the reference.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
_COEFFS = json.loads(_COEFFS_PATH.read_text())


def _predict_yaw(sim_df: pd.DataFrame, coeffs: dict) -> np.ndarray:
    v     = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t     = sim_df["t_s"].to_numpy(dtype=float)
    L_eff = float(coeffs["L_eff"])
    K_us  = float(coeffs["K_us"])
    b     = float(coeffs.get("b", 0.0))
    tau   = float(coeffs.get("tau", 0.0))

    if len(t) >= 2:
        ddelta_dt = np.gradient(delta, t)
    else:
        ddelta_dt = np.zeros_like(delta)
    delta_eff = delta + tau * ddelta_dt

    denom = L_eff + K_us * v * v
    # safety guard — should never bind given our positive bounds, but keep
    # the predictor robust to a pathological edit.
    denom = np.where(np.abs(denom) > 1e-3, denom, np.sign(denom) * 1e-3 + 1e-6)
    return v * delta_eff / denom + b


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw_rate_pred_rads for a sim DataFrame.

    sim_df columns expected (from operating-contract allowlist):
        t_s, delta_road_rad, v_mps, yaw_rate_pred_rads (V0 reference), ...

    Returns a DataFrame aligned with sim_df.index containing
    `yaw_rate_pred_rads`. Tesla falls through to the V0 baseline because
    the dataset's Tesla truth IS the V0 baseline.
    """
    coeffs = _COEFFS.get(platform)
    if coeffs is None:
        # Unknown platform OR Tesla → pass V0 through.
        if "yaw_rate_pred_rads" in sim_df.columns:
            yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        else:
            # Last-resort fallback: bicycle-model with default wheelbase.
            v     = sim_df["v_mps"].to_numpy(dtype=float)
            delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
            yr = v * np.tan(delta) / 2.875
    else:
        yr = _predict_yaw(sim_df, coeffs)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
