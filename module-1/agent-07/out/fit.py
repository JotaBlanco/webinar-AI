"""Fit per-platform corrections, with cross-validation on segments.

Model variants:
  V0 (KS):       psi_dot = (v/L) * tan(delta)
  V1 (understeer): psi_dot = gain * v * delta / (L + K * v^2)
  V2 (lag+understeer): same with low-pass-filtered delta (single-pole, tau)
  V3 (linear correction): psi_dot = a * (v/L)*tan(delta) + b*v*delta + c
"""
import sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

DATA = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-07/data/sim/segments")

WHEELBASE = {
    "TESLA_MODEL_3": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5": 3.00,
}

def truth_col_for(df):
    if "yaw_rate_meas_rads" in df.columns:
        return "yaw_rate_meas_rads"
    return "psi_dot_rads"  # Tesla older schema

def load_segments(plat, max_segs=None):
    files = sorted(glob.glob(str(DATA / plat / "*/*/*/sim.csv")))
    if max_segs:
        files = files[:max_segs]
    segs = []
    for f in files:
        d = pd.read_csv(f)
        d["__file__"] = f
        segs.append(d)
    return segs

def first_order_lp(x, tau, dt):
    """Single-pole low-pass: y[k] = a*y[k-1] + (1-a)*x[k], a=exp(-dt/tau)."""
    if tau <= 1e-4:
        return x.copy()
    a = np.exp(-dt / tau)
    y = np.empty_like(x)
    y[0] = x[0]
    for k in range(1, len(x)):
        y[k] = a * y[k - 1] + (1 - a) * x[k]
    return y

def rmse(p, t):
    return float(np.sqrt(np.mean((p - t) ** 2)))

def fit_understeer(segs, L):
    """Fit gain, K on all data: psi_dot = gain*v*delta/(L + K*v^2)."""
    d_all, v_all, t_all = [], [], []
    for d in segs:
        tcol = truth_col_for(d)
        m = d["v_mps"].values > 2.0
        d_all.append(d["delta_road_rad"].values[m])
        v_all.append(d["v_mps"].values[m])
        t_all.append(d[tcol].values[m])
    d_all = np.concatenate(d_all); v_all = np.concatenate(v_all); t_all = np.concatenate(t_all)
    def res(p):
        K, gain = p
        return gain * v_all * d_all / (L + K * v_all * v_all) - t_all
    sol = least_squares(res, [0.003, 1.0])
    return float(sol.x[0]), float(sol.x[1])

def fit_understeer_lag(segs, L):
    """Joint fit of K, gain, tau by minimising RMSE over per-segment time series."""
    # Pre-extract
    arrs = []
    for d in segs:
        tcol = truth_col_for(d)
        t = d["t_s"].values
        delta = d["delta_road_rad"].values
        v = d["v_mps"].values
        truth = d[tcol].values
        # Estimate dt
        dt = float(np.median(np.diff(t))) if len(t) > 1 else 0.02
        arrs.append((delta, v, truth, dt))

    def all_residuals(p):
        K, gain, tau = p
        out = []
        for delta, v, truth, dt in arrs:
            d_lp = first_order_lp(delta, tau, dt)
            pred = gain * v * d_lp / (L + K * v * v)
            m = v > 2.0
            out.append(pred[m] - truth[m])
        return np.concatenate(out)

    sol = least_squares(all_residuals, [0.003, 1.0, 0.05], bounds=([0.0, 0.5, 0.0], [0.05, 1.5, 1.0]))
    return float(sol.x[0]), float(sol.x[1]), float(sol.x[2])

def eval_models(segs, L, K, gain, tau, label):
    """Compute RMSE of each model variant across segments."""
    rmses = {"V0_KS": [], "V1_ust": [], "V2_ust_lag": []}
    n = 0
    for d in segs:
        tcol = truth_col_for(d)
        t = d["t_s"].values
        delta = d["delta_road_rad"].values
        v = d["v_mps"].values
        truth = d[tcol].values
        dt = float(np.median(np.diff(t))) if len(t) > 1 else 0.02

        v0 = (v / L) * np.tan(delta)
        v1 = gain * v * delta / (L + K * v * v)
        d_lp = first_order_lp(delta, tau, dt)
        v2 = gain * v * d_lp / (L + K * v * v)

        rmses["V0_KS"].append(((v0 - truth) ** 2).sum())
        rmses["V1_ust"].append(((v1 - truth) ** 2).sum())
        rmses["V2_ust_lag"].append(((v2 - truth) ** 2).sum())
        n += len(truth)
    out = {k: float(np.sqrt(sum(v) / n)) for k, v in rmses.items()}
    print(f"  [{label}] n={n}  RMSE: V0={out['V0_KS']:.5f}  V1={out['V1_ust']:.5f}  V2={out['V2_ust_lag']:.5f}")
    return out


def main():
    coeffs = {}
    summary = {}
    for plat, L in WHEELBASE.items():
        print(f"\n=== {plat}  L={L} ===")
        segs = load_segments(plat)
        # 80/20 split deterministically (file order)
        nsplit = int(0.8 * len(segs))
        train = segs[:nsplit]
        test = segs[nsplit:]
        print(f"  train={len(train)}  test={len(test)}")
        K1, gain1 = fit_understeer(train, L)
        print(f"  understeer-only fit:  K={K1:.6f}  gain={gain1:.4f}")
        try:
            K2, gain2, tau2 = fit_understeer_lag(train, L)
            print(f"  +lag fit:  K={K2:.6f}  gain={gain2:.4f}  tau={tau2:.4f}")
        except Exception as e:
            print(f"  +lag failed: {e}")
            K2, gain2, tau2 = K1, gain1, 0.0

        train_metrics = eval_models(train, L, K2, gain2, tau2, "train")
        test_metrics = eval_models(test, L, K2, gain2, tau2, "test")

        # Tesla special-case: V0 is essentially zero error — choose V0
        if plat == "TESLA_MODEL_3" and test_metrics["V0_KS"] < 1e-3:
            choice = "V0_KS"
        else:
            choice = min(["V0_KS", "V1_ust", "V2_ust_lag"], key=lambda k: test_metrics[k])

        coeffs[plat] = {
            "L": L,
            "K": K2,
            "gain": gain2,
            "tau": tau2,
            "K_us_only": K1,
            "gain_us_only": gain1,
            "variant": choice,
        }
        summary[plat] = {
            "train": train_metrics,
            "test": test_metrics,
            "chosen_variant": choice,
        }
        print(f"  CHOSEN: {choice}")

    out_dir = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-07/out")
    (out_dir / "coeffs.json").write_text(json.dumps(coeffs, indent=2))
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print("\n=== summary written ===")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
