#!/usr/bin/env python3
"""lateral_ladder.py — V0/V1/V2 lateral-fidelity ladder, per-platform.

Reads sim.csv files for a Ford platform, applies the locked ladder, writes
per-platform corrected CSVs to out/<PLATFORM>/sim_V<i>.csv (one per variant,
concatenated across segments with __source__), and prints per-regime RMSE on
the interleaved every-5th-sample TEST split.

Train / test split: TEST = rows where row index (per concatenated platform
frame) % 5 == 0. TRAIN = the rest. Fits use TRAIN only; scoring uses TEST.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REGIME_DELTA_THR = 0.01
REGIME_DDELTA_THR = 0.05


def regime_mask(df: pd.DataFrame) -> pd.Series:
    delta = df["delta_road_rad"].to_numpy()
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 0.02, dt)
    ddelta = np.gradient(delta) / dt
    out = np.full(len(df), "transient", dtype=object)
    out[np.abs(delta) < REGIME_DELTA_THR] = "straight"
    steady = (np.abs(delta) >= REGIME_DELTA_THR) & (np.abs(ddelta) < REGIME_DDELTA_THR)
    out[steady] = "steady"
    return pd.Series(out, index=df.index, name="regime")


def rmse(a) -> float:
    s = np.asarray(a, dtype=float)
    s = s[np.isfinite(s)]
    return float(np.sqrt(np.mean(s ** 2))) if s.size else float("nan")


def report_rmse(label: str, resid: np.ndarray, reg: np.ndarray):
    overall = rmse(resid)
    by = {r: rmse(resid[reg == r]) for r in ("straight", "steady", "transient")}
    print(f"  {label:<18s}  overall={overall:.5f}  "
          f"straight={by['straight']:.5f}  "
          f"steady={by['steady']:.5f}  "
          f"transient={by['transient']:.5f}")
    return overall, by


def process_platform(platform: str, out_root: Path):
    print(f"\n=== {platform} ===")
    data_root = Path("data/sim/segments") / platform
    csvs = sorted(data_root.rglob("sim.csv"))
    frames = []
    for p in csvs:
        df = pd.read_csv(p)
        df["__source__"] = str(p.relative_to(data_root))
        frames.append(df)
    big = pd.concat(frames, ignore_index=True)
    print(f"  segments={len(csvs)}  samples={len(big)}")

    reg_all = regime_mask(big).to_numpy()
    idx = np.arange(len(big))
    test = (idx % 5 == 0)
    train = ~test

    psi_meas = big["yaw_rate_meas_rads"].to_numpy()
    psi_pred_v0 = big["yaw_rate_pred_rads"].to_numpy()
    v = big["v_mps"].to_numpy()

    # ---- V0 (test split) ----
    resid_v0 = psi_pred_v0 - psi_meas
    print("Test-set RMSE (rad/s) per regime:")
    o0, _ = report_rmse("V0 baseline", resid_v0[test], reg_all[test])

    # ---- V1: bias removal, fit on TRAIN straights ----
    mask_train_straight = train & (reg_all == "straight")
    b = float(np.median(resid_v0[mask_train_straight]))
    print(f"  V1 fit: bias b = {b:+.6f} rad/s  (n_train_straight={mask_train_straight.sum()})")
    psi_pred_v1 = psi_pred_v0 - b
    resid_v1 = psi_pred_v1 - psi_meas
    o1, _ = report_rmse("V1 +bias", resid_v1[test], reg_all[test])

    # ---- V2: scalar yaw-rate gain, fit on TRAIN steady+transient ----
    mask_train_corner = train & (reg_all != "straight")
    pp = psi_pred_v1[mask_train_corner]
    pm = psi_meas[mask_train_corner]
    g = float(np.sum(pp * pm) / np.sum(pp * pp))
    print(f"  V2 fit: gain  g = {g:+.6f}     (n_train_corner={mask_train_corner.sum()})")
    psi_pred_v2 = g * psi_pred_v1
    resid_v2 = psi_pred_v2 - psi_meas
    o2, _ = report_rmse("V2 +bias+gain", resid_v2[test], reg_all[test])

    # Incremental attribution (overall, test set)
    print(f"  Attribution (Δoverall RMSE):")
    print(f"    V1 contribution: {o0 - o1:+.5f} rad/s  (V0→V1)")
    print(f"    V2 contribution: {o1 - o2:+.5f} rad/s  (V1→V2)")
    print(f"    Total          : {o0 - o2:+.5f} rad/s  (V0→V2, {(1 - o2/o0)*100:.1f}% rel)")

    # ---- V3: recompute a_y coupling (rule 9) ----
    ay_meas = big["a_lat_meas_mps2"].to_numpy()
    ay_pred_v0 = big["a_y_pred_mps2"].to_numpy()
    ay_pred_v2 = v * psi_pred_v2
    print(f"  a_y RMSE (test): V0={rmse(ay_pred_v0[test]-ay_meas[test]):.4f}  "
          f"V2-coupled={rmse(ay_pred_v2[test]-ay_meas[test]):.4f}")

    # ---- Write V2 CSV (per-platform concat) so schema_check can run ----
    out_dir = out_root / platform
    out_dir.mkdir(parents=True, exist_ok=True)
    out = big.copy()
    out["yaw_rate_pred_rads"] = psi_pred_v2
    out["yaw_rate_resid_rads"] = psi_pred_v2 - psi_meas
    out["a_y_pred_mps2"] = ay_pred_v2
    out["a_y_resid_mps2"] = ay_pred_v2 - ay_meas
    out_path = out_dir / "sim_V2.csv"
    out.to_csv(out_path, index=False)
    print(f"  wrote {out_path}")

    return {
        "platform": platform, "bias": b, "gain": g,
        "v0": o0, "v1": o1, "v2": o2,
        "v2_csv": str(out_path),
    }


def main():
    out_root = Path("out")
    results = []
    for plat in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
        results.append(process_platform(plat, out_root))

    print("\n=== summary ===")
    for r in results:
        print(f"{r['platform']}: b={r['bias']:+.5f} g={r['gain']:.5f}  "
              f"V0={r['v0']:.5f} -> V2={r['v2']:.5f}  "
              f"({(1 - r['v2']/r['v0'])*100:+.1f}%)")


if __name__ == "__main__":
    main()
