"""V0 baseline predict — just returns the precomputed yaw_rate_pred_rads."""
import pandas as pd


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()
    return out
