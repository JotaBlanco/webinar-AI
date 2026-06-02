"""V2 = V1 baseline + per-platform ridge residual learner.

Strategy (cohort §2 + §4):
- V1 (kinematic single-track + understeer + first-order lag + per-segment δ₀) is the floor.
- On top, a per-platform 11-feature ridge regression that learned the V1 residual
  from training data. Features are built from the 8-column allowlist + V1's own
  output (used as a feature), so the operating contract is honoured.
- Tesla → V0 passthrough (no truth; honest fallback).

Coefficients are baked-in (loaded from ridge_coeffs.json at module import).
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

# Mirror V1 baseline locally so we don't depend on `code/` at grading time
# (code/ should be available but better to be self-contained).
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
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _predict_v1(sim_df: pd.DataFrame, platform: str) -> np.ndarray:
    if platform not in PLATFORM_PARAMS_V1:
        return sim_df["yaw_rate_pred_rads"].to_numpy()
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
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


# Load coefficients once at module import.
_HERE = Path(__file__).parent
_COEFFS_PATH = _HERE / "ridge_coeffs.json"
with _COEFFS_PATH.open() as f:
    _COEFFS = json.load(f)


def _build_features(sim_df: pd.DataFrame, v1_yaw: np.ndarray) -> np.ndarray:
    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    a_long = sim_df["a_long_mps2"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt[dt <= 0] = 1e-3
    delta_dot = np.diff(delta, prepend=delta[0]) / dt
    win = 5
    if len(delta_dot) >= win:
        delta_dot = pd.Series(delta_dot).rolling(win, center=True, min_periods=1).mean().to_numpy()
    v2 = v * v
    feats = np.column_stack([
        np.ones_like(v),
        delta,
        v,
        v2,
        delta * v,
        delta * v2,
        v1_yaw,
        v1_yaw * v,
        a_long,
        delta_dot,
        delta_dot * v,
    ])
    return feats


def _residual_correction(sim_df: pd.DataFrame, v1_yaw: np.ndarray, platform: str) -> np.ndarray:
    if platform not in _COEFFS:
        return np.zeros_like(v1_yaw)
    cfg = _COEFFS[platform]
    w = np.array(cfg["w"])
    mu = np.array(cfg["mu"])
    sd = np.array(cfg["sd"])
    X = _build_features(sim_df, v1_yaw)
    Xs = (X - mu) / sd
    corr = Xs @ w
    # Clip extreme corrections to avoid pathological extrapolations.
    corr = np.clip(corr, -0.05, 0.05)
    # Per-segment partial demean over high-speed samples.
    # The ridge correction reduces high-frequency yaw error, but its slow drift
    # is poison for CTE. Removing 70% of the segment-mean correction (alpha=0.7)
    # kills most of the integrated drift while preserving useful low-freq signal.
    # alpha=0.7 chosen by dev-set sweep.
    alpha = 0.7
    v = sim_df["v_mps"].to_numpy()
    mask = v > 5.0
    if mask.sum() > 50:
        m = float(corr[mask].mean())
    else:
        m = float(corr.mean())
    corr = corr - alpha * m
    return corr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Operating-contract-compliant predict.

    Inputs (sim_df must have these 8 columns):
        t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
        accel_pedal_pct, brake_pressed, yaw_rate_pred_rads
    Returns DataFrame with 'yaw_rate_pred_rads' aligned to sim_df.index.
    """
    if platform == "TESLA_MODEL_3" or platform not in PLATFORM_PARAMS_V1:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    v1 = _predict_v1(sim_df, platform)
    corr = _residual_correction(sim_df, v1, platform)
    yr = v1 + corr
    # Gate at very low speed: V1 is more trustworthy there.
    v = sim_df["v_mps"].to_numpy()
    low = v < 3.0
    yr[low] = v1[low]
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
