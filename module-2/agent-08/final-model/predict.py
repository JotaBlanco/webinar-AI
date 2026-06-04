"""Final-model predict — V2 (understeer + steering-rate lead/lag + bias).

Model:
    delta_eff = delta_road + tau * d(delta_road)/dt
    yaw_rate_pred = v * delta_eff / (L + K_us * v^2) + bias

Per-platform coeffs in coeffs.json. Tesla is passed-through (its truth IS V0).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_COEFFS: dict | None = None


def _load_coeffs() -> dict:
    global _COEFFS
    if _COEFFS is None:
        with (_HERE / "coeffs.json").open() as fh:
            _COEFFS = json.load(fh)
    return _COEFFS


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """V2 yaw-rate prediction. Returns DataFrame aligned with sim_df.index."""
    coeffs = _load_coeffs()

    if platform not in coeffs:
        # Tesla and any unfitted platform: pass V0 through unchanged.
        if "yaw_rate_pred_rads" in sim_df.columns:
            return pd.DataFrame(
                {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                index=sim_df.index,
            )
        # Fallback: zero
        return pd.DataFrame(
            {"yaw_rate_pred_rads": np.zeros(len(sim_df))},
            index=sim_df.index,
        )

    c = coeffs[platform]
    L = float(c["L"])
    K_us = float(c["K_us"])
    tau = float(c["tau"])
    bias = float(c["bias"])

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)

    if len(t) >= 2:
        ddelta = np.gradient(delta, t)
    else:
        ddelta = np.zeros_like(delta)

    delta_eff = delta + tau * ddelta
    yr = v * delta_eff / (L + K_us * v * v) + bias

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
