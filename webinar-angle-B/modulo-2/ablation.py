"""Ablation study for lateral KS fidelity (Module 2).

Reads existing Ford sim CSVs (which carry measured v, delta, and truth
yaw_rate / a_lat), and recomputes lateral predictions under several
variants of the KS model. Reports RMSE per variant per platform.

Run:
    python3 ablation.py
"""
from __future__ import annotations

import glob
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

sys.path.insert(0, "code")
from parameters import PARAM_BY_PLATFORM  # noqa: E402


PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]


def load_platform(plat: str) -> pd.DataFrame:
    files = sorted(glob.glob(f"data/sim/segments/{plat}/*/*/*/sim.csv"))
    dfs = []
    for fp in files:
        df = pd.read_csv(fp)
        df["__seg"] = fp
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


# --- Variant predictors --------------------------------------------------
# All variants are "static" lateral predictors: given v and delta (already
# clamped to measured), produce psi_dot and a_y. We do NOT re-integrate
# position/heading because the residual metrics only care about psi_dot
# and a_y, which the baseline ks_model also computes as point-wise
# derivations of v and delta.


def predict_ks(v: np.ndarray, delta: np.ndarray, L: float) -> tuple[np.ndarray, np.ndarray]:
    """Baseline KS: psi_dot = v/L * tan(delta); a_y = v * psi_dot."""
    psi_dot = (v / L) * np.tan(delta)
    a_y = v * psi_dot
    return psi_dot, a_y


def predict_ks_bias(v, delta, L, bias_psi_dot):
    psi_dot, a_y = predict_ks(v, delta, L)
    psi_dot = psi_dot + bias_psi_dot
    # Re-derive a_y from corrected psi_dot to stay consistent
    a_y = v * psi_dot
    return psi_dot, a_y


def predict_ks_steer_cal(v, delta, L, delta0, k):
    delta_eff = (delta - delta0) * k
    return predict_ks(v, delta_eff, L)


def predict_bicycle_understeer(v, delta, L, K_u, delta0=0.0, k=1.0):
    """Steady-state bicycle with understeer gradient K_u [rad / (m/s^2)].

    psi_dot = v * delta_eff / (L + K_u * v^2)
    a_y = v * psi_dot
    """
    delta_eff = (delta - delta0) * k
    psi_dot = v * delta_eff / (L + K_u * v * v)
    a_y = v * psi_dot
    return psi_dot, a_y


def predict_ks_lag(v, delta, L, tau_s, dt=0.02):
    """First-order lag on delta with time constant tau, then KS."""
    if tau_s <= 0:
        d_lag = delta.copy()
    else:
        alpha = dt / (tau_s + dt)
        d_lag = np.empty_like(delta)
        d_lag[0] = delta[0]
        for i in range(1, len(delta)):
            d_lag[i] = d_lag[i - 1] + alpha * (delta[i] - d_lag[i - 1])
    return predict_ks(v, d_lag, L)


# --- Calibration helpers ---------------------------------------------------

def fit_bias(yr_meas, yr_pred):
    """Best constant added to yr_pred to minimize RMSE (= mean residual)."""
    return float(np.mean(yr_meas - yr_pred))


def fit_steer_cal(v, delta, yr_meas, L):
    """Fit (delta0, k) by linear regression of yr_meas on (v/L)*tan(delta-d0)*k.

    Use small-angle linearization: tan(delta) ~ delta. Then
        yr_meas ≈ (v/L) * k * delta - (v/L) * k * delta0
    Let x1 = (v/L) * delta, x2 = -(v/L). Fit yr = a*x1 + b*x2.
    Then k = a, delta0 = b / a.
    """
    x1 = (v / L) * delta
    x2 = -(v / L)
    X = np.column_stack([x1, x2])
    a, b = np.linalg.lstsq(X, yr_meas, rcond=None)[0]
    k = float(a)
    delta0 = float(b / a) if abs(a) > 1e-9 else 0.0
    return delta0, k


def fit_understeer(v, delta, yr_meas, L, delta0=0.0, k=1.0):
    """Fit K_u by 1-D minimization. psi_dot = v*delta_eff/(L+K_u*v^2)."""
    from scipy.optimize import minimize_scalar
    delta_eff = (delta - delta0) * k

    def loss(Ku):
        pred = v * delta_eff / (L + Ku * v * v)
        return float(np.mean((yr_meas - pred) ** 2))

    res = minimize_scalar(loss, bracket=(-0.05, 0.0, 0.05))
    return float(res.x)


def fit_lag(v, delta, yr_meas, L, dt=0.02):
    from scipy.optimize import minimize_scalar

    def loss(tau):
        pred, _ = predict_ks_lag(v, delta, L, max(0.0, float(tau)), dt=dt)
        return float(np.mean((yr_meas - pred) ** 2))

    res = minimize_scalar(loss, bounds=(0.0, 0.5), method="bounded")
    return float(res.x)


# --- Metrics ---------------------------------------------------------------

