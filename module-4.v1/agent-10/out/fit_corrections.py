"""Fit per-platform additive yaw bias + ridge residual head on V1 (V0 here is V1).

Strategy:
- Route-grouped train/dev split (80/20 by route).
- Per platform: fit additive scalar bias b such that pred + b ≈ truth (on rows with v>2).
- Per platform: fit ridge residual head r = w·φ(x) where r = (truth - pred - b), and φ uses
  only allowlist columns: delta_road_rad, v_mps, a_long_mps2, delta*v, delta_dot, delta^2,
  delta*|delta|, v*delta_dot.
- Save coefficients to JSON.
- Tesla: no truth — skip both, ship V0 passthrough.
"""
from __future__ import annotations
import json
import sys
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-10")
SEG_ROOT = ROOT / "data" / "sim" / "segments"

PLATFORMS_WITH_TRUTH = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
TRUTH_COL = "yaw_rate_meas_rads"

RNG_SEED = 1729

FEATURE_NAMES = [
    "delta",        # delta_road_rad
    "delta_v",      # delta * v
    "delta_sq",     # delta^2 * sign(delta)
    "v",            # v_mps (centered)
    "a_long",       # a_long_mps2
    "delta_ddot",   # d(delta)/dt
    "v_delta_ddot", # v * d(delta)/dt
    "delta_abs_v",  # |delta| * v
]


def build_features(sim_df: pd.DataFrame):
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    a_long = sim_df["a_long_mps2"].to_numpy(dtype=float) if "a_long_mps2" in sim_df.columns else np.zeros_like(delta)
    t = sim_df["t_s"].to_numpy(dtype=float)
    # finite diff for delta_dot
    delta_dot = np.zeros_like(delta)
    if len(t) >= 2:
        dt = np.diff(t)
        dt = np.where(dt <= 0, 1e-3, dt)
        delta_dot[1:] = np.diff(delta) / dt
        delta_dot[0] = delta_dot[1]
    v_c = v - 15.0  # center near a typical highway speed
    feats = np.column_stack([
        delta,
        delta * v,
        delta * np.abs(delta),
        v_c,
        a_long,
        delta_dot,
        v * delta_dot,
        np.abs(delta) * v,
    ])
    return feats


def list_segments(platform):
    return sorted((SEG_ROOT / platform).glob("*/*/*/sim.csv"))


def route_of(p: Path) -> str:
    return p.resolve().parents[1].name


def split_train_dev(paths, frac_train=0.8, seed=RNG_SEED):
    rng = np.random.default_rng(seed)
    routes = sorted({route_of(p) for p in paths})
    rng.shuffle(routes)
    n_train = int(round(len(routes) * frac_train))
    train_routes = set(routes[:n_train])
    train, dev = [], []
    for p in paths:
        (train if route_of(p) in train_routes else dev).append(p)
    return train, dev, train_routes


def load_segment(p: Path):
    df = pd.read_csv(p)
    if TRUTH_COL not in df.columns or "v_mps" not in df.columns or "t_s" not in df.columns:
        return None
    return df


