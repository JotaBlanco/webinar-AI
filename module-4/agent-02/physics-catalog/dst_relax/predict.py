"""dst_relax — linear-tyre dynamic single-track with tyre relaxation length.

Tyre force does not build up instantaneously. The classic relaxation model
adds a first-order lag with time constant τ(v) = σ / v, where σ is the
tyre relaxation length (carcass property; ~0.3–0.7 m for passenger tyres).

State: [β, ψ̇, F_yf, F_yr] — added per-axle lateral force state.
ODE:
    F_yf_dot = (v / σ_f) · (F_yf_steady - F_yf)
    F_yr_dot = (v / σ_r) · (F_yr_steady - F_yr)
    F_y*_steady = -C_α* · α*           (linear tyre as in dst_lin)

Fitted (per platform): {C_alpha_f, C_alpha_r, Iz, sigma_relax}.
sigma_relax shared front/rear by default (5 vs 6 fit params trade-off).

Cohort §8 evidence: V1's lag-τ is mis-modelling a structure. dst_relax says
that structure is the tyre carcass's relaxation — and a v-dependent τ
naturally produces the observed (δ, dδ/dt, v) coupling that V1's
constant-τ couldn't capture.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_MODEL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_MODEL_DIR.parent))

from _common import (  # noqa: E402
    GRAVITY,
    PASSTHROUGH_PLATFORMS,
    V_FLOOR_MPS,
    get_platform_params,
    load_coeffs,
)


def _step_rk4_relax(state: np.ndarray, delta: float, v: float, p: dict, dt: float) -> np.ndarray:
    """One RK4 step with relaxed tyre forces. State: [β, ψ̇, F_yf, F_yr]."""
    Cf, Cr = p["C_alpha_f"], p["C_alpha_r"]
    sigma = max(p.get("sigma_relax", 0.5), 0.05)
    m, Iz, lf, lr = p["m"], p["Iz"], p["lf"], p["lr"]

    def f(s):
        beta, psi_dot, Fyf, Fyr = s
        if v < 1e-3:
            return np.zeros(4)
        alpha_f = beta + lf * psi_dot / v - delta
        alpha_r = beta - lr * psi_dot / v
        Fyf_ss = -Cf * alpha_f
        Fyr_ss = -Cr * alpha_r
        # Relaxation: F dot = (v/σ) (F_ss - F)
        Fyf_dot = (v / sigma) * (Fyf_ss - Fyf)
        Fyr_dot = (v / sigma) * (Fyr_ss - Fyr)
        beta_dot = (Fyf + Fyr) / (m * v) - psi_dot
        psidd    = (lf * Fyf - lr * Fyr) / Iz
        return np.array([beta_dot, psidd, Fyf_dot, Fyr_dot])

    k1 = f(state)
    k2 = f(state + 0.5 * dt * k1)
    k3 = f(state + 0.5 * dt * k2)
    k4 = f(state + dt * k3)
    return state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform in PASSTHROUGH_PLATFORMS:
        return sim_df[["yaw_rate_pred_rads"]].copy()

    coeffs = load_coeffs(_MODEL_DIR)
    p = get_platform_params(platform, coeffs)

    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    yaw_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()

    n = len(t)
    psi_dot = np.zeros(n)
    # State: [β, ψ̇, F_yf, F_yr]
    state = np.array([0.0, yaw_v0[0] if n > 0 else 0.0, 0.0, 0.0])
    psi_dot[0] = state[1]

    for i in range(1, n):
        dt = max(t[i] - t[i - 1], 1e-3)
        if v[i] < V_FLOOR_MPS:
            state = np.array([0.0, yaw_v0[i], 0.0, 0.0])
            psi_dot[i] = yaw_v0[i]
            continue
        state = _step_rk4_relax(state, float(delta[i]), float(v[i]), p, dt)
        if not np.all(np.isfinite(state)):
            state = np.array([0.0, yaw_v0[i], 0.0, 0.0])
        psi_dot[i] = state[1]

    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = psi_dot
    return out
