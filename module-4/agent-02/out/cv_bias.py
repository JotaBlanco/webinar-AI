"""5-fold route-grouped CV on the additive yaw_bias term per platform.

Routes are the first directory level under each platform (the 16-char segment ids).
For each fold: fit bias on train routes, evaluate yaw+CTE on test routes (with bias),
report mean +/- sigma across folds. The full V1-refit physics is held fixed.
"""
from __future__ import annotations
import sys, math
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "final-model"))

from _shared.traj_metrics import cte_rmse_segment
import predict as final_predict_mod

SEG_ROOT = ROOT / "data" / "sim" / "segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def collect_with_routes(platform):
    paths = sorted((SEG_ROOT / platform).glob("**/sim.csv"))
    by_route = defaultdict(list)
    for p in paths:
        # platform/<route_id>/<...>/sim.csv
        rel = p.relative_to(SEG_ROOT / platform)
        route_id = rel.parts[0]
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        # Compute pred WITHOUT bias term — strip it from coeffs temporarily.
        # Reuse final-predict but subtract bias.
        from predict import _COEFFS
        yr_with_bias = final_predict_mod.predict(df, platform)["yaw_rate_pred_rads"].to_numpy()
        bias = _COEFFS[platform].get("yaw_bias", 0.0)
        yr_pred = yr_with_bias - bias
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        truth = df["yaw_rate_meas_rads"].to_numpy()
        mask = v > 2.0
        by_route[route_id].append((t, v, truth, yr_pred, mask))
    return by_route


def fold_score(test_segs, bias):
    yaw_ss = yaw_n = 0
    cte_ss = cte_n = 0
    for t, v, truth, yr_pred, mask in test_segs:
        yr = yr_pred + bias
        r = yr[mask] - truth[mask]
        yaw_ss += float(np.dot(r, r)); yaw_n += int(mask.sum())
        ss, nb, _ = cte_rmse_segment(t, v, truth, yr)
        cte_ss += ss; cte_n += nb
    yaw = math.sqrt(yaw_ss/max(yaw_n,1))
    cte = math.sqrt(cte_ss/max(cte_n,1))
    return yaw, cte


def fit_bias_on(segs):
    sd = 0.0; n = 0
    for _, _, truth, yr_pred, mask in segs:
        sd += float(np.sum(truth[mask] - yr_pred[mask]))
        n += int(mask.sum())
    return sd / max(n, 1)


if __name__ == "__main__":
    rng = np.random.default_rng(42)
    k = 5
    for plat in PLATFORMS:
        by_route = collect_with_routes(plat)
        routes = list(by_route.keys())
        rng.shuffle(routes)
        folds = np.array_split(routes, k)
        biases, yaws, ctes = [], [], []
        for i in range(k):
            test_routes = set(folds[i])
            train_segs, test_segs = [], []
            for r, segs in by_route.items():
                if r in test_routes:
                    test_segs.extend(segs)
                else:
                    train_segs.extend(segs)
            b = fit_bias_on(train_segs)
            y, c = fold_score(test_segs, b)
            biases.append(b); yaws.append(y); ctes.append(c)
        print(f"\n{plat}:  n_routes={len(routes)}")
        print(f"  fold biases: {[f'{b:+.6f}' for b in biases]}")
        print(f"  bias mean +/- sigma: {np.mean(biases):+.6f} +/- {np.std(biases):.6f}")
        print(f"  CV yaw RMSE: {np.mean(yaws):.6f} +/- {np.std(yaws):.6f}")
        print(f"  CV CTE RMSE: {np.mean(ctes):.4f} +/- {np.std(ctes):.4f}")
