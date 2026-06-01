"""V3 — V2 with low-pass-filtered derivative.

Use a simple exponential moving average of d(delta)/dt with time constant
`tau_lpf` (~5-10 samples at 50 Hz). Refit (L, Kus, tau, bias) with the smoothed
derivative.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.signal import butter, filtfilt

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


def gather(platform, lpf_hz=3.0):
    paths = sorted((DATA / platform).glob("*/*/*/sim.csv"))
    deltas, vs, yr_meas, ddt = [], [], [], []
    b, a = butter(2, lpf_hz / 25.0, btype="low")  # 50 Hz nyquist=25
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["t_s", "delta_road_rad", "v_mps", "yaw_rate_meas_rads"])
        except Exception:
            continue
        t = df["t_s"].to_numpy()
        if len(t) < 30 or np.any(np.diff(t) <= 0):
            continue
        d = df["delta_road_rad"].to_numpy()
        v = df["v_mps"].to_numpy()
        yr = df["yaw_rate_meas_rads"].to_numpy()
        dd = np.gradient(d, t)
        try:
            dd_smooth = filtfilt(b, a, dd)
        except Exception:
            dd_smooth = dd
        mask = v > 2.0
        deltas.append(d[mask])
        vs.append(v[mask])
        yr_meas.append(yr[mask])
        ddt.append(dd_smooth[mask])
    return {
        "delta": np.concatenate(deltas),
        "v": np.concatenate(vs),
        "yr": np.concatenate(yr_meas),
        "ddt": np.concatenate(ddt),
    }


def predict(d, dd, v, L, Kus, tau, bias):
    return v * (d + tau * dd) / (L + Kus * v * v) + bias


def fit(platform):
    data = gather(platform)
    d, dd, v, y = data["delta"], data["ddt"], data["v"], data["yr"]
    L0 = L_PRIOR[platform]

    def loss(params):
        L, Kus, tau, bias = params
        pred = predict(d, dd, v, L, Kus, tau, bias)
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
        "lpf_hz": 3.0,
    }


if __name__ == "__main__":
    out = {}
    for p in PLATFORMS:
        print(f"fitting {p} ...")
        r = fit(p)
        print(r)
        out[p] = r
    with open(ROOT / "out" / "coeffs_v3.json", "w") as f:
        json.dump(out, f, indent=2)
    print("wrote coeffs_v3.json")
