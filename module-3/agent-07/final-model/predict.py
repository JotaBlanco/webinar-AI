"""Final model — KS + understeer + first-order lag + per-segment δ₀.

Platform-gated per-segment δ₀ estimation from input channels only
(legal at inference time — no truth columns read).

Tesla -> V0 passthrough (no truth channel to fit against).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).parent / "coeffs.json"
with open(_COEFFS_PATH) as _f:
    _CFG = json.load(_f)

PLATFORM_PARAMS: dict[str, dict] = _CFG["params"]
PLATFORM_GATES: dict[str, bool] = _CFG["gates"]


def _per_segment_delta0(sim_df: pd.DataFrame,
                        fallback: float = 0.0,
                        yr_thresh: float = 0.03,
                        v_thresh: float = 5.0,
                        min_rows: int = 50) -> float:
    """Estimate δ₀ for THIS segment from its straight-driving rows.

    Uses input-allowlist channels only: v_mps, yaw_rate_pred_rads (V0 baseline),
    delta_road_rad. Legal at grading time.
    """
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return float(fallback)
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return DataFrame with yaw_rate_pred_rads aligned with sim_df.index."""
    if platform not in PLATFORM_PARAMS:
        # Tesla and any other platform without a fitted model -> V0 passthrough.
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = PLATFORM_PARAMS[platform]
    gate = bool(PLATFORM_GATES.get(platform, False))
    if gate:
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0"])
    else:
        delta0 = float(p["delta0"])

    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)

    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    tau = max(p["tau"], 1e-3)
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
