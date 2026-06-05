"""dst_combined_slip — friction-circle longitudinal × lateral coupling. Rung 2.

The available tire force is bounded by a friction "circle" (more precisely an
ellipse):

    F_x² + F_y² ≤ (μ · F_z)²

When the tyre is consuming F_x (driving / braking force), it has less F_y
available — the physical mechanism behind the well-known "you can't brake
and turn at the limit" observation. Captures the coupling that dst_load
approximates indirectly (via F_z changes).

We approximate F_x per axle from a_long and a simple drive distribution:

    F_x_total = m · a_long
    F_x_f = α_drive · F_x_total   (drive distribution; default 0 = RWD or
                                   pure-rear braking; 0.5 = even split)
    F_x_r = (1-α_drive) · F_x_total

Per-axle lateral force is then constrained by the friction ellipse:

    F_y_max = sqrt(max((μ·F_z)² - F_x², 0))
    F_y(α) = clamp(-C_α · α, -F_y_max, F_y_max)

Fitted (per platform): {C_alpha_f, C_alpha_r, Iz, mu, alpha_drive}.

State: [β, ψ̇] (same as dst_lin).
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


def _combined_slip_step(state, delta, v, a_long, p, dt):
    """RK4 step with combined-slip friction-circle limit on per-axle F_y."""
    m, Iz, lf, lr, L = p["m"], p["Iz"], p["lf"], p["lr"], p["L"]
    Cf, Cr = p["C_alpha_f"], p["C_alpha_r"]
    mu = p.get("mu", 0.9)
    alpha_drive = float(np.clip(p.get("alpha_drive", 0.0), 0.0, 1.0))

    Fz_f = m * GRAVITY * lr / L
    Fz_r = m * GRAVITY * lf / L
    F_x_total = m * a_long
    F_x_f = alpha_drive * F_x_total
    F_x_r = (1.0 - alpha_drive) * F_x_total

    Fy_max_f = float(np.sqrt(max((mu * Fz_f) ** 2 - F_x_f ** 2, 0.0)))
    Fy_max_r = float(np.sqrt(max((mu * Fz_r) ** 2 - F_x_r ** 2, 0.0)))

    def f(s):
        beta, psi_dot = s
        if v < 1e-3:
            return np.zeros(2)
        alpha_f = beta + lf * psi_dot / v - delta
        alpha_r = beta - lr * psi_dot / v
        Fyf_lin = -Cf * alpha_f
        Fyr_lin = -Cr * alpha_r
        # Clip by available lateral force (friction-ellipse limit).
        Fyf = float(np.clip(Fyf_lin, -Fy_max_f, Fy_max_f))
        Fyr = float(np.clip(Fyr_lin, -Fy_max_r, Fy_max_r))
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
    a_long = sim_df.get("a_long_mps2", pd.Series(np.zeros(len(t)))).to_numpy()
    yaw_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    n = len(t); psi_dot = np.zeros(n)
    state = np.array([0.0, yaw_v0[0] if n > 0 else 0.0])
    psi_dot[0] = state[1]
    YAW_RATE_BOUND = 2.0  # rad/s; ~115°/s. Beyond this the model is in "spin" regime.
    for i in range(1, n):
        dt = max(t[i] - t[i - 1], 1e-3)
        if v[i] < V_FLOOR_MPS:
            state = np.array([0.0, yaw_v0[i]]); psi_dot[i] = yaw_v0[i]; continue
        state = _combined_slip_step(state, float(delta[i]), float(v[i]),
                                    float(a_long[i]), p, dt)
        if not np.all(np.isfinite(state)) or abs(state[1]) > YAW_RATE_BOUND:
            # Friction-circle clipped rear F_y to zero → mathematical spin. Fall
            # back to V0 for this sample and reset state.
            state = np.array([0.0, yaw_v0[i]])
        psi_dot[i] = state[1]
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = psi_dot
    return out
