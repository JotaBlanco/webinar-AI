"""Final predict for module-3.v2 agent-09.

Recipe: Kinematic single-track + understeer + first-order yaw lag, with
platform-gated per-segment δ₀ estimation from input-only straight-driving rows.

Per-platform coefficients in `coeffs.json`. Tesla falls back to V0 passthrough
(no truth channel).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
with open(_HERE / "coeffs.json") as f:
    _COEFFS = json.load(f)


def _per_segment_delta0(sim_df, fallback=0.0,
                        yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    """Estimate δ₀ from THIS segment's own straight-driving rows.

    Uses input-only allowlist channels: V0 yaw-rate prediction as the
    straight-driving gate.
    """
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _predict_yaw(sim_df, p):
    """Compute yaw rate given platform params p (dict)."""
    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0"]
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    L_eff = p["L_eff"]
    K_us = p["K_us"]
    tau = p["tau"]
    yr_ss = v * delta / (L_eff + K_us * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in _COEFFS:
        # Tesla and any unknown platform → V0 passthrough.
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = _COEFFS[platform]
    yr = _predict_yaw(sim_df, p)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
