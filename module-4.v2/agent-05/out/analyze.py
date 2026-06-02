"""Diagnose: fit per-platform (L_eff, K_us, tau, delta0) by least squares against truth.

Compare V1's hardcoded params vs a refit on all training segments.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-05")

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def load_segments(platform, max_segs=120):
    seg_root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(seg_root.glob("**/sim.csv"))
    if max_segs:
        # Stride evenly so we get coverage
        step = max(1, len(paths) // max_segs)
        paths = paths[::step][:max_segs]
    return paths


def per_segment_delta0(df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(df.loc[mask, "delta_road_rad"].median())


def simulate(df, g, L_eff, K_us, tau, delta0):
    delta = (df["delta_road_rad"].to_numpy() - delta0) * g
    v = df["v_mps"].to_numpy()
    yr_ss = v * delta / (L_eff + K_us * v * v)
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def fit_platform(platform, init):
    paths = load_segments(platform)
    segs = []
    for p in paths:
        df = pd.read_csv(p, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads","yaw_rate_pred_rads"])
        if len(df) < 200: continue
        d0 = per_segment_delta0(df, fallback=init.get("delta0_fallback", 0.0))
        segs.append((df, d0))
    print(f"{platform}: {len(segs)} segments loaded")

    def loss(theta):
        g, L_eff, K_us, tau = theta
        if L_eff < 1.0 or tau < 0.01 or K_us < 0 or g < 0.5 or g > 1.5: return 1e9
        ss = 0.0; n = 0
        for df, d0 in segs:
            yr_pred = simulate(df, g, L_eff, K_us, tau, d0)
            yr_truth = df["yaw_rate_meas_rads"].to_numpy()
            v = df["v_mps"].to_numpy()
            mask = v > 2.0
            r = yr_pred[mask] - yr_truth[mask]
            ss += float(np.sum(r*r)); n += int(mask.sum())
        return ss / max(n,1)

    x0 = [init["g"], init["L_eff"], init["K_us"], init["tau"]]
    res = minimize(loss, x0, method="Nelder-Mead", options={"xatol":1e-5,"fatol":1e-9,"maxiter":400})
    print(f"  start: {x0}  loss={loss(x0):.3e}")
    print(f"  end:   {list(res.x)}  loss={res.fun:.3e}")
    return res.x


INIT = {
    "FORD_F_150_LIGHTNING_MK1": {"g":0.863,"L_eff":3.26,"K_us":0.00350,"tau":0.060,"delta0_fallback":0.00133},
    "FORD_MUSTANG_MACH_E_MK1":  {"g":0.891,"L_eff":2.22,"K_us":0.00150,"tau":0.069,"delta0_fallback":-0.0001},
    "HYUNDAI_IONIQ_5":          {"g":0.938,"L_eff":2.887,"K_us":0.00289,"tau":0.062,"delta0_fallback":0.0},
}

if __name__ == "__main__":
    out = {}
    for plat in PLATFORMS:
        x = fit_platform(plat, INIT[plat])
        out[plat] = {"g":x[0],"L_eff":x[1],"K_us":x[2],"tau":x[3]}
    import json
    print(json.dumps(out, indent=2))
    (ROOT / "out" / "fit_params.json").write_text(json.dumps(out, indent=2))
