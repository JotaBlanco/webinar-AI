"""idea-01 lateral fidelity — understeer-corrected single-track bicycle.

Model:
    yaw_rate = v * (a * delta_road + b) / (L + K * v^2)

Where (a, b, K) are per-platform coefficients fit by minimising RMSE against
the truth channel in data/sim/segments/<PLATFORM>/.../sim.csv.

Trajectory (x, y) integrated forward from yaw_rate + measured v via simple
forward-Euler (uniform t_s grid assumed; we cope with non-uniform too).
"""
from __future__ import annotations

import json
import os
from typing import Dict

import numpy as np
import pandas as pd

_COEFFS_PATH = os.path.join(os.path.dirname(__file__), "coeffs.json")
with open(_COEFFS_PATH) as _fh:
    _COEFFS: Dict[str, dict] = json.load(_fh)

# Generic fallback (median-ish of the three non-trivial platforms)
_FALLBACK = {"L": 3.0, "a": 0.97, "b": 0.0, "K": 0.0035}


def _coeffs_for(platform: str) -> dict:
    if platform in _COEFFS:
        return _COEFFS[platform]
    # Unknown platform — fall back gracefully
    return _FALLBACK


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned with sim_df.index containing at minimum
    `yaw_rate_pred_rads`, plus integrated `x_m`, `y_m`.
    """
    c = _coeffs_for(platform)
    L, a, b, K = c["L"], c["a"], c["b"], c["K"]

    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    # Understeer-corrected steady-state bicycle yaw rate.
    denom = L + K * v * v
    yaw = v * (a * delta + b) / denom

    # Integrate heading and position.
    N = len(t)
    if N == 0:
        return pd.DataFrame(index=sim_df.index, data={
            "yaw_rate_pred_rads": [], "x_m": [], "y_m": [],
        })

    dt = np.empty(N)
    dt[1:] = np.diff(t)
    dt[0] = dt[1] if N > 1 else 0.0

    # Trapezoidal-rule heading: psi[k+1] = psi[k] + 0.5*(yaw[k]+yaw[k+1])*dt[k+1]
    psi = np.zeros(N)
    for k in range(N - 1):
        psi[k + 1] = psi[k] + 0.5 * (yaw[k] + yaw[k + 1]) * dt[k + 1]

    # Trapezoidal x, y integration in world frame.
    x = np.zeros(N)
    y = np.zeros(N)
    cpsi = np.cos(psi)
    spsi = np.sin(psi)
    for k in range(N - 1):
        x[k + 1] = x[k] + 0.5 * (v[k] * cpsi[k] + v[k + 1] * cpsi[k + 1]) * dt[k + 1]
        y[k + 1] = y[k] + 0.5 * (v[k] * spsi[k] + v[k + 1] * spsi[k + 1]) * dt[k + 1]

    out = pd.DataFrame(index=sim_df.index, data={
        "yaw_rate_pred_rads": yaw,
        "x_m": x,
        "y_m": y,
    })
    return out


if __name__ == "__main__":
    # Smoke test against a sim-only segment.
    import glob, sys
    sample = glob.glob(
        "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03/"
        "data/sim-only/segments/FORD_MUSTANG_MACH_E_MK1/*/*/*/sim.csv"
    )[:3]
    for f in sample:
        df = pd.read_csv(f)
        out = predict(df, "FORD_MUSTANG_MACH_E_MK1")
        # Compare against the V0 column (already there)
        v0 = df["yaw_rate_pred_rads"].to_numpy()
        delta_pred = out["yaw_rate_pred_rads"].to_numpy() - v0
        print(f"{f}: shape={out.shape}  mean|Δvs V0|={np.mean(np.abs(delta_pred)):.4f} rad/s")
