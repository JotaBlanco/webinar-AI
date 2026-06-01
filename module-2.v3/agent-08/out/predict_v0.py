"""V0 baseline predict - returns yaw_rate_pred_rads unchanged."""
import pandas as pd


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                        index=sim_df.index)
