"""Per-segment ablation, with focus on the dynamic segments where the lateral
model is actually exercised. Mach-E segments and F-150 segment 34 are
essentially highway straights (|δ_road| < 0.6°), so they reward yaw-rate bias
removal but reveal nothing about the KS-vs-ST gap. F-150 segment 9 reaches
|δ_road| > 25° and |ψ̇| > 27°/s; that's where ST should pay off.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

MODULE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str((MODULE_DIR / "code").resolve()))
from parameters import PARAM_BY_PLATFORM  # noqa: E402
from ablation import (
    predict_v0_ks, predict_v2_st_steady, yaw_bias_offset,
    rmse, corrcoef,
)

DATA_DIR = (MODULE_DIR / "data").resolve()


def per_segment(platform: str):
    p = PARAM_BY_PLATFORM[platform]
    csvs = sorted((DATA_DIR / "sim/segments" / platform).glob("**/sim.csv"))
    rows = []
    for c in csvs:
        df = pd.read_csv(c)
        psi_meas = df["yaw_rate_meas_rads"].to_numpy()
        ay_meas = df["a_lat_meas_mps2"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        v = df["v_mps"].to_numpy()

        psi_v0, ay_v0 = predict_v0_ks(df, p)
        psi_v2, ay_v2 = predict_v2_st_steady(df, p)
        b1 = yaw_bias_offset(psi_v0, psi_meas, delta)
        psi_v1 = psi_v0 + b1
        ay_v1 = ay_v0 + v * b1
        b3 = yaw_bias_offset(psi_v2, psi_meas, delta)
        psi_v3 = psi_v2 + b3
        ay_v3 = ay_v2 + v * b3

        seg_id = c.parts[-2]
        max_delta_deg = float(np.degrees(np.abs(delta).max()))
        max_psi_degs = float(np.degrees(np.abs(psi_meas).max()))
        max_ay = float(np.abs(ay_meas).max())

        rows.append({
            "platform": platform,
            "seg": seg_id,
            "N": len(df),
            "|δ|max_deg": max_delta_deg,
            "|ψ̇meas|max_degs": max_psi_degs,
            "|a_y|max": max_ay,
            "V0_rmse_ψ̇_degs": np.degrees(rmse(psi_meas - psi_v0)),
            "V1_rmse_ψ̇_degs": np.degrees(rmse(psi_meas - psi_v1)),
            "V2_rmse_ψ̇_degs": np.degrees(rmse(psi_meas - psi_v2)),
            "V3_rmse_ψ̇_degs": np.degrees(rmse(psi_meas - psi_v3)),
            "V0_rmse_a_y": rmse(ay_meas - ay_v0),
            "V2_rmse_a_y": rmse(ay_meas - ay_v2),
            "bias_v1_degs": float(np.degrees(b1)),
        })
    return pd.DataFrame(rows)


def main():
    for plat in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
        print(f"\n=== {plat} ===")
        df = per_segment(plat)
        print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print()


if __name__ == "__main__":
    main()
