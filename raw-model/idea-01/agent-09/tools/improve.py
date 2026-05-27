"""Sweep improvements to the KS lateral yaw-rate prediction.

Approach: each Ford sim CSV already has the measured signals + the baseline KS
prediction. We can reconstruct alternative predictions cheaply (without re-decoding
rlogs) because KS yaw rate is a closed-form function of v and delta_road:

    psi_dot = (v / L) * tan(delta_road)

We try, on top of the baseline:
  V1: subtract a per-platform yaw-rate bias  b   (~ removing mean residual)
  V2: refit the steering-ratio scalar k     (delta_road *= k)
       i.e. equivalent to scaling i_s by 1/k
  V3: time-align the steering signal vs the measured yaw rate (sample-level lag)
  V4: linear understeer compensation
       psi_dot = ((v/L) * tan(delta)) / (1 + K_us * v^2)
  V5: full combined model

Attribution scheme: forward stepwise residual variance reduction (sum to total
RMSE^2 drop). We additionally show standalone effect of each.
"""
from __future__ import annotations
import glob, os, json
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-09/data/sim/segments"
PLATS = {
    "FORD_F_150_LIGHTNING_MK1": {"L": 3.70, "i_s": 16.9},
    "FORD_MUSTANG_MACH_E_MK1":  {"L": 2.984, "i_s": 17.0},
}
V_MIN = 2.0
MAX_LAG_SAMPLES = 25  # at 50 Hz that is 0.5 s

def load_all():
    """Return concat dataframes, per platform."""
    out = {}
    for plat in PLATS:
        frames = []
        for csv in sorted(glob.glob(os.path.join(ROOT, plat, "*", "*", "*", "sim.csv"))):
            try:
                df = pd.read_csv(csv, usecols=[
                    "t_s","delta_wheel_deg","delta_road_rad","v_mps",
                    "a_lat_meas_mps2","yaw_rate_meas_rads",
                    "yaw_rate_pred_rads","a_y_pred_mps2"
                ])
            except Exception:
                continue
            df["seg"] = csv
            frames.append(df)
        out[plat] = pd.concat(frames, ignore_index=True)
    return out

def rmse(r):
    return float(np.sqrt(np.mean(r**2)))

def mae(r):
    return float(np.mean(np.abs(r)))

def fit_bias(yaw_pred, yaw_meas):
    return float(np.mean(yaw_pred - yaw_meas))   # bias to subtract

def fit_scale_delta(v, delta_road, L, yaw_meas, w=None):
    """Find scalar k so that (v/L) * tan(k * delta_road) ~ yaw_meas.
    Approximate by linear least squares for tan-linearity (delta is small,
    median |delta_road| ~ 0.01 rad, so tan(x) ≈ x is accurate to <0.01%).
    => k * (v/L) * delta_road ≈ yaw_meas
    """
    x = (v / L) * delta_road
    if w is None:
        k = float(np.sum(x * yaw_meas) / np.sum(x * x))
    else:
        k = float(np.sum(w * x * yaw_meas) / np.sum(w * x * x))
    return k

def predict_ks(v, delta_road, L):
    return (v / L) * np.tan(delta_road)

def predict_ks_us(v, delta_road, L, K_us):
    return predict_ks(v, delta_road, L) / (1.0 + K_us * v * v)

def fit_us(v, delta_road, L, yaw_meas):
    """Bicycle understeer coefficient. Fit by ridge-free LS on linearised form.
    Let p0 = (v/L)*tan(delta). Then yaw_pred = p0 / (1 + K v^2).
    Equivalently yaw_pred + K v^2 yaw_pred = p0
    => K v^2 yaw_meas ≈ p0 - yaw_meas   (using measured as yaw_pred target)
    => K = sum(v^2 yaw_meas (p0 - yaw_meas)) / sum((v^2 yaw_meas)^2)
    """
    p0 = predict_ks(v, delta_road, L)
    rhs = p0 - yaw_meas
    x = v * v * yaw_meas
    denom = float(np.sum(x * x))
    if denom < 1e-12:
        return 0.0
    return float(np.sum(x * rhs) / denom)

