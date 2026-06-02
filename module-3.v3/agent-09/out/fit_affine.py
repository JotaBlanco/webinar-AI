"""Fit per-platform y_truth = s * y_v1 + b (2-param affine)."""
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


def fit_platform(platform):
    SX = SY = SXX = SXY = 0.0
    n = 0
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
        x = yr_v1[mask]; y = yr_truth[mask]
        SX += float(x.sum()); SY += float(y.sum())
        SXX += float((x*x).sum()); SXY += float((x*y).sum())
        n += int(mask.sum())
    if n == 0: return 1.0, 0.0, 0
    denom = n*SXX - SX*SX
    s = (n*SXY - SX*SY) / denom
    b = (SY - s*SX) / n
    return s, b, n


if __name__ == "__main__":
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        s, b, n = fit_platform(plat)
        out[plat] = {"s": s, "b": b, "n": n}
        print(f"{plat}: s={s:.6f} b={b:+.6f}  n={n}")
    p = ROOT / "models" / "v1_affine" / "coeffs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2))
