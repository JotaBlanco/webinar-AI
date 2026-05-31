"""Candidate v1: per-platform kinematic recompute + understeer gradient + low-pass."""
import numpy as np
import pandas as pd

L_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "TESLA_MODEL_3": 2.875,
}

# Fit on 70% train of each platform (see work/fit_v2.py)
PARAMS = {
    "FORD_MUSTANG_MACH_E_MK1": {"c_s": 1.2109, "K_us": 0.003135, "tau": 0.10},
    "FORD_F_150_LIGHTNING_MK1": {"c_s": 0.9736, "K_us": 0.003731, "tau": 0.06},
    # Tesla — no truth available so fall through to V0
    "TESLA_MODEL_3": {"c_s": 1.0, "K_us": 0.0, "tau": 0.0},
}


def _lowpass(arr, dt, tau):
    if tau <= 0:
        return arr.copy()
    alpha = dt / (tau + dt)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = out[i-1] * (1 - alpha) + arr[i] * alpha
    return out


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    L = L_PLATFORM.get(platform, 2.984)
    p = PARAMS.get(platform, {"c_s": 1.0, "K_us": 0.0, "tau": 0.0})

    # Steady-state bicycle with understeer gradient (CommonRoad-form):
    # yr = v * (c_s * delta) / (L + K_us * v^2)
    yr = v * (p["c_s"] * delta) / (L + p["K_us"] * v * v)

    if len(t) > 1:
        dt = float(np.median(np.diff(t)))
    else:
        dt = 0.02
    yr = _lowpass(yr, dt, p["tau"])

    out["yaw_rate_pred_rads"] = yr
    return out
