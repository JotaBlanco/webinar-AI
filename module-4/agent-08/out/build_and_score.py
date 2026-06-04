"""End-to-end: load sim segments, evaluate V0 / V1 / V1+bias / V1+residual-learner.

Uses sim/segments/ (full schema with truth) for fitting + scoring.
Scoring mirrors sim-only contract — predict() functions only read allowlist columns.
"""
from __future__ import annotations
import os, sys, json, math, glob, pickle
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-08")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))
from v1_baseline import predict_v1
from traj_metrics import cte_rmse_segment

SIM_ROOT = ROOT / "data" / "sim" / "segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
# Skip TESLA (no truth)

ALLOWLIST = [
    "t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
    "a_long_mps2", "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads",
]


def list_segments():
    rows = []
    for plat in PLATFORMS:
        plat_dir = SIM_ROOT / plat
        if not plat_dir.exists():
            continue
        for csv_path in plat_dir.rglob("sim.csv"):
            # Route id = first level after platform dir
            rel = csv_path.relative_to(plat_dir).parts
            route = rel[0]
            rows.append({"platform": plat, "route": route, "path": str(csv_path)})
    return pd.DataFrame(rows)


def load_seg(path):
    df = pd.read_csv(path)
    # add accel_pedal_pct & brake_pressed if missing (older sim.csv schemas)
    if "accel_pedal_pct" not in df.columns:
        df["accel_pedal_pct"] = 0.0
    if "brake_pressed" not in df.columns:
        df["brake_pressed"] = 0
    return df


def yaw_rmse_pooled(sum_sq, n):
    return math.sqrt(sum_sq / n) if n else float("nan")


def score_predict(predict_fn, segments, *, label):
    yaw_sum_sq = 0.0
    yaw_n = 0
    cte_sum_sq = 0.0
    cte_bins = 0
    per_plat = {}
    for _, r in segments.iterrows():
        df = load_seg(r["path"])
        truth = df["yaw_rate_meas_rads"].to_numpy()
        # Build allowlist-only input
        sim_in = df[ALLOWLIST].copy()
        pred_df = predict_fn(sim_in, r["platform"])
        pred = pred_df["yaw_rate_pred_rads"].to_numpy()
        resid = pred - truth
        yaw_sum_sq += float((resid ** 2).sum())
        yaw_n += len(resid)

        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        sq, nb, _ = cte_rmse_segment(t, v, truth, pred)
        cte_sum_sq += sq
        cte_bins += nb

        pp = per_plat.setdefault(r["platform"], {"yss": 0.0, "yn": 0, "cs": 0.0, "cb": 0})
        pp["yss"] += float((resid ** 2).sum())
        pp["yn"] += len(resid)
        pp["cs"] += sq
        pp["cb"] += nb
    out = {
        "label": label,
        "yaw_rmse": yaw_rmse_pooled(yaw_sum_sq, yaw_n),
        "cte_rmse": math.sqrt(cte_sum_sq / cte_bins) if cte_bins else float("nan"),
        "n_samples": yaw_n,
        "n_bins": cte_bins,
        "per_platform": {
            k: {
                "yaw_rmse": math.sqrt(v["yss"] / v["yn"]) if v["yn"] else float("nan"),
                "cte_rmse": math.sqrt(v["cs"] / v["cb"]) if v["cb"] else float("nan"),
            }
            for k, v in per_plat.items()
        },
    }
    return out


# ---------- predict functions ----------
def predict_v0(sim_df, platform):
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
        index=sim_df.index,
    )


def make_predict_v1_bias(bias_per_platform):
    """V1 + per-platform constant yaw-rate bias correction."""
    def predict(sim_df, platform):
        out = predict_v1(sim_df, platform)
        b = bias_per_platform.get(platform, 0.0)
        out["yaw_rate_pred_rads"] = out["yaw_rate_pred_rads"].to_numpy() - b
        return out
    return predict


