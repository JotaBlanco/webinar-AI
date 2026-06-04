"""V2 — add a steering-rate lead term:

    yaw_pred = v * (delta + tau * d_delta_dt) / (L + Kus * v^2) + bias

where d_delta_dt is the time-derivative of delta_road. The lead constant tau
compensates for the steering-measurement delay relative to yaw-rate truth.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-06")
DATA = ROOT / "data" / "sim" / "segments"

PLATFORMS = [
    "FORD_F_150_LIGHTNING_MK1",
    "FORD_MUSTANG_MACH_E_MK1",
    "HYUNDAI_IONIQ_5",
]

L_PRIOR = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "HYUNDAI_IONIQ_5": 3.0,
}


def gather(platform):
    paths = sorted((DATA / platform).glob("*/*/*/sim.csv"))
    deltas, vs, yr_meas, ddt = [], [], [], []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["t_s", "delta_road_rad", "v_mps", "yaw_rate_meas_rads"])
        except Exception:
            continue
        t = df["t_s"].to_numpy()
        if len(t) < 5 or np.any(np.diff(t) <= 0):
            continue
        d = df["delta_road_rad"].to_numpy()
        v = df["v_mps"].to_numpy()
        yr = df["yaw_rate_meas_rads"].to_numpy()
        dd = np.gradient(d, t)
        mask = v > 2.0
        deltas.append(d[mask])
        vs.append(v[mask])
        yr_meas.append(yr[mask])
        ddt.append(dd[mask])
    return {
        "delta": np.concatenate(deltas),
        "v": np.concatenate(vs),
        "yr": np.concatenate(yr_meas),
        "ddt": np.concatenate(ddt),
    }


def predict_v2(d, dd, v, L, Kus, tau, bias):
    return v * (d + tau * dd) / (L + Kus * v * v) + bias


def fit(platform):
    data = gather(platform)
    d, dd, v, y = data["delta"], data["ddt"], data["v"], data["yr"]
    L0 = L_PRIOR[platform]

    def loss(params):
        L, Kus, tau, bias = params
        pred = predict_v2(d, dd, v, L, Kus, tau, bias)
        return float(np.mean((pred - y) ** 2))

    x0 = [L0, 0.0, 0.0, 0.0]
    bounds = [(1.5, 5.5), (-0.05, 0.05), (-0.5, 0.5), (-0.02, 0.02)]
    res = minimize(loss, x0, bounds=bounds, method="L-BFGS-B")
    return {
        "platform": platform,
        "L": float(res.x[0]),
        "Kus": float(res.x[1]),
        "tau": float(res.x[2]),
        "bias": float(res.x[3]),
        "rmse_fit": float(np.sqrt(res.fun)),
        "n": int(len(d)),
        "converged": bool(res.success),
    }


if __name__ == "__main__":
    out = {}
    for p in PLATFORMS:
        print(f"fitting {p} ...")
        r = fit(p)
        print(r)
        out[p] = r
    with open(ROOT / "out" / "coeffs_v2.json", "w") as f:
        json.dump(out, f, indent=2)
    print("wrote coeffs_v2.json")
