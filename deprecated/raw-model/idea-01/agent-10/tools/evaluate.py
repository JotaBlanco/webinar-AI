"""Lateral-prediction improvement ladder for KS model on Ford segments.

Baseline metric: RMSE of predicted vs measured yaw rate [rad/s] across all
Ford (Mach-E + F-150 Lightning) sim CSVs. Lateral acceleration RMSE [m/s^2]
reported as a secondary metric.

Variants (cumulative ladder, applied incrementally):
  V0  Baseline: stock KS prediction already in sim.csv (yaw_rate_pred_rads).
  V1  + delta zero-offset bias correction (per-platform median residual delta)
  V2  + time-lag alignment (yaw measurement vs steering input, per platform)
  V3  + effective steering ratio fit (absorbs compliance), per platform
  V4  + understeer-gradient correction (bicycle steady-state):
            psi_dot = v * delta_eff / (L + K_us * v^2)
        K_us fit per platform.

For each variant we predict yaw rate from measured v and delta with parameters
tweaked, leaving everything else identical. Lateral acceleration is then
a_y = v * psi_dot.

Attribution scheme: Shapley-style **sequential drop-in attribution** -- for the
sequence V0->V1->V2->V3->V4 we report the marginal RMSE reduction at each step
("ladder attribution"). We also report a single-effect attribution
(each technique applied alone, dropped against baseline) so the reader sees
both additive and standalone contributions. Both are honest, neither is the
unique 'true' attribution: we will name the ladder version as primary.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-10")
SIM_ROOT = ROOT / "data" / "sim" / "segments"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]

# Openpilot-canonical params (mirrored from code/parameters.py to avoid
# importing the read-only code dir for side-effecting __main__ blocks):
PARAMS = {
    "FORD_MUSTANG_MACH_E_MK1":  dict(L=2.984, i_s=17.0),
    "FORD_F_150_LIGHTNING_MK1": dict(L=3.70,  i_s=16.9),
}


def list_segments():
    segs = []
    for plat in PLATFORMS:
        for p in (SIM_ROOT / plat).rglob("sim.csv"):
            segs.append((plat, p))
    return segs


def load_segment(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df


def predict_yaw(v, delta, L, K_us=0.0):
    """Steady-state bicycle yaw rate. K_us=0 reduces to KS."""
    return v * delta / (L + K_us * v * v)


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def _shift(arr: np.ndarray, k: int) -> np.ndarray:
    """Shift array by k samples (positive = delay measurement, i.e. compare
    pred[t] to meas[t+k]); we shift the *measurement* backward by k so that
    comparing pred[t] to meas_shifted[t] = meas[t+k] effectively delays meas.

    For our use we shift the prediction forward (delay) by k samples to match
    the lag of the measurement. We return arrays trimmed to common length.
    """
    if k == 0:
        return arr.copy()
    if k > 0:
        return np.concatenate([np.full(k, arr[0]), arr[:-k]])
    k = -k
    return np.concatenate([arr[k:], np.full(k, arr[-1])])


def fit_delta_offset(df_all: pd.DataFrame, L: float) -> float:
    """Fit a single delta_offset (rad, road-wheel) that minimises yaw-rate
    RMSE under KS using measured v. Closed form via linear regression:
        meas ~ (v/L) * (delta + offset)   ->   offset = ( <(meas*L/v) - delta> )
    weighted by samples where |v|>2 m/s to avoid division noise.
    """
    v = df_all["v_mps"].to_numpy()
    delta = df_all["delta_road_rad"].to_numpy()
    meas = df_all["yaw_rate_meas_rads"].to_numpy()
    mask = v > 2.0
    # Solve in least-squares sense: meas = (v/L)*delta + (v/L)*offset
    a = (v[mask] / L)
    b = meas[mask] - a * delta[mask]
    # offset = sum(a*b)/sum(a^2)
    offset = float(np.sum(a * b) / np.sum(a * a))
    return offset


def fit_time_lag(df_all: pd.DataFrame, L: float, max_lag: int = 25) -> int:
    """Find integer sample lag (50Hz -> max 0.5s) that minimises yaw RMSE
    when shifting the *prediction* forward by k (i.e. pred[t] corresponds to
    measurement at t+k*dt). We brute force.
    """
    v = df_all["v_mps"].to_numpy()
    delta = df_all["delta_road_rad"].to_numpy()
    meas = df_all["yaw_rate_meas_rads"].to_numpy()
    pred = predict_yaw(v, delta, L)

    best_k, best_err = 0, rmse(pred, meas)
    for k in range(1, max_lag + 1):
        # shift pred forward by k samples (pred at t aligns with meas at t-k samples back)
        pred_shift = _shift(pred, k)
        err = rmse(pred_shift, meas)
        if err < best_err:
            best_err, best_k = err, k
    return best_k


def fit_steer_ratio_scalar(df_all: pd.DataFrame, L: float, lag_k: int,
                            delta_offset: float) -> float:
    """Fit a multiplicative scale factor s on delta (equiv. to dividing the
    steering ratio by s) that minimises yaw RMSE. Closed form:
        meas_shifted = (v/L) * s * (delta + offset)
        -> s = sum( (v/L*(delta+off)) * meas_s ) / sum( (v/L*(delta+off))^2 )
    """
    v = df_all["v_mps"].to_numpy()
    delta = df_all["delta_road_rad"].to_numpy() + delta_offset
    meas = df_all["yaw_rate_meas_rads"].to_numpy()
    meas_s = _shift(meas, -lag_k)  # shift meas backward by lag => equivalent
    x = (v / L) * delta
    s = float(np.sum(x * meas_s) / np.sum(x * x))
    return s


def fit_understeer(df_all: pd.DataFrame, L: float, lag_k: int,
                    delta_offset: float, steer_scale: float) -> float:
    """Fit K_us in: meas = v * delta_eff / (L + K_us * v^2)
    Equivalent to: meas * (L + K_us v^2) = v * delta_eff
                    K_us * (meas * v^2) = v*delta_eff - meas*L
                    K_us = sum( (meas*v^2) * (v*delta_eff - meas*L) )
                           / sum( (meas*v^2)^2 )
    """
    v = df_all["v_mps"].to_numpy()
    delta_eff = steer_scale * (df_all["delta_road_rad"].to_numpy() + delta_offset)
    meas = df_all["yaw_rate_meas_rads"].to_numpy()
    meas_s = _shift(meas, -lag_k)
    A = meas_s * v * v
    rhs = v * delta_eff - meas_s * L
    mask = (v > 2.0)
    K = float(np.sum(A[mask] * rhs[mask]) / np.sum(A[mask] ** 2))
    return K


# -------------------- pipeline ----------------------------------------------

def gather_per_platform(min_speed=2.0):
    """Gather per-platform DataFrames. Apply min-speed mask (data hygiene:
    yaw rate and a_lat under v<2 m/s are dominated by IMU bias + ground tilt
    and the KS model trivially predicts ~0 there). Returns (by_plat, by_plat_all)
    so we can report both filtered and unfiltered.
    """
    segs = list_segments()
    print(f"Found {len(segs)} sim CSVs")
    by_plat_all = {p: [] for p in PLATFORMS}
    by_plat = {p: [] for p in PLATFORMS}
    for plat, path in segs:
        try:
            df = load_segment(path)
            df["platform"] = plat
            df["seg_id"] = str(path.parent)
            by_plat_all[plat].append(df)
            df_mv = df[df["v_mps"] > min_speed].copy()
            if len(df_mv) > 50:
                by_plat[plat].append(df_mv)
        except Exception as e:
            print(f"skip {path}: {e}")
    return ({p: pd.concat(v, ignore_index=True) for p, v in by_plat.items()},
            {p: pd.concat(v, ignore_index=True) for p, v in by_plat_all.items()})


def predict_with_variant(df, plat, variant, fits):
    """Apply variant transformations to predict yaw rate."""
    L = PARAMS[plat]["L"]
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()

    off = fits[plat]["offset"] if variant >= 1 else 0.0
    lag = fits[plat]["lag"] if variant >= 2 else 0
    scale = fits[plat]["scale"] if variant >= 3 else 1.0
    K_us = fits[plat]["K_us"] if variant >= 4 else 0.0

    delta_eff = scale * (delta + off)
    pred = v * delta_eff / (L + K_us * v * v)
    if lag > 0:
        pred = _shift(pred, lag)
    return pred


def evaluate(by_plat):
    # 1) fit each platform's params on its full dataset
    fits = {}
    for plat, df in by_plat.items():
        L = PARAMS[plat]["L"]
        off = fit_delta_offset(df, L)
        lag = fit_time_lag(df, L, max_lag=25)
        scale = fit_steer_ratio_scalar(df, L, lag, off)
        K_us = fit_understeer(df, L, lag, off, scale)
        fits[plat] = dict(offset=off, lag=lag, scale=scale, K_us=K_us)
        print(f"  {plat}: offset={off:+.5f} rad ({np.degrees(off):+.3f} deg road-wheel)"
              f"   lag={lag} samples ({lag*20} ms)"
              f"   scale={scale:.4f} (i_s_eff={PARAMS[plat]['i_s']/scale:.3f})"
              f"   K_us={K_us:.5f}")

    # 2) compute metrics: each platform, each variant, plus 'all' aggregate
    rows = []
    for variant in range(5):
        all_preds, all_meas = [], []
        all_ay_pred, all_ay_meas = [], []
        for plat, df in by_plat.items():
            pred = predict_with_variant(df, plat, variant, fits)
            meas = df["yaw_rate_meas_rads"].to_numpy()
            err = rmse(pred, meas)
            v = df["v_mps"].to_numpy()
            ay_pred = v * pred
            ay_meas = df["a_lat_meas_mps2"].to_numpy()
            ay_err = rmse(ay_pred, ay_meas)
            rows.append(dict(variant=f"V{variant}", platform=plat,
                              yaw_rmse=err, ay_rmse=ay_err, N=len(df)))
            all_preds.append(pred); all_meas.append(meas)
            all_ay_pred.append(ay_pred); all_ay_meas.append(ay_meas)
        ap = np.concatenate(all_preds); am = np.concatenate(all_meas)
        ayp = np.concatenate(all_ay_pred); aym = np.concatenate(all_ay_meas)
        rows.append(dict(variant=f"V{variant}", platform="ALL",
                          yaw_rmse=rmse(ap, am), ay_rmse=rmse(ayp, aym),
                          N=len(ap)))

    # 3) single-effect attribution: apply ONLY each technique vs V0
    standalone_rows = []
    for tech in ["offset", "lag", "scale", "K_us"]:
        all_preds, all_meas = [], []
        for plat, df in by_plat.items():
            L = PARAMS[plat]["L"]
            v = df["v_mps"].to_numpy()
            delta = df["delta_road_rad"].to_numpy()
            off = fits[plat]["offset"] if tech == "offset" else 0.0
            lag = fits[plat]["lag"]    if tech == "lag"    else 0
            scale = fits[plat]["scale"] if tech == "scale" else 1.0
            K_us = fits[plat]["K_us"]   if tech == "K_us"  else 0.0
            delta_eff = scale * (delta + off)
            pred = v * delta_eff / (L + K_us * v * v)
            if lag > 0:
                pred = _shift(pred, lag)
            all_preds.append(pred)
            all_meas.append(df["yaw_rate_meas_rads"].to_numpy())
        ap = np.concatenate(all_preds); am = np.concatenate(all_meas)
        standalone_rows.append(dict(technique=tech, yaw_rmse=rmse(ap, am)))

    return fits, pd.DataFrame(rows), pd.DataFrame(standalone_rows)


def main():
    by_plat, by_plat_all = gather_per_platform(min_speed=2.0)
    print("Sample counts (v>2 m/s mask):")
    for p, df in by_plat.items():
        print(f"  {p}: {len(df):,} samples (of {len(by_plat_all[p]):,} total)")
    # First report baseline on all data vs moving-only, to separate data
    # hygiene from model improvement.
    print("\n=== Baseline (V0) on all data vs moving only ===")
    for p in PLATFORMS:
        df_all = by_plat_all[p]; df_mv = by_plat[p]
        L = PARAMS[p]["L"]
        pa = predict_yaw(df_all.v_mps.values, df_all.delta_road_rad.values, L)
        pm = predict_yaw(df_mv.v_mps.values, df_mv.delta_road_rad.values, L)
        print(f"  {p}: yaw RMSE all={rmse(pa, df_all.yaw_rate_meas_rads):.5f}  "
              f"moving={rmse(pm, df_mv.yaw_rate_meas_rads):.5f}")
        aya = df_all.v_mps.values * pa
        aym = df_mv.v_mps.values * pm
        print(f"       ay  RMSE all={rmse(aya, df_all.a_lat_meas_mps2):.4f}  "
              f"moving={rmse(aym, df_mv.a_lat_meas_mps2):.4f}")

    fits, res, standalone = evaluate(by_plat)
    print("\n=== Ladder (cumulative, moving-only) ===")
    pivot = res.pivot_table(index="variant", columns="platform",
                             values="yaw_rmse").round(5)
    print(pivot)
    print("\nLateral-acceleration RMSE (m/s^2):")
    pivot_ay = res.pivot_table(index="variant", columns="platform",
                                values="ay_rmse").round(4)
    print(pivot_ay)
    print("\n=== Standalone (each technique alone vs V0) ===")
    v0_all = res[(res.variant == "V0") & (res.platform == "ALL")].yaw_rmse.iloc[0]
    standalone["delta_vs_V0"] = v0_all - standalone["yaw_rmse"]
    standalone["pct_of_total"] = standalone["delta_vs_V0"]
    print(standalone.round(5))

    # write outputs
    res.to_csv(OUT / "metrics_ladder.csv", index=False)
    standalone.to_csv(OUT / "metrics_standalone.csv", index=False)
    with open(OUT / "fits.json", "w") as f:
        json.dump(fits, f, indent=2)
    print(f"\nWrote {OUT/'metrics_ladder.csv'}, {OUT/'metrics_standalone.csv'}, {OUT/'fits.json'}")


if __name__ == "__main__":
    main()
