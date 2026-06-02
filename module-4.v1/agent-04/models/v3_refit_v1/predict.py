"""V3 = V1 with refit (g, K_us, tau, delta0) per platform.

Same model structure, tighter coefficients fit via Nelder-Mead pooled yaw-RMSE.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_PARAMS = json.loads((_HERE / "params.json").read_text())

# V1 base params for L_eff and per-segment-delta0 policy (we only override g,K_us,tau,delta0)
_BASE = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False, "L_eff": 3.26,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True, "L_eff": 2.22,
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True, "L_eff": 2.887,
    },
}


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    m = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(m.sum()) < min_rows:
        return fallback
    return float(np.median(sim_df.loc[m, "delta_road_rad"]))


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    base = _BASE.get(platform)
    fit = _PARAMS.get(platform)
    if base is None or fit is None:
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                            index=sim_df.index)
    delta0 = (
        _per_segment_delta0(sim_df, fallback=fit["delta0_fallback"])
        if base["use_per_segment_delta0"]
        else fit["delta0_fallback"]
    )
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * fit["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (base["L_eff"] + fit["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (fit["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
