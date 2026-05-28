#!/usr/bin/env python3
"""Run the lateral-fidelity-triage variant ladder on Mach-E segments."""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MOD = HERE.parent
sys.path.insert(0, str(MOD / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(MOD / "code"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402


PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
SEG_ROOT = MOD / "data" / "sim" / "segments" / PLATFORM
OUT = MOD / "out"
OUT.mkdir(exist_ok=True)


def per_regime(df: pd.DataFrame, err_col: str) -> dict[str, float]:
    reg = triage.regime_mask(df)
    out = {"overall": triage.rmse(df[err_col])}
    for r in ("straight", "steady", "transient"):
        sub = df.loc[reg == r, err_col]
        out[r] = triage.rmse(sub) if len(sub) else float("nan")
    return out


def main(n_max: int = 60) -> int:
    paths = sorted(SEG_ROOT.rglob("sim.csv"))[:n_max]
    print(f"Loading {len(paths)} Mach-E segments")
    df = triage.load_many(paths)
    p = PARAM_BY_PLATFORM[PLATFORM]
    L, l_f, l_r = p.L, p.l_f, p.l_r
    m, I_z = p.m, p.I_z
    Cf_prior, Cr_prior = p.C_alpha_f, p.C_alpha_r

    meas = df["yaw_rate_meas_rads"].to_numpy()
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()

    # V0 — baseline from existing residual column (no preprocessing).
    df["err_V0"] = df["yaw_rate_resid_rads"]

    # V1 — KS recalibrated using canonical L + per-segment yaw-gyro bias on straights.
    pred1 = triage.ks_yaw_rate(v, delta, L)
    df["pred_V1"] = pred1
    df["err_V1_raw"] = pred1 - meas
    # Per-segment bias on straight samples
    biases = {}
    for seg, sub in df.groupby("__source__"):
        mask = np.abs(sub["delta_road_rad"].to_numpy()) < 0.01
        bias = float(np.mean(sub.loc[mask, "err_V1_raw"])) if mask.any() else 0.0
        biases[seg] = bias
    df["bias_V1"] = df["__source__"].map(biases)
    df["err_V1"] = df["err_V1_raw"] - df["bias_V1"]
    df["pred_V1_corr"] = df["pred_V1"] - df["bias_V1"]

    # V2 — Linear ST with prior C_alpha (using same per-segment bias).
    pred2 = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, Cf_prior, Cr_prior)
    df["pred_V2"] = pred2
    df["err_V2_raw"] = pred2 - meas
    biases2 = {}
    for seg, sub in df.groupby("__source__"):
        mask = np.abs(sub["delta_road_rad"].to_numpy()) < 0.01
        b = float(np.mean(sub.loc[mask, "err_V2_raw"])) if mask.any() else 0.0
        biases2[seg] = b
    df["err_V2"] = df["err_V2_raw"] - df["__source__"].map(biases2)
    df["pred_V2_corr"] = df["pred_V2"] - df["__source__"].map(biases2)

    # V3 — Linear ST with fit C_alpha
    cf, cr, pegged = triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)
    print(f"V3 fit: C_alpha_f={cf:.0f}, C_alpha_r={cr:.0f}, pegged_upper={pegged}")
    pred3 = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf, cr)
    df["pred_V3"] = pred3
    df["err_V3_raw"] = pred3 - meas
    biases3 = {}
    for seg, sub in df.groupby("__source__"):
        mask = np.abs(sub["delta_road_rad"].to_numpy()) < 0.01
        b = float(np.mean(sub.loc[mask, "err_V3_raw"])) if mask.any() else 0.0
        biases3[seg] = b
    df["err_V3"] = df["err_V3_raw"] - df["__source__"].map(biases3)
    df["pred_V3_corr"] = df["pred_V3"] - df["__source__"].map(biases3)

    # V4 — residual learner on V3 residuals, LOO.
    # Use err_V3 as the residual to learn.
    df_for_learner = df.copy()
    df_for_learner["yaw_rate_resid_rads"] = df["err_V3"].values
    oof, info = triage.residual_learner_loo(df_for_learner, residual_col="yaw_rate_resid_rads")
    # err_V3 = pred_V3_corr - meas. Learner predicts that residual; subtract from pred.
    df["pred_V4_corr"] = df["pred_V3_corr"] - oof
    df["err_V4"] = df["pred_V4_corr"] - meas

    # Per-regime breakdown for each variant
    table = {}
    for v_name, err_col in [
        ("V0", "err_V0"),
        ("V1", "err_V1"),
        ("V2", "err_V2"),
        ("V3", "err_V3"),
        ("V4", "err_V4"),
    ]:
        table[v_name] = per_regime(df, err_col)

    # Determine best by overall RMSE
    best = min(table.items(), key=lambda kv: kv[1]["overall"])
    print(f"\nBest variant: {best[0]} overall RMSE = {best[1]['overall']:.5f}")

    # Save best-variant CSV for sensor.
    pred_map = {
        "V0": df["yaw_rate_pred_rads"].values,  # original
        "V1": df["pred_V1_corr"].values,
        "V2": df["pred_V2_corr"].values,
        "V3": df["pred_V3_corr"].values,
        "V4": df["pred_V4_corr"].values,
    }
    best_name = best[0]
    out_df = pd.DataFrame({
        "yaw_rate_pred_rads": pred_map[best_name],
        "yaw_rate_meas_rads": df["yaw_rate_meas_rads"].values,
        "delta_road_rad": df["delta_road_rad"].values,
        "yaw_rate_resid_rads": df["yaw_rate_resid_rads"].values,  # original V0 column
    })
    best_path = OUT / f"best_variant_{best_name}.csv"
    out_df.to_csv(best_path, index=False)
    print(f"Saved {best_path}")

    # Print summary
    print("\n=== RMSE TABLE (rad/s) ===")
    print(f"{'variant':<6} {'overall':>10} {'straight':>10} {'steady':>10} {'transient':>10}")
    for k, v_ in table.items():
        print(f"{k:<6} {v_['overall']:>10.5f} {v_['straight']:>10.5f} {v_['steady']:>10.5f} {v_['transient']:>10.5f}")

    rmse_V0 = table["V0"]["overall"]
    rmse_last = table["V4"]["overall"]
    total = rmse_V0 - rmse_last
    print(f"\nTotal drop V0->V4: {total:.5f}")
    marginal = []
    keys = ["V0", "V1", "V2", "V3", "V4"]
    for i in range(1, len(keys)):
        m_ = table[keys[i-1]]["overall"] - table[keys[i]]["overall"]
        marginal.append((keys[i], m_))
        print(f"  Δ {keys[i-1]}->{keys[i]} = {m_:+.5f}")
    s = sum(x[1] for x in marginal)
    if total != 0:
        ratio = s / total
        print(f"Sum marginals / total = {ratio:.3f} (target ≈ 1.0 ±15%)")

    # Sanity correlation (sign check) for awareness.
    mask_corn = np.abs(df["delta_road_rad"].values) >= 0.01
    for name, pred in pred_map.items():
        sp = pred[mask_corn]; sm = meas[mask_corn]
        sp = sp[np.isfinite(sp) & np.isfinite(sm)]
        if sp.size > 1:
            c = float(np.corrcoef(pred[mask_corn], meas[mask_corn])[0, 1])
            print(f"corr({name},meas) cornering = {c:+.3f}")
    print(f"\nC_alpha fit: Cf={cf:.0f} (prior {Cf_prior:.0f}), Cr={cr:.0f} (prior {Cr_prior:.0f}), pegged={pegged}")
    print(f"V4 OOF residual rmse (info): {info['oof_rmse']:.5f}")
    print(f"V0 baseline = {rmse_V0:.5f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
