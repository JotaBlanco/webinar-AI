"""Final model — KS + per-platform understeer + first-order lag
+ platform-gated per-segment delta0 (input-only straight-row gate).

Shape:
    delta_eff = (delta_road_rad - delta0) * g
    yr_ss     = v * delta_eff / (L_eff + K_us * v^2)      (linear understeer)
    yr        = first-order lag, alpha = dt / (tau + dt)

delta0 is estimated per-segment from straight-driving rows (yaw-rate gate)
for Mach-E and IONIQ-5; Lightning uses a fixed global delta0. Tesla passes
V0 through (no truth channel to fit against).

Coefficients live in `coeffs.json` next to this file.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd


_COEFFS_CACHE = None


def _load_coeffs():
    global _COEFFS_CACHE
    if _COEFFS_CACHE is None:
        with open(Path(__file__).parent / "coeffs.json") as f:
            _COEFFS_CACHE = json.load(f)
    return _COEFFS_CACHE


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03,
                        v_thresh=5.0, min_rows=50):
    """Estimate δ₀ from this segment's straight-driving rows. Allowlist-only:
    uses `yaw_rate_pred_rads` (V0 baseline) as the straight-driving gate.
    """
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df, platform):
    params = _load_coeffs()
    if platform not in params:
        # Tesla and any unknown platform — passthrough.
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = params[platform]
    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=p.get("delta0_fallback", 0.0))
    else:
        delta0 = p["delta0"]
    delta_r = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    delta = (delta_r - delta0) * p["g"]
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    tau = p["tau"]
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
