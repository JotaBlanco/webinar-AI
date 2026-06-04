"""dst_load — dst_lin + longitudinal-accel load transfer on per-axle slip stiffness.

Under longitudinal acceleration `a_long` (positive = accel, negative = brake),
weight shifts between front and rear axles:

    ΔF_z = m · a_long · h_cg / L
    F_z_f = m·g·lr/L  -  ΔF_z      (front unloads under accel; loads under brake)
    F_z_r = m·g·lf/L  +  ΔF_z

Cornering stiffness scales with F_z (linear-load approximation, valid in
the small-slip regime that dst_lin lives in):

    C_α(F_z) = C_α0 · F_z / F_z_nominal

Fitted (per platform): {C_alpha_f0, C_alpha_r0, Iz, h_cg}.
Lightning expected to benefit the most — h_cg is large, segments with hard
braking into corner show the biggest cohort §2/§9 residual on Lightning.
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
    step_rk4_tyre,
)


def _load_tyre(alpha: float, Fz: float, p: dict, which: str) -> float:
    """Linear tyre with F_z-scaled cornering stiffness.

    The nominal F_z per axle is the static load (no a_long); current F_z
    is set by step_rk4_tyre using a_long and h_cg. C_α0 is the stiffness
    at the nominal F_z.
    """
    m, lf, lr, L = p["m"], p["lf"], p["lr"], p["L"]
    if which == "front":
        Fz_nom = m * GRAVITY * lr / L
        C0 = p["C_alpha_f"]
    else:
        Fz_nom = m * GRAVITY * lf / L
        C0 = p["C_alpha_r"]
    Fz_safe = max(float(Fz), 100.0)
    Cf_eff = C0 * (Fz_safe / max(Fz_nom, 100.0))
    return -Cf_eff * alpha


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform in PASSTHROUGH_PLATFORMS:
        return sim_df[["yaw_rate_pred_rads"]].copy()

    coeffs = load_coeffs(_MODEL_DIR)
    p = get_platform_params(platform, coeffs)

    t     = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    v     = sim_df["v_mps"].to_numpy()
    a_long = sim_df.get("a_long_mps2", pd.Series(np.zeros(len(t)))).to_numpy()
    yaw_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()

    n = len(t); psi_dot = np.zeros(n)
    state = np.array([0.0, yaw_v0[0] if n > 0 else 0.0])
    psi_dot[0] = state[1]
    p_local = dict(p)

    for i in range(1, n):
        dt = max(t[i] - t[i - 1], 1e-3)
        if v[i] < V_FLOOR_MPS:
            state = np.array([0.0, yaw_v0[i]])
            psi_dot[i] = yaw_v0[i]; continue
        p_local["a_long_mps2"] = float(a_long[i])
        state = step_rk4_tyre(state, float(delta[i]), float(v[i]), p_local, dt,
                              tyre_fn=_load_tyre)
        if not np.all(np.isfinite(state)):
            state = np.array([0.0, yaw_v0[i]])
        psi_dot[i] = state[1]

    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = psi_dot
    return out
