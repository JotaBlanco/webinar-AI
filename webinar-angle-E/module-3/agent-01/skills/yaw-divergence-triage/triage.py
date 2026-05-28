"""triage.py — helpers for yaw-divergence-triage skill."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

DELTA_THR = 0.01
DDELTA_THR = 0.05
DEFAULT_DT = 0.02
V_MIN_ST = 2.0
C_BOUNDS = (5e4, 5e5)


def load_ford_segments(platform: str, data_root: Path | str = "data/sim/segments") -> pd.DataFrame:
    root = Path(data_root) / platform
    csvs = sorted(root.rglob("sim.csv"))
    if not csvs:
        raise FileNotFoundError(f"no sim.csv under {root}")
    frames = []
    for p in csvs:
        df = pd.read_csv(p)
        df["__source__"] = str(p)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def regime_mask(df: pd.DataFrame) -> pd.Series:
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt > 0, dt, DEFAULT_DT)
    delta = df["delta_road_rad"].to_numpy()
    ddelta = np.gradient(delta) / dt
    out = np.full(len(df), "transient", dtype=object)
    out[np.abs(delta) < DELTA_THR] = "straight"
    out[(np.abs(delta) >= DELTA_THR) & (np.abs(ddelta) < DDELTA_THR)] = "steady"
    return pd.Series(out, index=df.index, name="regime")


def rmse(arr):
    a = np.asarray(arr, dtype=float)
    a = a[np.isfinite(a)]
    return float("nan") if a.size == 0 else float(np.sqrt(np.mean(a ** 2)))


def per_regime_rmse(df: pd.DataFrame, resid: np.ndarray) -> dict[str, float]:
    reg = df["regime"].to_numpy() if "regime" in df.columns else regime_mask(df).to_numpy()
    out = {"overall": rmse(resid)}
    for r in ("straight", "steady", "transient"):
        out[r] = rmse(resid[reg == r])
    return out


def _load_params(platform: str, code_root: Path | str = "code") -> dict:
    sys.path.insert(0, str(Path(code_root).resolve()))
    from parameters import PARAM_BY_PLATFORM  # type: ignore
    return PARAM_BY_PLATFORM[platform]


def ks_yaw_rate(v, delta, L):
    return (np.asarray(v, dtype=float) / L) * np.tan(np.asarray(delta, dtype=float))


def linear_st_yaw_rate(v, delta, L, l_f, l_r, m, C_f, C_r, v_min=V_MIN_ST):
    K_us = (m * (l_r * C_r - l_f * C_f)) / (L ** 2 * C_f * C_r)
    v = np.asarray(v, dtype=float)
    d = np.asarray(delta, dtype=float)
    safe = v >= v_min
    psi = v * d / (L * (1.0 + K_us * v ** 2))
    return np.where(safe, psi, ks_yaw_rate(v, d, L))


def v1_ks_recalibrated(df: pd.DataFrame, platform: str) -> tuple[pd.DataFrame, np.ndarray]:
    P = _load_params(platform)
    if "regime" not in df.columns:
        df = df.copy()
        df["regime"] = regime_mask(df)
    pred = ks_yaw_rate(df["v_mps"].to_numpy(), df["delta_road_rad"].to_numpy(), float(P["L"]))
    bias = np.zeros(len(df))
    meas = df["yaw_rate_meas_rads"].to_numpy()
    for src, sub in df.groupby("__source__"):
        m_straight = sub["regime"].to_numpy() == "straight"
        if m_straight.any():
            b = float(np.mean(pred[df["__source__"] == src][m_straight] - meas[df["__source__"] == src][m_straight]))
            bias[df["__source__"] == src] = b
    resid = (pred - bias) - meas
    return df, resid


def v2_linear_st_prior(df: pd.DataFrame, platform: str) -> tuple[pd.DataFrame, np.ndarray]:
    P = _load_params(platform)
    pred = linear_st_yaw_rate(df["v_mps"].to_numpy(), df["delta_road_rad"].to_numpy(),
                              float(P["L"]), float(P["l_f"]), float(P["l_r"]),
                              float(P["m"]), float(P["C_alpha_f"]), float(P["C_alpha_r"]))
    return df, pred - df["yaw_rate_meas_rads"].to_numpy()


def v3_linear_st_fit(df: pd.DataFrame, platform: str) -> tuple[pd.DataFrame, np.ndarray, dict]:
    from scipy.optimize import minimize
    P = _load_params(platform)
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    meas = df["yaw_rate_meas_rads"].to_numpy()
    L = float(P["L"])

    def loss(params):
        cf, cr = params
        pred = linear_st_yaw_rate(v, delta, L, float(P["l_f"]), float(P["l_r"]),
                                  float(P["m"]), cf, cr)
        e = pred - meas
        e = e[np.isfinite(e)]
        return float(np.sqrt(np.mean(e ** 2))) if e.size else float("inf")

    res = minimize(loss, [1.5e5, 1.5e5], method="L-BFGS-B", bounds=[C_BOUNDS, C_BOUNDS])
    cf, cr = float(res.x[0]), float(res.x[1])
    pegged = (abs(cf - C_BOUNDS[1]) < 1.0) or (abs(cr - C_BOUNDS[1]) < 1.0)
    pred = linear_st_yaw_rate(v, delta, L, float(P["l_f"]), float(P["l_r"]),
                              float(P["m"]), cf, cr)
    return df, pred - meas, {"C_alpha_f": cf, "C_alpha_r": cr, "pegged": pegged}
