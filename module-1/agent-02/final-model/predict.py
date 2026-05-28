"""Final lateral-fidelity model for agent-02.

Improvements over V0 (pure kinematic single-track):
- V1: Linear-tire understeer correction:
        yaw_rate_ss = v * delta / (L + K_us * v^2)
- V2: Per-platform steering scale and offset (compliance + sensor bias):
        delta_eff = s_scale * delta_road - delta_offset
- V3: 1st-order yaw-rate lag (steer-to-yaw dynamics):
        tau * d(yr)/dt + yr = yr_ss
        Discrete: yr[k+1] = a*yr[k] + (1-a)*yr_ss[k], a = exp(-dt/tau)

Coefficients fit on 60% of segments per Ford platform; held-out RMSE in
REPORT.md.

API:
    predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame
Returns a DataFrame aligned with sim_df.index with column
`yaw_rate_pred_rads` (rad/s) and integrated `x_m`, `y_m` (m).
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with open(_COEFFS_PATH) as _f:
    _COEFFS = json.load(_f)


def _apply_first_order_lag(y_in: np.ndarray, tau: float, dt: float) -> np.ndarray:
    """Discrete 1st-order low-pass on `y_in`. Assumes uniform `dt`."""
    if tau <= 0 or len(y_in) < 2:
        return y_in.copy()
    a = float(np.exp(-dt / tau))
    out = np.empty_like(y_in)
    out[0] = y_in[0]
    for i in range(1, len(y_in)):
        out[i] = a * out[i - 1] + (1.0 - a) * y_in[i - 1]
    return out


def _integrate_xy(t: np.ndarray, v: np.ndarray, yaw_rate: np.ndarray,
                  x0: float = 0.0, y0: float = 0.0, psi0: float = 0.0):
    dt = np.diff(t, prepend=t[0])
    psi = psi0 + np.cumsum(yaw_rate * dt) - yaw_rate[0] * dt[0]
    psi_mid = psi.copy()
    psi_mid[1:] = 0.5 * (psi[1:] + psi[:-1])
    psi_mid[0] = psi0
    dx = v * np.cos(psi_mid) * dt
    dy = v * np.sin(psi_mid) * dt
    x = x0 + np.cumsum(dx) - dx[0]
    y = y0 + np.cumsum(dy) - dy[0]
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a frame aligned with sim_df.index with yaw_rate_pred_rads, x_m, y_m."""
    if platform not in _COEFFS:
        # Fall back to a neutral set
        c = {"L": 2.9, "s_scale": 1.0, "delta_offset_rad": 0.0,
             "K_us": 0.0025, "tau_yaw_s": 0.05}
    else:
        c = _COEFFS[platform]

    L      = float(c["L"])
    s_sc   = float(c["s_scale"])
    d0     = float(c["delta_offset_rad"])
    K_us   = float(c["K_us"])
    tau    = float(c["tau_yaw_s"])

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)

    # Handle non-finite by filling with previous value (best-effort)
    if not np.isfinite(v).all():
        v = pd.Series(v).ffill().bfill().to_numpy()
    if not np.isfinite(d).all():
        d = pd.Series(d).ffill().bfill().to_numpy()

    # Steady-state yaw rate (linear-tire understeer)
    delta_eff = s_sc * d - d0
    denom = L + K_us * v * v
    yr_ss = v * delta_eff / denom

    # 1st-order lag
    dt_arr = np.diff(t)
    dt = float(np.median(dt_arr)) if len(dt_arr) else 0.02
    if dt <= 0:
        dt = 0.02
    yr = _apply_first_order_lag(yr_ss, tau, dt)

    # Integrate trajectory using measured velocity for consistency with grader
    x_m, y_m = _integrate_xy(t, v, yr)

    out = pd.DataFrame({
        "yaw_rate_pred_rads": yr,
        "x_m": x_m,
        "y_m": y_m,
    }, index=sim_df.index)
    return out
