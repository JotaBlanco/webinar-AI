"""Final model — M4 relaxation-length tire on V1 kinematic core.

Rung: orthogonal (distance-domain phase lag replaces V1's time-domain `tau`).

Why this is the shipped model
-----------------------------
On the frozen route-grouped dev split (402 segments):

    V1 baseline        : yaw_rmse = 0.005430 rad/s,  cte_rmse = 52.215 m
    M4 (fit sigma)     : yaw_rmse = 0.005634 rad/s,  cte_rmse = 52.105 m
    M1 linear-dynamic  : yaw_rmse = 0.009192 rad/s,  cte_rmse = 116.889 m
    M2 fiala-tire-st   : yaw_rmse = 0.009207 rad/s,  cte_rmse = 116.890 m
    M5 friction-circle : yaw_rmse = 0.009187 rad/s,  cte_rmse = 116.890 m

M1/M2/M5 all degrade catastrophically because their dynamic ODE doesn't
get the steady-state cornering compliance right at the priors and we
didn't have time to refit (l_f/l_r/I_z/C_alpha all interact). M4 wins
because it *keeps* V1's already-tuned steady-state curve and only
replaces the phase-lag mechanism with a physically more correct
(distance-domain) one.

Coeffs
------
`coeffs.json` carries one fitted parameter per platform — `sigma`
(meters), the tire relaxation length — plus the held V1 constants
(g, L_eff, K_us, delta0 policy) inlined for self-containment.

Tesla returns V0 passthrough (no truth column).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_HERE = Path(__file__).resolve().parent


def _load_coeffs() -> dict:
    with (_HERE / "coeffs.json").open() as f:
        return json.load(f)


COEFFS = _load_coeffs()

# Local low-speed floor (below this we fall back to V0 passthrough).
V_MIN = 1.5


def _per_segment_delta0(
    sim_df: pd.DataFrame,
    fallback: float = 0.0,
    yr_thresh: float = 0.03,
    v_thresh: float = 5.0,
    min_rows: int = 50,
) -> float:
    """Median straight-driving steering offset for this segment (V1 rule)."""
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _safe_dt(t: np.ndarray) -> np.ndarray:
    dt = np.diff(t, prepend=t[0])
    dt[dt <= 0] = 0.02
    return dt


def _run_relax(sim_df: pd.DataFrame, p: dict, sigma: float) -> np.ndarray:
    """V1 steady-state yaw + distance-domain relaxation in place of tau."""
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
    out[0] = yr_demand[0] if v[0] >= V_MIN else yr_v0[0]
    state = out[0]

    for i in range(1, n):
        if v[i] < V_MIN or sigma <= 0.0:
            state = yr_v0[i]
            out[i] = yr_v0[i]
            continue
        alpha = 1.0 - np.exp(-v[i] * dt[i] / sigma)
        state = state + alpha * (yr_demand[i] - state)
        out[i] = state
    return out


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Operating-contract entry point called by the canonical grader.

    Reads ONLY the 8 sim-only columns (t_s, delta_wheel_deg, delta_road_rad,
    v_mps, a_long_mps2, accel_pedal_pct, brake_pressed, yaw_rate_pred_rads).
    Returns a DataFrame with `yaw_rate_pred_rads` aligned with sim_df.index.
    """
    plat_cfg = COEFFS.get(platform)
    if plat_cfg is None:
        # Unknown platform / Tesla: V0 passthrough.
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )

    sigma = float(plat_cfg["sigma"])
    p = {
        "use_per_segment_delta0": bool(plat_cfg["use_per_segment_delta0"]),
        "delta0": float(plat_cfg.get("delta0", 0.0)),
        "delta0_fallback": float(plat_cfg.get("delta0_fallback", 0.0)),
        "g": float(plat_cfg["g"]),
        "L_eff": float(plat_cfg["L_eff"]),
        "K_us": float(plat_cfg["K_us"]),
    }
    yr = _run_relax(sim_df, p, sigma)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
