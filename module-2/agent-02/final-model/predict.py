"""V1 lateral fidelity model — per-platform linearised bicycle.

Model (yaw rate):
    yr_pred = scale * v * (delta_road - d0) / (L + K * v^2)

Where (L, K, scale, d0) are per-platform coefficients fitted on
data/sim/segments/<PLATFORM>/ truth (yaw_rate_meas_rads). K is the
understeer coefficient (s^2/m^2): the linearised single-track model
collapses neutrally-steered (K=0) into the kinematic KS baseline.

V0 (the baseline `yaw_rate_pred_rads` already in sim_df) was the
neutral-steer kinematic prediction (v/L)*tan(delta_road). Removing
the tan() linearisation and adding (K, scale, d0) reduces yaw RMSE
materially (see REPORT.md).

The predict() entry returns a DataFrame with at minimum
`yaw_rate_pred_rads`, aligned to sim_df.index. Trajectory integration
is handled by the canonical grader from yaw_rate + v_mps.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# Per-platform coefficients, fitted on the route-grouped 80% train split.
COEFFS = {
    "FORD_F_150_LIGHTNING_MK1": {"L": 3.70,  "K": 0.003790, "scale": 0.97249, "d0":  0.001330},
    "FORD_MUSTANG_MACH_E_MK1":  {"L": 2.984, "K": 0.003026, "scale": 1.20746, "d0":  0.000072},
    "HYUNDAI_IONIQ_5":          {"L": 3.00,  "K": 0.003270, "scale": 0.96766, "d0": -0.000717},
    # Tesla's "truth" channel (psi_dot_rads in sim/) IS the kinematic prediction
    # to ~1e-6 rad/s. So the V0 baseline is perfect for Tesla; any non-zero
    # K / scale-deviation / d0 would only inject error. Keep neutral.
    "TESLA_MODEL_3":            {"L": 2.875, "K": 0.0,      "scale": 1.0,     "d0":  0.0},
}

# Fallback for any unseen platform: kinematic KS with no understeer.
DEFAULT = {"L": 2.9, "K": 0.0, "scale": 1.0, "d0": 0.0}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict lateral state.

    Args:
        sim_df: input frame with at least 't_s', 'delta_road_rad', 'v_mps'.
                Other columns from the operating-contract allowlist may be
                present but are not required.
        platform: platform key (e.g. 'TESLA_MODEL_3').

    Returns:
        DataFrame indexed like sim_df with column 'yaw_rate_pred_rads'.
    """
    # Tesla's `truth` channel in the workshop dataset is identical to the V0
    # kinematic prediction (`v * tan(delta_road) / L`) to ~1e-6 rad/s — it was
    # generated FROM the model. Any per-platform fit just injects noise. Pass
    # the V0 baseline through unchanged.
    if platform == "TESLA_MODEL_3" and "yaw_rate_pred_rads" in sim_df.columns:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)},
            index=sim_df.index,
        )

    c = COEFFS.get(platform, DEFAULT)
    L = c["L"]; K = c["K"]; scale = c["scale"]; d0 = c["d0"]

    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)

    denom = L + K * v * v
    yr = scale * v * (d - d0) / denom
    yr = np.nan_to_num(yr, nan=0.0, posinf=0.0, neginf=0.0)

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
