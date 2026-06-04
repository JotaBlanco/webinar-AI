"""3-fold route-grouped CV for V1 + residual head."""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-04")
sys.path.insert(0, str(ROOT / "out"))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))
from quick_score import find_segments, platform_from, PLATFORM_SCHEMA, ALLOWED, cte_rmse_segment
from v1_baseline import predict_v1
from fit_residual import build_features


def load_routes(plat):
    paths = [p for p in find_segments() if platform_from(p) == plat]
    routes = {}
    for p in paths:
        df = pd.read_csv(p)
        sch = PLATFORM_SCHEMA[plat]
        if sch["truth"] not in df.columns:
            continue
        sim_in = df[[c for c in df.columns if c in ALLOWED]].copy()
        if "yaw_rate_pred_rads" not in sim_in.columns:
            sim_in["yaw_rate_pred_rads"] = df[sch["baseline"]].to_numpy()
        route = p.resolve().parents[1].name
        routes.setdefault(route, []).append((sim_in, df[sch["truth"]].to_numpy()))
    return routes


def cv(plat, k=3, ridge=1e-4, seed=7):
    rdict = load_routes(plat)
    routes = sorted(rdict.keys())
    rng = np.random.default_rng(seed)
    rng.shuffle(routes)
    folds = [routes[i::k] for i in range(k)]
    yaw_h, cte_h = [], []
    yaw_v1_h, cte_v1_h = [], []
    for fi in range(k):
        held = set(folds[fi])
        Xs, ys = [], []
        for route, segs in rdict.items():
            if route in held:
                continue
            for sim_in, yr_t in segs:
                yr_v1 = predict_v1(sim_in, plat)["yaw_rate_pred_rads"].to_numpy()
                X = build_features(sim_in, yr_v1)
                v = sim_in["v_mps"].to_numpy()
                m = v > 2.0
                Xs.append(X[m]); ys.append((yr_t - yr_v1)[m])
        X_tr = np.vstack(Xs); y_tr = np.concatenate(ys)
        A = X_tr.T @ X_tr + ridge * np.eye(X_tr.shape[1])
        beta = np.linalg.solve(A, X_tr.T @ y_tr)
        # eval held
        yaw_sq=0.0; yaw_n=0; cte_sq=0.0; cte_n=0
        yaw_sq_v=0.0; cte_sq_v=0.0; cte_n_v=0
        for route in held:
            for sim_in, yr_t in rdict[route]:
                yr_v1 = predict_v1(sim_in, plat)["yaw_rate_pred_rads"].to_numpy()
                X = build_features(sim_in, yr_v1)
                yr_p = yr_v1 + X @ beta
                v = sim_in["v_mps"].to_numpy(); t = sim_in["t_s"].to_numpy()
                m = v > 2.0
                yaw_sq += float(((yr_p[m]-yr_t[m])**2).sum()); yaw_n += int(m.sum())
                yaw_sq_v += float(((yr_v1[m]-yr_t[m])**2).sum())
                c, n = cte_rmse_segment(t, v, yr_p, yr_t)
                if c is not None:
                    cte_sq += (c**2)*n; cte_n += n
                cv1, nv1 = cte_rmse_segment(t, v, yr_v1, yr_t)
                if cv1 is not None:
                    cte_sq_v += (cv1**2)*nv1; cte_n_v += nv1
        yaw_h.append(np.sqrt(yaw_sq/yaw_n))
        cte_h.append(np.sqrt(cte_sq/cte_n))
        yaw_v1_h.append(np.sqrt(yaw_sq_v/yaw_n))
        cte_v1_h.append(np.sqrt(cte_sq_v/cte_n_v))
    return yaw_h, cte_h, yaw_v1_h, cte_v1_h


if __name__ == "__main__":
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        yh, ch, yv, cv1 = cv(plat)
        print(f"{plat}:")
        print(f"  V1+resid CV yaw: {np.mean(yh):.6f} ± {np.std(yh):.6f}  (V1: {np.mean(yv):.6f})")
        print(f"  V1+resid CV cte: {np.mean(ch):.4f} ± {np.std(ch):.4f}    (V1: {np.mean(cv1):.4f})")