def fit_platform(paths, l2=10.0, v_filter=2.0):
    """Fit additive bias + ridge head on a list of segment paths."""
    X_list = []
    r_list = []  # residual = truth - (pred + 0); we'll absorb mean as separate bias
    for p in paths:
        df = load_segment(p)
        if df is None:
            continue
        v = df["v_mps"].to_numpy(dtype=float)
        mask = v > v_filter
        if not mask.any():
            continue
        feats = build_features(df)
        truth = df[TRUTH_COL].to_numpy(dtype=float)
        pred = df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        resid = truth - pred  # this is what we want to predict
        X_list.append(feats[mask])
        r_list.append(resid[mask])
    if not X_list:
        return None
    X = np.concatenate(X_list, axis=0)
    y = np.concatenate(r_list, axis=0)
    # Include bias column (intercept) at column 0.
    X_aug = np.column_stack([np.ones(len(X)), X])
    # Ridge: solve (X^T X + λI) w = X^T y; do not regularise intercept.
    n_features = X_aug.shape[1]
    L = np.eye(n_features) * l2
    L[0, 0] = 0.0  # no penalty on intercept
    XtX = X_aug.T @ X_aug
    Xty = X_aug.T @ y
    w = np.linalg.solve(XtX + L, Xty)
    # Predictions on training
    pred_resid = X_aug @ w
    train_rmse = float(np.sqrt(np.mean((y - pred_resid) ** 2)))
    naive_rmse = float(np.sqrt(np.mean(y ** 2)))
    return {
        "intercept": float(w[0]),
        "weights": {name: float(w[i + 1]) for i, name in enumerate(FEATURE_NAMES)},
        "train_rmse_residual": train_rmse,
        "naive_rmse_residual": naive_rmse,
        "n_samples": int(len(y)),
    }


def fit_bias_only(paths, v_filter=2.0):
    """Just additive bias per platform."""
    sums = 0.0
    n = 0
    for p in paths:
        df = load_segment(p)
        if df is None:
            continue
        v = df["v_mps"].to_numpy(dtype=float)
        mask = v > v_filter
        if not mask.any():
            continue
        truth = df[TRUTH_COL].to_numpy(dtype=float)
        pred = df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        resid = truth - pred
        sums += float(resid[mask].sum())
        n += int(mask.sum())
    return float(sums / n) if n > 0 else 0.0


def main():
    out = {"platforms": {}, "feature_names": FEATURE_NAMES, "v_center": 15.0, "l2": 10.0}
    # CV-style: also compute dev RMSE for each variant
    summary = []
    for platform in PLATFORMS_WITH_TRUTH:
        paths = list_segments(platform)
        train, dev, _ = split_train_dev(paths)
        # Fit on train.
        bias = fit_bias_only(train)
        ridge = fit_platform(train, l2=10.0)
        out["platforms"][platform] = {
            "bias_only": bias,
            "ridge": ridge,
        }
        # Evaluate on dev: baseline, +bias, +ridge
        # Reuse build_features
        ss_v0 = ss_bias = ss_ridge = 0.0
        n_v0 = n_bias = n_ridge = 0
        for p in dev:
            df = load_segment(p)
            if df is None:
                continue
            v = df["v_mps"].to_numpy(dtype=float)
            mask = v > 2.0
            if not mask.any():
                continue
            truth = df[TRUTH_COL].to_numpy(dtype=float)
            pred = df["yaw_rate_pred_rads"].to_numpy(dtype=float)
            feats = build_features(df)
            # v0
            r0 = (truth - pred)[mask]
            ss_v0 += float((r0 ** 2).sum()); n_v0 += int(mask.sum())
            # bias
            r1 = (truth - (pred + bias))[mask]
            ss_bias += float((r1 ** 2).sum()); n_bias += int(mask.sum())
            # ridge
            if ridge is not None:
                w0 = ridge["intercept"]
                ws = np.array([ridge["weights"][n] for n in FEATURE_NAMES])
                rcorr = w0 + feats @ ws
                r2 = (truth - (pred + rcorr))[mask]
                ss_ridge += float((r2 ** 2).sum()); n_ridge += int(mask.sum())
        rmse_v0 = math.sqrt(ss_v0 / n_v0) if n_v0 else float("nan")
        rmse_bias = math.sqrt(ss_bias / n_bias) if n_bias else float("nan")
        rmse_ridge = math.sqrt(ss_ridge / n_ridge) if n_ridge else float("nan")
        summary.append((platform, rmse_v0, rmse_bias, rmse_ridge, bias))
        print(f"{platform}: dev yaw_rmse V0={rmse_v0:.5f}  +bias={rmse_bias:.5f}  +ridge={rmse_ridge:.5f}  (bias={bias:+.5f})")

    out_path = ROOT / "final-model" / "coefficients.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
