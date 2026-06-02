"""Fit a per-platform gain correction g_scale on top of V1's prediction.

Hypothesis: V1's pooled yaw residual has a small signed bias on Mach-E and
IONIQ-5 that translates into 20+ m CTE drift. A single scalar multiplier
applied to V1's yaw output, fit per platform by least squares against truth,
could remove that bias.

This is a 1-parameter per-platform tweak, so risk of overfit is low.
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
    """Solve y_truth ≈ s * y_v1 for s. Closed form: s = sum(y_v1 * y_truth) / sum(y_v1^2)."""
    num = 0.0
    den = 0.0
    n_used = 0
    for p in get_segs(platform):
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        sub = df[[c for c in df.columns if c in
                  {"t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
                   "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"}]].copy()
        if "yaw_rate_pred_rads" not in sub.columns:
            continue
        try:
            yr_v1 = predict_v1(sub, platform)["yaw_rate_pred_rads"].to_numpy()
        except Exception:
            continue
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        v = sub["v_mps"].to_numpy()
        mask = v > 2.0
        if mask.sum() < 50:
            continue
        a = yr_v1[mask]
        b = yr_truth[mask]
        num += float(np.sum(a * b))
        den += float(np.sum(a * a))
        n_used += int(mask.sum())
    if den == 0:
        return 1.0, n_used
    return num / den, n_used


if __name__ == "__main__":
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        s, n = fit_platform(plat)
        out[plat] = {"g_scale": s, "n_samples": n}
        print(f"{plat}: g_scale={s:.6f}  n={n}")
    p = ROOT / "models" / "v1_gain" / "coeffs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2))
    print(f"wrote {p}")
