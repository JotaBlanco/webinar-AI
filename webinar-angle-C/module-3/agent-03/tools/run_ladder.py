#!/usr/bin/env python3
"""run_ladder.py — execute the locked V0→V3 variant ladder per the plan.

Reads all sim.csv for a Ford platform, does an interleaved test split
(test = idx % 5 == 0), fits per-platform corrections on TRAIN, scores RMSE on
TEST by regime, and dumps one variant CSV per ladder rung for one segment so
that evals/schema_check.py has something to bite on.

Residual sign convention: pred − meas (rule 1).
a_y_pred = v · ψ̇_pred (rule 9) — re-derived after every ψ̇ correction.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REGIME_DELTA_THR = 0.01
REGIME_DDELTA_THR = 0.05


def regime_mask(df: pd.DataFrame) -> np.ndarray:
    delta = df["delta_road_rad"].to_numpy()
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 0.02, dt)
    ddelta = np.gradient(delta) / dt
    out = np.full(len(df), "transient", dtype=object)
    out[np.abs(delta) < REGIME_DELTA_THR] = "straight"
    steady = (np.abs(delta) >= REGIME_DELTA_THR) & (np.abs(ddelta) < REGIME_DDELTA_THR)
    out[steady] = "steady"
    return out


def rmse(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x ** 2))) if x.size else float("nan")


def by_regime(resid, regime, mask):
    out = {"overall": rmse(resid[mask])}
    for r in ("straight", "steady", "transient"):
        m = mask & (regime == r)
        out[r] = rmse(resid[m])
    return out


def main():
    platform = sys.argv[1] if len(sys.argv) > 1 else "FORD_MUSTANG_MACH_E_MK1"
    data_root = Path("data/sim/segments") / platform
    csvs = sorted(data_root.rglob("sim.csv"))
    print(f"# platform={platform} segments={len(csvs)}")
    frames = []
    for p in csvs:
        df = pd.read_csv(p)
        df["__src__"] = str(p)
        frames.append(df)
    big = pd.concat(frames, ignore_index=True).reset_index(drop=True)
    print(f"# samples={len(big)}")

    # interleaved split (rule 7)
    idx = np.arange(len(big))
    test_mask = (idx % 5 == 0)
    train_mask = ~test_mask

    pred = big["yaw_rate_pred_rads"].to_numpy().astype(float)
    meas = big["yaw_rate_meas_rads"].to_numpy().astype(float)
    delta = big["delta_road_rad"].to_numpy().astype(float)
    v = big["v_mps"].to_numpy().astype(float)
    regime = regime_mask(big)

    # === V0 ===
    resid0 = pred - meas
    r0 = by_regime(resid0, regime, test_mask)
    print(f"V0 test RMSE  overall={r0['overall']:.5f} straight={r0['straight']:.5f} steady={r0['steady']:.5f} transient={r0['transient']:.5f}")

    # === V1: per-platform static bias on TRAIN straight samples ===
    straight_train = train_mask & (regime == "straight")
    bias = float(np.median(resid0[straight_train]))
    pred_v1 = pred - bias
    resid1 = pred_v1 - meas
    r1 = by_regime(resid1, regime, test_mask)
    print(f"V1 bias={bias:+.5f} rad/s | test  overall={r1['overall']:.5f} straight={r1['straight']:.5f} steady={r1['steady']:.5f} transient={r1['transient']:.5f}")

    # === V2: per-platform gain. Fit meas ~ a + b * pred_v1 on TRAIN cornering ===
    corn_train = train_mask & (np.abs(delta) >= REGIME_DELTA_THR)
    A = np.vstack([np.ones(corn_train.sum()), pred_v1[corn_train]]).T
    coef, *_ = np.linalg.lstsq(A, meas[corn_train], rcond=None)
    a_v2, b_v2 = float(coef[0]), float(coef[1])
    # we fit meas ≈ a + b·pred_v1; best estimator of meas given pred is therefore
    # pred_v2 = a + b·pred_v1 (NOT (pred_v1 − a)/b — that inverts the regression).
    pred_v2 = a_v2 + b_v2 * pred_v1
    resid2 = pred_v2 - meas
    r2 = by_regime(resid2, regime, test_mask)
    print(f"V2 a={a_v2:+.5f} b={b_v2:.4f} (b-1={b_v2-1:+.4f}) | test overall={r2['overall']:.5f} straight={r2['straight']:.5f} steady={r2['steady']:.5f} transient={r2['transient']:.5f}")

    # === V3: understeer-gradient correction. pred_v3 = pred_v2 / (1 + K * v^2 * pred_v2)
    # equivalently meas ≈ pred_v2 / (1 + K v^2 pred_v2)  → 1/meas - 1/pred_v2 ≈ K v^2 (sign-aware)
    # fit on TRAIN cornering, only where |pred_v2| and |meas| > 0.05 to avoid /0 noise.
    safe = corn_train & (np.abs(pred_v2) > 0.05) & (np.abs(meas) > 0.05)
    y = (1.0/meas[safe]) - (1.0/pred_v2[safe])
    x = v[safe]**2 * np.sign(pred_v2[safe])  # keep sign symmetry
    # actually 1/meas - 1/pred = K v^2 (no sign dep when both same sign), use plain v^2
    x = v[safe]**2
    K = float(np.sum(x*y) / np.sum(x*x)) if np.sum(x*x) > 0 else 0.0
    denom = 1.0 + K * v**2 * pred_v2
    denom = np.where(np.abs(denom) < 1e-3, np.sign(denom)*1e-3 + 1e-9, denom)
    pred_v3 = pred_v2 / denom
    resid3 = pred_v3 - meas
    r3 = by_regime(resid3, regime, test_mask)
    print(f"V3 K={K:+.6f} s^2/rad/m^2 | test overall={r3['overall']:.5f} straight={r3['straight']:.5f} steady={r3['steady']:.5f} transient={r3['transient']:.5f}")

    # === Contribution accounting (cumulative deltas on test overall) ===
    print()
    print("# Cumulative contribution to overall test RMSE (rad/s):")
    print(f"  V0 -> V1: {r0['overall']-r1['overall']:+.5f}")
    print(f"  V1 -> V2: {r1['overall']-r2['overall']:+.5f}")
    print(f"  V2 -> V3: {r2['overall']-r3['overall']:+.5f}")
    print(f"  V0 -> V3: {r0['overall']-r3['overall']:+.5f}  (total)")

    # ---- emit a variant CSV for schema_check on one source segment ----
    out_dir = Path("out") / platform
    out_dir.mkdir(parents=True, exist_ok=True)
    src0 = csvs[0]
    df0 = pd.read_csv(src0).reset_index(drop=True)
    # Apply V1+V2+V3 chain to that segment
    p_ = df0["yaw_rate_pred_rads"].to_numpy().astype(float)
    v_ = df0["v_mps"].to_numpy().astype(float)
    m_ = df0["yaw_rate_meas_rads"].to_numpy().astype(float)
    p1 = p_ - bias
    p2 = a_v2 + b_v2 * p1
    den = 1.0 + K * v_**2 * p2
    den = np.where(np.abs(den) < 1e-3, np.sign(den)*1e-3 + 1e-9, den)
    p3 = p2 / den
    df_out = df0.copy()
    df_out["yaw_rate_pred_rads"] = p3
    df_out["a_y_pred_mps2"] = v_ * p3  # rule 9
    df_out["yaw_rate_resid_rads"] = p3 - m_
    df_out["a_y_resid_mps2"] = df_out["a_y_pred_mps2"] - df0["a_lat_meas_mps2"]
    out_csv = out_dir / "sim_v3.csv"
    df_out.to_csv(out_csv, index=False)
    print(f"# wrote variant CSV: {out_csv}")

    # also write a summary table
    summary = pd.DataFrame({
        "variant": ["V0","V1","V2","V3"],
        "overall": [r0['overall'], r1['overall'], r2['overall'], r3['overall']],
        "straight":[r0['straight'],r1['straight'],r2['straight'],r3['straight']],
        "steady":  [r0['steady'],  r1['steady'],  r2['steady'],  r3['steady']],
        "transient":[r0['transient'],r1['transient'],r2['transient'],r3['transient']],
    })
    summary.to_csv(out_dir / "ladder_test_rmse.csv", index=False)
    with open(out_dir / "fit_params.txt", "w") as f:
        f.write(f"platform={platform}\nbias_rad_s={bias}\nV2_a={a_v2}\nV2_b={b_v2}\nV3_K={K}\n")
    print(f"# wrote {out_dir/'ladder_test_rmse.csv'}")
    print(f"# wrote {out_dir/'fit_params.txt'}")


if __name__ == "__main__":
    main()
