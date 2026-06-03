"""Fit per-platform corrections on V1 residuals using sim/segments (truth available).

Strategy:
 - For each platform, gather (v_mps, yr_v1, yr_truth) over many segments.
 - Fit  yr_truth ≈ a + b * yr_v1   (and consider a scaled version too).
 - Also fit a constant additive bias `c` such that yr_truth - yr_v1 ≈ c.
 - Cross-validate by route.
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-07")
sys.path.insert(0, str(ROOT))
import importlib.util
spec = importlib.util.spec_from_file_location("v1_baseline", ROOT / "code/v1_baseline.py")
v1_mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(v1_mod)
predict_v1 = v1_mod.predict_v1

SEG_ROOT = ROOT / "data/sim/segments"

# subsample per platform for speed
import random
random.seed(0)

per_plat = {}
for plat_dir in sorted(SEG_ROOT.iterdir()):
    plat = plat_dir.name
    if plat == "TESLA_MODEL_3":
        continue
    csvs = list(plat_dir.glob("**/sim.csv"))
    random.shuffle(csvs)
    csvs = csvs[:200]   # cap
    rows = []
    for p in csvs:
        try:
            df = pd.read_csv(p, usecols=["t_s","v_mps","delta_road_rad","yaw_rate_meas_rads","yaw_rate_pred_rads"])
        except Exception:
            continue
        if len(df) < 50: continue
        try:
            pred = predict_v1(df, plat)
        except Exception:
            continue
        yr_v1 = pred["yaw_rate_pred_rads"].to_numpy()
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        v = df["v_mps"].to_numpy()
        mask = v > 2.0
        if mask.sum() == 0: continue
        rows.append(pd.DataFrame({
            "yr_v1": yr_v1[mask],
            "yr_truth": yr_truth[mask],
            "v": v[mask],
            "route": p.resolve().parents[1].name,
        }))
    if not rows: continue
    all_df = pd.concat(rows, ignore_index=True)
    per_plat[plat] = all_df
    yr_v1 = all_df["yr_v1"].to_numpy(); yr_truth = all_df["yr_truth"].to_numpy()
    # additive c
    c = np.mean(yr_truth - yr_v1)
    # linear fit: yr_truth = a + b * yr_v1
    A = np.vstack([np.ones_like(yr_v1), yr_v1]).T
    coef, *_ = np.linalg.lstsq(A, yr_truth, rcond=None)
    a, b = coef
    # residual stats
    r0 = yr_v1 - yr_truth
    r_add = (yr_v1 + c) - yr_truth
    r_lin = (a + b*yr_v1) - yr_truth
    print(f"\n=== {plat}  n={len(all_df):,}  routes={all_df['route'].nunique()}")
    print(f"  V1            mean={r0.mean():+.5f}  rmse={np.sqrt((r0**2).mean()):.5f}")
    print(f"  V1 + c={c:+.5f}  mean={r_add.mean():+.5f}  rmse={np.sqrt((r_add**2).mean()):.5f}")
    print(f"  a={a:+.5f}, b={b:+.5f}    mean={r_lin.mean():+.5f}  rmse={np.sqrt((r_lin**2).mean()):.5f}")

    # route-grouped CV for both
    routes = all_df["route"].unique().tolist()
    random.shuffle(routes)
    K = 5
    folds = [routes[i::K] for i in range(K)]
    cv_add, cv_lin = [], []
    for k in range(K):
        test_routes = set(folds[k])
        train = all_df[~all_df["route"].isin(test_routes)]
        test  = all_df[ all_df["route"].isin(test_routes)]
        if len(train) == 0 or len(test) == 0: continue
        c_k = np.mean(train["yr_truth"] - train["yr_v1"])
        A_k = np.vstack([np.ones(len(train)), train["yr_v1"].to_numpy()]).T
        coef_k, *_ = np.linalg.lstsq(A_k, train["yr_truth"].to_numpy(), rcond=None)
        a_k, b_k = coef_k
        # test rmse
        t_v1 = test["yr_v1"].to_numpy(); t_truth = test["yr_truth"].to_numpy()
        cv_add.append(np.sqrt(((t_v1 + c_k - t_truth)**2).mean()))
        cv_lin.append(np.sqrt(((a_k + b_k*t_v1 - t_truth)**2).mean()))
    print(f"  CV add mean rmse: {np.mean(cv_add):.5f} ± {np.std(cv_add):.5f}")
    print(f"  CV lin mean rmse: {np.mean(cv_lin):.5f} ± {np.std(cv_lin):.5f}")

    out = {"additive_c": float(c), "lin_a": float(a), "lin_b": float(b),
           "cv_add_mean": float(np.mean(cv_add)), "cv_add_std": float(np.std(cv_add)),
           "cv_lin_mean": float(np.mean(cv_lin)), "cv_lin_std": float(np.std(cv_lin)),
           "n_samples": int(len(all_df)), "n_routes": int(all_df['route'].nunique())}
    Path(ROOT / f"out/corrections_{plat}.json").write_text(json.dumps(out, indent=2))
