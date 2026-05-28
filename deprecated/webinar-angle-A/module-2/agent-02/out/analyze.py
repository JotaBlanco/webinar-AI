"""Lateral-fidelity variant ladder for KS yaw-rate residual on Ford Mach-E.

Speed-known operating contract: v and delta are clamped to measurement.
We do NOT touch v or delta from the CSV; we only post-process the prediction
or replace the prediction with a richer model (still consuming measured v, delta).

V0  baseline: yaw_rate_resid_rads as-is.
V1  per-segment bias removal on the residual.
V2  V1 + steering-to-yaw time alignment via cross-correlation lag.
V3  V2 + linear single-track yaw-rate prediction (replaces KS pred).
"""
from __future__ import annotations
import os, sys, glob, json
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-02"
sys.path.insert(0, os.path.join(ROOT, "code"))
from parameters import PARAM_BY_PLATFORM  # type: ignore

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
PARAM = PARAM_BY_PLATFORM[PLATFORM]
DT = 0.02
SEG_GLOB = os.path.join(ROOT, "data/sim/segments", PLATFORM, "*/*/*/sim.csv")

# Regime thresholds (rad/s on measured yaw rate, smoothed). Tunable; stated in report.
STRAIGHT_THR = 0.05   # |ψ̇_meas| < 0.05 rad/s -> straight
TRANSIENT_THR = 0.20  # |dψ̇_meas/dt| > 0.20 rad/s² -> transient


def load_segment(path):
    df = pd.read_csv(path)
    if len(df) < 100:
        return None
    return df


def classify(df):
    yr = df["yaw_rate_meas_rads"].values
    # smooth a bit for regime classification
    k = 5
    yr_s = np.convolve(yr, np.ones(k)/k, mode="same")
    dyr = np.gradient(yr_s, DT)
    straight = np.abs(yr_s) < STRAIGHT_THR
    transient = (~straight) & (np.abs(dyr) > TRANSIENT_THR)
    steady = (~straight) & (~transient)
    return {"straight": straight, "cornering_steady": steady, "cornering_transient": transient}


def rmse(x, mask=None):
    if mask is not None:
        x = x[mask]
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return np.nan
    return float(np.sqrt(np.mean(x**2)))


def linear_st_yawrate(v, delta, param):
    """Steady-state linear single-track yaw rate (bicycle model w/ tire stiffness).

    psi_dot_ss = v * delta / (L + K_us * v^2)
    K_us = (m / L) * (l_r / C_f - l_f / C_r)   (understeer gradient in [rad / (m/s^2)])
    """
    L = param.L
    m = param.m
    l_f = param.l_f
    l_r = param.l_r
    C_f = param.C_alpha_f
    C_r = param.C_alpha_r
    K_us = (m / L) * (l_r / C_f - l_f / C_r)
    den = L + K_us * v * v
    return v * delta / den


def best_lag(a, b, max_lag=15):
    """Find integer sample lag k that minimizes ||a - shift(b, k)||.

    Positive k means b is delayed relative to a (shift b forward).
    """
    best, best_k = np.inf, 0
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            aa = a[k:]
            bb = b[: len(a) - k]
        else:
            aa = a[: len(a) + k]
            bb = b[-k:]
        if len(aa) < 100:
            continue
        e = aa - bb
        s = np.sum(e * e)
        if s < best:
            best, best_k = s, k
    return best_k


def shift(arr, k):
    """Shift arr by k samples; fill edges with edge values."""
    out = np.empty_like(arr)
    if k == 0:
        return arr.copy()
    if k > 0:
        out[:k] = arr[0]
        out[k:] = arr[:-k]
    else:
        out[k:] = arr[-1]
        out[:k] = arr[-k:]
    return out


