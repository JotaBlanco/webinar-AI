"""Explore yaw-rate residuals across platforms to design a correction."""
import sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-07/data/sim/segments")

PLATFORMS = ["TESLA_MODEL_3", "FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5"]

# Tesla schema is older — psi_dot_rads is the truth label there (it's actually the *measured* yaw rate
# under a different naming). Let's verify by looking at residuals to delta/v.
WHEELBASE = {
    "TESLA_MODEL_3": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5": 3.00,  # guess for ioniq5
}

for plat in PLATFORMS:
    files = sorted(glob.glob(str(DATA / plat / "*/*/*/sim.csv")))
    print(f"\n=== {plat}: {len(files)} segments ===")
    if not files:
        continue
    df0 = pd.read_csv(files[0])
    print("cols:", list(df0.columns))

    # Decide truth column
    if "yaw_rate_meas_rads" in df0.columns:
        truth_col = "yaw_rate_meas_rads"
        pred_col = "yaw_rate_pred_rads"
    else:
        # Tesla older format
        truth_col = "psi_dot_rads"  # check: this might actually be model output not measurement
        pred_col = None

    # Collect samples across multiple segments
    rows = []
    for f in files[:10]:
        d = pd.read_csv(f)
        rows.append(d)
    big = pd.concat(rows, ignore_index=True)
    L = WHEELBASE[plat]
    delta = big["delta_road_rad"].values
    v = big["v_mps"].values
    ks_pred = (v / L) * np.tan(delta)
    if truth_col in big.columns:
        truth = big[truth_col].values
        # baseline RMSE (KS-from-formula)
        rmse_ks = float(np.sqrt(np.mean((ks_pred - truth) ** 2)))
        print(f"  truth col: {truth_col}  baseline KS RMSE = {rmse_ks:.5f} rad/s")
        if pred_col and pred_col in big.columns:
            pred = big[pred_col].values
            rmse_pred = float(np.sqrt(np.mean((pred - truth) ** 2)))
            print(f"  precomputed yaw_rate_pred_rads RMSE = {rmse_pred:.5f} rad/s")
        # fit linear: truth = a * ks_pred (no intercept), and understeer model
        # Linear single track: truth ≈ v*delta / (L + K*v^2)
        # Equivalent: 1/truth = (L + K v^2)/(v*delta)  -> nonlinear. Let's fit by least squares directly.
        from scipy.optimize import least_squares
        def res(p, d, vv, t):
            K, gain = p
            denom = (L + K * vv * vv)
            return gain * vv * d / denom - t
        # mask zero velocities and very small yaw
        m = (np.abs(v) > 2.0)
        try:
            sol = least_squares(res, [0.005, 1.0], args=(delta[m], v[m], truth[m]))
            K, gain = sol.x
            pred_ust = gain * v * delta / (L + K * v * v)
            rmse_ust = float(np.sqrt(np.mean((pred_ust - truth) ** 2)))
            print(f"  understeer-fit RMSE = {rmse_ust:.5f}  (K={K:.6f}, gain={gain:.4f})")
        except Exception as e:
            print("  understeer fit fail:", e)
    else:
        print(f"  no truth col found — schema mismatch")
