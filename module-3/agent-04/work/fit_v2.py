"""V2: add polynomial steering scale and refit.

Model:
    g_eff(delta) = g0 + g1 * |delta|
    yr_ss(t) = v(t) * g_eff(delta) * (delta - delta0) / (L + K_us * v^2)
    yr_pred(t) = first-order lag with tau

V2 also fits the loss as a weighted combination:
    loss = (yaw_rmse / yaw_v0)^2 + lambda * (CTE / CTE_v0)^2

But we'll start simple — pure yaw-RMSE loss, then see if the CTE follows.
We can also fit a CTE-aware loss by mixing in the integrated trajectory error.
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
sys.path.insert(0, str(ROOT / "_shared"))

from score import score  # noqa: E402
from split import split  # noqa: E402
from traj_metrics import integrate_trajectory  # noqa: E402

os.chdir(ROOT)

WHEELBASE = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "TESLA_MODEL_3": 2.875,
}

V_MIN = 2.0


def load_segment(path: Path) -> dict | None:
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if "yaw_rate_meas_rads" not in df.columns or len(df) < 5:
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


def predict_yr_v2(t, v, delta, g0, g1, delta0, K_us, tau, L):
    g_eff = g0 + g1 * np.abs(delta)
    yr_ss = v * g_eff * (delta - delta0) / (L + K_us * v * v)
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


def loss_for_platform(params, segments, L, cte_weight=0.0):
    g0, g1, delta0, K_us, tau = params
    # Bounds
    if (g0 < 0.5 or g0 > 2.0 or g1 < -2.0 or g1 > 5.0
            or K_us < -0.01 or K_us > 0.05 or tau < 0 or tau > 0.5):
        return 1e9
    yr_sum_sq = 0.0
    yr_n = 0
    cte_sum_sq = 0.0
    cte_n_bins = 0
    for seg in segments:
        yr_p = predict_yr_v2(seg["t"], seg["v"], seg["delta"],
                             g0, g1, delta0, K_us, tau, L)
        mask = seg["v"] > V_MIN
        if mask.any():
            r = yr_p[mask] - seg["yr_truth"][mask]
            yr_sum_sq += float(np.sum(r * r))
            yr_n += int(mask.sum())
        if cte_weight > 0:
            dt = np.diff(seg["t"])
            if np.any(dt <= 0):
                continue
            s_t, x_t, y_t, _ = integrate_trajectory(dt, seg["v"], seg["yr_truth"])
            _, x_p, y_p, _ = integrate_trajectory(dt, seg["v"], yr_p)
            total = float(s_t[-1])
            if total < 20.0:
                continue
            n_bins = int(np.floor(total))
            if n_bins <= 0:
                continue
            grid = np.arange(1, n_bins + 1, dtype=float)
            x_t_g = np.interp(grid, s_t, x_t)
            y_t_g = np.interp(grid, s_t, y_t)
            x_p_g = np.interp(grid, s_t, x_p)
            y_p_g = np.interp(grid, s_t, y_p)
            err_sq = (x_t_g - x_p_g) ** 2 + (y_t_g - y_p_g) ** 2
            cte_sum_sq += float(err_sq.sum())
            cte_n_bins += n_bins
    if yr_n == 0:
        return 1e9
    yr_mse = yr_sum_sq / yr_n
    if cte_weight > 0 and cte_n_bins > 0:
        cte_mse = cte_sum_sq / cte_n_bins
        # Normalise: yaw mse ~1e-4, CTE mse ~1e4. We want them comparable.
        return yr_mse + cte_weight * cte_mse / 1e6
    return yr_mse


def fit_platform(platform: str, segments: list, L: float, cte_weight: float = 0.0) -> dict:
    print(f"\nFitting {platform} (cte_weight={cte_weight}) on {len(segments)} segments…")
    best = None
    for x0i in [
        [1.0, 0.0, 0.0, 0.002, 0.06],
        [1.0, 0.5, 0.0, 0.003, 0.05],
        [1.2, 0.0, 0.001, 0.003, 0.07],
        [0.95, 1.0, 0.0, 0.004, 0.08],
        [1.1, 0.5, 0.0005, 0.003, 0.06],
    ]:
        try:
            res = minimize(
                loss_for_platform,
                x0i,
                args=(segments, L, cte_weight),
                method="Nelder-Mead",
                options={"xatol": 1e-6, "fatol": 1e-9, "maxiter": 3000, "disp": False},
            )
        except Exception as e:
            print(f"  start {x0i} failed: {e}")
            continue
        if best is None or res.fun < best.fun:
            best = res
    g0, g1, delta0, K_us, tau = best.x
    print(f"  g0={g0:.5f}  g1={g1:.5f}  delta0={delta0:.6f}  K_us={K_us:.6f}  tau={tau:.4f}  loss={best.fun:.6e}")
    return {"g0": float(g0), "g1": float(g1), "delta0": float(delta0),
            "K_us": float(K_us), "tau": float(tau), "L": float(L),
            "n_segments_train": len(segments)}


def main():
    train, dev = split(dev_fraction=0.25, seed=42)
    print(f"Train: {len(train)}   Dev: {len(dev)}")

    by_platform: dict[str, list] = {}
    for p in train:
        platform = Path(p).resolve().parents[3].name
        if platform not in WHEELBASE or platform == "TESLA_MODEL_3":
            continue
        seg = load_segment(Path(p))
        if seg is not None:
            by_platform.setdefault(platform, []).append(seg)

    # Pure yaw MSE first (fast)
    coeffs = {}
    for platform, segs in by_platform.items():
        L = WHEELBASE[platform]
        coeffs[platform] = fit_platform(platform, segs, L, cte_weight=0.0)

    out_path = ROOT / "final-model" / "coeffs.json"
    out_path.parent.mkdir(exist_ok=True)
    with out_path.open("w") as fh:
        json.dump({"version": "v2", "model": "ks_understeer_polysteer_lag", "platforms": coeffs}, fh, indent=2)
    print(f"\nCoeffs written to {out_path}")

    def predict_v2(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        if platform not in coeffs:
            return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                                index=sim_df.index)
        c = coeffs[platform]
        t = sim_df["t_s"].to_numpy(float)
        v = sim_df["v_mps"].to_numpy(float)
        delta = sim_df["delta_road_rad"].to_numpy(float)
        yr = predict_yr_v2(t, v, delta, c["g0"], c["g1"], c["delta0"],
                           c["K_us"], c["tau"], c["L"])
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    print("\n=== V2 — dev set ===")
    res = score(predict_v2, segment_paths=dev)
    print(f"Overall: yaw_RMSE={res['yaw_rate_rmse']:.6f}  CTE_RMSE={res['cte_rmse']:.3f}")
    for plat, sub in res["per_platform"].items():
        print(f"  {plat}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  CTE_RMSE={sub['cte_rmse']:.3f}  n_seg={sub['n_segments']}")
    for reg, sub in res["per_regime"].items():
        print(f"  regime {reg}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  n={sub['n_samples']}")

    print("\n=== V2 — full data ===")
    res2 = score(predict_v2)
    print(f"Overall: yaw_RMSE={res2['yaw_rate_rmse']:.6f}  CTE_RMSE={res2['cte_rmse']:.3f}")
    for plat, sub in res2["per_platform"].items():
        print(f"  {plat}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  CTE_RMSE={sub['cte_rmse']:.3f}  n_seg={sub['n_segments']}")


if __name__ == "__main__":
    main()
