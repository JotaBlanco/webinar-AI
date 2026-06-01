"""Rung 1 — Linear dynamic single-track. Fit C_af per platform, fix others.

Quick attempt: Mach-E only. Compare rung-1 dev RMSE vs rung-0 dev RMSE.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-04")
SIM = ROOT / "data" / "sim" / "segments"
sys.path.insert(0, str(ROOT / "code"))
from parameters import PARAM_BY_PLATFORM  # noqa


def rung1_predict(df, C_af, C_ar, m, Iz, a, b, n_sub=4):
    delta = df["delta_road_rad"].to_numpy()
    vx = df["v_mps"].to_numpy()
    t = df["t_s"].to_numpy()
    vx_safe = np.maximum(vx, 1.0)
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt > 0, dt, 0.02)
    vy = 0.0
    yr = 0.0
    out = np.empty_like(vx)
    for i in range(len(vx)):
        h = dt[i] / n_sub
        for _ in range(n_sub):
            a_f = delta[i] - (vy + a * yr) / vx_safe[i]
            a_r = -(vy - b * yr) / vx_safe[i]
            F_yf = C_af * a_f
            F_yr = C_ar * a_r
            vy_dot = (F_yf + F_yr) / m - vx[i] * yr
            yr_dot = (a * F_yf - b * F_yr) / Iz
            vy += vy_dot * h
            yr += yr_dot * h
        out[i] = yr
    return out


def load_segments(platform, max_n=None):
    paths = sorted((SIM / platform).glob("*/*/*/sim.csv"))
    if max_n:
        paths = paths[:max_n]
    segs = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        route = p.parents[1].name
        segs.append((route, df))
    return segs


def route_split(segs, train_frac=0.75, seed=0):
    routes = sorted({r for r, _ in segs})
    rng = np.random.default_rng(seed)
    rng.shuffle(routes)
    n_train = int(len(routes) * train_frac)
    train_routes = set(routes[:n_train])
    train, dev = [], []
    for r, df in segs:
        (train if r in train_routes else dev).append((r, df))
    return train, dev


def rmse(segs, C_af, p):
    sum_sq = 0.0
    n = 0
    for _, df in segs:
        yr = rung1_predict(df, C_af, p.C_alpha_r, p.m, p.I_z, p.l_f, p.l_r)
        truth = df["yaw_rate_meas_rads"].to_numpy()
        v = df["v_mps"].to_numpy()
        mask = v > 2.0
        r = yr[mask] - truth[mask]
        sum_sq += float(np.sum(r * r))
        n += int(mask.sum())
    return np.sqrt(sum_sq / n) if n > 0 else np.inf


def fit_platform(platform, max_n=80):
    print(f"\n=== Rung 1 fit on {platform} (max_n={max_n}) ===")
    p = PARAM_BY_PLATFORM[platform]
    segs = load_segments(platform, max_n=max_n)
    train, dev = route_split(segs)
    print(f"  segs: {len(segs)} train: {len(train)} dev: {len(dev)}")
    print(f"  carParams: m={p.m} Iz={p.I_z} l_f={p.l_f} l_r={p.l_r} C_af0={p.C_alpha_f}")
    # Optimize C_af
    res = minimize_scalar(
        lambda c: rmse(train, c, p),
        bounds=(20_000, 400_000),
        method="bounded",
        options={"xatol": 500},
    )
    C_af_best = res.x
    train_rmse = rmse(train, C_af_best, p)
    dev_rmse = rmse(dev, C_af_best, p)
    print(f"  best C_af={C_af_best:,.0f}  train_rmse={train_rmse:.5f}  dev_rmse={dev_rmse:.5f}")
    return {"C_af": C_af_best, "train_rmse": train_rmse, "dev_rmse": dev_rmse}


if __name__ == "__main__":
    out = {}
    for plat in ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]:
        out[plat] = fit_platform(plat, max_n=60)
    print("\nSummary:")
    for plat, r in out.items():
        print(f"  {plat}: C_af={r['C_af']:,.0f}  dev_rmse={r['dev_rmse']:.5f}")
