"""Run the V0->V4 variant ladder on Ford Mach-E segments.

Outputs a JSON summary + a per-segment dataframe under ../out/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(ROOT / "code"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402


PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
SEG_GLOB = ROOT / "data" / "sim" / "segments" / PLATFORM
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

# Cap how many segments we use to keep runtime sane and produce stable estimates.
MAX_SEGMENTS = 60


def regime_breakdown(df: pd.DataFrame, resid_col: str) -> dict:
    return triage.per_regime_rmse(df, resid_col)


def main():
    paths = sorted(SEG_GLOB.rglob("sim.csv"))[:MAX_SEGMENTS]
    print(f"loading {len(paths)} segments from {PLATFORM}")

    df = triage.load_many(paths)
    # drop rows where v or delta are non-finite
    df = df.dropna(subset=["v_mps", "delta_road_rad", "yaw_rate_meas_rads"]).reset_index(drop=True)

    p = PARAM_BY_PLATFORM[PLATFORM]
    L, m, I_z, l_f, l_r = p.L, p.m, p.I_z, p.l_f, p.l_r
    Cf, Cr = p.C_alpha_f, p.C_alpha_r
    print(f"params: L={L} m={m} l_f={l_f} l_r={l_r} Cf={Cf} Cr={Cr}")

    results = {}
    # ----- V0: baseline residual as-is -----
    results["V0"] = regime_breakdown(df, "yaw_rate_resid_rads")

    # ----- V1: KS recalibrated -----
    # Use canonical L. Subtract per-segment yaw-gyro bias on straight-line samples.
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    meas = df["yaw_rate_meas_rads"].to_numpy()
    ks_pred = triage.ks_yaw_rate(v, delta, L)
    df["yaw_rate_pred_v1_raw"] = ks_pred

    bias = {}
    straight_mask = np.abs(delta) < 0.01
    for src, sub in df.groupby("__source__"):
        m_s = straight_mask[sub.index]
        if m_s.sum() < 10:
            bias[src] = 0.0
        else:
            r = (sub["yaw_rate_pred_v1_raw"].to_numpy() - sub["yaw_rate_meas_rads"].to_numpy())[m_s]
            bias[src] = float(np.nanmean(r))
    bias_vec = df["__source__"].map(bias).to_numpy()
    df["yaw_rate_pred_v1"] = df["yaw_rate_pred_v1_raw"] - bias_vec
    df["resid_v1"] = df["yaw_rate_pred_v1"] - df["yaw_rate_meas_rads"]
    results["V1"] = regime_breakdown(df, "resid_v1")
    results["V1_meta"] = {
        "mean_bias_rad_s": float(np.mean(list(bias.values()))),
        "n_segments_with_bias": int(sum(1 for b in bias.values() if b != 0.0)),
    }

    # ----- V2: Linear ST with prior C_alpha (still bias-corrected per-segment) -----
    st_pred = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, Cf, Cr)
    df["yaw_rate_pred_v2_raw"] = st_pred
    # recompute bias on the V2 raw predictor (so V2 keeps the V1-style honesty)
    bias2 = {}
    for src, sub in df.groupby("__source__"):
        m_s = straight_mask[sub.index]
        if m_s.sum() < 10:
            bias2[src] = 0.0
        else:
            r = (sub["yaw_rate_pred_v2_raw"].to_numpy() - sub["yaw_rate_meas_rads"].to_numpy())[m_s]
            bias2[src] = float(np.nanmean(r))
    bias2_vec = df["__source__"].map(bias2).to_numpy()
    df["yaw_rate_pred_v2"] = df["yaw_rate_pred_v2_raw"] - bias2_vec
    df["resid_v2"] = df["yaw_rate_pred_v2"] - df["yaw_rate_meas_rads"]
    results["V2"] = regime_breakdown(df, "resid_v2")

    # ----- V3: ST with fit C_alpha -----
    Cf_fit, Cr_fit, pegged = triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)
    print(f"V3 fit: Cf={Cf_fit:.0f} Cr={Cr_fit:.0f} pegged={pegged}")
    st_pred_fit = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, Cf_fit, Cr_fit)
    df["yaw_rate_pred_v3_raw"] = st_pred_fit
    bias3 = {}
    for src, sub in df.groupby("__source__"):
        m_s = straight_mask[sub.index]
        if m_s.sum() < 10:
            bias3[src] = 0.0
        else:
            r = (sub["yaw_rate_pred_v3_raw"].to_numpy() - sub["yaw_rate_meas_rads"].to_numpy())[m_s]
            bias3[src] = float(np.nanmean(r))
    bias3_vec = df["__source__"].map(bias3).to_numpy()
    df["yaw_rate_pred_v3"] = df["yaw_rate_pred_v3_raw"] - bias3_vec
    df["resid_v3"] = df["yaw_rate_pred_v3"] - df["yaw_rate_meas_rads"]
    results["V3"] = regime_breakdown(df, "resid_v3")
    results["V3_meta"] = {"Cf_fit": Cf_fit, "Cr_fit": Cr_fit, "pegged_at_upper": pegged}

    # ----- V4: residual learner (Ridge) with LOSO CV on V3 residuals -----
    try:
        # Build feature frame: target is V3 residual (signed). We predict it and subtract.
        from sklearn.linear_model import Ridge

        segs = df["__source__"].unique()
        t = df["t_s"].to_numpy()
        dt = np.where(np.diff(t, prepend=t[0]) > 0, np.diff(t, prepend=t[0]), 0.02)
        ddelta = np.gradient(df["delta_road_rad"].to_numpy()) / dt
        a_y = df["a_y_pred_mps2"].to_numpy() if "a_y_pred_mps2" in df.columns else np.zeros(len(df))
        X = np.column_stack([
            df["v_mps"].to_numpy(),
            np.abs(a_y),
            np.abs(df["delta_road_rad"].to_numpy()),
            np.sign(ddelta),
        ])
        y = df["resid_v3"].to_numpy()

        oof = np.full(len(df), np.nan)
        for seg in segs:
            tr = df["__source__"].to_numpy() != seg
            te = ~tr
            model = Ridge(alpha=1.0).fit(X[tr], y[tr])
            oof[te] = model.predict(X[te])
        df["resid_v4"] = y - oof
        results["V4"] = regime_breakdown(df, "resid_v4")
        results["V4_meta"] = {"loso_oof": True}
    except Exception as e:
        results["V4_error"] = str(e)
        print(f"V4 failed: {e}")

    out_json = OUT / "ladder_summary.json"
    out_json.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))

    # save residuals for reference
    cols = ["__source__", "t_s", "v_mps", "delta_road_rad",
            "yaw_rate_meas_rads", "yaw_rate_pred_rads", "yaw_rate_resid_rads",
            "yaw_rate_pred_v1", "resid_v1",
            "yaw_rate_pred_v2", "resid_v2",
            "yaw_rate_pred_v3", "resid_v3"]
    if "resid_v4" in df.columns:
        cols.append("resid_v4")
    df[cols].to_csv(OUT / "ladder_residuals.csv", index=False)


if __name__ == "__main__":
    main()
