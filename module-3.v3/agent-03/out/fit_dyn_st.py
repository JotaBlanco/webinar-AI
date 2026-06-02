"""Fit a linear dynamic single-track per platform.

State: (vy, yr). Input: (delta_road, vx=v_meas).
  vy_dot = (F_yf + F_yr)/m - vx * yr
  yr_dot = (a*F_yf - b*F_yr)/Iz
  F_yf = C_af * (delta - (vy + a*yr)/vx)
  F_yr = C_ar * (-(vy - b*yr)/vx)

We use SEMI-IMPLICIT (backward) Euler for stability at 20 ms with stiff C_a:
  Linear system:
    [vy_new]   [1 + dt*(C_af+C_ar)/(m*vx),  dt*(vx + (a*C_af - b*C_ar)/(m*vx))] [vy_new]   [vy + dt*delta*C_af/m]
    [yr_new] = solved per-step.

Actually: discretise state-space x_dot = A(vx) x + B(vx) u, then x_new = (I - dt*A)^-1 (x + dt*B*u).

Per-segment delta0 from V1 spec applied to delta before model.

Fit: {C_af, C_ar, Iz_scale, g_scale} on yaw RMSE. m, a, b from V1 priors.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
data_full = ROOT / "data" / "sim" / "segments"


# Priors (mass, a, b, Iz) from openpilot/typical values.
# a + b = L (wheelbase).
PRIORS = {
    "FORD_F_150_LIGHTNING_MK1": dict(m=3000.0, L=3.7, a_frac=0.46, Iz=8000.0),
    "FORD_MUSTANG_MACH_E_MK1":  dict(m=2150.0, L=2.99, a_frac=0.46, Iz=4500.0),
    "HYUNDAI_IONIQ_5":          dict(m=2100.0, L=3.0, a_frac=0.46, Iz=4500.0),
}


def per_segment_delta0(df, fallback, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(df.loc[mask, "delta_road_rad"].median())


def predict_dyn(df, params, prior):
    """Run dynamic single-track."""
    g_steer, C_af, C_ar, Iz_mul, delta0_global, delta0_fallback, use_per_seg = params
    if use_per_seg:
        delta0 = per_segment_delta0(df, delta0_fallback)
    else:
        delta0 = delta0_global
    delta = (df["delta_road_rad"].to_numpy() - delta0) * g_steer
    v = df["v_mps"].to_numpy()
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.clip(dt, 0.005, 0.1)
    m = prior["m"]
    L = prior["L"]
    a = prior["a_frac"] * L
    b = L - a
    Iz = prior["Iz"] * Iz_mul

    n = len(v)
    yr = np.zeros(n)
    vy = np.zeros(n)
    # Warm start
    yr[0] = df["yaw_rate_pred_rads"].to_numpy()[0]
    # Clamp vx for stability
    vx = np.maximum(v, 1.0)
    for i in range(1, n):
        d = delta[i]
        vxi = vx[i]
        dti = dt[i]
        # Continuous-time A, B
        # dvy/dt = (C_af + C_ar)/(m*vx) * (-vy) + ((-a*C_af + b*C_ar)/(m*vx) - vx) * yr + (C_af/m)*d
        # dyr/dt = (-a*C_af + b*C_ar)/(Iz*vx) * (-vy) ... let's be careful with signs.
        # Standard bicycle linearised about straight:
        #   F_yf = C_af * (d - (vy + a*yr)/vx)
        #   F_yr = C_ar * (- (vy - b*yr)/vx)
        # dvy/dt = (F_yf + F_yr)/m - vx*yr
        #        = (C_af + C_ar)/m * (-vy/vx) + ((-a*C_af + b*C_ar)/(m*vx))*yr + (C_af/m)*d - vx*yr
        # dyr/dt = (a*F_yf - b*F_yr)/Iz
        #        = (a*C_af - b*C_ar)/(Iz)*(-vy/vx ... hmm let's expand)
        #   a*F_yf = a*C_af*d - a*C_af*(vy + a*yr)/vx
        #   b*F_yr = -b*C_ar*(vy - b*yr)/vx
        #   a*F_yf - b*F_yr = a*C_af*d - a*C_af*(vy+a*yr)/vx + b*C_ar*(vy - b*yr)/vx
        #                    = a*C_af*d + (-a*C_af + b*C_ar)*vy/vx + (-a^2*C_af - b^2*C_ar)*yr/vx
        A11 = -(C_af + C_ar) / (m * vxi)
        A12 = (-a * C_af + b * C_ar) / (m * vxi) - vxi
        A21 = (-a * C_af + b * C_ar) / (Iz * vxi)
        A22 = -(a * a * C_af + b * b * C_ar) / (Iz * vxi)
        B1 = C_af / m
        B2 = a * C_af / Iz
        # Backward Euler: (I - dt*A) x_new = x + dt*B*d
        M11 = 1 - dti * A11
        M12 = -dti * A12
        M21 = -dti * A21
        M22 = 1 - dti * A22
        det = M11 * M22 - M12 * M21
        if abs(det) < 1e-12:
            vy[i] = vy[i-1]
            yr[i] = yr[i-1]
            continue
        r1 = vy[i-1] + dti * B1 * d
        r2 = yr[i-1] + dti * B2 * d
        vy[i] = (M22 * r1 - M12 * r2) / det
        yr[i] = (-M21 * r1 + M11 * r2) / det
    return yr


CFG = {
    "FORD_F_150_LIGHTNING_MK1": dict(use_per_seg=False, delta0_init=0.00133),
    "FORD_MUSTANG_MACH_E_MK1": dict(use_per_seg=True, delta0_init=-0.0001),
    "HYUNDAI_IONIQ_5": dict(use_per_seg=True, delta0_init=0.0),
}


def loss_for_plat(plat):
    cfg = CFG[plat]
    prior = PRIORS[plat]
    segs = []
    for sim_csv in sorted((data_full / plat).rglob("sim.csv")):
        df = pd.read_csv(sim_csv)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        segs.append(df)

    def loss(x):
        g_steer, log_Caf, log_Car, log_Iz_mul = x
        C_af = float(np.exp(log_Caf))
        C_ar = float(np.exp(log_Car))
        Iz_mul = float(np.exp(log_Iz_mul))
        if not (0.3 < g_steer < 1.5):
            return 1e9
        if not (1e4 < C_af < 5e5) or not (1e4 < C_ar < 5e5):
            return 1e9
        if not (0.2 < Iz_mul < 5.0):
            return 1e9
        params = (g_steer, C_af, C_ar, Iz_mul,
                  cfg["delta0_init"] if not cfg["use_per_seg"] else 0.0,
                  cfg["delta0_init"] if cfg["use_per_seg"] else 0.0,
                  cfg["use_per_seg"])
        sumsq = 0.0
        n = 0
        try:
            for df in segs:
                yr = predict_dyn(df, params, prior)
                r = df["yaw_rate_meas_rads"].to_numpy() - yr
                if not np.all(np.isfinite(r)):
                    return 1e9
                sumsq += float(np.sum(r * r))
                n += len(r)
        except Exception:
            return 1e9
        return sumsq / n

    return loss


def main():
    out = {}
    for plat in PLATFORMS:
        print(f"\n--- {plat} ---")
        loss = loss_for_plat(plat)
        # initial: g~V1 g, C_af = C_ar = 150000, Iz_mul=1
        x0 = [0.88, np.log(150000.0), np.log(150000.0), np.log(1.0)]
        l0 = loss(x0)
        print(f"  initial MSE={l0:.6e} RMSE={np.sqrt(l0):.5f}")
        res = minimize(loss, x0, method="Nelder-Mead", options={"xatol":1e-4, "fatol":1e-9, "maxiter":250})
        print(f"  final MSE={res.fun:.6e} RMSE={np.sqrt(res.fun):.5f} iters={res.nit}")
        g_steer, log_Caf, log_Car, log_Iz_mul = res.x
        out[plat] = {
            "g_steer": float(g_steer),
            "C_af": float(np.exp(log_Caf)),
            "C_ar": float(np.exp(log_Car)),
            "Iz_mul": float(np.exp(log_Iz_mul)),
            "prior": PRIORS[plat],
            "use_per_segment_delta0": CFG[plat]["use_per_seg"],
            "delta0_global": CFG[plat]["delta0_init"] if not CFG[plat]["use_per_seg"] else 0.0,
            "delta0_fallback": CFG[plat]["delta0_init"] if CFG[plat]["use_per_seg"] else 0.0,
        }
    (ROOT / "models" / "dynamic_st" / "coeffs.json").write_text(json.dumps(out, indent=2))
    print("Saved coeffs.json")


if __name__ == "__main__":
    main()
