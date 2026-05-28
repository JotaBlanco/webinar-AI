"""Lateral fidelity ladder for KS model on Ford Mustang Mach-E.

V0  baseline  : RMSE of yaw_rate_resid_rads as-is
V1  bias      : per-segment mean removal of (pred - meas)
V2  align     : per-segment time-shift compensation (cross-corr lag of pred vs meas)
V3  K_us fit  : linear-bicycle-inspired understeer correction
                psi_dot_corrected = psi_dot_pred / (1 + K_us * v^2)
                with K_us fit globally by least squares against meas
V4  combo     : V3 + V2 + V1, applied in that order
"""

from __future__ import annotations
import glob
import os
import sys
import numpy as np
import pandas as pd

SEG_ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-03/data/sim/segments/FORD_MUSTANG_MACH_E_MK1"
OUT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-03/out"

DT = 0.02  # 50 Hz

# Regime thresholds (rad/s on truth yaw rate)
STRAIGHT_THR = 0.05
TRANSIENT_DPSIDT = 0.5  # |d/dt yaw_rate_meas| rad/s^2 => transient


def load_segments() -> list[pd.DataFrame]:
    paths = sorted(glob.glob(os.path.join(SEG_ROOT, "*/*/*/sim.csv")))
    out = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if len(df) < 100:
            continue
        # require finite required cols
        need = ["yaw_rate_pred_rads", "yaw_rate_meas_rads", "v_mps", "delta_road_rad"]
        if not all(c in df.columns for c in need):
            continue
        df = df.dropna(subset=need).reset_index(drop=True)
        if len(df) < 100:
            continue
        df["_seg"] = p
        out.append(df)
    return out


def regime_mask(df: pd.DataFrame) -> dict[str, np.ndarray]:
    y = df["yaw_rate_meas_rads"].to_numpy()
    dy = np.gradient(y, DT)
    abs_y = np.abs(y)
    abs_dy = np.abs(dy)
    straight = abs_y < STRAIGHT_THR
    transient = (~straight) & (abs_dy > TRANSIENT_DPSIDT)
    steady = (~straight) & (~transient)
    return {"straight": straight, "steady": steady, "transient": transient,
            "all": np.ones(len(df), dtype=bool)}


