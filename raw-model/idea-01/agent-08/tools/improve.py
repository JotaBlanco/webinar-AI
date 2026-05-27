"""Improvement ladder for KS lateral predictions on Ford segments.

Predictions are functions of (v_meas, delta_road, vehicle params). We do not
re-run rlog decoding — we re-derive the prediction from the columns already
present in sim.csv and compare to the same truth channels.

Ladder (each step builds on the previous):

  V0  Baseline KS:               psi_dot = v/L * tan(delta)
  V1  + drop bad-truth samples:  drop |a_lat_meas| > 20 m/s² (CAN-decode glitches)
  V2  + steering zero-offset:    delta_eff = delta - delta_0  (per-platform)
  V3  + understeer correction:   delta_eff = delta - delta_0 - K_us * v * psi_dot
      (linearised bicycle: psi_dot_ss = v/L * delta / (1 + K_us * v^2))
  V4  + steer-ratio scale:       delta_eff = k_sr * (delta - delta_0) - K_us*...
      (allow proportional bias on the steering channel)
  V5  + lag compensation:        align prediction to measured with best-fit dt

The understeer-corrected steady-state bicycle equation:

    psi_dot_ss(v, delta) = v / (L + K_us * v^2) * delta

For a_y prediction we also use: a_y = v * psi_dot.

Fit method: closed-form least squares for V2/V4 (linear), 1-D scalar minimise
for V3 (K_us) and V5 (lag). Fit per platform.

Attribution accounting: SEQUENTIAL drop in RMSE (V_k - V_{k-1}). Reported
fractions sum to 100% of the total RMSE reduction V0 -> V5.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-08")

L_BY_PLAT = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
}


def rmse(x):
    return float(np.sqrt(np.mean(x ** 2)))


def predict_ks(v, delta, L):
    return (v / L) * np.tan(delta)


def predict_bicycle_ss(v, delta, L, K_us):
    """Linearised steady-state bicycle yaw rate.

    psi_dot = v / (L + K_us * v^2) * delta
    K_us has units s²/m  (often called the understeer gradient times g).
    """
    return v / (L + K_us * v * v) * delta


def metrics_block(meas, pred, label=""):
    r = meas - pred
    out = {
        "label": label,
        "n": int(len(meas)),
        "rmse": rmse(r),
        "rmse_deg_s": float(np.degrees(rmse(r))),
        "bias": float(np.mean(r)),
        "bias_deg_s": float(np.degrees(np.mean(r))),
    }
    if np.var(meas) > 0:
        out["r2"] = 1.0 - np.var(r) / np.var(meas)
    return out


def fit_offset(meas, v, delta, L):
    """Best constant delta-offset: minimise RMSE of yaw_meas - v/L*tan(delta-d0).
    For small offsets, equivalent to linear fit of (meas - v/L*tan(delta))
    against d(v/L*tan(delta))/dd evaluated at delta. Use scalar minimise.
    """
    def loss(d0):
        return rmse(meas - (v / L) * np.tan(delta - d0))
    res = minimize_scalar(loss, bounds=(-0.05, 0.05), method="bounded",
                          options={"xatol": 1e-6})
    return res.x


def fit_kus(meas, v, delta, L):
    """Fit understeer gradient K_us (s²/m) by minimising RMSE."""
    def loss(K):
        return rmse(meas - predict_bicycle_ss(v, delta, L, K))
    res = minimize_scalar(loss, bounds=(-0.02, 0.05), method="bounded",
                          options={"xatol": 1e-7})
    return res.x


def fit_kus_with_offset(meas, v, delta, L, d0):
    """Same as fit_kus but with steering offset pre-applied."""
    de = delta - d0
    def loss(K):
        return rmse(meas - predict_bicycle_ss(v, de, L, K))
    res = minimize_scalar(loss, bounds=(-0.02, 0.05), method="bounded",
                          options={"xatol": 1e-7})
    return res.x


def fit_scale_offset_kus(meas, v, delta, L):
    """Fit (k_sr, d0, K_us) jointly. Nested: outer over K_us, inner closed-form
    over (k_sr, d0) since for fixed K_us:
        pred = v/(L+K*v^2) * (k_sr*delta - d0_eff)
    where d0_eff = k_sr*d0. This is linear in (k_sr, d0_eff)."""
    def loss(K):
        c = v / (L + K * v * v)              # (N,)
        X = np.column_stack([c * delta, -c])  # cols for k_sr, d0_eff
        # Least squares meas ~ X @ [k_sr, d0_eff]
        coef, *_ = np.linalg.lstsq(X, meas, rcond=None)
        pred = X @ coef
        return rmse(meas - pred)
    res = minimize_scalar(loss, bounds=(-0.02, 0.05), method="bounded",
                          options={"xatol": 1e-7})
    K = res.x
    c = v / (L + K * v * v)
    X = np.column_stack([c * delta, -c])
    coef, *_ = np.linalg.lstsq(X, meas, rcond=None)
    k_sr, d0_eff = float(coef[0]), float(coef[1])
    d0 = d0_eff / k_sr if abs(k_sr) > 1e-9 else 0.0
    return k_sr, d0, K


def fit_lag(meas, pred, dt=0.02, max_lag_s=0.5):
    """Find integer-sample shift of pred that minimises RMSE vs meas."""
    n_max = int(max_lag_s / dt)
    best_rmse = rmse(meas - pred)
    best_lag = 0
    for lag in range(-n_max, n_max + 1):
        if lag == 0:
            r = meas - pred
        elif lag > 0:
            # predicted leads measured: shift pred forward by `lag` samples
            r = meas[lag:] - pred[:-lag]
        else:
            r = meas[:lag] - pred[-lag:]
        e = rmse(r)
        if e < best_rmse:
            best_rmse = e
            best_lag = lag
    return best_lag, best_rmse


def run_platform(df_plat, plat):
    L = L_BY_PLAT[plat]
    out = {}

    # V0: baseline (as written to CSV)
    meas = df_plat["yaw_rate_meas_rads"].values
    pred0 = df_plat["yaw_rate_pred_rads"].values  # = v/L * tan(delta) already
    out["V0_baseline"] = metrics_block(meas, pred0, "V0")

    # V1: drop bad-truth samples (|a_lat|>20)
    mask = df_plat["a_lat_meas_mps2"].abs() < 20.0
    dfc = df_plat[mask].copy()
    v = dfc["v_mps"].values
    delta = dfc["delta_road_rad"].values
    meas_c = dfc["yaw_rate_meas_rads"].values
    pred_c = (v / L) * np.tan(delta)
    out["V1_clean"] = metrics_block(meas_c, pred_c, "V1")

    # V2: steering zero-offset
    d0 = fit_offset(meas_c, v, delta, L)
    pred2 = (v / L) * np.tan(delta - d0)
    out["V2_offset"] = metrics_block(meas_c, pred2, "V2")
    out["V2_offset"]["fit_d0_rad"] = float(d0)
    out["V2_offset"]["fit_d0_deg_wheel"] = float(np.degrees(d0))

    # V3: + understeer correction (steady-state bicycle)
    K_us = fit_kus_with_offset(meas_c, v, delta, L, d0)
    pred3 = predict_bicycle_ss(v, delta - d0, L, K_us)
    out["V3_understeer"] = metrics_block(meas_c, pred3, "V3")
    out["V3_understeer"]["fit_K_us"] = float(K_us)

    # V4: + steer-ratio scale (joint fit of k_sr, d0, K_us)
    k_sr, d0_j, K_j = fit_scale_offset_kus(meas_c, v, delta, L)
    pred4 = predict_bicycle_ss(v, k_sr * delta - k_sr * d0_j, L, K_j)
    out["V4_scale"] = metrics_block(meas_c, pred4, "V4")
    out["V4_scale"]["fit_k_sr"] = float(k_sr)
    out["V4_scale"]["fit_d0_rad"] = float(d0_j)
    out["V4_scale"]["fit_K_us"] = float(K_j)

    # V5: + lag compensation (per platform integer-sample shift)
    best_lag, lag_rmse = fit_lag(meas_c, pred4, dt=0.02, max_lag_s=0.30)
    out["V5_lag"] = {
        "label": "V5",
        "n": int(len(meas_c) - abs(best_lag)),
        "rmse": float(lag_rmse),
        "rmse_deg_s": float(np.degrees(lag_rmse)),
        "fit_lag_samples": int(best_lag),
        "fit_lag_ms": int(best_lag * 20),
    }
    return out


def attribution(out):
    """Sequential RMSE drops V_k -> V_{k+1}.

    V0 -> V1 cleaning is reported separately as 'data cleanup' since it is not
    a model change. Attribution percentages reported among the MODEL steps
    (V1 -> V5).
    """
    rmses = {
        "V0_baseline": out["V0_baseline"]["rmse"],
        "V1_clean":    out["V1_clean"]["rmse"],
        "V2_offset":   out["V2_offset"]["rmse"],
        "V3_understeer": out["V3_understeer"]["rmse"],
        "V4_scale":    out["V4_scale"]["rmse"],
        "V5_lag":      out["V5_lag"]["rmse"],
    }
    steps = list(rmses.keys())
    drops = {}
    for a, b in zip(steps[:-1], steps[1:]):
        drops[f"{a} -> {b}"] = rmses[a] - rmses[b]
    model_total = rmses["V1_clean"] - rmses["V5_lag"]
    pct = {}
    for k, v in drops.items():
        if k == "V0_baseline -> V1_clean":
            pct[k] = "(data-cleanup, not model)"
        else:
            pct[k] = f"{100 * v / model_total:.1f}%" if model_total > 0 else "n/a"
    return rmses, drops, pct


def main():
    print("Loading...")
    df = pd.read_parquet(ROOT / "out" / "all_ford.parquet")
    print(f"{len(df)} samples total")

    all_results = {}
    for plat in L_BY_PLAT:
        print(f"\n========= {plat} =========")
        dfp = df[df["__seg"].str.startswith(plat)].reset_index(drop=True)
        print(f"  {len(dfp)} samples")
        out = run_platform(dfp, plat)
        all_results[plat] = out
        for k, v in out.items():
            extras = {kk: vv for kk, vv in v.items()
                      if kk not in ("label", "n", "rmse", "rmse_deg_s", "bias",
                                    "bias_deg_s", "r2")}
            print(f"  {k}: RMSE={v['rmse']:.5f} rad/s "
                  f"({v.get('rmse_deg_s', float('nan')):.3f} deg/s)  "
                  f"{extras}")
        rmses, drops, pct = attribution(out)
        print("\n  Sequential RMSE drops (deg/s) and % of MODEL-improvement total:")
        for k, v in drops.items():
            print(f"    {k}: drop = {np.degrees(v):.4f} deg/s  share={pct[k]}")
        total_drop = rmses['V0_baseline'] - rmses['V5_lag']
        print(f"  TOTAL drop V0 -> V5: {np.degrees(total_drop):.4f} deg/s "
              f"({100*total_drop/rmses['V0_baseline']:.1f}% of baseline RMSE)")

    # ===== COMBINED across both Ford platforms =====
    print("\n\n========= COMBINED (both Fords pooled, per-platform fits applied) =========")
    parts = []
    for plat in L_BY_PLAT:
        dfp = df[df["__seg"].str.startswith(plat)].reset_index(drop=True)
        mask = dfp["a_lat_meas_mps2"].abs() < 20.0
        dfc = dfp[mask].copy()
        L = L_BY_PLAT[plat]
        v = dfc["v_mps"].values
        delta = dfc["delta_road_rad"].values
        meas_c = dfc["yaw_rate_meas_rads"].values

        # apply per-plat fitted V4 then apply per-plat V5 lag
        d0 = all_results[plat]["V2_offset"]["fit_d0_rad"]
        k_sr = all_results[plat]["V4_scale"]["fit_k_sr"]
        d0_j = all_results[plat]["V4_scale"]["fit_d0_rad"]
        K_j = all_results[plat]["V4_scale"]["fit_K_us"]
        lag = all_results[plat]["V5_lag"]["fit_lag_samples"]

        pred0 = (v / L) * np.tan(delta)
        pred1 = pred0
        pred2 = (v / L) * np.tan(delta - d0)
        pred3 = predict_bicycle_ss(v, delta - d0,
                                   L, all_results[plat]["V3_understeer"]["fit_K_us"])
        pred4 = predict_bicycle_ss(v, k_sr * (delta - d0_j), L, K_j)
        # lag align
        if lag > 0:
            m5 = meas_c[lag:]
            p5 = pred4[:-lag]
        elif lag < 0:
            m5 = meas_c[:lag]
            p5 = pred4[-lag:]
        else:
            m5 = meas_c
            p5 = pred4
        parts.append({
            "plat": plat, "L": L,
            "meas": meas_c, "v0": pred0, "v1": pred1, "v2": pred2,
            "v3": pred3, "v4": pred4, "meas_l": m5, "v5": p5,
        })

    # Raw baseline across BOTH (using uncleaned data so it matches reported headline)
    full = df
    raw0 = (full["v_mps"].values / np.where(full["__seg"].str.startswith("FORD_F_150_LIGHTNING_MK1"), 3.70, 2.984)) * np.tan(full["delta_road_rad"].values)
    raw_rmse = rmse(full["yaw_rate_meas_rads"].values - raw0)
    print(f"V0 RAW pooled (uncleaned): RMSE = {raw_rmse:.5f} rad/s "
          f"= {np.degrees(raw_rmse):.4f} deg/s")

    def cat(key):
        return np.concatenate([p[key] for p in parts])
    meas_full = cat("meas")
    print(f"V1 CLEANED pooled:        RMSE = {rmse(meas_full - cat('v1')):.5f} rad/s "
          f"= {np.degrees(rmse(meas_full - cat('v1'))):.4f} deg/s")
    print(f"V2 + offset:              RMSE = {rmse(meas_full - cat('v2')):.5f} rad/s "
          f"= {np.degrees(rmse(meas_full - cat('v2'))):.4f} deg/s")
    print(f"V3 + understeer:          RMSE = {rmse(meas_full - cat('v3')):.5f} rad/s "
          f"= {np.degrees(rmse(meas_full - cat('v3'))):.4f} deg/s")
    print(f"V4 + scale-joint:         RMSE = {rmse(meas_full - cat('v4')):.5f} rad/s "
          f"= {np.degrees(rmse(meas_full - cat('v4'))):.4f} deg/s")
    meas_l = np.concatenate([p["meas_l"] for p in parts])
    v5     = np.concatenate([p["v5"]     for p in parts])
    print(f"V5 + lag align:           RMSE = {rmse(meas_l - v5):.5f} rad/s "
          f"= {np.degrees(rmse(meas_l - v5)):.4f} deg/s")

    # SEQUENTIAL attribution (pooled)
    print("\nSEQUENTIAL attribution (pooled), % of total V1->V5 improvement:")
    rmses = {
        "V0_baseline_raw": raw_rmse,
        "V1_clean":        rmse(meas_full - cat("v1")),
        "V2_offset":       rmse(meas_full - cat("v2")),
        "V3_understeer":   rmse(meas_full - cat("v3")),
        "V4_scale":        rmse(meas_full - cat("v4")),
        "V5_lag":          rmse(meas_l - v5),
    }
    keys = list(rmses.keys())
    model_total = rmses["V1_clean"] - rmses["V5_lag"]
    print(f"  Data-cleanup V0->V1: drop = {np.degrees(rmses['V0_baseline_raw']-rmses['V1_clean']):.4f} deg/s "
          f"({100*(rmses['V0_baseline_raw']-rmses['V1_clean'])/rmses['V0_baseline_raw']:.2f}% of baseline)")
    for a, b in zip(keys[1:-1], keys[2:]):
        drop = rmses[a] - rmses[b]
        print(f"  {a} -> {b}: drop = {np.degrees(drop):.4f} deg/s  "
              f"share = {100*drop/model_total:.1f}% of model improvement")

    print("\nFINAL HEADLINE:")
    print(f"  Baseline RMSE  = {np.degrees(rmses['V0_baseline_raw']):.4f} deg/s")
    print(f"  Final RMSE     = {np.degrees(rmses['V5_lag']):.4f} deg/s")
    total = rmses['V0_baseline_raw'] - rmses['V5_lag']
    print(f"  Total reduction = {np.degrees(total):.4f} deg/s "
          f"({100*total/rmses['V0_baseline_raw']:.1f}% of baseline)")


if __name__ == "__main__":
    main()
