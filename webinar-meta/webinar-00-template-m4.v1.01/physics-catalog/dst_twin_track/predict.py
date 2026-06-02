"""dst_twin_track — 4-wheel twin-track model with lateral load transfer.

Each axle has TWO wheels (left, right) with their own α and F_z. Lateral
load transfer in a corner shifts weight outward; tyres on the inside lose
F_z (and proportionally lose C_α), tyres on the outside gain it. This is
the model where Lightning's high CG + track width matters most.

State: [β, ψ̇] (same as dst_lin — the model doesn't add states, it just
splits the per-axle force into per-wheel forces and computes lateral load
transfer geometrically each step).

Per-wheel slip angle for the front L/R:
    α_fL = β + l_f·ψ̇/v - (δ + ackermann_correction_L)
    α_fR = β + l_f·ψ̇/v - (δ + ackermann_correction_R)

For simplicity the catalogue ships with **no Ackermann split** in the
twin-track baseline (a_correction_L = a_correction_R = 0); that puts
dst_twin_track squarely on the load-transfer effect. dst_steer_compliance
covers the Ackermann split separately.

Lateral load transfer (steady-state, per axle):
    ΔF_z_axle = k_LLT_axle · m · a_lat · h_cg / track_width

a_lat is approximated as v·ψ̇ (small-angle steady-state). k_LLT_f/k_LLT_r
are the roll-stiffness distribution between axles; sum to 1.

Fitted (per platform): {C_alpha_f, C_alpha_r, Iz, h_cg, track_width, k_LLT_f}.
k_LLT_r = 1 - k_LLT_f.
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


def _twin_track_step(state, delta, v, p, dt):
    """RK4 step for twin-track with lateral load transfer."""
    m, Iz, lf, lr, L = p["m"], p["Iz"], p["lf"], p["lr"], p["L"]
    Cf0, Cr0 = p["C_alpha_f"], p["C_alpha_r"]
    h_cg = p.get("h_cg", 0.55)
    track = max(p.get("track_width", 1.6), 0.5)
    k_LLT_f = float(np.clip(p.get("k_LLT_f", 0.5), 0.0, 1.0))
    k_LLT_r = 1.0 - k_LLT_f

    def f(s):
        beta, psi_dot = s
        if v < 1e-3:
            return np.zeros(2)
        # Approx steady-state lateral accel for load-transfer term.
        a_lat = v * psi_dot
        # Static per-wheel F_z (half of each axle).
        Fz_f_static = m * GRAVITY * lr / L / 2.0
        Fz_r_static = m * GRAVITY * lf / L / 2.0
        # Per-axle load transfer.
        dFz_f = k_LLT_f * m * a_lat * h_cg / track
        dFz_r = k_LLT_r * m * a_lat * h_cg / track
        # Per-wheel F_z: left = static - dFz/2, right = static + dFz/2.
        # (a_lat positive → vehicle yawing/turning left → load shifts right)
        Fz_fL = max(Fz_f_static - dFz_f / 2.0, 100.0)
        Fz_fR = max(Fz_f_static + dFz_f / 2.0, 100.0)
        Fz_rL = max(Fz_r_static - dFz_r / 2.0, 100.0)
        Fz_rR = max(Fz_r_static + dFz_r / 2.0, 100.0)
        # Per-wheel C_α scales with F_z (linear-load approximation).
        Cf_L = Cf0 * (Fz_fL / Fz_f_static) / 2.0  # half the axle stiffness per wheel
        Cf_R = Cf0 * (Fz_fR / Fz_f_static) / 2.0
        Cr_L = Cr0 * (Fz_rL / Fz_r_static) / 2.0
        Cr_R = Cr0 * (Fz_rR / Fz_r_static) / 2.0
        # Per-wheel slip angle (no Ackermann split in this baseline).
        alpha_f = beta + lf * psi_dot / v - delta
        alpha_r = beta - lr * psi_dot / v
        # Per-wheel lateral force.
        Fy_fL = -Cf_L * alpha_f
        Fy_fR = -Cf_R * alpha_f
        Fy_rL = -Cr_L * alpha_r
        Fy_rR = -Cr_R * alpha_r
        Fyf = Fy_fL + Fy_fR
        Fyr = Fy_rL + Fy_rR
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
            state = np.array([0.0, yaw_v0[i]])
            psi_dot[i] = yaw_v0[i]; continue
        state = _twin_track_step(state, float(delta[i]), float(v[i]), p, dt)
        if not np.all(np.isfinite(state)):
            state = np.array([0.0, yaw_v0[i]])
        psi_dot[i] = state[1]
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = psi_dot
    return out
