"""Train + evaluate V1 + per-platform bias + ridge residual learner.

Inputs are read from data/sim-only/segments/<plat>/<route>/<run>/<idx>/sim.csv
(the 8-column allowlist mirror — matches what grader hands predict()).
Truth column (`yaw_rate_meas_rads`) is read from the paired
data/sim/segments/<...>/sim.csv. Truth NEVER enters predict() input.
"""
from __future__ import annotations
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-02")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))

from v1_baseline import predict_v1  # noqa
from traj_metrics import cte_rmse_segment  # noqa

OUT = ROOT / "out"
ARTIFACTS = ROOT / "final-model"
ARTIFACTS.mkdir(exist_ok=True)

ALLOW = ["t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
         "a_long_mps2", "accel_pedal_pct", "brake_pressed",
         "yaw_rate_pred_rads"]


def load_index() -> dict[str, list[tuple[str, str, str]]]:
    """Returns platform -> list of (route, simonly_path, sim_path)."""
    so_idx = pd.read_csv(OUT / "index_simonly.csv")
    s_idx = pd.read_csv(OUT / "index_sim.csv")
    s_map = dict(zip(s_idx["rel"], s_idx["path"]))
    out: dict[str, list[tuple[str, str, str]]] = {}
    for _, row in so_idx.iterrows():
        sim_path = s_map.get(row["rel"])
        if sim_path is None:
            continue
        out.setdefault(row["platform"], []).append((row["route"], row["path"], sim_path))
    return out


def route_split(routes: list[str], train_frac: float = 0.8, seed: int = 17) -> set[str]:
    uniq = sorted(set(routes))
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(uniq))
    n_train = int(round(train_frac * len(uniq)))
    return set([uniq[i] for i in perm[:n_train]])


FEAT_NAMES_NO_INT = ["delta", "delta*v", "v", "v^2", "ddelta", "ddelta*v",
                     "yr_v1", "yr_v1*v", "a_long", "ped", "brake"]


def _nan_to_zero(x):
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)


