"""Fit per-platform bias + small ridge residual learner on V1, with route-grouped CV.

- Train against data/sim/segments/ (truth available).
- Score V1 baseline and candidate models (V1+bias, V1+bias+ridge) under 5-fold route-grouped CV.
- Tesla: passthrough V0 (no truth).
"""
from __future__ import annotations
import sys, json, math, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-01")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))
from v1_baseline import predict_v1, PLATFORM_PARAMS_V1  # type: ignore
from traj_metrics import cte_rmse_segment  # type: ignore

SIM_ROOT = ROOT / "data" / "sim" / "segments"
PLATFORMS_WITH_TRUTH = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]

INPUT_COLS = [
    "t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
    "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads",
]

def list_segments(platform: str):
    """Return list of (route_id, sim_csv_path)."""
    out = []
    pdir = SIM_ROOT / platform
    for route_dir in sorted(pdir.iterdir()):
        if not route_dir.is_dir(): continue
        for seg_dir in sorted(route_dir.iterdir()):
            if not seg_dir.is_dir(): continue
            for sub in sorted(seg_dir.iterdir()):
                if not sub.is_dir(): continue
                f = sub / "sim.csv"
                if f.exists():
                    out.append((route_dir.name, f))
    return out


def load_seg(path: Path, need_truth: bool = True) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Ensure accel_pedal_pct / brake_pressed present (some segs may lack — fill 0)
    for c in ["accel_pedal_pct","brake_pressed"]:
        if c not in df.columns:
            df[c] = 0.0
    return df


def yaw_residual_features(df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    """Features for ridge residual learner (V1 input-domain only, no truth)."""
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    a_long = df["a_long_mps2"].to_numpy()
    # steering rate from delta
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt > 0, dt, 1e-3)
    ddelta = np.gradient(delta, t)
    # a_lat proxy
    a_lat_proxy = v * yr_v1
    feats = np.column_stack([
        yr_v1,
        v,
        v * v,
        delta,
        delta * v,
        ddelta,
        ddelta * v,
        a_long,
        a_lat_proxy,
        a_lat_proxy * v,
        np.sign(delta) * delta * delta,
    ])
    return feats


def score_v1_segment(df: pd.DataFrame, platform: str):
    """Return (yr_pred, yr_truth, t, v, residual)."""
    pred = predict_v1(df, platform)["yaw_rate_pred_rads"].to_numpy()
    truth = df["yaw_rate_meas_rads"].to_numpy()
    return pred, truth, df["t_s"].to_numpy(), df["v_mps"].to_numpy(), truth - pred


def pooled_metrics(segs):
    """segs: list of (t, v, yr_truth, yr_pred). Return yaw RMSE + CTE RMSE."""
    sse_yaw = 0.0; n_yaw = 0
    sse_cte = 0.0; n_bins = 0
    for (t,v,yt,yp) in segs:
        d = yp - yt
        sse_yaw += float(np.sum(d*d))
        n_yaw += len(d)
        s, nb, _ = cte_rmse_segment(t, v, yt, yp)
        sse_cte += s; n_bins += nb
    yaw_rmse = math.sqrt(sse_yaw / max(n_yaw,1))
    cte_rmse = math.sqrt(sse_cte / max(n_bins,1))
    return yaw_rmse, cte_rmse, n_yaw, n_bins


def fit_bias(residuals_pooled: np.ndarray) -> float:
    """Per-platform additive bias = mean residual."""
    return float(np.mean(residuals_pooled))


def fit_ridge(X: np.ndarray, y: np.ndarray, lam: float = 30.0) -> np.ndarray:
    """Ridge regression: w = (X^T X + lam I)^{-1} X^T y. y is residual (truth - V1)."""
    # Standardize features
    mu = X.mean(0); sd = X.std(0) + 1e-9
    Xs = (X - mu) / sd
    # add intercept
    Xs = np.column_stack([np.ones(len(Xs)), Xs])
    A = Xs.T @ Xs
    A += lam * np.eye(A.shape[0])
    A[0,0] -= lam  # don't penalize intercept
    w = np.linalg.solve(A, Xs.T @ y)
    return {"mu": mu, "sd": sd, "w": w}


def apply_ridge(X: np.ndarray, model: dict) -> np.ndarray:
    Xs = (X - model["mu"]) / model["sd"]
    Xs = np.column_stack([np.ones(len(Xs)), Xs])
    return Xs @ model["w"]


