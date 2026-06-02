"""Final model: V3 = refitted V1 coefficients + per-platform additive residual correction.

predict(sim_df, platform) -> DataFrame aligned with sim_df.index with column
`yaw_rate_pred_rads`. Optional x_m, y_m omitted — grader integrates from
yaw_rate_pred_rads + v_mps.

Structure:
  yr_v1_shape = first-order lag of (v * (delta - delta0) * g / (L_eff + K_us v^2))
  yr_final    = yr_v1_shape + a_ay * (v * yr_v1_shape) + b
  with platform-specific (g, L_eff, K_us, tau, delta0/fallback, a_ay, b).
  Tesla -> V0 passthrough (no truth, fitting hurts).

Coeffs from v2_coeffs.json and v3_correction.json (sit next to this file).
Honours the operating-contract allowlist: reads only t_s, delta_road_rad,
v_mps, yaw_rate_pred_rads.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
COEFFS = json.loads((_HERE / "v2_coeffs.json").read_text())
CORR   = json.loads((_HERE / "v3_correction.json").read_text())


def _per_segment_delta0(sim_df: pd.DataFrame, fallback: float = 0.0,
                        yr_thresh: float = 0.03, v_thresh: float = 5.0,
                        min_rows: int = 50) -> float:
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in COEFFS:
        # Tesla and any unknown platform: V0 passthrough
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = COEFFS[platform]
    if p["use_per_segment_delta0"]:
        d0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        d0 = p["delta0"]
    v  = sim_df["v_mps"].to_numpy()
    dr = sim_df["delta_road_rad"].to_numpy()
    t  = sim_df["t_s"].to_numpy()
    delta = (dr - d0) * p["g"]
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    # Per-platform residual correction
    c = CORR.get(platform)
    if c is not None:
        yr = yr + c["a_ay"] * (v * yr) + c["b"]
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