def find_best_lag(v, delta_road, L, yaw_meas, max_lag=MAX_LAG_SAMPLES):
    """Shift delta_road by k samples; positive k = delta leads yaw by k samples
    (so we shift delta forward into the future to align with yaw).
    Try [-max_lag, max_lag], return shift with min residual RMS."""
    best_k, best_rmse = 0, None
    for k in range(-max_lag, max_lag + 1):
        if k > 0:
            d_shift = np.concatenate([delta_road[k:], np.full(k, delta_road[-1])])
            v_shift = v
            y_meas = yaw_meas
        elif k < 0:
            kk = -k
            d_shift = np.concatenate([np.full(kk, delta_road[0]), delta_road[:-kk]])
            v_shift = v
            y_meas = yaw_meas
        else:
            d_shift = delta_road
            v_shift = v
            y_meas = yaw_meas
        pred = predict_ks(v_shift, d_shift, L)
        r = rmse(pred - y_meas)
        if best_rmse is None or r < best_rmse:
            best_rmse, best_k = r, k
    return best_k, best_rmse

def apply_lag(arr, k):
    n = len(arr)
    if k == 0:
        return arr.copy()
    if k > 0:
        return np.concatenate([arr[k:], np.full(k, arr[-1])])
    kk = -k
    return np.concatenate([np.full(kk, arr[0]), arr[:-kk]])

