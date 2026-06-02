"""V2 predict — operating-contract-clean.

V2 = V1 (KS + understeer + first-order lag + per-segment delta0) extended with:
  - per-platform residual bias correction
  - nonlinear understeer term K_us2 * v^2 * delta^2 in the denominator (cubic
    correction to steady-state yaw vs delta)
  - small feedforward correction k_ff * v * d(delta_road)/dt to compensate
    transient steering-lag mismatch.

Tesla has no truth in training data — V0 passthrough is the honest fallback.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_HERE = Path(__file__).resolve().parent
with (_HERE / "coeffs.json").open() as fh:
    PLATFORM_PARAMS = json.load(fh)


def _per_segment_delta0(
    sim_df: pd.DataFrame,
    fallback: float = 0.0,
    yr_thresh: float = 0.03,
    v_thresh: float = 5.0,
    min_rows: int = 50,
) -> float:
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in PLATFORM_PARAMS:
        # Tesla (no truth) or any unknown platform — V0 passthrough.
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = PLATFORM_PARAMS[platform]
    if p["use_per_segment_delta0"]:
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0"]

    delta_road = sim_df["delta_road_rad"].to_numpy()
    delta = (delta_road - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()

    denom = p["L_eff"] + p["K_us"] * v * v + p.get("K_us2", 0.0) * v * v * delta * delta
    # Guard denominator strictly positive
    denom = np.where(denom < 0.1, 0.1, denom)
    yr_ss = v * delta / denom

    dt = np.diff(t, prepend=t[0])
    tau = max(p["tau"], 1e-3)
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])

    k_ff = p.get("k_ff", 0.0)
    if k_ff != 0.0 and len(t) > 1:
        ddelta_dt = np.gradient(delta_road, t)
        yr = yr + k_ff * v * ddelta_dt

    yr = yr + p.get("bias", 0.0)

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
