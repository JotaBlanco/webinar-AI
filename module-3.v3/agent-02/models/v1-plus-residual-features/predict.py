"""V1 + residual-feature regression with steering-rate + saturation.

yr = a*yr_v1 + b + c * yr_v1 * (v*yr_v1)^2 + d * ddelta_dt
where ddelta_dt is the per-sample numerical derivative of delta_road_rad.

The steering-rate term targets transient residual where V1's first-order lag
under-models real vehicle dynamics. The saturation term targets high-a_lat.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

_HERE = Path(__file__).parent
_AGENT = _HERE.parent.parent
sys.path.insert(0, str(_AGENT / "code"))

import v1_baseline  # noqa: E402

COEFFS = {
    "FORD_F_150_LIGHTNING_MK1": {"a": 0.98393, "b": -0.000460, "c": 3.973e-04, "d": -0.007997},
    "FORD_MUSTANG_MACH_E_MK1":   {"a": 0.97278, "b":  0.001698, "c": 1.999e-04, "d": -0.022071},
    "HYUNDAI_IONIQ_5":           {"a": 0.99137, "b":  0.000639, "c": 1.484e-04, "d":  0.004507},
}


def _ddelta(t, delta):
    dd = np.gradient(delta, t)
    return np.clip(dd, -2.0, 2.0)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v1_out = v1_baseline.predict_v1(sim_df, platform)
    yr_v1 = v1_out["yaw_rate_pred_rads"].to_numpy()
    if platform in COEFFS:
        c = COEFFS[platform]
        v = sim_df["v_mps"].to_numpy()
        t = sim_df["t_s"].to_numpy()
        delta = sim_df["delta_road_rad"].to_numpy()
        a_lat = v * yr_v1
        dd = _ddelta(t, delta)
        yr = c["a"] * yr_v1 + c["b"] + c["c"] * yr_v1 * a_lat * a_lat + c["d"] * dd
    else:
        yr = yr_v1
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
