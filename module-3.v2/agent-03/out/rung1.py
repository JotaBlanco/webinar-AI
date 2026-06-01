"""Minimum-viable rung-1 attempt: linear dynamic single-track for Mach-E only.

Fits only C_af; others fixed from openpilot carParams. Run against data/sim/
for truth-aware fitting, but the predict signature obeys the allowlist.
"""
import sys
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "score-model"))

ROOT = REPO / "data" / "sim" / "segments"

# Mach-E carParams
MACHE = dict(m=2336.0, Iz=4879.05, a=1.3130, b=1.671, C_ar=355_912.0)


def rung1_yaw(df, C_af, n_substeps=4):
    delta = df["delta_road_rad"].to_numpy()
    vx = df["v_mps"].to_numpy()
    t = df["t_s"].to_numpy()
    vx_safe = np.maximum(vx, 1.0)
    dt_full = np.diff(t, prepend=t[0])
    a, b = MACHE["a"], MACHE["b"]
    m, Iz, C_ar = MACHE["m"], MACHE["Iz"], MACHE["C_ar"]
    vy = 0.0
    yr = 0.0
    out = np.empty_like(vx)
    for i in range(len(vx)):
        dt = dt_full[i] / n_substeps
        for _ in range(n_substeps):
            af = delta[i] - (vy + a * yr) / vx_safe[i]
            ar = -(vy - b * yr) / vx_safe[i]
            Fyf = C_af * af
            Fyr = C_ar * ar
            vy_dot = (Fyf + Fyr) / m - vx[i] * yr
            yr_dot = (a * Fyf - b * Fyr) / Iz
            vy += vy_dot * dt
            yr += yr_dot * dt
        out[i] = yr
    return out


def load_mache():
    segs = []
    for p in sorted(ROOT.glob("FORD_MUSTANG_MACH_E_MK1/**/sim.csv")):
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" in df.columns:
            segs.append(df)
    return segs


def objective(C_af, segs, v_min=2.0):
    ss = 0.0
    n = 0
    for df in segs:
        try:
            yr = rung1_yaw(df, C_af)
        except Exception:
            return 1e6
        truth = df["yaw_rate_meas_rads"].to_numpy()
        v = df["v_mps"].to_numpy()
        mask = (v > v_min) & np.isfinite(yr)
        r = yr[mask] - truth[mask]
        ss += float(np.sum(r * r))
        n += int(mask.sum())
    return math.sqrt(ss / max(n, 1))


def main():
    segs = load_mache()
    # Sub-sample for speed
    segs_sub = segs[:: max(1, len(segs) // 60)]
    print(f"Mach-E rung-1 fit on {len(segs_sub)} segments (subsample of {len(segs)})", flush=True)
    res = minimize_scalar(objective, args=(segs_sub,),
                          bounds=(20_000, 600_000), method="bounded",
                          options={"xatol": 100, "maxiter": 40})
    print(f"  fitted C_af = {res.x:.0f} N/rad, yaw rmse = {res.fun:.6f}", flush=True)
    # Evaluate on full set
    full = objective(res.x, segs)
    print(f"  full-set yaw rmse: {full:.6f}", flush=True)
    return res.x


if __name__ == "__main__":
    main()
