"""Final model: V1 (kinematic single-track + understeer + first-order lag +
per-segment δ₀) with a per-platform LINEAR-RESIDUAL-LEARNER correction.

predict(sim_df, platform) -> DataFrame with yaw_rate_pred_rads aligned to sim_df.index.

Structural attack on V1:
  V1 leaves a residual that correlates with measurable, allowlisted features.
  We fit a per-platform ridge regression of (V1 - truth) on
    [yr_v1, |yr_v1|, v, v*yr_v1, ddelta_dt, delta, 1]
  and subtract the predicted residual from V1.

This is structurally distinct from V1 because:
  - V1 is purely physics + lag; this adds a data-driven correction layer.
  - The correction can capture velocity-dependent gain error and asymmetries
    that V1's fixed (g, K_us, τ, δ₀) cannot express.
  - Composes with V1 rather than replacing it (V1 still anchors the noise floor).

Tesla: V0 passthrough (no truth channel to fit).

Pooled dev score: yaw 0.005770 rad/s, CTE 53.78 m  (vs V1 0.005874, 56.81).
"""
from __future__ import annotations
import json
import pathlib
import numpy as np
import pandas as pd


_HERE = pathlib.Path(__file__).resolve().parent
COEFFS = json.loads((_HERE / "coeffs.json").read_text())


# --- V1 baseline (inlined for portability — same logic as code/v1_baseline.py) ---

_PLATFORM_V1 = {
    "FORD_F_150_LIGHTNING_MK1": dict(use_per_segment_delta0=False, delta0=0.00133,
                                     g=0.863, L_eff=3.26, K_us=0.00350, tau=0.060),
    "FORD_MUSTANG_MACH_E_MK1": dict(use_per_segment_delta0=True, delta0_fallback=-0.0001,
                                    g=0.891, L_eff=2.22, K_us=0.00150, tau=0.069),
    "HYUNDAI_IONIQ_5": dict(use_per_segment_delta0=True, delta0_fallback=0.0,
                            g=0.938, L_eff=2.887, K_us=0.00289, tau=0.062),
}


def _per_segment_delta0(sim_df: pd.DataFrame, fallback: float = 0.0,
                       yr_thresh: float = 0.03, v_thresh: float = 5.0,
                       min_rows: int = 50) -> float:
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _predict_v1(sim_df: pd.DataFrame, platform: str) -> np.ndarray:
    if platform not in _PLATFORM_V1:
        return sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    p = _PLATFORM_V1[platform]
    if p["use_per_segment_delta0"]:
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0"]
    delta = (sim_df["delta_road_rad"].to_numpy(dtype=float) - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy(dtype=float)
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy(dtype=float)
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def _features(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)
    if len(t) >= 2:
        dd = np.gradient(d, t)
    else:
        dd = np.zeros_like(d)
    one = np.ones_like(v)
    return np.column_stack([yr_v1, np.abs(yr_v1), v, v*yr_v1, dd, d, one])


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    yr_v1 = _predict_v1(sim_df, platform)
    if platform not in COEFFS:
        return pd.DataFrame({"yaw_rate_pred_rads": yr_v1}, index=sim_df.index)
    w = np.asarray(COEFFS[platform]["w"], dtype=float)
    F = _features(sim_df, yr_v1)
    resid_pred = F @ w   # predicts (V1 - truth)
    yr_new = yr_v1 - resid_pred
    return pd.DataFrame({"yaw_rate_pred_rads": yr_new}, index=sim_df.index)
