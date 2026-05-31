"""Final-model predict for module-3 lateral-fidelity challenge — agent-07.

Per-platform fitted single-track model with:
  - Steering scale  g
  - Steering offset d0  (road-wheel rad)
  - Understeer term K_us
  - First-order yaw-rate lag tau

yr_ss(t) = g * (delta(t) - d0) * v(t) / (L + K_us * v(t)^2)
yr(t)    = lowpass( yr_ss, tau )            # variable-dt first-order lag

For Tesla there is no truth channel, so we fall back to V0:
yr = (v/L) * tan(delta).

Trajectory (x, y) is integrated from the predicted yaw rate using the same
Euler integration the grader uses (see _shared/traj_metrics.py); we omit it
from the output and let the grader compute it from yaw-rate + measured v.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# Embedded coefficients (also stored in coeffs.json next to this file).
_COEFFS = {
    "FORD_MUSTANG_MACH_E_MK1": {
        "L": 2.984,
        "g": 1.1762462360941122,
        "d0": 0.00010063505427400637,
        "K_us": 0.0026382633004772204,
        "tau": 0.06840716946070041,
    },
    "FORD_F_150_LIGHTNING_MK1": {
        "L": 3.70,
        "g": 0.9812529513258541,
        "d0": 0.0011869609888145339,
        "K_us": 0.0041443305277957445,
        "tau": 0.06130822211279313,
    },
}

# Tesla fallback wheelbase (V0 passthrough).
_TESLA_L = 2.875


def _load_coeffs() -> dict:
    """Prefer coeffs.json if shipped alongside; fall back to embedded constants."""
    here = Path(__file__).resolve().parent
    cj = here / "coeffs.json"
    if cj.exists():
        try:
            with cj.open("r") as fh:
                data = json.load(fh)
            # the saved file stores extra fields (V1, V3) — pick the V2 fields.
            return {
                plat: {
                    "L": d["L"],
                    "g": d["g"],
                    "d0": d["d0"],
                    "K_us": d["K_us"],
                    "tau": d["tau"],
                }
                for plat, d in data.items()
                if all(k in d for k in ("L", "g", "d0", "K_us", "tau"))
            }
        except Exception:
            return _COEFFS
    return _COEFFS


def _first_order_lag(x: np.ndarray, dt: np.ndarray, tau: float) -> np.ndarray:
    """Discrete first-order lowpass with variable dt.

    y[k+1] = y[k] + min(dt[k]/tau, 1) * (x[k] - y[k])
    Length of dt must be len(x) - 1.
    """
    n = len(x)
    if n == 0:
        return x.copy()
    if tau <= 1e-6 or n == 1:
        return x.copy()
    y = np.empty(n, dtype=float)
    y[0] = x[0]
    a = np.clip(dt / tau, 0.0, 1.0)
    for k in range(n - 1):
        y[k + 1] = y[k] + a[k] * (x[k] - y[k])
    return y


def _predict_ford(t: np.ndarray, delta: np.ndarray, v: np.ndarray,
                  L: float, g: float, d0: float, K_us: float, tau: float) -> np.ndarray:
    yr_ss = g * (delta - d0) * v / (L + K_us * v * v)
    if len(t) < 2:
        return yr_ss
    dt = np.diff(t)
    return _first_order_lag(yr_ss, dt, tau)


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Euler integration matching _shared/traj_metrics.integrate_trajectory."""
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
    """Predict yaw rate (and x, y) for one segment.

    Args:
        sim_df: DataFrame with columns t_s, delta_road_rad, v_mps.
        platform: e.g. "FORD_MUSTANG_MACH_E_MK1".

    Returns:
        DataFrame aligned with sim_df.index, columns
        ``yaw_rate_pred_rads`` (required) and ``x_m``, ``y_m`` (optional).
    """
    coeffs = _load_coeffs()

    t = sim_df["t_s"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)

    if platform in coeffs:
        c = coeffs[platform]
        yr = _predict_ford(t, delta, v, c["L"], c["g"], c["d0"], c["K_us"], c["tau"])
    else:
        # Tesla and any unknown platform: V0 passthrough.
        L = _TESLA_L if platform == "TESLA_MODEL_3" else 2.984
        yr = (v / L) * np.tan(delta)

    x, y = _integrate_xy(t, v, yr)

    out = pd.DataFrame(
        {
            "yaw_rate_pred_rads": yr,
            "x_m": x,
            "y_m": y,
        },
        index=sim_df.index,
    )
    # Replace any non-finite values (shouldn't happen) with zeros.
    if not np.isfinite(out["yaw_rate_pred_rads"].to_numpy()).all():
        out["yaw_rate_pred_rads"] = np.nan_to_num(out["yaw_rate_pred_rads"].to_numpy(), nan=0.0, posinf=0.0, neginf=0.0)
    if not np.isfinite(out["x_m"].to_numpy()).all():
        out["x_m"] = np.nan_to_num(out["x_m"].to_numpy(), nan=0.0, posinf=0.0, neginf=0.0)
        out["y_m"] = np.nan_to_num(out["y_m"].to_numpy(), nan=0.0, posinf=0.0, neginf=0.0)
    return out
