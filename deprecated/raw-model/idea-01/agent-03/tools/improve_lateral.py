"""Improve KS lateral predictions on Ford simdata and attribute RMSE drops.

We use the Ford simdata CSVs that already contain the baseline KS lateral prediction
(yaw_rate_pred_rads, a_y_pred_mps2) alongside the measurement truth
(yaw_rate_meas_rads, a_lat_meas_mps2). We DO NOT touch the model code; we
re-derive predictions from the same recorded inputs (v_mps, delta_road_rad)
using improved parameter/physics choices, then compute residuals.

Variants on the ladder (each builds on the previous):
  V0 baseline   : yaw_rate_pred = (v / L) * tan(delta_road)               [as stored]
  V1 +bias      : subtract per-segment steering bias estimated at low speed
  V2 +ratio fit : fit a single scalar effective steer ratio per platform on a
                  training split using least-squares against measured yaw
  V3 +understeer: linear-bicycle understeer-gradient correction
                  delta_eff = delta - Kus * a_y_meas    (a_y from truth)
                  with Kus fit per platform on training split

Metric: RMSE of yaw-rate prediction error (rad/s), pooled across segments,
weighted by sample count. We use the standard 80/20 train/test split by
segment id (hash-based, reproducible).

Attribution scheme: "marginal / sequential ablation". For each variant we
report (RMSE_prev - RMSE_now), and its share of total improvement
(RMSE_V0 - RMSE_V3). We also report Shapley-style averaged contribution over
all variant orderings as a sanity check.
"""
from __future__ import annotations

import hashlib
import itertools
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-03/data/sim/segments")
PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]

# Platform constants — must match parameters.py.
L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}
IS_BY_PLATFORM = {  # nominal steer ratio used by the adapter
    "FORD_MUSTANG_MACH_E_MK1":  17.0,
    "FORD_F_150_LIGHTNING_MK1": 16.9,
}

SAMPLE_HZ = 50.0


def list_segments(platform: str):
    return sorted((ROOT / platform).glob("*/*/*/sim.csv"))


def load_segment(csv: Path) -> pd.DataFrame:
    df = pd.read_csv(csv)
    needed = ["t_s", "delta_road_rad", "v_mps",
              "a_lat_meas_mps2", "yaw_rate_meas_rads",
              "yaw_rate_pred_rads", "a_y_pred_mps2"]
    if not all(c in df.columns for c in needed):
        return None
    # restrict to "moving" samples — at v ≈ 0 yaw rate is meaningless and
    # measurement bias dominates.
    df = df[df["v_mps"] > 2.0].reset_index(drop=True)
    if len(df) < 100:
        return None
    return df


def seg_hash(p: Path) -> int:
    return int(hashlib.sha1(str(p).encode()).hexdigest(), 16)


def split_train_test(paths, frac_test=0.2, seed=42):
    train, test = [], []
    for p in paths:
        h = (seg_hash(p) ^ seed) % 100
        (test if h < int(frac_test * 100) else train).append(p)
    return train, test


# ---------------------------- prediction variants ----------------------------

def predict_v0(df, L, i_s_nom):
    """Baseline: pure kinematic with nominal road-wheel angle as stored."""
    return (df["v_mps"].values / L) * np.tan(df["delta_road_rad"].values)


def predict_v1(df, L, i_s_nom, delta_bias):
    delta_corr = df["delta_road_rad"].values - delta_bias
    return (df["v_mps"].values / L) * np.tan(delta_corr)


def predict_v2(df, L, i_s_nom, delta_bias, ratio_scale):
    """Adjust effective steer ratio: delta_eff = delta * (i_s_nom / i_s_eff).
    Equivalent to delta_eff = delta / ratio_scale where
    ratio_scale = i_s_eff / i_s_nom.
    """
    delta_corr = (df["delta_road_rad"].values - delta_bias) / ratio_scale
    return (df["v_mps"].values / L) * np.tan(delta_corr)


def predict_v3(df, L, i_s_nom, delta_bias, ratio_scale, Kus):
    """Linear-bicycle understeer correction:
       delta_required = (L/R) + Kus * a_y    →    invert to get yaw rate from delta_in.

    Recast: for the linear bicycle in steady-state,
       psi_dot = v / (L + Kus * v^2) * delta
    We apply small-angle approximation (delta_corr small) for the lateral
    coefficient consistent with the linear single-track derivation.
    """
    delta_corr = (df["delta_road_rad"].values - delta_bias) / ratio_scale
    v = df["v_mps"].values
    # Avoid singularity for very low Kus and very low v.
    return v / (L + Kus * v * v) * delta_corr


