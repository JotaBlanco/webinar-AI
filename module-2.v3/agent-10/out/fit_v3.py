"""Fit V3: cubic-in-delta + rate-lead understeer.

  psi_dot = v * (s_d*delta + c_d*delta^3 + tau_d*d(delta)/dt) / (L + K_us*v^2) + b
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-10")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import PLATFORM_SCHEMA  # noqa: E402

L_BY = {
    "TESLA_MODEL_3": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5": 3.00,
}
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def gather(platform: str, max_segments: int = 100, max_rows_per: int = 6000):
    seg_root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(p for p in seg_root.glob("**/sim.csv") if p.is_file())
    if max_segments and len(paths) > max_segments:
        rng = np.random.default_rng(0)
        paths = [paths[i] for i in sorted(rng.choice(len(paths), max_segments, replace=False))]
    tcol = PLATFORM_SCHEMA[platform]["truth_col"]
    D, V, DD, Y = [], [], [], []
    for p in paths:
        df = pd.read_csv(p)
        if tcol not in df.columns:
            continue
        t = df["t_s"].to_numpy(float)
        if len(t) < 10 or np.any(np.diff(t) <= 0):
            continue
        d = df["delta_road_rad"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        y = df[tcol].to_numpy(float)
        dd = np.gradient(d, t)
        m = v > 2.0
        d, v, dd, y = d[m], v[m], dd[m], y[m]
        if len(d) == 0:
            continue
        if len(d) > max_rows_per:
            s = len(d)//max_rows_per + 1
            d, v, dd, y = d[::s], v[::s], dd[::s], y[::s]
        D.append(d); V.append(v); DD.append(dd); Y.append(y)
    return (np.concatenate(D), np.concatenate(V), np.concatenate(DD), np.concatenate(Y))


def fit(platform: str):
    L = L_BY[platform]
    d, v, ddot, y = gather(platform)
    print(f"  {platform}: n={len(d)}")
    def model(p):
        s_d, c_d, tau_d, K_us, b = p
        denom = L + K_us*v*v
        return v*(s_d*d + c_d*d**3 + tau_d*ddot)/denom + b
    def loss(p):
        r = model(p) - y
        return float(np.mean(r*r))
    x0 = [1.0, 0.0, 0.0, 0.0, 0.0]
    res = minimize(loss, x0=x0, method="Nelder-Mead",
                    options={"xatol":1e-8,"fatol":1e-11,"maxiter":20000})
    s_d, c_d, tau_d, K_us, b = res.x
    rmse = np.sqrt(res.fun)
    print(f"    V3: s_d={s_d:.4f} c_d={c_d:.4f} tau_d={tau_d:.4f} K_us={K_us:.5f} b={b:+.5f}  rmse={rmse:.5f}")
    return {"s_d":float(s_d), "c_d":float(c_d), "tau_d":float(tau_d), "K_us":float(K_us), "b":float(b), "L":L}


def main():
    coeffs = {}
    for p in PLATFORMS:
        coeffs[p] = fit(p)
    coeffs["TESLA_MODEL_3"] = {"passthrough": True}
    (ROOT/"out"/"coeffs_v3.json").write_text(json.dumps(coeffs, indent=2))
    print("wrote coeffs_v3.json")


if __name__ == "__main__":
    main()
