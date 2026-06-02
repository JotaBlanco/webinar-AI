"""Final model: V1 baseline + per-platform low-rank bias correction.

Strategy chosen from m4 cohort findings §0/§2/§4 and local k-fold route-grouped
CV on data/sim/segments:
  - FORD_MUSTANG_MACH_E_MK1: scale+bias affine on V1 yaw (a=+1.696e-3, b=0.97463)
    -> yaw -0.79%, CTE -6.94%
  - HYUNDAI_IONIQ_5: linear-in-velocity bias added to V1 yaw
    (b(v) = 0.000223 + 2.79e-5 * v)  -> yaw -0.28%, CTE -3.23%
  - FORD_F_150_LIGHTNING_MK1: scale-only on V1 (s=0.98734)
    -> yaw -0.10%, CTE -0.41% (cohort §5: noise floor; bias hurts)
  - TESLA_MODEL_3: V0 passthrough (no truth channel; cohort/baseline guidance)

Anything heavier (full ridge head with delta, v, delta*v features) regressed CTE
on Mach-E and IONIQ-5 in CV — the residual structure on this dataset is dominated
by a near-constant signed-bias + a small scale, with the rest below noise.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

# Inline V1 baseline so this predict module is fully self-contained for grading.
_V1_PARAMS = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False, "delta0": 0.00133, "g": 0.863,
        "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True, "delta0_fallback": -0.0001, "g": 0.891,
        "L_eff": 2.22, "K_us": 0.00150, "tau": 0.069,
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True, "delta0_fallback": 0.0, "g": 0.938,
        "L_eff": 2.887, "K_us": 0.00289, "tau": 0.062,
    },
}

# Per-platform correction coefficients (fitted on data/sim/segments with k=5
# route-grouped CV, then refit on full data; see notes.md).
CORRECTIONS = {
    "FORD_MUSTANG_MACH_E_MK1": {"kind": "scale_bias", "a": 0.001696, "b": 0.97463},
    "HYUNDAI_IONIQ_5":         {"kind": "linbias",    "c0": 0.00022308460801747, "c1": 2.7894952461816927e-05},
    "FORD_F_150_LIGHTNING_MK1":{"kind": "scale",      "scale": 0.98734},
    "TESLA_MODEL_3":           {"kind": "passthrough"},
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
    if platform not in _V1_PARAMS:
        return sim_df["yaw_rate_pred_rads"].to_numpy()
    p = _V1_PARAMS[platform]
    delta0 = (_per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
              if p["use_per_segment_delta0"] else p["delta0"])
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


def _apply_correction(yr_v1: np.ndarray, v: np.ndarray, platform: str) -> np.ndarray:
    c = CORRECTIONS.get(platform, {"kind": "passthrough"})
    kind = c["kind"]
    if kind == "passthrough":
        return yr_v1
    if kind == "scale":
        return c["scale"] * yr_v1
    if kind == "scale_bias":
        return c["a"] + c["b"] * yr_v1
    if kind == "linbias":
        return yr_v1 + c["c0"] + c["c1"] * v
    return yr_v1


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(t)
    if n < 2:
        return np.zeros(n), np.zeros(n)
    dt = np.diff(t)
    psi = np.empty(n); psi[0] = 0.0
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x = np.empty(n); x[0] = 0.0
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y = np.empty(n); y[0] = 0.0
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return DataFrame aligned with sim_df.index containing yaw_rate_pred_rads, x_m, y_m."""
    yr_v1 = _predict_v1(sim_df, platform)
    v = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    yr_post = _apply_correction(yr_v1, v, platform)
    x, y = _integrate_xy(t, v, yr_post)
    return pd.DataFrame(
        {"yaw_rate_pred_rads": yr_post, "x_m": x, "y_m": y},
        index=sim_df.index,
    )
