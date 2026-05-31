"""V0 baseline: returns the precomputed yaw_rate_pred_rads (KS model).

Used as the reference for any improvements.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

L_BY_PLATFORM = {
    "TESLA_MODEL_3": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5": 3.0,  # rough guess; only used as fallback
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if "yaw_rate_pred_rads" in sim_df.columns and not sim_df["yaw_rate_pred_rads"].isna().all():
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy(float)},
                            index=sim_df.index)
    # Fallback to KS analytic
    L = L_BY_PLATFORM.get(platform, 2.9)
    v = sim_df["v_mps"].to_numpy(float)
    delta = sim_df["delta_road_rad"].to_numpy(float)
    yr = (v / L) * np.tan(delta)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
