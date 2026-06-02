"""Fit y_truth = s * y_v1 + b + k_ff * d(delta)/dt (gated) — 3-param per platform.

Closed-form LS via normal equations. Features:
  x1 = y_v1
  x2 = 1
  x3 = ddelta_gated  (d(delta_road)/dt * gate where gate = clip((|d|-0.005)/0.005, 0, 1))
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1  # type: ignore


def get_segs(platform):
    return sorted((ROOT / "data" / "sim" / "segments" / platform).glob("**/sim.csv"))


def features_for_seg(df, platform):
    sub = df[[c for c in df.columns if c in
              {"t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
               "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"}]].copy()
    if "yaw_rate_pred_rads" not in sub.columns:
        return None
    yr_v1 = predict_v1(sub, platform)["yaw_rate_pred_rads"].to_numpy()
    yr_truth = df["yaw_rate_meas_rads"].to_numpy()
    t = sub["t_s"].to_numpy()
    delta = sub["delta_road_rad"].to_numpy()
    v = sub["v_mps"].to_numpy()
    if len(t) < 3:
        return None
    ddelta = np.gradient(delta, t)
    gate = np.clip((np.abs(delta) - 0.005) / 0.005, 0.0, 1.0)
    feat = ddelta * gate
    mask = v > 2.0
    return yr_v1[mask], np.ones(mask.sum()), feat[mask], yr_truth[mask]


def fit_platform(platform):
    AtA = np.zeros((3, 3))
    Atb = np.zeros(3)
    n_total = 0
    for p in get_segs(platform):
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        try:
            r = features_for_seg(df, platform)
        except Exception:
            continue
        if r is None:
            continue
        x1, x2, x3, y = r
        X = np.column_stack([x1, x2, x3])
        AtA += X.T @ X
        Atb += X.T @ y
        n_total += len(y)
    try:
        beta = np.linalg.solve(AtA, Atb)
    except np.linalg.LinAlgError:
        return (1.0, 0.0, 0.0, n_total)
    return float(beta[0]), float(beta[1]), float(beta[2]), n_total


if __name__ == "__main__":
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        s, b, k, n = fit_platform(plat)
        out[plat] = {"s": s, "b": b, "k_ff": k, "n": n}
        print(f"{plat}: s={s:.5f} b={b:+.6f} k_ff={k:+.6f} n={n}")
    p = ROOT / "models" / "v1_combined" / "coeffs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2))
