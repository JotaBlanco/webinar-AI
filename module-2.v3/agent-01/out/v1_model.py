"""V1 lateral fidelity model — bicycle/understeer with optional steering-rate lead.

For each platform we fit a small per-platform coefficient set:

    yaw_pred = gain * v * (delta + tau * d_delta/dt) / (L_eff + K_us * v^2) + bias

For Tesla, predict() is a pass-through to V0 (sim's "truth" IS V0).
"""
from __future__ import annotations
import numpy as np
import pandas as pd


PLATFORMS = (
    "FORD_F_150_LIGHTNING_MK1",
    "FORD_MUSTANG_MACH_E_MK1",
    "HYUNDAI_IONIQ_5",
)


def predict_yaw(sim_df: pd.DataFrame, coeffs: dict) -> np.ndarray:
    """Compute predicted yaw rate vector from sim_df given coeffs."""
    t      = sim_df["t_s"].to_numpy(dtype=float)
    v      = sim_df["v_mps"].to_numpy(dtype=float)
    delta  = sim_df["delta_road_rad"].to_numpy(dtype=float)

    L_eff = float(coeffs.get("L_eff", 2.9))
    K_us  = float(coeffs.get("K_us", 0.0))
    gain  = float(coeffs.get("gain", 1.0))
    bias  = float(coeffs.get("bias", 0.0))
    tau   = float(coeffs.get("tau", 0.0))

    if abs(tau) > 1e-9 and len(t) >= 2:
        ddelta_dt = np.gradient(delta, t)
        delta_eff = delta + tau * ddelta_dt
    else:
        delta_eff = delta

    denom = L_eff + K_us * v * v
    yr = gain * v * delta_eff / denom + bias
    return yr


def predict_factory(platform: str, coeffs: dict):
    if platform == "TESLA_MODEL_3":
        def predict_tesla(sim_df):
            return sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        return predict_tesla

    def predict(sim_df):
        return predict_yaw(sim_df, coeffs)
    return predict
