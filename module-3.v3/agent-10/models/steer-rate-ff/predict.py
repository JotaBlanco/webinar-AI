"""V1 + steering-rate feedforward.

Structurally different from V1: V1 is steady-state + first-order lag (one pole).
This model adds a *feedforward* zero — an explicit kick proportional to d(delta)/dt
to model the lead the lag is band-aiding. Equivalent in shape to going from a
first-order to a lead-lag transfer function on the steering channel.

   yr = yr_v1(t) + k_ff(platform) * v(t) * d(delta_road)/dt(t)

The per-platform k_ff is fit by least-squares on the V1 residual against the
feedforward feature alone (one parameter; can't overfit). This is a
**structure: differs-from-v1** model because V1 has no derivative term in its
transfer function — the residual diagnosis on Mach-E points exactly at this
shape (transient regime carries 16% of residual yaw RMSE at 0.0165 vs straight's
0.0044).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "code"))
from v1_baseline import predict_v1  # noqa: E402


with (HERE / "coeffs.json").open() as fh:
    COEFFS = json.load(fh)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v1 = predict_v1(sim_df, platform)
    yr = v1["yaw_rate_pred_rads"].to_numpy().copy()
    if platform not in COEFFS:
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    k_ff = COEFFS[platform]["k_ff"]
    bias = COEFFS[platform].get("bias", 0.0)
    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    if len(t) > 1:
        d_delta = np.gradient(delta, t)
    else:
        d_delta = np.zeros_like(delta)
    yr_corr = yr + k_ff * v * d_delta + bias
    return pd.DataFrame({"yaw_rate_pred_rads": yr_corr}, index=sim_df.index)
