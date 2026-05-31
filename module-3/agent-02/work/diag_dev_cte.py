"""Diagnose: which dev segments dominate Mach-E CTE under V3?"""
import sys, os, json, math
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-02")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
os.chdir(ROOT)

import numpy as np
import pandas as pd
from split import split
from traj_metrics import cte_rmse_segment

train, dev = split(dev_fraction=0.25, seed=42)

with open(ROOT / "work" / "fitted_v3.json") as fh:
    fitted = json.load(fh)


def apply_lag(yr_ss, dt, tau):
    n = len(yr_ss)
    y = np.empty(n)
    y[0] = yr_ss[0]
    for k in range(n - 1):
        a = dt[k] / tau
        y[k + 1] = y[k] + a * (yr_ss[k] - y[k])
    return y


def model_yr(delta, v, p, dt):
    g_eff = p["g0"] + p["g2"] * delta * delta
    K_eff = p["K0"] + p["K1"] * v
    yr_ss = v * (g_eff * delta + p["delta0"]) / (p["L"] + K_eff * v * v)
    return apply_lag(yr_ss, dt, p["tau"])


def platform_of(p):
    return Path(p).resolve().parents[3].name


me_results = []
for path in dev:
    plat = platform_of(path)
    if plat != "FORD_MUSTANG_MACH_E_MK1":
        continue
    df = pd.read_csv(path)
    t = df["t_s"].to_numpy(float)
    v = df["v_mps"].to_numpy(float)
    delta = df["delta_road_rad"].to_numpy(float)
    yr_truth = df["yaw_rate_meas_rads"].to_numpy(float)
    if len(t) < 5 or np.any(np.diff(t) <= 0):
        continue
    dt = np.diff(t)
    p = fitted[plat]
    yr_pred = model_yr(delta, v, p, dt)
    sum_sq, n_bins, total = cte_rmse_segment(t, v, yr_truth, yr_pred, 1.0, 20.0)
    if n_bins > 0:
        rmse = math.sqrt(sum_sq / n_bins)
        me_results.append((rmse, n_bins, total, str(path)))

me_results.sort(reverse=True)
print(f"Mach-E DEV segments: {len(me_results)}")
print("\nTop 10 by per-segment RMSE:")
for r, n, d, p in me_results[:10]:
    print(f"  rmse={r:7.2f} m  n_bins={n:5d}  dist={d:7.1f}  {p[-90:]}")

print("\nBottom 10:")
for r, n, d, p in me_results[-10:]:
    print(f"  rmse={r:7.2f} m  n_bins={n:5d}  dist={d:7.1f}  {p[-90:]}")

# Recompute pooled RMSE without top-N to see how concentrated the drift is.
all_sumsq = [r*r*n for r, n, d, p in me_results]
all_n = [n for r, n, d, p in me_results]
total_sumsq = sum(all_sumsq)
total_n = sum(all_n)
print(f"\nPooled Mach-E CTE RMSE all: {math.sqrt(total_sumsq/total_n):.2f} m   over {total_n} bins, {len(me_results)} segs")
for k in [1, 3, 5, 10]:
    rest_sumsq = sum(all_sumsq[k:])
    rest_n = sum(all_n[k:])
    print(f"  Excluding worst {k}: {math.sqrt(rest_sumsq/rest_n):.2f} m   over {rest_n} bins")
