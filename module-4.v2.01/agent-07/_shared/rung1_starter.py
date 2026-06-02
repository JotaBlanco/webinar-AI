"""Rung-1 starter: linear dynamic single-track (bicycle) with slip angles.

Drop-in scaffold to remove the "Euler-instability risk in 45 min" objection
that blocked every m3.v3 rung-1 attempt (references/m4-cohort-findings.md §1, §7).

What's done for you:
- State-space form: states [β, ψ̇] (sideslip, yaw rate), input δ (road wheel angle).
- RK4 integration (numerically stable across the v range in this dataset).
- Per-platform parameter slot for {m, Iz, lf, lr, C_αf, C_αr}.
- A 30-line fit loop using scipy that fits {C_αf, C_αr, Iz} against pooled
  yaw RMSE on dev — the three parameters cohort §1 + §7 evidence says you
  MUST fit (carParams values caused every cohort failure).

What you have to do:
- Decide whether to fit globally or per-platform (start global; per-platform
  often hurts on this dataset).
- Decide whether to bound Iz (recommended: [0.6, 1.6] × prior to prevent
  collapse).
- Decide whether to add a regime gate (use V1 below threshold, dynamic above).
- Inspect identifiability: if `C_αf` and `C_αr` fit to a ratio not their
  absolute values, your data lacks the excitation to separate them.

This file is in `_shared/` so you can edit it freely. It is NOT in the
operating-contract-pinned `code/` tree — it's your scratch.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Defaults — initial guesses, not gospel. Cohort §1 + §7: fitting these is the
# whole point; carParams values blew up every rung-1 attempt.
DEFAULTS = {
    "m":      1850.0,   # kg
    "Iz":     2800.0,   # kg·m² — FIT this
    "lf":     1.40,     # m
    "lr":     1.50,     # m
    "C_alpha_f": 80000.0,  # N/rad — FIT this
    "C_alpha_r": 80000.0,  # N/rad — FIT this
    "g":      9.81,
}


def _step_rk4(state, delta, v, params, dt):
    """One RK4 step of the linear dynamic single-track.

    State: [beta, psi_dot]   beta = sideslip angle at CG, psi_dot = yaw rate.
    Input: delta (rad), v (m/s).
    """
    def f(s):
        beta, psi_dot = s
        m = params["m"]; Iz = params["Iz"]
        lf = params["lf"]; lr = params["lr"]
        Cf = params["C_alpha_f"]; Cr = params["C_alpha_r"]
        if v < 1e-3:
            return np.array([0.0, 0.0])
        # Slip angles, small-angle linearised tyres.
        alpha_f = beta + lf * psi_dot / v - delta
        alpha_r = beta - lr * psi_dot / v
        Fyf = -Cf * alpha_f
        Fyr = -Cr * alpha_r
        beta_dot = (Fyf + Fyr) / (m * v) - psi_dot
        psidd    = (lf * Fyf - lr * Fyr) / Iz
        return np.array([beta_dot, psidd])
    k1 = f(state)
    k2 = f(state + 0.5 * dt * k1)
    k3 = f(state + 0.5 * dt * k2)
    k4 = f(state + dt * k3)
    return state + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)


def predict_rung1(sim_df: pd.DataFrame, platform: str, params: dict | None = None) -> pd.DataFrame:
    """Rung-1 dynamic single-track predict() following the operating contract.

    Reads only allowlist columns. Falls back to V0 passthrough when |delta|
    or v is tiny (avoids singular regime). Tesla → V0 passthrough.
    """
    p = {**DEFAULTS, **(params or {})}
    out = sim_df[["yaw_rate_pred_rads"]].copy()

    if platform == "TESLA_MODEL_3":
        return out  # No truth; ship passthrough.

    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    n = len(t)
    psi_dot = np.zeros(n)
    state = np.array([0.0, 0.0])
    for i in range(1, n):
        dt = max(t[i] - t[i-1], 1e-3)
        if v[i] < 2.0:
            state = np.array([0.0, sim_df["yaw_rate_pred_rads"].iloc[i]])
            psi_dot[i] = sim_df["yaw_rate_pred_rads"].iloc[i]
            continue
        state = _step_rk4(state, delta[i], v[i], p, dt)
        psi_dot[i] = state[1]
    out["yaw_rate_pred_rads"] = psi_dot
    return out


def fit_calpha_and_iz(predict_factory, segment_paths, *, platform: str,
                      bounds=((20000, 200000), (20000, 200000), (1500, 4500))):
    """Fit {C_αf, C_αr, Iz} on dev against pooled yaw RMSE.

    This is the minimum that worked nowhere in m3.v3 because nobody fit it —
    the cohort kept using carParams values. Fitting these three parameters is
    the difference between "rung-1 looks worse" and "rung-1 might actually work".
    """
    from scipy.optimize import minimize  # local import — scipy is in pyproject

    def loss(x):
        Cf, Cr, Iz = x
        params = {"C_alpha_f": Cf, "C_alpha_r": Cr, "Iz": Iz}
        # Score against dev — replace with your loaded dev segments + truth.
        # SKELETON: integrate predict_rung1 across segment_paths, return pooled RMSE.
        ...
        return 0.0  # replace

    x0 = [DEFAULTS["C_alpha_f"], DEFAULTS["C_alpha_r"], DEFAULTS["Iz"]]
    result = minimize(loss, x0, method="Nelder-Mead",
                      bounds=bounds, options={"xatol": 1e-2, "fatol": 1e-6, "maxiter": 200})
    return {
        "C_alpha_f": result.x[0],
        "C_alpha_r": result.x[1],
        "Iz":        result.x[2],
        "loss":      result.fun,
        "converged": result.success,
        "stuck_on_bound": _stuck(result.x, bounds),
    }


def _stuck(x, bounds, tol=0.02):
    flags = []
    for xi, (lo, hi) in zip(x, bounds):
        span = hi - lo
        if (xi - lo) / span < tol or (hi - xi) / span < tol:
            flags.append(True)
        else:
            flags.append(False)
    return any(flags)
