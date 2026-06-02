"""Final model — V1 baseline + per-platform bias correction + ridge residual-learner head.

Strategy (cohort-evidenced, m4-cohort-findings §2 + §4):
  1. Run V1 baseline (kinematic single-track + understeer + lag).
  2. Subtract per-platform signed yaw bias (Mach-E and IONIQ-5 carry persistent biases;
     Lightning is near noise floor).
  3. Add ridge residual-learner head on top of V1 residual, using only allowlist-derived
     features. Ridge lambda was picked per-platform on a held-out 20% segment-hashed dev split.

Only the 8 allowlist columns are read. Tesla falls through to V0 (no truth channel).
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_COEFFS = json.loads((_HERE / "coeffs.json").read_text())
_FEATURE_NAMES = _COEFFS["feature_names"]
_PLATFORMS = _COEFFS["platforms"]

# V1 baseline parameters — inlined here so predict has no cross-tree imports at grading time.
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


def _v1_predict(sim_df: pd.DataFrame, platform: str) -> np.ndarray:
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


def _build_features(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    t = sim_df["t_s"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    a_long = sim_df["a_long_mps2"].to_numpy() if "a_long_mps2" in sim_df.columns else np.zeros_like(v)
    brake = sim_df["brake_pressed"].to_numpy().astype(float) if "brake_pressed" in sim_df.columns else np.zeros_like(v)
    accel = (sim_df["accel_pedal_pct"].to_numpy() / 100.0) if "accel_pedal_pct" in sim_df.columns else np.zeros_like(v)
    a_lat_proxy = v * yr_v1
    dd = np.gradient(delta, t)
    ydot = np.gradient(yr_v1, t)
    feats = np.column_stack([
        yr_v1,
        np.abs(yr_v1),
        a_lat_proxy,
        delta,
        np.abs(delta),
        dd,
        np.abs(dd),
        v,
        v * delta,
        v * yr_v1,
        a_long,
        brake,
        accel,
        ydot,
    ])
    return np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    yr_v1 = _v1_predict(sim_df, platform)
    if platform not in _PLATFORMS:
        return pd.DataFrame({"yaw_rate_pred_rads": yr_v1}, index=sim_df.index)

    p = _PLATFORMS[platform]
    bias = float(p["bias"])
    # Residual sign convention: training computed `truth - v1`. Mean is `bias`.
    # So corrected prediction = v1 + bias.
    yr_corr = yr_v1 + bias

    # Apply ridge head ONLY if it improved dev resid RMSE over bias-only.
    use_ridge = float(p["dev_resid_rmse_ridge"]) < float(p["dev_resid_rmse_bias_only"]) - 1e-7
    if use_ridge:
        X = _build_features(sim_df, yr_v1)
        mu = np.asarray(p["feature_mu"])
        sd = np.asarray(p["feature_sd"])
        Z = (X - mu) / sd
        w = np.asarray(p["ridge_w"])
        dyr = Z @ w
        yr_corr = yr_corr + dyr

    return pd.DataFrame({"yaw_rate_pred_rads": yr_corr}, index=sim_df.index)
