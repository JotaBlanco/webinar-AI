"""Model E — V1 + per-platform 3-param correction (s, b, k_ff).

y = s * y_v1 + b + k_ff * d(delta_road)/dt * gate

Combines:
  - affine bias correction (s, b) — removes signed yaw bias that drives CTE
  - transient feed-forward (k_ff) — corrects V1's over-shoot during fast
    steering (V1's first-order lag is too lossy)

Fit by closed-form OLS on sim/segments, per platform. Tesla falls through
to V0 (no truth). 3 scalars per non-Tesla platform = 9 fitted scalars total.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1  # type: ignore

_COEFFS = None


def _coeffs():
    global _COEFFS
    if _COEFFS is None:
        _COEFFS = json.loads((HERE / "coeffs.json").read_text())
    return _COEFFS


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    base = predict_v1(sim_df, platform)
    if platform == "TESLA_MODEL_3" or platform not in _coeffs():
        return base
    c = _coeffs()[platform]
    s = float(c.get("s", 1.0))
    b = float(c.get("b", 0.0))
    k_ff = float(c.get("k_ff", 0.0))
    yr_v1 = base["yaw_rate_pred_rads"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    if len(t) >= 3:
        ddelta = np.gradient(delta, t)
        gate = np.clip((np.abs(delta) - 0.005) / 0.005, 0.0, 1.0)
        feat = ddelta * gate
    else:
        feat = np.zeros_like(yr_v1)
    yr = s * yr_v1 + b + k_ff * feat
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