def main():
    paths = sorted(glob.glob(SEG_GLOB))
    # cap for runtime
    MAX_SEGS = 120
    paths = paths[:MAX_SEGS]
    print(f"Found {len(paths)} segments")

    all_v0, all_v1, all_v2, all_v3 = [], [], [], []
    all_masks = {"straight": [], "cornering_steady": [], "cornering_transient": []}
    seg_lags = []
    used = 0

    for p in paths:
        df = load_segment(p)
        if df is None:
            continue
        v = df["v_mps"].values
        delta = df["delta_road_rad"].values
        yr_meas = df["yaw_rate_meas_rads"].values
        yr_pred = df["yaw_rate_pred_rads"].values
        resid0 = df["yaw_rate_resid_rads"].values  # pred - meas
        # sanity: recompute matches
        # V0 residual
        v0 = resid0.copy()
        # V1 per-segment bias removal on residual
        bias = np.nanmean(v0)
        v1 = v0 - bias
        # V2 time-align: find lag minimizing ||shift(yr_pred, k) - yr_meas||
        lag = best_lag(yr_meas, yr_pred, max_lag=10)
        seg_lags.append(lag)
        yr_pred_aligned = shift(yr_pred, lag)
        v2_resid = yr_pred_aligned - yr_meas
        # re-remove bias after alignment
        v2 = v2_resid - np.nanmean(v2_resid)
        # V3 linear single-track yaw-rate, replacing pred
        yr_st = linear_st_yawrate(v, delta, PARAM)
        # time-align ST too
        lag_st = best_lag(yr_meas, yr_st, max_lag=10)
        yr_st_aligned = shift(yr_st, lag_st)
        v3_resid = yr_st_aligned - yr_meas
        v3 = v3_resid - np.nanmean(v3_resid)

        masks = classify(df)

        all_v0.append(v0)
        all_v1.append(v1)
        all_v2.append(v2)
        all_v3.append(v3)
        for k in all_masks:
            all_masks[k].append(masks[k])
        used += 1

    print(f"Used {used} segments")
    v0 = np.concatenate(all_v0)
    v1 = np.concatenate(all_v1)
    v2 = np.concatenate(all_v2)
    v3 = np.concatenate(all_v3)
    masks = {k: np.concatenate(v) for k, v in all_masks.items()}
    overall_mask = np.ones_like(v0, dtype=bool)

    rows = []
    for name, arr in [("V0_baseline", v0), ("V1_seg_bias", v1),
                       ("V2_time_align", v2), ("V3_linear_ST", v3)]:
        rows.append({
            "variant": name,
            "N": int(overall_mask.sum()),
            "RMSE_overall": rmse(arr),
            "RMSE_straight": rmse(arr, masks["straight"]),
            "RMSE_corner_steady": rmse(arr, masks["cornering_steady"]),
            "RMSE_corner_transient": rmse(arr, masks["cornering_transient"]),
        })
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))

    # marginal drops on overall RMSE (chain accounting)
    rmses = out["RMSE_overall"].tolist()
    drops = [None]
    for i in range(1, len(rmses)):
        drops.append(rmses[i-1] - rmses[i])
    out["marginal_drop"] = drops
    out["total_drop_vs_V0"] = [rmses[0] - r for r in rmses]

    out.to_csv(os.path.join(ROOT, "out/variant_ladder.csv"), index=False)

    # regime breakdown of mask sizes
    regime_counts = {k: int(m.sum()) for k, m in masks.items()}
    print("Regime counts:", regime_counts)

    # mean segment lag (in samples)
    print(f"Mean segment lag samples (yaw_meas vs yr_pred): {np.mean(seg_lags):.2f}  "
          f"(= {np.mean(seg_lags)*DT*1000:.0f} ms)")

    meta = {
        "platform": PLATFORM,
        "n_segments_used": used,
        "regime_counts": regime_counts,
        "mean_lag_samples_KS": float(np.mean(seg_lags)),
        "mean_lag_ms_KS": float(np.mean(seg_lags)) * DT * 1000,
        "straight_thr_yawrate_rads": STRAIGHT_THR,
        "transient_thr_yawaccel_rads2": TRANSIENT_THR,
        "K_us_machE_rad_per_mps2": (PARAM.m / PARAM.L) * (PARAM.l_r / PARAM.C_alpha_f - PARAM.l_f / PARAM.C_alpha_r),
    }
    with open(os.path.join(ROOT, "out/meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
