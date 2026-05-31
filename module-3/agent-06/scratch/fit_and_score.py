"""Fit a per-platform lateral model and score against V0 baseline.

Model (per platform):
    delta_eff = g * (delta_road - delta0)
    yr_ss     = v * delta_eff / (L + K_us * v^2)
    yr_pred   = first-order lag with time constant tau applied to yr_ss

Fit by minimising sample-weighted MSE on yr vs yr_meas, with v>v_min filter.
Hold out routes for honest dev evaluation.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_rmse_segment  # noqa: E402

sys.path.insert(0, str(ROOT / "code"))
from parameters import PARAM_BY_PLATFORM  # noqa: E402


# ---------- Loading -----------------------------------------------------------

def list_ford_segments():
    return sorted((ROOT / "data" / "sim" / "segments").glob("FORD_*/**/sim.csv"))


def route_key(p: Path):
    # parts: PLATFORM, DEVICE, ROUTE, IDX, sim.csv
    return (p.parents[3].name, p.parents[2].name, p.parents[1].name)


def platform_of(p: Path):
    return p.parents[3].name


# ---------- Model -------------------------------------------------------------

def first_order_lag(yr_ss: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    """Apply a first-order lag: dy/dt = (yr_ss - y) / tau, init y[0]=yr_ss[0]."""
    if tau <= 1e-6:
        return yr_ss.copy()
    n = len(yr_ss)
    y = np.empty(n)
    y[0] = yr_ss[0]
    for i in range(1, n):
        dt = t[i] - t[i - 1]
        alpha = dt / (tau + dt)  # discrete-time gain
        y[i] = y[i - 1] + alpha * (yr_ss[i] - y[i - 1])
    return y


def predict_segment(sim_df: pd.DataFrame, platform: str, params: dict) -> np.ndarray:
    """Predict yaw-rate for one segment given fit params for that platform.

    params keys: g, delta0, K_us, tau, (optional) L_eff (overrides nominal L).
    """
    p = PARAM_BY_PLATFORM[platform]
    L = params.get("L_eff", p.L)
    g = params["g"]
    delta0 = params["delta0"]
    K_us = params["K_us"]
    tau = params["tau"]

    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    delta_eff = g * (delta - delta0)
    # steady-state yaw rate from bicycle model w/ understeer
    denom = L + K_us * v * v
    yr_ss = v * delta_eff / np.maximum(denom, 1e-6)
    yr = first_order_lag(yr_ss, t, tau)
    return yr


# ---------- Fitting -----------------------------------------------------------

def load_segment_arrays(paths, sample_v_min=2.0):
    """Pre-load t, v, delta_road, yr_meas, yr_v0 from each segment."""
    data = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy(dtype=float)
        v = df["v_mps"].to_numpy(dtype=float)
        delta = df["delta_road_rad"].to_numpy(dtype=float)
        yr_m = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        yr_v0 = df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        if len(t) < 5 or np.any(np.diff(t) <= 0):
            continue
        data.append({
            "path": p,
            "platform": platform_of(p),
            "route": route_key(p),
            "t": t, "v": v, "delta": delta,
            "yr_m": yr_m, "yr_v0": yr_v0,
            "mask_v": v > sample_v_min,
        })
    return data


def fit_platform(segs, platform: str, init=None, bounds=None):
    """Fit (g, delta0, K_us, tau) to minimise pooled MSE on yaw rate."""
    p = PARAM_BY_PLATFORM[platform]
    plat_segs = [s for s in segs if s["platform"] == platform]
    if not plat_segs:
        return None

    if init is None:
        init = [1.0, 0.0, 0.002, 0.06]
    if bounds is None:
        bounds = [(0.5, 1.5), (-0.05, 0.05), (-0.005, 0.02), (0.0, 0.3)]

    def loss(theta):
        g, delta0, K_us, tau = theta
        params = {"g": g, "delta0": delta0, "K_us": K_us, "tau": tau}
        total_sq = 0.0
        total_n = 0
        for s in plat_segs:
            try:
                yr_pred = predict_segment_arrays(s["t"], s["v"], s["delta"], p.L, params)
            except Exception:
                return 1e6
            mask = s["mask_v"]
            resid = (yr_pred - s["yr_m"])[mask]
            total_sq += float(np.sum(resid ** 2))
            total_n += int(mask.sum())
        if total_n == 0:
            return 1e6
        return total_sq / total_n

    res = minimize(loss, np.array(init), method="L-BFGS-B", bounds=bounds,
                   options={"maxiter": 60, "ftol": 1e-8})
    return {
        "g": float(res.x[0]),
        "delta0": float(res.x[1]),
        "K_us": float(res.x[2]),
        "tau": float(res.x[3]),
        "loss": float(res.fun),
        "n_segments": len(plat_segs),
    }


def predict_segment_arrays(t, v, delta, L, params):
    g = params["g"]; delta0 = params["delta0"]
    K_us = params["K_us"]; tau = params["tau"]
    delta_eff = g * (delta - delta0)
    denom = L + K_us * v * v
    yr_ss = v * delta_eff / np.maximum(denom, 1e-6)
    return first_order_lag(yr_ss, t, tau)


# ---------- Scoring -----------------------------------------------------------

def score_predictions(segs, pred_fn, label=""):
    """pred_fn: (seg_dict) -> yr_pred array.

    Returns dict with yr RMSE and CTE RMSE pooled, and per-platform.
    """
    overall = {"yr_ss": 0.0, "yr_n": 0, "cte_ss": 0.0, "cte_n": 0}
    by_plat = defaultdict(lambda: {"yr_ss": 0.0, "yr_n": 0, "cte_ss": 0.0, "cte_n": 0})
    for s in segs:
        yr_pred = pred_fn(s)
        mask = s["mask_v"]
        resid = (yr_pred - s["yr_m"])[mask]
        ss = float(np.sum(resid ** 2))
        n = int(mask.sum())
        cte_ss, cte_n, _ = cte_rmse_segment(s["t"], s["v"], s["yr_m"], yr_pred)
        overall["yr_ss"] += ss; overall["yr_n"] += n
        overall["cte_ss"] += cte_ss; overall["cte_n"] += cte_n
        bp = by_plat[s["platform"]]
        bp["yr_ss"] += ss; bp["yr_n"] += n
        bp["cte_ss"] += cte_ss; bp["cte_n"] += cte_n
    def finalize(d):
        return {
            "yr_rmse": math.sqrt(d["yr_ss"]/d["yr_n"]) if d["yr_n"] else float("nan"),
            "cte_rmse": math.sqrt(d["cte_ss"]/d["cte_n"]) if d["cte_n"] else float("nan"),
            "n_samples": d["yr_n"], "n_bins": d["cte_n"],
        }
    return {
        "label": label,
        "overall": finalize(overall),
        "per_platform": {k: finalize(v) for k, v in by_plat.items()},
    }


def print_score(s):
    print(f"\n=== {s['label']} ===")
    o = s["overall"]
    print(f"  Overall: yr_rmse={o['yr_rmse']:.6f}  cte_rmse={o['cte_rmse']:.3f}  n_samples={o['n_samples']}  n_bins={o['n_bins']}")
    for plat, p in s["per_platform"].items():
        print(f"  {plat}: yr_rmse={p['yr_rmse']:.6f}  cte_rmse={p['cte_rmse']:.3f}  n={p['n_samples']}")


# ---------- Route split -------------------------------------------------------

def route_split(data, dev_frac=0.25, seed=0):
    routes = sorted({s["route"] for s in data})
    rng = np.random.default_rng(seed)
    rng.shuffle(routes)
    n_dev = max(1, int(len(routes) * dev_frac))
    dev_routes = set(routes[:n_dev])
    train = [s for s in data if s["route"] not in dev_routes]
    dev = [s for s in data if s["route"] in dev_routes]
    return train, dev


# ---------- Main --------------------------------------------------------------

def main():
    paths = list_ford_segments()
    print(f"Loading {len(paths)} Ford segments...")
    data = load_segment_arrays(paths)
    print(f"Loaded {len(data)} valid segments.")

    train, dev = route_split(data, dev_frac=0.25, seed=42)
    print(f"Route split: train={len(train)} segs, dev={len(dev)} segs")
    print(f"  train routes: {len({s['route'] for s in train})}, dev routes: {len({s['route'] for s in dev})}")

    # ---------- V0 baseline ----
    v0 = score_predictions(dev, lambda s: s["yr_v0"], label="V0 (dev)")
    print_score(v0)
    v0_all = score_predictions(data, lambda s: s["yr_v0"], label="V0 (all)")
    print_score(v0_all)

    # ---------- Fit per-platform ----
    fits = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1"]:
        f = fit_platform(train, plat)
        print(f"\nFit {plat}: g={f['g']:.4f}, delta0={f['delta0']:.5f} rad ({math.degrees(f['delta0']):.2f}°), "
              f"K_us={f['K_us']:.5f}, tau={f['tau']:.4f} s, "
              f"loss={f['loss']:.3e}, n_segs={f['n_segments']}")
        fits[plat] = f

    # Score on dev using fits
    def pred_v1(s):
        f = fits[s["platform"]]
        p = PARAM_BY_PLATFORM[s["platform"]]
        return predict_segment_arrays(s["t"], s["v"], s["delta"], p.L, f)
    v1 = score_predictions(dev, pred_v1, label="V1 fitted (dev)")
    print_score(v1)
    v1_train = score_predictions(train, pred_v1, label="V1 fitted (train)")
    print_score(v1_train)
    v1_all = score_predictions(data, pred_v1, label="V1 fitted (all)")
    print_score(v1_all)

    # Dump fit params to JSON for the predict module
    import json
    out = {"fits": fits}
    with open(ROOT / "scratch" / "fits.json", "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nWrote {ROOT/'scratch'/'fits.json'}")


if __name__ == "__main__":
    main()
