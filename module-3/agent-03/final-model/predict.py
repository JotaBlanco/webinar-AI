"""Lateral-fidelity predict — KS + understeer + first-order lag + per-segment δ₀.

Schema-aware (operating contract): reads only the 8-column allowlist.
For Tesla, passes through V0 (no truth channel — fitting is moot).
For each Ford/Hyundai platform, applies:

    delta = (delta_road_rad - delta0_seg) * g
    yr_ss = v * delta / (L_eff + K_us * v^2)
    yr_smoothed[i] = yr_smoothed[i-1] + alpha[i] * (yr_ss[i] - yr_smoothed[i-1])
    where alpha = dt / (tau + dt)

`delta0_seg` is the per-segment steering offset estimated from input-only
straight-driving rows (legal). Platforms gated per the bias-spread diagnostic.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).parent / "coeffs.json"
_COEFFS = json.loads(_COEFFS_PATH.read_text())


def _per_segment_delta0(sim_df: pd.DataFrame, fallback: float,
                        yr_thresh: float = 0.03, v_thresh: float = 5.0,
                        min_rows: int = 50) -> float:
    """δ₀ estimated from THIS segment's straight-driving rows (input-only)."""
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _apply_model(sim_df: pd.DataFrame, p: dict) -> np.ndarray:
    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=p.get("delta0_fallback", 0.0))
    else:
        delta0 = p.get("delta0", 0.0)

    delta_road = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    delta_eff = (delta_road - delta0) * p["g"]
    yr_ss = v * delta_eff / (p["L_eff"] + p["K_us"] * v * v)

    tau = p["tau"]
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in _COEFFS:
        # V0 passthrough for unknown platforms (including Tesla — no truth to fit).
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = _COEFFS[platform]
    yr = _apply_model(sim_df, p)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
