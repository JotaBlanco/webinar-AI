"""Lateral fidelity variant ladder for FORD_MUSTANG_MACH_E_MK1.

Scoring: RMSE of yaw-rate residual (rad/s), strict marginal accounting
across V0 -> V_last. Per-platform fit only.
"""
from __future__ import annotations
import glob, os, sys
import numpy as np
import pandas as pd

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI"
SIM_GLOB = f"{ROOT}/data/sim/segments/{PLATFORM}/*/*/*/sim.csv"
OUT_DIR = f"{ROOT}/webinar-angle-C/module-2/agent-05/out"
os.makedirs(OUT_DIR, exist_ok=True)

def load_all() -> list[pd.DataFrame]:
    paths = sorted(glob.glob(SIM_GLOB))
    dfs = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            if "yaw_rate_meas_rads" not in df.columns:
                continue
            df = df.dropna(subset=["yaw_rate_meas_rads", "yaw_rate_pred_rads",
                                   "delta_road_rad", "v_mps"])
            if len(df) < 50:
                continue
            df["__seg__"] = p
            dfs.append(df)
        except Exception as e:
            print(f"skip {p}: {e}", file=sys.stderr)
    return dfs

def regime_mask(df: pd.DataFrame):
    yr = df["yaw_rate_meas_rads"].to_numpy()
    abs_yr = np.abs(yr)
    # straight: low yaw-rate
    straight = abs_yr < 0.03
    # steady cornering: yaw-rate elevated AND low derivative
    dyr = np.gradient(yr, 0.02)
    steady = (abs_yr >= 0.03) & (np.abs(dyr) < 0.10)
    transient = (abs_yr >= 0.03) & (np.abs(dyr) >= 0.10)
    return {"straight": straight, "steady_corner": steady,
            "transient_corner": transient, "all": np.ones_like(straight, dtype=bool)}

