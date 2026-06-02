"""Explore data, build per-platform additive bias correction + ridge residual head on V1.

Strategy (cohort §0+§2+§4 stack):
  - Score V1 on each platform.
  - Compute residual r = yaw_truth - yaw_v1_pred.
  - Estimate per-platform additive bias b = mean(r) (median fallback).
  - Fit ridge regression on features (delta_road, v, v*delta, delta^2, lat_accel_proxy,
    abs_delta, brake, a_long) -> residual minus bias.
  - Evaluate yaw RMSE + CTE RMSE per platform vs V1, with held-out fold.
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-03")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))

from v1_baseline import predict_v1, PLATFORM_PARAMS_V1  # type: ignore
from traj_metrics import cte_rmse_segment, integrate_trajectory  # type: ignore

INPUT_COLS = ["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
              "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]

def list_segments(platform: str, root: Path) -> list[Path]:
    base = root / "data" / "sim" / "segments" / platform
    return sorted(base.rglob("sim.csv"))

def load_segment(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p)
    return df

def build_features(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    delta = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    a_long = sim_df["a_long_mps2"].to_numpy()
    brake = sim_df["brake_pressed"].to_numpy().astype(float)
    # lateral acc proxy from V1 yaw rate
    a_lat_proxy = v * yr_v1
    # derivative of delta over time
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 1e-3, dt)
    ddelta = np.gradient(delta, t)
    feats = np.column_stack([
        delta,
        v,
        delta * v,
        delta * v * v,
        np.sign(delta) * delta * delta,
        a_lat_proxy,
        a_long,
        brake,
        ddelta,
        ddelta * v,
        np.ones_like(delta),
    ])
    return feats

def fit_ridge(X: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    # Solve (X^T X + lam I) w = X^T y; do not regularize intercept (last col).
    XtX = X.T @ X
    p = X.shape[1]
    R = lam * np.eye(p)
    R[-1, -1] = 0.0
    w = np.linalg.solve(XtX + R, X.T @ y)
    return w

def score_yaw_rmse(yr_truth, yr_pred):
    return float(np.sqrt(np.mean((yr_truth - yr_pred) ** 2)))

def score_cte_per_segment(df, yr_pred):
    t = df["t_s"].to_numpy()
    v = df["v_mps"].to_numpy()
    yr_truth = df["yaw_rate_meas_rads"].to_numpy()
    return cte_rmse_segment(t, v, yr_truth, yr_pred)

def main():
    summary = {}
    cache = {}
    print("Loading segments...")
    for plat in PLATFORMS:
        seg_paths = list_segments(plat, ROOT)
        segs = []
        for p in seg_paths:
            df = load_segment(p)
            if "yaw_rate_meas_rads" not in df.columns: continue
            if len(df) < 50: continue
            missing = [c for c in INPUT_COLS if c not in df.columns]
            if missing:
                for c in missing:
                    df[c] = 0.0
            sim_df = df[INPUT_COLS].copy()
            yr_v1 = predict_v1(sim_df, plat)["yaw_rate_pred_rads"].to_numpy()
            segs.append({"path": str(p), "df": df, "sim_df": sim_df, "yr_v1": yr_v1})
        cache[plat] = segs
        print(f"  {plat}: {len(segs)} segments")

    # Concatenate per-platform residual training data
    coeffs_out = {}
    for plat in PLATFORMS:
        segs = cache[plat]
        # Compute concat residual
        Xs, ys = [], []
        for s in segs:
            r = s["df"]["yaw_rate_meas_rads"].to_numpy() - s["yr_v1"]
            X = build_features(s["sim_df"], s["yr_v1"])
            Xs.append(X); ys.append(r)
        X = np.vstack(Xs); y = np.concatenate(ys)
        print(f"\n=== {plat} === residual stats: mean={y.mean():.6f}, std={y.std():.6f}, n={len(y)}")
        # 5-fold route-grouped CV: each fold = a contiguous block of segments
        n_segs = len(segs)
        rng = np.random.default_rng(42)
        order = np.arange(n_segs)
        rng.shuffle(order)
        folds = np.array_split(order, min(5, n_segs))
        # Run a small lam sweep + plain bias baseline
        results = {}
        # Pure bias-only model
        for lam in [None, 1.0, 10.0, 100.0, 300.0, 1000.0]:
            yaw_rmses_pre, yaw_rmses_post = [], []
            cte_sumsq_pre = cte_sumsq_post = 0.0
            cte_bins_pre = cte_bins_post = 0
            for k, val_idx in enumerate(folds):
                val_set = set(int(i) for i in val_idx)
                tr_X, tr_y = [], []
                for i, s in enumerate(segs):
                    if i in val_set: continue
                    r = s["df"]["yaw_rate_meas_rads"].to_numpy() - s["yr_v1"]
                    Xi = build_features(s["sim_df"], s["yr_v1"])
                    tr_X.append(Xi); tr_y.append(r)
                tr_X = np.vstack(tr_X); tr_y = np.concatenate(tr_y)
                if lam is None:
                    # bias-only
                    w = np.zeros(tr_X.shape[1]); w[-1] = float(tr_y.mean())
                else:
                    w = fit_ridge(tr_X, tr_y, lam)
                for i in val_set:
                    s = segs[i]
                    Xi = build_features(s["sim_df"], s["yr_v1"])
                    delta_yr = Xi @ w
                    yr_pre = s["yr_v1"]
                    yr_post = yr_pre + delta_yr
                    yr_truth = s["df"]["yaw_rate_meas_rads"].to_numpy()
                    yaw_rmses_pre.append((np.sum((yr_truth - yr_pre)**2), len(yr_truth)))
                    yaw_rmses_post.append((np.sum((yr_truth - yr_post)**2), len(yr_truth)))
                    sq, nb, _ = score_cte_per_segment(s["df"], yr_pre)
                    cte_sumsq_pre += sq; cte_bins_pre += nb
                    sq, nb, _ = score_cte_per_segment(s["df"], yr_post)
                    cte_sumsq_post += sq; cte_bins_post += nb
            pre_ss = sum(a for a,_ in yaw_rmses_pre); pre_n = sum(b for _,b in yaw_rmses_pre)
            post_ss = sum(a for a,_ in yaw_rmses_post); post_n = sum(b for _,b in yaw_rmses_post)
            yaw_pre = math.sqrt(pre_ss/pre_n); yaw_post = math.sqrt(post_ss/post_n)
            cte_pre = math.sqrt(cte_sumsq_pre/cte_bins_pre) if cte_bins_pre else float("nan")
            cte_post = math.sqrt(cte_sumsq_post/cte_bins_post) if cte_bins_post else float("nan")
            results[str(lam)] = {
                "yaw_pre": yaw_pre, "yaw_post": yaw_post,
                "cte_pre": cte_pre, "cte_post": cte_post,
                "delta_yaw_pct": (yaw_post-yaw_pre)/yaw_pre*100,
                "delta_cte_pct": (cte_post-cte_pre)/cte_pre*100,
            }
            print(f"  lam={lam}: yaw {yaw_pre:.6f}->{yaw_post:.6f} ({results[str(lam)]['delta_yaw_pct']:+.2f}%), cte {cte_pre:.2f}->{cte_post:.2f} ({results[str(lam)]['delta_cte_pct']:+.2f}%)")
        # Pick best lam by yaw_post (or by some combined score). Use yaw_post as primary.
        best_lam = min(results.keys(), key=lambda k: results[k]["yaw_post"])
        print(f"  best lam by yaw: {best_lam}")
        # Fit final on full data
        if best_lam == "None":
            w_final = np.zeros(X.shape[1]); w_final[-1] = float(y.mean())
            best_lam_val = None
        else:
            best_lam_val = float(best_lam)
            w_final = fit_ridge(X, y, best_lam_val)
        coeffs_out[plat] = {"lam": best_lam_val, "w": w_final.tolist(), "cv": results[best_lam]}
        summary[plat] = results
    out = Path(ROOT) / "out"
    (out / "coeffs.json").write_text(json.dumps(coeffs_out, indent=2))
    (out / "cv_summary.json").write_text(json.dumps(summary, indent=2))
    print("\nWrote out/coeffs.json and out/cv_summary.json")

if __name__ == "__main__":
    main()
