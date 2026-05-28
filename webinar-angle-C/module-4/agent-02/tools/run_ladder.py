#!/usr/bin/env python3
"""run_ladder.py — lateral-fidelity variant ladder for FORD_MUSTANG_MACH_E_MK1.

Implements the V0→V3 ladder locked in rpi/runs/<TS>/plan.md with the discipline
from skills/ablation-study (interleaved 4/5-1/5 train/test, additive monotone
variants, marginal attribution, per-regime breakdown, attribution coherence).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
L_CANON = 2.984  # from code/parameters.py MachEKS
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


def rmse(a) -> float:
    s = np.asarray(a, dtype=float)
    s = s[np.isfinite(s)]
    return float(np.sqrt(np.mean(s ** 2))) if s.size else float("nan")


def per_regime(resid: np.ndarray, mask: np.ndarray) -> dict:
    out = {"overall": rmse(resid)}
    for r in ("straight", "steady", "transient"):
        out[r] = rmse(resid[mask == r])
    return out


def shift_array(a: np.ndarray, k: int) -> np.ndarray:
    """Shift by k samples; positive k means delta lags meas by k (i.e. use delta[i-k])."""
    if k == 0:
        return a.copy()
    out = np.empty_like(a)
    if k > 0:
        out[:k] = a[0]
        out[k:] = a[:-k]
    else:
        out[k:] = a[-1]
        out[:k] = a[-k:]
    return out


def main():
    repo_root = Path(__file__).resolve().parents[1]
    data_root = repo_root / "data" / "sim" / "segments" / PLATFORM
    csvs = sorted(data_root.rglob("sim.csv"))
    frames = [pd.read_csv(p) for p in csvs]
    big = pd.concat(frames, ignore_index=True)
    n = len(big)

    mask = regime_mask(big).to_numpy()
    delta = big["delta_road_rad"].to_numpy(dtype=float)
    v = big["v_mps"].to_numpy(dtype=float)
    yr_meas = big["yaw_rate_meas_rads"].to_numpy(dtype=float)
    yr_pred_v0 = big["yaw_rate_pred_rads"].to_numpy(dtype=float)
    # Sanity: yr_pred_v0 should equal v*tan(delta)/L_CANON
    # (Small numerical drift expected.)

    # Interleaved split
    idx = np.arange(n)
    test_idx = idx[4::5]
    train_idx = np.setdiff1d(idx, test_idx)

    results = []

    # V0
    resid_v0 = yr_pred_v0 - yr_meas
    rm = per_regime(resid_v0[test_idx], mask[test_idx])
    results.append(("V0 baseline", rm, None))

    # V1 — bias removal
    b = float(np.median(resid_v0[train_idx]))
    resid_v1 = resid_v0 - b
    rm1 = per_regime(resid_v1[test_idx], mask[test_idx])
    results.append((f"V1 bias-remove (b={b:+.5f} rad/s)", rm1, results[-1][1]["overall"] - rm1["overall"]))

    # V2 — lag fit on shifted delta, then re-apply bias
    best_k = 0
    best_rmse = float("inf")
    for k in range(-10, 11):
        delta_s = shift_array(delta, k)
        yr_pred_k = v * np.tan(delta_s) / L_CANON
        resid_k = yr_pred_k - yr_meas
        # refit bias on train under this k
        b_k = float(np.median(resid_k[train_idx]))
        r_train = rmse(resid_k[train_idx] - b_k)
        if r_train < best_rmse:
            best_rmse = r_train
            best_k = k
    delta_s = shift_array(delta, best_k)
    yr_pred_v2_raw = v * np.tan(delta_s) / L_CANON
    b2 = float(np.median((yr_pred_v2_raw - yr_meas)[train_idx]))
    resid_v2 = (yr_pred_v2_raw - yr_meas) - b2
    rm2 = per_regime(resid_v2[test_idx], mask[test_idx])
    results.append((f"V2 lag-align (k={best_k} samples = {best_k*20} ms, b={b2:+.5f})",
                    rm2, results[-1][1]["overall"] - rm2["overall"]))

    # V3 — effective wheelbase fit on top of V2's shifted delta
    # ψ̇ = v·tan(δ_s)/L_eff − b ; minimise RMSE wrt L_eff on train.
    # Closed-form-ish: let u = v·tan(δ_s); we want ψ̇ ≈ yr_meas + b
    # so L_eff ≈ Σ u·(yr_meas+b) / Σ (yr_meas+b)²  is wrong direction; use
    # 1/L_eff = α minimising Σ (α·u − (yr_meas + b_alpha))². Refit bias jointly.
    u = v * np.tan(delta_s)
    # Joint fit of α=1/L_eff and bias b on train:
    # residual = α·u − yr_meas − b ; minimise via least-squares with bias.
    X_train = np.column_stack([u[train_idx], np.ones(len(train_idx))])
    y_train = yr_meas[train_idx]
    coef, *_ = np.linalg.lstsq(X_train, y_train, rcond=None)
    alpha, b3_neg = coef  # model: yr_meas = alpha·u + (-b3) → pred = α·u, bias = -b3_neg
    L_eff = 1.0 / alpha
    # Clamp physical
    L_eff = float(np.clip(L_eff, 0.5 * L_CANON, 1.5 * L_CANON))
    alpha = 1.0 / L_eff
    yr_pred_v3_raw = alpha * u
    b3 = float(np.median((yr_pred_v3_raw - yr_meas)[train_idx]))
    resid_v3 = (yr_pred_v3_raw - yr_meas) - b3
    rm3 = per_regime(resid_v3[test_idx], mask[test_idx])
    results.append((f"V3 L_eff fit (L_eff={L_eff:.3f} m vs L={L_CANON:.3f}, b={b3:+.5f})",
                    rm3, results[-1][1]["overall"] - rm3["overall"]))

    # Print summary
    print(f"Platform: {PLATFORM}")
    print(f"Segments: {len(csvs)}  samples: {n}  test samples: {len(test_idx)}")
    print()
    header = f"{'Variant':<55s} {'overall':>9s} {'straight':>9s} {'steady':>9s} {'transient':>10s} {'marginal':>10s}"
    print(header)
    print("-" * len(header))
    for name, rm, marg in results:
        marg_s = f"{marg:+.5f}" if marg is not None else "    --   "
        flag = "  REGRESSION" if (marg is not None and marg < 0) else ""
        print(f"{name:<55s} {rm['overall']:>9.5f} {rm['straight']:>9.5f} {rm['steady']:>9.5f} {rm['transient']:>10.5f} {marg_s:>10s}{flag}")

    total = results[0][1]["overall"] - results[-1][1]["overall"]
    marg_sum = sum(r[2] for r in results[1:] if r[2] is not None)
    coh = abs(marg_sum - total) / abs(total) if total else float("inf")
    print()
    print(f"Σ marginals = {marg_sum:+.5f}   total drop = {total:+.5f}   coherence err = {coh:.4f} (must be < 0.15)")

    out_dir = repo_root / "out"
    out_dir.mkdir(exist_ok=True)
    summary = {
        "platform": PLATFORM,
        "L_canonical": L_CANON,
        "best_lag_samples": best_k,
        "best_lag_ms": best_k * 20,
        "L_eff": L_eff,
        "bias_v1": b,
        "bias_v2": b2,
        "bias_v3": b3,
        "n_segments": len(csvs),
        "n_samples": int(n),
        "n_test": int(len(test_idx)),
        "results": [
            {"name": name, "rmse": rm, "marginal": marg}
            for name, rm, marg in results
        ],
        "coherence_err": coh,
    }
    (out_dir / "ladder_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out_dir / 'ladder_summary.json'}")


if __name__ == "__main__":
    main()
