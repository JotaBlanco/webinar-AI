"""V1 lateral-fidelity predict.

Model shape (per-platform fitted):
  delta'   = (delta_road_rad - delta0) * g
  yr_ss    = v * delta' / (L_eff + K_us * v^2)
  yr[k+1]  = yr[k] + alpha * (yr_ss[k+1] - yr[k])    # first-order lag
            with alpha = dt / (tau + dt)

δ₀ selection is platform-gated:
  - Mach-E and IONIQ-5 use per-segment δ₀ estimated from the segment's own
    straight-driving rows (gate: |yaw_rate_pred_rads| < 0.03 ∧ v > 5).
  - Lightning uses a global static δ₀ (per-segment scatter is too tight to help).
  - Tesla has no truth — V0 passthrough.

All inputs read from the operating-contract allowlist:
  t_s, delta_road_rad, v_mps, yaw_rate_pred_rads.

Trajectory (x_m, y_m) is omitted — the grader's `_shared/traj_metrics` will
integrate from predicted yaw rate + measured v.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Load fitted coefficients (sibling JSON file).
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
with open(_HERE / "coeffs.json") as _f:
    _COEFFS = json.load(_f)


def _per_segment_delta0(sim_df, fallback=0.0,
                        yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(sim_df["delta_road_rad"].to_numpy()[mask]))


def _predict_one(sim_df, p):
    if p.get("use_per_segment_delta0", False):
        d0 = _per_segment_delta0(sim_df, fallback=float(p.get("delta0_fallback", 0.0)))
    else:
        d0 = float(p.get("delta0", 0.0))
    delta = (sim_df["delta_road_rad"].to_numpy() - d0) * float(p["g"])
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (float(p["L_eff"]) + float(p["K_us"]) * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    tau = float(p["tau"])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    if len(yr) == 0:
        return yr
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate aligned with sim_df.index.

    Returns a DataFrame with column `yaw_rate_pred_rads`. (x_m, y_m are
    omitted; the canonical grader integrates them from yaw_rate + v.)
    """
    coeffs = _COEFFS.get(platform)
    if coeffs is None or coeffs.get("passthrough", False):
        # No fitted model for this platform — V0 passthrough.
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    yr = _predict_one(sim_df, coeffs)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
