"""Lateral-fidelity predictor — agent-10.

Per-platform single-track with:
  - Polynomial steering scale     g(delta) = g0 + g2 * (delta - delta0)^2
  - Effective wheelbase           L_eff
  - Understeer                    K_us
  - Steering offset               delta0
  - First-order yaw-rate lag      tau

Model:
    delta_eff = delta - delta0
    g         = g0 + g2 * delta_eff^2
    yr_ss(t)  = v(t) * g * delta_eff(t) / (L_eff + K_us * v(t)^2)
    yr_pred   = first_order_lag(yr_ss, tau)

For TESLA_MODEL_3 (no truth channel in training data), passthrough V0's yaw_rate_pred_rads.

Parameters fit on 75% whole-route holdout (seed=42); see COEFFS.json.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
with (_THIS_DIR / "COEFFS.json").open() as fh:
    COEFFS = json.load(fh)


def _first_order_lag(yr_ss: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 0 or len(yr_ss) < 2:
        return yr_ss.copy()
    out = np.empty_like(yr_ss)
    out[0] = yr_ss[0]
    dt = np.diff(t)
    for k in range(len(yr_ss) - 1):
        a = dt[k] / (tau + dt[k])
        out[k + 1] = out[k] + a * (yr_ss[k + 1] - out[k])
    return out


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)

    if platform not in COEFFS:
        # Tesla (or any unknown platform) — passthrough V0.
        if "yaw_rate_pred_rads" in sim_df.columns:
            out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float).values
        else:
            out["yaw_rate_pred_rads"] = 0.0
        return out

    p = COEFFS[platform]
    g0 = float(p["g0"]); g2 = float(p["g2"])
    L_eff = float(p["L_eff"]); K_us = float(p["K_us"])
    delta0 = float(p["delta0"]); tau = float(p["tau"])

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)

    de = delta - delta0
    g = g0 + g2 * de * de
    yr_ss = v * g * de / (L_eff + K_us * v * v)
    yr_pred = _first_order_lag(yr_ss, t, tau)

    bad = ~np.isfinite(yr_pred)
    if bad.any():
        fallback = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float) if "yaw_rate_pred_rads" in sim_df.columns else np.zeros_like(yr_pred)
        yr_pred = np.where(bad, fallback, yr_pred)

    out["yaw_rate_pred_rads"] = yr_pred
    return out
