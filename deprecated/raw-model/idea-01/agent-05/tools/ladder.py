"""Variant ladder for improving lateral predictions.

Primary metric: pooled RMSE of predicted yaw rate vs measured yaw rate
across all Ford segments (only Fords have a measured-truth channel).

Baseline (v0) uses the existing prediction columns in sim.csv:
    yaw_rate_pred = (v/L) * tan(delta_road)

Each subsequent variant re-computes the prediction from raw fields
(v_mps, delta_road_rad, yaw_rate_meas_rads, a_lat_meas_mps2) using
the same KS structure plus one targeted modification.

Attribution scheme: sequential / cumulative improvement on the ladder,
also reported as "leave-one-out" effect when applied alone vs baseline.
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

DATA_ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-05/data/sim/segments"

# Wheelbase per platform (openpilot-canonical, from parameters.py)
L_BY_PLAT = {
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.700,
}
# ST stiffness parameters for understeer gradient (linear-bicycle):
#   K_us = m * (l_r * C_alpha_r - l_f * C_alpha_f) / (L * C_alpha_f * C_alpha_r)
# yields yaw_rate = v * delta / (L + K_us * v^2)  (steady-state)
ST_BY_PLAT = {
    "FORD_MUSTANG_MACH_E_MK1": dict(m=2336.0, l_f=1.3130, l_r=1.671,
                                    Caf=286_551, Car=355_912, L=2.984),
    "FORD_F_150_LIGHTNING_MK1": dict(m=3084.0, l_f=1.628,  l_r=2.072,
                                     Caf=378_307, Car=469_878, L=3.700),
}


def find_ford_csvs():
    paths = []
    for plat in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
        paths.extend(glob.glob(os.path.join(DATA_ROOT, plat, "**", "sim.csv"),
                               recursive=True))
    return sorted(paths)


def load_segments():
    """Yield (platform, path, df) for usable Ford segments."""
    paths = find_ford_csvs()
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        for plat in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
            if plat in p:
                yield plat, p, df
                break


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


# ---- Variants ---------------------------------------------------------------

def predict_v0_baseline(df, plat):
    """Reproduces existing column: yaw = (v/L) * tan(delta_road)."""
    L = L_BY_PLAT[plat]
    return (df["v_mps"].to_numpy() / L) * np.tan(df["delta_road_rad"].to_numpy())


def predict_v1_outlier_filter(df, plat, mask=None):
    """Same as v0 — outlier filtering is done at scoring time by mask."""
    return predict_v0_baseline(df, plat)


def fit_steer_offset(df, plat):
    """Fit a static road-wheel-angle offset that best aligns yaw_rate_pred to
    yaw_rate_meas, using a velocity-weighted linear least squares on the
    steady-state KS identity:

        yaw_meas ≈ (v/L) * tan(delta + delta_off)
        for small angles & small offset: tan(δ+ε) ≈ tan(δ) + (1+tan²δ)·ε

    So: residual_yaw ≈ (v/L) * (1 + tan²δ) * delta_off

    Solve: delta_off = sum(w * r) / sum(w * (v/L * sec²δ))  (weighted regression
    on x = (v/L)*sec²δ, y = (yaw_meas - yaw_pred_baseline)).
    """
    L = L_BY_PLAT[plat]
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    yaw_meas = df["yaw_rate_meas_rads"].to_numpy()
    yaw_pred0 = (v / L) * np.tan(delta)
    x = (v / L) * (1.0 + np.tan(delta) ** 2)
    y = yaw_meas - yaw_pred0
    # weight by speed: only meaningful when moving
    w = np.clip(v - 3.0, 0.0, None)
    num = float(np.sum(w * x * y))
    den = float(np.sum(w * x * x)) + 1e-12
    return num / den


def predict_v2_steer_offset(df, plat, delta_off):
    L = L_BY_PLAT[plat]
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy() + delta_off
    return (v / L) * np.tan(delta)


def understeer_K(plat):
    p = ST_BY_PLAT[plat]
    return p["m"] * (p["l_r"] * p["Car"] - p["l_f"] * p["Caf"]) / \
           (p["L"] * p["Caf"] * p["Car"])


def predict_v3_understeer(df, plat, delta_off=0.0):
    """Steady-state bicycle: yaw = v*delta / (L + K*v²)."""
    L = L_BY_PLAT[plat]
    K = understeer_K(plat)
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy() + delta_off
    return v * delta / (L + K * v ** 2)


def fit_understeer_K_with_offset(plat, segments, delta_off):
    """Fit K so that yaw_meas ≈ v*(δ+off) / (L + K v²).
    Equivalently: yaw_meas * (L + K v²) = v*(δ+off)
    => K * (yaw_meas * v²) = v*(δ+off) - L*yaw_meas
    Linear LS in K, pooled, weighted by v.
    """
    L = L_BY_PLAT[plat]
    num = 0.0
    den = 0.0
    for p, path, df in segments:
        if p != plat:
            continue
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy() + delta_off
        yaw = df["yaw_rate_meas_rads"].to_numpy()
        # outlier mask (a_lat sane)
        m = (np.abs(df["a_lat_meas_mps2"].to_numpy()) < 12) & (v > 5)
        x = (yaw * v * v)[m]
        y = (v * delta - L * yaw)[m]
        w = v[m] - 4.0  # weight
        num += float(np.sum(w * x * y))
        den += float(np.sum(w * x * x))
    return num / (den + 1e-12)


# ---- Scoring ---------------------------------------------------------------

def score_variant(predict_fn, segments, *, fit_offsets=None,
                  outlier_mask_only=False):
    """Pool yaw-rate predictions across all Ford segments and report RMSE.

    fit_offsets: optional dict {platform: delta_off} for variant 2/3.
    outlier_mask_only: if True, applies a sensor-sanity mask
        (|a_lat_meas| < 15 m/s²). Always applied actually — it just keeps
        the comparison apples-to-apples between v0 (no filter) and others.
    """
    pred_all = []
    meas_all = []
    for plat, path, df in segments:
        kwargs = {}
        if fit_offsets is not None and plat in fit_offsets:
            kwargs["delta_off"] = fit_offsets[plat]
        try:
            pred = predict_fn(df, plat, **kwargs)
        except TypeError:
            pred = predict_fn(df, plat)
        meas = df["yaw_rate_meas_rads"].to_numpy()
        # Sensor sanity mask: drop frames with absurd a_lat values
        m = np.abs(df["a_lat_meas_mps2"].to_numpy()) < 15.0
        pred_all.append(pred[m])
        meas_all.append(meas[m])
    p = np.concatenate(pred_all)
    m = np.concatenate(meas_all)
    return rmse(p, m), len(p)


def score_unfiltered(predict_fn, segments):
    pred_all = []
    meas_all = []
    for plat, path, df in segments:
        pred = predict_fn(df, plat)
        meas = df["yaw_rate_meas_rads"].to_numpy()
        pred_all.append(pred)
        meas_all.append(meas)
    p = np.concatenate(pred_all)
    m = np.concatenate(meas_all)
    return rmse(p, m), len(p)


def main():
    print("Loading segments...")
    segments = list(load_segments())
    print(f"Loaded {len(segments)} Ford segments.")

    # ---- v0: as-shipped baseline (unfiltered) ----
    rmse0_unf, n0 = score_unfiltered(predict_v0_baseline, segments)
    print(f"\n[v0] Unfiltered baseline (existing prediction column):")
    print(f"     RMSE_yaw = {rmse0_unf:.5f} rad/s  (n={n0})")

    # ---- v1: drop sensor-spike frames (|a_lat|>15) ----
    rmse1, n1 = score_variant(predict_v0_baseline, segments)
    print(f"\n[v1] + sensor-sanity outlier mask (|a_lat|<15 m/s²):")
    print(f"     RMSE_yaw = {rmse1:.5f} rad/s  (n={n1}, dropped {n0-n1})")

    # ---- v2: fit per-platform static steering-angle offset ----
    offsets = {}
    for plat in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
        # combine across that platform's segments
        L = L_BY_PLAT[plat]
        num = 0.0; den = 0.0
        for p, path, df in segments:
            if p != plat:
                continue
            v = df["v_mps"].to_numpy()
            delta = df["delta_road_rad"].to_numpy()
            yaw_meas = df["yaw_rate_meas_rads"].to_numpy()
            m = (np.abs(df["a_lat_meas_mps2"].to_numpy()) < 15) & (v > 5)
            yaw_pred0 = (v / L) * np.tan(delta)
            x = (v / L) * (1.0 + np.tan(delta) ** 2)
            y = yaw_meas - yaw_pred0
            w = np.clip(v - 3.0, 0.0, None)
            num += float(np.sum((w * x * y)[m]))
            den += float(np.sum((w * x * x)[m]))
        offsets[plat] = num / (den + 1e-12)
    print(f"\nFitted steering offsets (road wheel, rad):")
    for plat, off in offsets.items():
        print(f"  {plat}: {off:+.6f} rad = {np.degrees(off)*17:+.3f} deg at "
              f"the wheel (×i_s~17)")

    rmse2, n2 = score_variant(predict_v2_steer_offset, segments,
                              fit_offsets=offsets)
    print(f"\n[v2] + per-platform fitted static steering-offset:")
    print(f"     RMSE_yaw = {rmse2:.5f} rad/s  (n={n2})")

    # ---- v3: steady-state understeer (linear bicycle) using openpilot stiffnesses ----
    rmse3, n3 = score_variant(predict_v3_understeer, segments,
                              fit_offsets=offsets)
    print(f"\n[v3] + steady-state understeer (canonical Caf/Car):")
    for plat in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
        K = understeer_K(plat)
        print(f"     K_us({plat}) = {K:+.5f}  "
              f"(neg = oversteer; pos = understeer)")
    print(f"     RMSE_yaw = {rmse3:.5f} rad/s  (n={n3})")

    # ---- v4: refit K per platform jointly with already-fitted offset ----
    K_fit = {}
    for plat in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
        K_fit[plat] = fit_understeer_K_with_offset(plat, segments,
                                                    offsets[plat])
    print(f"\nFitted understeer gradients (refit K):")
    for plat, k in K_fit.items():
        print(f"  {plat}: K_us = {k:+.5f}  (canonical was "
              f"{understeer_K(plat):+.5f})")

    def predict_v4(df, plat, delta_off=0.0):
        L = L_BY_PLAT[plat]
        K = K_fit[plat]
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy() + delta_off
        return v * delta / (L + K * v ** 2)

    rmse4, n4 = score_variant(predict_v4, segments, fit_offsets=offsets)
    print(f"\n[v4] + understeer K refit from data:")
    print(f"     RMSE_yaw = {rmse4:.5f} rad/s  (n={n4})")

    # ---- Summary attribution (sequential / cumulative) ----
    print("\n" + "=" * 64)
    print("ATTRIBUTION (sequential, each step adds to previous)")
    print("=" * 64)
    rows = [
        ("v0  baseline (unfiltered)",                rmse0_unf),
        ("v1  + outlier mask (|a_lat|<15)",          rmse1),
        ("v2  + per-platform steering offset",       rmse2),
        ("v3  + canonical understeer (Caf/Car)",     rmse3),
        ("v4  + understeer K refit from data",       rmse4),
    ]
    prev = rmse0_unf
    for name, r in rows:
        d = prev - r
        d_pct = 100.0 * d / rmse0_unf if rmse0_unf else 0.0
        print(f"  {name:40s}  RMSE={r:.5f}  Δ={d:+.5f}  ({d_pct:+5.2f}%)")
        prev = r
    total = rmse0_unf - rows[-1][1]
    print(f"\n  Total improvement: {total:+.5f} rad/s "
          f"({100*total/rmse0_unf:+.2f}% of baseline)")

    # ---- Leave-one-out style: single-change-from-baseline ----
    print("\n" + "=" * 64)
    print("MARGINAL (single change applied to v1 = mask-only baseline)")
    print("=" * 64)
    rmse_b = rmse1
    # offset alone
    rmse_off, _ = score_variant(predict_v2_steer_offset, segments,
                                fit_offsets=offsets)
    # understeer alone (no offset)
    rmse_us, _ = score_variant(predict_v3_understeer, segments,
                               fit_offsets={p: 0.0 for p in offsets})
    # k-refit alone (no offset)
    def predict_v4_no_off(df, plat, delta_off=0.0):
        L = L_BY_PLAT[plat]
        K = K_fit[plat]
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        return v * delta / (L + K * v ** 2)
    rmse_kr, _ = score_unfiltered(predict_v4_no_off, segments)
    # but masked:
    rmse_kr, _ = score_variant(predict_v4_no_off, segments)

    rows_m = [
        ("offset only (no understeer)",              rmse_off),
        ("understeer only (canonical, no offset)",   rmse_us),
        ("understeer-K refit only (no offset)",      rmse_kr),
    ]
    for name, r in rows_m:
        d = rmse_b - r
        d_pct = 100.0 * d / rmse_b
        print(f"  {name:40s}  RMSE={r:.5f}  vs v1 Δ={d:+.5f}  ({d_pct:+5.2f}%)")


if __name__ == "__main__":
    main()
