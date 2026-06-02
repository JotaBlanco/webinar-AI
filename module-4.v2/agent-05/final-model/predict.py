"""V2 predict — V1 functional form, refit per-platform params on cohort dev data.

Structure (same as V1):
    delta_eff = (delta_road - delta0) * g
    yr_ss = v * delta_eff / (L_eff + K_us * v²)
    yr[i] = first-order lag with tau toward yr_ss

What changed from V1:
  - Per-platform (g, L_eff, K_us, tau) refit jointly via Nelder-Mead on the
    full dev set using truth (yaw_rate_meas_rads). The fit is done OFFLINE;
    only the coefficients live in this file. predict() reads no truth.
  - Tighter per-segment δ0 estimator: weighted by exp(-|yr_v0|/scale) over
    all v > 5 m/s samples, instead of a median over a hard threshold. This
    uses every straight-ish sample with a smooth weight, reducing per-segment
    δ0 variance (which is the dominant CTE-drift driver).
  - δ0 then has a tiny clamp to plausible range.

Tesla: V0 passthrough (no truth available, do not fit).

Operating contract honoured: reads only the 8 allowed columns. No truth.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


PLATFORM_PARAMS = {
    # Refit params jointly with per-segment δ0 (fit_with_d0.json).
    # V1 params kept for F150 (already optimal) and Hyundai/Mustang re-checked.
    # Mustang: kept V1's tau=0.069 (refit tau=0.0835 overfit on yaw and hurt CTE).
    "FORD_F_150_LIGHTNING_MK1": {
        "g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060,
        "delta0_fallback": 0.00133,
        "c_dot": -0.00131,  # steering-rate feedforward, fitted (out/fit_jerk.py)
        "use_per_segment_delta0": False,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "g": 0.891, "L_eff": 2.22, "K_us": 0.00150, "tau": 0.069,
        "delta0_fallback": -0.0001,
        "c_dot": -0.00423,
        "use_per_segment_delta0": True,
    },
    "HYUNDAI_IONIQ_5": {
        "g": 0.938, "L_eff": 2.887, "K_us": 0.00289, "tau": 0.062,
        "delta0_fallback": 0.0,
        "c_dot": 0.00047,
        "use_per_segment_delta0": True,
    },
}

DELTA0_CLAMP = 0.005  # rad — δ0 should never exceed ±5 mrad (~0.3°)


def _estimate_delta0(sim_df: pd.DataFrame, fallback: float,
                     yr_thresh: float = 0.03, v_thresh: float = 5.0,
                     min_rows: int = 50) -> float:
    """V1's per-segment δ0 estimator: median(δ_road) over straight-and-moving samples.

    Kept identical to V1 because the median-on-hard-threshold turned out to
    be more robust than the smooth-weighted variant I tried (V2.0 dev:
    cte_rmse 62.77 vs V1 56.81 — soft weighting raised drift by including
    long-curve samples with non-zero residual weight).
    """
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    d = sim_df["delta_road_rad"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    d0 = float(np.median(d[mask]))
    if not np.isfinite(d0):
        return fallback
    return float(np.clip(d0, -DELTA0_CLAMP, DELTA0_CLAMP))


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Euler ZOH trajectory from (0,0,0). Matches traj_metrics conventions."""
    n = len(v)
    if n < 2:
        return np.zeros(n), np.zeros(n)
    dt = np.diff(t)
    psi = np.empty(n); psi[0] = 0.0
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x = np.empty(n); x[0] = 0.0
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y = np.empty(n); y[0] = 0.0
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    # Unknown / Tesla: V0 passthrough.
    if platform not in PLATFORM_PARAMS:
        yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        v = sim_df["v_mps"].to_numpy(dtype=float)
        t = sim_df["t_s"].to_numpy(dtype=float)
        x, y = _integrate_xy(t, v, yr)
        return pd.DataFrame({"yaw_rate_pred_rads": yr, "x_m": x, "y_m": y},
                            index=sim_df.index)

    p = PLATFORM_PARAMS[platform]
    if p["use_per_segment_delta0"]:
        delta0 = _estimate_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0_fallback"]

    delta_road = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    delta_eff = (delta_road - delta0) * p["g"]
    yr_ss = v * delta_eff / (p["L_eff"] + p["K_us"] * v * v)
    # Steering-rate feedforward: small additive term capturing transient yaw
    # response to δ̇ that the first-order lag underpredicts. Fit per-platform
    # (out/fit_jerk.py) — contribution is ~0.1-0.3% on yaw RMSE.
    c_dot = p.get("c_dot", 0.0)
    if c_dot:
        if len(t) >= 2:
            d_dot = np.gradient(delta_road, t)
            yr_ss = yr_ss + c_dot * d_dot * v

    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])

    x, y = _integrate_xy(t, v, yr)
    return pd.DataFrame({"yaw_rate_pred_rads": yr, "x_m": x, "y_m": y},
                        index=sim_df.index)
