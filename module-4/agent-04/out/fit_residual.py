"""Per-platform residual-learner head on top of V1.

V1 predicts yr_v1. Truth is yr_t. We learn a small linear correction:
    yr_corrected = yr_v1 + sum(beta_k * feature_k)
features available at predict time (allowlist + derived):
  - 1 (bias)
  - delta_road_rad
  - delta_road_rad * v_mps
  - v_mps
  - a_long_mps2
  - yr_v1
  - yr_v1 * v_mps
  - d(yr_v1)/dt    (steering-rate proxy)
  - delta_road * v^2 (kinematic gain)
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-04")
sys.path.insert(0, str(ROOT / "out"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))

from quick_score import find_segments, platform_from, PLATFORM_SCHEMA, ALLOWED, cte_rmse_segment
from v1_baseline import predict_v1


def build_features(sim_df, yr_v1):
    t = sim_df["t_s"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    a = sim_df["a_long_mps2"].to_numpy()
    dyr = np.gradient(yr_v1, t)
    ddelta = np.gradient(delta, t)
    n = len(t)
    X = np.column_stack([
        np.ones(n),
        delta,
        delta * v,
        v,
        a,
        yr_v1,
        yr_v1 * v,
        dyr,
        delta * v * v,
        ddelta,
    ])
    return X


FEATURE_NAMES = ["bias", "delta", "delta*v", "v", "a_long", "yr_v1", "yr_v1*v", "dyr/dt", "delta*v^2", "ddelta/dt"]


def load_platform(plat):
    paths = [p for p in find_segments() if platform_from(p) == plat]
    bag = []
    for p in paths:
        df = pd.read_csv(p)
        sch = PLATFORM_SCHEMA[plat]
        if sch["truth"] not in df.columns:
            continue
        sim_in = df[[c for c in df.columns if c in ALLOWED]].copy()
        if "yaw_rate_pred_rads" not in sim_in.columns:
            sim_in["yaw_rate_pred_rads"] = df[sch["baseline"]].to_numpy()
        # group identifier from path: route is parents[1]
        route = p.resolve().parents[1].name
        bag.append((route, sim_in, df[sch["truth"]].to_numpy()))
    return bag


def fit_platform(plat, ridge=1e-4, train_frac=1.0, seed=0):
    bag = load_platform(plat)
    print(f"[{plat}] {len(bag)} segments")
    # All segments — use route-grouped split for diagnostic
    routes = sorted({r for r, _, _ in bag})
    rng = np.random.default_rng(seed)
    rng.shuffle(routes)
    # fit on all (final ship); also compute holdout score
    k = max(1, int(len(routes) * 0.2))
    held = set(routes[:k])
    Xs_train, ys_train = [], []
    Xs_all, ys_all = [], []
    for route, sim_in, yr_t in bag:
        yr_v1 = predict_v1(sim_in, plat)["yaw_rate_pred_rads"].to_numpy()
        X = build_features(sim_in, yr_v1)
        v = sim_in["v_mps"].to_numpy()
        m = v > 2.0
        target = (yr_t - yr_v1)[m]
        Xs_all.append(X[m]); ys_all.append(target)
        if route not in held:
            Xs_train.append(X[m]); ys_train.append(target)
    X_all = np.vstack(Xs_all); y_all = np.concatenate(ys_all)
    X_train = np.vstack(Xs_train); y_train = np.concatenate(ys_train)
    # Ridge
    A = X_train.T @ X_train + ridge * np.eye(X_train.shape[1])
    b = X_train.T @ y_train
    beta = np.linalg.solve(A, b)
    # also fit on all for shipping
    A_all = X_all.T @ X_all + ridge * np.eye(X_all.shape[1])
    b_all = X_all.T @ y_all
    beta_ship = np.linalg.solve(A_all, b_all)

    # eval pooled
    def eval_beta(b_use):
        yaw_sq = 0.0; yaw_n = 0; cte_sq = 0.0; cte_n = 0
        h_yaw_sq = 0.0; h_yaw_n = 0; h_cte_sq = 0.0; h_cte_n = 0
        for route, sim_in, yr_t in bag:
            yr_v1 = predict_v1(sim_in, plat)["yaw_rate_pred_rads"].to_numpy()
            X = build_features(sim_in, yr_v1)
            yr_p = yr_v1 + X @ b_use
            v = sim_in["v_mps"].to_numpy(); t = sim_in["t_s"].to_numpy()
            m = v > 2.0
            res = yr_p[m] - yr_t[m]
            yaw_sq += float((res**2).sum()); yaw_n += int(m.sum())
            c, n = cte_rmse_segment(t, v, yr_p, yr_t)
            if c is not None:
                cte_sq += (c**2)*n; cte_n += n
            if route in held:
                h_yaw_sq += float((res**2).sum()); h_yaw_n += int(m.sum())
                if c is not None:
                    h_cte_sq += (c**2)*n; h_cte_n += n
        return (np.sqrt(yaw_sq/yaw_n), np.sqrt(cte_sq/cte_n),
                np.sqrt(h_yaw_sq/h_yaw_n) if h_yaw_n else None,
                np.sqrt(h_cte_sq/h_cte_n) if h_cte_n else None)

    y_full, c_full, y_h, c_h = eval_beta(beta_ship)
    y_t, c_t, y_ht, c_ht = eval_beta(beta)
    print(f"  trained-on-80%  : full yaw={y_t:.6f} cte={c_t:.4f}  held yaw={y_ht:.6f} cte={c_ht:.4f}")
    print(f"  trained-on-100% : full yaw={y_full:.6f} cte={c_full:.4f}")
    print(f"  coefs:")
    for name, b in zip(FEATURE_NAMES, beta_ship):
        print(f"    {name:>10s} = {b:+.6e}")
    return beta_ship.tolist(), y_full, c_full, y_ht, c_ht


if __name__ == "__main__":
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        beta, y, c, yh, ch = fit_platform(plat)
        out[plat] = {"beta": beta, "feature_names": FEATURE_NAMES,
                     "train_pooled_yaw": y, "train_pooled_cte": c,
                     "holdout_yaw": yh, "holdout_cte": ch}
    with open(ROOT / "out" / "residual_coeffs.json", "w") as f:
        json.dump(out, f, indent=2)
    print("wrote residual_coeffs.json")