def featurise_no_intercept(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    t = sim_df["t_s"].to_numpy()
    delta = _nan_to_zero(sim_df["delta_road_rad"].to_numpy())
    v = _nan_to_zero(sim_df["v_mps"].to_numpy())
    a_long = _nan_to_zero(sim_df["a_long_mps2"].to_numpy())
    ped = _nan_to_zero(sim_df["accel_pedal_pct"].to_numpy())
    brk = _nan_to_zero(sim_df["brake_pressed"].to_numpy().astype(float))
    dt = np.diff(t, prepend=t[0])
    dt_safe = np.where(dt > 0, dt, 1e-3)
    ddelta = _nan_to_zero(np.diff(delta, prepend=delta[0]) / dt_safe)
    return np.column_stack([
        delta, delta * v, v, v * v, ddelta, ddelta * v,
        yr_v1, yr_v1 * v, a_long, ped, brk,
    ])


def collect_residuals(segs, platform):
    Xs, ys = [], []
    for route, so_path, sim_path in segs:
        sim_df = pd.read_csv(so_path)[ALLOW].copy()
        yr_truth = pd.read_csv(sim_path)["yaw_rate_meas_rads"].to_numpy()
        if len(yr_truth) != len(sim_df):
            n = min(len(yr_truth), len(sim_df))
            sim_df = sim_df.iloc[:n].reset_index(drop=True)
            yr_truth = yr_truth[:n]
        yr_v1 = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy()
        X = featurise_no_intercept(sim_df, yr_v1)
        Xs.append(X)
        ys.append(yr_truth - yr_v1)
    return np.vstack(Xs), np.concatenate(ys)


def ridge_fit(X, y, lam):
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd = np.where(sd < 1e-9, 1.0, sd)
    Xs = (X - mu) / sd
    n, p = Xs.shape
    A = Xs.T @ Xs + lam * np.eye(p)
    w = np.linalg.solve(A, Xs.T @ y)
    yhat = Xs @ w
    return {
        "w": w.tolist(), "mu": mu.tolist(), "sd": sd.tolist(),
        "lam": lam,
        "r2": float(1 - np.sum((y - yhat) ** 2) / max(np.sum((y - y.mean()) ** 2), 1e-12)),
    }


def ridge_apply(coef, X):
    mu = np.asarray(coef["mu"])
    sd = np.asarray(coef["sd"])
    w = np.asarray(coef["w"])
    return ((X - mu) / sd) @ w


def score(segs, predict_fn, platform):
    yaw_ss, yaw_n = 0.0, 0
    cte_ss, cte_bins = 0.0, 0
    for route, so_path, sim_path in segs:
        sim_df = pd.read_csv(so_path)[ALLOW].copy()
        yr_truth = pd.read_csv(sim_path)["yaw_rate_meas_rads"].to_numpy()
        if len(yr_truth) != len(sim_df):
            n = min(len(yr_truth), len(sim_df))
            sim_df = sim_df.iloc[:n].reset_index(drop=True)
            yr_truth = yr_truth[:n]
        yr_pred = predict_fn(sim_df, platform)["yaw_rate_pred_rads"].to_numpy()
        e = yr_pred - yr_truth
        yaw_ss += float(np.sum(e * e))
        yaw_n += len(e)
        t = sim_df["t_s"].to_numpy()
        v = sim_df["v_mps"].to_numpy()
        sum_sq, n_bins, _ = cte_rmse_segment(t, v, yr_truth, yr_pred)
        cte_ss += sum_sq
        cte_bins += n_bins
    yaw = math.sqrt(yaw_ss / max(yaw_n, 1))
    cte = math.sqrt(cte_ss / max(cte_bins, 1)) if cte_bins > 0 else float("nan")
    return yaw, cte, yaw_n, cte_bins, yaw_ss, cte_ss


def main():
    idx = load_index()
    print("Index:", {k: len(v) for k, v in idx.items()})

    biases: dict[str, float] = {}
    ridges: dict[str, dict] = {}
    per_plat: dict[str, dict] = {}
    pool: dict[str, dict] = {n: {"yss": 0.0, "yn": 0, "css": 0.0, "cb": 0}
                             for n in ["V1", "V1+bias", "V1+bias+ridge", "best_per_plat"]}

    for platform in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1",
                     "HYUNDAI_IONIQ_5"]:
        segs = idx[platform]
        routes = [r for r, _, _ in segs]
        train_routes = route_split(routes, train_frac=0.8, seed=17)
        train_segs = [s for s in segs if s[0] in train_routes]
        dev_segs = [s for s in segs if s[0] not in train_routes]
        print(f"\n=== {platform}: {len(train_segs)} train / {len(dev_segs)} dev ===")

        X_tr, y_tr = collect_residuals(train_segs, platform)
        bias = float(y_tr.mean())
        print(f"  resid: n={len(y_tr)} mean={bias:+.6f} std={y_tr.std():.6f}")

        # lam selection via random 90/10 within train
        y_c = y_tr - bias
        rng = np.random.default_rng(42)
        perm = rng.permutation(len(y_c))
        cut = int(0.9 * len(perm))
        tr_i, vl_i = perm[:cut], perm[cut:]
        best_lam, best_r2 = None, -np.inf
        for lam in [0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0]:
            coef = ridge_fit(X_tr[tr_i], y_c[tr_i], lam=lam)
            yhat = ridge_apply(coef, X_tr[vl_i])
            ss = float(np.sum((y_c[vl_i] - yhat) ** 2))
            ss_tot = float(np.sum((y_c[vl_i] - y_c[vl_i].mean()) ** 2))
            r2 = 1 - ss / max(ss_tot, 1e-12)
            if r2 > best_r2:
                best_r2, best_lam = r2, lam
        print(f"  lam_best={best_lam}  inner-val R2={best_r2:+.4f}")
        coef = ridge_fit(X_tr, y_c, lam=best_lam)
        coef["bias"] = bias
        coef["features"] = FEAT_NAMES_NO_INT
        biases[platform] = bias
        ridges[platform] = coef
        print(f"  ridge full-train R2={coef['r2']:+.4f}")
        print(f"  weights (standardised): " +
              ", ".join(f"{n}={w:+.5f}" for n, w in zip(FEAT_NAMES_NO_INT, coef['w'])))

        def predict_v1_plus_bias(sim_df, plat, bias=bias):
            out = predict_v1(sim_df, plat)
            out["yaw_rate_pred_rads"] = out["yaw_rate_pred_rads"].to_numpy() + bias
            return out

        def predict_full(sim_df, plat, bias=bias, coef=coef):
            v1 = predict_v1(sim_df, plat)["yaw_rate_pred_rads"].to_numpy()
            X = featurise_no_intercept(sim_df, v1)
            r = ridge_apply(coef, X)
            return pd.DataFrame({"yaw_rate_pred_rads": v1 + bias + r}, index=sim_df.index)

        yaw_v1, cte_v1, yn, cb, yss_v1, css_v1 = score(dev_segs, predict_v1, platform)
        yaw_b, cte_b, _, _, yss_b, css_b = score(dev_segs, predict_v1_plus_bias, platform)
        yaw_f, cte_f, _, _, yss_f, css_f = score(dev_segs, predict_full, platform)
        per_plat[platform] = {
            "n_dev": len(dev_segs), "yaw_n": yn, "cte_bins": cb,
            "V1": {"yaw": yaw_v1, "cte": cte_v1},
            "V1+bias": {"yaw": yaw_b, "cte": cte_b},
            "V1+bias+ridge": {"yaw": yaw_f, "cte": cte_f},
        }
        print(f"  V1            yaw={yaw_v1:.6f}  cte={cte_v1:.4f}")
        print(f"  V1+bias       yaw={yaw_b:.6f}  cte={cte_b:.4f}")
        print(f"  V1+bias+ridge yaw={yaw_f:.6f}  cte={cte_f:.4f}")

        for name, (yss, css) in [("V1", (yss_v1, css_v1)),
                                 ("V1+bias", (yss_b, css_b)),
                                 ("V1+bias+ridge", (yss_f, css_f))]:
            pool[name]["yss"] += yss
            pool[name]["yn"] += yn
            pool[name]["css"] += css
            pool[name]["cb"] += cb

        # per-platform best CTE (and yaw): choose smallest cte_rmse on dev
        candidates = [("V1", yaw_v1, cte_v1, yss_v1, css_v1),
                      ("V1+bias", yaw_b, cte_b, yss_b, css_b),
                      ("V1+bias+ridge", yaw_f, cte_f, yss_f, css_f)]
        # prefer minimising (yaw + cte/100) as a composite to avoid CTE-noise picks
        best = min(candidates, key=lambda c: c[1] + c[2] / 100.0)
        per_plat[platform]["best_variant"] = best[0]
        pool["best_per_plat"]["yss"] += best[3]
        pool["best_per_plat"]["yn"] += yn
        pool["best_per_plat"]["css"] += best[4]
        pool["best_per_plat"]["cb"] += cb
        print(f"  >> best variant for {platform}: {best[0]}")

    print("\n=== POOLED DEV (Lightning+Mach-E+IONIQ-5) ===")
    pool_results = {}
    for name, d in pool.items():
        yaw = math.sqrt(d["yss"] / d["yn"])
        cte = math.sqrt(d["css"] / d["cb"]) if d["cb"] > 0 else float("nan")
        pool_results[name] = {"yaw": yaw, "cte": cte, "yaw_n": d["yn"], "cte_bins": d["cb"]}
        print(f"  {name:18s} yaw={yaw:.6f}  cte={cte:.4f}")

    # Persist
    artifact = {
        "biases": biases,
        "ridges": ridges,
        "feature_names": FEAT_NAMES_NO_INT,
        "per_platform_dev": per_plat,
        "pooled_dev": pool_results,
        "best_variant_per_platform": {p: per_plat[p]["best_variant"] for p in per_plat},
    }
    (ARTIFACTS / "coeffs.json").write_text(json.dumps(artifact, indent=2))
    print(f"\nWrote {ARTIFACTS / 'coeffs.json'}")


if __name__ == "__main__":
    main()
