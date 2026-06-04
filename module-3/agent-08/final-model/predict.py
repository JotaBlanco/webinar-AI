"""Lateral-fidelity predictor.

Single-track kinematic core with platform-tuned (g, L_eff, K_us, tau, delta0),
per-segment δ₀ estimation gated by platform (Mach-E + IONIQ-5: on; Lightning: off),
and a first-order lag on yaw rate. Tesla falls back to V0 passthrough (no truth
to fit). Reads only allowlist columns. See REPORT.md for derivation.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_HERE = Path(__file__).resolve().parent
with open(_HERE / "coeffs.json") as _f:
    PLATFORM_PARAMS: dict = json.load(_f)


def _per_segment_delta0(
    sim_df: pd.DataFrame,
    fallback: float = 0.0,
    yr_thresh: float = 0.03,
    v_thresh: float = 5.0,
    min_rows: int = 50,
) -> float:
    """Estimate δ₀ from THIS segment's straight-driving rows.

    Uses only allowlist inputs: yaw_rate_pred_rads (V0) as straight detector,
    plus v_mps and delta_road_rad.
    """
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _yaw_rate_with_lag(
    t: np.ndarray,
    v: np.ndarray,
    delta_eff: np.ndarray,
    L_eff: float,
    K_us: float,
    tau: float,
) -> np.ndarray:
    yr_ss = v * delta_eff / (L_eff + K_us * v * v)
    dt = np.diff(t, prepend=t[0])
    # First sample dt=0 -> alpha=0 (anchor at yr_ss[0])
    safe_tau = max(tau, 1e-6)
    alpha = dt / (safe_tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in PLATFORM_PARAMS:
        # Tesla and unknowns: V0 passthrough
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )

    p = PLATFORM_PARAMS[platform]
    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=p.get("delta0_fallback", 0.0))
    else:
        delta0 = p.get("delta0", 0.0)

    delta_road = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()

    delta_eff = (delta_road - delta0) * p["g"]
    yr = _yaw_rate_with_lag(t, v, delta_eff, p["L_eff"], p["K_us"], p["tau"])

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
