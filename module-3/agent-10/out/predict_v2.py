"""V2 — KS + understeer + tau + per/global delta0, ALL three platforms fitted.

Reads coeffs from coeffs_fit.json (produced by fit2.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
COEFFS_PATH = ROOT / "out" / "coeffs_fit.json"

with open(COEFFS_PATH) as f:
    COEFFS = json.load(f)


def _per_segment_delta0(sim_df, fallback=0.0,
                        ax_thresh=0.3, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    a_lat = v * yr0
    delta_road = sim_df["delta_road_rad"].to_numpy()
    mask = (np.abs(a_lat) < ax_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(delta_road[mask]))


def _ks_pred(sim_df, p, delta0):
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in COEFFS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = COEFFS[platform]
    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_glob"])
    else:
        delta0 = p["delta0_glob"]
    yr = _ks_pred(sim_df, p, delta0)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
