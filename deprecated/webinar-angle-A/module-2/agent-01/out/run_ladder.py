"""Variant ladder for lateral-fidelity improvement on Ford platforms.

V0: baseline RMSE on yaw_rate_resid_rads as-is.
V1: per-segment bias removal of measured yaw rate (gyro bias estimate during
    straight-line driving). Improves straight-regime RMSE.
V2: V1 + low-pass smoothing of delta_road_rad input (Butterworth/Gaussian) to
    suppress 1-deg CAN quantization in delta_wheel_deg.
V3: V2 + time-lag alignment between predicted and measured yaw rate (xcorr).
V4: V3 + understeer-gradient correction: psi_dot_corrected = psi_dot_pred /
    (1 + K_us * v^2 / L), fit K_us by global least-squares on cornering points.

All variants share the same Ford segment-set and the same regime mask.
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-01")
DATA = ROOT / "data" / "sim" / "segments"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

# Use Mach-E and Lightning (Ford). Lock platform via param lookup.
sys.path.insert(0, str(ROOT / "code"))
from parameters import PARAM_BY_PLATFORM  # noqa: E402

FORD_PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]

DT = 0.02  # 50 Hz

def gather_segments():
    rows = []
    for plat in FORD_PLATFORMS:
        for csv in (DATA / plat).rglob("sim.csv"):
            rows.append((plat, csv))
    return rows


def regime_mask(df: pd.DataFrame):
    """Define three regimes from measured channels.

    straight: |delta_road| < 0.005 rad  AND  |a_lat_meas| < 0.5 m/s^2
    cornering steady: |delta_road| >= 0.005 AND |d(delta_road)/dt| < 0.02 rad/s
    cornering transient: rest of cornering
    """
    d = df["delta_road_rad"].to_numpy()
    a_lat = df["a_lat_meas_mps2"].to_numpy()
    ddot = np.gradient(d, DT)

    straight = (np.abs(d) < 0.005) & (np.abs(a_lat) < 0.5)
    cornering = ~straight
    transient = cornering & (np.abs(ddot) >= 0.02)
    steady = cornering & ~transient
    return straight, steady, transient


def rmse(x: np.ndarray):
    return float(np.sqrt(np.mean(x ** 2)))


def v0_residual(df: pd.DataFrame) -> np.ndarray:
    return df["yaw_rate_resid_rads"].to_numpy()


def v1_residual(df: pd.DataFrame) -> np.ndarray:
    """Per-segment bias removal: subtract gyro bias estimated during straight."""
    pred = df["yaw_rate_pred_rads"].to_numpy()
    meas = df["yaw_rate_meas_rads"].to_numpy()
    d = df["delta_road_rad"].to_numpy()
    a_lat = df["a_lat_meas_mps2"].to_numpy()
    # bias = mean(meas) during strict-straight stationary turning of wheel ~ 0
    straight = (np.abs(d) < 0.003) & (np.abs(a_lat) < 0.3)
    if straight.sum() < 20:
        bias = 0.0
    else:
        bias = float(np.mean(meas[straight]))
    return pred - (meas - bias)


def lowpass(x: np.ndarray, fc_hz=3.0, fs_hz=50.0, order=4):
    if len(x) < 3 * order:
        return x
    b, a = butter(order, fc_hz / (fs_hz / 2.0), btype="low")
    return filtfilt(b, a, x)


def v2_residual(df: pd.DataFrame, p) -> np.ndarray:
    """V1 + recompute prediction from low-pass-smoothed delta_road & v."""
    d = lowpass(df["delta_road_rad"].to_numpy(), fc_hz=3.0)
    v = df["v_mps"].to_numpy()
    pred_smooth = (v / p.L) * np.tan(d)
    meas = df["yaw_rate_meas_rads"].to_numpy()
    d_raw = df["delta_road_rad"].to_numpy()
    a_lat = df["a_lat_meas_mps2"].to_numpy()
    straight = (np.abs(d_raw) < 0.003) & (np.abs(a_lat) < 0.3)
    bias = float(np.mean(meas[straight])) if straight.sum() >= 20 else 0.0
    return pred_smooth - (meas - bias)


def estimate_lag(pred: np.ndarray, meas: np.ndarray, max_lag: int = 25):
    """Estimate integer-sample lag k such that pred[t] ~ meas[t+k] (meas lags pred)."""
    pred = pred - pred.mean()
    meas = meas - meas.mean()
    n = len(pred)
    best_k, best_c = 0, -np.inf
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            a = pred[: n - k]
            b = meas[k:]
        else:
            a = pred[-k:]
            b = meas[: n + k]
        if len(a) < 50:
            continue
        c = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        if c > best_c:
            best_c, best_k = c, k
    return best_k


def v3_residual(df: pd.DataFrame, p, global_lag: int) -> np.ndarray:
    """V2 + shift measurement by global_lag samples (meas leads/lags pred)."""
    d = lowpass(df["delta_road_rad"].to_numpy(), fc_hz=3.0)
    v = df["v_mps"].to_numpy()
    pred = (v / p.L) * np.tan(d)
    meas = df["yaw_rate_meas_rads"].to_numpy()
    d_raw = df["delta_road_rad"].to_numpy()
    a_lat = df["a_lat_meas_mps2"].to_numpy()
    straight = (np.abs(d_raw) < 0.003) & (np.abs(a_lat) < 0.3)
    bias = float(np.mean(meas[straight])) if straight.sum() >= 20 else 0.0
    meas_c = meas - bias

    k = global_lag
    n = len(pred)
    if k > 0:
        # shift meas earlier by k samples (predict is "ahead")
        pred_a = pred[: n - k]
        meas_a = meas_c[k:]
        resid = np.full(n, np.nan)
        resid[: n - k] = pred_a - meas_a
    elif k < 0:
        kk = -k
        pred_a = pred[kk:]
        meas_a = meas_c[: n - kk]
        resid = np.full(n, np.nan)
        resid[kk:] = pred_a - meas_a
    else:
        resid = pred - meas_c
    return resid


def fit_understeer_K(all_data, p_by_plat) -> dict:
    """Fit K_us per platform: psi_dot_meas ~ psi_dot_kin / (1 + K_us * v^2 / L)
    => psi_dot_kin / psi_dot_meas - 1 ~ K_us * v^2 / L  (in cornering, away from 0).
    Solve K_us by least squares on cornering steady points.
    """
    K_by = {}
    for plat in FORD_PLATFORMS:
        L = p_by_plat[plat].L
        X, Y = [], []
        for plat_i, df in all_data:
            if plat_i != plat:
                continue
            d = lowpass(df["delta_road_rad"].to_numpy(), fc_hz=3.0)
            v = df["v_mps"].to_numpy()
            psi_kin = (v / L) * np.tan(d)
            meas = df["yaw_rate_meas_rads"].to_numpy()
            d_raw = df["delta_road_rad"].to_numpy()
            a_lat = df["a_lat_meas_mps2"].to_numpy()
            straight = (np.abs(d_raw) < 0.003) & (np.abs(a_lat) < 0.3)
            bias = float(np.mean(meas[straight])) if straight.sum() >= 20 else 0.0
            meas_c = meas - bias

            # take cornering steady at moderate-high speed
            ddot = np.gradient(d, DT)
            mask = (np.abs(d_raw) >= 0.02) & (np.abs(ddot) < 0.02) & (v > 8) & (np.abs(meas_c) > 0.05)
            if mask.sum() < 50:
                continue
            ratio = psi_kin[mask] / meas_c[mask] - 1.0
            v2L = (v[mask] ** 2) / L
            X.append(v2L)
            Y.append(ratio)
        if not X:
            K_by[plat] = 0.0
            continue
        X = np.concatenate(X)
        Y = np.concatenate(Y)
        # Robust: trim 5/95 pct
        lo, hi = np.percentile(Y, [5, 95])
        sel = (Y >= lo) & (Y <= hi)
        X, Y = X[sel], Y[sel]
        K = float(np.dot(X, Y) / (np.dot(X, X) + 1e-9))
        K_by[plat] = K
    return K_by


def v4_residual(df: pd.DataFrame, p, global_lag: int, K_us: float) -> np.ndarray:
    d = lowpass(df["delta_road_rad"].to_numpy(), fc_hz=3.0)
    v = df["v_mps"].to_numpy()
    psi_kin = (v / p.L) * np.tan(d)
    psi_corr = psi_kin / (1.0 + K_us * (v ** 2) / p.L)
    meas = df["yaw_rate_meas_rads"].to_numpy()
    d_raw = df["delta_road_rad"].to_numpy()
    a_lat = df["a_lat_meas_mps2"].to_numpy()
    straight = (np.abs(d_raw) < 0.003) & (np.abs(a_lat) < 0.3)
    bias = float(np.mean(meas[straight])) if straight.sum() >= 20 else 0.0
    meas_c = meas - bias

    k = global_lag
    n = len(psi_corr)
    resid = np.full(n, np.nan)
    if k > 0:
        resid[: n - k] = psi_corr[: n - k] - meas_c[k:]
    elif k < 0:
        kk = -k
        resid[kk:] = psi_corr[kk:] - meas_c[: n - kk]
    else:
        resid = psi_corr - meas_c
    return resid


def regime_rmse(resid: np.ndarray, masks):
    out = []
    for m in masks:
        r = resid[m]
        r = r[np.isfinite(r)]
        out.append(rmse(r) if len(r) else float("nan"))
    return out


def main():
    segs = gather_segments()
    print(f"Found {len(segs)} Ford segments", flush=True)
    # Load all into memory (each is small)
    all_data = []
    for plat, path in segs:
        try:
            df = pd.read_csv(path)
        except Exception as e:
            print(f"skip {path}: {e}")
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        all_data.append((plat, df))
    print(f"Loaded {len(all_data)} segments", flush=True)

    # Estimate global lag using V2 predictions on a subsample of cornering segments
    lags = []
    for plat, df in all_data[:50]:
        p = PARAM_BY_PLATFORM[plat]
        d = lowpass(df["delta_road_rad"].to_numpy(), fc_hz=3.0)
        v = df["v_mps"].to_numpy()
        pred = (v / p.L) * np.tan(d)
        meas = df["yaw_rate_meas_rads"].to_numpy()
        if np.std(pred) < 0.01:
            continue
        lags.append(estimate_lag(pred, meas, max_lag=20))
    global_lag = int(np.median(lags)) if lags else 0
    print(f"Global lag (samples, 50 Hz): {global_lag} ({global_lag*DT*1000:.0f} ms)", flush=True)

    K_by = fit_understeer_K(all_data, PARAM_BY_PLATFORM)
    print(f"Understeer K_us: {K_by}", flush=True)

    # Accumulate per-regime squared-error sums across all segments
    variants = ["V0", "V1", "V2", "V3", "V4"]
    sq = {v: [[], [], []] for v in variants}  # [straight, steady, transient]
    sq_all = {v: [] for v in variants}

    for plat, df in all_data:
        p = PARAM_BY_PLATFORM[plat]
        masks = regime_mask(df)
        K = K_by[plat]
        residuals = {
            "V0": v0_residual(df),
            "V1": v1_residual(df),
            "V2": v2_residual(df, p),
            "V3": v3_residual(df, p, global_lag),
            "V4": v4_residual(df, p, global_lag, K),
        }
        for v, r in residuals.items():
            for i, m in enumerate(masks):
                rr = r[m]
                rr = rr[np.isfinite(rr)]
                sq[v][i].append(rr)
            rr_all = r[np.isfinite(r)]
            sq_all[v].append(rr_all)

    # Compute global RMSE (concat then sqrt(mean(x^2)))
    results = {}
    for v in variants:
        per_regime = []
        for i in range(3):
            arr = np.concatenate(sq[v][i]) if sq[v][i] else np.array([])
            per_regime.append(rmse(arr) if len(arr) else float("nan"))
        all_arr = np.concatenate(sq_all[v]) if sq_all[v] else np.array([])
        results[v] = {
            "straight": per_regime[0],
            "steady": per_regime[1],
            "transient": per_regime[2],
            "overall": rmse(all_arr) if len(all_arr) else float("nan"),
        }

    print("\n=== RMSE on yaw_rate (rad/s) ===")
    print(f"{'variant':<6} {'straight':>10} {'steady':>10} {'transient':>10} {'overall':>10}")
    for v in variants:
        r = results[v]
        print(f"{v:<6} {r['straight']:>10.5f} {r['steady']:>10.5f} {r['transient']:>10.5f} {r['overall']:>10.5f}")

    # Marginal drops (overall)
    overall = [results[v]["overall"] for v in variants]
    margs = [0.0] + [overall[i - 1] - overall[i] for i in range(1, len(variants))]
    total_drop = overall[0] - overall[-1]
    print(f"\nTotal RMSE drop: {total_drop:.5f}  ({100*total_drop/overall[0]:.1f}%)")
    for v, m in zip(variants, margs):
        print(f"  {v} marginal drop: {m:+.5f}")

    # Persist
    import json
    with open(OUT / "results.json", "w") as f:
        json.dump({
            "results": results,
            "global_lag_samples": global_lag,
            "global_lag_ms": global_lag * DT * 1000,
            "K_us": K_by,
            "n_segments": len(all_data),
            "platforms": FORD_PLATFORMS,
        }, f, indent=2)

    rows = []
    for v in variants:
        rows.append({"variant": v, **results[v]})
    pd.DataFrame(rows).to_csv(OUT / "results.csv", index=False)
    print(f"\nWrote {OUT/'results.json'} and {OUT/'results.csv'}")


if __name__ == "__main__":
    main()
