"""Fit per-platform residual learner head: ridge regression on V1 yaw residual.

Features (input-only, allowlist-safe):
  bias=1, v, v^2, delta, delta*v, delta^2, |delta|, ddelta_dt, ddelta_dt*v,
  a_long, brake_pressed, yr_v1, yr_v1*v, yr_v1**2

After fitting, write coeffs to out/residual_coeffs.json keyed by platform.
"""
from __future__ import annotations
import sys, json, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-09")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "out"))

from v1_baseline import predict_v1
from harness import list_segments, PLATFORMS_FIT, ALLOWED_COLS


FEATURE_NAMES = [
    "bias", "v", "v2",
    "delta", "delta_v", "delta_sq", "abs_delta",
    "ddelta", "ddelta_v", "ddelta_sq",
    "a_long", "brake",
    "yr_v1", "yr_v1_v", "yr_v1_sq", "yr_v1_abs",
    "yr_v1_delta", "yr_v1_v_sq",
    "delta_v2", "yr_v1_v2",
]


def build_features(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    t = sim_df["t_s"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    d = sim_df["delta_road_rad"].to_numpy()
    a = sim_df["a_long_mps2"].to_numpy()
    b = sim_df["brake_pressed"].fillna(0).to_numpy()
    a = np.nan_to_num(a, nan=0.0)
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 1e-3, dt)
    ddelta = np.diff(d, prepend=d[0]) / dt
    # Smooth ddelta via simple causal EMA (no future-leak) to reduce noise
    n = len(v)
    F = np.zeros((n, len(FEATURE_NAMES)))
    F[:, 0] = 1.0
    F[:, 1] = v
    F[:, 2] = v * v
    F[:, 3] = d
    F[:, 4] = d * v
    F[:, 5] = d * d
    F[:, 6] = np.abs(d)
    F[:, 7] = ddelta
    F[:, 8] = ddelta * v
    F[:, 9] = ddelta * ddelta
    F[:, 10] = a
    F[:, 11] = b
    F[:, 12] = yr_v1
    F[:, 13] = yr_v1 * v
    F[:, 14] = yr_v1 * yr_v1
    F[:, 15] = np.abs(yr_v1)
    F[:, 16] = yr_v1 * d
    F[:, 17] = yr_v1 * v * v
    F[:, 18] = d * v * v
    F[:, 19] = yr_v1 * v * v
    return F


def fit_platform(platform: str, lam: float = 1e-3, max_segs=None):
    pairs = list_segments(platform)
    if max_segs:
        pairs = pairs[:max_segs]
    Fs, ys = [], []
    n_used = 0
    for sp_only, sp_full in pairs:
        sim_df = pd.read_csv(sp_only)
        if not all(c in sim_df.columns for c in ALLOWED_COLS):
            continue
        sim_df = sim_df[ALLOWED_COLS].copy()
        full = pd.read_csv(sp_full)
        if "yaw_rate_meas_rads" not in full.columns:
            continue
        yr_truth = full["yaw_rate_meas_rads"].to_numpy()
        out = predict_v1(sim_df, platform)
        yr_v1 = out["yaw_rate_pred_rads"].to_numpy()
        if len(yr_truth) != len(yr_v1):
            continue
        resid = yr_truth - yr_v1
        F = build_features(sim_df, yr_v1)
        # Drop rows with NaN/inf
        good = np.isfinite(F).all(axis=1) & np.isfinite(resid)
        Fs.append(F[good]); ys.append(resid[good])
        n_used += 1
    F = np.vstack(Fs); y = np.concatenate(ys)
    good = np.isfinite(F).all(axis=1) & np.isfinite(y)
    F = F[good]; y = y[good]
    # Standardise for numerics
    mu = F.mean(axis=0); sigma = F.std(axis=0); sigma[sigma < 1e-12] = 1.0
    # Don't standardise the bias column
    mu[0] = 0.0; sigma[0] = 1.0
    Fz = (F - mu) / sigma
    # Ridge: (Fz^T Fz + lam*I)^-1 Fz^T y
    n_feat = Fz.shape[1]
    A = Fz.T @ Fz + lam * len(y) * np.eye(n_feat)
    rhs = Fz.T @ y
    w, *_ = np.linalg.lstsq(A, rhs, rcond=None)
    # Compute R^2
    pred = Fz @ w
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / max(ss_tot, 1e-12)
    return {
        "platform": platform,
        "n_segments_used": n_used,
        "n_samples": int(len(y)),
        "lam": lam,
        "mu": mu.tolist(),
        "sigma": sigma.tolist(),
        "w": w.tolist(),
        "feature_names": FEATURE_NAMES,
        "r2": r2,
        "resid_std_before": float(np.std(y)),
        "resid_std_after": float(np.std(y - pred)),
    }


PLATFORM_LAM = {
    "FORD_F_150_LIGHTNING_MK1": 1.0,
    "FORD_MUSTANG_MACH_E_MK1": 1.0,
    "HYUNDAI_IONIQ_5": 1e-2,
}

if __name__ == "__main__":
    out_dir = ROOT / "out"
    coeffs = {}
    for plat in PLATFORMS_FIT:
        c = fit_platform(plat, lam=PLATFORM_LAM[plat])
        print(f"{plat}: n_segs={c['n_segments_used']}, R2={c['r2']:.4f}, "
              f"resid_std {c['resid_std_before']:.5f} -> {c['resid_std_after']:.5f}")
        coeffs[plat] = c
    (out_dir / "residual_coeffs.json").write_text(json.dumps(coeffs, indent=2))
    print("written", out_dir / "residual_coeffs.json")
