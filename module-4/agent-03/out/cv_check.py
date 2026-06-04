"""Route-grouped k-fold CV on bias+ridge fit per platform.

Cohort §6 warns: naive subset fits overfit on asymmetric/bias levers. Run a
5-fold split by route (the top-level segment dir under the platform), refit on
4 folds, score yaw RMSE on the held-out fold. Report mean ± σ across folds.

This is the gate the m4.v1.01 harness adds: `bias_without_route_cv`. Run it
here as a sanity, not as a re-fit driver.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-03")
sys.path.insert(0, str(ROOT / "out"))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))

from fit_and_score import (  # noqa: E402
    load_platform_paired,
    fit_platform,
    build_features,
    SIM_ONLY_COLS,
    TRUTH_COL_BY_PLATFORM,
)
from v1_baseline import predict_v1  # noqa: E402


def route_of(path: Path) -> str:
    # path is sim-only/.../<platform>/<route>/<segment>/<n>/sim.csv
    parts = path.parts
    # find platform index
    for i, p in enumerate(parts):
        if p in TRUTH_COL_BY_PLATFORM:
            return parts[i + 1]  # route dir
    return path.parts[-4]


def cv_platform(platform: str, k: int = 5):
    paired = load_platform_paired(platform)
    routes = sorted({route_of(p) for p, _ in paired})
    if len(routes) < k:
        k = len(routes)
    rng = np.random.RandomState(7)
    perm = rng.permutation(routes)
    folds = np.array_split(perm, k)
    fold_set = [set(f) for f in folds]
    yaw_rmses = []
    biases = []
    for i in range(k):
        train_paired = [(p, d) for p, d in paired if route_of(p) not in fold_set[i]]
        test_paired = [(p, d) for p, d in paired if route_of(p) in fold_set[i]]
        if not train_paired or not test_paired:
            continue
        c = fit_platform(platform, train_paired)
        biases.append(c["bias"])
        w = np.asarray(c["ridge_w"])
        sq, n = 0.0, 0
        for path, df in test_paired:
            sim_only = df[SIM_ONLY_COLS].copy()
            yp = predict_v1(sim_only, platform)["yaw_rate_pred_rads"].to_numpy()
            feats = build_features(sim_only)
            ypc = yp + c["bias"] + feats @ w
            res = ypc - df["_truth"].to_numpy()
            sq += float(np.sum(res * res))
            n += len(res)
        if n:
            yaw_rmses.append(math.sqrt(sq / n))
    return {
        "k": k,
        "yaw_rmse_mean": float(np.mean(yaw_rmses)) if yaw_rmses else None,
        "yaw_rmse_sigma": float(np.std(yaw_rmses)) if yaw_rmses else None,
        "bias_mean": float(np.mean(biases)) if biases else None,
        "bias_sigma": float(np.std(biases)) if biases else None,
        "per_fold_yaw_rmse": yaw_rmses,
    }


def main():
    out = {}
    for plat in ("FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        print(f"CV {plat}...")
        r = cv_platform(plat, k=5)
        print(json.dumps(r, indent=2))
        out[plat] = r
    json.dump(out, open(ROOT / "out" / "cv_check.json", "w"), indent=2)


if __name__ == "__main__":
    main()
