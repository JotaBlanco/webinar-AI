"""Final-model predict() — V1 lateral fidelity (single-track + understeer + steering-rate lead).

Per-platform parameterised model:

    delta_eff = delta_road + tau * d(delta_road)/dt        # steering-rate lead
    yaw_pred  = gain * v * delta_eff / (L_eff + K_us * v^2) + bias

Coefficients are loaded from sibling coeffs.json. For TESLA_MODEL_3 the model is a
pass-through to the V0 baseline `yaw_rate_pred_rads` column (Tesla sim has no
independent truth channel — V0 IS the truth — so deviating from V0 strictly
increases RMSE).

Optional `x_m, y_m` are integrated by the scorer using the predicted yaw_rate and
the measured v_mps, so we don't emit trajectory columns ourselves.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd


_HERE = Path(__file__).resolve().parent
with open(_HERE / "coeffs.json") as _fh:
    _COEFFS = json.load(_fh)["coeffs"]


def _predict_yaw(sim_df: pd.DataFrame, coeffs: dict) -> np.ndarray:
    t      = sim_df["t_s"].to_numpy(dtype=float)
    v      = sim_df["v_mps"].to_numpy(dtype=float)
    delta  = sim_df["delta_road_rad"].to_numpy(dtype=float)

    L_eff = float(coeffs.get("L_eff", 2.9))
    K_us  = float(coeffs.get("K_us",  0.0))
    gain  = float(coeffs.get("gain",  1.0))
    bias  = float(coeffs.get("bias",  0.0))
    tau   = float(coeffs.get("tau",   0.0))

    if abs(tau) > 1e-12 and len(t) >= 2:
        ddelta_dt = np.gradient(delta, t)
        delta_eff = delta + tau * ddelta_dt
    else:
        delta_eff = delta

    denom = L_eff + K_us * v * v
    return gain * v * delta_eff / denom + bias


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned with sim_df.index containing yaw_rate_pred_rads.

    Tesla: pass-through V0 (no independent truth). All other platforms: V1 model.
    """
    if platform == "TESLA_MODEL_3":
        yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    else:
        coeffs = _COEFFS.get(platform)
        if coeffs is None:
            # Unknown platform — fall back to the V0 baseline if available.
            if "yaw_rate_pred_rads" in sim_df.columns:
                yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
            else:
                yr = np.zeros(len(sim_df), dtype=float)
        else:
            yr = _predict_yaw(sim_df, coeffs)

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
