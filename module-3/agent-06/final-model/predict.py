"""Rung-0 KS + understeer + first-order lag + per-segment-δ₀ (platform-gated).

Operating contract: at grading time `sim_df` is restricted to:
    t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
    accel_pedal_pct, brake_pressed, yaw_rate_pred_rads.

In particular, NO `a_lat_meas_mps2` and NO truth (`yaw_rate_meas_rads`,
`psi_dot_rads`). So per-segment δ₀ is estimated from input channels alone —
specifically, rows where the steering angle is near zero (driving straight).

Per-platform coefficients live in `coeffs.json` alongside this file.
Tesla falls back to V0 passthrough — no truth channel to fit against.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"


def _load_coeffs() -> dict[str, Any]:
    if not _COEFFS_PATH.exists():
        return {}
    with _COEFFS_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


_COEFFS: dict[str, Any] = _load_coeffs()


def _per_segment_delta0_from_inputs(
    delta_road: np.ndarray,
    v: np.ndarray,
    delta_thresh: float = 0.005,
    v_thresh: float = 5.0,
    min_rows: int = 50,
    fallback: float = 0.0,
) -> float:
    """Estimate δ₀ from THIS segment's own straight-driving rows.

    Uses input channels only (legal at inference time). A row is straight
    if |delta_road_rad| < delta_thresh AND v > v_thresh. Median over those
    rows is the segment-level zero point. Falls back if too few qualifying
    rows.
    """
    mask = (np.abs(delta_road) < delta_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(delta_road[mask]))


def _predict_yaw(sim_df: pd.DataFrame, p: dict) -> np.ndarray:
    delta_road = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0_from_inputs(
            delta_road, v,
            delta_thresh=p.get("delta0_detect_thresh", 0.005),
            v_thresh=5.0,
            min_rows=50,
            fallback=p.get("delta0_fallback", p.get("delta0", 0.0)),
        )
    else:
        delta0 = float(p["delta0"])

    delta = (delta_road - delta0) * float(p["g"])
    L_eff = float(p["L_eff"])
    K_us = float(p["K_us"])
    yr_ss = v * delta / (L_eff + K_us * v * v)

    tau = max(float(p["tau"]), 1e-4)
    dt = np.diff(t, prepend=t[0])
    # First sample: dt[0]==0 by construction. Replace with median dt to avoid alpha=0.
    if dt[0] <= 0 and len(dt) > 1:
        dt[0] = float(np.median(dt[1:]))
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return DataFrame with `yaw_rate_pred_rads` aligned to sim_df.index.

    Platform-gated:
      - FORD_F_150_LIGHTNING_MK1, FORD_MUSTANG_MACH_E_MK1, HYUNDAI_IONIQ_5:
        rung-0 model with per-platform-fitted coefficients.
      - TESLA_MODEL_3 (or anything else): V0 passthrough.
    """
    coeffs = _COEFFS.get(platform)
    if coeffs is None or coeffs.get("passthrough"):
        yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    try:
        yr = _predict_yaw(sim_df, coeffs)
    except Exception:
        # On any unexpected failure, fall back to V0 — never raise out of predict.
        yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
