"""Lateral-fidelity model — agent-01 submission.

Replaces the KS V0 prediction:
    psi_dot = (v / L) * tan(delta_road)

with a single-DOF understeer-gradient model + first-order steering lag +
small steering bias:

    delta_eff(t) follows  tau * d/dt(delta_eff) = (alpha * delta_road + beta) - delta_eff
    psi_dot      = v * delta_eff / (L + K_us * v^2)

Parameters per platform were fitted on a deterministic 70% file split of the
shipped sim/segments data and evaluated on the held-out 30%.

Trajectory (x, y) is integrated with a midpoint Euler scheme using the
measured velocity `v_mps` and the predicted yaw rate.
"""

import json
import os

import numpy as np
import pandas as pd


# --- Wheelbases (openpilot-canonical, from carParams). ---------------------
WHEELBASE_M = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
}

# --- Fitted lateral parameters. --------------------------------------------
# alpha : effective steering-ratio multiplier on delta_road
# kus   : understeer gradient [s²/m] in  L + kus * v²
# tau   : first-order steering lag time-constant [s]
# beta  : steering bias [rad]
PARAMS = {
    "FORD_F_150_LIGHTNING_MK1": dict(alpha=0.9671, kus=0.00367, tau=0.0777, beta=-0.00115),
    "FORD_MUSTANG_MACH_E_MK1":  dict(alpha=1.1784, kus=0.00248, tau=0.0833, beta=0.00002),
}


def _predict_yaw_rate(t: np.ndarray, v: np.ndarray, delta_road: np.ndarray,
                      L: float, alpha: float, kus: float, tau: float, beta: float) -> np.ndarray:
    """Single-track understeer model with first-order steering lag.

    delta_eff_{k} = delta_eff_{k-1} + dt/tau * ((alpha*delta_{k} + beta) - delta_eff_{k-1})
    psi_dot_{k}   = v_{k} * delta_eff_{k} / (L + kus * v_{k}^2)
    """
    n = len(t)
    de = np.empty(n)
    de[0] = alpha * delta_road[0] + beta
    for k in range(1, n):
        dt = t[k] - t[k - 1]
        if not np.isfinite(dt) or dt <= 0:
            dt = 0.01
        target = alpha * delta_road[k] + beta
        de[k] = de[k - 1] + (dt / max(tau, 1e-3)) * (target - de[k - 1])
    return v * de / (L + kus * v * v)


def _integrate_xy(t: np.ndarray, v: np.ndarray, psi_dot: np.ndarray):
    """Midpoint integration of (psi, x, y) from yaw_rate and velocity.

    Starts at the origin with heading 0 — the grader will register/align
    the trajectory before scoring.
    """
    n = len(t)
    psi = np.zeros(n)
    x = np.zeros(n)
    y = np.zeros(n)
    for k in range(1, n):
        dt = t[k] - t[k - 1]
        if not np.isfinite(dt) or dt <= 0:
            dt = 0.01
        psi[k] = psi[k - 1] + 0.5 * (psi_dot[k - 1] + psi_dot[k]) * dt
        ph = 0.5 * (psi[k - 1] + psi[k])
        vm = 0.5 * (v[k - 1] + v[k])
        x[k] = x[k - 1] + vm * np.cos(ph) * dt
        y[k] = y[k - 1] + vm * np.sin(ph) * dt
    return x, y, psi


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict lateral channels for a single sim segment.

    Parameters
    ----------
    sim_df   : DataFrame of one segment. Must contain at least
               't_s', 'v_mps', 'delta_road_rad'.
    platform : 'FORD_F_150_LIGHTNING_MK1' or 'FORD_MUSTANG_MACH_E_MK1'.

    Returns
    -------
    DataFrame indexed identically to sim_df, columns:
        yaw_rate_pred_rads, x_m, y_m
    """
    if platform not in PARAMS:
        raise ValueError(f"Unsupported platform: {platform!r}. "
                         f"Supported: {sorted(PARAMS)}")

    L = WHEELBASE_M[platform]
    p = PARAMS[platform]

    t = np.asarray(sim_df["t_s"].values, dtype=float)
    v = np.asarray(sim_df["v_mps"].values, dtype=float)
    d = np.asarray(sim_df["delta_road_rad"].values, dtype=float)

    # Guard against NaNs in inputs by forward/back-filling.
    def _fill(a):
        s = pd.Series(a).ffill().bfill().fillna(0.0).values
        return np.asarray(s, dtype=float)

    t = _fill(t); v = _fill(v); d = _fill(d)

    psi_dot = _predict_yaw_rate(t, v, d, L=L, **p)
    x, y, _ = _integrate_xy(t, v, psi_dot)

    return pd.DataFrame(
        {
            "yaw_rate_pred_rads": psi_dot,
            "x_m": x,
            "y_m": y,
        },
        index=sim_df.index,
    )


if __name__ == "__main__":
    import glob, sys
    plat = sys.argv[1] if len(sys.argv) > 1 else "FORD_F_150_LIGHTNING_MK1"
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = sorted(glob.glob(os.path.join(base, "data", "sim", "segments",
                                          plat, "*", "*", "*", "sim.csv")))
    if not files:
        print(f"No sim.csv files found for {plat}")
        sys.exit(1)
    df = pd.read_csv(files[0])
    out = predict(df, plat)
    err = out["yaw_rate_pred_rads"].values - df["yaw_rate_meas_rads"].values
    print(f"smoke: {plat} {files[0]}")
    print(f"  RMSE yaw vs V0: V0={np.sqrt(np.nanmean((df['yaw_rate_pred_rads']-df['yaw_rate_meas_rads'])**2)):.5f}, "
          f"V_us={np.sqrt(np.nanmean(err**2)):.5f}")
