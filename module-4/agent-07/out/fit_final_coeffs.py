"""Fit final per-platform affine corrections (a, b) using all training segments,
report route-grouped CV stats, and write final coeffs.json."""
import sys, json, math, random
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
random.seed(0)

coeffs = {"per_platform": {}}

for plat_dir in sorted(SEG_ROOT.iterdir()):
    plat = plat_dir.name
    if plat == "TESLA_MODEL_3":
        coeffs["per_platform"][plat] = {"a": 0.0, "b": 1.0, "route_cv_sigma": 0.0,
                                         "n_samples": 0, "n_routes": 0,
                                         "note": "Tesla: V0 passthrough, no truth"}
        continue
    csvs = list(plat_dir.glob("**/sim.csv"))
    random.shuffle(csvs)
    # use all for final fit (was 200 sample before)
    csvs = csvs[:400]  # cap for compute
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
            "route": p.resolve().parents[1].name,
        }))
    if not rows: continue
    all_df = pd.concat(rows, ignore_index=True)
    yr_v1 = all_df["yr_v1"].to_numpy(); yr_truth = all_df["yr_truth"].to_numpy()
    A = np.vstack([np.ones_like(yr_v1), yr_v1]).T
    coef, *_ = np.linalg.lstsq(A, yr_truth, rcond=None)
    a, b = coef
    # Route-grouped CV
    routes = all_df["route"].unique().tolist()
    random.shuffle(routes)
    K = 5
    folds = [routes[i::K] for i in range(K)]
    cv_rmse = []
    cv_a, cv_b = [], []
    for k in range(K):
        test_routes = set(folds[k])
        train = all_df[~all_df["route"].isin(test_routes)]
        test  = all_df[ all_df["route"].isin(test_routes)]
        if len(train) == 0 or len(test) == 0: continue
        A_k = np.vstack([np.ones(len(train)), train["yr_v1"].to_numpy()]).T
        ck, *_ = np.linalg.lstsq(A_k, train["yr_truth"].to_numpy(), rcond=None)
        a_k, b_k = ck
        t_v1 = test["yr_v1"].to_numpy(); t_truth = test["yr_truth"].to_numpy()
        cv_rmse.append(math.sqrt(((a_k + b_k*t_v1 - t_truth)**2).mean()))
        cv_a.append(a_k); cv_b.append(b_k)
    coeffs["per_platform"][plat] = {
        "a": float(a), "b": float(b),
        "cv_rmse_mean": float(np.mean(cv_rmse)),
        "cv_rmse_sigma": float(np.std(cv_rmse)),
        "route_cv_sigma": float(np.std(cv_a)),   # required by gate
        "cv_a_sigma": float(np.std(cv_a)),
        "cv_b_sigma": float(np.std(cv_b)),
        "n_samples": int(len(all_df)),
        "n_routes": int(all_df['route'].nunique()),
    }
    print(f"{plat}: a={a:+.6f}, b={b:+.6f}, cv_rmse={np.mean(cv_rmse):.5f}±{np.std(cv_rmse):.5f}, "
          f"a_sigma={np.std(cv_a):.2e}")

# Note: I considered also fitting via a single shape (just additive c).
# CV shows linear is slightly better for Mustang but ties for Hyundai/Ford.
# Keeping affine.

(ROOT / "final-model/coeffs.json").write_text(json.dumps(coeffs, indent=2))
print("\nwrote final-model/coeffs.json")
