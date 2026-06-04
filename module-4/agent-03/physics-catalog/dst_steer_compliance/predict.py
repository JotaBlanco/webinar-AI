"""dst_steer_compliance — steering compliance + Ackermann split on dst_lin.

Two effects added to dst_lin's state-space:

1. **Steering compliance.** The road-wheel angle the tyre actually sees
   is less than the commanded angle because the steering column / rack /
   tyre carcass deflects under lateral load:

       delta_effective = delta_commanded − K_compl · F_yf

   K_compl is the compliance coefficient (rad / N). For passenger cars,
   ~5e-6 to 5e-5 rad/N — meaning ~5 N of lateral force produces ~0.0001
   rad of "lost" steering.

2. **Ackermann split.** When the vehicle turns, the inner wheel needs a
   larger angle than the outer wheel (geometry: their turn radii differ
   by track_width). True Ackermann is exact; real vehicles use a
   compromise that introduces a slip-angle bias between L/R.

We model this as an effective single-track with a small angle offset
proportional to |delta|:

       delta_effective_axle = delta_commanded · (1 − k_ackermann · |delta|)

k_ackermann is the deviation from perfect Ackermann; positive = inner
wheel over-steered (parallel steering), negative = inner under-steered
(true Ackermann). Range ~ ±0.5.

State: [β, ψ̇] (same as dst_lin).
Fitted (per platform): {C_alpha_f, C_alpha_r, Iz, K_compl, k_ackermann}.

Cohort §8 evidence: V1's lag-τ is mis-modelling a structure non-linear
in (δ, dδ/dt, v). Steering compliance produces exactly that shape — the
effective δ depends on F_yf which depends on δ, with a non-linear coupling.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_MODEL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_MODEL_DIR.parent))

from _common import (  # noqa: E402
    PASSTHROUGH_PLATFORMS,
    V_FLOOR_MPS,
    get_platform_params,
    load_coeffs,
)


def _steer_step(state, delta_cmd, v, p, dt):
    """RK4 step with steering compliance + Ackermann correction."""
    m, Iz, lf, lr = p["m"], p["Iz"], p["lf"], p["lr"]
    Cf, Cr = p["C_alpha_f"], p["C_alpha_r"]
    K_compl = p.get("K_compl", 1e-5)
    k_ack   = p.get("k_ackermann", 0.0)
    # Ackermann correction (geometric, no F_y dependence).
    delta_ack = delta_cmd * (1.0 - k_ack * abs(delta_cmd))

    def f(s):
        beta, psi_dot = s
        if v < 1e-3:
            return np.zeros(2)
        # Closed-form solution of the steering-compliance fixed point:
        #   δ_eff = δ_ack - K_compl · F_yf
        #   F_yf  = -C_f · (β + l_f·ψ̇/v - δ_eff)
        # Substituting:
        #   δ_eff (1 + K·C_f) = δ_ack + K·C_f · (β + l_f·ψ̇/v)
        #   δ_eff = [δ_ack + K·C_f · (β + l_f·ψ̇/v)] / (1 + K·C_f)
        # No iteration; stable for any K·C_f > 0.
        KC = K_compl * Cf
        slip_kin_f = beta + lf * psi_dot / v
        delta_eff = (delta_ack + KC * slip_kin_f) / (1.0 + KC)
        alpha_f = slip_kin_f - delta_eff
        Fyf = -Cf * alpha_f
        alpha_r = beta - lr * psi_dot / v
        Fyr = -Cr * alpha_r
        beta_dot = (Fyf + Fyr) / (m * v) - psi_dot
        psidd    = (lf * Fyf - lr * Fyr) / Iz
        return np.array([beta_dot, psidd])

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
    n = len(t); psi_dot = np.zeros(n)
    state = np.array([0.0, yaw_v0[0] if n > 0 else 0.0])
    psi_dot[0] = state[1]
    for i in range(1, n):
        dt = max(t[i] - t[i - 1], 1e-3)
        if v[i] < V_FLOOR_MPS:
            state = np.array([0.0, yaw_v0[i]]); psi_dot[i] = yaw_v0[i]; continue
        state = _steer_step(state, float(delta[i]), float(v[i]), p, dt)
        if not np.all(np.isfinite(state)):
            state = np.array([0.0, yaw_v0[i]])
        psi_dot[i] = state[1]
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = psi_dot
    return out
