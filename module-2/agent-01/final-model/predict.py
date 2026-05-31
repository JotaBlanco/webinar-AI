"""Lateral-fidelity model V2.

V2 = linear-bicycle steady-state yaw-rate with understeer gradient + steering
bias, passed through a first-order low-pass to capture tire build-up.

  y_ss[k] = v[k] * (delta[k] - delta0) / (L + K_us * v[k]^2)
  y[k+1]  = y[k] + (dt[k] / (tau + dt[k])) * (y_ss[k+1] - y[k])

Coefficients (L, K_us, delta0, tau) are per-platform; see coeffs.json. They
were fitted by Nelder-Mead on a deterministic train split (even-index sorted
sim.csv paths) for each Ford platform. Tesla has no truth channel, so the
Tesla coefficients use a literature-informed K_us prior and the Tesla
wheelbase from openpilot carParams; results there are uncalibrated.

Returns a DataFrame with required `yaw_rate_pred_rads` and optional `x_m`,
`y_m` integrated with the SAME Euler / cumsum scheme the grader uses in
`_shared/traj_metrics.integrate_trajectory`, so the two are consistent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_COEFF_PATH = Path(__file__).parent / "coeffs.json"
with _COEFF_PATH.open("r") as _fh:
    COEFFS: dict[str, dict[str, float]] = json.load(_fh)

# Fallback defaults if a platform is missing.
_DEFAULT = {"L": 2.984, "K_us": 0.001, "delta0": 0.0, "tau": 0.06}


def _params(platform: str) -> dict[str, float]:
    return COEFFS.get(platform, _DEFAULT)


def _steady_state_yaw(v: np.ndarray, delta: np.ndarray, L: float,
                      K_us: float, delta0: float) -> np.ndarray:
    """Steady-state yaw rate from understeer-corrected linear bicycle."""
    return v * (delta - delta0) / (L + K_us * v * v)


def _apply_lag(t: np.ndarray, y_ss: np.ndarray, tau: float,
               y0: float | None = None) -> np.ndarray:
    """Discrete first-order low-pass with variable dt; implicit-Euler blend.

    y[k+1] = y[k] + (dt / (tau + dt)) * (y_ss[k+1] - y[k])

    This is unconditionally stable for any dt, tau > 0.
    """
    n = len(y_ss)
    if n == 0:
        return y_ss
    y = np.empty(n, dtype=float)
    y[0] = float(y_ss[0]) if y0 is None else float(y0)
    if tau <= 0 or n == 1:
        return y_ss.copy()
    dt = np.diff(t)
    # Vectorised loop (small N per segment; numpy scalar ops keep this tight).
    for k in range(n - 1):
        a = dt[k] / (tau + dt[k])
        y[k + 1] = y[k] + a * (y_ss[k + 1] - y[k])
    return y


def _integrate_trajectory(dt: np.ndarray, v: np.ndarray, yr: np.ndarray):
    """Euler / zero-order-hold integration, matching _shared/traj_metrics.

    psi[i+1] = psi[i] + yr[i] * dt[i]
    x[i+1]   = x[i] + v[i] * cos(psi[i]) * dt[i]
    y[i+1]   = y[i] + v[i] * sin(psi[i]) * dt[i]
    """
    n = len(v)
    if n < 2:
        z = np.zeros(n)
        return z, z, z, z
    psi = np.empty(n)
    psi[0] = 0.0
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x = np.empty(n)
    x[0] = 0.0
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y = np.empty(n)
    y[0] = 0.0
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    s = np.empty(n)
    s[0] = 0.0
    s[1:] = np.cumsum(v[:-1] * dt)
    return s, x, y, psi


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict per-sample yaw rate (+ optional trajectory) for one segment.

    Args:
        sim_df: pre-loaded segment DataFrame with columns ``t_s``, ``v_mps``,
            ``delta_road_rad``. Must contain at least 1 row.
        platform: one of the keys in coeffs.json. Unknown platforms fall back
            to a generic prior — no exception is raised.

    Returns:
        DataFrame with the same index as sim_df, columns:
          - ``yaw_rate_pred_rads`` (required)
          - ``x_m``, ``y_m`` (integrated from yaw_rate and v_mps)
    """
    p = _params(platform)
    L = float(p["L"])
    K_us = float(p["K_us"])
    delta0 = float(p["delta0"])
    tau = float(p["tau"])

    n = len(sim_df)
    out = pd.DataFrame(index=sim_df.index)

    # Defensive: handle missing columns.
    if "v_mps" not in sim_df.columns or "delta_road_rad" not in sim_df.columns or "t_s" not in sim_df.columns:
        out["yaw_rate_pred_rads"] = np.zeros(n)
        out["x_m"] = np.zeros(n)
        out["y_m"] = np.zeros(n)
        return out

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)

    # NaN-safe.
    v = np.nan_to_num(v, nan=0.0)
    d = np.nan_to_num(d, nan=0.0)

    if n < 2:
        out["yaw_rate_pred_rads"] = np.zeros(n)
        out["x_m"] = np.zeros(n)
        out["y_m"] = np.zeros(n)
        return out

    y_ss = _steady_state_yaw(v, d, L, K_us, delta0)
    y = _apply_lag(t, y_ss, tau, y0=float(y_ss[0]))

    # Integrate trajectory consistently with the metric.
    dt = np.diff(t)
    # Guard against non-monotonic time.
    if np.any(dt <= 0):
        # Fall back to zero-trajectory; yaw rate is still valid sample-wise.
        out["yaw_rate_pred_rads"] = y
        out["x_m"] = np.zeros(n)
        out["y_m"] = np.zeros(n)
        return out

    _s, x, yc, _psi = _integrate_trajectory(dt, v, y)

    out["yaw_rate_pred_rads"] = y
    out["x_m"] = x
    out["y_m"] = yc
    return out


# Smoke test.
if __name__ == "__main__":
    import sys
    df = pd.DataFrame({
        "t_s": np.arange(100) * 0.02,
        "v_mps": np.full(100, 20.0),
        "delta_road_rad": np.full(100, 0.02),
    })
    res = predict(df, "FORD_F_150_LIGHTNING_MK1")
    print(res.head())
    print("ok, columns:", list(res.columns))
