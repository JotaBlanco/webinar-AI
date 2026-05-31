"""Lateral-fidelity model V3.

Per-platform calibrated understeer bicycle:

    yaw_rate = g * v * delta_road / (L + K * v^2) + b

Coefficients (g, b, K, L) fitted offline (see ../out/fit.py and fit_results.json)
on data/sim/segments/ truth (yaw_rate_meas_rads, or psi_dot_rads for Tesla).

Trajectory (x_m, y_m) is left for the scorer to integrate from
yaw_rate_pred_rads + v_mps, per the standard contract.

predict(sim_df, platform) -> DataFrame with `yaw_rate_pred_rads`, aligned to
sim_df.index. Only reads columns in the grader allowlist:
{t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2, accel_pedal_pct,
 brake_pressed, yaw_rate_pred_rads}.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent

# Per-platform calibration (V3 fit). L is wheelbase in metres.
COEFFS: dict[str, dict[str, float]] = {
    "FORD_F_150_LIGHTNING_MK1": {
        "L": 3.7,
        "g": 0.9745606614390315,
        "b": -0.004413459312582783,
        "K": 0.0038227890419968093,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "L": 2.984,
        "g": 1.1997759567616932,
        "b": 0.0002141691332021686,
        "K": 0.002873342046876606,
    },
    "HYUNDAI_IONIQ_5": {
        "L": 3.0,
        "g": 0.9713440546476004,
        "b": 0.001981953567425843,
        "K": 0.0034142168703549265,
    },
    "TESLA_MODEL_3": {
        # Tesla's truth (psi_dot_rads) is essentially V0 (RMSE ~1.7e-7 against
        # the kinematic baseline). V3 fit on Tesla also stays very close to V0
        # (g=1.017, K=6.4e-5, b=-2e-5) and improves RMSE on the truth used in
        # the truth-aware fit. Keep it.
        "L": 2.875,
        "g": 1.0173777794440362,
        "b": -2.0323637825572535e-05,
        "K": 6.448127615112944e-05,
    },
}


def _coeffs_for(platform: str) -> dict[str, float]:
    if platform in COEFFS:
        return COEFFS[platform]
    # Fallback for unknown platforms: pure V0 (g=1, b=0, K=0) with L from
    # delta_road = delta_wheel / steering_ratio assumption. We just need a
    # neutral wheelbase guess; Mustang's 2.984 m is mid-pack.
    return {"L": 2.984, "g": 1.0, "b": 0.0, "K": 0.0}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """V3 per-platform calibrated bicycle yaw-rate prediction.

    Args:
        sim_df: input frame with at least `delta_road_rad` and `v_mps`.
        platform: e.g. "FORD_MUSTANG_MACH_E_MK1".

    Returns:
        DataFrame indexed identically to sim_df with column
        `yaw_rate_pred_rads`.
    """
    c = _coeffs_for(platform)
    L, g, b, K = c["L"], c["g"], c["b"], c["K"]

    # Defensive column access — fall back to V0 column if inputs missing.
    if "delta_road_rad" in sim_df.columns and "v_mps" in sim_df.columns:
        delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
        v = sim_df["v_mps"].to_numpy(dtype=float)
        denom = L + K * v * v
        # Avoid divide-by-zero at perfectly zero wheelbase (shouldn't happen).
        denom = np.where(denom == 0.0, L, denom)
        yaw = g * v * delta / denom + b
    elif "yaw_rate_pred_rads" in sim_df.columns:
        yaw = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    else:
        yaw = np.zeros(len(sim_df), dtype=float)

    out = pd.DataFrame({"yaw_rate_pred_rads": yaw}, index=sim_df.index)
    return out
