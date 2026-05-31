"""V1 predict: per-platform understeer + bias.

yr = v * (delta_road + bias) / (L_eff + K * v^2)

Falls back to V0 (column or v*d/L0) if platform unknown.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
COEFFS = json.loads((_HERE / "coeffs_v1.json").read_text())

WHEELBASE_M = {
    "TESLA_MODEL_3": 2.875, "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70, "HYUNDAI_IONIQ_5": 3.00,
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v = sim_df["v_mps"].to_numpy(float)
    d = sim_df["delta_road_rad"].to_numpy(float)
    coef = COEFFS.get(platform, {})
    L_eff = coef.get("L_eff")
    K = coef.get("K_u")
    b = coef.get("delta_bias_rad")
    if L_eff is None or K is None or b is None:
        # Fallback: V0
        L = WHEELBASE_M.get(platform, 2.95)
        yr = (v / L) * np.tan(d)
    else:
        denom = L_eff + K * v * v
        yr = v * (d + b) / denom
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
