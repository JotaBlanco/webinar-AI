"""Cleaner lateral-prediction ladder + Shapley attribution.

Truth: psi_dot estimated from rear wheel-speed differential
       (RL - RR) / track_rear, sign-aligned with the KS convention used
       in the existing sim CSVs.

Mask: v >= 5 m/s AND |truth| >= 2 deg/s  (cornering activity)

Variants (all evaluated independently; combined via Shapley):
  C1 - effective steer-ratio (alpha):       delta_eff = alpha * delta
  C2 - understeer gradient (Ku, fitted):    psi_dot *= 1 / (1 + Ku * v^2 / (g*L))
  C3 - steer->yaw lag (tau):                low-pass psi_dot with tau

Base model:
  psi_dot = v * tan(delta) / L                 (CommonRoad KS, the existing one)

We Shapley-decompose the total RMSE reduction over the power set of {C1,C2,C3}.
"""
from __future__ import annotations
from pathlib import Path
import itertools
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SIM_ROOT = ROOT / "data" / "sim" / "segments" / "TESLA_MODEL_3"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

L = 2.875
TRACK_REAR = 1.580
G = 9.81
V_MIN = 5.0
Y_MIN_DEG = 2.0


def truth_psi_dot(df):
    v_rl = df["wheel_RL_kph"].to_numpy() / 3.6
    v_rr = df["wheel_RR_kph"].to_numpy() / 3.6
    return (v_rl - v_rr) / TRACK_REAR


def lowpass(y, fs, fc):
    from scipy.signal import butter, filtfilt
    if fc >= fs / 2:
        return y.copy()
    b, a = butter(2, fc / (fs / 2.0))
    return filtfilt(b, a, y)


def predict(df, alpha=1.0, Ku=0.0, tau=0.0):
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    delta_eff = alpha * delta
    denom = L * (1.0 + (Ku * v * v) / (G * L))
    p = v * np.tan(delta_eff) / denom
    if tau > 0:
        dt = float(df["t_s"].iloc[1] - df["t_s"].iloc[0])
        fs = 1.0 / dt
        fc = 1.0 / (2.0 * np.pi * tau)
        p = lowpass(p, fs, fc)
    return p


def mask(df, y_truth):
    v = df["v_mps"].to_numpy()
    return (v >= V_MIN) & (np.abs(y_truth) >= np.deg2rad(Y_MIN_DEG))


def pooled_rmse(dfs, **kwargs):
    sq, n = 0.0, 0
    for df in dfs:
        y = truth_psi_dot(df)
        m = mask(df, y)
        p = predict(df, **kwargs)
        d = (p - y)[m]
        sq += float((d * d).sum()); n += int(m.sum())
    return float(np.sqrt(sq / n))


def fit_alpha(dfs):
    """Min RMSE of (alpha * v * delta / L) on activity-masked samples."""
    num, den = 0.0, 0.0
    for df in dfs:
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        y = truth_psi_dot(df)
        m = mask(df, y)
        v = v[m]; delta = delta[m]; y = y[m]
        # base predictor with alpha=1: p0 = v*tan(delta)/L. Linear in alpha (small angle):
        p0 = v * delta / L
        num += float(np.sum(y * p0))
        den += float(np.sum(p0 * p0))
    return num / den


def fit_Ku_given_alpha(dfs, alpha):
    """Grid + golden search over Ku >= 0 to minimise RMSE with alpha fixed."""
    candidates = np.linspace(0.0, 0.05, 26)  # rad/(m/s² of g)
    best = (0.0, np.inf)
    for k in candidates:
        r = pooled_rmse(dfs, alpha=alpha, Ku=float(k))
        if r < best[1]:
            best = (float(k), r)
    return best[0]


def fit_tau_given_alpha_Ku(dfs, alpha, Ku):
    best = (0.0, np.inf)
    for tau in [0.0, 0.02, 0.04, 0.06, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25, 0.3]:
        r = pooled_rmse(dfs, alpha=alpha, Ku=Ku, tau=tau)
        if r < best[1]:
            best = (tau, r)
    return best[0]


