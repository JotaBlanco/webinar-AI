"""Lateral-fidelity predict — kinematic single-track with per-platform
calibration (steering scale g, effective wheelbase L_eff, understeer K_us),
first-order yaw-rate lag tau, platform-gated per-segment delta0 estimated
from straight-driving rows.

Recipe shape from references/anti-patterns.md "Legal cousin" section.
Coefficients in `coeffs.json` (sibling file).

Operating contract: sim_df is the operating-contract input (no truth columns).
Per-segment delta0 detector uses `yaw_rate_pred_rads` (V0 baseline reference,
in the allowed-input list) as the straight-driving proxy — `a_lat_meas_mps2`
is NOT in the scorer's allowlist so we can't use the recipe's original gate.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_COEFFS_PATH = Path(__file__).parent / "coeffs.json"
with open(_COEFFS_PATH) as _f:
    _COEFFS_RAW = json.load(_f)

# Drop the _meta key if present
PLATFORM_PARAMS = {k: v for k, v in _COEFFS_RAW.items() if not k.startswith("_")}


def _per_segment_delta0(
    sim_df: pd.DataFrame,
    fallback: float = 0.0,
    yr_thresh: float = 0.03,
    v_thresh: float = 5.0,
    min_rows: int = 50,
) -> float:
    """Estimate per-segment steering offset using V0 yaw-rate prediction as
    a straight-driving detector. Returns `fallback` if too few straight rows."""
    v = sim_df["v_mps"].to_numpy()
    if "yaw_rate_pred_rads" in sim_df.columns:
        yr_proxy = sim_df["yaw_rate_pred_rads"].to_numpy()
        mask = (np.abs(yr_proxy) < yr_thresh) & (v > v_thresh)
    else:
        # Fallback gating if baseline column isn't supplied (very small
        # delta as a weak straight proxy)
        mask = (sim_df["delta_road_rad"].to_numpy().__abs__() < 0.005) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _bicycle_yaw_rate(
    sim_df: pd.DataFrame,
    p: dict,
) -> np.ndarray:
    """KS + understeer + first-order lag, with per-segment or fixed delta0."""
    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=p.get("delta0", 0.0))
    else:
        delta0 = float(p.get("delta0", 0.0))

    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)

    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    tau = p["tau"]
    alpha = dt / (tau + dt)

    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned with sim_df.index containing yaw_rate_pred_rads.

    Tesla and any platform with no fitted params fall back to V0 (the baseline
    yaw_rate_pred_rads passed through the operating contract).
    """
    if platform not in PLATFORM_PARAMS:
        # Tesla: no truth channel — pass V0 baseline through unchanged.
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )

    p = PLATFORM_PARAMS[platform]
    yr = _bicycle_yaw_rate(sim_df, p)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)


__all__ = ["predict", "PLATFORM_PARAMS"]