def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def corr(a, b):
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def report_platform(plat: str) -> dict:
    df = load_platform(plat)
    p = PARAM_BY_PLATFORM[plat]
    L = p.L

    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    yr_meas = df["yaw_rate_meas_rads"].to_numpy()
    ay_meas = df["a_lat_meas_mps2"].to_numpy()

    out = {}

    # V0: CSV baseline (already computed by generate_simdata_ford)
    yr_p0 = df["yaw_rate_pred_rads"].to_numpy()
    ay_p0 = df["a_y_pred_mps2"].to_numpy()
    out["V0_baseline_csv"] = dict(
        yr_rmse_degs=np.degrees(rmse(yr_meas, yr_p0)),
        ay_rmse=rmse(ay_meas, ay_p0),
        yr_corr=corr(yr_meas, yr_p0),
        ay_corr=corr(ay_meas, ay_p0),
        yr_bias_degs=np.degrees(float(np.mean(yr_meas - yr_p0))),
    )

    # V1: Recompute KS from CSV inputs (sanity vs CSV)
    yr_p1, ay_p1 = predict_ks(v, delta, L)
    out["V1_ks_recompute"] = dict(
        yr_rmse_degs=np.degrees(rmse(yr_meas, yr_p1)),
        ay_rmse=rmse(ay_meas, ay_p1),
        yr_corr=corr(yr_meas, yr_p1),
        ay_corr=corr(ay_meas, ay_p1),
        yr_bias_degs=np.degrees(float(np.mean(yr_meas - yr_p1))),
    )

    # V2: KS + yaw-rate bias correction
    b = fit_bias(yr_meas, yr_p1)
    yr_p2, ay_p2 = predict_ks_bias(v, delta, L, b)
    out["V2_ks_plus_bias"] = dict(
        yr_rmse_degs=np.degrees(rmse(yr_meas, yr_p2)),
        ay_rmse=rmse(ay_meas, ay_p2),
        yr_corr=corr(yr_meas, yr_p2),
        ay_corr=corr(ay_meas, ay_p2),
        yr_bias_degs=np.degrees(float(np.mean(yr_meas - yr_p2))),
        params=dict(bias_psi_dot_rads=b, bias_psi_dot_degs=np.degrees(b)),
    )

    # V3: KS + steering calibration (offset + scale)
    d0, ksc = fit_steer_cal(v, delta, yr_meas, L)
    yr_p3, ay_p3 = predict_ks_steer_cal(v, delta, L, d0, ksc)
    out["V3_ks_plus_steer_cal"] = dict(
        yr_rmse_degs=np.degrees(rmse(yr_meas, yr_p3)),
        ay_rmse=rmse(ay_meas, ay_p3),
        yr_corr=corr(yr_meas, yr_p3),
        ay_corr=corr(ay_meas, ay_p3),
        yr_bias_degs=np.degrees(float(np.mean(yr_meas - yr_p3))),
        params=dict(delta0_rad=d0, k=ksc),
    )

    # V4: V3 + understeer-gradient term
    Ku = fit_understeer(v, delta, yr_meas, L, delta0=d0, k=ksc)
    yr_p4, ay_p4 = predict_bicycle_understeer(v, delta, L, Ku, delta0=d0, k=ksc)
    out["V4_bicycle_understeer"] = dict(
        yr_rmse_degs=np.degrees(rmse(yr_meas, yr_p4)),
        ay_rmse=rmse(ay_meas, ay_p4),
        yr_corr=corr(yr_meas, yr_p4),
        ay_corr=corr(ay_meas, ay_p4),
        yr_bias_degs=np.degrees(float(np.mean(yr_meas - yr_p4))),
        params=dict(delta0_rad=d0, k=ksc, K_u=Ku),
    )

    # V5: V4 + steering first-order lag
    tau = fit_lag(v, (delta - d0) * ksc, yr_meas, L)
    # apply lag to corrected delta_eff, then understeer model
    d_eff = (delta - d0) * ksc
    if tau > 0:
        alpha = 0.02 / (tau + 0.02)
        d_lag = np.empty_like(d_eff)
        d_lag[0] = d_eff[0]
        for i in range(1, len(d_eff)):
            d_lag[i] = d_lag[i - 1] + alpha * (d_eff[i] - d_lag[i - 1])
    else:
        d_lag = d_eff
    yr_p5 = v * d_lag / (L + Ku * v * v)
    ay_p5 = v * yr_p5
    out["V5_understeer_plus_lag"] = dict(
        yr_rmse_degs=np.degrees(rmse(yr_meas, yr_p5)),
        ay_rmse=rmse(ay_meas, ay_p5),
        yr_corr=corr(yr_meas, yr_p5),
        ay_corr=corr(ay_meas, ay_p5),
        yr_bias_degs=np.degrees(float(np.mean(yr_meas - yr_p5))),
        params=dict(delta0_rad=d0, k=ksc, K_u=Ku, tau_s=tau),
    )
    return out


def main() -> None:
    all_results = {}
    for plat in PLATFORMS:
        print(f"\n=== {plat} ===")
        res = report_platform(plat)
        all_results[plat] = res
        header = f"{'variant':28s} {'yr_RMSE(°/s)':>14s} {'ay_RMSE(m/s²)':>15s} {'yr_corr':>8s} {'ay_corr':>8s} {'yr_bias(°/s)':>14s}"
        print(header)
        print("-" * len(header))
        for k, v in res.items():
            print(f"{k:28s} {v['yr_rmse_degs']:>14.3f} {v['ay_rmse']:>15.3f} {v['yr_corr']:>8.3f} {v['ay_corr']:>8.3f} {v['yr_bias_degs']:>14.3f}")
            if "params" in v:
                print(f"    params: {v['params']}")
    return all_results


if __name__ == "__main__":
    main()
