"""Variant-ladder runner — composes regime-segmentation + lateral-fidelity-triage.

Reads Ford Mach-E sim.csv files, runs V0..V4, prints a per-regime RMSE table,
writes best-variant CSV and a small JSON summary under out/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(ROOT / "skills" / "regime-segmentation"))
sys.path.insert(0, str(ROOT / "code"))

import triage  # noqa: E402
import segment  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
P = PARAM_BY_PLATFORM[PLATFORM]

SIM_ROOT = ROOT / "data" / "sim" / "segments" / PLATFORM
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)


def gather_csvs(limit: int = 12) -> list[Path]:
    return sorted(SIM_ROOT.rglob("sim.csv"))[:limit]


def per_regime_rmse(values: np.ndarray, regime: np.ndarray) -> dict:
    out = {"overall": float(np.sqrt(np.nanmean(values ** 2)))}
    for r in ("straight", "steady", "transient"):
        mask = regime == r
        out[r] = float(np.sqrt(np.nanmean(values[mask] ** 2))) if mask.any() else float("nan")
    return out


def yaw_bias(df: pd.DataFrame, resid: np.ndarray) -> float:
    """Per-segment yaw-gyro bias = mean residual on straight-line samples."""
    delta = df["delta_road_rad"].to_numpy()
    biases = np.zeros(len(df))
    for src, sub in df.groupby("__source__"):
        idx = sub.index.to_numpy()
        straight = np.abs(delta[idx]) < 0.01
        if straight.any():
            b = float(np.nanmean(resid[idx][straight]))
        else:
            b = 0.0
        biases[idx] = b
    return biases


def main() -> int:
    csvs = gather_csvs(limit=12)
    print(f"[load] {len(csvs)} Mach-E segments")
    df = segment.load_and_validate(csvs)
    df = segment.tag(df)
    regime = df["regime"].to_numpy()

    meas = df["yaw_rate_meas_rads"].to_numpy()
    pred_v0 = df["yaw_rate_pred_rads"].to_numpy()
    resid_v0 = df["yaw_rate_resid_rads"].to_numpy()

    # V0 — baseline (as-is)
    v0 = per_regime_rmse(resid_v0, regime)

    # V1 — KS recalibrated (canonical L) minus per-segment yaw-gyro bias
    L = P.L
    ks_pred = triage.ks_yaw_rate(df["v_mps"].to_numpy(), df["delta_road_rad"].to_numpy(), L)
    resid_pre_bias = ks_pred - meas
    bias = yaw_bias(df, resid_pre_bias)
    pred_v1 = ks_pred - bias
    resid_v1 = pred_v1 - meas
    v1 = per_regime_rmse(resid_v1, regime)

    # V2 — Linear ST with prior C_alpha
    pred_v2 = triage.linear_st_yaw_rate(
        df["v_mps"].to_numpy(), df["delta_road_rad"].to_numpy(),
        L, P.l_f, P.l_r, P.m, P.I_z,
        P.C_alpha_f, P.C_alpha_r,
    )
    # Apply the same per-segment yaw-bias subtraction (consistent V1+ treatment).
    bias2 = yaw_bias(df, pred_v2 - meas)
    pred_v2 = pred_v2 - bias2
    resid_v2 = pred_v2 - meas
    v2 = per_regime_rmse(resid_v2, regime)

    # V3 — Linear ST with fit C_alpha
    cf, cr, pegged = triage.fit_c_alpha(df, L, P.l_f, P.l_r, P.m, P.I_z)
    print(f"[V3] fit C_alpha_f={cf:.0f}, C_alpha_r={cr:.0f}, pegged_upper={pegged}")
    pred_v3 = triage.linear_st_yaw_rate(
        df["v_mps"].to_numpy(), df["delta_road_rad"].to_numpy(),
        L, P.l_f, P.l_r, P.m, P.I_z, cf, cr,
    )
    bias3 = yaw_bias(df, pred_v3 - meas)
    pred_v3 = pred_v3 - bias3
    resid_v3 = pred_v3 - meas
    v3 = per_regime_rmse(resid_v3, regime)

    # V4 — residual learner (LOO)
    # Train against the V3 residual, out-of-fold by segment.
    df_for_learner = df.copy()
    df_for_learner["yaw_rate_resid_v3"] = resid_v3
    oof, info = triage.residual_learner_loo(df_for_learner, residual_col="yaw_rate_resid_v3")
    pred_v4 = pred_v3 - oof
    resid_v4 = pred_v4 - meas
    v4 = per_regime_rmse(resid_v4, regime)
    print(f"[V4] LOO residual-learner oof_rmse={info['oof_rmse']:.5f}")

    rows = [
        ("V0 baseline (as-is)", v0),
        ("V1 KS recal + yaw-bias", v1),
        ("V2 Linear ST (prior Cα)", v2),
        ("V3 Linear ST (fit Cα)", v3),
        ("V4 + residual learner (LOO)", v4),
    ]
    print(f"\n{'variant':35s} {'overall':>9s} {'straight':>9s} {'steady':>9s} {'transient':>9s}")
    for name, r in rows:
        print(f"{name:35s} {r['overall']:9.5f} {r['straight']:9.5f} {r['steady']:9.5f} {r['transient']:9.5f}")

    # Pick best by overall RMSE (excluding regressions vs V0).
    candidates = [(name, r, p) for (name, r), p in zip(rows, [pred_v0, pred_v1, pred_v2, pred_v3, pred_v4])]
    valid = [(n, r, p) for (n, r, p) in candidates if r["overall"] <= v0["overall"]]
    best = min(valid, key=lambda x: x[1]["overall"]) if valid else candidates[0]
    best_name, best_r, best_pred = best
    print(f"\n[best] {best_name} overall={best_r['overall']:.5f}")

    out_df = pd.DataFrame({
        "yaw_rate_pred_rads": best_pred,
        "yaw_rate_meas_rads": meas,
        "delta_road_rad": df["delta_road_rad"].to_numpy(),
        "yaw_rate_resid_rads": resid_v0,
    })
    best_csv = OUT / "best_variant.csv"
    out_df.to_csv(best_csv, index=False)
    print(f"[wrote] {best_csv}")

    # Marginal drops (strict, V0..V4)
    deltas = [v0["overall"] - v1["overall"],
              v1["overall"] - v2["overall"],
              v2["overall"] - v3["overall"],
              v3["overall"] - v4["overall"]]
    total = v0["overall"] - v4["overall"]
    sum_marg = sum(deltas)
    print(f"\n[acc] marginal drops V0->V4: {deltas}  sum={sum_marg:.5f}  total={total:.5f}")

    summary = {
        "platform": PLATFORM,
        "n_segments": len(csvs),
        "rows": {name: r for name, r in rows},
        "v3_fit": {"cf": cf, "cr": cr, "pegged_upper": pegged},
        "v4_loo_rmse": info["oof_rmse"],
        "marginal": {
            "V0->V1": deltas[0],
            "V1->V2": deltas[1],
            "V2->V3": deltas[2],
            "V3->V4": deltas[3],
            "total_V0->V4": total,
            "sum_marginal": sum_marg,
        },
        "best_variant": best_name,
        "best_csv": str(best_csv),
        "v0_baseline_rmse": v0["overall"],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[wrote] {OUT/'summary.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
