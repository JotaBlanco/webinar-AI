"""Try adding a first-order lag on delta (driver/steering compliance).

Hypothesis: actual yaw lags commanded steering. We low-pass filter delta with
time constant tau, then plug into the V1 formula. Fit tau per platform.
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/make-train-dev-split"))
sys.path.insert(0, str(ROOT / "skills/score-model"))
sys.path.insert(0, str(ROOT / "_shared"))
from split import split as make_split
from score import score

train_paths, dev_paths = make_split(dev_fraction=0.25, seed=42)

with open(ROOT / "final-model/coeffs.json") as f:
    COEFFS = json.load(f)

def lowpass(x, dt, tau):
    if tau <= 0:
        return x.copy()
    a = dt / (tau + dt)
    y = np.empty_like(x)
    y[0] = x[0]
    for i in range(1, len(x)):
        y[i] = y[i-1] + a[i-1] * (x[i] - y[i-1])
    return y

def predict_with_tau(sim_df, platform, tau_map):
    c = COEFFS.get(platform, {"K":0.0008,"delta0":0.0,"scale":1.0,"L":2.875})
    L=c["L"]; K=c["K"]; d0=c["delta0"]; sc=c["scale"]
    tau = tau_map.get(platform, 0.0)
    v = sim_df["v_mps"].to_numpy(float)
    delta = sim_df["delta_road_rad"].to_numpy(float)
    t = sim_df["t_s"].to_numpy(float)
    if tau > 0:
        dt = np.diff(t)
        # Pad with mean dt at end
        dt_full = np.concatenate([dt, [dt[-1] if len(dt) else 0.02]])
        delta = lowpass(delta, dt_full, tau)
    denom = 1.0 + K*v*v
    yr = sc * (v/L) * np.tan(delta - d0) / denom
    yr = np.where(np.isfinite(yr), yr, 0.0)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

# Search tau per platform on TRAIN
best = {}
for plat in COEFFS:
    if plat == "TESLA_MODEL_3":
        best[plat] = 0.0
        continue
    plat_train = [p for p in train_paths if plat in str(p)]
    best_tau, best_rmse = 0.0, 1e9
    for tau in [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20, 0.30, 0.50]:
        r = score(lambda d,p,t=tau: predict_with_tau(d, p, {plat:t}), segment_paths=plat_train, platform_filter=plat)
        if r['yaw_rate_rmse'] < best_rmse:
            best_rmse = r['yaw_rate_rmse']
            best_tau = tau
    best[plat] = best_tau
    print(f'{plat}: best tau={best_tau}, train RMSE={best_rmse:.5f}')

# Evaluate on dev
print("\n--- DEV evaluation with lag ---")
r = score(lambda d,p: predict_with_tau(d,p,best), segment_paths=dev_paths)
print(f"DEV overall yaw RMSE={r['yaw_rate_rmse']:.6f}  CTE RMSE={r['cte_rmse']:.4f}")
for plat, pp in r['per_platform'].items():
    print(f"  {plat}: yaw RMSE={pp['yaw_rate_rmse']:.6f}  CTE={pp['cte_rmse']:.4f}")
print(f"  per-regime: {{k: round(v['yaw_rate_rmse'],5) for k,v in r['per_regime'].items()}}")
print("regime detail:", {k: round(v['yaw_rate_rmse'],5) for k,v in r['per_regime'].items()})

print("\nBest taus:", best)
