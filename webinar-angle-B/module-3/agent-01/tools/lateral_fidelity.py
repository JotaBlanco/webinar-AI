"""Lateral fidelity variant ladder for FORD_MUSTANG_MACH_E_MK1.

V0  KS baseline (yaw_rate_resid_rads as-is)
V1  KS + per-segment yaw-gyro bias (straight-line samples only)
V2  Linear ST steady-state gain, prior C_alpha
V3  Linear ST steady-state gain, fit C_alpha (bounded 50-500 kN/rad)
V4  V3 + Ridge residual learner on [v, |a_y|, |delta|, sign(ddelta/dt)], LOSO CV

All variants share the same Ford Mach-E segment set and the same regime mask.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-01")
PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
SIM_DIR = ROOT / "data" / "sim" / "segments" / PLATFORM

# openpilot priors from PARAM_BY_PLATFORM (Mach-E MK1)
L = 2.984
M = 2336.0
I_Z = 4879.05
L_F = 1.313
L_R = 1.671
CAF_PRIOR = 286_551.0
CAR_PRIOR = 355_912.0
V_MIN = 2.0  # fall back to KS below this

DT = 0.02


def load_all_segments() -> pd.DataFrame:
    csvs = sorted(SIM_DIR.rglob("sim.csv"))
    frames = []
    for c in csvs:
        df = pd.read_csv(c)
        seg = "/".join(c.relative_to(SIM_DIR).parts[:-1])
        df["segment"] = seg
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def regime(df: pd.DataFrame) -> pd.Series:
    delta = df["delta_road_rad"].to_numpy()
    dd = np.gradient(delta, DT)
    r = np.where(np.abs(delta) < 0.01, "straight",
                 np.where(np.abs(dd) < 0.05, "steady", "transient"))
    return pd.Series(r, index=df.index)


def rmse(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def ks_yaw_pred(v: np.ndarray, delta: np.ndarray) -> np.ndarray:
    return (v / L) * np.tan(delta)


def st_yaw_pred(v: np.ndarray, delta: np.ndarray, caf: float, car: float) -> np.ndarray:
    """Linear ST steady-state gain. KS below V_MIN."""
    Kus = M * (L_R * car - L_F * caf) / (L * L * caf * car)
    out = np.empty_like(v)
    mask_low = v < V_MIN
    out[mask_low] = ks_yaw_pred(v[mask_low], delta[mask_low])
    out[~mask_low] = (v[~mask_low] * delta[~mask_low]) / (L * (1.0 + Kus * v[~mask_low] ** 2))
    return out


def fit_cornering_stiffness(df: pd.DataFrame) -> tuple[float, float, bool]:
    """Fit (caf, car) minimising RMSE of ST yaw-rate vs measured on steady-cornering
    samples, bounded 50-500 kN/rad. Flag = True iff a bound is hit (regression flag)."""
    from scipy.optimize import minimize

    reg = regime(df)
    m = (reg == "steady") & (df["v_mps"].to_numpy() > V_MIN)
    v = df.loc[m, "v_mps"].to_numpy()
    delta = df.loc[m, "delta_road_rad"].to_numpy()
    y_meas = df.loc[m, "yaw_rate_meas_rads"].to_numpy()

    lo, hi = 50_000.0, 500_000.0

    def loss(theta):
        caf, car = theta
        pred = st_yaw_pred(v, delta, caf, car)
        return float(np.mean((pred - y_meas) ** 2))

    res = minimize(
        loss,
        x0=[CAF_PRIOR, CAR_PRIOR],
        method="L-BFGS-B",
        bounds=[(lo, hi), (lo, hi)],
    )
    caf, car = float(res.x[0]), float(res.x[1])
    pegged = (abs(caf - lo) < 1e-3 or abs(caf - hi) < 1e-3 or
              abs(car - lo) < 1e-3 or abs(car - hi) < 1e-3)
    return caf, car, pegged


def per_segment_bias(df: pd.DataFrame, pred_col: str) -> np.ndarray:
    """Per-segment yaw-gyro bias estimated on straight samples only;
    subtracted from predictions across all samples in that segment."""
    reg = regime(df)
    bias = {}
    for seg, sub in df.groupby("segment"):
        idx = sub.index
        rseg = reg.loc[idx]
        straight = rseg == "straight"
        if straight.sum() < 50:
            bias[seg] = 0.0
            continue
        resid_straight = (df.loc[idx[straight], pred_col].to_numpy() -
                          df.loc[idx[straight], "yaw_rate_meas_rads"].to_numpy())
        bias[seg] = float(np.mean(resid_straight))
    return df["segment"].map(bias).to_numpy()


def loso_ridge_residual(df: pd.DataFrame, pred_col: str) -> np.ndarray:
    """LOSO Ridge on [v, |a_y|, |delta|, sign(ddelta/dt)] predicting the
    residual (pred - meas). Returns out-of-fold residual_after."""
    delta = df["delta_road_rad"].to_numpy()
    dd = np.gradient(delta, DT)
    a_y = df.get("a_lat_meas_mps2", df["a_y_pred_mps2"]).to_numpy()
    X = np.column_stack([
        df["v_mps"].to_numpy(),
        np.abs(a_y),
        np.abs(delta),
        np.sign(dd),
    ])
    y_resid = df[pred_col].to_numpy() - df["yaw_rate_meas_rads"].to_numpy()
    segments = df["segment"].to_numpy()
    out = np.zeros_like(y_resid)
    for seg in np.unique(segments):
        test = segments == seg
        train = ~test
        if train.sum() < 1000 or test.sum() < 50:
            out[test] = y_resid[test]
            continue
        clf = Ridge(alpha=1.0)
        clf.fit(X[train], y_resid[train])
        out[test] = y_resid[test] - clf.predict(X[test])
    return out


def regime_rmse(resid: np.ndarray, reg: pd.Series) -> dict:
    out = {"all": rmse(resid)}
    for r in ("straight", "steady", "transient"):
        m = (reg == r).to_numpy()
        out[r] = rmse(resid[m]) if m.any() else float("nan")
    return out


def main() -> None:
    df = load_all_segments()
    reg = regime(df)

    n_seg = df["segment"].nunique()
    n_rows = len(df)

    # Sign sanity
    corner = (reg != "straight").to_numpy()
    sign_corr = float(np.corrcoef(df.loc[corner, "delta_road_rad"],
                                  df.loc[corner, "yaw_rate_meas_rads"])[0, 1])

    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    y_meas = df["yaw_rate_meas_rads"].to_numpy()

    # V0  KS baseline — use precomputed residual
    v0_resid = df["yaw_rate_resid_rads"].to_numpy()

    # V1  KS + per-segment straight-line bias
    df["_ks_pred"] = ks_yaw_pred(v, delta)
    bias_ks = per_segment_bias(df.assign(_pred=df["_ks_pred"]).rename(columns={"_pred": "_ks_bias_src"}),
                               pred_col="_ks_pred")
    v1_resid = (df["_ks_pred"].to_numpy() - bias_ks) - y_meas

    # V2  Linear ST prior C_alpha
    v2_pred = st_yaw_pred(v, delta, CAF_PRIOR, CAR_PRIOR)
    df["_st_prior"] = v2_pred
    bias_st_prior = per_segment_bias(df, pred_col="_st_prior")
    v2_resid = (v2_pred - bias_st_prior) - y_meas

    # V3  Linear ST fit C_alpha
    caf, car, pegged = fit_cornering_stiffness(df)
    v3_pred = st_yaw_pred(v, delta, caf, car)
    df["_st_fit"] = v3_pred
    bias_st_fit = per_segment_bias(df, pred_col="_st_fit")
    v3_resid = (v3_pred - bias_st_fit) - y_meas

    # V4  V3 + LOSO Ridge residual learner
    df["_st_fit_debiased"] = v3_pred - bias_st_fit
    v4_resid = loso_ridge_residual(df, pred_col="_st_fit_debiased")

    variants = {
        "V0_KS_baseline": v0_resid,
        "V1_KS_plus_seg_bias": v1_resid,
        "V2_ST_prior_Calpha": v2_resid,
        "V3_ST_fit_Calpha": v3_resid,
        "V4_V3_plus_LOSO_Ridge": v4_resid,
    }

    rows = []
    prev = None
    for name, resid in variants.items():
        rr = regime_rmse(resid, reg)
        marginal = (prev - rr["all"]) if prev is not None else 0.0
        rows.append({"variant": name, **{k: round(v, 5) for k, v in rr.items()},
                     "marginal_drop_all": round(marginal, 5)})
        prev = rr["all"]

    total_drop = rows[0]["all"] - rows[-1]["all"]
    sum_marginals = sum(r["marginal_drop_all"] for r in rows[1:])
    accounting_gap_pct = 100.0 * (sum_marginals - total_drop) / total_drop if total_drop else 0.0

    summary = {
        "platform": PLATFORM,
        "n_segments": int(n_seg),
        "n_rows": int(n_rows),
        "clamped_inputs": ["v", "delta"],
        "predicted_channels": ["yaw_rate_pred_rads", "a_y_pred_mps2"],
        "truth_channels": ["yaw_rate_meas_rads", "a_lat_meas_mps2"],
        "metric": "RMSE of (yaw_rate_pred - yaw_rate_meas_rads) [rad/s]",
        "sign_check_corr_delta_yawrate_corner": round(sign_corr, 4),
        "fit_Calpha_N_per_rad": {"C_af": round(caf, 1), "C_ar": round(car, 1),
                                 "pegged_at_bound": pegged},
        "accounting_scheme": "sequential_marginal_drop_on_all_regime_rmse",
        "marginal_sum_gap_pct": round(accounting_gap_pct, 2),
        "ladder": rows,
        "regression_flags": [r["variant"] for r in rows[1:]
                             if r["marginal_drop_all"] < 0],
        "calpha_bound_pegged": pegged,
    }

    out_path = ROOT / "out" / "lateral_fidelity_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
