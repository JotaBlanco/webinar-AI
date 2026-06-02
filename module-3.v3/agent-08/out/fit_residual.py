"""Fit a per-platform linear residual on top of V1's yaw prediction.

Features (allowlist-derived, no truth peeks):
    1, delta_road_rad, v_mps, v_mps*delta_road_rad, ddelta_road_dt,
    v_mps*ddelta_road_dt, yaw_rate_pred_rads, |yaw_rate_pred_rads|, a_long_mps2

Target: truth - V1_pred  (= the residual we want to learn).
Sample filter: v_mps > 2 (matches scorer).

Solve with ridge regression (alpha=1e-6) for stability.
Writes coeffs.json keyed by platform.
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v3/agent-08")
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1

ALLOWLIST = ["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
             "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]

FEATURE_NAMES = [
    "bias",
    "delta_road",
    "v",
    "v_delta",
    "ddelta",
    "v_ddelta",
    "v0_yaw",
    "abs_v0_yaw",
    "a_long",
    "v_sq_delta",
]

def make_features(df: pd.DataFrame) -> np.ndarray:
    t = df["t_s"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    a_long = df["a_long_mps2"].to_numpy() if "a_long_mps2" in df.columns else np.zeros_like(t)
    v0_yaw = df["yaw_rate_pred_rads"].to_numpy()
    if len(t) > 1:
        ddelta = np.gradient(delta, t)
    else:
        ddelta = np.zeros_like(delta)
    X = np.column_stack([
        np.ones_like(t),
        delta,
        v,
        v * delta,
        ddelta,
        v * ddelta,
        v0_yaw,
        np.abs(v0_yaw),
        a_long,
        v * v * delta,
    ])
    return X

def fit_platform(platform: str, paths: list[Path], alpha: float = 1e-6):
    XTX = np.zeros((len(FEATURE_NAMES), len(FEATURE_NAMES)))
    XTy = np.zeros(len(FEATURE_NAMES))
    n_total = 0
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        truth = df["yaw_rate_meas_rads"].to_numpy()
        sim_df = pd.DataFrame(index=df.index)
        for c in ALLOWLIST:
            sim_df[c] = df[c].to_numpy() if c in df.columns else 0.0
        v1pred = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy()
        target = truth - v1pred
        X = make_features(sim_df)
        v = sim_df["v_mps"].to_numpy()
        mask = v > 2.0
        if mask.sum() < 10:
            continue
        Xm = X[mask]
        ym = target[mask]
        XTX += Xm.T @ Xm
        XTy += Xm.T @ ym
        n_total += int(mask.sum())
    # Ridge
    A = XTX + alpha * np.eye(len(FEATURE_NAMES)) * max(np.diag(XTX).max(), 1.0)
    beta = np.linalg.solve(A, XTy)
    return beta.tolist(), n_total

if __name__ == "__main__":
    SIM = ROOT / "data" / "sim" / "segments"
    coeffs = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1","FORD_MUSTANG_MACH_E_MK1","HYUNDAI_IONIQ_5"]:
        paths = sorted(SIM.glob(f"{plat}/**/sim.csv"))
        beta, n = fit_platform(plat, paths)
        coeffs[plat] = {"features": FEATURE_NAMES, "beta": beta, "n_samples": n}
        print(plat, "n=", n)
        for name, b in zip(FEATURE_NAMES, beta):
            print(f"    {name:14s} {b:+.6e}")
    out = ROOT / "models" / "v1-plus-residual" / "coeffs.json"
    out.write_text(json.dumps(coeffs, indent=2))
    print("Wrote", out)
