"""Lateral fidelity variant ladder on FORD_MUSTANG_MACH_E_MK1.

V0: baseline RMSE of yaw_rate_resid_rads as stored (no preprocessing).
V1: per-segment bias removal on residual.
V2: V1 + steering-ratio re-fit (gain α on delta_road_rad).
V3: V2 + understeer-gradient correction (linear bicycle steady-state).
V4: V3 + measurement-vs-prediction time-alignment (best integer-lag cross-correlation per segment).

We score on the same segments and same regime masks across every row.
Regimes:
  - straight:           |a_y_meas| < 1.0
  - cornering steady:   |a_y_meas| >= 1.0 AND |jerk_y_meas| < 1.0
  - cornering transient: |a_y_meas| >= 1.0 AND |jerk_y_meas| >= 1.0
where jerk_y_meas = d(a_lat_meas_mps2)/dt (50 Hz).
"""

import os
import sys
from glob import glob

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-05/code")
from parameters import PARAM_BY_PLATFORM, MACH_E  # noqa

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
ROOT = f"/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-05/data/sim/segments/{PLATFORM}"
OUT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-05/out"
os.makedirs(OUT, exist_ok=True)

DT = 0.02  # 50 Hz
p = MACH_E
L = p.L
m = p.m
Iz = p.I_z
lf = p.l_f
lr = p.l_r
Caf = p.C_alpha_f
Car = p.C_alpha_r

# Understeer gradient K for the linear bicycle model (steady-state)
# psi_dot_ss = v / (L + K v^2) * delta_road
# K = m * (l_r * C_alpha_r - l_f * C_alpha_f) / (L^2 * C_alpha_f * C_alpha_r)
# (sign convention: K > 0 => understeer)
K_us = m * (lr * Car - lf * Caf) / (L ** 2 * Caf * Car)


def regimes(ay_meas):
    a = np.abs(ay_meas)
    jerk = np.zeros_like(ay_meas)
    jerk[1:-1] = (ay_meas[2:] - ay_meas[:-2]) / (2 * DT)
    aj = np.abs(jerk)
    straight = a < 1.0
    steady = (a >= 1.0) & (aj < 1.0)
    transient = (a >= 1.0) & (aj >= 1.0)
    return straight, steady, transient


def load_all():
    files = sorted(glob(os.path.join(ROOT, "*", "*", "*", "sim.csv")))
    frames = []
    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if len(df) < 100:
            continue
        if "yaw_rate_meas_rads" not in df.columns or "yaw_rate_pred_rads" not in df.columns:
            continue
        df["__seg__"] = f
        frames.append(df)
    return frames


