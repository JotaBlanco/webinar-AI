"""Final-model predict — M4 relaxation-length tire on V1 kinematic core.

Per-platform fitted sigma (relaxation length, meters); V1 understeer / δ₀ /
speed-clamp constants held verbatim from `code/v1_baseline.py`. Tesla and
unknown platforms return V0 passthrough.

Operating contract:
    predict(sim_df, platform) -> DataFrame with `yaw_rate_pred_rads` column
    aligned with `sim_df.index`. No truth columns read.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# V1 constants of record — inlined verbatim from code/v1_baseline.py.
# ---------------------------------------------------------------------------
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

# Speed floor below which we passthrough V0 (kinematic baseline). M4's
# relaxation filter has no 1/v singularity but very low speed is noisy.
V_MIN_M4 = 1.5


def _safe_dt(t: np.ndarray) -> np.ndarray:
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt > 0, dt, 0.01)
    return dt


def _per_segment_delta0(
    sim_df: pd.DataFrame,
    fallback: float = 0.0,
    yr_thresh: float = 0.03,
    v_thresh: float = 5.0,
    min_rows: int = 50,
) -> float:
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _run_relax(sim_df: pd.DataFrame, p: dict, sigma: float) -> np.ndarray:
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


def _load_coeffs() -> dict:
    coeffs_path = Path(__file__).parent / "coeffs.json"
    if coeffs_path.is_file():
        with coeffs_path.open() as f:
            return json.load(f)
    return {}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Operating-contract entry point used by the canonical grader."""
    coeffs = _load_coeffs().get(platform, {})

    if platform not in V1_PARAMS:
        # Tesla + any other platform: V0 passthrough.
        yr = sim_df["yaw_rate_pred_rads"].to_numpy().copy()
    else:
        sigma = float(coeffs.get("sigma", 0.5))
        yr = _run_relax(sim_df, V1_PARAMS[platform], sigma)

    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = yr
    return out
