"""Fit per-platform bias + residual-learner ridge head on top of V1.

Approach (driven by cohort findings §2 and §4):
1. Load all sim.csv from data/sim/segments/ for the three fittable platforms.
2. Compute V1 predictions.
3. Compute V1 residual = truth - V1.
4. Fit per-platform additive bias on residual.
5. Fit ridge on additional residual features (after bias).
6. Evaluate locally on a held-out split: yaw RMSE + pooled CTE RMSE.
7. Save coefficients to coeffs.json.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-06")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))

import importlib.util
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
_v1 = _load("v1_baseline", str(ROOT / "code" / "v1_baseline.py"))
_tm = _load("traj_metrics", str(ROOT / "_shared" / "traj_metrics.py"))
predict_v1 = _v1.predict_v1
PLATFORM_PARAMS_V1 = _v1.PLATFORM_PARAMS_V1
cte_rmse_segment = _tm.cte_rmse_segment

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
DATA_DIR = ROOT / "data" / "sim" / "segments"


def segment_files(platform):
    return sorted((DATA_DIR / platform).rglob("sim.csv"))


def feature_matrix(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    """Build residual-learner features from V1-aware quantities (sim_df has only allowlist cols at predict time)."""
    v = sim_df["v_mps"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt[dt <= 0] = 1e-3
    # Steering rate
    ddelta = np.gradient(delta, t)
    # Yaw rate derivative (from V1 — proxy for measured yaw-rate-derivative since we don't have truth)
    dyr_v1 = np.gradient(yr_v1, t)
    a_lat_proxy = v * yr_v1
    # Features
    feats = np.column_stack([
        np.ones_like(v),                 # bias (intercept, will be absorbed by per-platform bias)
        v,                                # 1
        delta,                            # 2
        v * delta,                        # 3
        ddelta,                           # 4
        v * ddelta,                       # 5
        yr_v1,                            # 6
        v * yr_v1,                        # 7
        dyr_v1,                           # 8
        a_lat_proxy,                      # 9
        np.sign(delta) * delta * delta,   # 10 nonlinear in steering
    ])
    return feats


def load_platform(platform, max_segments=None):
    files = segment_files(platform)
    if max_segments:
        files = files[:max_segments]
    rows = []
    seg_index = []
    for i, f in enumerate(files):
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns or len(df) < 10:
            continue
        df["_seg"] = i
        df["_file"] = str(f)
        rows.append(df)
        seg_index.append((i, str(f)))
    if not rows:
        return None
    return pd.concat(rows, ignore_index=True), files


def train_eval():
    np.random.seed(42)
    results = {}
    coeffs = {}

    for platform in PLATFORMS:
        print(f"\n=== {platform} ===")
        loaded = load_platform(platform)
        if loaded is None:
            print(f"  no segments")
            continue
        df, files = loaded
        seg_ids = sorted(df["_seg"].unique())
        n_seg = len(seg_ids)
        np.random.shuffle(seg_ids)
        n_train = int(0.8 * n_seg)
        train_segs = set(seg_ids[:n_train])
        dev_segs = set(seg_ids[n_train:])

        # Build features and V1 preds per segment
        train_X, train_y = [], []
        dev_X, dev_y = [], []
        # Also track for CTE later
        seg_data = {}  # seg_id -> dict(t, v, yr_truth, yr_v1, feats)

        for sid in seg_ids:
            sub = df[df["_seg"] == sid].sort_values("t_s").reset_index(drop=True)
            if len(sub) < 10:
                continue
            needed = ["t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
                      "a_long_mps2", "accel_pedal_pct", "brake_pressed",
                      "yaw_rate_pred_rads"]
            for c in needed:
                if c not in sub.columns:
                    sub[c] = 0.0
            sim_in = sub[needed].copy()
            v1_out = predict_v1(sim_in, platform)
            yr_v1 = v1_out["yaw_rate_pred_rads"].to_numpy()
            yr_truth = sub["yaw_rate_meas_rads"].to_numpy()
            feats = feature_matrix(sim_in, yr_v1)
            resid = yr_truth - yr_v1
            seg_data[sid] = {
                "t": sub["t_s"].to_numpy(),
                "v": sub["v_mps"].to_numpy(),
                "yr_truth": yr_truth,
                "yr_v1": yr_v1,
                "feats": feats,
                "resid": resid,
            }
            if sid in train_segs:
                train_X.append(feats)
                train_y.append(resid)
            else:
                dev_X.append(feats)
                dev_y.append(resid)

        train_X = np.vstack(train_X)
        train_y = np.concatenate(train_y)
        dev_X = np.vstack(dev_X) if dev_X else None
        dev_y = np.concatenate(dev_y) if dev_y is not None else None

        # 1) Per-platform additive bias = mean residual on train
        bias = float(np.mean(train_y))
        print(f"  bias (mean train residual) = {bias:.6f}")

        # 2) Ridge fit on residual MINUS bias, using features (drop the intercept column since bias handles it)
        train_y_de = train_y - bias
        # Drop intercept col 0
        X = train_X[:, 1:]
        # Standardize features for ridge
        mu = X.mean(axis=0)
        sd = X.std(axis=0) + 1e-9
        Xs = (X - mu) / sd

        # Try several lambdas, pick by dev yaw RMSE on full V1+correction
        lambdas = [0.1, 1.0, 10.0, 30.0, 100.0, 300.0, 1000.0, 3000.0]
        best = None
        for lam in lambdas:
            # Ridge closed-form
            A = Xs.T @ Xs + lam * np.eye(Xs.shape[1])
            b = Xs.T @ train_y_de
            w = np.linalg.solve(A, b)

            # Evaluate on dev
            train_pred_corr = bias + Xs @ w
            train_yaw_rmse = float(np.sqrt(np.mean((train_y - train_pred_corr) ** 2)))

            # Dev
            if dev_X is not None:
                Xd = (dev_X[:, 1:] - mu) / sd
                dev_pred_corr = bias + Xd @ w
                dev_yaw_rmse = float(np.sqrt(np.mean((dev_y - dev_pred_corr) ** 2)))
            else:
                dev_yaw_rmse = train_yaw_rmse

            # V1 baseline (no correction) — yaw RMSE = sqrt(mean(resid^2))
            v1_dev_rmse = float(np.sqrt(np.mean(dev_y ** 2))) if dev_y is not None else None
            v1_train_rmse = float(np.sqrt(np.mean(train_y ** 2)))

            score = dev_yaw_rmse
            print(f"  lam={lam:7.2f}  train_yaw_rmse={train_yaw_rmse:.5f}  dev_yaw_rmse={dev_yaw_rmse:.5f}  (V1 dev={v1_dev_rmse:.5f})")
            if best is None or score < best["dev_yaw_rmse"]:
                best = {
                    "lam": lam,
                    "w": w.tolist(),
                    "mu": mu.tolist(),
                    "sd": sd.tolist(),
                    "bias": bias,
                    "dev_yaw_rmse": dev_yaw_rmse,
                    "train_yaw_rmse": train_yaw_rmse,
                    "v1_dev_yaw_rmse": v1_dev_rmse,
                    "v1_train_yaw_rmse": v1_train_rmse,
                }
        print(f"  BEST lam={best['lam']}  dev_yaw_rmse={best['dev_yaw_rmse']:.5f}  (V1 was {best['v1_dev_yaw_rmse']:.5f})")

        # CTE eval on dev
        sum_sq_v1 = 0.0
        n_bins_v1 = 0
        sum_sq_new = 0.0
        n_bins_new = 0
        w_arr = np.array(best["w"])
        mu_arr = np.array(best["mu"])
        sd_arr = np.array(best["sd"])
        for sid in dev_segs:
            if sid not in seg_data:
                continue
            d = seg_data[sid]
            Xs_seg = (d["feats"][:, 1:] - mu_arr) / sd_arr
            corr = bias + Xs_seg @ w_arr
            yr_new = d["yr_v1"] + corr
            ss, nb, _ = cte_rmse_segment(d["t"], d["v"], d["yr_truth"], d["yr_v1"])
            sum_sq_v1 += ss
            n_bins_v1 += nb
            ss2, nb2, _ = cte_rmse_segment(d["t"], d["v"], d["yr_truth"], yr_new)
            sum_sq_new += ss2
            n_bins_new += nb2
        cte_v1 = math.sqrt(sum_sq_v1 / n_bins_v1) if n_bins_v1 else None
        cte_new = math.sqrt(sum_sq_new / n_bins_new) if n_bins_new else None
        print(f"  dev CTE V1 = {cte_v1}  dev CTE corrected = {cte_new}")

        coeffs[platform] = {
            "bias": best["bias"],
            "w": best["w"],
            "mu": best["mu"],
            "sd": best["sd"],
            "lam": best["lam"],
        }
        results[platform] = {
            "dev_yaw_rmse_v1": best["v1_dev_yaw_rmse"],
            "dev_yaw_rmse_new": best["dev_yaw_rmse"],
            "dev_cte_v1": cte_v1,
            "dev_cte_new": cte_new,
        }

    # Tesla = passthrough (no truth)
    coeffs["TESLA_MODEL_3"] = {"passthrough": True}

    out_dir = ROOT / "out"
    (out_dir / "coeffs.json").write_text(json.dumps(coeffs, indent=2))
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    print("\n=== Summary ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    train_eval()
