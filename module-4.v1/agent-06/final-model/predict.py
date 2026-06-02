"""V3 — V1 (KS + understeer + lag + per-segment delta0) PLUS a 10-feature ridge
residual-learner head fit per platform on V1's signed residual.

Cohort-evidenced pattern (m4 cohort findings §2 + §4): per-platform bias is
absorbed into the ridge intercept; a low-rank linear approximation of V1's
empirical residual recovers further yaw error nonlinearly in (delta, v, ay).

Tesla falls through to V0 passthrough — no truth channel exists.

Inputs honour the operating-contract allowlist (only the 8 declared columns).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_HERE = Path(__file__).resolve().parent


PLATFORM_PARAMS_V1 = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False,
        "delta0": 0.00133,
        "g": 0.863,
        "L_eff": 3.26,
        "K_us": 0.00350,
        "tau": 0.060,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True,
        "delta0_fallback": -0.0001,
        "g": 0.891,
        "L_eff": 2.22,
        "K_us": 0.00150,
        "tau": 0.069,
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True,
        "delta0_fallback": 0.0,
        "g": 0.938,
        "L_eff": 2.887,
        "K_us": 0.00289,
        "tau": 0.062,
    },
}


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _v1_yawrate(sim_df: pd.DataFrame, platform: str) -> np.ndarray:
    """The V1 baseline yaw-rate prediction."""
    p = PLATFORM_PARAMS_V1[platform]
    delta0 = (
        _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
        if p["use_per_segment_delta0"]
        else p["delta0"]
    )
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def _features(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    """10-feature design matrix used by the per-platform ridge head."""
    v = sim_df["v_mps"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    # np.gradient is well-defined for non-uniform t.
    ddelta = np.gradient(delta, t)
    ay = v * yr_v1  # allowlist lateral-accel proxy (no a_lat truth read)
    return np.column_stack([
        yr_v1,
        delta,
        delta * v,
        v,
        v * v,
        ddelta,
        ay,
        ay * v,
        yr_v1 * v,
        np.sign(delta) * delta * delta,
    ])


_COEFFS_PATH = _HERE / "ridge_coeffs.json"
with open(_COEFFS_PATH) as _f:
    _COEFFS = json.load(_f)


def _residual_correction(sim_df: pd.DataFrame, platform: str, yr_v1: np.ndarray) -> np.ndarray:
    c = _COEFFS.get(platform)
    if c is None:
        return np.zeros_like(yr_v1)
    mu = np.asarray(c["mu"])
    sd = np.asarray(c["sd"])
    w = np.asarray(c["w"])
    b = float(c["intercept"])
    F = _features(sim_df, yr_v1)
    Fs = (F - mu) / sd
    return Fs @ w + b


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Integrate trajectory from yaw rate + speed (forward Euler)."""
    dt = np.diff(t, prepend=t[0])
    psi = np.cumsum(yr * dt) - yr[0] * dt[0]
    x = np.cumsum(v * np.cos(psi) * dt) - v[0] * np.cos(psi[0]) * dt[0]
    y = np.cumsum(v * np.sin(psi) * dt) - v[0] * np.sin(psi[0]) * dt[0]
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate (and integrated x, y) for one segment.

    Args:
        sim_df: input-only DataFrame with the 8 allowlist columns.
        platform: platform tag.

    Returns:
        DataFrame aligned with sim_df.index containing yaw_rate_pred_rads
        (and x_m, y_m).
    """
    if platform not in PLATFORM_PARAMS_V1:
        # Tesla / unknown — V0 passthrough.
        yr = sim_df["yaw_rate_pred_rads"].to_numpy().astype(float)
    else:
        yr_v1 = _v1_yawrate(sim_df, platform)
        resid = _residual_correction(sim_df, platform, yr_v1)
        yr = yr_v1 - resid

    t = sim_df["t_s"].to_numpy().astype(float)
    v = sim_df["v_mps"].to_numpy().astype(float)
    x, y = _integrate_xy(t, v, yr)
    return pd.DataFrame(
        {"yaw_rate_pred_rads": yr, "x_m": x, "y_m": y},
        index=sim_df.index,
    )
