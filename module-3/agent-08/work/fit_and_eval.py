"""Fit per-platform lateral-fidelity parameters and evaluate against V0.

Model (per platform, fitted from data):
  delta_eff(t) = g * delta_road(t) + delta0
  yr_ss(t)     = v(t) * delta_eff(t) / (L_eff + K_us * v(t)**2)
  yr_pred(t)   = first-order lag of yr_ss with time constant tau

Fit on TRAIN (route-grouped); evaluate on DEV and full set.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

AGENT_DIR = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-08")
sys.path.insert(0, str(AGENT_DIR / "_shared"))
sys.path.insert(0, str(AGENT_DIR / "skills" / "score-model"))
sys.path.insert(0, str(AGENT_DIR / "skills" / "make-train-dev-split"))

from traj_metrics import cte_rmse_segment  # noqa: E402
from split import split as split_fn  # noqa: E402


DATA_ROOT = AGENT_DIR / "data" / "sim" / "segments"


def load_segment(p: Path) -> dict:
    df = pd.read_csv(p)
    return {
        "path": p,
        "platform": p.resolve().parents[3].name,
        "t": df["t_s"].to_numpy(dtype=float),
        "v": df["v_mps"].to_numpy(dtype=float),
        "delta": df["delta_road_rad"].to_numpy(dtype=float),
        "a_lat": df["a_lat_meas_mps2"].to_numpy(dtype=float) if "a_lat_meas_mps2" in df else None,
        "yr_truth": df["yaw_rate_meas_rads"].to_numpy(dtype=float),
        "yr_v0": df["yaw_rate_pred_rads"].to_numpy(dtype=float),
    }


def apply_lag(yr_ss: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 1e-4:
        return yr_ss.copy()
    n = len(yr_ss)
    out = np.empty(n)
    out[0] = yr_ss[0]
    for i in range(1, n):
        dt = t[i] - t[i - 1]
        alpha = dt / (tau + dt)
        out[i] = out[i - 1] + alpha * (yr_ss[i] - out[i - 1])
    return out


def predict_segment(seg: dict, params: dict) -> np.ndarray:
    g = params["g"]
    d0 = params["delta0"]
    L_eff = params["L_eff"]
    K_us = params["K_us"]
    tau = params["tau"]
    delta_eff = g * seg["delta"] + d0
    v = seg["v"]
    yr_ss = v * delta_eff / (L_eff + K_us * v * v)
    return apply_lag(yr_ss, seg["t"], tau)


def loss_fn(theta: np.ndarray, segs: list, v_min: float = 2.0, cte_weight: float = 0.0) -> float:
    g, d0, L_eff, K_us, tau = theta
    if L_eff <= 0.5 or L_eff > 6.0 or tau < 0 or tau > 0.5 or g < 0.3 or g > 2.0:
        return 1e9
    params = dict(g=g, delta0=d0, L_eff=L_eff, K_us=K_us, tau=tau)
    sq = 0.0
    n = 0
    cte_sq = 0.0
    cte_bins = 0
    for seg in segs:
        yr_pred = predict_segment(seg, params)
        m = seg["v"] > v_min
        resid = yr_pred[m] - seg["yr_truth"][m]
        if np.any(~np.isfinite(resid)):
            return 1e9
        sq += float(np.sum(resid ** 2))
        n += int(m.sum())
        if cte_weight > 0:
            cs, nb, _ = cte_rmse_segment(seg["t"], seg["v"], seg["yr_truth"], yr_pred)
            cte_sq += cs
            cte_bins += nb
    if n == 0:
        return 1e9
    yaw_mse = sq / n
    if cte_weight > 0 and cte_bins > 0:
        cte_mse = cte_sq / cte_bins
        return yaw_mse + cte_weight * cte_mse
    return yaw_mse


def fit_platform(segs: list, init: np.ndarray, cte_weight: float = 0.0) -> dict:
    res = minimize(
        loss_fn,
        init,
        args=(segs, 2.0, cte_weight),
        method="Nelder-Mead",
        options=dict(xatol=1e-5, fatol=1e-8, maxiter=4000, adaptive=True),
    )
    theta = res.x
    return dict(g=float(theta[0]), delta0=float(theta[1]),
                L_eff=float(theta[2]), K_us=float(theta[3]),
                tau=float(theta[4]), loss=float(res.fun), nit=int(res.nit))


def score_segs(segs: list, predictor_fn) -> dict:
    sq = 0.0
    n = 0
    cte_sq = 0.0
    cte_bins = 0
    for seg in segs:
        yr_pred = predictor_fn(seg)
        m = seg["v"] > 2.0
        resid = yr_pred[m] - seg["yr_truth"][m]
        sq += float(np.sum(resid ** 2))
        n += int(m.sum())
        cs, nb, _ = cte_rmse_segment(seg["t"], seg["v"], seg["yr_truth"], yr_pred)
        cte_sq += cs
        cte_bins += nb
    return dict(
        yaw_rmse=math.sqrt(sq / n) if n else float("nan"),
        cte_rmse=math.sqrt(cte_sq / cte_bins) if cte_bins else float("nan"),
        n_segments=len(segs),
        n_samples=n,
        n_cte_bins=cte_bins,
    )


def main():
    ford_paths = sorted(DATA_ROOT.glob("FORD_*/**/sim.csv"))
    print(f"Found {len(ford_paths)} FORD segments")

    train, dev = split_fn(ford_paths, dev_fraction=0.25, seed=42)
    print(f"Train: {len(train)}, Dev: {len(dev)}")

    by_platform_train: dict = {}
    by_platform_dev: dict = {}
    by_platform_all: dict = {}
    for paths, bucket in ((train, by_platform_train), (dev, by_platform_dev), (ford_paths, by_platform_all)):
        for p in paths:
            seg = load_segment(p)
            bucket.setdefault(seg["platform"], []).append(seg)

    init_per_platform = {
        "FORD_MUSTANG_MACH_E_MK1": np.array([1.0, 0.0, 2.984, 0.002, 0.06]),
        "FORD_F_150_LIGHTNING_MK1": np.array([1.0, 0.0, 3.70, 0.003, 0.07]),
    }

    fitted: dict = {}
    for plat, segs in by_platform_train.items():
        init = init_per_platform.get(plat, np.array([1.0, 0.0, 3.0, 0.002, 0.06]))
        fit = fit_platform(segs, init, cte_weight=0.0)
        # Refit with CTE weighting nudged in
        init2 = np.array([fit["g"], fit["delta0"], fit["L_eff"], fit["K_us"], fit["tau"]])
        fit2 = fit_platform(segs, init2, cte_weight=0.5)
        fitted[plat] = fit2
        print(f"\n[{plat}] N_train_segs={len(segs)}")
        print(f"  fit1 (yaw only): g={fit['g']:.4f} d0={fit['delta0']:.5f} L={fit['L_eff']:.3f} K_us={fit['K_us']:.5f} tau={fit['tau']:.4f}")
        print(f"  fit2 (+cte 0.5): g={fit2['g']:.4f} d0={fit2['delta0']:.5f} L={fit2['L_eff']:.3f} K_us={fit2['K_us']:.5f} tau={fit2['tau']:.4f}")

    # Save fitted coeffs
    coeff_path = AGENT_DIR / "work" / "coeffs.json"
    coeff_path.parent.mkdir(parents=True, exist_ok=True)
    with coeff_path.open("w") as fh:
        json.dump(fitted, fh, indent=2)
    print(f"\nSaved coeffs to {coeff_path}")

    # Evaluate V0 vs fitted on train, dev, and pooled — per platform
    def v0_predict(seg):
        return seg["yr_v0"]

    def fitted_predict_factory(params):
        def fn(seg):
            return predict_segment(seg, params)
        return fn

    print("\n=== PER-PLATFORM scoring ===")
    summary = {}
    for plat in by_platform_all:
        for split_name, bucket in (("train", by_platform_train), ("dev", by_platform_dev), ("all", by_platform_all)):
            segs = bucket.get(plat, [])
            if not segs:
                continue
            v0 = score_segs(segs, v0_predict)
            fit_params = fitted[plat]
            fitted_score = score_segs(segs, fitted_predict_factory(fit_params))
            print(f"[{plat:32s} {split_name:5s}] V0  yaw={v0['yaw_rmse']:.5f} cte={v0['cte_rmse']:.2f} n_segs={v0['n_segments']}")
            print(f"[{plat:32s} {split_name:5s}] NEW yaw={fitted_score['yaw_rmse']:.5f} cte={fitted_score['cte_rmse']:.2f}")
            summary[f"{plat}/{split_name}"] = dict(v0=v0, fitted=fitted_score)

    # POOLED — both platforms together
    print("\n=== POOLED scoring (both Fords) ===")
    for split_name, bucket in (("train", by_platform_train), ("dev", by_platform_dev), ("all", by_platform_all)):
        all_segs = [s for segs in bucket.values() for s in segs]
        if not all_segs:
            continue
        v0 = score_segs(all_segs, v0_predict)

        def fn_all(seg):
            return predict_segment(seg, fitted[seg["platform"]])

        nw = score_segs(all_segs, fn_all)
        print(f"[POOLED {split_name:5s}] V0  yaw={v0['yaw_rmse']:.5f} cte={v0['cte_rmse']:.2f} n_segs={v0['n_segments']}")
        print(f"[POOLED {split_name:5s}] NEW yaw={nw['yaw_rmse']:.5f} cte={nw['cte_rmse']:.2f}")
        summary[f"POOLED/{split_name}"] = dict(v0=v0, fitted=nw)

    out_summary = AGENT_DIR / "work" / "scores.json"
    with out_summary.open("w") as fh:
        json.dump(summary, fh, indent=2, default=float)


if __name__ == "__main__":
    main()
