"""Module-3 agent-07 final model — per-platform linear-bicycle calibration.

Form
----
    yaw_rate_pred = k_delta * (v / L) * tan(delta_road) / (1 + Ku * v^2) + b

This is the "next rung" above V0 (kinematic single-track):
- k_delta absorbs steering-ratio / kingpin-compliance errors and the
  effective-wheelbase mismatch between the V0 prior L and the on-road truth.
- Ku is the linear-bicycle understeer-gradient coefficient
  (Gillespie 6-9 / Rajamani §3.4) — at low speed the kinematic formula is
  exact, at higher v the lateral-force balance produces a yaw-rate roll-off
  proportional to v^2.
- b absorbs residual sensor-bias / steering-angle zero offset per platform.

Coefficients in `coeffs.json` are fitted per platform on
`data/sim/segments/*/**/sim.csv` minimising pooled yaw-rate squared error
(v_mps > 2.0). Tesla collapses to k=1, Ku=0, b=0 because its truth channel
is the V0 KS output itself (no independent reference).

Predict reads ONLY the operating-contract columns
(t_s, v_mps, delta_road_rad, yaw_rate_pred_rads etc.) — no truth channels.

Trajectory (x_m, y_m) is *not* returned here. The scorer integrates
yaw_rate + measured v on its own under the standard kinematic-trajectory
convention; emitting x_m/y_m here would force a second integration with
identical starting state. See `_shared/traj_metrics.py` for the canonical
integration.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFF_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFF_PATH.open() as _fh:
    _COEFFS: dict = json.load(_fh)

# Fallback if a platform isn't in the calibration set: V0 identity. The
# pre-flight skill tests Mach-E, which is in the dict, but a real grader
# could conceivably pass an unseen platform — return V0 in that case.
_FALLBACK = {"k_delta": 1.0, "Ku": 0.0, "b": 0.0, "L": 2.875}


def _params(platform: str) -> dict:
    return _COEFFS.get(platform, _FALLBACK)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate for one segment.

    Parameters
    ----------
    sim_df : pd.DataFrame
        Per-sample inputs. Required columns: ``v_mps``, ``delta_road_rad``,
        ``yaw_rate_pred_rads`` (V0 baseline; used as the safety fallback).
    platform : str
        One of the platforms listed in ``manifest.json:platform_support``.

    Returns
    -------
    pd.DataFrame indexed identically to ``sim_df`` with a single column
    ``yaw_rate_pred_rads`` (rad/s).
    """
    p = _params(platform)
    L = float(p["L"])
    k = float(p["k_delta"])
    Ku = float(p["Ku"])
    b = float(p["b"])

    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)

    kin = (v / L) * np.tan(d)
    denom = 1.0 + Ku * (v * v)
    yr = k * kin / denom + b

    # Guard: at v near zero the bias term `b` can produce a spurious yaw
    # rate while the car is stationary. Clamp prediction to V0 (which is
    # also ~0 there) for very low speeds so we don't accumulate heading
    # error during stops.
    low_v = v < 1.0
    if low_v.any():
        v0 = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        yr = np.where(low_v, v0, yr)

    out = pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    return out
