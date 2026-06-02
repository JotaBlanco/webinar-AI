"""Model C: V1 + richer correction including transient feature ddelta/dt and
nonlinear-curvature term delta^3.

Features per sample:
    1, |delta|*delta, v*delta, v^2*delta, delta^3, ddelta/dt, ddelta/dt * v,
    sign(yr_v1)*delta^2 (asymmetric curvature)
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v3/agent-04")
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1

ALLOWED = {
    "t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
    "accel_pedal_pct","brake_pressed","brake_pedal_state","steer_rate_dps",
    "yaw_rate_pred_rads","di_torque_actual_nm",
    "wheel_FL_kph","wheel_FR_kph","wheel_RL_kph","wheel_RR_kph",
}


def build_features(df: pd.DataFrame) -> np.ndarray:
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    t = df["t_s"].to_numpy()
    if len(t) >= 2:
        ddelta = np.gradient(delta, t)
    else:
        ddelta = np.zeros_like(delta)
    return np.column_stack([
        np.ones_like(v),
        np.abs(delta) * delta,
        v * delta,
        v * v * delta,
        delta ** 3,
        ddelta,
        ddelta * v,
        np.sign(delta) * delta * delta * v,
    ])


def fit_platform(platform: str, max_segs: int = 400):
    base = ROOT / "data" / "sim" / "segments" / platform
    segs = sorted(base.glob("**/sim.csv"))[:max_segs]
    Xs, ys = [], []
    for p in segs:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        sim_df = df[[c for c in df.columns if c in ALLOWED]].copy()
        pred = predict_v1(sim_df, platform)
        yr_v1 = pred["yaw_rate_pred_rads"].to_numpy()
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        v = df["v_mps"].to_numpy()
        mask = v > 2.0
        if mask.sum() < 50:
            continue
        feats = build_features(df)
        Xs.append(feats[mask])
        ys.append(yr_truth[mask] - yr_v1[mask])
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    lam = 1e-5
    A = X.T @ X + lam * np.eye(X.shape[1])
    b = X.T @ y
    coef = np.linalg.solve(A, b)
    pred = X @ coef
    rmse_before = np.sqrt(np.mean(y ** 2))
    rmse_after = np.sqrt(np.mean((y - pred) ** 2))
    return coef.tolist(), rmse_before, rmse_after, len(y)


if __name__ == "__main__":
    feature_names = ["1", "|delta|*delta", "v*delta", "v^2*delta", "delta^3",
                     "ddelta_dt", "ddelta_dt*v", "sign(delta)*delta^2*v"]
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        coef, r0, r1, n = fit_platform(plat)
        out[plat] = {"coef": coef, "feature_names": feature_names}
        print(f"{plat}: n={n}, resid_rmse {r0:.5f} -> {r1:.5f}")
        for nm, c in zip(feature_names, coef):
            print(f"   {nm:>25s}: {c:+.5f}")
    out_path = ROOT / "out" / "correction_v2_coeffs.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"saved {out_path}")
