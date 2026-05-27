"""triage.py — utilities for the lateral-fidelity-triage skill.

Import from a script under `tools/` or run interactively. Reads Ford `sim.csv`
files; provides RMSE, regime masks, KS baseline computation, linear-ST
integrator, and a Cα fit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Iterable

REGIME_DELTA_THR = 0.01    # rad
REGIME_DDELTA_THR = 0.05   # rad/s
V_MIN_ST = 2.0             # m/s — below this, fall back to KS
C_ALPHA_BOUNDS = (5e4, 5e5)  # N/rad — physical range for cornering stiffness


def load_ford_sim(csv_path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    required = {
        "t_s", "delta_road_rad", "v_mps",
        "yaw_rate_meas_rads", "yaw_rate_pred_rads", "yaw_rate_resid_rads",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing columns in {csv_path}: {missing}")
    return df


def load_many(csv_paths: Iterable[str | Path]) -> pd.DataFrame:
    frames = []
    for p in csv_paths:
        df = load_ford_sim(p)
        df["__source__"] = str(p)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def regime_mask(df: pd.DataFrame) -> pd.Series:
    delta = df["delta_road_rad"].to_numpy()
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 0.02, dt)
    ddelta = np.gradient(delta) / dt
    out = np.full(len(df), "transient", dtype=object)
    out[np.abs(delta) < REGIME_DELTA_THR] = "straight"
    steady = (np.abs(delta) >= REGIME_DELTA_THR) & (np.abs(ddelta) < REGIME_DDELTA_THR)
    out[steady] = "steady"
    return pd.Series(out, index=df.index, name="regime")


def rmse(series) -> float:
    s = np.asarray(series, dtype=float)
    s = s[np.isfinite(s)]
    if s.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean(s ** 2)))


def per_regime_rmse(df: pd.DataFrame, resid_col: str) -> dict[str, float]:
    reg = regime_mask(df)
    out = {"overall": rmse(df[resid_col])}
    for r in ("straight", "steady", "transient"):
        sub = df.loc[reg == r, resid_col]
        out[r] = rmse(sub) if len(sub) else float("nan")
    return out


def ks_yaw_rate(v_mps, delta_road_rad, L: float) -> np.ndarray:
    """Stock KS yaw-rate prediction: ψ̇ = (v/L) · tan(δ). No slip."""
    v = np.asarray(v_mps, dtype=float)
    d = np.asarray(delta_road_rad, dtype=float)
    return (v / L) * np.tan(d)


def linear_st_yaw_rate(
    v_mps, delta_road_rad,
    L: float, l_f: float, l_r: float,
    m: float, I_z: float,
    C_alpha_f: float, C_alpha_r: float,
    v_min: float = V_MIN_ST,
) -> np.ndarray:
    """Linear single-track steady-state yaw-rate gain.

        ψ̇ = v · δ / (L · (1 + K_us · v²))
        K_us = m · (l_r·C_αr − l_f·C_αf) / (L² · C_αf · C_αr)

    Below `v_min`, falls back to KS (linearisation is unstable).
    """
    K_us = (m * (l_r * C_alpha_r - l_f * C_alpha_f)) / (L ** 2 * C_alpha_f * C_alpha_r)
    v = np.asarray(v_mps, dtype=float)
    d = np.asarray(delta_road_rad, dtype=float)
    safe = v >= v_min
    return np.where(
        safe,
        v * d / (L * (1.0 + K_us * v ** 2)),
        ks_yaw_rate(v, d, L),
    )


def fit_c_alpha(
    df: pd.DataFrame,
    L: float, l_f: float, l_r: float, m: float, I_z: float,
    bounds: tuple[float, float] = C_ALPHA_BOUNDS,
) -> tuple[float, float, bool]:
    """Fit (C_αf, C_αr) to minimise RMSE of linear-ST yaw rate vs measured.

    Returns (C_αf_fit, C_αr_fit, pegged_at_upper).
    """
    from scipy.optimize import minimize
    meas = df["yaw_rate_meas_rads"].to_numpy()
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()

    def loss(params):
        cf, cr = params
        pred = linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf, cr)
        e = pred - meas
        e = e[np.isfinite(e)]
        return float(np.sqrt(np.mean(e ** 2))) if e.size else float("inf")

    x0 = [1.5e5, 1.5e5]
    res = minimize(loss, x0, method="L-BFGS-B", bounds=[bounds, bounds])
    cf, cr = float(res.x[0]), float(res.x[1])
    pegged = (abs(cf - bounds[1]) < 1.0) or (abs(cr - bounds[1]) < 1.0)
    return cf, cr, pegged


def residual_learner_loo(
    df: pd.DataFrame,
    residual_col: str = "yaw_rate_resid_rads",
) -> tuple[np.ndarray, dict[str, float]]:
    """Ridge regression on [v, |a_y|, |δ|, sign(δ̇)] with leave-one-segment-out CV.

    Returns (oof_predictions, info). `oof_predictions` has the same length as `df`;
    each row's prediction was produced by a model trained on the *other* segments.
    `info` includes oof_rmse for the residual learner.
    """
    from sklearn.linear_model import Ridge
    if "__source__" not in df.columns:
        raise ValueError("residual_learner_loo requires '__source__' (segment id) column")
    segs = df["__source__"].unique()
    if len(segs) < 2:
        raise ValueError("need ≥ 2 segments for LOO cross-validation")

    t = df["t_s"].to_numpy()
    dt = np.where(np.diff(t, prepend=t[0]) > 0, np.diff(t, prepend=t[0]), 0.02)
    delta = df["delta_road_rad"].to_numpy()
    ddelta = np.gradient(delta) / dt
    a_y = df["a_y_pred_mps2"].to_numpy() if "a_y_pred_mps2" in df.columns else np.zeros(len(df))
    X = np.column_stack([
        df["v_mps"].to_numpy(),
        np.abs(a_y),
        np.abs(delta),
        np.sign(ddelta),
    ])
    y = df[residual_col].to_numpy()

    oof = np.full(len(df), np.nan)
    for seg in segs:
        train = df["__source__"] != seg
        test = ~train
        model = Ridge(alpha=1.0).fit(X[train], y[train])
        oof[test] = model.predict(X[test])
    info = {"oof_rmse": rmse(y - oof)}
    return oof, info
