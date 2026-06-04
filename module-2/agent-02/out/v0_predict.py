"""V0 baseline replicator: just return the pre-computed yaw_rate_pred_rads."""
from __future__ import annotations
import pandas as pd


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    yr = sim_df["yaw_rate_pred_rads"].to_numpy()
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