def rmse(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    return float(np.sqrt(np.mean(x ** 2)))

def score(pred: np.ndarray, meas: np.ndarray, regimes: dict, mask_extra=None) -> dict:
    resid = pred - meas
    out = {}
    for name, m in regimes.items():
        if mask_extra is not None:
            m = m & mask_extra
        out[name] = rmse(resid[m])
    return out

def main():
    dfs = load_all()
    print(f"Loaded {len(dfs)} segments from {PLATFORM}")

    # Concatenate (track segment ids for any per-segment work, but we fit per-platform).
    big = pd.concat(dfs, ignore_index=True)
    regs = regime_mask(big)

    yr_meas = big["yaw_rate_meas_rads"].to_numpy()
    yr_pred_v0 = big["yaw_rate_pred_rads"].to_numpy()
    delta = big["delta_road_rad"].to_numpy()
    v = big["v_mps"].to_numpy()

    # Sanity: ISO 8855 sign check on cornering samples
    corner = regs["steady_corner"] | regs["transient_corner"]
    if corner.sum() > 100:
        c = np.corrcoef(delta[corner], yr_meas[corner])[0, 1]
        print(f"corr(delta_road, yaw_rate_meas) on cornering = {c:+.3f} (expect >0)")

    results = []

    # ---- V0: baseline residual as-is ----
    s = score(yr_pred_v0, yr_meas, regs)
    results.append(("V0_baseline", s, "per-platform (no fit)"))

    # ---- Interleaved train/test split (every 5th -> test) ----
    idx = np.arange(len(big))
    test_mask = (idx % 5) == 0
    train_mask = ~test_mask

    # ---- V1: per-platform constant bias removal (yaw-rate) ----
    bias = float(np.median((yr_pred_v0 - yr_meas)[train_mask]))
    yr_pred_v1 = yr_pred_v0 - bias
    s = score(yr_pred_v1, yr_meas, regs, mask_extra=test_mask)
    s_all_train_test = score(yr_pred_v1, yr_meas, regs)  # full for reporting only
    results.append((f"V1_bias_removal (b={bias:+.5f} rad/s)", s, "per-platform fit, test-only"))

    # ---- V2: per-platform steer-ratio / steer-gain calibration ----
    # yaw_rate ~ (v / L) * (delta_road * k). Fit k on train, ignoring tan() for small delta.
    # k that minimises RMSE of (k * yr_pred_v1 - yr_meas) over cornering+train.
    fit_mask = train_mask & corner
    # Use original V0 pred (linear in delta) -> after bias removal, find scalar gain
    a = yr_pred_v1[fit_mask]
    b_ = yr_meas[fit_mask]
    k = float(np.dot(a, b_) / np.dot(a, a))
    yr_pred_v2 = k * yr_pred_v1
    s = score(yr_pred_v2, yr_meas, regs, mask_extra=test_mask)
    results.append((f"V2_steer_gain (k={k:.4f})", s, "per-platform fit, test-only"))

    # ---- V3: per-platform constant lag alignment ----
    # Choose integer lag (samples at 50 Hz) that minimises RMSE on train cornering.
    # pred leads meas if positive lag means shift pred forward (pred[t+L] vs meas[t]).
    best_lag = 0
    best_rmse = float("inf")
    for lag in range(-10, 11):  # -200ms .. +200ms
        if lag >= 0:
            p_shift = yr_pred_v2[: len(yr_pred_v2) - lag]
            m_shift = yr_meas[lag:]
        else:
            p_shift = yr_pred_v2[-lag:]
            m_shift = yr_meas[: len(yr_meas) + lag]
        # restrict to train+corner aligned subset (approx — use overall RMSE on cornering)
        # Build corner mask aligned to shifted length
        n = len(p_shift)
        if lag >= 0:
            cm = corner[: n] & train_mask[: n]
        else:
            cm = corner[-lag : -lag + n] & train_mask[-lag : -lag + n]
        r = rmse(p_shift[cm] - m_shift[cm])
        if r < best_rmse:
            best_rmse = r
            best_lag = lag
    # Apply best_lag to full series via pandas shift then realign for scoring on test
    s_pred = pd.Series(yr_pred_v2)
    yr_pred_v3 = s_pred.shift(-best_lag).to_numpy()  # shift so that pred[t] -> pred[t+lag]
    valid = np.isfinite(yr_pred_v3)
    # Score on test_mask & valid
    s = score(np.where(valid, yr_pred_v3, np.nan), yr_meas, regs, mask_extra=test_mask & valid)
    results.append((f"V3_lag_align (lag={best_lag*20:+d}ms)", s, "per-platform fit, test-only"))

    # Save CSV summary
    rows = []
    for name, s, lbl in results:
        rows.append({"variant": name, "label": lbl, **{f"rmse_{k}": v for k, v in s.items()}})
    pd.DataFrame(rows).to_csv(f"{OUT_DIR}/variants_summary.csv", index=False)

    # Print summary
    print("\n=== Variant ladder (RMSE of yaw-rate residual, rad/s) — test split ===")
    print(f"{'variant':<45} {'all':>9} {'straight':>10} {'steady':>10} {'transient':>11}")
    for name, s, lbl in results:
        print(f"{name:<45} {s['all']:>9.5f} {s['straight']:>10.5f} {s['steady_corner']:>10.5f} {s['transient_corner']:>11.5f}  [{lbl}]")

    # Strict marginal improvement vs V0
    v0_all = results[0][1]["all"]
    print(f"\nStrict marginal vs V0 (all, rad/s):")
    prev = v0_all
    for name, s, _ in results[1:]:
        delta = prev - s["all"]
        pct = 100 * delta / v0_all
        print(f"  {name:<45}  Δ={delta:+.5f}  ({pct:+.2f}% of V0)")
        prev = s["all"]
    final = results[-1][1]["all"]
    print(f"Total V0 -> V_last: {v0_all:.5f} -> {final:.5f}  ({100*(v0_all-final)/v0_all:+.2f}%)")

if __name__ == "__main__":
    main()