def load(n=120):
    csvs = sorted(SIM_ROOT.glob("*/*/*/sim.csv"))
    step = max(1, len(csvs) // n)
    dfs = []
    for p in csvs[::step][:n]:
        try:
            df = pd.read_csv(p)
            if {"wheel_RL_kph","wheel_RR_kph","v_mps","delta_road_rad","t_s"}.issubset(df.columns):
                dfs.append(df)
        except Exception:
            pass
    return dfs


def main():
    dfs = load(120)
    print(f"Loaded {len(dfs)} Tesla Model 3 segments.")
    print(f"Truth: (v_RL - v_RR)/{TRACK_REAR} m   [no IMU available]")
    print(f"Mask:  v >= {V_MIN} m/s   AND   |psi_dot_truth| >= {Y_MIN_DEG} deg/s")
    print()

    # Baseline (no corrections)
    base = pooled_rmse(dfs)
    print(f"Baseline (KS as-shipped):       {np.degrees(base):7.3f} deg/s RMSE")

    # Fit
    alpha = fit_alpha(dfs)
    Ku    = fit_Ku_given_alpha(dfs, alpha)
    tau   = fit_tau_given_alpha_Ku(dfs, alpha, Ku)
    print(f"\nFitted parameters")
    print(f"  alpha (steer-ratio scale)   = {alpha:.4f}   "
          f"(=> i_s_eff = 12.0/alpha = {12.0/alpha:.2f}, vs openpilot 12.0)")
    print(f"  Ku    (understeer, g-norm)  = {Ku:.5f}")
    print(f"  tau   (steer->yaw lag)      = {tau:.3f} s")

    # All subsets
    corrections = {"C1_alpha": dict(alpha=alpha),
                   "C2_Ku":    dict(Ku=Ku),
                   "C3_tau":   dict(tau=tau)}
    keys = list(corrections.keys())

    def kwargs_for(subset):
        kw = {}
        for k in subset:
            kw.update(corrections[k])
        return kw

    subset_rmse = {}
    for r in range(0, 4):
        for s in itertools.combinations(keys, r):
            subset_rmse[frozenset(s)] = pooled_rmse(dfs, **kwargs_for(s))

    print("\nRMSE over all subsets of corrections (deg/s):")
    for s, r in sorted(subset_rmse.items(), key=lambda kv: len(kv[0])):
        nm = "{" + ", ".join(sorted(s)) + "}" if s else "{}"
        print(f"  {nm:35s}  {np.degrees(r):7.3f}")

    # Shapley attribution on RMSE-reduction
    # phi_i = sum_{S not containing i} |S|! (n-|S|-1)!/n! * (RMSE(S) - RMSE(S U {i}))
    import math
    n = len(keys)
    phi = {k: 0.0 for k in keys}
    for k in keys:
        for r in range(n):
            for s in itertools.combinations([x for x in keys if x != k], r):
                S = frozenset(s)
                Si = S | {k}
                weight = math.factorial(r) * math.factorial(n - r - 1) / math.factorial(n)
                phi[k] += weight * (subset_rmse[S] - subset_rmse[Si])

    total = subset_rmse[frozenset()] - subset_rmse[frozenset(keys)]
    print(f"\nTotal RMSE reduction (baseline -> full): {np.degrees(total):.3f} deg/s "
          f"({100*total/subset_rmse[frozenset()]:.1f}%)")
    print(f"\nShapley attribution (deg/s reduction, normalised share):")
    for k, val in phi.items():
        share = 100 * val / total if total != 0 else 0.0
        print(f"  {k:10s}  {np.degrees(val):+.3f} deg/s   ({share:+5.1f}%)")

    # Save
    rows = []
    for s, r in subset_rmse.items():
        rows.append({"subset": "+".join(sorted(s)) or "baseline",
                     "rmse_deg_s": np.degrees(r)})
    pd.DataFrame(rows).to_csv(OUT / "subset_rmse.csv", index=False)

    with open(OUT / "shapley.txt", "w") as f:
        f.write(f"alpha={alpha}\nKu={Ku}\ntau={tau}\n")
        f.write(f"baseline_rmse_deg_s={np.degrees(base)}\n")
        f.write(f"full_rmse_deg_s={np.degrees(subset_rmse[frozenset(keys)])}\n")
        for k, val in phi.items():
            f.write(f"shapley_{k}_deg_s={np.degrees(val)}\n")
    print(f"\nWrote {OUT/'subset_rmse.csv'} and {OUT/'shapley.txt'}")


if __name__ == "__main__":
    main()
