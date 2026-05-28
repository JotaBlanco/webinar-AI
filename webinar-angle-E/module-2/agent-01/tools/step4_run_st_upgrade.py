#!/usr/bin/env python3
"""step4_run_st_upgrade.py — V1 (KS recalib), V2 (ST prior), V3 (ST fit). Per-regime RMSE."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

V_MIN_ST = 2.0
C_BOUNDS = (5e4, 5e5)


def rmse(arr):
    a = np.asarray(arr, dtype=float)
    a = a[np.isfinite(a)]
    return float("nan") if a.size == 0 else float(np.sqrt(np.mean(a ** 2)))


def per_regime(df, resid):
    out = {"overall": rmse(resid)}
    for r in ("straight", "steady", "transient"):
        out[r] = rmse(resid[df["regime"].to_numpy() == r])
    return out


def linear_st(v, delta, L, l_f, l_r, m, C_f, C_r):
    K_us = (m * (l_r * C_r - l_f * C_f)) / (L ** 2 * C_f * C_r)
    safe = v >= V_MIN_ST
    psi = v * delta / (L * (1.0 + K_us * v ** 2))
    fallback = (v / L) * np.tan(delta)
    return np.where(safe, psi, fallback)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, type=Path)
    ap.add_argument("--platform", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--code-root", default="code", type=Path)
    args = ap.parse_args()

    sys.path.insert(0, str(args.code_root.resolve()))
    from parameters import PARAM_BY_PLATFORM  # type: ignore
    _P = PARAM_BY_PLATFORM[args.platform]
    if hasattr(_P, "__getitem__"):
        P = _P
    else:
        P = {k: getattr(_P, k) for k in ("L", "l_f", "l_r", "m", "C_alpha_f", "C_alpha_r")}

    df = pd.read_parquet(args.inp)
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    meas = df["yaw_rate_meas_rads"].to_numpy()

    # V1 — KS recalibrated + per-segment yaw-gyro bias on straight rows.
    L = float(P["L"])
    ks_pred = (v / L) * np.tan(delta)
    df["__ks_pred__"] = ks_pred
    bias = np.zeros(len(df))
    for src, sub in df.groupby("__source__"):
        mask_straight = sub["regime"].to_numpy() == "straight"
        if mask_straight.any():
            b = float(np.mean(sub.loc[mask_straight, "__ks_pred__"].to_numpy()
                              - sub.loc[mask_straight, "yaw_rate_meas_rads"].to_numpy()))
            bias[df["__source__"] == src] = b
    v1_pred = ks_pred - bias
    v1_resid = v1_pred - meas

    # V2 — Linear ST with prior Cα.
    v2_pred = linear_st(v, delta, L, float(P["l_f"]), float(P["l_r"]),
                        float(P["m"]), float(P["C_alpha_f"]), float(P["C_alpha_r"]))
    v2_resid = v2_pred - meas

    # V3 — Linear ST with fit Cα.
    from scipy.optimize import minimize

    def loss(params):
        cf, cr = params
        pred = linear_st(v, delta, L, float(P["l_f"]), float(P["l_r"]), float(P["m"]), cf, cr)
        e = pred - meas
        e = e[np.isfinite(e)]
        return float(np.sqrt(np.mean(e ** 2))) if e.size else float("inf")

    x0 = [1.5e5, 1.5e5]
    res = minimize(loss, x0, method="L-BFGS-B", bounds=[C_BOUNDS, C_BOUNDS])
    cf, cr = float(res.x[0]), float(res.x[1])
    pegged = (abs(cf - C_BOUNDS[1]) < 1.0) or (abs(cr - C_BOUNDS[1]) < 1.0)
    v3_pred = linear_st(v, delta, L, float(P["l_f"]), float(P["l_r"]),
                        float(P["m"]), cf, cr)
    v3_resid = v3_pred - meas

    out = {
        "V1": per_regime(df, v1_resid),
        "V2": per_regime(df, v2_resid),
        "V3": per_regime(df, v3_resid),
        "V3_fit": {"C_alpha_f": cf, "C_alpha_r": cr, "pegged": pegged},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"V1/V2/V3 → {args.out}: V1.overall={out['V1']['overall']:.5f} "
          f"V2.overall={out['V2']['overall']:.5f} V3.overall={out['V3']['overall']:.5f} "
          f"pegged={pegged}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
