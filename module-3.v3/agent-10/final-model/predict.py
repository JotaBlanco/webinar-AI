"""Final-model predict() for the lateral-fidelity task.

Per-platform reconstruction shape:
    delta_eff = (delta_road_rad - delta0) * g
    yr_ss     = v * delta_eff / (L_eff + K_us * v**2)      # bicycle steady-state w/ understeer
    yr        = first-order lag(yr_ss, tau)                # discretised over the segment dt

δ₀ is platform-gated:
  - Mach-E and Hyundai IONIQ-5: per-segment, estimated from input-only straight-row gate.
  - Lightning: single global δ₀ (per-segment was shown to hurt on this platform).
  - Tesla: V0 passthrough (no truth channel).

Inputs read are inside the operating-contract allowlist only.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
with open(_HERE / "coeffs.json", "r") as f:
    PLATFORM_PARAMS = json.load(f)


def _per_segment_delta0(sim_df: pd.DataFrame, fallback: float = 0.0,
                        yr_thresh: float = 0.03, v_thresh: float = 5.0,
                        min_rows: int = 50) -> float:
    """Estimate δ₀ from THIS segment's own straight-driving rows.

    Uses allowlist channels only:
      - yaw_rate_pred_rads (V0 baseline): straight-driving indicator
      - v_mps: speed gate (avoid stationary rows)
      - delta_road_rad: the offset estimate itself (median of the gated rows)
    """
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return float(fallback)
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _first_order_lag(yr_ss: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 0.0:
        return yr_ss.copy()
    dt = np.diff(t, prepend=t[0])
    # Stable discretisation: alpha = dt / (tau + dt)
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Forward-integrate (x, y) from yaw rate + measured speed.

    psi[0] = 0 (the canonical scorer aligns trajectories by yaw integration —
    the absolute heading offset cancels in CTE).
    """
    dt = np.diff(t, prepend=t[0])
    psi = np.cumsum(yr * dt)
    # Shift so psi[0] = 0 in the cumulative sense.
    psi = psi - psi[0]
    x = np.cumsum(v * np.cos(psi) * dt)
    y = np.cumsum(v * np.sin(psi) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned with sim_df.index with at least 'yaw_rate_pred_rads'."""
    # Defensive: any platform not in our coeffs falls through to V0 passthrough.
    if platform not in PLATFORM_PARAMS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )

    p = PLATFORM_PARAMS[platform]

    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=p.get("delta0_fallback", 0.0))
    else:
        delta0 = p["delta0"]

    delta = (sim_df["delta_road_rad"].to_numpy(dtype=float) - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    denom = p["L_eff"] + p["K_us"] * v * v
    # Guard against any pathological zero denominators (shouldn't happen with positive L_eff).
    denom = np.where(denom <= 0.0, p["L_eff"], denom)
    yr_ss = v * delta / denom

    yr = _first_order_lag(yr_ss, t, p["tau"])

    x, y = _integrate_xy(t, v, yr)

    return pd.DataFrame(
        {
            "yaw_rate_pred_rads": yr,
            "x_m": x,
            "y_m": y,
        },
        index=sim_df.index,
    )