def make_features(sim_df, v1_pred):
    """Safe (allowlist-only) features for residual learner."""
    v = sim_df["v_mps"].to_numpy()
    d = sim_df["delta_road_rad"].to_numpy()
    a = sim_df["a_long_mps2"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    # ay proxy = v * v1_pred
    ay = v * v1_pred
    X = np.column_stack([
        np.ones_like(v),
        v1_pred,
        d,
        v * d,
        v * v * d,
        a,
        ay,
        np.sign(d) * d * d,  # nonlinear steering
        v,
    ])
    return X


def make_predict_v1_residlearner(coeffs_per_platform):
    def predict(sim_df, platform):
        out = predict_v1(sim_df, platform).copy()
        if platform not in coeffs_per_platform:
            return out
        v1_pred = out["yaw_rate_pred_rads"].to_numpy()
        X = make_features(sim_df, v1_pred)
        beta = np.array(coeffs_per_platform[platform])
        delta = X @ beta
        out["yaw_rate_pred_rads"] = v1_pred - delta  # subtract estimated residual
        return out
    return predict


def fit_bias(segments):
    """Per-platform mean of (V1_pred - truth) -> bias to subtract."""
    bias = {}
    for plat, grp in segments.groupby("platform"):
        s = 0.0
        n = 0
        for _, r in grp.iterrows():
            df = load_seg(r["path"])
            sim_in = df[ALLOWLIST].copy()
            v1 = predict_v1(sim_in, plat)["yaw_rate_pred_rads"].to_numpy()
            truth = df["yaw_rate_meas_rads"].to_numpy()
            resid = v1 - truth
            s += float(resid.sum())
            n += len(resid)
        bias[plat] = s / n if n else 0.0
    return bias


def fit_residlearner(segments, ridge=1e-3):
    """Per-platform ridge regression: residual = V1_pred - truth ≈ X @ beta."""
    coefs = {}
    diag = {}
    for plat, grp in segments.groupby("platform"):
        XtX = None
        Xty = None
        n_total = 0
        for _, r in grp.iterrows():
            df = load_seg(r["path"])
            sim_in = df[ALLOWLIST].copy()
            v1 = predict_v1(sim_in, plat)["yaw_rate_pred_rads"].to_numpy()
            truth = df["yaw_rate_meas_rads"].to_numpy()
            resid = v1 - truth
            X = make_features(sim_in, v1)
            if XtX is None:
                XtX = np.zeros((X.shape[1], X.shape[1]))
                Xty = np.zeros(X.shape[1])
            XtX += X.T @ X
            Xty += X.T @ resid
            n_total += len(resid)
        # ridge
        reg = ridge * np.trace(XtX) / XtX.shape[0] * np.eye(XtX.shape[0])
        beta = np.linalg.solve(XtX + reg, Xty)
        coefs[plat] = beta.tolist()
        diag[plat] = {"n_samples": n_total}
    return coefs, diag


def route_grouped_cv_resid(segments, k=5, ridge=1e-3, seed=0):
    """K-fold route-grouped CV for residual learner. Returns per-fold pooled scores."""
    rng = np.random.default_rng(seed)
    fold_scores = []
    # group by (platform, route)
    keys = segments.groupby(["platform", "route"]).size().reset_index().drop(columns=0)
    keys = keys.sample(frac=1, random_state=seed).reset_index(drop=True)
    folds = np.array_split(np.arange(len(keys)), k)
    for fi, val_idx in enumerate(folds):
        val_keys = set(map(tuple, keys.iloc[val_idx][["platform", "route"]].values.tolist()))
        train_mask = ~segments.set_index(["platform", "route"]).index.isin(val_keys)
        train_segs = segments[train_mask].reset_index(drop=True)
        val_segs = segments[~train_mask].reset_index(drop=True)
        coefs, _ = fit_residlearner(train_segs, ridge=ridge)
        pred_fn = make_predict_v1_residlearner(coefs)
        res = score_predict(pred_fn, val_segs, label=f"fold{fi}")
        fold_scores.append(res)
    yaw_rmses = [s["yaw_rmse"] for s in fold_scores]
    cte_rmses = [s["cte_rmse"] for s in fold_scores]
    return {
        "yaw_mean": float(np.mean(yaw_rmses)),
        "yaw_std": float(np.std(yaw_rmses)),
        "cte_mean": float(np.mean(cte_rmses)),
        "cte_std": float(np.std(cte_rmses)),
        "fold_scores": fold_scores,
    }


def main():
    segments = list_segments()
    print(f"Loaded {len(segments)} segments across {segments['platform'].nunique()} platforms")
    print(segments.groupby("platform").size())

    # Score baselines on full data
    res_v0 = score_predict(predict_v0, segments, label="V0")
    res_v1 = score_predict(predict_v1, segments, label="V1")
    print("V0:", json.dumps({"yaw_rmse": res_v0["yaw_rmse"], "cte_rmse": res_v0["cte_rmse"]}, indent=2))
    print("V1:", json.dumps({"yaw_rmse": res_v1["yaw_rmse"], "cte_rmse": res_v1["cte_rmse"]}, indent=2))

    # Fit bias
    bias = fit_bias(segments)
    print("Bias per platform:", bias)
    pred_bias = make_predict_v1_bias(bias)
    res_bias = score_predict(pred_bias, segments, label="V1+bias")
    print("V1+bias:", json.dumps({"yaw_rmse": res_bias["yaw_rmse"], "cte_rmse": res_bias["cte_rmse"]}, indent=2))

    # Fit residual learner
    coefs, diag = fit_residlearner(segments)
    pred_rl = make_predict_v1_residlearner(coefs)
    res_rl = score_predict(pred_rl, segments, label="V1+resid")
    print("V1+resid (in-sample):", json.dumps({"yaw_rmse": res_rl["yaw_rmse"], "cte_rmse": res_rl["cte_rmse"]}, indent=2))

    # 5-fold route-grouped CV for resid learner
    cv = route_grouped_cv_resid(segments, k=5)
    print("CV V1+resid:", json.dumps({k: v for k, v in cv.items() if k != "fold_scores"}, indent=2))

    # Save all results
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / "scores.json", "w") as f:
        json.dump({
            "V0": res_v0,
            "V1": res_v1,
            "V1_bias": res_bias,
            "V1_resid_insample": res_rl,
            "V1_resid_cv": {k: v for k, v in cv.items() if k != "fold_scores"},
            "bias_per_platform": bias,
        }, f, indent=2)

    # Save coeffs for final-model
    with open(out_dir / "resid_coeffs.json", "w") as f:
        json.dump({"coefs": coefs, "bias": bias, "diag": diag,
                   "feature_names": ["1", "v1_pred", "delta", "v*delta", "v^2*delta",
                                     "a_long", "ay_proxy", "sign(d)*d^2", "v"]}, f, indent=2)
    print("Wrote out/scores.json and out/resid_coeffs.json")


if __name__ == "__main__":
    main()
