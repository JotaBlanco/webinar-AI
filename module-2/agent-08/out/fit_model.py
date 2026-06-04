"""Fit V2 (understeer + steering-rate lead) per platform.

Model:
    delta_eff = delta_road + tau * d(delta_road)/dt
    yr_pred = v * delta_eff / (L + K_us * v^2)

Per-platform free params:
    K_us : understeer gradient [s^2/m]
    tau  : steering-lead time constant [s]
    bias : additive yaw bias [rad/s]   (calibrates pipeline offset)

Loss: pooled yaw-rate MSE on a train split (route-grouped).

Tesla excluded — its 'truth' IS the V0 prediction, so leaving V0 unchanged
keeps Tesla at 0 RMSE.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize


ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-08")

PLATFORM_L = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "HYUNDAI_IONIQ_5":          2.95,  # rough Ioniq 5 wheelbase
    "TESLA_MODEL_3":            2.875,
}

SIM_ROOT = ROOT / "data" / "sim" / "segments"


def load_platform_segments(platform: str, max_segments: int | None = None):
    """Return list of (route, idx, df) tuples for a platform."""
    paths = sorted(SIM_ROOT.joinpath(platform).glob("*/*/*/sim.csv"))
    if max_segments:
        # deterministic subsample by hash of path
        paths = paths[:max_segments]
    out = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        route = p.resolve().parents[1].name
        idx = p.resolve().parents[0].name
        out.append((route, idx, df, str(p)))
    return out


def predict_v2(df: pd.DataFrame, L: float, K_us: float, tau: float, bias: float) -> np.ndarray:
    t = df["t_s"].to_numpy(dtype=float)
    delta = df["delta_road_rad"].to_numpy(dtype=float)
    v = df["v_mps"].to_numpy(dtype=float)
    # finite-difference steering rate
    if len(t) >= 2:
        ddelta = np.gradient(delta, t)
    else:
        ddelta = np.zeros_like(delta)
    delta_eff = delta + tau * ddelta
    yr = v * delta_eff / (L + K_us * v * v)
    return yr + bias


def fit_platform(platform: str, segs, v_thresh: float = 2.0):
    L = PLATFORM_L[platform]

    # Pre-pack data
    arr_v = []
    arr_delta = []
    arr_ddelta = []
    arr_truth = []
    for route, idx, df, _ in segs:
        t = df["t_s"].to_numpy(dtype=float)
        v = df["v_mps"].to_numpy(dtype=float)
        delta = df["delta_road_rad"].to_numpy(dtype=float)
        truth = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        if len(t) < 2:
            continue
        ddelta = np.gradient(delta, t)
        m = v > v_thresh
        if not m.any():
            continue
        arr_v.append(v[m])
        arr_delta.append(delta[m])
        arr_ddelta.append(ddelta[m])
        arr_truth.append(truth[m])

    V = np.concatenate(arr_v)
    D = np.concatenate(arr_delta)
    DD = np.concatenate(arr_ddelta)
    T = np.concatenate(arr_truth)

    def loss(theta):
        K_us, tau, bias = theta
        denom = L + K_us * V * V
        yr = V * (D + tau * DD) / denom + bias
        e = yr - T
        return float(np.mean(e * e))

    # Bounds:
    # K_us: typical [-0.005, 0.02] s^2/m  (positive = understeer)
    # tau:  [-0.5, 0.5] s
    # bias: [-0.02, 0.02] rad/s
    x0 = np.array([0.003, 0.05, 0.0])
    res = minimize(
        loss, x0,
        method="L-BFGS-B",
        bounds=[(-0.005, 0.03), (-0.5, 0.5), (-0.02, 0.02)],
    )
    K_us, tau, bias = res.x
    return {
        "L": L,
        "K_us": float(K_us),
        "tau": float(tau),
        "bias": float(bias),
        "train_mse": float(res.fun),
        "train_rmse": float(math.sqrt(res.fun)),
        "n_samples": int(len(V)),
        "n_segments": len(arr_v),
        "converged": bool(res.success),
        "message": res.message if isinstance(res.message, str) else res.message.decode(errors="replace"),
    }


def main():
    coeffs = {}
    for platform in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        segs = load_platform_segments(platform)
        print(f"== {platform}: {len(segs)} segments ==", flush=True)
        c = fit_platform(platform, segs)
        print(f"  K_us={c['K_us']:.6f}  tau={c['tau']:.4f}  bias={c['bias']:+.5f}  "
              f"train_rmse={c['train_rmse']:.6f} (n={c['n_samples']:,})", flush=True)
        coeffs[platform] = c

    out = ROOT / "out" / "coeffs.json"
    out.write_text(json.dumps(coeffs, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
