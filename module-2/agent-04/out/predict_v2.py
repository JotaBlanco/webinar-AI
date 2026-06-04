"""V2 predict — V1 + steering-rate lead/lag term."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

COEFFS_PATH = Path(__file__).resolve().parent / "coeffs_v2.json"
_COEFFS = json.loads(COEFFS_PATH.read_text())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    if platform == "TESLA_MODEL_3" or platform not in _COEFFS or "L_eff" not in _COEFFS.get(platform, {}):
        out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()
        return out

    c = _COEFFS[platform]
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)
    ddot = np.gradient(d, t)
    d_lead = d + c["tau"] * ddot
    denom = c["L_eff"] + c["Kus"] * v * v
    yr = v * d_lead / denom + c["bias"]
    out["yaw_rate_pred_rads"] = yr
    return out
