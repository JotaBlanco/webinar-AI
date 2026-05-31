"""Lateral-fidelity predict: per-platform bicycle-with-understeer + affine fit.

For each supported platform we predict the yaw rate as

    yr_pred = gain * (v * delta_road / (L + K * v^2)) + bias

with (L, K, gain, bias) loaded from `coeffs.json`. This is the kinematic
single-track yaw equation augmented with a single understeer coefficient K
(a linearised tire-slip term) plus a per-platform affine correction that
absorbs steady-state offsets (steer-ratio mis-calibration, suspension
compliance, sensor zero error).

For TESLA_MODEL_3 (no ground truth available locally) we fall back to the
V0 KS formula `yr = v * tan(delta_road) / L`.

x_m, y_m are optionally integrated from yaw rate + measured v using the
shared `_shared/traj_metrics.integrate_trajectory` math. We omit them and
let the grader integrate (the contract allows omission and is consistent
with our local scoring).

Operating contract: predict reads only ALLOWED_INPUT_COLUMNS — t_s,
delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2, accel_pedal_pct,
brake_pressed, yaw_rate_pred_rads.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
with (_HERE / "coeffs.json").open() as fh:
    _COEFFS: dict[str, Any] = json.load(fh)

# Fallback for unknown platforms
_DEFAULT = {"L": 2.95, "K": 0.0, "gain": 1.0, "bias": 0.0, "passthrough": True}


def _predict_yaw_rate(v: np.ndarray, delta_road: np.ndarray, platform: str,
                       v0_col: np.ndarray | None) -> np.ndarray:
    c = _COEFFS.get(platform, _DEFAULT)
    if c.get("passthrough", False):
        if v0_col is not None:
            return v0_col.astype(float)
        L = float(c["L"])
        return v * np.tan(delta_road) / L
    L = float(c["L"])
    K = float(c["K"])
    gain = float(c["gain"])
    bias = float(c["bias"])
    denom = L + K * v * v
    # Guard against tiny denominator (cannot realistically happen but be safe)
    denom = np.where(np.abs(denom) < 1e-3, 1e-3 * np.sign(denom + 1e-12), denom)
    return gain * (v * delta_road / denom) + bias


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate (and optionally x_m, y_m) for one segment.

    Args:
        sim_df: input columns from the operating contract allowlist.
                Must contain t_s, v_mps, delta_road_rad. May contain
                yaw_rate_pred_rads (V0 baseline).
        platform: one of {FORD_F_150_LIGHTNING_MK1, FORD_MUSTANG_MACH_E_MK1,
                  HYUNDAI_IONIQ_5, TESLA_MODEL_3}.

    Returns:
        DataFrame aligned with sim_df.index, column `yaw_rate_pred_rads`.
    """
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v0 = (
        sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        if "yaw_rate_pred_rads" in sim_df.columns
        else None
    )
    yr = _predict_yaw_rate(v, delta, platform, v0)
    out = pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    return out
