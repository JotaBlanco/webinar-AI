"""Model C — V1 + feed-forward correction from d(delta_road)/dt.

Attacks V1's transient-regime yaw residual. After V1's first-order lag, the
residual on transient (rapid steering) samples retains structure correlated
with d(delta_road)/dt. We fit a single per-platform gain k_ff (closed-form
LS on sim/segments) and add k_ff * d(delta_road)/dt to V1's yaw output.

The coefficient is gated by a smooth |delta_road| envelope so we don't
push noise on near-straight driving.
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
        p = HERE / "coeffs.json"
        if p.exists():
            _COEFFS = json.loads(p.read_text())
        else:
            _COEFFS = {}
    return _COEFFS


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    base = predict_v1(sim_df, platform)
    cf = _coeffs().get(platform)
    if cf is None or platform == "TESLA_MODEL_3":
        return base
    k_ff = float(cf.get("k_ff", 0.0))
    if k_ff == 0.0:
        return base
    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    if len(t) < 3:
        return base
    ddelta = np.gradient(delta, t)
    # gate by |delta| > 0.005 (not straight) so we only fire on cornering input
    gate = np.clip((np.abs(delta) - 0.005) / 0.005, 0.0, 1.0)
    correction = k_ff * ddelta * gate
    yr = base["yaw_rate_pred_rads"].to_numpy() + correction
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
