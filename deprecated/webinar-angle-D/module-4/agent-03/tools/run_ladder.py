#!/usr/bin/env python3
"""Run the lateral-fidelity-triage variant ladder on Mach-E segments,
composing regime-segmentation for per-regime breakdown."""
from __future__ import annotations

import sys
import random
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-03")
sys.path.insert(0, str(ROOT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(ROOT / "skills" / "regime-segmentation"))
sys.path.insert(0, str(ROOT / "code"))

import triage
import segment
from parameters import PARAM_BY_PLATFORM

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
P = PARAM_BY_PLATFORM[PLATFORM]


def pick_segments(n: int = 8) -> list[Path]:
    base = ROOT / "data" / "sim" / "segments" / PLATFORM
    paths = sorted(base.rglob("sim.csv"))
    rng = random.Random(42)
    rng.shuffle(paths)
    # Filter to ones that load cleanly and have enough rows
    chosen = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            if len(df) < 500:
                continue
            if df["yaw_rate_meas_rads"].notna().sum() < 200:
                continue
            chosen.append(p)
            if len(chosen) == n:
                break
        except Exception:
            continue
    return chosen


def per_regime_rmse(df: pd.DataFrame, resid_col: str) -> dict:
    return segment.per_regime_rmse(df, resid_col)


def main():
    paths = pick_segments(8)
    print(f"Using {len(paths)} Mach-E segments")
    for p in paths:
        print(" ", p.relative_to(ROOT / "data"))

    # Load via segment skill (load_and_validate handles t_s checks)
    # but it requires monotone t_s; fall back to triage.load_many if any fail
    frames = []
    valid_paths = []
    for p in paths:
        try:
            df = segment.load_and_validate([p])
            frames.append(df)
            valid_paths.append(p)
        except Exception as e:
            print(f"  skip {p.name}: {e}")
    df = pd.concat(frames, ignore_index=True)
    df = segment.tag(df)
    print(f"\nTotal rows: {len(df)}; regime counts:")
    print(df["regime"].value_counts().to_dict())

    L, l_f, l_r = P.L, P.l_f, P.l_r
    m, I_z = P.m, P.I_z
    Caf_p, Car_p = P.C_alpha_f, P.C_alpha_r

    # ----- V0: baseline residual as-is -----
    v0_rmse = per_regime_rmse(df, "yaw_rate_resid_rads")
    print("\nV0:", v0_rmse)

    # ----- V1: KS recalibrated (canonical L, gyro-bias subtracted) -----
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    meas = df["yaw_rate_meas_rads"].to_numpy()

    psi_ks = triage.ks_yaw_rate(v, delta, L)
    # per-segment gyro bias on straight-line samples
    bias = np.zeros(len(df))
    for src, sub in df.groupby("__source__"):
        idx = sub.index
        straight = np.abs(delta[idx]) < 0.01
        if straight.sum() > 5:
            b = float(np.nanmean((psi_ks[idx][straight] - meas[idx][straight])))
        else:
            b = 0.0
        bias[idx] = b
    psi_v1 = psi_ks - bias
    df["yaw_rate_pred_v1"] = psi_v1
    df["resid_v1"] = psi_v1 - meas
    v1_rmse = per_regime_rmse(df, "resid_v1")
    print("V1:", v1_rmse)

    # ----- V2: Linear ST with prior C_alpha -----
    psi_v2 = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, Caf_p, Car_p)
    df["resid_v2"] = psi_v2 - meas
    df["yaw_rate_pred_v2"] = psi_v2
    v2_rmse = per_regime_rmse(df, "resid_v2")
    print("V2:", v2_rmse)

    # ----- V3: Linear ST with fit C_alpha -----
    cf, cr, pegged = triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)
    print(f"V3 fit C_alpha: cf={cf:.0f}, cr={cr:.0f}, pegged={pegged}")
    psi_v3 = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf, cr)
    df["resid_v3"] = psi_v3 - meas
    df["yaw_rate_pred_v3"] = psi_v3
    v3_rmse = per_regime_rmse(df, "resid_v3")
    print("V3:", v3_rmse)

    # ----- V4: residual learner LOO on V3's residuals -----
    df_for_learner = df.copy()
    df_for_learner["yaw_rate_resid_rads"] = df["resid_v3"]
    oof, info = triage.residual_learner_loo(df_for_learner)
    psi_v4 = psi_v3 - oof  # correction
    df["resid_v4"] = psi_v4 - meas
    df["yaw_rate_pred_v4"] = psi_v4
    v4_rmse = per_regime_rmse(df, "resid_v4")
    print("V4:", v4_rmse, "oof_info:", info)

    # ----- assemble report -----
    rows = [
        ("V0  baseline (as-shipped)", v0_rmse),
        ("V1  KS recalibrated + gyro bias", v1_rmse),
        ("V2  Linear ST, prior C_alpha", v2_rmse),
        (f"V3  Linear ST, fit C_alpha (cf={cf:.0f}, cr={cr:.0f})", v3_rmse),
        ("V4  V3 + Ridge residual learner (LOO)", v4_rmse),
    ]

    def fmt(x):
        return f"{x*1000:.2f}" if np.isfinite(x) else "n/a"

    lines = []
    lines.append("| Variant | Overall (mrad/s) | Straight | Steady | Transient | ΔOverall vs V0 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    base_overall = v0_rmse["overall"]
    for name, r in rows:
        drop_pct = (base_overall - r["overall"]) / base_overall * 100 if base_overall else 0.0
        lines.append(
            f"| {name} | {fmt(r['overall'])} | {fmt(r['straight'])} | {fmt(r['steady'])} | {fmt(r['transient'])} | {drop_pct:+.1f}% |"
        )

    # marginal drops
    overalls = [v0_rmse["overall"], v1_rmse["overall"], v2_rmse["overall"], v3_rmse["overall"], v4_rmse["overall"]]
    marginals = [overalls[i] - overalls[i + 1] for i in range(4)]
    total_drop = overalls[0] - overalls[-1]

    print("\nMarginal drops (rad/s):", marginals)
    print(f"Total drop V0->V4 = {total_drop:.5f}; sum marginals = {sum(marginals):.5f}")

    # Write sensor input CSV for the best variant
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    best_idx = int(np.argmin(overalls))
    best_name = ["V0", "V1", "V2", "V3", "V4"][best_idx]
    best_col = {0: "yaw_rate_pred_rads", 1: "yaw_rate_pred_v1", 2: "yaw_rate_pred_v2",
                3: "yaw_rate_pred_v3", 4: "yaw_rate_pred_v4"}[best_idx]
    sensor_df = pd.DataFrame({
        "yaw_rate_pred_rads": df[best_col],
        "yaw_rate_meas_rads": df["yaw_rate_meas_rads"],
        "delta_road_rad": df["delta_road_rad"],
        "yaw_rate_resid_rads": df["yaw_rate_resid_rads"],
    })
    sensor_csv = out_dir / f"best_{best_name}.csv"
    sensor_df.to_csv(sensor_csv, index=False)
    print(f"\nBest variant: {best_name}; wrote {sensor_csv}")

    # also save per-variant CSVs lightly
    for vname, pcol in [("v1", "yaw_rate_pred_v1"), ("v2", "yaw_rate_pred_v2"),
                        ("v3", "yaw_rate_pred_v3"), ("v4", "yaw_rate_pred_v4")]:
        d = pd.DataFrame({
            "yaw_rate_pred_rads": df[pcol],
            "yaw_rate_meas_rads": df["yaw_rate_meas_rads"],
            "delta_road_rad": df["delta_road_rad"],
            "yaw_rate_resid_rads": df["yaw_rate_resid_rads"],
        })
        d.to_csv(out_dir / f"variant_{vname}.csv", index=False)

    # dump table + meta to stdout for capture
    import json
    print("\nTABLE_START")
    for line in lines:
        print(line)
    print("TABLE_END")
    print("META", json.dumps({
        "platform": PLATFORM,
        "n_segments": len(valid_paths),
        "n_rows": int(len(df)),
        "regime_counts": {k: int(v) for k, v in df["regime"].value_counts().to_dict().items()},
        "v0": v0_rmse, "v1": v1_rmse, "v2": v2_rmse, "v3": v3_rmse, "v4": v4_rmse,
        "cf": cf, "cr": cr, "pegged": pegged,
        "marginals": marginals,
        "total_drop": total_drop,
        "best": best_name,
        "best_csv": str(sensor_csv),
        "v0_rmse": v0_rmse["overall"],
    }))


if __name__ == "__main__":
    main()
