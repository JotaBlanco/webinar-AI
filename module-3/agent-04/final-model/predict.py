"""Lateral-fidelity model — Module 3 v2 agent-04.

Architecture (per platform):
  yr_ss(t) = v(t) * g * (delta_road(t) - delta0) / (L_eff + K_us * v(t)^2)
  yr(t)    = first-order lag of yr_ss with time constant tau

Per-segment delta0 estimation (platform-gated) is computed from input
channels only — never from the truth column. The straight-driving gate uses
|yaw_rate_pred_rads| < 0.03 and v_mps > 5.

Tesla: no truth available — passthrough V0.

Coeffs were fit per-platform on data/sim/ with route-grouped train/dev split.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
with (_HERE / "coeffs.json").open("r") as fh:
    PLATFORM_PARAMS: dict = json.load(fh)


def _per_segment_delta0(sim_df, fallback=0.0,
                        yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    """Estimate delta0 from THIS segment's straight-driving rows.

    Uses input channels only. Gate: |yaw_rate_pred_rads| < yr_thresh and
    v_mps > v_thresh. If too few qualifying rows, fall back.
    """
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return float(fallback)
    return float(np.median(sim_df.loc[mask, "delta_road_rad"].to_numpy()))


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Yaw-rate prediction. Returns DataFrame aligned with sim_df.index."""
    # Tesla and any unknown platform: passthrough V0 (no truth to fit).
    if platform not in PLATFORM_PARAMS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )

    p = PLATFORM_PARAMS[platform]
    g = float(p["g"])
    L_eff = float(p["L_eff"])
    K_us = float(p["K_us"])
    tau = float(p["tau"])
    fallback = float(p.get("delta0_fallback", p.get("delta0", 0.0)))

    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=fallback)
    else:
        delta0 = float(p.get("delta0", fallback))

    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * g
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (L_eff + K_us * v * v)

    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    # Safety: clamp dt to a positive small value
    dt = np.where(dt > 0, dt, 0.02)
    alpha = dt / (tau + dt)

    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
