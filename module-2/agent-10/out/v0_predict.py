"""V0 predict: passes through the precomputed `yaw_rate_pred_rads` baseline."""
from __future__ import annotations
import pandas as pd

def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()
    return out
