"""Fit per-platform constant yaw offset to drive pooled cte_drift toward zero.

For each platform: scan a small range of delta_yr values around the V1
signed-yaw-bias guess and find the one that minimises pooled CTE RMSE.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))

from v1_baseline import predict_v1  # noqa: E402
from traj_metrics import cte_rmse_segment  # noqa: E402


def pooled_cte_for_offset(segs, plat, offset):
    sum_sq = 0.0
    n_bins = 0
    for p in segs:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns or len(df) < 50:
            continue
        t = df["t_s"].to_numpy()
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            continue
        v = df["v_mps"].to_numpy()
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        yr_pred = predict_v1(df, plat)["yaw_rate_pred_rads"].to_numpy() + offset
        ss, n, _ = cte_rmse_segment(t, v, yr_truth, yr_pred)
        sum_sq += ss
        n_bins += n
    return math.sqrt(sum_sq / n_bins) if n_bins > 0 else float("nan")


def main():
    seg_root = ROOT / "data" / "sim" / "segments"
    coeffs = {}
    for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        segs = sorted((seg_root / plat).glob("**/sim.csv"))
        # 1D search.
        best = (None, float("inf"))
        for offset in np.linspace(-0.005, 0.005, 41):
            r = pooled_cte_for_offset(segs, plat, offset)
            if r < best[1]:
                best = (float(offset), r)
        # refine
        center = best[0]
        for offset in np.linspace(center - 2.5e-4, center + 2.5e-4, 21):
            r = pooled_cte_for_offset(segs, plat, offset)
            if r < best[1]:
                best = (float(offset), r)
        coeffs[plat] = {"delta_yr": best[0]}
        print(f"{plat}: optimal offset = {best[0]:+.5f}, cte_rmse = {best[1]:.3f}")
    out = ROOT / "out" / "cte_debias_coeffs.json"
    out.write_text(json.dumps(coeffs, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
