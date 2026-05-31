"""V2 predict: V1 + first-order lag on the steering channel.

yr = v * (delta_lag + bias) / (L_eff + K * v^2)
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
COEFFS = json.loads((_HERE / "coeffs_v2.json").read_text())

WHEELBASE_M = {
    "TESLA_MODEL_3": 2.875, "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70, "HYUNDAI_IONIQ_5": 3.00,
}


def _lag(delta: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 1e-6 or len(delta) < 2:
        return delta.astype(float).copy()
    dt = np.diff(t, prepend=t[0])
    out = np.empty_like(delta, dtype=float)
    out[0] = delta[0]
    for i in range(1, len(delta)):
        a = dt[i] / (tau + dt[i])
        out[i] = (1 - a) * out[i-1] + a * delta[i]
    return out


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v = sim_df["v_mps"].to_numpy(float)
    d = sim_df["delta_road_rad"].to_numpy(float)
    t = sim_df["t_s"].to_numpy(float)
    coef = COEFFS.get(platform)
    if coef is None:
        L = WHEELBASE_M.get(platform, 2.95)
        yr = (v / L) * np.tan(d)
    else:
        d_lag = _lag(d, t, coef["tau"])
        denom = coef["L_eff"] + coef["K_u"] * v * v
        yr = v * (d_lag + coef["delta_bias_rad"]) / denom
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
