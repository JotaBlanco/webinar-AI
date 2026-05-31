"""Quick exploration: understeer fit per platform."""
import sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
from out.scorer import segment_paths, _platform_from_path
from parameters import PARAM_BY_PLATFORM

# Load all training data per platform, fit yaw_rate = v*delta / (L + K * v^2)
# i.e., truth*L + truth*K*v^2 = v*delta
# Linear regression: y = truth*v^2, X = v*delta - truth*L
# K = (v*delta - truth*L) / (truth*v^2)
# Better: minimize sum( (truth - v*delta/(L + K v^2))^2 )  -> nonlinear in K
# Easier closed-form: rewrite as truth*(L + K v^2) = v*delta
#   => truth*K*v^2 = v*delta - truth*L
#   => K = sum((v*delta - truth*L)*(truth*v^2)) / sum((truth*v^2)^2)

from scipy.optimize import minimize_scalar

paths_by_plat = {}
for p in segment_paths():
    plat = _platform_from_path(p)
    paths_by_plat.setdefault(plat, []).append(p)

# Subsample
import random
random.seed(0)
SUB = 60
results = {}
for plat in paths_by_plat:
    if plat == "TESLA_MODEL_3":
        # no truth -> skip
        continue
    pths = paths_by_plat[plat]
    random.shuffle(pths)
    pths = pths[:SUB]
    rows = []
    for p in pths:
        try:
            df = pd.read_csv(p, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads"])
        except Exception:
            continue
        rows.append(df)
    if not rows:
        continue
    big = pd.concat(rows, ignore_index=True)
    big = big[big["v_mps"] > 2.0].dropna()
    v = big["v_mps"].to_numpy(float)
    d = big["delta_road_rad"].to_numpy(float)
    yr = big["yaw_rate_meas_rads"].to_numpy(float)

    p_param = PARAM_BY_PLATFORM.get(plat)
    L = p_param.L if p_param else 2.875

    # Linear closed-form for K
    num = np.sum((v*d - yr*L) * (yr * v*v))
    den = np.sum((yr * v*v) ** 2)
    K_closed = num / den if den > 0 else 0.0

    # Verify by nonlinear search
    def rmse(K):
        pred = v*d / (L + K*v*v)
        return float(np.sqrt(np.mean((pred - yr)**2)))
    rmse_baseline = rmse(0.0)
    rmse_closed = rmse(K_closed)
    res = minimize_scalar(rmse, bracket=(-0.01, 0.0, 0.05))
    K_nl = res.x
    rmse_nl = rmse(K_nl)
    print(f"{plat}: L={L:.3f}  K_closed={K_closed:.5f} ({rmse_closed:.5f})  K_nl={K_nl:.5f} ({rmse_nl:.5f})  baseline_rmse={rmse_baseline:.5f}  n={len(v)}")
    results[plat] = {"L": L, "K": K_nl, "rmse_nl": rmse_nl, "rmse_v0": rmse_baseline}

# Save
import json
with open(ROOT/"out"/"coeffs_understeer.json", "w") as f:
    json.dump(results, f, indent=2)
print("Saved", ROOT/"out"/"coeffs_understeer.json")
