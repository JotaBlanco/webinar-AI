"""Compose regime-segmentation + lateral-fidelity-triage to improve the
lateral (yaw-rate) prediction on Ford Mach-E segments.

Variant ladder (fixed order, strict marginal accounting):
  V0 baseline   -- RMSE(yaw_rate_resid_rads) as-is, no preprocessing
  V1 KS recal   -- (v/L) tan(δ) with canonical L + per-segment yaw-gyro bias
  V2 ST prior   -- linear single-track w/ prior Cα (with v_min fallback)
  V3 ST fit     -- linear single-track w/ Cα fit on the segment set
  V4 residual   -- Ridge on [v, |a_y|, |δ|, sign(δ̇)] LOO-CV on top of V3
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

AGENT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-4/agent-05")
sys.path.insert(0, str(AGENT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(AGENT / "skills" / "regime-segmentation"))
sys.path.insert(0, str(AGENT / "code"))

import triage  # noqa: E402
import segment  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402


PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
SEG_ROOT = AGENT / "data" / "sim" / "segments" / PLATFORM


def pick_segments(n: int = 8) -> list[Path]:
    """Pick a deterministic subset of Mach-E segments — first n found sorted."""
    paths = sorted(SEG_ROOT.rglob("sim.csv"))
    return paths[:n]


def per_segment_bias(df: pd.DataFrame, pred: np.ndarray) -> np.ndarray:
    """Subtract per-segment mean (pred - meas) computed on straight-line samples
    (|δ_road| < 0.01). Returns bias-corrected pred."""
    meas = df["yaw_rate_meas_rads"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    out = pred.copy()
    for seg, idx in df.groupby("__source__").indices.items():
        idx = np.asarray(idx)
        straight = idx[np.abs(delta[idx]) < 0.01]
        if straight.size > 50:
            bias = float(np.nanmean(pred[straight] - meas[straight]))
        else:
            bias = 0.0
        out[idx] = pred[idx] - bias
    return out


def fmt_pr(d: dict[str, float]) -> str:
    return (f"overall={d['overall']:.5f}, straight={d['straight']:.5f}, "
            f"steady={d['steady']:.5f}, transient={d['transient']:.5f}")


def main() -> None:
    seg_paths = pick_segments(8)
    print(f"using {len(seg_paths)} Mach-E segments:")
    for p in seg_paths:
        print(" ", p.relative_to(SEG_ROOT))

    # Compose: regime-segmentation loads & validates, then triage uses df
    df = segment.load_and_validate([str(p) for p in seg_paths])
    df = segment.tag(df)

    n = len(df)
    print(f"\nrows: {n}")
    counts = df["regime"].value_counts().to_dict()
    print(f"regime counts: {counts}")

    pp = PARAM_BY_PLATFORM[PLATFORM]
    L, l_f, l_r, m, I_z = pp.L, pp.l_f, pp.l_r, pp.m, pp.I_z
    Cf, Cr = pp.C_alpha_f, pp.C_alpha_r
    print(f"\nparams: L={L:.3f}, l_f={l_f:.3f}, l_r={l_r:.3f}, m={m:.0f}, "
          f"I_z={I_z:.1f}, Cαf={Cf:.0f}, Cαr={Cr:.0f}")

    meas = df["yaw_rate_meas_rads"].to_numpy()

    # ---- V0 baseline (resid as-is)
    pred_v0 = df["yaw_rate_pred_rads"].to_numpy()
    df_v0 = df.assign(yaw_rate_pred_rads=pred_v0,
                      __resid__=df["yaw_rate_resid_rads"].to_numpy())
    rmse_v0 = segment.per_regime_rmse(df_v0, "__resid__")
    print(f"\nV0 (baseline, as-is yaw_rate_resid_rads):  {fmt_pr(rmse_v0)}")

    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()

    # ---- V1 KS recalibrated + per-segment bias on straights
    pred_v1_raw = triage.ks_yaw_rate(v, delta, L)
    pred_v1 = per_segment_bias(df, pred_v1_raw)
    resid_v1 = pred_v1 - meas
    df_v1 = df.assign(__resid__=resid_v1)
    rmse_v1 = segment.per_regime_rmse(df_v1, "__resid__")
    print(f"V1 (KS recal + per-seg bias):              {fmt_pr(rmse_v1)}")

    # ---- V2 ST with prior Cα
    pred_v2_raw = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, Cf, Cr)
    pred_v2 = per_segment_bias(df, pred_v2_raw)
    resid_v2 = pred_v2 - meas
    df_v2 = df.assign(__resid__=resid_v2)
    rmse_v2 = segment.per_regime_rmse(df_v2, "__resid__")
    print(f"V2 (ST prior Cα):                          {fmt_pr(rmse_v2)}")

    # ---- V3 ST with fit Cα
    cf_fit, cr_fit, pegged = triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)
    print(f"\nV3 fit: Cαf={cf_fit:.0f}, Cαr={cr_fit:.0f}, pegged_upper={pegged}")
    pred_v3_raw = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf_fit, cr_fit)
    pred_v3 = per_segment_bias(df, pred_v3_raw)
    resid_v3 = pred_v3 - meas
    df_v3 = df.assign(__resid__=resid_v3)
    rmse_v3 = segment.per_regime_rmse(df_v3, "__resid__")
    print(f"V3 (ST fit Cα):                            {fmt_pr(rmse_v3)}")

    # ---- V4 residual learner LOO on top of V3
    df_for_v4 = df.assign(__v3_resid__=resid_v3)
    oof, info = triage.residual_learner_loo(df_for_v4, residual_col="__v3_resid__")
    # corrected pred: pred_v3 - learned residual (because resid = pred - meas;
    # subtracting the learned resid pushes pred toward meas)
    pred_v4 = pred_v3 - oof
    resid_v4 = pred_v4 - meas
    df_v4 = df.assign(__resid__=resid_v4)
    rmse_v4 = segment.per_regime_rmse(df_v4, "__resid__")
    print(f"\nV4 residual learner: oof_rmse on resids = {info['oof_rmse']:.5f}")
    print(f"V4 (V3 + Ridge LOO residual):              {fmt_pr(rmse_v4)}")

    # ---- accounting
    total = rmse_v0["overall"] - rmse_v4["overall"]
    marg = {
        "V1": rmse_v0["overall"] - rmse_v1["overall"],
        "V2": rmse_v1["overall"] - rmse_v2["overall"],
        "V3": rmse_v2["overall"] - rmse_v3["overall"],
        "V4": rmse_v3["overall"] - rmse_v4["overall"],
    }
    print(f"\ntotal drop V0->V4 (overall): {total:.5f}")
    print(f"marginal: {marg}")
    print(f"sum marginal: {sum(marg.values()):.5f}")

    # ---- pick best variant by overall RMSE, write its CSV for sensor
    variants = {
        "V0": (rmse_v0["overall"], pred_v0),
        "V1": (rmse_v1["overall"], pred_v1),
        "V2": (rmse_v2["overall"], pred_v2),
        "V3": (rmse_v3["overall"], pred_v3),
        "V4": (rmse_v4["overall"], pred_v4),
    }
    best_name = min(variants, key=lambda k: variants[k][0])
    best_pred = variants[best_name][1]
    out_dir = AGENT / "out"
    out_dir.mkdir(exist_ok=True)
    best_path = out_dir / f"best_{best_name}.csv"
    pd.DataFrame({
        "t_s": df["t_s"].to_numpy(),
        "delta_road_rad": delta,
        "v_mps": v,
        "yaw_rate_pred_rads": best_pred,
        "yaw_rate_meas_rads": meas,
        "yaw_rate_resid_rads": df["yaw_rate_resid_rads"].to_numpy(),
    }).to_csv(best_path, index=False)
    print(f"\nbest variant: {best_name}  RMSE_overall={variants[best_name][0]:.5f}")
    print(f"wrote: {best_path}")

    # write all intermediate variant csvs
    for name, pred in [("V1", pred_v1), ("V2", pred_v2), ("V3", pred_v3), ("V4", pred_v4)]:
        p = out_dir / f"variant_{name}.csv"
        pd.DataFrame({
            "t_s": df["t_s"].to_numpy(),
            "delta_road_rad": delta,
            "v_mps": v,
            "yaw_rate_pred_rads": pred,
            "yaw_rate_meas_rads": meas,
            "yaw_rate_resid_rads": df["yaw_rate_resid_rads"].to_numpy(),
        }).to_csv(p, index=False)

    # Save summary numbers as JSON for later
    import json
    summary = {
        "platform": PLATFORM,
        "n_segments": len(seg_paths),
        "n_rows": int(n),
        "regime_counts": counts,
        "cf_fit": cf_fit, "cr_fit": cr_fit, "pegged_upper": pegged,
        "rmse": {"V0": rmse_v0, "V1": rmse_v1, "V2": rmse_v2,
                  "V3": rmse_v3, "V4": rmse_v4},
        "marginal_overall": marg,
        "total_drop_overall": total,
        "best": best_name,
        "best_path": str(best_path),
        "oof_rmse_v4_resids": info["oof_rmse"],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print("wrote summary.json")


if __name__ == "__main__":
    main()
