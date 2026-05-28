"""Improvement ladder for KS lateral predictions on Ford simdata.

Primary metric: RMS yaw-rate residual (deg/s) aggregated over all samples
across both Ford platforms (Mach-E + F-150).

Why yaw rate (not a_y)? a_y in the CSVs is contaminated by a small number of
F-150 segments with obviously broken a_lat decoding (RMS > 100 m/s^2). Yaw
rate is clean across the corpus.

The KS prediction is yaw_rate_pred = (v/L) * tan(delta_road).
We treat the prediction problem as: given (v_meas, delta_wheel_meas, platform
params L, i_s), produce a better estimate of measured yaw_rate.

Ladder (each level adds one knob to the previous):
  V0 KS baseline (as stored in CSV)
  V1 + per-segment steering-angle bias (DC offset removed)
  V2 + global steering-ratio rescale (one scalar per platform, fit on full corpus)
  V3 + understeer correction (linear bicycle yaw-gain: psi_dot = v*delta/(L+Kus*v^2))
       (Kus fit per platform, on top of V2's i_s correction)
  V4 + steering-to-yaw time lag (one tau per platform, integer-sample shift)

Attribution scheme: SEQUENTIAL waterfall. Each level reports
  - this-level RMS
  - delta vs previous level (absolute deg/s, and % of remaining error closed)
Sum of deltas = total improvement (by construction).
"""
from __future__ import annotations
import glob, os, json
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-07/data/sim/segments"
PLATFORMS = ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1")

# Wheelbases from parameters.py
L_BY_PLAT = {"FORD_MUSTANG_MACH_E_MK1": 2.984,
             "FORD_F_150_LIGHTNING_MK1": 3.70}
# Steering ratios (i_s) from parameters.py
IS_BY_PLAT = {"FORD_MUSTANG_MACH_E_MK1": 17.0,
              "FORD_F_150_LIGHTNING_MK1": 16.9}

def load():
    rows = []
    for plat in PLATFORMS:
        csvs = sorted(glob.glob(os.path.join(ROOT, plat, "*", "*", "*", "sim.csv")))
        for c in csvs:
            df = pd.read_csv(c)
            df["__platform"] = plat
            df["__seg"] = c
            rows.append(df)
    big = pd.concat(rows, ignore_index=True)
    return big

def rms(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x**2))) if len(x) else float("nan")

def pred_v0(df):
    """KS baseline: as stored in CSV (= (v/L)*tan(delta_road))."""
    return df["yaw_rate_pred_rads"].values.copy()

def pred_from_delta(v, delta_road, L):
    return (v / L) * np.tan(delta_road)

def fit_segment_bias(df):
    """Per-segment delta_road bias: choose b minimising
       || y_meas - (v/L)*tan(delta_road - b) ||^2 for each segment.
       Closed-form: linearise tan(delta-b) ≈ tan(delta) - sec^2(delta)*b.
       Iterate once around 0 (delta_road small in practice).
       Returns: dict seg -> bias (rad at road wheel).
    """
    biases = {}
    for seg, g in df.groupby("__seg"):
        plat = g["__platform"].iloc[0]
        L = L_BY_PLAT[plat]
        v = g["v_mps"].values
        d = g["delta_road_rad"].values
        y = g["yaw_rate_meas_rads"].values
        # Linearise: pred(b) = (v/L) * (tan(d) - sec^2(d)*b)
        # residual = y - pred = y - (v/L)tan(d) + (v/L)sec^2(d)*b
        # minimise sum (resid)^2 over b: linear LS in b
        a = (v / L) * (1.0 / np.cos(d))**2       # coefficient on b
        r0 = y - (v / L) * np.tan(d)              # residual at b=0
        # min || r0 + a*b ||^2 -> b = -(a.r0)/(a.a)
        denom = float(np.dot(a, a))
        if denom < 1e-9:
            biases[seg] = 0.0
        else:
            biases[seg] = float(-np.dot(a, r0) / denom)
    return biases

