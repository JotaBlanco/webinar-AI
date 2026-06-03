"""Final model — M4 (relaxation-length tire on V1 kinematic core).

Orthogonal rung-1 model. Holds V1's per-platform (g, L_eff, K_us, δ₀ policy)
fixed and replaces V1's time-domain first-order yaw lag (τ) with a
distance-domain first-order tire-force relaxation parameterised by σ
(meters per platform). Fitted σ values were grid-searched on the frozen
train split (sigma ∈ {0.05..2.2}); the yaw-RMSE-minimising sigma was
selected per platform.

This `predict(sim_df, platform) -> DataFrame` honours the operating-
contract input allowlist — only reads the eight declared sim-only columns.
Tesla / unknown platforms fall through to V0 passthrough.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


# Per-platform constants — copied verbatim from V1 (code/v1_baseline.py).
# M4 holds these fixed; only sigma is fitted.
V1_PARAMS: dict[str, dict] = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False,
        "delta0": 0.00133,
        "g": 0.863,
        "L_eff": 3.26,
        "K_us": 0.00350,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True,
        "delta0_fallback": -0.0001,
        "g": 0.891,
        "L_eff": 2.22,
        "K_us": 0.00150,
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True,
        "delta0_fallback": 0.0,
        "g": 0.938,
        "L_eff": 2.887,
        "K_us": 0.00289,
    },
}

V_MIN_M4 = 1.5  # m/s — below this, fall back to V0 passthrough
DT_FALLBACK = 0.01


def _safe_dt(t: np.ndarray) -> np.ndarray:
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt > 0, dt, DT_FALLBACK)
    return dt


def _per_segment_delta0(sim_df: pd.DataFrame, fallback: float,
                        yr_thresh: float = 0.03, v_thresh: float = 5.0,
                        min_rows: int = 50) -> float:
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _coeffs() -> dict:
    here = Path(__file__).resolve().parent
    p = here / "coeffs.json"
    if not p.is_file():
        return {}
    with p.open() as f:
        return json.load(f)


def _run(sim_df: pd.DataFrame, p: dict, sigma: float) -> np.ndarray:
    delta_row = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    dt = _safe_dt(t)

    if p["use_per_segment_delta0"]:
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0"]

    delta_eff = (delta_row - delta0) * p["g"]
    yr_demand = v * delta_eff / (p["L_eff"] + p["K_us"] * v * v)

    n = len(t)
    out = np.empty(n, dtype=float)
    out[0] = yr_demand[0] if v[0] >= V_MIN_M4 else yr_v0[0]
    yr_state = out[0]
    for i in range(1, n):
        if v[i] < V_MIN_M4 or sigma <= 0.0:
            yr_state = yr_v0[i]
            out[i] = yr_v0[i]
            continue
        alpha = 1.0 - np.exp(-v[i] * dt[i] / sigma)
        yr_state = yr_state + alpha * (yr_demand[i] - yr_state)
        out[i] = yr_state
    return out


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Operating-contract entry point.

    Returns DataFrame aligned with sim_df.index containing yaw_rate_pred_rads.
    """
    if platform not in V1_PARAMS:
        # Tesla and any unknown platform → V0 passthrough.
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = V1_PARAMS[platform]
    all_coeffs = _coeffs()
    sigma = float(all_coeffs.get(platform, {}).get("sigma", 0.5))
    yr = _run(sim_df, p, sigma)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
