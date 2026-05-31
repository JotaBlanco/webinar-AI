"""Fit per-platform affine+understeer correction:
    yaw_corrected = a0*y_v0 + a1*y_v0*v + a2*y_v0*v^2 + b
Save coefficients to JSON.

Uses ALL training segments under data/sim/segments/ for the three platforms
that have an independent truth channel. Tesla is excluded (no truth) — its
predict is V0 passthrough.

We also do a simple route-grouped 80/20 split sanity check so we know the
fitted coefficients aren't a pathological overfit.
"""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TRUTH = "yaw_rate_meas_rads"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]

rng = np.random.default_rng(42)


def gather_paths(platform):
    return sorted(glob.glob(
        str(ROOT / "data" / "sim" / "segments" / platform / "*" / "**" / "sim.csv"),
        recursive=True,
    ))


def route_of(path):
    # data/sim/segments/<plat>/<device>/<route>/<idx>/sim.csv
    return Path(path).resolve().parents[1].name


def fit_one(yv0, yt, v):
    X = np.column_stack([yv0, yv0 * v, yv0 * v ** 2, np.ones_like(yv0)])
    coef, *_ = np.linalg.lstsq(X, yt, rcond=None)
    pred = X @ coef
    rmse = float(np.sqrt(np.mean((pred - yt) ** 2)))
    bias = float(np.mean(pred - yt))
    return coef.tolist(), rmse, bias


def collect(paths):
    chunks = []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["v_mps", "yaw_rate_pred_rads", TRUTH])
        except Exception:
            continue
        m = df["v_mps"] > 2.0
        if m.sum() == 0:
            continue
        chunks.append(df.loc[m, ["v_mps", "yaw_rate_pred_rads", TRUTH]].to_numpy())
    if not chunks:
        return None
    arr = np.vstack(chunks)
    return arr[:, 0], arr[:, 1], arr[:, 2]  # v, yv0, yt


coeffs = {}
for plat in PLATFORMS:
    paths = gather_paths(plat)
    print(f"\n{plat}: {len(paths)} segments")
    routes = sorted(set(route_of(p) for p in paths))
    print(f"  {len(routes)} unique routes")
    # 80/20 route-grouped split
    perm = rng.permutation(len(routes))
    n_train = max(1, int(0.8 * len(routes)))
    train_routes = set(routes[i] for i in perm[:n_train])
    dev_routes = set(routes[i] for i in perm[n_train:])
    train_paths = [p for p in paths if route_of(p) in train_routes]
    dev_paths   = [p for p in paths if route_of(p) in dev_routes]
    print(f"  train_routes={len(train_routes)}  dev_routes={len(dev_routes)}  "
          f"train_segs={len(train_paths)}  dev_segs={len(dev_paths)}")

    # fit on train, evaluate train+dev
    tr = collect(train_paths)
    if tr is None:
        continue
    v_tr, y0_tr, yt_tr = tr
    coef, rmse_tr, bias_tr = fit_one(y0_tr, yt_tr, v_tr)
    print(f"  coef={coef}")
    print(f"  train RMSE={rmse_tr:.6f}  bias={bias_tr:+.6f}")
    if dev_paths:
        dv = collect(dev_paths)
        if dv:
            v_d, y0_d, yt_d = dv
            X_d = np.column_stack([y0_d, y0_d * v_d, y0_d * v_d ** 2, np.ones_like(y0_d)])
            pred_d = X_d @ np.asarray(coef)
            rmse_d = float(np.sqrt(np.mean((pred_d - yt_d) ** 2)))
            bias_d = float(np.mean(pred_d - yt_d))
            print(f"  dev   RMSE={rmse_d:.6f}  bias={bias_d:+.6f}")
            # baseline V0 dev RMSE
            rmse_v0 = float(np.sqrt(np.mean((y0_d - yt_d) ** 2)))
            print(f"  dev V0 RMSE={rmse_v0:.6f} (for comparison)")

    # FINAL: refit on ALL data for shipping
    all_data = collect(paths)
    v_a, y0_a, yt_a = all_data
    final_coef, rmse_a, bias_a = fit_one(y0_a, yt_a, v_a)
    print(f"  FINAL ALL: coef={final_coef}, RMSE={rmse_a:.6f}, bias={bias_a:+.6f}")
    coeffs[plat] = {"a0": final_coef[0], "a1": final_coef[1], "a2": final_coef[2], "b": final_coef[3]}

# Tesla: passthrough (no truth available)
coeffs["TESLA_MODEL_3"] = {"a0": 1.0, "a1": 0.0, "a2": 0.0, "b": 0.0}

out_path = ROOT / "final-model" / "coeffs.json"
out_path.write_text(json.dumps(coeffs, indent=2))
print(f"\nWrote {out_path}")
print(json.dumps(coeffs, indent=2))
