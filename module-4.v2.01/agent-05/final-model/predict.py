"""Final model — V1 baseline (kinematic + understeer + tau lag + per-segment delta0).

Honest result: I implemented and fit the M4 relaxation-length tire (rung-1
orthogonal) on top of the V1 kinematic core. Per-platform sigma was tuned on
the frozen 402-segment dev split (sigmas: F150=0.30, MachE=0.35, Ioniq5=0.25).

On the SAME apples-to-apples dev scoring, V1 dominates M4:
    V1 : yaw=0.005430 rad/s, cte=52.215 m
    M4 : yaw=0.005610 rad/s, cte=52.100 m       (+3.3% yaw, -0.2% cte)

M4 wins CTE by 0.12 m — within noise — at the cost of 3.3% yaw. That is not
a real win. Per-platform, V1 beats M4 on yaw across all three Ford/Hyundai
platforms. The M4 sigma sweep (sigma in {0, 0.1, 0.3, 1.0}) confirms no
sigma setting beats V1 on yaw. Conclusion: relaxation-length is NOT the right
mechanism here; the prior agent's claim of an M4 win was against a stale V1
metric (manifest cited 0.005706, actual on this split 0.005430).

So we ship V1. The rung-1 climb was attempted and logged honestly as shelved
in MODELS.md. The dynamics ladder (M1/M2/M3/M5) was not fit due to budget
exhaustion in the prior session — those candidates remain `drafting`.

V1 coefficients come from m3.v3 converged values. Tesla passes through V0.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent

PLATFORM_PARAMS_V1 = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False,
        "delta0": 0.00133,
        "g": 0.863,
        "L_eff": 3.26,
        "K_us": 0.00350,
        "tau": 0.060,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True,
        "delta0_fallback": -0.0001,
        "g": 0.891,
        "L_eff": 2.22,
        "K_us": 0.00150,
        "tau": 0.069,
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True,
        "delta0_fallback": 0.0,
        "g": 0.938,
        "L_eff": 2.887,
        "K_us": 0.00289,
        "tau": 0.062,
    },
}


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
    """Operating-contract entry point.

    sim_df has the canonical 8-column allowlist (t_s, delta_wheel_deg,
    delta_road_rad, v_mps, a_long_mps2, accel_pedal_pct, brake_pressed,
    yaw_rate_pred_rads). Returns a DataFrame aligned with sim_df.index
    containing yaw_rate_pred_rads. No truth columns are read.
    """
    if platform not in PLATFORM_PARAMS_V1:
        # Tesla and any unknown platform pass V0 through.
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = PLATFORM_PARAMS_V1[platform]
    delta0 = (
        _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
        if p["use_per_segment_delta0"]
        else p["delta0"]
    )
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt[dt <= 0] = 1e-3
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
