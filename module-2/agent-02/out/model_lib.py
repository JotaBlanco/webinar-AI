"""Model library — V1 (understeer) and V2 (understeer + steering-rate lead).

Both models operate on the speed-known framing: yaw_rate is computed from the
measured speed v_mps and measured road-wheel angle delta_road_rad.

V1: yaw = v * delta / (L_eff + K_us * v^2) + b
   where L_eff and K_us and b are per-platform fitted coeffs.

V2: V1 + tau * d(delta)/dt
   adds a phase-lead term to compensate measurement-pipeline delay between
   steering and yaw channels.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def predict_v1(sim_df: pd.DataFrame, coeffs: dict) -> np.ndarray:
    """V1 linear understeer.

    yaw_rate = v * delta / (L_eff + K_us * v^2) + b
    """
    v     = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    L_eff = coeffs["L_eff"]
    K_us  = coeffs["K_us"]
    b     = coeffs.get("b", 0.0)
    denom = L_eff + K_us * v * v
    # safe denominator
    denom = np.where(np.abs(denom) > 1e-3, denom, np.sign(denom) * 1e-3 + 1e-6)
    return v * delta / denom + b


def predict_v2(sim_df: pd.DataFrame, coeffs: dict) -> np.ndarray:
    """V2: V1 + tau * d(delta)/dt.

    Phase-lead in steering to compensate measurement-pipeline delay.
    """
    v     = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t     = sim_df["t_s"].to_numpy(dtype=float)
    L_eff = coeffs["L_eff"]
    K_us  = coeffs["K_us"]
    b     = coeffs.get("b", 0.0)
    tau   = coeffs.get("tau", 0.0)

    # Use a phase-shifted delta (lead by tau): delta_eff = delta + tau * d(delta)/dt
    if len(t) >= 2:
        ddelta_dt = np.gradient(delta, t)
    else:
        ddelta_dt = np.zeros_like(delta)
    delta_eff = delta + tau * ddelta_dt

    denom = L_eff + K_us * v * v
    denom = np.where(np.abs(denom) > 1e-3, denom, np.sign(denom) * 1e-3 + 1e-6)
    return v * delta_eff / denom + b


# Defaults per platform (initial guesses based on physical priors)
# L_eff approximately the wheelbase, K_us small understeer gradient, b small bias.
INITIAL_COEFFS_V1 = {
    "FORD_F_150_LIGHTNING_MK1": {"L_eff": 3.70, "K_us": 0.0, "b": 0.0},
    "FORD_MUSTANG_MACH_E_MK1":  {"L_eff": 2.984, "K_us": 0.0, "b": 0.0},
    "HYUNDAI_IONIQ_5":          {"L_eff": 3.0,  "K_us": 0.0, "b": 0.0},
    "TESLA_MODEL_3":            {"L_eff": 2.875, "K_us": 0.0, "b": 0.0},
}

INITIAL_COEFFS_V2 = {
    plat: {**c, "tau": 0.0}
    for plat, c in INITIAL_COEFFS_V1.items()
}

BOUNDS_V1 = {
    plat: {"L_eff": (1.5, 6.0), "K_us": (-0.5, 1.0), "b": (-0.01, 0.01)}
    for plat in INITIAL_COEFFS_V1
}

BOUNDS_V2 = {
    plat: {"L_eff": (1.5, 6.0), "K_us": (-0.5, 1.0), "b": (-0.01, 0.01), "tau": (-0.5, 0.5)}
    for plat in INITIAL_COEFFS_V2
}
