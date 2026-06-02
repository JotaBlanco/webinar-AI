"""final-model/predict.py — ships `bias-corrected-v1`.

V1 + per-platform additive yaw-rate offset. Attacks the residual signed CTE
drift surviving V1 (Mach-E −22 m, IONIQ-5 −12 m) without touching V1's
internals. See REPORT.md for full diagnosis and rationale.

Bundle is self-contained: the V1 baseline is re-implemented inline so the
predict module imports nothing from the agent's `code/` symlink at grading
time. The implementation is byte-for-byte identical to `code/v1_baseline.py`
modulo formatting.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


# Inline copy of code/v1_baseline.PLATFORM_PARAMS_V1.
_PARAMS_V1: dict[str, dict] = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False,
        "delta0": 0.00133,
        "g": 0.863,
        "L_eff": 3.26,
        "K_us": 0.00350,
        "tau": 0.060,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True,
        "delta0_fallback": -0.0001,
        "g": 0.891,
        "L_eff": 2.22,
        "K_us": 0.00150,
        "tau": 0.069,
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True,
        "delta0_fallback": 0.0,
        "g": 0.938,
        "L_eff": 2.887,
        "K_us": 0.00289,
        "tau": 0.062,
    },
}


_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"


def _load_yaw_offsets() -> dict[str, float]:
    if _COEFFS_PATH.exists():
        with _COEFFS_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return {k: float(v) for k, v in data.get("yaw_offset_rad_s", {}).items()}
    # Fallback if coeffs.json is missing — equivalent to V1.
    return {}


_YAW_OFFSET = _load_yaw_offsets()


def _per_segment_delta0(
    sim_df: pd.DataFrame,
    fallback: float = 0.0,
    yr_thresh: float = 0.03,
    v_thresh: float = 5.0,
    min_rows: int = 50,
) -> float:
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _predict_v1_inline(sim_df: pd.DataFrame, platform: str) -> np.ndarray:
    p = _PARAMS_V1[platform]
    delta0 = (
        _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
        if p["use_per_segment_delta0"]
        else p["delta0"]
    )
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return DataFrame aligned with sim_df.index, column yaw_rate_pred_rads.

    Falls through to V0 passthrough on platforms without V1 parameters (Tesla).
    """
    if platform not in _PARAMS_V1:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    yr = _predict_v1_inline(sim_df, platform)
    yr = yr + float(_YAW_OFFSET.get(platform, 0.0))
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
