"""V1/V2 predict: kinematic bicycle with per-platform understeer + optional steering-rate lead."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent

def _load(name: str) -> dict:
    return json.loads((ROOT / name).read_text())

COEFFS_V1 = _load("coeffs_v1.json")
COEFFS_V2 = _load("coeffs_v2.json")
COEFFS_V3 = _load("coeffs_v3.json")


def _build_predict(coeff_table):
    def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        out = pd.DataFrame(index=sim_df.index)
        coef = coeff_table.get(platform)
        if not coef or coef.get("passthrough"):
            out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()
            return out
        t = sim_df["t_s"].to_numpy(float)
        d = sim_df["delta_road_rad"].to_numpy(float)
        v = sim_df["v_mps"].to_numpy(float)
        if len(t) >= 2 and np.all(np.diff(t) > 0):
            ddot = np.gradient(d, t)
        else:
            ddot = np.zeros_like(d)
        s_d  = coef["s_d"]
        c_d  = coef.get("c_d", 0.0)
        tau_d = coef.get("tau_d", 0.0)
        K_us = coef["K_us"]
        b    = coef.get("b", 0.0)
        L    = coef["L"]
        denom = L + K_us * v * v
        yr = v * (s_d * d + c_d * d**3 + tau_d * ddot) / denom + b
        out["yaw_rate_pred_rads"] = yr
        return out
    return predict


predict_v1 = _build_predict(COEFFS_V1)
predict_v2 = _build_predict(COEFFS_V2)
predict_v3 = _build_predict(COEFFS_V3)

# Default exported predict is V3.
def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return predict_v3(sim_df, platform)
