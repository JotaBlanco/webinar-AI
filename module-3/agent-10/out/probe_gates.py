"""Probe: do different straight-row gates for per-segment delta0 give better Mach-E / IONIQ-5 results?

The current gate is `|yr_v0| < 0.03 and v > 5`. Try a few alternatives.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402

import json
COEFFS = json.loads((ROOT / "final-model" / "coeffs.json").read_text())


def make_predict(gate_kind):
    def delta0_yr(df, fb):
        v = df["v_mps"].to_numpy()
        yr = df["yaw_rate_pred_rads"].to_numpy()
        m = (np.abs(yr) < 0.03) & (v > 5)
        if m.sum() < 50: return fb
        return float(df.loc[m, "delta_road_rad"].median())
    def delta0_alat(df, fb):
        v = df["v_mps"].to_numpy()
        yr = df["yaw_rate_pred_rads"].to_numpy()
        m = (np.abs(v * yr) < 0.3) & (v > 5)
        if m.sum() < 50: return fb
        return float(df.loc[m, "delta_road_rad"].median())
    def delta0_steer(df, fb):
        v = df["v_mps"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        m = (np.abs(d) < 0.005) & (v > 8)
        if m.sum() < 50: return fb
        return float(df.loc[m, "delta_road_rad"].median())
    def delta0_wide_yr(df, fb):
        v = df["v_mps"].to_numpy()
        yr = df["yaw_rate_pred_rads"].to_numpy()
        m = (np.abs(yr) < 0.015) & (v > 8)
        if m.sum() < 30: return fb
        return float(df.loc[m, "delta_road_rad"].median())

    gates = {
        "yr": delta0_yr, "alat": delta0_alat, "steer": delta0_steer, "wide_yr": delta0_wide_yr,
    }
    gate = gates[gate_kind]

    def predict(sim_df, platform):
        if platform not in COEFFS:
            return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()}, index=sim_df.index)
        p = COEFFS[platform]
        if p.get("use_per_segment_delta0", False):
            d0 = gate(sim_df, p.get("delta0_fallback", 0.0))
        else:
            d0 = p["delta0"]
        delta = (sim_df["delta_road_rad"].to_numpy(dtype=float) - d0) * p["g"]
        v = sim_df["v_mps"].to_numpy(dtype=float)
        t = sim_df["t_s"].to_numpy(dtype=float)
        yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
        dt = np.diff(t, prepend=t[0])
        alpha = dt / (p["tau"] + dt)
        yr = np.empty_like(yr_ss)
        yr[0] = yr_ss[0]
        for i in range(1, len(yr)):
            yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    return predict


def main():
    sim_root = ROOT / "data" / "sim" / "segments"
    seg_paths = sorted(p for p in sim_root.glob("*/**/sim.csv") if p.is_file())
    for kind in ["yr", "alat", "steer", "wide_yr"]:
        res = score(make_predict(kind), segment_paths=seg_paths)
        print(f"\n=== gate={kind} === yaw={res['yaw_rate_rmse']:.5f} cte={res['cte_rmse']:.3f}")
        for plat, m in res["per_platform"].items():
            print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f} bias={m['yaw_residual_mean']:+.5f} cte={m['cte_rmse']:.3f}")


if __name__ == "__main__":
    main()
