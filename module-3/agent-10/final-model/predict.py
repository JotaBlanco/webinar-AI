"""Final model — kinematic single-track with understeer, first-order yaw lag,
and platform-fitted coefficients (g, L_eff, K_us, tau, delta0).

For FORD_MUSTANG_MACH_E_MK1 we estimate a per-segment delta0 from an
input-only lateral acceleration proxy (a_lat ≈ v * yaw_rate_pred_rads) to
absorb per-segment steering bias. For other platforms a global delta0 is
used. For any unfitted platform we fall back to passthrough of the
pre-computed V0 prediction.

Coefficients in coeffs.json were fitted per-platform on truth via
Nelder-Mead minimisation of yaw-rate MSE over data/sim/segments/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_COEFFS_PATH = _HERE / "coeffs.json"

with open(_COEFFS_PATH) as _f:
    COEFFS = json.load(_f)


def _per_segment_delta0(sim_df: pd.DataFrame,
                        fallback: float,
                        ax_thresh: float = 0.3,
                        v_thresh: float = 5.0,
                        min_rows: int = 50) -> float:
    """Estimate steering zero-offset from rows where the car is going (near)
    straight at speed. Uses the V0 yaw-rate prediction as an input-only proxy
    for lateral acceleration: a_lat ≈ v * yaw_rate_pred_rads.
    """
    v = sim_df["v_mps"].to_numpy()
    yr0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    a_lat = v * yr0
    delta_road = sim_df["delta_road_rad"].to_numpy()
    mask = (np.abs(a_lat) < ax_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(delta_road[mask]))


def _ks_predict(sim_df: pd.DataFrame, p: dict, delta0: float) -> np.ndarray:
    """Steady-state KS with understeer + first-order lag."""
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
    """Produce yaw-rate predictions for one segment.

    Returns a DataFrame indexed by sim_df.index with column
    `yaw_rate_pred_rads`. x_m, y_m are not produced — the grader integrates
    from yaw_rate + measured v when these columns are absent.
    """
    if platform not in COEFFS:
        # Unknown platform — fall back to pre-computed V0 prediction.
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = COEFFS[platform]
    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_glob"])
    else:
        delta0 = p["delta0_glob"]
    yr = _ks_predict(sim_df, p, delta0)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