def analyse():
    data = load_all()
    report = {"per_platform": {}, "pooled": {}}
    all_baseline_sse = 0.0
    all_n = 0
    all_v5_sse = 0.0

    pooled_fits = {}

    for plat, df in data.items():
        L = PLATS[plat]["L"]
        m = df["v_mps"].values > V_MIN
        v = df["v_mps"].values[m]
        d = df["delta_road_rad"].values[m]
        y = df["yaw_rate_meas_rads"].values[m]
        # Use a per-segment lag fit aggregated: estimate one global lag here (cheap)
        N = len(v)
        # subsample for lag search if huge
        if N > 200000:
            idx = np.random.default_rng(0).choice(N, 200000, replace=False)
            v_s, d_s, y_s = v[idx], d[idx], y[idx]
        else:
            v_s, d_s, y_s = v, d, y

        # Baseline yaw_pred from CSV column (should match formula)
        base_pred = predict_ks(v, d, L)
        base_res = base_pred - y
        base_rmse = rmse(base_res)
        base_mae = mae(base_res)
        base_bias = float(np.mean(base_res))
        base_sse = float(np.sum(base_res ** 2))

        # V1 — bias
        b = base_bias
        v1_pred = base_pred - b
        v1_rmse = rmse(v1_pred - y)

        # V2 — refit steering-ratio scalar (k applied to delta_road)
        k_ratio = fit_scale_delta(v, d, L, y)
        v2_pred = predict_ks(v, k_ratio * d, L)
        v2_rmse = rmse(v2_pred - y)

        # V3 — time alignment (sample-level)
        # Use a stratified shuffled subset for speed
        idx2 = np.random.default_rng(1).choice(N, min(N, 100000), replace=False)
        # Need to keep temporal order for lag — use full chrono signal per platform pool is meaningless.
        # Instead, estimate lag per-segment, then take median.
        per_seg_lags = []
        for seg, dseg in df.groupby("seg"):
            if len(dseg) < 500: continue
            mm = dseg["v_mps"].values > V_MIN
            if mm.sum() < 200: continue
            vv = dseg["v_mps"].values[mm]
            dd = dseg["delta_road_rad"].values[mm]
            yy = dseg["yaw_rate_meas_rads"].values[mm]
            # Only fit lag on segments with non-trivial steering
            if np.std(dd) < 1e-4: continue
            klag, _ = find_best_lag(vv, dd, L, yy, max_lag=20)
            per_seg_lags.append(klag)
        if per_seg_lags:
            lag_med = int(np.median(per_seg_lags))
        else:
            lag_med = 0

        # Apply lag at the per-segment level for fairness
        v3_resid_sq_sum = 0.0
        v3_n = 0
        for seg, dseg in df.groupby("seg"):
            mm = dseg["v_mps"].values > V_MIN
            if mm.sum() < 10: continue
            vv = dseg["v_mps"].values[mm]
            dd = dseg["delta_road_rad"].values[mm]
            yy = dseg["yaw_rate_meas_rads"].values[mm]
            d_lag = apply_lag(dd, lag_med)
            pred = predict_ks(vv, d_lag, L)
            v3_resid_sq_sum += float(np.sum((pred - yy) ** 2))
            v3_n += len(vv)
        v3_rmse = float(np.sqrt(v3_resid_sq_sum / v3_n))

        # V4 — understeer K_us
        K_us = fit_us(v, d, L, y)
        v4_pred = predict_ks_us(v, d, L, K_us)
        v4_rmse = rmse(v4_pred - y)

        # V5 — combined: time-align, then refit ratio, then bias, then understeer
        # do it per segment for the lag step
        v5_pred_all = []
        v5_y_all = []
        v5_v_all = []
        v5_d_all = []
        for seg, dseg in df.groupby("seg"):
            mm = dseg["v_mps"].values > V_MIN
            if mm.sum() < 10: continue
            vv = dseg["v_mps"].values[mm]
            dd = dseg["delta_road_rad"].values[mm]
            yy = dseg["yaw_rate_meas_rads"].values[mm]
            d_lag = apply_lag(dd, lag_med)
            v5_y_all.append(yy)
            v5_v_all.append(vv)
            v5_d_all.append(d_lag)
        vv = np.concatenate(v5_v_all)
        dd = np.concatenate(v5_d_all)
        yy = np.concatenate(v5_y_all)
        # refit ratio scalar on lag-aligned data
        k_ratio_c = fit_scale_delta(vv, dd, L, yy)
        # then understeer
        K_us_c = fit_us(vv, k_ratio_c * dd, L, yy)
        v5_pred = predict_ks_us(vv, k_ratio_c * dd, L, K_us_c)
        # then bias
        b_c = float(np.mean(v5_pred - yy))
        v5_pred = v5_pred - b_c
        v5_rmse = rmse(v5_pred - yy)
        v5_sse = float(np.sum((v5_pred - yy) ** 2))

        report["per_platform"][plat] = {
            "N": N,
            "baseline_rmse_rads": base_rmse,
            "baseline_mae_rads": base_mae,
            "baseline_bias_rads": base_bias,
            "V1_bias_only_rmse": v1_rmse,
            "V2_ratio_only_rmse": v2_rmse,
            "V3_lag_only_rmse": v3_rmse,
            "V4_us_only_rmse": v4_rmse,
            "V5_combined_rmse": v5_rmse,
            "fits": {
                "bias_rads": b,
                "ratio_scale_k": k_ratio,
                "implied_i_s": PLATS[plat]["i_s"] / k_ratio,
                "lag_samples_50Hz": lag_med,
                "K_us": K_us,
                "K_us_combined": K_us_c,
                "bias_combined_rads": b_c,
            },
        }
        all_baseline_sse += base_sse
        all_n += N
        all_v5_sse += v5_sse

    report["pooled"] = {
        "N": all_n,
        "baseline_rmse_rads": float(np.sqrt(all_baseline_sse / all_n)),
        "V5_combined_rmse": float(np.sqrt(all_v5_sse / all_n)),
        "improvement_pct": (1 - np.sqrt(all_v5_sse / all_baseline_sse)) * 100.0,
    }

    # ATTRIBUTION (per platform) — stepwise variance-reduction accounting
    # delta_var = baseline_mse - new_mse  (in rad²/s²)
    for plat, r in report["per_platform"].items():
        base_mse = r["baseline_rmse_rads"] ** 2
        v1 = r["V1_bias_only_rmse"] ** 2
        v2 = r["V2_ratio_only_rmse"] ** 2
        v3 = r["V3_lag_only_rmse"] ** 2
        v4 = r["V4_us_only_rmse"] ** 2
        v5 = r["V5_combined_rmse"] ** 2
        # Standalone contributions
        attr = {
            "standalone_mse_drop_rad2": {
                "V1_bias": base_mse - v1,
                "V2_ratio": base_mse - v2,
                "V3_lag": base_mse - v3,
                "V4_us": base_mse - v4,
            },
            "standalone_pct_drop_in_mse": {
                "V1_bias": (base_mse - v1)/base_mse * 100,
                "V2_ratio": (base_mse - v2)/base_mse * 100,
                "V3_lag": (base_mse - v3)/base_mse * 100,
                "V4_us": (base_mse - v4)/base_mse * 100,
            },
            "combined_mse_drop": base_mse - v5,
            "combined_pct_drop_in_mse": (base_mse - v5) / base_mse * 100,
            "combined_pct_drop_in_rmse": (1 - r["V5_combined_rmse"] / r["baseline_rmse_rads"]) * 100,
        }
        r["attribution"] = attr

    return report

if __name__ == "__main__":
    rep = analyse()
    out_path = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-09/out/improvement_report.json"
    with open(out_path, "w") as f:
        json.dump(rep, f, indent=2)
    print(json.dumps(rep, indent=2))
