"""Final-model predict function for lateral-fidelity challenge (agent-02).

Model class: per-platform extended kinematic single-track with:
  - Polynomial steering scale  g(δ) = g0 + g2 * δ²        (Mach-E shows clear nonlinearity)
  - Speed-dependent understeer K(v) = K0 + K1 * v
  - Constant steering offset   δ0  (small global bias)
  - First-order yaw-rate lag   τ
  - Per-segment delta-offset removal estimated from straight-driving rows
    using a_lat as the "going straight" indicator (no truth dependency).

Steady-state form:
    yr_ss(t) = v * (g(δ) * δ_corrected + δ0) / (L + K(v) * v²)

Transient form:
    yr_pred[k+1] = yr_pred[k] + (dt[k] / τ) * (yr_ss[k] - yr_pred[k])

Coefficients (coeffs.json) were fit on TRAIN segments only (whole-route hold-out, seed=42).

Tesla: V0 passthrough (no yaw_rate_meas_rads channel exists, so we have no truth to fit on).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Coefficient loading
# -----------------------------------------------------------------------------

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFFS_PATH.open("r", encoding="utf-8") as _fh:
    _COEFFS: dict = json.load(_fh)


# -----------------------------------------------------------------------------
# Core model
# -----------------------------------------------------------------------------

def _apply_first_order_lag(yr_ss: np.ndarray, dt: np.ndarray, tau: float) -> np.ndarray:
    """Apply a first-order lag with possibly non-uniform dt.

    yr_pred[k+1] = yr_pred[k] + (dt[k] / tau) * (yr_ss[k] - yr_pred[k])
    """
    n = len(yr_ss)
    if n == 0:
        return yr_ss.copy()
    y = np.empty(n, dtype=float)
    y[0] = yr_ss[0]
    if tau <= 1e-6:
        return yr_ss.copy()
    for k in range(n - 1):
        a = dt[k] / tau
        if a > 1.0:
            a = 1.0  # under-damped safety; dt[k]/tau should normally be ~0.3
        y[k + 1] = y[k] + a * (yr_ss[k] - y[k])
    return y


def _model_yr(delta: np.ndarray, v: np.ndarray, p: dict, dt: np.ndarray) -> np.ndarray:
    """Compute predicted yaw rate from corrected delta, v, and platform params p."""
    g_eff = p["g0"] + p["g2"] * delta * delta
    K_eff = p["K0"] + p["K1"] * v
    L = p["L"]
    # Avoid divide-by-zero (denom is always > 0 in practice, but be safe).
    denom = L + K_eff * v * v
    denom = np.where(denom > 1e-3, denom, 1e-3)
    yr_ss = v * (g_eff * delta + p["delta0"]) / denom
    return _apply_first_order_lag(yr_ss, dt, p["tau"])


def _estimate_delta_offset(delta: np.ndarray, v: np.ndarray, a_lat: np.ndarray) -> float:
    """Per-segment steering offset estimate from 'going-straight' rows.

    On rows where |a_lat| is small and v is reasonable, the vehicle is going
    nearly straight; measured delta on those rows reveals the small steering
    centring offset. Median for robustness; capped to ±0.02 rad.
    """
    mask = (np.abs(a_lat) < 0.3) & (v > 5.0)
    if mask.sum() < 100:
        return 0.0
    off = float(np.median(delta[mask]))
    if off > 0.02:
        off = 0.02
    elif off < -0.02:
        off = -0.02
    return off


# -----------------------------------------------------------------------------
# Public predict API
# -----------------------------------------------------------------------------

def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate for a single segment.

    Parameters
    ----------
    sim_df : pd.DataFrame
        Per-sample simulation inputs. Required columns: ``t_s``, ``v_mps``,
        ``delta_road_rad``. Optional: ``a_lat_meas_mps2`` (used for per-segment
        steering-offset estimation), ``yaw_rate_pred_rads`` (V0 fallback for
        platforms without fitted coefficients, e.g. Tesla).
    platform : str
        Platform identifier (e.g. "FORD_MUSTANG_MACH_E_MK1").

    Returns
    -------
    pd.DataFrame
        Aligned with ``sim_df.index``. Contains column ``yaw_rate_pred_rads``.
    """
    out = pd.DataFrame(index=sim_df.index)

    # Tesla / any platform with no fitted coefficients -> V0 passthrough.
    if platform not in _COEFFS:
        if "yaw_rate_pred_rads" in sim_df.columns:
            out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        else:
            out["yaw_rate_pred_rads"] = np.zeros(len(sim_df), dtype=float)
        return out

    p = _COEFFS[platform]

    # Required channels.
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)

    # Degenerate-segment fallback.
    if len(t) < 2:
        out["yaw_rate_pred_rads"] = np.zeros(len(sim_df), dtype=float)
        return out

    dt = np.diff(t)
    # Safety: dt must be positive. If anything is non-positive, fall back to V0.
    if np.any(dt <= 0):
        if "yaw_rate_pred_rads" in sim_df.columns:
            out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        else:
            out["yaw_rate_pred_rads"] = np.zeros(len(sim_df), dtype=float)
        return out

    # Per-segment steering offset (estimated from inputs only).
    if "a_lat_meas_mps2" in sim_df.columns:
        a_lat = sim_df["a_lat_meas_mps2"].to_numpy(dtype=float)
        off = _estimate_delta_offset(delta, v, a_lat)
    else:
        off = 0.0
    delta_c = delta - off

    y = _model_yr(delta_c, v, p, dt)
    out["yaw_rate_pred_rads"] = y
    return out


__all__ = ["predict"]
