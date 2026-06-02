"""Fit a per-platform feed-forward gain on d(delta_road)/dt to attack the
transient yaw residual on top of V1.

Hypothesis: V1's first-order lag underestimates yaw during fast steering
inputs. Adding k_ff * d(delta_road)/dt to V1's yaw prediction should reduce
transient RMSE.

Fits k_ff by closed-form least squares per platform on the v>2, transient
mask using sim/segments truth.
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
    root = ROOT / "data" / "sim" / "segments" / platform
    return sorted(root.glob("**/sim.csv"))


def fit_platform(platform):
    segs = get_segs(platform)
    A_sum = 0.0  # sum of f^2
    b_sum = 0.0  # sum of f * resid
    n = 0
    for p in segs:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        # build agent-facing input
        cols = ["t_s", "delta_road_rad", "v_mps", "yaw_rate_pred_rads", "delta_wheel_deg",
                "a_long_mps2", "accel_pedal_pct", "brake_pressed"]
        sub = df[[c for c in cols if c in df.columns]].copy()
        if "yaw_rate_pred_rads" not in sub.columns:
            continue
        yr_v1 = predict_v1(sub, platform)["yaw_rate_pred_rads"].to_numpy()
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        t = sub["t_s"].to_numpy()
        delta = sub["delta_road_rad"].to_numpy()
        v = sub["v_mps"].to_numpy()
        if len(t) < 3:
            continue
        # central-diff derivative
        ddelta = np.gradient(delta, t)
        resid = yr_truth - yr_v1   # what to add
        # Only fit on transient + moving
        mask = (v > 2.0) & (np.abs(ddelta) > 0.05) & (np.abs(delta) > 0.005)
        if mask.sum() < 20:
            continue
        f = ddelta[mask]
        r = resid[mask]
        A_sum += float(np.sum(f * f))
        b_sum += float(np.sum(f * r))
        n += int(mask.sum())
    if A_sum == 0:
        return 0.0, n
    return b_sum / A_sum, n


if __name__ == "__main__":
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        k, n = fit_platform(plat)
        out[plat] = {"k_ff": k, "n_samples": n}
        print(f"{plat}: k_ff={k:.6f}  n={n}")
    p = ROOT / "models" / "v1_plus_ddelta" / "coeffs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2))
    print(f"wrote {p}")
