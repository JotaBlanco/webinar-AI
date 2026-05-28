#!/usr/bin/env python3
"""Run V0→V4 variant ladder for lateral-fidelity-challenge.

Variants:
  V0: baseline yaw_rate_resid_rads as-is.
  V1: per-platform constant yaw-rate bias subtracted from pred.
  V2: per-segment yaw-rate bias subtracted from pred.
  V3: per-platform steering gain k on delta_road, then pred = v * (k*delta) / L.
  V4: per-platform affine on delta + bias on pred.

Fit on TRAIN (samples not in every-5th interleave), report held-out TEST RMSE.
Outputs:
  out/variants_<PLATFORM>.csv   — RMSE table per regime per variant.
  out/v4_sample_<PLATFORM>.csv  — first segment with V4 columns + recomputed
                                  residuals (for schema_check).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REGIME_DELTA_THR = 0.01
REGIME_DDELTA_THR = 0.05

PARAM_L = {
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}


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


def rmse(arr):
    s = np.asarray(arr, dtype=float)
    s = s[np.isfinite(s)]
    return float(np.sqrt(np.mean(s ** 2))) if s.size else float("nan")


def load_platform(platform: str) -> pd.DataFrame:
    root = Path("data/sim/segments") / platform
    csvs = sorted(root.rglob("sim.csv"))
    frames = []
    for p in csvs:
        df = pd.read_csv(p, usecols=[
            "t_s", "delta_road_rad", "v_mps",
            "yaw_rate_meas_rads", "yaw_rate_pred_rads", "yaw_rate_resid_rads",
        ])
        df["__seg__"] = str(p.parent)
        frames.append(df)
    big = pd.concat(frames, ignore_index=True)
    big["__idx__"] = np.arange(len(big))
    return big


def split_train_test(df: pd.DataFrame):
    # interleaved every-5th sample (rule 7)
    is_test = (df["__idx__"] % 5 == 0)
    return df.loc[~is_test].copy(), df.loc[is_test].copy()


def per_regime_rmse(resid: np.ndarray, reg: pd.Series) -> dict:
    out = {"overall": rmse(resid)}
    for r in ("straight", "steady", "transient"):
        m = (reg == r).to_numpy()
        out[r] = rmse(resid[m])
    return out


def main():
    platform = sys.argv[1] if len(sys.argv) > 1 else "FORD_MUSTANG_MACH_E_MK1"
    L = PARAM_L[platform]
    print(f"Platform: {platform}  L={L}")
    big = load_platform(platform)
    big["regime"] = regime_mask(big)
    train, test = split_train_test(big)
    print(f"Samples train={len(train)} test={len(test)}")

    rows = []

    # --- V0: baseline ---
    test_resid = test["yaw_rate_resid_rads"].to_numpy()
    rows.append(("V0_baseline", per_regime_rmse(test_resid, test["regime"])))

    # --- V1: per-platform constant bias ---
    b_v1 = float(np.median(train["yaw_rate_resid_rads"]))
    print(f"V1 per-platform bias b = {b_v1:.6e} rad/s")
    test_resid_v1 = test["yaw_rate_resid_rads"].to_numpy() - b_v1
    rows.append(("V1_platform_bias", per_regime_rmse(test_resid_v1, test["regime"])))

    # --- V2: per-segment bias ---
    seg_bias = train.groupby("__seg__")["yaw_rate_resid_rads"].median()
    test_seg_bias = test["__seg__"].map(seg_bias).fillna(b_v1).to_numpy()
    test_resid_v2 = test["yaw_rate_resid_rads"].to_numpy() - test_seg_bias
    rows.append(("V2_segment_bias", per_regime_rmse(test_resid_v2, test["regime"])))

    # --- V3: per-platform steering gain k ---
    # KS speed-known lateral-only with clamped v and delta gives
    #   yaw_rate_pred ≈ v * delta / L. Refit k by least-squares of:
    #     yaw_rate_meas = k * (v * delta / L) + ε
    x_train = (train["v_mps"] * train["delta_road_rad"] / L).to_numpy()
    y_train = train["yaw_rate_meas_rads"].to_numpy()
    # restrict fit to cornering samples to avoid degenerate near-zero rows
    mcorner = np.abs(train["delta_road_rad"].to_numpy()) >= REGIME_DELTA_THR
    k_v3 = float(np.dot(x_train[mcorner], y_train[mcorner]) / np.dot(x_train[mcorner], x_train[mcorner]))
    print(f"V3 per-platform gain k = {k_v3:.4f}")
    pred_v3 = k_v3 * (test["v_mps"] * test["delta_road_rad"] / L).to_numpy()
    test_resid_v3 = pred_v3 - test["yaw_rate_meas_rads"].to_numpy()
    rows.append(("V3_steering_gain", per_regime_rmse(test_resid_v3, test["regime"])))

    # --- V4: per-platform affine on delta + bias ---
    # pred = (k*delta + d0) * v / L + b
    # Fit (k, d0, b) jointly: y = k * (v*delta/L) + d0 * (v/L) + b
    X = np.column_stack([
        (train["v_mps"] * train["delta_road_rad"] / L).to_numpy(),
        (train["v_mps"] / L).to_numpy(),
        np.ones(len(train)),
    ])
    y = train["yaw_rate_meas_rads"].to_numpy()
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    k_v4, d0_v4, b_v4 = float(coef[0]), float(coef[1]), float(coef[2])
    print(f"V4 affine: k={k_v4:.4f}  d0={d0_v4:.6e} rad  b={b_v4:.6e} rad/s")
    X_test = np.column_stack([
        (test["v_mps"] * test["delta_road_rad"] / L).to_numpy(),
        (test["v_mps"] / L).to_numpy(),
        np.ones(len(test)),
    ])
    pred_v4 = X_test @ coef
    test_resid_v4 = pred_v4 - test["yaw_rate_meas_rads"].to_numpy()
    rows.append(("V4_delta_affine_bias", per_regime_rmse(test_resid_v4, test["regime"])))

    # Print table
    out_df = pd.DataFrame([{"variant": name, **r} for name, r in rows])
    print()
    print(out_df.to_string(index=False))
    out_df.to_csv(f"out/variants_{platform}.csv", index=False)
    print(f"\nwrote out/variants_{platform}.csv")

    # --- Build a V4 sample CSV for schema_check: take one segment, recompute ---
    seg = sorted(big["__seg__"].unique())[0]
    one = big.loc[big["__seg__"] == seg].copy()
    one = one.reset_index(drop=True)
    # load original to keep all required columns
    orig = pd.read_csv(Path(seg) / "sim.csv")
    new_pred = (k_v4 * orig["delta_road_rad"] + d0_v4) * orig["v_mps"] / L + b_v4
    orig["yaw_rate_pred_rads"] = new_pred
    orig["yaw_rate_resid_rads"] = orig["yaw_rate_pred_rads"] - orig["yaw_rate_meas_rads"]
    # Re-derive a_y_pred and a_y_resid per rule 9
    orig["a_y_pred_mps2"] = orig["v_mps"] * orig["yaw_rate_pred_rads"]
    orig["a_y_resid_mps2"] = orig["a_y_pred_mps2"] - orig["a_lat_meas_mps2"]
    out_path = Path(f"out/v4_sample_{platform}.csv")
    orig.to_csv(out_path, index=False)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
