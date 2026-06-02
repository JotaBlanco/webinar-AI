"""Final predict for module-4.v2 agent-06.

Approach: V1 (per-segment δ₀ kinematic single-track + understeer + first-order lag)
plus a per-platform additive bias and a small ridge residual-learner head
operating on V1-aware features. Tesla → V0 passthrough (no truth available).

Honours the operating contract — uses ONLY the eight allowlist columns:
  t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
  accel_pedal_pct, brake_pressed, yaw_rate_pred_rads.

Returns a DataFrame aligned with sim_df.index containing yaw_rate_pred_rads.
Optionally adds x_m, y_m integrated from the corrected yaw rate and measured v.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_COEFFS = json.loads((_HERE / "coeffs.json").read_text())

# Pinned V1 parameters (copied from code/v1_baseline.py — keeps the predict
# self-contained and removes the `code/` import dependency).
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


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(sim_df.loc[mask, "delta_road_rad"].to_numpy()))


def _predict_v1(sim_df: pd.DataFrame, platform: str) -> np.ndarray:
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
    dt = np.where(dt <= 0, 1e-3, dt)
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def _features(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    """Build residual-learner features. Drops the intercept column (handled by bias)."""
    v = sim_df["v_mps"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    # Robust gradients
    if len(t) >= 2:
        ddelta = np.gradient(delta, t)
        dyr_v1 = np.gradient(yr_v1, t)
    else:
        ddelta = np.zeros_like(delta)
        dyr_v1 = np.zeros_like(yr_v1)
    a_lat_proxy = v * yr_v1
    feats = np.column_stack([
        v,                                # 1
        delta,                            # 2
        v * delta,                        # 3
        ddelta,                           # 4
        v * ddelta,                       # 5
        yr_v1,                            # 6
        v * yr_v1,                        # 7
        dyr_v1,                           # 8
        a_lat_proxy,                      # 9
        np.sign(delta) * delta * delta,   # 10
    ])
    return feats


def _integrate_xy(t, v, yr):
    n = len(t)
    psi = np.zeros(n)
    x = np.zeros(n)
    y = np.zeros(n)
    if n < 2:
        return x, y
    dt = np.diff(t)
    dt = np.where(dt <= 0, 1e-3, dt)
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    # Tesla and unknown platforms — V0 passthrough.
    if platform not in PLATFORM_PARAMS_V1:
        yr_pt = sim_df["yaw_rate_pred_rads"].to_numpy()
        t = sim_df["t_s"].to_numpy()
        v = sim_df["v_mps"].to_numpy()
        x, y = _integrate_xy(t, v, yr_pt)
        return pd.DataFrame(
            {"yaw_rate_pred_rads": yr_pt, "x_m": x, "y_m": y},
            index=sim_df.index,
        )

    yr_v1 = _predict_v1(sim_df, platform)
    coeffs = _COEFFS.get(platform, {})

    if coeffs.get("passthrough"):
        yr_final = yr_v1
    elif "w" in coeffs:
        bias = float(coeffs["bias"])
        w = np.array(coeffs["w"])
        mu = np.array(coeffs["mu"])
        sd = np.array(coeffs["sd"])
        feats = _features(sim_df, yr_v1)
        Xs = (feats - mu) / sd
        corr = bias + Xs @ w
        # Safety: clip correction to within physical range (yaw-rate residual stays small).
        corr = np.clip(corr, -0.05, 0.05)
        yr_final = yr_v1 + corr
    else:
        yr_final = yr_v1

    t = sim_df["t_s"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    x, y = _integrate_xy(t, v, yr_final)

    return pd.DataFrame(
        {"yaw_rate_pred_rads": yr_final, "x_m": x, "y_m": y},
        index=sim_df.index,
    )
