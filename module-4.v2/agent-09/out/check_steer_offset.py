"""Check whether a steering-offset estimate (per-segment) improves yaw rmse.

Compute: best delta_offset that minimises yaw rmse on each segment.
If there's no truth at grading time, we can't subtract per-segment offset.
But we *can* look at the bulk distribution to see if there's a global one.
"""
from __future__ import annotations
import sys, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-09")
SIM_ROOT = ROOT / "data" / "sim" / "segments"

L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1":    2.984,
    "FORD_F_150_LIGHTNING_MK1":   3.70,
    "HYUNDAI_IONIQ_5":            3.00,
}
COEFFS = {
    "FORD_MUSTANG_MACH_E_MK1": {"K_us": 0.002635, "scale": 1.1831},
    "FORD_F_150_LIGHTNING_MK1": {"K_us": 0.003440, "scale": 0.9608},
    "HYUNDAI_IONIQ_5": {"K_us": 0.003522, "scale": 0.9719},
}


def load_segment(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "yaw_rate_meas_rads" not in df.columns and "psi_dot_rads" in df.columns:
        df["yaw_rate_meas_rads"] = df["psi_dot_rads"]
    return df


for plat in COEFFS:
    L = L_BY_PLATFORM[plat]; K_us = COEFFS[plat]["K_us"]; scale = COEFFS[plat]["scale"]
    offsets = []
    for p in sorted((SIM_ROOT / plat).rglob("sim.csv")):
        df = load_segment(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        v = df["v_mps"].to_numpy(); d = df["delta_road_rad"].to_numpy(); yr = df["yaw_rate_meas_rads"].to_numpy()
        m = np.isfinite(yr) & (v > 5.0)
        if m.sum() < 100: continue
        v_, d_, yr_ = v[m], d[m], yr[m]
        # The relationship: yr = v*(d+do)*scale/(L+K_us*v^2)
        # Solving for do that minimises sum (yr - v*(d+do)*s/(L+Kv2))^2 — linear in do.
        gain = v_ * scale / (L + K_us * v_ * v_)
        # yr ≈ gain * d + gain * do  -> residual = (yr - gain*d) - gain*do
        r = yr_ - gain * d_
        # do_hat = (r·gain) / (gain·gain)
        do = float(np.dot(r, gain) / np.dot(gain, gain))
        offsets.append(do)
    arr = np.array(offsets)
    print(f"{plat}: n={len(arr)} do mean={arr.mean()*1000:.3f} mrad std={arr.std()*1000:.3f} mrad median={np.median(arr)*1000:.3f}")
