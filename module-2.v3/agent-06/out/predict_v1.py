"""V1 predict: per-platform refit of v*delta/(L + Kus*v^2) + bias."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-06")
with open(ROOT / "out" / "coeffs_v1.json") as f:
    COEFFS = json.load(f)


def predict(sim_df, platform):
    if platform == "TESLA_MODEL_3":
        # V0 is the truth; passthrough.
        out = sim_df[["yaw_rate_pred_rads"]].copy()
        return out
    c = COEFFS.get(platform)
    if c is None:
        return sim_df[["yaw_rate_pred_rads"]].copy()
    d = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    yr = v * d / (c["L"] + c["Kus"] * v * v) + c["bias"]
    out = pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    return out
