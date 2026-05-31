"""V1 lateral-fidelity predictor.

Strategy
--------
The V0 kinematic single-track (KS) model has two systematic failure modes that
dominate yaw-rate and CTE error:

1. **Constant signed bias** — for F150 Lightning, V0 over-predicts yaw rate
   by +0.004 rad/s on average (steering offset or steering-ratio mismatch);
   for Hyundai it under-predicts. This bias double-integrates into CTE drift
   that is the dominant CTE term (V0 baseline CTE = 163 m, with F150 +40 m
   and Hyundai -55 m signed drift).
2. **Speed-dependent gain error** — at high speed, real vehicles understeer
   (lateral force saturation), so the KS yaw rate is too aggressive. A linear
   regression of (truth - V0) against v and v^2 fits this cleanly.

We model both with a per-platform 4-parameter affine + understeer correction:

    yaw_corrected(v, y_v0) = a0*y_v0 + a1*y_v0*v + a2*y_v0*v^2 + b

Coefficients are fit per platform on every available sim segment by ordinary
least squares (sample-weighted, v_mps > 2 filter to match scorer). Tesla
passes V0 through unchanged because Tesla's sim.csv has no independent truth
channel (psi_dot_rads IS V0 there — any deviation increases its RMSE).

Trajectory (x_m, y_m) is omitted; the harness integrates from corrected yaw
rate and measured v_mps automatically.

Operating-contract input columns:
    t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
    accel_pedal_pct, brake_pressed, yaw_rate_pred_rads
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
_COEFFS: dict = json.loads(_COEFFS_PATH.read_text())

# Sensible default if we ever see a brand new platform — passthrough V0.
_DEFAULT = {"a0": 1.0, "a1": 0.0, "a2": 0.0, "b": 0.0}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return corrected yaw rate aligned with sim_df.index.

    Args:
        sim_df: per the operating-contract column allowlist.
        platform: one of the canonical platform names (Tesla/Mach-E/F150/Hyundai).

    Returns:
        DataFrame with one column ``yaw_rate_pred_rads``.
    """
    y0 = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    c = _COEFFS.get(platform, _DEFAULT)
    y = c["a0"] * y0 + c["a1"] * y0 * v + c["a2"] * y0 * v * v + c["b"]
    return pd.DataFrame({"yaw_rate_pred_rads": y}, index=sim_df.index)
