"""Compute V1 residuals and check structure vs candidate features."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v3/agent-04")
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1


def load_residuals(platform: str, max_segs: int = 200):
    base = ROOT / "data" / "sim" / "segments" / platform
    segs = sorted(base.glob("**/sim.csv"))[:max_segs]
    feats = []
    resids = []
    for p in segs:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        # Strip to allowlist before V1 sees it (same as grader)
        ALLOWED = {
            "t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
            "accel_pedal_pct","brake_pressed","brake_pedal_state","steer_rate_dps",
            "yaw_rate_pred_rads","di_torque_actual_nm",
            "wheel_FL_kph","wheel_FR_kph","wheel_RL_kph","wheel_RR_kph",
        }
        sim_df = df[[c for c in df.columns if c in ALLOWED]].copy()
        pred = predict_v1(sim_df, platform)
        yr_v1 = pred["yaw_rate_pred_rads"].to_numpy()
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        dt = np.diff(t, prepend=t[0])
        ddelta = np.gradient(delta, t)
        a_long = df["a_long_mps2"].to_numpy() if "a_long_mps2" in df.columns else np.zeros_like(v)
        mask = v > 2.0
        if mask.sum() < 50:
            continue
        resid = yr_truth - yr_v1  # what V1 still misses
        feats.append(np.column_stack([
            v[mask],
            delta[mask],
            ddelta[mask],
            v[mask] * delta[mask],
            v[mask] * v[mask] * delta[mask],
            yr_v1[mask],
            a_long[mask],
            np.sign(delta[mask]) * delta[mask] * delta[mask],  # |delta|*delta
        ]))
        resids.append(resid[mask])
    X = np.vstack(feats)
    y = np.concatenate(resids)
    return X, y


def correlations(X, y, names):
    print(f"  n={len(y)}, residual mean={y.mean():+.5f}, std={y.std():.5f}")
    for i, n in enumerate(names):
        c = np.corrcoef(X[:, i], y)[0, 1]
        print(f"    {n:>20s}: corr={c:+.4f}")


if __name__ == "__main__":
    names = ["v", "delta", "ddelta_dt", "v*delta", "v^2*delta", "yr_v1", "a_long", "|delta|*delta"]
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        print(f"\n== {plat} ==")
        X, y = load_residuals(plat, max_segs=80)
        correlations(X, y, names)
