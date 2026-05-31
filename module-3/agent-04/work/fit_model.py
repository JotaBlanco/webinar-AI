"""Fit per-platform parameters on the TRAIN split, evaluate on the DEV split.

Model:
    yr_ss(t) = v(t) * g * (delta(t) - delta0) / (L + K_us * v(t)^2)
    yr_pred(t) = (1 - alpha) * yr_pred(t-dt) + alpha * yr_ss(t),   alpha = dt / (tau + dt)

We fit (g, delta0, K_us, tau) per platform on training data with v > v_min.
We minimise per-platform pooled yaw-rate squared error.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))

from score import score  # noqa: E402
from split import split  # noqa: E402

os.chdir(ROOT)

WHEELBASE = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "TESLA_MODEL_3": 2.875,
}

V_MIN = 2.0  # m/s — match score-model's sample filter


def load_segment(path: Path) -> dict | None:
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if "yaw_rate_meas_rads" not in df.columns:
        return None
    if len(df) < 5:
        return None
    t = df["t_s"].to_numpy(float)
    if np.any(np.diff(t) <= 0):
        return None
    return {
        "t": t,
        "v": df["v_mps"].to_numpy(float),
        "delta": df["delta_road_rad"].to_numpy(float),
        "yr_truth": df["yaw_rate_meas_rads"].to_numpy(float),
    }


def predict_yr(t, v, delta, g, delta0, K_us, tau, L):
    """Steady-state bicycle with steering scale + offset + understeer, plus first-order yaw lag."""
    yr_ss = v * g * (delta - delta0) / (L + K_us * v * v)
    n = len(t)
    if tau <= 1e-6:
        return yr_ss
    yr = np.empty(n)
    yr[0] = yr_ss[0]
    for i in range(1, n):
        dt = t[i] - t[i - 1]
        alpha = dt / (tau + dt)
        yr[i] = (1 - alpha) * yr[i - 1] + alpha * yr_ss[i]
    return yr


def loss_for_platform(params, segments, L):
    g, delta0, K_us, tau = params
    if K_us < -0.01 or K_us > 0.05 or tau < 0 or tau > 0.5 or g < 0.5 or g > 2.0:
        return 1e9
    total_sq = 0.0
    total_n = 0
    for seg in segments:
        yr_p = predict_yr(seg["t"], seg["v"], seg["delta"], g, delta0, K_us, tau, L)
        mask = seg["v"] > V_MIN
        if mask.any():
            r = yr_p[mask] - seg["yr_truth"][mask]
            total_sq += float(np.sum(r * r))
            total_n += int(mask.sum())
    if total_n == 0:
        return 1e9
    return total_sq / total_n


def fit_platform(platform: str, segments: list, L: float) -> dict:
    print(f"\nFitting {platform} on {len(segments)} segments…")
    # Initial guess: g=1, delta0=0, K_us=0.002, tau=0.06
    x0 = np.array([1.0, 0.0, 0.002, 0.06])
    best = None
    for x0i in [
        [1.0, 0.0, 0.002, 0.06],
        [1.0, 0.0, 0.005, 0.05],
        [1.0, 0.0, 0.0, 0.0],
        [1.1, 0.001, 0.003, 0.08],
    ]:
        try:
            res = minimize(
                loss_for_platform,
                x0i,
                args=(segments, L),
                method="Nelder-Mead",
                options={"xatol": 1e-6, "fatol": 1e-9, "maxiter": 2000, "disp": False},
            )
        except Exception as e:
            print(f"  start {x0i} failed: {e}")
            continue
        if best is None or res.fun < best.fun:
            best = res
    g, delta0, K_us, tau = best.x
    rmse = np.sqrt(best.fun)
    print(f"  g={g:.5f}  delta0={delta0:.6f}  K_us={K_us:.6f}  tau={tau:.4f}  rmse={rmse:.6f}")
    return {"g": float(g), "delta0": float(delta0), "K_us": float(K_us), "tau": float(tau),
            "L": float(L), "train_rmse": float(rmse), "n_segments_train": len(segments)}


def main():
    train, dev = split(dev_fraction=0.25, seed=42)
    print(f"Train: {len(train)}   Dev: {len(dev)}")

    # Group train segments by platform
    by_platform: dict[str, list] = {}
    for p in train:
        platform = Path(p).resolve().parents[3].name
        if platform not in WHEELBASE or platform == "TESLA_MODEL_3":
            continue
        seg = load_segment(Path(p))
        if seg is not None:
            by_platform.setdefault(platform, []).append(seg)

    coeffs = {}
    for platform, segs in by_platform.items():
        L = WHEELBASE[platform]
        coeffs[platform] = fit_platform(platform, segs, L)

    out_path = ROOT / "final-model" / "coeffs.json"
    out_path.parent.mkdir(exist_ok=True)
    with out_path.open("w") as fh:
        json.dump(coeffs, fh, indent=2)
    print(f"\nCoeffs written to {out_path}")

    # --- Evaluate on dev ---
    def predict_v1(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        if platform not in coeffs:
            # Tesla / unknown: passthrough V0
            return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                                index=sim_df.index)
        c = coeffs[platform]
        t = sim_df["t_s"].to_numpy(float)
        v = sim_df["v_mps"].to_numpy(float)
        delta = sim_df["delta_road_rad"].to_numpy(float)
        yr = predict_yr(t, v, delta, c["g"], c["delta0"], c["K_us"], c["tau"], c["L"])
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    print("\n=== V1 — dev set ===")
    res = score(predict_v1, segment_paths=dev)
    print(f"Overall: yaw_RMSE={res['yaw_rate_rmse']:.6f}  CTE_RMSE={res['cte_rmse']:.3f}")
    for plat, sub in res["per_platform"].items():
        print(f"  {plat}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  CTE_RMSE={sub['cte_rmse']:.3f}  n_seg={sub['n_segments']}")
    for reg, sub in res["per_regime"].items():
        print(f"  regime {reg}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  n={sub['n_samples']}")

    print("\n=== V1 — full data ===")
    res2 = score(predict_v1)
    print(f"Overall: yaw_RMSE={res2['yaw_rate_rmse']:.6f}  CTE_RMSE={res2['cte_rmse']:.3f}")
    for plat, sub in res2["per_platform"].items():
        print(f"  {plat}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  CTE_RMSE={sub['cte_rmse']:.3f}  n_seg={sub['n_segments']}")


if __name__ == "__main__":
    main()