def fit_scalar_gain(v, delta, y, L):
    """Fit gain k so pred = k * (v/L) * tan(delta) minimises RMS y-residual."""
    p = (v / L) * np.tan(delta)
    denom = float(np.dot(p, p))
    if denom < 1e-9:
        return 1.0
    return float(np.dot(p, y) / denom)

def fit_understeer(v, delta, y, L):
    """Fit Kus in psi_dot = v*delta / (L + Kus*v^2).
       Re-arrange: y * (L + Kus*v^2) = v*delta
                   y*L + y*Kus*v^2 = v*delta
                   Kus = sum( (v*delta - y*L) * y*v^2 ) / sum( (y*v^2)^2 )
       Treating small-angle delta ≈ tan(delta).
    """
    rhs = v * delta - y * L      # = Kus * y * v^2 in the ideal case
    basis = y * v * v
    denom = float(np.dot(basis, basis))
    if denom < 1e-9:
        return 0.0
    return float(np.dot(basis, rhs) / denom)

def shift_pred(p, k):
    """Shift prediction by k samples (positive = pred is delayed by k samples,
       i.e. compare meas[k:] to pred[:-k] before applied)."""
    if k == 0:
        return p, slice(None)
    if k > 0:
        # pred is leading; align pred[:-k] with meas[k:]
        return p[:-k], slice(k, None)
    k = -k
    return p[k:], slice(0, -k)

def fit_lag(v, delta, y_meas, L, K_us, max_shift=10):
    """For each platform, find integer sample shift (50 Hz, so 1 sample = 20 ms)
    that minimises RMS. Search [-max_shift, max_shift]."""
    # build base pred at this stage
    pred_full = v * delta / (L + K_us * v * v)
    best = (0, rms(y_meas - pred_full))
    for k in range(-max_shift, max_shift + 1):
        if k == 0:
            continue
        if k > 0:
            r = y_meas[k:] - pred_full[:-k]
        else:
            kk = -k
            r = y_meas[:-kk] - pred_full[kk:]
        s = rms(r)
        if s < best[1]:
            best = (k, s)
    return best  # (k_samples, rms_rad)


