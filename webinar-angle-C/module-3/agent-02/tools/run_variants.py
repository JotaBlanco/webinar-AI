#!/usr/bin/env python3
"""run_variants.py — V0..V3 lateral-fidelity variant ladder.

Per-platform fits, interleaved every-5th-sample train/test split.
Recomputes coupled a_y prediction and residuals so schema_check.py passes.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REGIME_DELTA_THR = 0.01
REGIME_DDELTA_THR = 0.05
CORNERING_DELTA = 0.01


def regime_mask(df):
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


def rmse(arr):
    s = np.asarray(arr, dtype=float)
    s = s[np.isfinite(s)]
    return float(np.sqrt(np.mean(s ** 2))) if s.size else float("nan")


def load_platform(platform):
    data_root = Path("data/sim/segments") / platform
    csvs = sorted(data_root.rglob("sim.csv"))
    frames = []
    for p in csvs:
        d = pd.read_csv(p)
        d["__source__"] = str(p)
        frames.append(d)
    big = pd.concat(frames, ignore_index=True)
    big["__row__"] = np.arange(len(big))
    big["regime"] = regime_mask(big)
    return big, csvs


def summarize(label, df, pred_col, regimes):
    resid = df[pred_col] - df["yaw_rate_meas_rads"]
    out = {"variant": label, "overall": rmse(resid)}
    for r in ("straight", "steady", "transient"):
        m = regimes == r
        out[r] = rmse(resid[m])
    return out


def run(platform):
    big, csvs = load_platform(platform)
    print(f"Platform: {platform}  segments={len(csvs)}  samples={len(big)}")

    # interleaved split
    is_test = (big["__row__"] % 5 == 0)
    train = ~is_test

    pred0 = big["yaw_rate_pred_rads"].to_numpy()
    meas = big["yaw_rate_meas_rads"].to_numpy()
    delta = big["delta_road_rad"].to_numpy()

    # --- fit on train ---
    # V1 bias: median resid on train, straight
    straight_train = train & (big["regime"] == "straight")
    b = float(np.median(pred0[straight_train] - meas[straight_train]))

    # V2 gain g such that g * pred ≈ meas on cornering train
    cornering_train = train & (np.abs(delta) >= CORNERING_DELTA)
    p_c = pred0[cornering_train]
    m_c = meas[cornering_train]
    g = float(np.sum(p_c * m_c) / np.sum(p_c * p_c))

    # V3: gain then bias on straight: bias' = median((g*pred - meas)) on straight train
    pred_v2 = g * pred0
    b3 = float(np.median(pred_v2[straight_train] - meas[straight_train]))

    print(f"V1 bias  b  = {b:.6f} rad/s")
    print(f"V2 gain  g  = {g:.6f}")
    print(f"V3 bias' b3 = {b3:.6f} rad/s")

    big["yaw_rate_pred_v0"] = pred0
    big["yaw_rate_pred_v1"] = pred0 - b
    big["yaw_rate_pred_v2"] = pred_v2
    big["yaw_rate_pred_v3"] = pred_v2 - b3

    # --- score on test ---
    test_df = big.loc[is_test].reset_index(drop=True)
    test_reg = test_df["regime"]

    rows = []
    for v in ("v0", "v1", "v2", "v3"):
        rows.append(summarize(v.upper(), test_df, f"yaw_rate_pred_{v}", test_reg))
    table = pd.DataFrame(rows)
    print("\nTest-set RMSE (rad/s):")
    print(table.to_string(index=False, float_format=lambda x: f"{x:.5f}"))

    # write derived CSVs for schema_check on V3 (first segment, as smoke test)
    outdir = Path("out") / platform
    outdir.mkdir(parents=True, exist_ok=True)
    table.to_csv(outdir / "variant_rmse.csv", index=False)

    # Build a per-segment V3 sim.csv smoke sample (first segment) with coupled a_y
    # to satisfy schema_check.py.
    first_src = big["__source__"].iloc[0]
    seg = big[big["__source__"] == first_src].copy().reset_index(drop=True)
    psi_dot_v3 = g * seg["yaw_rate_pred_rads"].to_numpy() - b3
    seg["yaw_rate_pred_rads"] = psi_dot_v3
    seg["a_y_pred_mps2"] = seg["v_mps"].to_numpy() * psi_dot_v3
    seg["yaw_rate_resid_rads"] = seg["yaw_rate_pred_rads"] - seg["yaw_rate_meas_rads"]
    seg["a_y_resid_mps2"] = seg["a_y_pred_mps2"] - seg["a_lat_meas_mps2"]
    drop_cols = [c for c in ("__source__", "__row__", "regime",
                             "yaw_rate_pred_v0", "yaw_rate_pred_v1",
                             "yaw_rate_pred_v2", "yaw_rate_pred_v3") if c in seg.columns]
    seg = seg.drop(columns=drop_cols)
    seg_out = outdir / "v3_sample_sim.csv"
    seg.to_csv(seg_out, index=False)
    print(f"\nWrote V3 sample (coupled a_y, recomputed residuals): {seg_out}")
    return table


if __name__ == "__main__":
    platforms = sys.argv[1:] or ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]
    for plat in platforms:
        print("=" * 70)
        run(plat)
