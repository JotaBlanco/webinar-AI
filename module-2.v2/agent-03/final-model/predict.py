"""Lateral-fidelity model — kinematic bicycle with understeer + steering lag.

Per-sample model:
    delta_eff[k+1] = delta_eff[k] + dt/(tau+dt) * (delta_road[k+1] - delta_eff[k])
    yaw_rate[k]    = v[k] * tan(delta_eff[k] - delta_offset)
                       / (L * (1 + K * v[k]^2))

Terms:
- K  : understeer-gradient correction. Real vehicles' tires slip, so the
       steady-state yaw gain decays with v compared to KS (V0).
- delta_offset : per-platform steering-zero offset (radians at road wheel).
       Wipes out signed yaw bias, which is what kills CTE.
- tau : first-order steering response lag. Helps in transient (steering ramp)
       segments where V0 leads the truth.

Coefficients in coeffs.json are fitted per platform on the full
sim/segments/<PLATFORM> set (see ../out/fit_with_lag.py).

Tesla: no independent truth (sim psi_dot_rads IS V0). We pass V0 through
unchanged — anything else would *raise* Tesla's RMSE.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).parent / "coeffs.json"
with _COEFFS_PATH.open() as fh:
    _COEFFS = json.load(fh)


def _ks_passthrough(sim_df: pd.DataFrame) -> pd.DataFrame:
    return sim_df[["yaw_rate_pred_rads"]].copy()


def _apply_lag(delta: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    """First-order lag (implicit step): y[k+1] = y[k] + dt/(tau+dt)*(u[k+1]-y[k])."""
    if tau <= 1e-6 or len(delta) < 2:
        return delta.copy()
    out = np.empty_like(delta)
    out[0] = delta[0]
    dt = np.diff(t)
    # Vectorised forward sweep — recurrence so loop is unavoidable in pure numpy.
    a = dt / (tau + dt)
    prev = out[0]
    for k in range(len(dt)):
        prev = prev + a[k] * (delta[k + 1] - prev)
        out[k + 1] = prev
    return out


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return DataFrame aligned with sim_df.index with `yaw_rate_pred_rads`."""
    if platform not in _COEFFS:
        return _ks_passthrough(sim_df)

    c = _COEFFS[platform]
    L = float(c["L"])
    K = float(c["K"])
    doff = float(c.get("delta_offset_rad", 0.0))
    tau = float(c.get("tau_s", 0.0))

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d_road = sim_df["delta_road_rad"].to_numpy(dtype=float)

    # Guard: degenerate time array — fall back to no-lag.
    if len(t) < 2 or np.any(np.diff(t) <= 0):
        d_eff = d_road
    else:
        d_eff = _apply_lag(d_road, t, tau)

    yaw = (v * np.tan(d_eff - doff)) / (L * (1.0 + K * v * v))

    return pd.DataFrame({"yaw_rate_pred_rads": yaw}, index=sim_df.index)