def main():
    print("Loading...")
    big = load()
    n = len(big)
    print(f"Loaded {n:,} samples across {big['__seg'].nunique()} segments, 2 platforms.")

    # ----- V0 baseline (as in CSV) -----
    p0 = big["yaw_rate_pred_rads"].values
    y  = big["yaw_rate_meas_rads"].values
    rms0 = rms(y - p0)
    rms0_d = np.degrees(rms0)
    print(f"\nV0 baseline KS                 : {rms0_d:.4f} deg/s")

    # By platform
    for plat in PLATFORMS:
        m = big["__platform"] == plat
        print(f"   {plat:32s}: {np.degrees(rms(y[m]-p0[m])):.4f} deg/s")

    # ----- V1: per-segment steering bias -----
    print("\nFitting per-segment steering bias...")
    biases = fit_segment_bias(big)
    # Build new prediction
    p1 = np.zeros_like(p0)
    for seg, g in big.groupby("__seg"):
        idx = g.index.values
        plat = g["__platform"].iloc[0]
        L = L_BY_PLAT[plat]
        v = g["v_mps"].values
        d = g["delta_road_rad"].values - biases[seg]
        p1[idx] = (v / L) * np.tan(d)
    rms1 = rms(y - p1)
    print(f"V1 + per-segment δ-bias        : {np.degrees(rms1):.4f} deg/s   "
          f"(Δ vs V0 = {np.degrees(rms0-rms1):+.4f} deg/s, "
          f"{100*(rms0-rms1)/rms0:.1f}% of baseline error)")
    # diagnostic: bias magnitude stats
    b_arr = np.array(list(biases.values()))
    print(f"   bias stats (rad): mean {b_arr.mean():+.5f}  std {b_arr.std():.5f}  "
          f"P95(|b|) {np.percentile(np.abs(b_arr),95):.5f}")
    print(f"   equiv. wheel-deg: P95 {np.degrees(np.percentile(np.abs(b_arr),95))*17:.3f} deg")

    # ----- V2: + global steering ratio scaling per platform -----
    # After V1, fit a scalar gain k on (v/L)*tan(delta_road - bias). Equivalent
    # to a steering-ratio correction (i_s_new = i_s_old / k).
    p2 = np.zeros_like(p0)
    gains = {}
    for plat in PLATFORMS:
        m = big["__platform"] == plat
        # Build adjusted delta (post-bias) for this platform
        d_adj_list = []
        for seg, g in big[m].groupby("__seg"):
            d_adj_list.append((g.index.values, g["delta_road_rad"].values - biases[seg]))
        # Compute base pred per-segment with bias only
        v = big.loc[m, "v_mps"].values
        idx_plat = big.index[m].values
        # Use already-built p1 for this subset
        p1_plat = p1[idx_plat]
        y_plat = y[idx_plat]
        denom = float(np.dot(p1_plat, p1_plat))
        k = float(np.dot(p1_plat, y_plat) / denom) if denom > 1e-9 else 1.0
        gains[plat] = k
        p2[idx_plat] = k * p1_plat
    rms2 = rms(y - p2)
    print(f"\nV2 + per-platform yaw-gain k   : {np.degrees(rms2):.4f} deg/s   "
          f"(Δ vs V1 = {np.degrees(rms1-rms2):+.4f} deg/s, "
          f"{100*(rms1-rms2)/rms0:.1f}% of baseline error)")
    for plat, kk in gains.items():
        is_new = IS_BY_PLAT[plat] / kk
        print(f"   {plat}: k = {kk:.4f}  (i_s {IS_BY_PLAT[plat]:.2f} -> {is_new:.2f})")

    # ----- V3: + understeer correction (linear-bicycle yaw gain) -----
    # Replace (v/L)*tan(delta - b) with v*(delta-b)/(L + Kus*v^2),
    # fit Kus per platform on top of V2's k (i.e. on k * (delta - b)).
    p3 = np.zeros_like(p0)
    kus = {}
    for plat in PLATFORMS:
        m = big["__platform"] == plat
        L = L_BY_PLAT[plat]
        v = big.loc[m, "v_mps"].values
        # Build effective delta = gains[plat] * (delta_road - bias)
        d_eff = np.zeros(m.sum())
        idx_local = 0
        # Build via groupby to apply per-segment bias
        starts = []
        # Simpler: rebuild via index alignment
        d_eff = np.zeros_like(v)
        # use p2 as v*delta_eff/L ... so delta_eff = p2 * L / v (for non-zero v).
        # That's a valid recovery since tan(small)≈small for these regimes. To be
        # exact, work in tan-space: tan(delta_eff_road) = k * tan(delta_road - b).
        # Then psi_dot_V2 = (v/L)*tan(delta_eff_road).
        # For V3 we shift to v*tan(delta_eff)/(L+Kus*v^2).
        idx_plat = big.index[m].values
        y_plat = y[idx_plat]
        # tan(delta_eff_road) from V2:
        tan_de = (p2[idx_plat] * L) / np.maximum(v, 1e-3)
        # Equation y = v*tan(delta_eff)/(L + Kus*v^2)
        # => y*(L + Kus*v^2) = v*tan_de
        # => Kus * (y*v^2) = v*tan_de - y*L
        rhs = v * tan_de - y_plat * L
        basis = y_plat * v * v
        denom = float(np.dot(basis, basis))
        kus_p = float(np.dot(basis, rhs) / denom) if denom > 1e-9 else 0.0
        kus[plat] = kus_p
        p3[idx_plat] = v * tan_de / (L + kus_p * v * v)
    rms3 = rms(y - p3)
    print(f"\nV3 + understeer K_us           : {np.degrees(rms3):.4f} deg/s   "
          f"(Δ vs V2 = {np.degrees(rms2-rms3):+.4f} deg/s, "
          f"{100*(rms2-rms3)/rms0:.1f}% of baseline error)")
    for plat, kk in kus.items():
        # Convert Kus to characteristic speed v_ch = sqrt(L/Kus) when Kus>0
        L = L_BY_PLAT[plat]
        if kk > 1e-6:
            vch = float(np.sqrt(L / kk))
            print(f"   {plat}: K_us = {kk:.6f}  (v_char = {vch:.1f} m/s, {vch*3.6:.1f} km/h)")
        else:
            print(f"   {plat}: K_us = {kk:.6f}  (oversteer or negligible)")

    # ----- V4: + steering-to-yaw lag (per-platform integer sample shift) -----
    # Shift the V3 prediction in time. Sample rate 50 Hz -> 20 ms / sample.
    # Per-segment lag estimation could be done; for simplicity per-platform.
    print("\nFitting per-platform integer-sample yaw lag (50 Hz, +/-10 samples)...")
    best_lags = {}
    p4 = p3.copy()
    for plat in PLATFORMS:
        m = big["__platform"] == plat
        idx_plat = big.index[m].values
        y_plat = y[idx_plat]
        pred_plat = p3[idx_plat]
        # We must NOT cross segment boundaries; for simplicity ignore boundary
        # effects (rare relative to corpus size). Search shift k in [-10, +10].
        best = (0, rms(y_plat - pred_plat))
        for k in range(-10, 11):
            if k == 0: continue
            if k > 0:
                r = y_plat[k:] - pred_plat[:-k]
            else:
                kk2 = -k
                r = y_plat[:-kk2] - pred_plat[kk2:]
            s = rms(r)
            if s < best[1]:
                best = (k, s)
        best_lags[plat] = best
        # Apply shift in-place over the platform indices (carry first/last sample)
        k = best[0]
        if k > 0:
            shifted = np.concatenate([pred_plat[:k], pred_plat[:-k]])
        elif k < 0:
            kk2 = -k
            shifted = np.concatenate([pred_plat[kk2:], pred_plat[-kk2:]])
        else:
            shifted = pred_plat
        p4[idx_plat] = shifted

    rms4 = rms(y - p4)
    print(f"V4 + per-platform yaw lag      : {np.degrees(rms4):.4f} deg/s   "
          f"(Δ vs V3 = {np.degrees(rms3-rms4):+.4f} deg/s, "
          f"{100*(rms3-rms4)/rms0:.1f}% of baseline error)")
    for plat, (k, _) in best_lags.items():
        print(f"   {plat}: best lag = {k} samples ({k*20} ms; positive = pred leads meas)")

    # ----- Summary table -----
    print("\n" + "=" * 72)
    print(f"{'Variant':<32s} {'RMS deg/s':>10s} {'Δ deg/s':>10s} {'% of base':>10s}")
    print("=" * 72)
    levels = [
        ("V0 KS baseline (CSV)",           rms0),
        ("V1 + per-seg δ-bias",            rms1),
        ("V2 + per-platform i_s scale",    rms2),
        ("V3 + understeer K_us",           rms3),
        ("V4 + per-platform yaw lag",      rms4),
    ]
    prev = rms0
    for label, r in levels:
        d = prev - r
        pct = 100 * d / rms0
        print(f"{label:<32s} {np.degrees(r):>10.4f} {np.degrees(d):>+10.4f} {pct:>9.1f}%")
        prev = r
    total_pct = 100 * (rms0 - rms4) / rms0
    print("-" * 72)
    print(f"{'TOTAL improvement':<32s} {'':>10s} {np.degrees(rms0-rms4):>+10.4f} {total_pct:>9.1f}%")

    # save JSON
    out = {
        "metric": "RMS yaw-rate residual (deg/s), combined Ford corpus",
        "n_samples": int(n),
        "n_segments": int(big["__seg"].nunique()),
        "V0_baseline_KS": float(np.degrees(rms0)),
        "V1_segment_steering_bias": float(np.degrees(rms1)),
        "V2_per_platform_gain":     float(np.degrees(rms2)),
        "V3_understeer_Kus":        float(np.degrees(rms3)),
        "V4_per_platform_lag":      float(np.degrees(rms4)),
        "gains": gains,
        "Kus":   kus,
        "best_lag_samples": {p: lk[0] for p, lk in best_lags.items()},
    }
    os.makedirs("out", exist_ok=True)
    with open("out/ladder_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote out/ladder_results.json")

if __name__ == "__main__":
    main()
