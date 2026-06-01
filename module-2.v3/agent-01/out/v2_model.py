"""V2 model — bicycle/understeer + steering-rate lead + delta cubic correction.

    delta_eff = delta + tau * d_delta/dt
    yaw_pred  = gain * v * (delta_eff + c3 * delta_eff^3) / (L_eff + K_us * v^2) + bias

For Tesla, predict() is pass-through (no independent truth).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

PLATFORMS = (
    "FORD_F_150_LIGHTNING_MK1",
    "FORD_MUSTANG_MACH_E_MK1",
    "HYUNDAI_IONIQ_5",
)


def predict_yaw(sim_df, coeffs):
    t      = sim_df["t_s"].to_numpy(dtype=float)
    v      = sim_df["v_mps"].to_numpy(dtype=float)
    delta  = sim_df["delta_road_rad"].to_numpy(dtype=float)

    L_eff = float(coeffs.get("L_eff", 2.9))
    K_us  = float(coeffs.get("K_us", 0.0))
    gain  = float(coeffs.get("gain", 1.0))
    bias  = float(coeffs.get("bias", 0.0))
    tau   = float(coeffs.get("tau", 0.0))
    c3    = float(coeffs.get("c3", 0.0))

    if abs(tau) > 1e-9 and len(t) >= 2:
        ddelta_dt = np.gradient(delta, t)
        delta_eff = delta + tau * ddelta_dt
    else:
        delta_eff = delta

    if abs(c3) > 1e-12:
        delta_used = delta_eff + c3 * delta_eff ** 3
    else:
        delta_used = delta_eff

    denom = L_eff + K_us * v * v
    return gain * v * delta_used / denom + bias


def predict_factory(platform, coeffs):
    if platform == "TESLA_MODEL_3":
        def predict_tesla(sim_df):
            return sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        return predict_tesla

    def predict(sim_df):
        return predict_yaw(sim_df, coeffs)
    return predict
