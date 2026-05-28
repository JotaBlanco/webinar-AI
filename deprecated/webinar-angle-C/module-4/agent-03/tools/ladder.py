#!/usr/bin/env python3
"""Variant ladder for lateral yaw-rate fidelity on a Ford platform.

V0: baseline residual as-is (yaw_rate_resid_rads).
V1: steering bias correction (fit constant delta_offset on straight samples, per-platform).
V2: V1 + understeer gradient (linear bicycle: psi_dot = v*delta_corr / (L + K_us*v^2), fit K_us, per-platform).
V3: V2 + lag alignment (shift pred by k samples, fit integer k in [-10, 10], per-platform).

Discipline:
  * Interleaved 4/1 train/test split (every 5th sample -> test).
  * All RMSE numbers reported are HELD-OUT TEST RMSE.
  * Same segment set, same regime mask, additive monotone.
  * Per-platform fits.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from parameters import PARAM_BY_PLATFORM  # noqa: E402

REGIME_DELTA_THR = 0.01
REGIME_DDELTA_THR = 0.05


def regime_mask(df: pd.DataFrame) -> pd.Series:
    delta = df["delta_road_rad"].to_numpy()
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 0.02, dt)
    ddelta = np.gradient(delta) / dt
    out = np.full(len(df), "transient", dtype=object)
    out[np.abs(delta) < REGIME_DELTA_THR] = "straight"
    steady = (np.abs(delta) >= REGIME_DELTA_THR) & (np.abs(ddelta) < REGIME_DDELTA_THR)
    out[steady] = "steady"
    return pd.Series(out, index=df.index, name="regime")


def rmse(arr) -> float:
    s = np.asarray(arr, dtype=float)
    s = s[np.isfinite(s)]
    return float(np.sqrt(np.mean(s ** 2))) if s.size else float("nan")


def load_platform(platform: str) -> pd.DataFrame:
    root = Path("data/sim/segments") / platform
    csvs = sorted(root.rglob("sim.csv"))
    frames = []
    for i, p in enumerate(csvs):
        df = pd.read_csv(p)
        df["__seg__"] = i
        frames.append(df)
    big = pd.concat(frames, ignore_index=True)
    big["__regime__"] = regime_mask(big)
    # Interleaved test mask: every 5th sample
    big["__test__"] = (np.arange(len(big)) % 5 == 0)
    return big


def report_rmse(label: str, resid: np.ndarray, regime: pd.Series, test_mask: np.ndarray):
    """Return dict of RMSE on TEST mask: overall + per regime."""
    out = {"label": label}
    sel = test_mask & np.isfinite(resid)
    out["overall"] = rmse(resid[sel])
    for r in ("straight", "steady", "transient"):
        m = sel & (regime.to_numpy() == r)
        out[r] = rmse(resid[m])
    return out


def fit_delta_offset(df: pd.DataFrame) -> float:
    """Fit steering offset on STRAIGHT-DRIVING train samples.
    On straights, expected yaw rate ~ 0; residual should mean ~ 0.
    Instead we fit offset s.t. (v/L)*tan(delta+off) matches meas yaw rate
    using small-angle linearisation on near-straight: psi_dot_meas ~ (v/L)*(delta+off)
    -> off = mean( (psi_dot_meas * L / v) - delta ) on train+straight samples.
    """
    train = ~df["__test__"].to_numpy()
    straight = df["__regime__"].to_numpy() == "straight"
    m = train & straight & (df["v_mps"].to_numpy() > 3.0)
    L = df["__L__"].iloc[0]
    delta = df["delta_road_rad"].to_numpy()[m]
    v = df["v_mps"].to_numpy()[m]
    psi_dot_meas = df["yaw_rate_meas_rads"].to_numpy()[m]
    # psi_dot_meas ~ (v/L)*(delta + off)  =>  off = (psi_dot_meas*L/v) - delta
    est = (psi_dot_meas * L / v) - delta
    return float(np.median(est))


def fit_k_us(df: pd.DataFrame, delta_off: float) -> float:
    """Fit understeer gradient K_us via least squares on TRAIN cornering samples.
    Model: psi_dot = v*delta_c / (L + K_us*v^2),   delta_c = delta + off
    Rearrange: v*delta_c/psi_dot - L = K_us * v^2
    Fit K_us = mean((v*delta_c/psi_dot - L) / v^2) weighted by |psi_dot|.
    Use only meaningful yaw-rate samples.
    """
    L = df["__L__"].iloc[0]
    train = ~df["__test__"].to_numpy()
    cornering = df["__regime__"].to_numpy() != "straight"
    psi_dot_meas = df["yaw_rate_meas_rads"].to_numpy()
    delta_c = df["delta_road_rad"].to_numpy() + delta_off
    v = df["v_mps"].to_numpy()
    m = (
        train & cornering
        & (np.abs(psi_dot_meas) > 0.02)
        & (v > 5.0)
        & (np.sign(psi_dot_meas) == np.sign(delta_c))
    )
    # Weighted least squares: minimise sum w_i (psi_dot_pred - psi_dot_meas)^2
    # parametrise psi_dot_pred = v*delta_c / (L + K_us*v^2)
    # Closed-form via 1D grid search on K_us in [-0.005, 0.020]
    K_grid = np.linspace(-0.005, 0.02, 251)
    best_K = 0.0
    best_rmse = np.inf
    psi_m = psi_dot_meas[m]
    dc = delta_c[m]
    vv = v[m]
    for K in K_grid:
        denom = L + K * vv * vv
        pred = vv * dc / denom
        e = pred - psi_m
        r = float(np.sqrt(np.mean(e * e)))
        if r < best_rmse:
            best_rmse = r
            best_K = float(K)
    return best_K


def fit_lag(df: pd.DataFrame, pred_v2: np.ndarray) -> int:
    """Fit an integer sample lag (in [-10, 10]) that minimises train RMSE."""
    train = ~df["__test__"].to_numpy()
    meas = df["yaw_rate_meas_rads"].to_numpy()
    best_k = 0
    best = np.inf
    for k in range(-10, 11):
        shifted = np.roll(pred_v2, k)
        # Invalidate wrapped region
        n = len(shifted)
        valid = np.ones(n, dtype=bool)
        if k > 0:
            valid[:k] = False
        elif k < 0:
            valid[k:] = False
        m = train & valid
        e = shifted[m] - meas[m]
        r = float(np.sqrt(np.mean(e * e)))
        if r < best:
            best = r
            best_k = k
    return int(best_k)


def run_platform(platform: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {platform} ===")
    df = load_platform(platform)
    p = PARAM_BY_PLATFORM[platform]
    df["__L__"] = p.L
    n = len(df)
    n_test = int(df["__test__"].sum())
    print(f"  samples={n}  test={n_test}  segments={df['__seg__'].nunique()}")

    regime = df["__regime__"]
    test_mask = df["__test__"].to_numpy()

    psi_dot_meas = df["yaw_rate_meas_rads"].to_numpy()

    # V0: residual as-is
    v0_resid = df["yaw_rate_resid_rads"].to_numpy()
    v0 = report_rmse("V0_baseline", v0_resid, regime, test_mask)

    # V1: steering bias correction (per-platform)
    delta_off = fit_delta_offset(df)
    delta_corr = df["delta_road_rad"].to_numpy() + delta_off
    L = p.L
    v_arr = df["v_mps"].to_numpy()
    v1_pred = (v_arr / L) * np.tan(delta_corr)
    v1_resid = v1_pred - psi_dot_meas
    v1 = report_rmse("V1_delta_offset", v1_resid, regime, test_mask)
    v1["delta_offset_rad"] = delta_off

    # V2: + understeer gradient (per-platform)
    K_us = fit_k_us(df, delta_off)
    v2_pred = v_arr * delta_corr / (L + K_us * v_arr * v_arr)
    v2_resid = v2_pred - psi_dot_meas
    v2 = report_rmse("V2_understeer", v2_resid, regime, test_mask)
    v2["K_us"] = K_us

    # V3: + lag alignment (per-platform)
    k = fit_lag(df, v2_pred)
    v3_pred = np.roll(v2_pred, k)
    valid = np.ones(len(df), dtype=bool)
    if k > 0:
        valid[:k] = False
    elif k < 0:
        valid[k:] = False
    v3_resid = np.where(valid, v3_pred - psi_dot_meas, np.nan)
    v3 = report_rmse("V3_lag", v3_resid, regime, test_mask)
    v3["lag_samples"] = int(k)

    # Marginal accounting (on overall)
    marginals = {
        "V1": v0["overall"] - v1["overall"],
        "V2": v1["overall"] - v2["overall"],
        "V3": v2["overall"] - v3["overall"],
    }
    total = v0["overall"] - v3["overall"]
    sum_marg = sum(marginals.values())
    coherence = abs(sum_marg - total) / abs(total) if total != 0 else 0.0

    result = {
        "platform": platform,
        "n_samples": n,
        "n_test": n_test,
        "n_segments": int(df["__seg__"].nunique()),
        "variants": [v0, v1, v2, v3],
        "marginals_overall": marginals,
        "total_drop_overall": total,
        "attribution_coherence": coherence,
        "fit_scope": "per-platform",
    }
    print(json.dumps(result, indent=2))
    (out_dir / f"{platform}.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    out_dir = Path("out/ladder")
    results = {}
    for plat in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
        results[plat] = run_platform(plat, out_dir)
    (out_dir / "summary.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