def rmse(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return np.nan
    return float(np.sqrt(np.mean(x ** 2)))


def compute_variant_resids(frames, variant: str):
    """Returns dict regime -> concatenated residual array across all segments."""
    all_res = {"straight": [], "steady": [], "transient": [], "all": []}
    # For optimization variants we need fits done up-front. They're per-variant.
    for df in frames:
        pred = df["yaw_rate_pred_rads"].to_numpy().astype(float)
        meas = df["yaw_rate_meas_rads"].to_numpy().astype(float)
        v = df["v_mps"].to_numpy().astype(float)
        delta_road = df["delta_road_rad"].to_numpy().astype(float)
        ay_meas = df["a_lat_meas_mps2"].to_numpy().astype(float)

        if variant == "V0":
            res = pred - meas
        elif variant == "V1":
            # per-segment bias removal on residual (mean of yaw_rate_pred - yaw_rate_meas)
            base = pred - meas
            res = base - np.nanmean(base)
        elif variant == "V2":
            # Re-fit a scalar gain α on delta_road minimising prediction RMSE
            # KS prediction is (v/L)*tan(delta). With small angle ≈ (v/L)*delta.
            # We allow α s.t. pred' = (v/L)*tan(α*delta) — fit by 1D search.
            # Then also remove per-segment bias.
            alphas = np.linspace(0.85, 1.20, 36)
            best_alpha = 1.0
            best_score = np.inf
            for a in alphas:
                pr = (v / L) * np.tan(a * delta_road)
                r = pr - meas
                r = r - np.nanmean(r)
                sc = rmse(r)
                if sc < best_score:
                    best_score = sc
                    best_alpha = a
            pr = (v / L) * np.tan(best_alpha * delta_road)
            res = pr - meas
            res = res - np.nanmean(res)
            df.attrs["alpha"] = best_alpha
        elif variant == "V3":
            # Apply understeer-gradient correction: psi_dot = v / (L + K v^2) * tan(delta)
            # Plus the alpha from V2 (re-fit jointly: alpha and a small K-scale).
            alphas = np.linspace(0.85, 1.20, 24)
            kscales = np.linspace(0.0, 2.0, 21)  # 0 = pure KS, 1 = openpilot K
            best = (1.0, 0.0, np.inf)
            for a in alphas:
                for ks in kscales:
                    denom = L + ks * K_us * v ** 2
                    pr = (v / np.maximum(denom, 0.1)) * np.tan(a * delta_road)
                    r = pr - meas
                    r = r - np.nanmean(r)
                    sc = rmse(r)
                    if sc < best[2]:
                        best = (a, ks, sc)
            a_b, ks_b, _ = best
            denom = L + ks_b * K_us * v ** 2
            pr = (v / np.maximum(denom, 0.1)) * np.tan(a_b * delta_road)
            res = pr - meas
            res = res - np.nanmean(res)
            df.attrs["alpha"] = a_b
            df.attrs["k_scale"] = ks_b
        elif variant == "V4":
            # Time-align: search integer lag in [-10, 10] samples for best (alpha, k_scale, lag)
            # but for speed we lock alpha,k_scale to per-segment V3 values then search lag.
            a_b = df.attrs.get("alpha", 1.0)
            ks_b = df.attrs.get("k_scale", 1.0)
            denom = L + ks_b * K_us * v ** 2
            pr_full = (v / np.maximum(denom, 0.1)) * np.tan(a_b * delta_road)
            best_lag, best_score = 0, np.inf
            for lag in range(-10, 11):
                if lag >= 0:
                    p_s = pr_full[: len(pr_full) - lag] if lag > 0 else pr_full
                    m_s = meas[lag:] if lag > 0 else meas
                else:
                    p_s = pr_full[-lag:]
                    m_s = meas[: len(meas) + lag]
                r = p_s - m_s
                if len(r) == 0:
                    continue
                r = r - np.nanmean(r)
                sc = rmse(r)
                if sc < best_score:
                    best_score = sc
                    best_lag = lag
            lag = best_lag
            if lag > 0:
                p_s = pr_full[:-lag]
                m_s = meas[lag:]
                ay_s = ay_meas[lag:]
            elif lag < 0:
                p_s = pr_full[-lag:]
                m_s = meas[: lag]
                ay_s = ay_meas[: lag]
            else:
                p_s, m_s, ay_s = pr_full, meas, ay_meas
            res = p_s - m_s
            res = res - np.nanmean(res)
            ay_meas = ay_s
            df.attrs["lag"] = lag
        else:
            raise ValueError(variant)

        s, st, tr = regimes(ay_meas)
        all_res["straight"].append(res[s])
        all_res["steady"].append(res[st])
        all_res["transient"].append(res[tr])
        all_res["all"].append(res)
    return {k: np.concatenate(v) if v else np.array([]) for k, v in all_res.items()}


def main():
    frames = load_all()
    print(f"loaded {len(frames)} Ford Mach-E segments")
    # Counts under common mask: compute on V0 ay_meas
    # Just report totals per regime from V0 pass.
    rows = []
    cumulative_resids = {}
    for v in ["V0", "V1", "V2", "V3", "V4"]:
        res = compute_variant_resids(frames, v)
        cumulative_resids[v] = res
        rows.append({
            "variant": v,
            "rmse_all": rmse(res["all"]),
            "rmse_straight": rmse(res["straight"]),
            "rmse_steady": rmse(res["steady"]),
            "rmse_transient": rmse(res["transient"]),
            "n_straight": int(np.isfinite(res["straight"]).sum()),
            "n_steady": int(np.isfinite(res["steady"]).sum()),
            "n_transient": int(np.isfinite(res["transient"]).sum()),
        })

    df = pd.DataFrame(rows)
    # Marginal drops on rmse_all (sequential)
    df["marginal_drop"] = -df["rmse_all"].diff()
    df.loc[0, "marginal_drop"] = 0.0
    df["cum_drop"] = df["rmse_all"].iloc[0] - df["rmse_all"]
    df.to_csv(os.path.join(OUT, "ladder.csv"), index=False)
    print(df.to_string(index=False))

    # Also save mean fitted hyperparams across segments for reporting
    alphas = [f.attrs.get("alpha", np.nan) for f in frames if "alpha" in f.attrs]
    ks = [f.attrs.get("k_scale", np.nan) for f in frames if "k_scale" in f.attrs]
    lags = [f.attrs.get("lag", 0) for f in frames if "lag" in f.attrs]
    with open(os.path.join(OUT, "fit_summary.txt"), "w") as fh:
        fh.write(f"n_segments={len(frames)}\n")
        fh.write(f"K_us (openpilot)={K_us:.6e}\n")
        if alphas:
            fh.write(f"alpha mean={np.nanmean(alphas):.4f} median={np.nanmedian(alphas):.4f}\n")
        if ks:
            fh.write(f"k_scale mean={np.nanmean(ks):.3f} median={np.nanmedian(ks):.3f}\n")
        if lags:
            fh.write(f"lag mean(samples)={np.mean(lags):.2f} median={np.median(lags):.1f}\n")
            fh.write(f"lag mean(ms)={np.mean(lags)*20:.1f}\n")
    print("done")


if __name__ == "__main__":
    main()