def rmse(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    return float(np.sqrt(np.mean(x * x)))


def best_lag(pred: np.ndarray, meas: np.ndarray, max_lag: int = 25) -> int:
    """Return integer lag k such that pred[t-k] best matches meas[t].
    Positive k means prediction leads measurement."""
    # remove DC
    p = pred - pred.mean()
    m = meas - meas.mean()
    n = len(p)
    best = (0, -np.inf)
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            a = p[: n - k]
            b = m[k:]
        else:
            a = p[-k:]
            b = m[: n + k]
        if len(a) < 50:
            continue
        denom = np.sqrt(np.sum(a * a) * np.sum(b * b))
        if denom == 0:
            continue
        c = np.sum(a * b) / denom
        if c > best[1]:
            best = (k, c)
    return best[0]


def shift(arr: np.ndarray, k: int) -> np.ndarray:
    """Shift array by k samples; positive k shifts pred forward in time (delays it).
    Out-of-range filled with edge value."""
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


def fit_kus(segs: list[pd.DataFrame]) -> float:
    """Fit understeer gradient K_us by minimising L2 on aligned bias-removed signals.

    Model: psi_dot_corr = psi_dot_pred / (1 + K_us * v^2)
    Equivalent to: psi_dot_pred = psi_dot_corr * (1 + K_us * v^2)
                                ≈ psi_dot_meas * (1 + K_us * v^2)
    So we solve: psi_dot_pred / psi_dot_meas ≈ 1 + K_us * v^2 in mean-square sense.

    We use a robust formulation: minimise sum (psi_dot_pred - psi_dot_meas*(1+K*v^2))^2
    -> K = sum( (pred-meas) * meas * v^2 ) / sum( (meas*v^2)^2 )
    """
    num = 0.0
    den = 0.0
    for df in segs:
        v = df["v_mps"].to_numpy()
        pred = df["yaw_rate_pred_rads"].to_numpy()
        meas = df["yaw_rate_meas_rads"].to_numpy()
        # Only use samples with non-trivial yaw rate to avoid pure-straight dominating
        mask = (np.abs(meas) > 0.05) & (v > 3.0) & np.isfinite(pred) & np.isfinite(meas)
        if mask.sum() < 50:
            continue
        m = meas[mask]
        p = pred[mask]
        vv = v[mask] ** 2
        num += np.sum((p - m) * m * vv)
        den += np.sum((m * vv) ** 2)
    if den == 0:
        return 0.0
    return num / den


def compute_variants(segs: list[pd.DataFrame], K_us: float):
    """Return dict: variant -> dict[regime -> rmse]."""
    regimes = ["all", "straight", "steady", "transient"]
    results = {v: {r: [] for r in regimes} for v in ["V0", "V1", "V2", "V3", "V4"]}
    # also accumulate per-sample arrays for global RMSE
    pooled = {v: {r: [] for r in regimes} for v in ["V0", "V1", "V2", "V3", "V4"]}

    for df in segs:
        v = df["v_mps"].to_numpy()
        pred = df["yaw_rate_pred_rads"].to_numpy()
        meas = df["yaw_rate_meas_rads"].to_numpy()

        rmask = regime_mask(df)

        # V0: as-is
        r0 = pred - meas

        # V1: per-segment bias removal
        bias = np.mean(r0)
        r1 = r0 - bias

        # V2: time-align (find lag from V1-corrected signals)
        lag = best_lag(pred - bias, meas, max_lag=15)  # up to 0.3s
        pred_shifted = shift(pred - bias, lag)
        r2 = pred_shifted - meas

        # V3: understeer correction (no bias, no shift) -- just to isolate effect
        pred_us = pred / (1.0 + K_us * v * v)
        r3 = pred_us - meas

        # V4: combo -- apply US correction, then per-seg bias, then align
        pred_us2 = pred / (1.0 + K_us * v * v)
        bias4 = np.mean(pred_us2 - meas)
        pred_us2_b = pred_us2 - bias4
        lag4 = best_lag(pred_us2_b, meas, max_lag=15)
        pred_final = shift(pred_us2_b, lag4)
        r4 = pred_final - meas

        for name, r in [("V0", r0), ("V1", r1), ("V2", r2), ("V3", r3), ("V4", r4)]:
            for rg in regimes:
                m = rmask[rg]
                pooled[name][rg].append(r[m])

    out = {}
    for v in pooled:
        out[v] = {}
        for rg in pooled[v]:
            arr = np.concatenate(pooled[v][rg]) if pooled[v][rg] else np.array([])
            out[v][rg] = rmse(arr)
    return out


def main():
    print("Loading segments...", file=sys.stderr)
    segs = load_segments()
    print(f"Loaded {len(segs)} Mach-E segments", file=sys.stderr)

    # Quick sign sanity check
    sign_ok = 0
    sign_total = 0
    for df in segs[:50]:
        d = df["delta_road_rad"].to_numpy()
        y = df["yaw_rate_meas_rads"].to_numpy()
        m = np.abs(d) > 0.01
        if m.sum() > 50:
            c = np.corrcoef(d[m], y[m])[0, 1]
            sign_total += 1
            if c > 0:
                sign_ok += 1
    print(f"Sign sanity: corr(delta, yaw_rate_meas) > 0 in {sign_ok}/{sign_total} segs", file=sys.stderr)

    K_us = fit_kus(segs)
    print(f"Fitted K_us = {K_us:.6f} s²/m²", file=sys.stderr)

    results = compute_variants(segs, K_us)

    # Print table
    print("\nVariant ladder — RMSE on yaw_rate residual (rad/s)")
    print(f"{'variant':8s}  {'all':>8s}  {'straight':>8s}  {'steady':>8s}  {'transient':>10s}")
    for v in ["V0", "V1", "V2", "V3", "V4"]:
        row = results[v]
        print(f"{v:8s}  {row['all']:8.5f}  {row['straight']:8.5f}  {row['steady']:8.5f}  {row['transient']:10.5f}")

    # Save CSV
    rows = []
    for v in ["V0", "V1", "V2", "V3", "V4"]:
        rows.append({"variant": v, **results[v]})
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "variants_rmse.csv"), index=False)
    with open(os.path.join(OUT, "fit.txt"), "w") as f:
        f.write(f"K_us={K_us:.8f}\nn_segments={len(segs)}\n")

    # Compute marginal drops (sequential V0 -> V1 -> V2 -> V4)
    # And isolated V3 contribution: V0 -> V3
    print("\nMarginal drops (rad/s) on 'all' regime:")
    seq = ["V0", "V1", "V2", "V4"]
    for i in range(1, len(seq)):
        d = results[seq[i-1]]["all"] - results[seq[i]]["all"]
        print(f"  {seq[i-1]} -> {seq[i]}: {d:+.5f}")
    print(f"  Isolated V3 (V0 -> V3): {results['V0']['all'] - results['V3']['all']:+.5f}")
    print(f"  Total V0 -> V4: {results['V0']['all'] - results['V4']['all']:+.5f}")

    return results, K_us


if __name__ == "__main__":
    main()
