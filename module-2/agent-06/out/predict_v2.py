"""V2 predict: V1 + steering-rate lead term."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-06")
with open(ROOT / "out" / "coeffs_v2.json") as f:
    COEFFS = json.load(f)


def predict(sim_df, platform):
    if platform == "TESLA_MODEL_3":
        out = sim_df[["yaw_rate_pred_rads"]].copy()
        return out
    c = COEFFS.get(platform)
    if c is None:
        return sim_df[["yaw_rate_pred_rads"]].copy()
    t = sim_df["t_s"].to_numpy()
    d = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    if len(t) >= 2:
        dd = np.gradient(d, t)
    else:
        dd = np.zeros_like(d)
    yr = v * (d + c["tau"] * dd) / (c["L"] + c["Kus"] * v * v) + c["bias"]
    out = pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    return out