# ---------------------------- fitters ----------------------------

def fit_bias(dfs, L, i_s_nom):
    """Estimate steering bias per segment as median(delta - delta_for_measured_yaw)
    on near-straight-line samples (|yaw|<0.02 rad/s), then take pooled median.

    A non-zero steering bias is a classic sensor offset. We fit a SINGLE scalar
    per platform (not per segment) so the fit is "model parameter", not a hack.
    """
    deltas = []
    for df in dfs:
        m = (np.abs(df["yaw_rate_meas_rads"].values) < 0.02) & (df["v_mps"].values > 8.0)
        if m.sum() < 50:
            continue
        # On near-straight: measured yaw≈0 → ideal delta_road≈0. Any nonzero
        # delta_road is steer-sensor bias (or transient).
        deltas.append(df["delta_road_rad"].values[m])
    if not deltas:
        return 0.0
    pool = np.concatenate(deltas)
    return float(np.median(pool))


def fit_ratio_scale(dfs, L, i_s_nom, delta_bias):
    """Fit s = i_s_eff / i_s_nom by least-squares on the LINEAR map
       psi_dot ≈ (v / L) * (delta - bias) / s          (small-angle)
    Closed form: s = sum(x*y) / sum(y*y) where
       x_i = (v_i / L) * (delta_i - bias),  y_i = psi_dot_meas_i.
    Wait — that gives s = sum(x*y)/sum(y*y) for the model x = s*y. Re-derive:
       y_meas = x / s   →   s = x / y_meas   →   in LS: s = sum(x*y)/sum(y*y).
    """
    xs, ys = [], []
    for df in dfs:
        v = df["v_mps"].values
        d = df["delta_road_rad"].values - delta_bias
        m = (v > 5.0)
        x = (v[m] / L) * d[m]                     # kinematic prediction at s=1
        y = df["yaw_rate_meas_rads"].values[m]
        xs.append(x); ys.append(y)
    x = np.concatenate(xs); y = np.concatenate(ys)
    # model: y = x / s   →   x = s * y   →   s = (x·y)/(y·y)
    s = float(np.dot(x, y) / np.dot(y, y))
    return s


def fit_Kus(dfs, L, i_s_nom, delta_bias, ratio_scale):
    """Fit understeer coefficient Kus by 1-D LS.

    Steady-state linear bicycle:
       delta = (L/R) + Kus * a_y
       psi_dot = v/R = v * delta_eff / (L + Kus*v^2)
    Rearranging w/ delta_eff already corrected for bias and ratio,
       L * psi_dot / v - delta_eff   ≈ -Kus * v * psi_dot
    so regress  (delta_eff - L*psi_dot/v) on (v*psi_dot)   slope = Kus.
    Use measured psi_dot.
    """
    rhs, lhs = [], []
    for df in dfs:
        v = df["v_mps"].values
        d_eff = (df["delta_road_rad"].values - delta_bias) / ratio_scale
        psi = df["yaw_rate_meas_rads"].values
        m = v > 10.0
        rhs.append(v[m] * psi[m])               # x  (independent)
        lhs.append(d_eff[m] - L * psi[m] / v[m])  # y
    x = np.concatenate(rhs); y = np.concatenate(lhs)
    # y = Kus * x
    Kus = float(np.dot(x, y) / np.dot(x, x))
    return Kus


# ---------------------------- driver ----------------------------

def rmse(pred, meas):
    return float(np.sqrt(np.mean((pred - meas) ** 2)))


