"""dynamic-st — rung-1 linear dynamic single-track model.

State: (vy, yr). Inputs: vx (=v_mps), delta_road (with V1's per-segment delta0
correction kept in front). Tyres are linear: F_y = C_alpha * slip.

Equations:
  alpha_f = (delta - (vy + l_f * yr) / vx)
  alpha_r = -(vy - l_r * yr) / vx
  F_yf = C_af * alpha_f ;  F_yr = C_ar * alpha_r
  vy_dot = (F_yf + F_yr) / m - vx * yr
  yr_dot = (l_f * F_yf - l_r * F_yr) / Iz

Integrator: explicit RK4 with vx clamped to vx_min for stability.
Coefficients per platform live in coeffs.json; Tesla/unknown -> V0 passthrough.
"""
from __future__ import annotations
import json, pathlib, sys
import numpy as np
import pandas as pd

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[1] / "code"))
from v1_baseline import predict_v1, PLATFORM_PARAMS_V1, _per_segment_delta0  # noqa: E402

COEFFS = json.loads((_HERE / "coeffs.json").read_text())

VX_MIN = 1.0  # m/s

def _delta0_for(sim_df, platform):
    p = PLATFORM_PARAMS_V1.get(platform)
    if p is None:
        return 0.0
    if p["use_per_segment_delta0"]:
        return _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    return p["delta0"]


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in COEFFS:
        return predict_v1(sim_df, platform)
    c = COEFFS[platform]
    m, Iz, lf, lr = c["m"], c["Iz"], c["l_f"], c["l_r"]
    Caf, Car = c["C_af"], c["C_ar"]
    g = c["g"]
    a_post, b_post = c.get("a", 1.0), c.get("b", 0.0)

    delta0 = _delta0_for(sim_df, platform)
    delta = (sim_df["delta_road_rad"].to_numpy(dtype=float) - delta0) * g
    vx_raw = sim_df["v_mps"].to_numpy(dtype=float)
    vx = np.maximum(vx_raw, VX_MIN)
    t = sim_df["t_s"].to_numpy(dtype=float)
    N = len(t)

    vy = np.zeros(N)
    yr = np.zeros(N)
    # init yr[0] from V0 baseline for warm start (allowlist column)
    yr0 = float(sim_df["yaw_rate_pred_rads"].iloc[0]) if "yaw_rate_pred_rads" in sim_df.columns else 0.0
    yr[0] = yr0

    def deriv(vy_, yr_, dlt, vxi):
        alpha_f = dlt - (vy_ + lf * yr_) / vxi
        alpha_r = -(vy_ - lr * yr_) / vxi
        Fyf = Caf * alpha_f
        Fyr = Car * alpha_r
        vy_dot = (Fyf + Fyr) / m - vxi * yr_
        yr_dot = (lf * Fyf - lr * Fyr) / Iz
        return vy_dot, yr_dot

    SUB_DT = 0.0025  # 2.5 ms sub-step for RK4 stability at openpilot C_alpha priors
    VY_CAP = 50.0    # m/s — physical clamp; protects against integrator excursion
    YR_CAP = 2.0     # rad/s
    for i in range(N - 1):
        dt = t[i+1] - t[i]
        if dt <= 0 or dt > 0.5:
            vy[i+1] = vy[i]; yr[i+1] = yr[i]; continue
        n_sub = max(1, int(np.ceil(dt / SUB_DT)))
        h = dt / n_sub
        vy_k = vy[i]; yr_k = yr[i]
        for s in range(n_sub):
            frac0 = s / n_sub; frac1 = (s+1) / n_sub
            d0 = delta[i] + frac0*(delta[i+1] - delta[i])
            d1 = delta[i] + frac1*(delta[i+1] - delta[i])
            dm = 0.5*(d0+d1)
            vx0 = vx[i] + frac0*(vx[i+1]-vx[i])
            vx1 = vx[i] + frac1*(vx[i+1]-vx[i])
            vxm = 0.5*(vx0+vx1)
            k1vy, k1yr = deriv(vy_k, yr_k, d0, vx0)
            k2vy, k2yr = deriv(vy_k + 0.5*h*k1vy, yr_k + 0.5*h*k1yr, dm, vxm)
            k3vy, k3yr = deriv(vy_k + 0.5*h*k2vy, yr_k + 0.5*h*k2yr, dm, vxm)
            k4vy, k4yr = deriv(vy_k + h*k3vy, yr_k + h*k3yr, d1, vx1)
            vy_k = vy_k + h/6.0 * (k1vy + 2*k2vy + 2*k3vy + k4vy)
            yr_k = yr_k + h/6.0 * (k1yr + 2*k2yr + 2*k3yr + k4yr)
            if abs(vy_k) > VY_CAP: vy_k = np.sign(vy_k)*VY_CAP
            if abs(yr_k) > YR_CAP: yr_k = np.sign(yr_k)*YR_CAP
        vy[i+1] = vy_k; yr[i+1] = yr_k

    yr = a_post * yr + b_post
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
