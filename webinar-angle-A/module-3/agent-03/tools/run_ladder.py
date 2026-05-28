"""Run the lateral-fidelity variant ladder on Ford segments.

V0: stock yaw_rate_resid_rads as-is.
V1: KS recalibrated (recompute (v/L)·tan(δ) using canonical L) + per-segment bias.
V2: Linear ST with prior C_α.
V3: Linear ST with fit C_α (joint, bounded).
V4: Residual learner (Ridge) on top of V3, LOO over segments.
"""
from __future__ import annotations

import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd

AGENT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-03")
sys.path.insert(0, str(AGENT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(AGENT / "code"))

import triage  # type: ignore
from parameters import PARAM_BY_PLATFORM  # type: ignore


def gather_segments(platform: str) -> list[Path]:
    root = AGENT / "data" / "sim" / "segments" / platform
    return sorted(root.rglob("sim.csv"))


def per_regime_rmse_from_resid(df: pd.DataFrame, regime: pd.Series, resid: np.ndarray) -> dict:
    out = {}
    e = resid
    out["overall"] = triage.rmse(e)
    for r in ("straight", "steady", "transient"):
        m = (regime == r).to_numpy()
        out[r] = triage.rmse(e[m]) if m.any() else float("nan")
    return out


def main():
    platform = "FORD_MUSTANG_MACH_E_MK1"
    p = PARAM_BY_PLATFORM[platform]
    seg_paths = gather_segments(platform)
    print(f"Platform: {platform}, {len(seg_paths)} segments", flush=True)

    df = triage.load_many(seg_paths)
    regime = triage.regime_mask(df)
    n = len(df)
    print(f"Rows: {n}; regime counts: {regime.value_counts().to_dict()}", flush=True)

    meas = df["yaw_rate_meas_rads"].to_numpy()
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()

    # V0 — stock residual column as-is
    resid_v0 = df["yaw_rate_resid_rads"].to_numpy()
    rmse_v0 = per_regime_rmse_from_resid(df, regime, resid_v0)

    # V1 — KS recalibrated with canonical L + per-segment yaw-gyro bias subtraction
    pred_v1_raw = triage.ks_yaw_rate(v, delta, p.L)
    resid_v1_raw = pred_v1_raw - meas
    # per-segment bias on straight samples
    biases = {}
    resid_v1 = resid_v1_raw.copy()
    for seg, sub in df.groupby("__source__"):
        idx = sub.index.to_numpy()
        mask_straight = (regime.loc[idx] == "straight").to_numpy()
        if mask_straight.sum() > 5:
            b = float(np.nanmean(resid_v1_raw[idx][mask_straight]))
        else:
            b = 0.0
        biases[seg] = b
        resid_v1[idx] = resid_v1_raw[idx] - b
    rmse_v1 = per_regime_rmse_from_resid(df, regime, resid_v1)

    # V2 — Linear ST with prior C_α (apply same per-segment bias)
    pred_v2_raw = triage.linear_st_yaw_rate(
        v, delta, p.L, p.l_f, p.l_r, p.m, p.I_z, p.C_alpha_f, p.C_alpha_r
    )
    resid_v2_raw = pred_v2_raw - meas
    resid_v2 = resid_v2_raw.copy()
    for seg, sub in df.groupby("__source__"):
        idx = sub.index.to_numpy()
        mask_straight = (regime.loc[idx] == "straight").to_numpy()
        if mask_straight.sum() > 5:
            b = float(np.nanmean(resid_v2_raw[idx][mask_straight]))
        else:
            b = 0.0
        resid_v2[idx] = resid_v2_raw[idx] - b
    rmse_v2 = per_regime_rmse_from_resid(df, regime, resid_v2)

    # Sign sanity check
    sign_corr = float(np.corrcoef(delta, meas)[0, 1])

    # V3 — Linear ST with fit C_α
    cf_fit, cr_fit, pegged = triage.fit_c_alpha(
        df, p.L, p.l_f, p.l_r, p.m, p.I_z
    )
    pred_v3_raw = triage.linear_st_yaw_rate(
        v, delta, p.L, p.l_f, p.l_r, p.m, p.I_z, cf_fit, cr_fit
    )
    resid_v3_raw = pred_v3_raw - meas
    resid_v3 = resid_v3_raw.copy()
    for seg, sub in df.groupby("__source__"):
        idx = sub.index.to_numpy()
        mask_straight = (regime.loc[idx] == "straight").to_numpy()
        if mask_straight.sum() > 5:
            b = float(np.nanmean(resid_v3_raw[idx][mask_straight]))
        else:
            b = 0.0
        resid_v3[idx] = resid_v3_raw[idx] - b
    rmse_v3 = per_regime_rmse_from_resid(df, regime, resid_v3)

    # V4 — residual learner LOO on top of V3 residual
    # Feed the v3 residual into the learner instead of the pre-computed resid_col.
    df2 = df.copy()
    df2["v3_resid"] = resid_v3
    # ensure a_y_pred_mps2 present
    oof, info = triage.residual_learner_loo(df2, residual_col="v3_resid")
    resid_v4 = resid_v3 - oof
    # mask NaNs (shouldn't be any from LOO)
    rmse_v4 = per_regime_rmse_from_resid(df, regime, resid_v4)

    summary = {
        "platform": platform,
        "n_segments": len(seg_paths),
        "n_rows": int(n),
        "regime_counts": {k: int(v) for k, v in regime.value_counts().to_dict().items()},
        "sign_corr_delta_meas": sign_corr,
        "L": p.L,
        "C_alpha_prior": [p.C_alpha_f, p.C_alpha_r],
        "C_alpha_fit": [cf_fit, cr_fit],
        "C_alpha_pegged_upper": bool(pegged),
        "V0": rmse_v0,
        "V1": rmse_v1,
        "V2": rmse_v2,
        "V3": rmse_v3,
        "V4": rmse_v4,
        "V4_oof_info": info,
        "mean_bias_v1": float(np.mean(list(biases.values()))),
    }

    out = AGENT / "out"
    out.mkdir(exist_ok=True)
    with open(out / "ladder_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=float)
    print(json.dumps(summary, indent=2, default=float))


if __name__ == "__main__":
    main()
