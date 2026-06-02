"""V3 — V1 + richer ridge residual head. Loads from coefs_v3/."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_THIS = Path(__file__).resolve().parent
_COEF_DIR = _THIS / "coefs_v3"

_PLATFORM_PARAMS_V1 = {
    "FORD_F_150_LIGHTNING_MK1": {"use_per_segment_delta0": False, "delta0": 0.00133,
                                 "g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060},
    "FORD_MUSTANG_MACH_E_MK1":  {"use_per_segment_delta0": True, "delta0_fallback": -0.0001,
                                 "g": 0.891, "L_eff": 2.22, "K_us": 0.00150, "tau": 0.069},
    "HYUNDAI_IONIQ_5":          {"use_per_segment_delta0": True, "delta0_fallback": 0.0,
                                 "g": 0.938, "L_eff": 2.887, "K_us": 0.00289, "tau": 0.062},
}

_FEAT_NAMES = ["bias","v","v2","delta","delta_v","delta2","delta2_v",
               "dd","dd_v","ay","ay_absay","sgn_delta","abs_delta_v"]


def _per_segment_delta0(sim_df, fallback=0.0):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
    if int(mask.sum()) < 50:
        return fallback
    return float(np.median(sim_df.loc[mask, "delta_road_rad"]))


def _predict_v1(sim_df, platform):
    p = _PLATFORM_PARAMS_V1[platform]
    delta0 = (_per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
              if p["use_per_segment_delta0"] else p["delta0"])
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


def _features(sim_df, yr_v1):
    v = sim_df["v_mps"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    dd = np.clip(np.gradient(delta, t) if len(t) >= 2 else np.zeros_like(delta), -5.0, 5.0)
    ay = v * yr_v1
    sgn = np.where(np.abs(delta) > 0.01, np.sign(delta), 0.0)
    return np.column_stack([
        np.ones_like(v),
        v, v*v,
        delta, delta*v, delta*delta, delta*delta*v,
        dd, dd*v,
        ay, ay*np.abs(ay),
        sgn, np.abs(delta)*v,
    ])


def _load_coefs(platform):
    p = _COEF_DIR / f"{platform}.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return np.array([data["coefs"][n] for n in _FEAT_NAMES], dtype=float)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in _PLATFORM_PARAMS_V1:
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                            index=sim_df.index)
    yr_v1 = _predict_v1(sim_df, platform)
    w = _load_coefs(platform)
    if w is None:
        yr = yr_v1
    else:
        X = _features(sim_df, yr_v1)
        yr = yr_v1 + X @ w
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