def main():
    rng = np.random.default_rng(0)
    K = 5

    # Cache: per platform, segment-level V1 predictions + features + truth + route id
    cache = {}
    for plat in PLATFORMS_WITH_TRUTH:
        print(f"== Loading {plat}", flush=True)
        segs_paths = list_segments(plat)
        print(f"   {len(segs_paths)} segments", flush=True)
        seg_recs = []
        for route_id, path in segs_paths:
            df = load_seg(path)
            if "yaw_rate_meas_rads" not in df.columns: continue
            yr_v1 = predict_v1(df, plat)["yaw_rate_pred_rads"].to_numpy()
            truth = df["yaw_rate_meas_rads"].to_numpy()
            feats = yaw_residual_features(df, yr_v1)
            seg_recs.append({
                "route": route_id,
                "t": df["t_s"].to_numpy(),
                "v": df["v_mps"].to_numpy(),
                "yr_v1": yr_v1,
                "truth": truth,
                "resid": truth - yr_v1,
                "feats": feats,
            })
        cache[plat] = seg_recs

    # Group by route within each platform for K-fold route-grouped CV.
    cv_metrics = {"v1": {}, "v1_bias": {}, "v1_bias_ridge": {}}
    fitted = {}  # final fits on FULL data per platform

    for plat in PLATFORMS_WITH_TRUTH:
        recs = cache[plat]
        routes = sorted({r["route"] for r in recs})
        rng.shuffle(routes)
        folds = [routes[i::K] for i in range(K)]
        per_fold = {"v1": [], "v1_bias": [], "v1_bias_ridge": []}

        for k in range(K):
            test_routes = set(folds[k])
            train = [r for r in recs if r["route"] not in test_routes]
            test  = [r for r in recs if r["route"] in test_routes]

            # Fit bias on train residuals (pooled)
            train_resid = np.concatenate([r["resid"] for r in train])
            bias = fit_bias(train_resid)
            # Fit ridge on (train residual - bias) -> features
            X_tr = np.vstack([r["feats"] for r in train])
            y_tr = np.concatenate([r["resid"] for r in train]) - bias
            ridge = fit_ridge(X_tr, y_tr, lam=30.0)

            # Score on test for each variant
            v1_segs, bias_segs, full_segs = [], [], []
            for r in test:
                yr_v1 = r["yr_v1"]
                yr_bias = yr_v1 + bias
                resid_hat = apply_ridge(r["feats"], ridge)
                yr_full = yr_v1 + bias + resid_hat
                v1_segs.append((r["t"], r["v"], r["truth"], yr_v1))
                bias_segs.append((r["t"], r["v"], r["truth"], yr_bias))
                full_segs.append((r["t"], r["v"], r["truth"], yr_full))

            per_fold["v1"].append(pooled_metrics(v1_segs))
            per_fold["v1_bias"].append(pooled_metrics(bias_segs))
            per_fold["v1_bias_ridge"].append(pooled_metrics(full_segs))

        for variant in ["v1","v1_bias","v1_bias_ridge"]:
            arr = np.array([m[:2] for m in per_fold[variant]])
            cv_metrics[variant][plat] = {
                "yaw_rmse_mean": float(arr[:,0].mean()),
                "yaw_rmse_std": float(arr[:,0].std()),
                "cte_rmse_mean": float(arr[:,1].mean()),
                "cte_rmse_std": float(arr[:,1].std()),
            }

        # Fit final on full data
        full_resid = np.concatenate([r["resid"] for r in recs])
        bias_full = fit_bias(full_resid)
        X_full = np.vstack([r["feats"] for r in recs])
        y_full = full_resid - bias_full
        ridge_full = fit_ridge(X_full, y_full, lam=30.0)
        fitted[plat] = {
            "bias": bias_full,
            "ridge_mu": ridge_full["mu"].tolist(),
            "ridge_sd": ridge_full["sd"].tolist(),
            "ridge_w":  ridge_full["w"].tolist(),
            "n_routes": len(routes),
            "route_cv_sigma": cv_metrics["v1_bias_ridge"][plat]["yaw_rmse_std"],
            "route_cv_bias_sigma": cv_metrics["v1_bias"][plat]["yaw_rmse_std"],
        }

    # Pool across platforms-with-truth (Tesla excluded — passthrough)
    print("\n== Per-platform CV results (mean ± std) ==", flush=True)
    for variant in ["v1","v1_bias","v1_bias_ridge"]:
        print(f"\n{variant}:")
        for plat, m in cv_metrics[variant].items():
            print(f"  {plat}: yaw {m['yaw_rmse_mean']:.6f}±{m['yaw_rmse_std']:.6f}  CTE {m['cte_rmse_mean']:.3f}±{m['cte_rmse_std']:.3f}")

    # Pooled (sample-weighted not done; per-platform means; quote also full-pool by re-scoring full data with final fit)
    # Compute full-data pooled score for V1, v1+bias, v1+bias+ridge using *final* fits
    print("\n== Full-data pooled metrics (final fits, in-sample) ==", flush=True)
    for variant in ["v1","v1_bias","v1_bias_ridge"]:
        all_segs = []
        for plat in PLATFORMS_WITH_TRUTH:
            f = fitted[plat]
            for r in cache[plat]:
                yr_v1 = r["yr_v1"]
                if variant == "v1":
                    yp = yr_v1
                elif variant == "v1_bias":
                    yp = yr_v1 + f["bias"]
                else:
                    rh = apply_ridge(r["feats"], {"mu": np.array(f["ridge_mu"]), "sd": np.array(f["ridge_sd"]), "w": np.array(f["ridge_w"])})
                    yp = yr_v1 + f["bias"] + rh
                all_segs.append((r["t"], r["v"], r["truth"], yp))
        yaw, cte, nyaw, nbins = pooled_metrics(all_segs)
        print(f"  {variant}: yaw RMSE = {yaw:.6f}, CTE RMSE = {cte:.3f}  (n={nyaw}, bins={nbins})")

    # Save coeffs
    out_path = ROOT / "final-model" / "coeffs.json"
    coeffs = {plat: fitted[plat] for plat in PLATFORMS_WITH_TRUTH}
    out_path.write_text(json.dumps(coeffs, indent=2))
    print(f"\nWrote {out_path}")

    # Save cv metrics
    (ROOT / "out" / "cv_metrics.json").write_text(json.dumps(cv_metrics, indent=2))


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\nelapsed {time.time()-t0:.1f}s")
