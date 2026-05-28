"""Lateral-prediction improvement ladder.

Headline metric: yaw-rate RMS residual (rad/s) across all Ford segments
(Mach-E + F-150 Lightning), with basic data hygiene applied (v > 2 m/s,
finite values, |a_lat_meas| < 20 m/s²).

We don't re-run the integrator (it's just psi_dot = (v/L)tan(delta) under
the speed-known clamps). We compute prediction in pandas from the columns
already in the CSV and iterate the model:

  V0 baseline:            psi_dot = (v / L) * tan(delta)
  V1 hygiene:             same model, evaluated on a clean subset
  V2 steer bias:          psi_dot = (v / L) * tan(delta - delta_bias),
                          delta_bias = least-squares minimiser on training half
  V3 time-align:          shift delta by tau samples to minimise residual
                          (50 Hz; tau in [-10, +10] samples = ±200 ms)
  V4 effective-wheelbase: psi_dot = (v / L_eff) * tan(delta - bias),
                          L_eff = L * (1 + K_us * v^2) understeer gradient
                          fit jointly with bias

Attribution scheme: sequential / left-to-right. Each row reports the RMS
after applying THAT improvement on top of all previous ones. The
"contribution" column is the drop relative to the previous row.

Train/test split: per-segment 50/50 by time. Parameters fit on first half,
metric reported on second half (so improvements that just memorise noise
don't pay off).
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-04/data/sim/segments")
PLATFORMS = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}
DT = 0.02  # 50 Hz

def load_all_clean():
    rows = []
    for plat, L in PLATFORMS.items():
        for c in sorted(ROOT.joinpath(plat).rglob("sim.csv")):
            df = pd.read_csv(c, usecols=[
                "t_s","delta_road_rad","v_mps",
                "a_lat_meas_mps2","yaw_rate_meas_rads",
                "yaw_rate_pred_rads",
            ])
            df["L"] = L
            df["platform"] = plat
            df["seg"] = str(c.relative_to(ROOT / plat).parent)
            rows.append(df)
    big = pd.concat(rows, ignore_index=True)
    finite = np.isfinite(big[["delta_road_rad","v_mps","yaw_rate_meas_rads","a_lat_meas_mps2"]]).all(axis=1)
    big = big[finite].copy()
    return big

def mask_hygiene(df):
    """Reasonable physics: moving, sane lateral telemetry."""
    return (
        (df["v_mps"] > 2.0) &
        (df["a_lat_meas_mps2"].abs() < 20.0) &
        (df["yaw_rate_meas_rads"].abs() < 2.0)
    )

def split_train_test(df):
    """Per-segment 50/50 split by time."""
    df = df.copy()
    # rank within (platform, seg) by t_s
    df["rank"] = df.groupby(["platform","seg"])["t_s"].rank(method="first")
    df["n"] = df.groupby(["platform","seg"])["t_s"].transform("size")
    df["is_train"] = df["rank"] <= df["n"] / 2.0
    return df

def rms(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    return float(np.sqrt(np.mean(x ** 2)))

def predict_baseline(df, delta_bias=0.0, L_scale=1.0, K_us=0.0, tau_samples=0):
    """
    psi_dot = (v / (L*L_scale*(1+K_us*v^2))) * tan(delta_shifted - delta_bias)
    delta_shifted = delta lag by tau samples (per segment)
    """
    delta = df["delta_road_rad"].values
    if tau_samples != 0:
        # shift within each segment so we don't cross boundaries
        delta = df.groupby(["platform","seg"])["delta_road_rad"].shift(tau_samples).values
    v = df["v_mps"].values
    L = df["L"].values
    L_eff = L * L_scale * (1.0 + K_us * v * v)
    return (v / L_eff) * np.tan(delta - delta_bias)

def fit_delta_bias(df):
    """Minimise sum (psi_dot_meas - (v/L) tan(delta - b))^2 over b.
    Linearise: for small delta, tan(delta-b) ≈ tan(delta) - b*sec²(delta).
    => residual_after = residual_before + b * (v/L) * sec²(delta)
       so b = sum(resid * coef) / sum(coef²)
    """
    delta = df["delta_road_rad"].values
    v = df["v_mps"].values
    L = df["L"].values
    yaw = df["yaw_rate_meas_rads"].values
    sec2 = 1.0 / np.cos(delta) ** 2
    coef = (v / L) * sec2
    pred0 = (v / L) * np.tan(delta)
    resid0 = yaw - pred0
    # yaw ≈ pred0 - b * coef  =>  resid0 ≈ -b * coef => b = -sum(resid0*coef)/sum(coef^2)
    b = -float(np.sum(resid0 * coef) / np.sum(coef * coef))
    return b

def fit_tau(df_train, b):
    """Best integer-sample shift in [-10, +10]. Apply per segment.
    delta lagged by k samples means delta[t] := delta[t-k]. We want yaw lag delta
    by ~50-100 ms (steering -> response). Test grid.
    """
    best = (0, np.inf)
    for k in range(-10, 11):
        pred = predict_baseline(df_train, delta_bias=b, tau_samples=k)
        r = df_train["yaw_rate_meas_rads"].values - pred
        m = np.isfinite(r)
        score = float(np.sqrt(np.mean(r[m] ** 2)))
        if score < best[1]:
            best = (k, score)
    return best[0]

def fit_kus_and_bias(df, tau):
    """Joint fit of b and K_us in: yaw = (v / (L*(1+K_us v^2))) tan(delta - b)
    Linearise: pred ≈ (v/L) tan(delta) - b (v/L) sec²(delta) - K_us v² (v/L) tan(delta).
    Let p0 = (v/L) tan(delta).
    Features: phi1 = (v/L) sec²(delta) ; phi2 = v² * p0
    yaw - p0 = -b * phi1 - K_us * phi2   =>  least squares.
    """
    if tau != 0:
        delta = df.groupby(["platform","seg"])["delta_road_rad"].shift(tau).values
    else:
        delta = df["delta_road_rad"].values
    v = df["v_mps"].values
    L = df["L"].values
    yaw = df["yaw_rate_meas_rads"].values
    mask = np.isfinite(delta)
    delta = delta[mask]; v = v[mask]; L = L[mask]; yaw = yaw[mask]
    p0 = (v / L) * np.tan(delta)
    phi1 = (v / L) / np.cos(delta) ** 2
    phi2 = (v * v) * p0
    y = yaw - p0
    A = np.column_stack([-phi1, -phi2])
    # Solve A @ [b, K_us] = y
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return float(coef[0]), float(coef[1])

# ------------------------------ pipeline ------------------------------

def report():
    print("Loading ...")
    big = load_all_clean()
    print(f"Loaded {len(big):,} rows, {big['seg'].nunique()} segments, "
          f"platforms: {big['platform'].unique().tolist()}")

    # V0: report on raw (no hygiene)
    yaw_meas = big["yaw_rate_meas_rads"].values
    pred0 = predict_baseline(big)
    rms_v0 = rms(yaw_meas - pred0)
    print(f"\nV0 baseline (all rows, no hygiene):  yaw-rate RMS = {rms_v0:.5f} rad/s "
          f"({np.degrees(rms_v0):.3f}°/s)")

    # V1: hygiene mask
    m = mask_hygiene(big)
    clean = big[m].copy()
    pred1 = predict_baseline(clean)
    rms_v1 = rms(clean["yaw_rate_meas_rads"].values - pred1)
    print(f"\nV1 + data hygiene (v>2, sane telemetry):  rows {len(clean):,}/{len(big):,}, "
          f"RMS = {rms_v1:.5f} rad/s ({np.degrees(rms_v1):.3f}°/s)")

    # Train/test split for the model parameters
    clean = split_train_test(clean)
    train = clean[clean["is_train"]].copy()
    test = clean[~clean["is_train"]].copy()

    # V2: fit steering bias on train, evaluate on test
    b = fit_delta_bias(train)
    pred2_test = predict_baseline(test, delta_bias=b)
    rms_v2 = rms(test["yaw_rate_meas_rads"].values - pred2_test)
    # for fair comparison, also evaluate V1 on the same test subset
    pred1_test = predict_baseline(test)
    rms_v1_test = rms(test["yaw_rate_meas_rads"].values - pred1_test)
    print(f"\n   (train/test split: train={len(train):,}, test={len(test):,})")
    print(f"V1 (test only) RMS = {rms_v1_test:.5f}")
    print(f"V2 + steer-bias (b={np.degrees(b):.3f}° road = {np.degrees(b*16):.2f}° wheel): "
          f"RMS = {rms_v2:.5f}  Δ={rms_v1_test - rms_v2:+.5f}")

    # V3: time-align tau
    tau = fit_tau(train, b)
    pred3_test = predict_baseline(test, delta_bias=b, tau_samples=tau)
    rms_v3 = rms(test["yaw_rate_meas_rads"].values - pred3_test)
    print(f"V3 + time-align tau={tau} samples ({tau*DT*1000:.0f} ms): "
          f"RMS = {rms_v3:.5f}  Δ={rms_v2 - rms_v3:+.5f}")

    # V4: K_us understeer + re-fit b (joint)
    b2, kus = fit_kus_and_bias(train, tau)
    pred4_test = predict_baseline(test, delta_bias=b2, K_us=kus, tau_samples=tau)
    rms_v4 = rms(test["yaw_rate_meas_rads"].values - pred4_test)
    print(f"V4 + understeer K_us={kus:.5e} s²/m², refit b={np.degrees(b2):.3f}°: "
          f"RMS = {rms_v4:.5f}  Δ={rms_v3 - rms_v4:+.5f}")

    print(f"\n--- Attribution (sequential, all on TEST set) ---")
    rows = [
        ("V1 hygiene (drop stationary/glitched rows)", rms_v0, rms_v1_test),
        ("V2 steering-bias correction",                 rms_v1_test, rms_v2),
        ("V3 transport-lag (delta -> yaw)",             rms_v2, rms_v3),
        ("V4 understeer gradient + refit bias",         rms_v3, rms_v4),
    ]
    total_drop = rms_v0 - rms_v4
    print(f"{'step':<46} {'RMS_before':>10} {'RMS_after':>10} {'drop':>10} {'%':>7}")
    for name, before, after in rows:
        drop = before - after
        pct = 100.0 * drop / total_drop if total_drop > 0 else 0.0
        print(f"{name:<46} {before:10.5f} {after:10.5f} {drop:+10.5f} {pct:7.1f}%")
    print(f"{'TOTAL':<46} {rms_v0:10.5f} {rms_v4:10.5f} {total_drop:+10.5f} {100.0:7.1f}%")
    print(f"\nBaseline (V0): {rms_v0:.5f} rad/s = {np.degrees(rms_v0):.3f} °/s")
    print(f"Final    (V4): {rms_v4:.5f} rad/s = {np.degrees(rms_v4):.3f} °/s")
    print(f"Total improvement: {100.0 * total_drop / rms_v0:.1f}% reduction in RMS")

    # also per-platform final
    print("\n--- Per-platform on test, final V4 ---")
    for plat in PLATFORMS:
        sub = test[test["platform"] == plat]
        if not len(sub): continue
        pred = predict_baseline(sub, delta_bias=b2, K_us=kus, tau_samples=tau)
        r = sub["yaw_rate_meas_rads"].values - pred
        print(f"  {plat}: RMS={rms(r):.5f} ({np.degrees(rms(r)):.3f}°/s)  rows={len(sub):,}")

if __name__ == "__main__":
    report()
