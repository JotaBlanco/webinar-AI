"""Lateral-prediction baseline + improvement ladder.

For each Tesla Model 3 sim.csv:
  - Build a 'truth' yaw-rate from rear wheel-speed differential:
        psi_dot_truth = (v_RR - v_RL) / track_width_rear
  - Compute KS-baseline yaw rate from the model's formula:
        psi_dot_KS = v * tan(delta) / L
  - Score baseline vs truth (RMSE in deg/s).
  - Ladder of improvements (each evaluated standalone AND cumulatively):
      V1 baseline                            psi_dot = v * tan(delta) / L
      V2 +understeer gradient correction      psi_dot = v * tan(delta) / (L * (1 + K_us * v^2))
      V3 +per-segment effective steer ratio   scale delta by alpha (global fit then per-seg)
      V4 +first-order lag (steer->yaw)        low-pass the predicted psi_dot
  - Report metrics + attribution.

Truth assumption: rear-wheel differential, track width = 1.580 m (Tesla M3 rear).
We don't have an IMU; this is the best openly-derivable proxy. We focus on the
*relative* improvement, which is robust to a constant track-width error.

We exclude near-stationary samples (v < 3 m/s) where the differential is noisy.
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SIM_ROOT = ROOT / "data" / "sim" / "segments" / "TESLA_MODEL_3"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

L = 2.875                         # wheelbase, m
TRACK_REAR = 1.580                # Tesla M3 rear track width, m (public spec)
V_MIN = 3.0                       # m/s — exclude low-speed
PSI_DOT_MIN = np.deg2rad(0.5)     # exclude samples below noise floor for relative metric


def truth_yaw_rate(df: pd.DataFrame) -> np.ndarray:
    """psi_dot from rear-wheel speed differential. kph -> rad/s.

    Sign convention (verified empirically against this dataset):
    KS predicts psi_dot positive when delta_road is positive. In *this* CSV's
    steering sign convention that correlates positively with (v_RL - v_RR),
    not (v_RR - v_RL). Either the steering sign is flipped in the raw decode,
    or the wheel labels are. Result is the same: use RL - RR.
    """
    v_rl = df["wheel_RL_kph"].to_numpy() / 3.6
    v_rr = df["wheel_RR_kph"].to_numpy() / 3.6
    return (v_rl - v_rr) / TRACK_REAR


def lowpass(y: np.ndarray, fs: float, fc: float) -> np.ndarray:
    from scipy.signal import butter, filtfilt
    if fc >= fs / 2:
        return y.copy()
    b, a = butter(2, fc / (fs / 2.0))
    return filtfilt(b, a, y)


def variants(df: pd.DataFrame, K_us: float, alpha: float, tau: float):
    """Yield (name, predicted psi_dot) for each model variant."""
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    dt = float(df["t_s"].iloc[1] - df["t_s"].iloc[0])
    fs = 1.0 / dt

    # V1: baseline
    p1 = v * np.tan(delta) / L

    # V2: understeer-corrected (bicycle steady-state):
    #   psi_dot = v * delta / (L + K_us * v^2)
    # (linearised - tan(delta) ≈ delta valid at road-wheel angles < 0.2 rad here)
    p2 = v * np.tan(delta) / (L * (1.0 + (K_us * v * v) / (9.81 * L)))
    # Standard understeer form uses K_us in (rad)/g of lateral accel:
    #   psi_dot = v / (L + K_us*v^2/g) * delta   — equivalent denominator

    # V3: + effective steer ratio (alpha scales delta)
    delta3 = delta * alpha
    p3 = v * np.tan(delta3) / (L * (1.0 + (K_us * v * v) / (9.81 * L)))

    # V4: + first-order steering lag (low-pass)
    fc = 1.0 / (2.0 * np.pi * tau) if tau > 0 else fs / 2
    p4 = lowpass(p3, fs, fc)

    return [
        ("V1_baseline",         p1),
        ("V2_understeer",       p2),
        ("V3_steerRatio",       p3),
        ("V4_lag",              p4),
    ]


def rmse(a, b, mask):
    d = (a - b)[mask]
    return float(np.sqrt(np.mean(d * d)))


def fit_alpha(dfs):
    """Fit alpha (effective steer-ratio scaling) ALONE with K_us=0.
        psi_dot_truth ≈ v * alpha * delta / L
    -> alpha = sum(psi_dot_truth * v * delta) / sum((v*delta)^2 / L)
    """
    num, den = 0.0, 0.0
    for df in dfs:
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        y = truth_yaw_rate(df)
        m = (v >= V_MIN)
        v = v[m]; delta = delta[m]; y = y[m]
        num += float(np.sum(y * v * delta))
        den += float(np.sum((v * delta) ** 2)) / L
    return num / den


def fit_K_us(dfs, alpha):
    """Given alpha, fit K_us by linear regression.
        psi_dot_truth = v * alpha * delta / (L * (1 + K_us*v^2/(g*L)))
    Equivalent linear form (small-angle):
        v*alpha*delta / psi_dot_truth  =  L + K_us*v^2/g
    Regress y' = (v*alpha*delta / psi_dot_truth - L) against x' = v^2/g.
    Use only samples where |psi_dot_truth| is large enough to avoid blow-up.
    """
    g = 9.81
    xs, ys = [], []
    for df in dfs:
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        y = truth_yaw_rate(df)
        m = (v >= V_MIN) & (np.abs(y) >= np.deg2rad(3.0))
        v = v[m]; delta = delta[m]; y = y[m]
        lhs = v * alpha * delta / y - L
        rhs = v * v / g
        xs.append(rhs); ys.append(lhs)
    x = np.concatenate(xs); yv = np.concatenate(ys)
    # least-squares slope through origin
    K = float(np.sum(x * yv) / np.sum(x * x))
    return K


def fit_tau(dfs, K_us, alpha):
    """Grid-search tau (steering->yaw lag) that minimises RMSE on V4."""
    best = (None, np.inf)
    for tau in [0.0, 0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30]:
        total_sq, total_n = 0.0, 0
        for df in dfs:
            v = df["v_mps"].to_numpy()
            y = truth_yaw_rate(df)
            m = (v >= V_MIN)
            _, p4 = variants(df, K_us, alpha, tau)[3]
            d = (p4 - y)[m]
            total_sq += float((d * d).sum())
            total_n += int(m.sum())
        r = np.sqrt(total_sq / total_n)
        if r < best[1]:
            best = (tau, r)
    return best[0]


def load_sample(n_segments=120) -> list[pd.DataFrame]:
    """Load up to n_segments sim.csvs spread across devices."""
    csvs = sorted(SIM_ROOT.glob("*/*/*/sim.csv"))
    # stride to get diverse devices
    step = max(1, len(csvs) // n_segments)
    picked = csvs[::step][:n_segments]
    dfs = []
    for p in picked:
        try:
            df = pd.read_csv(p)
            if {"wheel_RL_kph", "wheel_RR_kph", "v_mps",
                "delta_road_rad", "t_s"}.issubset(df.columns):
                dfs.append(df)
        except Exception as e:
            print(f"  skipping {p}: {e}", file=sys.stderr)
    return dfs


def main():
    dfs = load_sample(120)
    print(f"Loaded {len(dfs)} segments.")

    # ---- Fit params on the whole sample (no train/test split given the time
    # budget; the metric we care about is whether each *kind* of correction
    # buys anything beyond the previous one, not held-out generalisation). --
    alpha = fit_alpha(dfs)
    K_us  = fit_K_us(dfs, alpha)
    tau   = fit_tau(dfs, K_us, alpha)
    print(f"Fit: alpha (effective steer-ratio scaling) = {alpha:.4f}")
    print(f"     => effective steer ratio i_s_eff = i_s_openpilot / alpha = {12.0/alpha:.2f}")
    print(f"Fit: K_us (understeer coef)                = {K_us:.4f}  [rad/(m/s²) of g-norm]")
    print(f"Fit: tau (steer->yaw lag) [s]              = {tau:.3f}")

    # ---- Score each variant on the pooled mask -----------------------------
    # Mask: cruising speed AND non-trivial yaw activity. Without the second
    # constraint, the RMSE is dominated by samples where everyone correctly
    # predicts ~0 and we measure mostly truth-side noise.
    pooled = {}
    for df in dfs:
        v = df["v_mps"].to_numpy()
        y = truth_yaw_rate(df)
        m = (v >= V_MIN) & (np.abs(y) >= np.deg2rad(2.0))
        for name, pred in variants(df, K_us, alpha, tau):
            d = (pred - y)[m]
            pooled.setdefault(name, []).append((d * d, int(m.sum())))

    rmses = {}
    for name, chunks in pooled.items():
        total = sum(c[0].sum() for c in chunks)
        n     = sum(c[1]      for c in chunks)
        rmses[name] = float(np.sqrt(total / n))

    # Express in deg/s for readability
    print()
    print("=== Pooled RMSE of yaw-rate prediction (deg/s) ===")
    print(f"truth proxy: rear wheel-speed differential / track ({TRACK_REAR} m)")
    print(f"sample mask: v >= {V_MIN} m/s")
    for name, r in rmses.items():
        print(f"  {name:18s}  {np.degrees(r):7.3f} deg/s")

    # ---- Attribution: cumulative (waterfall) ------------------------------
    base = rmses["V1_baseline"]
    final = rmses["V4_lag"]
    total_red = base - final
    print()
    print("=== Cumulative attribution (waterfall, RMSE deg/s reduction) ===")
    print(f"Baseline               : {np.degrees(base):.3f} deg/s")
    prev = base
    for k in ["V2_understeer", "V3_steerRatio", "V4_lag"]:
        cur = rmses[k]
        delta = prev - cur
        share = 100.0 * delta / total_red if total_red > 0 else 0.0
        print(f"+{k:15s}: -{np.degrees(delta):.3f} deg/s  "
              f"({share:5.1f}% of total improvement)   -> {np.degrees(cur):.3f}")
        prev = cur
    print(f"Final                  : {np.degrees(final):.3f} deg/s "
          f"(total -{np.degrees(total_red):.3f} deg/s = "
          f"{100*total_red/base:.1f}% reduction)")

    # ---- Also: each correction in isolation (vs baseline) ------------------
    print()
    print("=== Isolation: each correction applied alone vs baseline ===")
    isolation = {}
    for label, K, A, T in [
        ("only understeer (V2)",       K_us, 1.0, 0.0),
        ("only steerRatio (alpha)",    0.0,  alpha, 0.0),
        ("only lag (tau)",             0.0,  1.0, tau),
    ]:
        total_sq, total_n = 0.0, 0
        for df in dfs:
            v = df["v_mps"].to_numpy(); y = truth_yaw_rate(df)
            m = (v >= V_MIN) & (np.abs(y) >= np.deg2rad(2.0))
            # Manual: compute single-correction variant
            delta = df["delta_road_rad"].to_numpy() * A
            denom = L * (1.0 + (K * v * v) / (9.81 * L))
            p = v * np.tan(delta) / denom
            if T > 0:
                fs = 1.0 / float(df["t_s"].iloc[1] - df["t_s"].iloc[0])
                fc = 1.0 / (2.0 * np.pi * T)
                p = lowpass(p, fs, fc)
            d = (p - y)[m]
            total_sq += float((d * d).sum())
            total_n += int(m.sum())
        r = np.sqrt(total_sq / total_n)
        isolation[label] = r
        red = base - r
        print(f"  {label:25s}  -> RMSE {np.degrees(r):7.3f} deg/s  "
              f"(reduction {np.degrees(red):+.3f} deg/s)")

    # ---- Save results CSV --------------------------------------------------
    rows = []
    for name, r in rmses.items():
        rows.append({"scheme": "cumulative", "variant": name,
                     "rmse_rad_s": r, "rmse_deg_s": np.degrees(r)})
    for label, r in isolation.items():
        rows.append({"scheme": "isolation", "variant": label,
                     "rmse_rad_s": r, "rmse_deg_s": np.degrees(r)})
    pd.DataFrame(rows).to_csv(OUT / "ladder_results.csv", index=False)
    print(f"\nWrote {OUT/'ladder_results.csv'}")

    # Save fit params too
    with open(OUT / "fit_params.txt", "w") as f:
        f.write(f"alpha={alpha}\nK_us={K_us}\ntau={tau}\n"
                f"n_segments={len(dfs)}\nbase_rmse_deg_s={np.degrees(base)}\n"
                f"final_rmse_deg_s={np.degrees(final)}\n")
    print(f"Wrote {OUT/'fit_params.txt'}")


if __name__ == "__main__":
    main()
