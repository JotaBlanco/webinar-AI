"""V1 baseline — the kinematic-single-track + understeer + first-order-lag + per-segment δ₀ model.

V1 is the converged rung-0 ceiling from the m3.v2 cohort: 10 of 10 agents shipped
some variant of this; six shipped its coefficients to 3 decimal places. Canonical
grades for the typical V1 shape were +56.6% yaw / +72.2% CTE vs the V0 baseline
(`yaw_rate_pred_rads` passthrough). Fitting tighter coefficients on this shape
buys at most a basis point or two on either KPI.

V1 is exposed here so module-3.v3 agents have it as a known, scored floor — not
as a recipe to copy, but as the thing to beat with a structurally-different model.

Use:

    from code.v1_baseline import predict_v1, PLATFORM_PARAMS_V1
    out = predict_v1(sim_df, platform)   # DataFrame aligned with sim_df.index

`predict_v1` honours the operating-contract allowlist — uses only the 8 declared
columns. Tesla falls through to V0 passthrough (no truth channel).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


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


def predict_v1(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in PLATFORM_PARAMS_V1:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
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
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)


# Backwards-compatible alias for code paths that call the function as `predict`.
predict = predict_v1
