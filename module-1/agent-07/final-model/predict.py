"""Final lateral-fidelity model for agent-07.

Submission contract (per orchestrator):

    predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame

Returns a DataFrame aligned with `sim_df.index` containing at minimum a column
`yaw_rate_pred_rads` (rad/s). Optionally `x_m`, `y_m` (m). If x/y are omitted
the grader integrates from yaw_rate using measured velocity.

================================================================================
Methodology — short version
================================================================================

V0 (baseline shipped in `code/ks_model.py`):
    psi_dot_KS = (v / L) * tan(delta_road)

V0 is a pure kinematic single-track ("driving school") model. It is exact at
zero lateral acceleration but increasingly under-predicts curvature as
a_y = v * psi_dot grows — because the real vehicle understeers (tyres slip,
heading lags wheels).

V1 (this submission): steady-state understeer-corrected bicycle yaw rate.
This is the canonical first step up the CommonRoad fidelity ladder when you
have the openpilot ST-rung parameters (m, l_f, l_r, C_alpha_f, C_alpha_r).
The closed-form steady-state cornering relation is:

    psi_dot_SS = v * delta / ( L + K_us * v^2 )

with the understeer gradient (in s^2/m, equivalently 1/(m/s)^2):

    K_us = (m / L) * ( l_r / C_alpha_f  -  l_f / C_alpha_r )

A Mach-E with the openpilot ST parameters has K_us > 0 (understeer), so for a
given delta the predicted yaw rate at speed is *smaller* than KS — this is
the dominant V0 error at higher a_y, which is exactly where V0 is observed to
bleed RMSE on Ford data.

Two practical refinements on top of V1:

  (a) `tan(delta)` is kept for small-angle consistency with the KS form
      (numerically equivalent to `delta` for |delta| << 1, but degrades
      gracefully at large rack angles). The substitution is:
          psi_dot = v * tan(delta) / ( L + K_us * v^2 )
  (b) A low-speed guard. At v -> 0 the steady-state form is undefined for the
      KS-form denominator only in the trivial sense; we explicitly fall back
      to psi_dot = 0 when v < V_FLOOR (default 0.5 m/s) to avoid noise
      amplification at standstill.

Why I did not include a fitted steering-bias / delay term:
  My harness did not permit running Python (the orchestrator's sandbox blocked
  even `python3 -c`), so I could not measure residual bias or the optimal
  steer-to-yaw lag against the truth channels. The V1 closed form is *fully
  parameterised by the openpilot-canonical numbers already in parameters.py*,
  so it is shipped here without empirical tuning. Hook points are provided
  (`STEER_BIAS_RAD`, `STEER_LAG_S`) so a calibrated version could be dropped
  in.

x_m / y_m: not returned. Letting the grader integrate from predicted yaw and
measured velocity ensures the trajectory uses the same `v_mps` channel the
grader already has, removing one source of disagreement.

================================================================================
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Platform parameter table (mirrors code/parameters.py, baked in so this
# module has zero side-effects on import path of `code/`).
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class _Params:
    L: float            # wheelbase [m]
    m: float            # mass [kg]
    l_f: float          # CoG -> front axle [m]
    l_r: float          # CoG -> rear axle [m]
    C_alpha_f: float    # front cornering stiffness [N/rad]
    C_alpha_r: float    # rear cornering stiffness [N/rad]

    @property
    def K_us(self) -> float:
        """Understeer gradient in s^2/m.

        K_us = m / L * ( l_r / Cf  -  l_f / Cr )

        Positive => understeer (real-vehicle yaw rate < KS yaw rate at speed).
        """
        return (self.m / self.L) * (self.l_r / self.C_alpha_f
                                    - self.l_f / self.C_alpha_r)


# openpilot-canonical numbers from code/parameters.py
_PARAMS_BY_PLATFORM: dict[str, _Params] = {
    "TESLA_MODEL_3": _Params(
        L=2.875, m=2035.0, l_f=1.4375, l_r=1.4375,
        C_alpha_f=222_882, C_alpha_r=352_332,
    ),
    "FORD_MUSTANG_MACH_E_MK1": _Params(
        L=2.984, m=2336.0, l_f=1.3130, l_r=1.671,
        C_alpha_f=286_551, C_alpha_r=355_912,
    ),
    "FORD_F_150_LIGHTNING_MK1": _Params(
        L=3.70, m=3084.0, l_f=1.628, l_r=2.072,
        C_alpha_f=378_307, C_alpha_r=469_878,
    ),
}


# Hook for an empirically-fitted steering-rack bias (rad). Default 0 — would
# normally be fit per-platform by minimising mean yaw residual at low a_y.
STEER_BIAS_RAD: dict[str, float] = {
    "TESLA_MODEL_3":             0.0,
    "FORD_MUSTANG_MACH_E_MK1":   0.0,
    "FORD_F_150_LIGHTNING_MK1":  0.0,
}

# Hook for empirically-fitted lag in seconds between measured delta and the
# yaw rate it produces. Default 0 — would be fit by cross-correlating residual
# against d(delta)/dt.
STEER_LAG_S: dict[str, float] = {
    "TESLA_MODEL_3":             0.0,
    "FORD_MUSTANG_MACH_E_MK1":   0.0,
    "FORD_F_150_LIGHTNING_MK1":  0.0,
}

V_FLOOR = 0.5  # m/s — below this, predict zero yaw to avoid noise.


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _shift(arr: np.ndarray, n: int) -> np.ndarray:
    """Shift `arr` by integer samples `n` (positive => delay), edge-padding."""
    if n == 0:
        return arr
    out = np.empty_like(arr)
    if n > 0:
        out[:n] = arr[0]
        out[n:] = arr[:-n]
    else:
        n = -n
        out[:-n] = arr[n:]
        out[-n:] = arr[-1]
    return out


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict lateral response for a single segment.

    Parameters
    ----------
    sim_df : pd.DataFrame
        At minimum must contain columns `t_s`, `v_mps`, and `delta_road_rad`.
        (These are the standard columns in `data/sim/segments/.../sim.csv`.)
    platform : str
        One of {TESLA_MODEL_3, FORD_MUSTANG_MACH_E_MK1, FORD_F_150_LIGHTNING_MK1}.

    Returns
    -------
    pd.DataFrame
        Aligned with sim_df.index. Column `yaw_rate_pred_rads` (rad/s).
        x_m / y_m intentionally not returned (grader integrates them).
    """
    if platform not in _PARAMS_BY_PLATFORM:
        raise ValueError(f"unknown platform: {platform!r}")
    p = _PARAMS_BY_PLATFORM[platform]
    K_us = p.K_us

    # Fetch channels. Robust to either snake_case (sim.csv) or alternative
    # naming, in case the grader rewrites columns.
    if "delta_road_rad" in sim_df.columns:
        delta = sim_df["delta_road_rad"].to_numpy(dtype=float, copy=True)
    elif "delta_rad" in sim_df.columns:
        delta = sim_df["delta_rad"].to_numpy(dtype=float, copy=True)
    else:
        raise KeyError("predict(): no delta_road_rad / delta_rad column")

    if "v_mps" in sim_df.columns:
        v = sim_df["v_mps"].to_numpy(dtype=float, copy=True)
    elif "v" in sim_df.columns:
        v = sim_df["v"].to_numpy(dtype=float, copy=True)
    else:
        raise KeyError("predict(): no v_mps / v column")

    # Optional bias / lag corrections.
    bias = STEER_BIAS_RAD.get(platform, 0.0)
    if bias:
        delta = delta - bias

    lag_s = STEER_LAG_S.get(platform, 0.0)
    if lag_s and "t_s" in sim_df.columns:
        t = sim_df["t_s"].to_numpy(dtype=float)
        if len(t) > 1:
            dt = float(np.median(np.diff(t)))
            n_shift = int(round(lag_s / dt)) if dt > 0 else 0
            if n_shift:
                delta = _shift(delta, n_shift)

    # V1 — understeer-corrected steady-state bicycle yaw rate.
    # Uses tan(delta) for graceful behaviour at large rack angles; for the
    # small-angle regime this collapses to v*delta/(L+K_us*v^2).
    denom = p.L + K_us * (v ** 2)
    psi_dot = v * np.tan(delta) / denom

    # Low-speed guard
    psi_dot = np.where(v < V_FLOOR, 0.0, psi_dot)

    out = pd.DataFrame(
        {"yaw_rate_pred_rads": psi_dot},
        index=sim_df.index,
    )
    return out


# -----------------------------------------------------------------------------
# Self-test (does not run on import)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # Synthetic sanity: constant v, constant delta -> steady-state yaw rate
    # should match (1) closed-form V1 expression and (2) be smaller in
    # magnitude than the pure-KS prediction for any platform with K_us > 0.
    for plat, P in _PARAMS_BY_PLATFORM.items():
        N = 50
        v0, d0 = 25.0, math.radians(2.0)
        df = pd.DataFrame({
            "t_s": np.arange(N) * 0.02,
            "v_mps": np.full(N, v0),
            "delta_road_rad": np.full(N, d0),
        })
        y = predict(df, plat)["yaw_rate_pred_rads"].iloc[-1]
        y_ks = v0 * math.tan(d0) / P.L
        print(f"{plat:30s}  K_us={P.K_us:.4e}  KS={y_ks:.4f}  V1={y:.4f}  "
              f"reduction={100*(y_ks-y)/y_ks:+.1f}%")
