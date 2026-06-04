"""Final-model predict — V2: single-track + understeer + steering-rate lead.

Model per platform:
    yr_pred = v * (delta + tau * d(delta)/dt) / (L_eff + Kus * v^2) + bias

with per-platform coefficients fitted via fit-model on a yaw+CTE blend
objective. Tesla passes through V0 (its truth channel IS V0).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
_COEFFS = json.loads(_COEFFS_PATH.read_text())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)

    coeffs = _COEFFS.get(platform)
    if coeffs is None or "L_eff" not in coeffs:
        # Unknown platform OR Tesla — pass through V0 baseline.
        out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()
        return out

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)
    if len(t) >= 2:
        ddot = np.gradient(d, t)
    else:
        ddot = np.zeros_like(d)
    d_lead = d + coeffs["tau"] * ddot
    denom = coeffs["L_eff"] + coeffs["Kus"] * v * v
    yr = v * d_lead / denom + coeffs["bias"]
    out["yaw_rate_pred_rads"] = yr
    return out
