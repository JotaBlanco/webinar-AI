"""Lateral-fidelity predictor (agent-06).

Model V2 — KS kinematic + steady-state understeer + first-order steering lag.

For each segment:
    delta_f(t) = lowpass(delta(t), tau)                    # first-order lag
    yr(t)      = scale * (v/L) * tan(delta_f - delta0) / (1 + K * v^2)

Per-platform coefficients (tau, K, delta0, scale, L) are fitted on a held-out
train split (seed=42, dev_fraction=0.25). The four physical effects:

  - 1/(1+K*v^2)  : steady-state understeer (linear bicycle limit)
  - delta0       : steering-system zero offset (sensor / alignment bias)
  - scale        : residual yaw gain (steering-ratio / Ackermann mismatch)
  - tau          : first-order driver/EPS lag on steering input

`x_m`, `y_m` are integrated with forward-Euler / zero-order-hold, identical to
`_shared/traj_metrics.integrate_trajectory`, so the model's reported trajectory
matches the grader's CTE pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFFS_PATH.open() as _fh:
    _COEFFS: Dict[str, Dict[str, float]] = json.load(_fh)

_DEFAULT_COEFF = {"K": 0.0008, "delta0": 0.0, "scale": 1.0, "L": 2.875, "tau": 0.06}


def _coeffs_for(platform: str) -> Dict[str, float]:
    return _COEFFS.get(platform, _DEFAULT_COEFF)


def _lowpass(x: np.ndarray, dt: np.ndarray, tau: float) -> np.ndarray:
    """First-order low-pass filter with time constant tau, irregular dt.

    Discrete update:   y[i] = y[i-1] + (dt[i-1] / (tau + dt[i-1])) * (x[i] - y[i-1])
    """
    if tau <= 0 or len(x) < 2:
        return x.astype(float, copy=True)
    y = np.empty_like(x, dtype=float)
    y[0] = x[0]
    # Vectorising the recursion is awkward; keep the loop, it's microseconds per segment.
    for i in range(1, len(x)):
        a = dt[i - 1] / (tau + dt[i - 1]) if dt[i - 1] > 0 else 0.0
        y[i] = y[i - 1] + a * (x[i] - y[i - 1])
    return y


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mirror of `_shared/traj_metrics.integrate_trajectory` (xy only)."""
    n = len(v)
    x = np.zeros(n)
    y = np.zeros(n)
    if n < 2:
        return x, y
    dt = np.diff(t)
    psi = np.empty(n)
    psi[0] = 0.0
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate and trajectory for a single segment.

    Parameters
    ----------
    sim_df : pd.DataFrame
        Must contain columns ``t_s``, ``v_mps``, ``delta_road_rad``.
    platform : str
        Platform key, e.g. ``"FORD_F_150_LIGHTNING_MK1"``.

    Returns
    -------
    pd.DataFrame indexed identically to ``sim_df`` with columns
    ``yaw_rate_pred_rads``, ``x_m``, ``y_m``.
    """
    c = _coeffs_for(platform)
    L = float(c.get("L", 2.875))
    K = float(c["K"])
    d0 = float(c["delta0"])
    scale = float(c["scale"])
    tau = float(c.get("tau", 0.0))

    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    if len(t) >= 2 and tau > 0:
        dt = np.diff(t)
        # pad to length(t) for the recursion
        dt_full = np.append(dt, dt[-1] if len(dt) else 0.02)
        delta_f = _lowpass(delta, dt_full, tau)
    else:
        delta_f = delta

    denom = 1.0 + K * v * v
    yr = scale * (v / L) * np.tan(delta_f - d0) / denom
    yr = np.where(np.isfinite(yr), yr, 0.0)

    x, y = _integrate_xy(t, v, yr)

    return pd.DataFrame(
        {"yaw_rate_pred_rads": yr, "x_m": x, "y_m": y},
        index=sim_df.index,
    )
