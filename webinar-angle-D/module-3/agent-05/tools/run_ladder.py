#!/usr/bin/env python3
"""Run the lateral-fidelity-triage variant ladder."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
AGENT = HERE.parent
sys.path.insert(0, str(AGENT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(AGENT / "code"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
P = PARAM_BY_PLATFORM[PLATFORM]


def gather_segments(n: int = 20) -> list[Path]:
    root = AGENT / "data" / "sim" / "segments" / PLATFORM
    paths = sorted(root.rglob("sim.csv"))
    return paths[:n]


def per_regime(df: pd.DataFrame, resid_col: str, regimes: pd.Series) -> dict:
    out = {"overall": triage.rmse(df[resid_col])}
    for r in ("straight", "steady", "transient"):
        sub = df.loc[regimes == r, resid_col]
        out[r] = triage.rmse(sub) if len(sub) else float("nan")
    return out


def main() -> int:
    segs = gather_segments(20)
    print(f"Loaded {len(segs)} Mach-E sim.csv segments", file=sys.stderr)
    df = triage.load_many(segs)
    regimes = triage.regime_mask(df)
    print(f"rows total: {len(df)}; straight: {(regimes=='straight').sum()}, "
          f"steady: {(regimes=='steady').sum()}, transient: {(regimes=='transient').sum()}",
          file=sys.stderr)

    L = P.L
    l_f = P.l_f
    l_r = P.l_r
    m = P.m
    I_z = P.I_z
    Cf0 = P.C_alpha_f
    Cr0 = P.C_alpha_r

    results = {}

    # V0: as-is residual
    results["V0"] = per_regime(df, "yaw_rate_resid_rads", regimes)

    # V1: KS recalibrated with canonical L + per-segment yaw-gyro bias on straights
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    meas = df["yaw_rate_meas_rads"].to_numpy()
    psi_ks = triage.ks_yaw_rate(v, delta, L)

    # Per-segment bias on straights
    bias = np.zeros(len(df))
    for seg in df["__source__"].unique():
        idx = (df["__source__"] == seg).to_numpy()
        straight_idx = idx & (np.abs(delta) < triage.REGIME_DELTA_THR)
        if straight_idx.sum() >= 5:
            b = float(np.mean((psi_ks[straight_idx] - meas[straight_idx])))
        else:
            b = 0.0
        bias[idx] = b
    psi_v1 = psi_ks - bias
    df["v1_resid"] = psi_v1 - meas
    results["V1"] = per_regime(df, "v1_resid", regimes)

    # V2: linear ST with prior C_alpha
    psi_v2 = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, Cf0, Cr0)
    # Apply same per-segment bias correction technique:
    bias2 = np.zeros(len(df))
    for seg in df["__source__"].unique():
        idx = (df["__source__"] == seg).to_numpy()
        straight_idx = idx & (np.abs(delta) < triage.REGIME_DELTA_THR)
        if straight_idx.sum() >= 5:
            b = float(np.mean((psi_v2[straight_idx] - meas[straight_idx])))
        else:
            b = 0.0
        bias2[idx] = b
    psi_v2c = psi_v2 - bias2
    df["v2_resid"] = psi_v2c - meas
    results["V2"] = per_regime(df, "v2_resid", regimes)

    # V3: fit C_alpha
    cf, cr, pegged = triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)
    print(f"V3 fit: C_alpha_f={cf:.1f}, C_alpha_r={cr:.1f}, pegged={pegged}", file=sys.stderr)
    psi_v3 = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf, cr)
    bias3 = np.zeros(len(df))
    for seg in df["__source__"].unique():
        idx = (df["__source__"] == seg).to_numpy()
        straight_idx = idx & (np.abs(delta) < triage.REGIME_DELTA_THR)
        if straight_idx.sum() >= 5:
            b = float(np.mean((psi_v3[straight_idx] - meas[straight_idx])))
        else:
            b = 0.0
        bias3[idx] = b
    psi_v3c = psi_v3 - bias3
    df["v3_resid"] = psi_v3c - meas
    results["V3"] = per_regime(df, "v3_resid", regimes)

    # V4: residual learner (LOO) on V3 residuals
    # Build a frame with the residual column set to V3 resid
    df_v4 = df.copy()
    df_v4["yaw_rate_resid_rads"] = df_v4["v3_resid"]
    try:
        oof, info = triage.residual_learner_loo(df_v4, residual_col="yaw_rate_resid_rads")
        psi_v4 = psi_v3c - oof  # subtract learned residual estimate from V3 pred
        df["v4_resid"] = psi_v4 - meas
        results["V4"] = per_regime(df, "v4_resid", regimes)
        v4_oof_rmse = info["oof_rmse"]
        print(f"V4 LOO residual RMSE = {v4_oof_rmse:.6f}", file=sys.stderr)
    except Exception as e:
        print(f"V4 failed: {e}", file=sys.stderr)
        results["V4"] = None

    # Pick best variant by overall RMSE
    overall = {k: v["overall"] for k, v in results.items() if v is not None}
    best = min(overall, key=overall.get)
    print(f"Best variant: {best} ({overall[best]:.6f})", file=sys.stderr)

    # Write best variant CSV for sensor
    pred_map = {
        "V0": df["yaw_rate_pred_rads"].to_numpy(),
        "V1": psi_v1,
        "V2": psi_v2c,
        "V3": psi_v3c,
    }
    if "V4" in overall:
        pred_map["V4"] = psi_v4

    out_dir = AGENT / "out"
    out_dir.mkdir(exist_ok=True)
    best_csv = out_dir / f"best_{best}.csv"
    pd.DataFrame({
        "yaw_rate_pred_rads": pred_map[best],
        "yaw_rate_meas_rads": meas,
        "delta_road_rad": delta,
        "yaw_rate_resid_rads": df["yaw_rate_resid_rads"].to_numpy(),  # V0 truth for baseline
    }).to_csv(best_csv, index=False)
    print(f"Wrote {best_csv}", file=sys.stderr)

    # Print results
    import json
    print("\n=== RESULTS (RMSE rad/s) ===")
    print(json.dumps(results, indent=2))
    print(f"\nBest variant: {best}")
    print(f"V3 fit: C_alpha_f={cf:.1f} N/rad, C_alpha_r={cr:.1f} N/rad, pegged_upper={pegged}")
    print(f"\nBest CSV: {best_csv}")

    # Marginal accounting
    order = [k for k in ("V0", "V1", "V2", "V3", "V4") if results.get(k) is not None]
    marginals = []
    for i in range(1, len(order)):
        a = results[order[i-1]]["overall"]
        b = results[order[i]]["overall"]
        marginals.append((order[i], a - b))
    total = results[order[0]]["overall"] - results[order[-1]]["overall"]
    print("\nMarginal drops:")
    for name, d in marginals:
        print(f"  {name}: {d:+.6f}")
    print(f"Sum marginals: {sum(d for _,d in marginals):+.6f}")
    print(f"V0 - V_last:   {total:+.6f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