def evaluate(platform):
    paths = list_segments(platform)
    dfs_all = []
    for p in paths:
        df = load_segment(p)
        if df is not None:
            dfs_all.append((p, df))
    print(f"[{platform}] loaded {len(dfs_all)} segments")

    train_paths, test_paths = split_train_test([p for p, _ in dfs_all])
    train_dfs = [df for p, df in dfs_all if p in set(train_paths)]
    test_dfs  = [df for p, df in dfs_all if p in set(test_paths)]
    print(f"  train segments: {len(train_dfs)}   test segments: {len(test_dfs)}")

    L = L_BY_PLATFORM[platform]
    i_s_nom = IS_BY_PLATFORM[platform]

    # Fit on train.
    bias = fit_bias(train_dfs, L, i_s_nom)
    ratio = fit_ratio_scale(train_dfs, L, i_s_nom, bias)
    Kus = fit_Kus(train_dfs, L, i_s_nom, bias, ratio)
    print(f"  fit on train: bias={np.degrees(bias)*i_s_nom:+.3f} deg (steering wheel), "
          f"ratio_scale={ratio:.4f}, Kus={Kus:.5f} s²/m  (effective i_s = "
          f"{i_s_nom*ratio:.3f})")

    def variant_rmse(predict_fn, *args):
        preds, meass = [], []
        for df in test_dfs:
            p_ = predict_fn(df, L, i_s_nom, *args)
            preds.append(p_); meass.append(df["yaw_rate_meas_rads"].values)
        return rmse(np.concatenate(preds), np.concatenate(meass))

    r0 = variant_rmse(predict_v0)
    r1 = variant_rmse(predict_v1, bias)
    r2 = variant_rmse(predict_v2, bias, ratio)
    r3 = variant_rmse(predict_v3, bias, ratio, Kus)

    print(f"  RMSE yaw rate (rad/s) on TEST:")
    print(f"    V0 baseline                                  : {r0:.5f}")
    print(f"    V1 +steering bias                            : {r1:.5f}  Δ={r0-r1:+.5f}")
    print(f"    V2 +effective steer ratio                    : {r2:.5f}  Δ={r1-r2:+.5f}")
    print(f"    V3 +understeer gradient (linear bicycle)     : {r3:.5f}  Δ={r2-r3:+.5f}")
    total = r0 - r3
    print(f"    total improvement                            : {total:+.5f}  ({100*total/r0:.1f}%)")
    if total > 0:
        print("  marginal-ablation attribution (share of total):")
        for name, delta in [("bias", r0 - r1), ("ratio", r1 - r2), ("Kus", r2 - r3)]:
            print(f"    {name:>6}: {100*delta/total:+5.1f}%")

    # Shapley-style attribution (avg marginal across all 6 orderings of 3 factors)
    factors = ["bias", "ratio", "Kus"]
    fit_vals = dict(bias=bias, ratio=ratio, Kus=Kus)

    def predict_with(active, df):
        b = fit_vals["bias"]  if "bias"  in active else 0.0
        r = fit_vals["ratio"] if "ratio" in active else 1.0
        k = fit_vals["Kus"]   if "Kus"   in active else 0.0
        return predict_v3(df, L, i_s_nom, b, r, k)

    def coalition_rmse(active):
        preds, meass = [], []
        for df in test_dfs:
            preds.append(predict_with(set(active), df))
            meass.append(df["yaw_rate_meas_rads"].values)
        return rmse(np.concatenate(preds), np.concatenate(meass))

    coalitions = {}
    from itertools import combinations
    for k in range(0, 4):
        for c in combinations(factors, k):
            coalitions[frozenset(c)] = coalition_rmse(c)

    shapley = {f: 0.0 for f in factors}
    n = len(factors)
    for perm in itertools.permutations(factors):
        for i, f in enumerate(perm):
            without = frozenset(perm[:i])
            withf   = frozenset(perm[:i+1])
            # Improvement contributed by adding f to coalition `without`
            shapley[f] += (coalitions[without] - coalitions[withf])
    for f in factors:
        shapley[f] /= math.factorial(n)

    print("  Shapley-style attribution (avg marginal across all orderings):")
    s_total = sum(shapley.values())
    for f in factors:
        print(f"    {f:>6}: ΔRMSE={shapley[f]:+.5f}   "
              f"share={100*shapley[f]/s_total if s_total else 0:+5.1f}%")

    return {
        "platform": platform,
        "r0": r0, "r1": r1, "r2": r2, "r3": r3,
        "bias_deg_wheel": np.degrees(bias)*i_s_nom,
        "ratio_scale": ratio, "Kus": Kus,
        "shapley": shapley,
    }


if __name__ == "__main__":
    results = []
    for plat in PLATFORMS:
        try:
            results.append(evaluate(plat))
        except Exception as e:
            print(f"[{plat}] FAILED: {e}")
            raise

    # Pooled
    print("\n==== POOLED ACROSS PLATFORMS ====")
    for k in ["r0", "r1", "r2", "r3"]:
        vals = [r[k] for r in results]
        print(f"  {k}: mean={np.mean(vals):.5f}   per-platform={vals}")
