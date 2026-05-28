"""Run the lateral-fidelity variant ladder on Ford Mach-E segments.

V0: baseline (yaw_rate_resid_rads as-is)
V1: KS recalibrated with canonical L + per-segment yaw-gyro bias
V2: Linear ST with prior C_alpha
V3: Linear ST with fit C_alpha
V4: Residual learner (Ridge) trained on V3 residuals with LOO CV
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json

AGENT_DIR = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-04")
sys.path.insert(0, str(AGENT_DIR / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(AGENT_DIR / "code"))

import triage  # noqa
from parameters import PARAM_BY_PLATFORM  # noqa

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
SEG_GLOB = AGENT_DIR / "data" / "sim" / "segments" / PLATFORM
OUT_DIR = AGENT_DIR / "out"
OUT_DIR.mkdir(exist_ok=True)


def collect_segments(platform: str, limit: int | None = None):
    base = AGENT_DIR / "data" / "sim" / "segments" / platform
    paths = sorted(p for p in base.rglob("sim.csv"))
    if limit:
        paths = paths[:limit]
    return paths


def per_regime_rmse_of_series(df: pd.DataFrame, resid: np.ndarray, reg: pd.Series) -> dict:
    out = {"overall": triage.rmse(resid)}
    for r in ("straight", "steady", "transient"):
        sub = resid[(reg == r).to_numpy()]
        out[r] = triage.rmse(sub) if sub.size else float("nan")
    return out


def main():
    paths = collect_segments(PLATFORM, limit=60)  # keep wall-clock manageable
    print(f"Loading {len(paths)} segments from {PLATFORM}")
    df = triage.load_many(paths)
    print(f"Rows: {len(df):,}")

    p = PARAM_BY_PLATFORM[PLATFORM]
    print(f"Params: L={p.L}, m={p.m}, I_z={p.I_z}, l_f={p.l_f}, l_r={p.l_r}, "
          f"Cf={p.C_alpha_f}, Cr={p.C_alpha_r}")

    reg = triage.regime_mask(df)
    df["__regime__"] = reg.values

    results = {}

    # V0 — baseline
    v0_resid = df["yaw_rate_resid_rads"].to_numpy()
    results["V0"] = per_regime_rmse_of_series(df, v0_resid, reg)

    # V1 — KS recalibrated with canonical L and per-segment yaw bias
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    meas = df["yaw_rate_meas_rads"].to_numpy()

    ks_pred = triage.ks_yaw_rate(v, delta, p.L)
    # Per-segment yaw bias on straight samples
    df["__ks_pred__"] = ks_pred
    df["__resid_ks__"] = ks_pred - meas
    bias_by_seg = {}
    bias_arr = np.zeros(len(df))
    for seg, sub in df.groupby("__source__"):
        straight_mask = (reg.loc[sub.index] == "straight").to_numpy()
        if straight_mask.sum() > 10:
            b = float(np.nanmean(sub["__resid_ks__"].to_numpy()[straight_mask]))
        else:
            b = 0.0
        bias_by_seg[seg] = b
        bias_arr[sub.index.to_numpy()] = b
    v1_resid = (ks_pred - bias_arr) - meas
    results["V1"] = per_regime_rmse_of_series(df, v1_resid, reg)
    print(f"V1 mean bias subtracted: {np.mean(list(bias_by_seg.values())):.4e} rad/s "
          f"(median={np.median(list(bias_by_seg.values())):.4e})")

    # V2 — Linear ST with prior Cα (with same per-segment bias term)
    st_pred = triage.linear_st_yaw_rate(
        v, delta, p.L, p.l_f, p.l_r, p.m, p.I_z, p.C_alpha_f, p.C_alpha_r
    )
    # Recompute bias on straight under ST
    df["__st_pred__"] = st_pred
    df["__resid_st__"] = st_pred - meas
    bias_st = np.zeros(len(df))
    bias_st_seg = {}
    for seg, sub in df.groupby("__source__"):
        straight_mask = (reg.loc[sub.index] == "straight").to_numpy()
        if straight_mask.sum() > 10:
            b = float(np.nanmean(sub["__resid_st__"].to_numpy()[straight_mask]))
        else:
            b = 0.0
        bias_st_seg[seg] = b
        bias_st[sub.index.to_numpy()] = b
    v2_resid = (st_pred - bias_st) - meas
    results["V2"] = per_regime_rmse_of_series(df, v2_resid, reg)

    # V3 — Linear ST with fit Cα
    cf_fit, cr_fit, pegged = triage.fit_c_alpha(
        df.rename(columns={"yaw_rate_meas_rads": "yaw_rate_meas_rads"}),
        p.L, p.l_f, p.l_r, p.m, p.I_z,
    )
    print(f"V3 fit C_alpha_f={cf_fit:,.0f}, C_alpha_r={cr_fit:,.0f}, pegged={pegged}")
    st_pred_fit = triage.linear_st_yaw_rate(
        v, delta, p.L, p.l_f, p.l_r, p.m, p.I_z, cf_fit, cr_fit
    )
    df["__st_fit_pred__"] = st_pred_fit
    df["__resid_st_fit__"] = st_pred_fit - meas
    bias_st_fit = np.zeros(len(df))
    bias_v3_seg = {}
    for seg, sub in df.groupby("__source__"):
        straight_mask = (reg.loc[sub.index] == "straight").to_numpy()
        if straight_mask.sum() > 10:
            b = float(np.nanmean(sub["__resid_st_fit__"].to_numpy()[straight_mask]))
        else:
            b = 0.0
        bias_v3_seg[seg] = b
        bias_st_fit[sub.index.to_numpy()] = b
    v3_resid = (st_pred_fit - bias_st_fit) - meas
    results["V3"] = per_regime_rmse_of_series(df, v3_resid, reg)

    # V4 — residual learner on V3 residuals with LOO CV
    # Use V3's residual as the target
    df["__v3_resid__"] = v3_resid
    oof, info = triage.residual_learner_loo(df, residual_col="__v3_resid__")
    v4_resid = v3_resid - oof
    results["V4"] = per_regime_rmse_of_series(df, v4_resid, reg)
    print(f"V4 LOO oof rmse (learning V3 resid) = {info['oof_rmse']:.4e}")

    # Marginal attribution
    order = ["V0", "V1", "V2", "V3", "V4"]
    marginals = {}
    for i in range(1, len(order)):
        marginals[order[i]] = results[order[i-1]]["overall"] - results[order[i]]["overall"]
    total = results["V0"]["overall"] - results[order[-1]]["overall"]
    sum_marg = sum(marginals.values())
    print(f"\nTotal V0 - V4 = {total:.6f}")
    print(f"Sum of marginals = {sum_marg:.6f}")

    out = {
        "platform": PLATFORM,
        "n_segments": len(paths),
        "n_rows": int(len(df)),
        "params": {
            "L": p.L, "m": p.m, "I_z": p.I_z, "l_f": p.l_f, "l_r": p.l_r,
            "C_alpha_f": p.C_alpha_f, "C_alpha_r": p.C_alpha_r, "i_s": p.i_s,
        },
        "v3_fit": {"C_alpha_f": cf_fit, "C_alpha_r": cr_fit, "pegged": bool(pegged)},
        "v1_mean_bias": float(np.mean(list(bias_by_seg.values()))),
        "results": results,
        "marginals": marginals,
        "total_drop": total,
        "sum_marginals": sum_marg,
        "v4_loo_oof_rmse": info["oof_rmse"],
    }
    (OUT_DIR / "ladder_results.json").write_text(json.dumps(out, indent=2))
    print("\nResults JSON written to out/ladder_results.json")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
