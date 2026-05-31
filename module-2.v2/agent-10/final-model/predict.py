"""Final-model predict — per-platform understeer correction over V0 (KS) baseline.

Model:
    yr_corr = yr_v0 / (1 + k * v^2) + g * delta_road + b

- The (1 + k v^2)^-1 factor is the linear-bicycle understeer attenuation that
  V0 (KS, no tire) lacks at speed.
- A small steering-coupled term `g * delta_road` captures residual asymmetry
  (e.g. mild oversteer/understeer that varies with steering angle).
- `b` is a calibration offset to null any leftover signed yaw drift.

Coefficients are fitted per platform against pooled distance-resampled CTE
RMSE on an 80% train split of `data/sim/segments/`. Tesla is a passthrough
because its sim.csv has no independent truth channel (psi_dot_rads IS the
V0 KS output).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
with (_HERE / "coeffs.json").open() as _fh:
    COEFFS: dict = json.load(_fh)

_DEFAULT = {"k": 0.0, "g": 0.0, "b": 0.0}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return DataFrame aligned with sim_df.index, with `yaw_rate_pred_rads`.

    Inputs read from sim_df (operating contract — input-only columns):
      - v_mps
      - delta_road_rad
      - yaw_rate_pred_rads  (V0 baseline)
    """
    c = COEFFS.get(platform, _DEFAULT)
    k = float(c.get("k", 0.0))
    g = float(c.get("g", 0.0))
    b = float(c.get("b", 0.0))

    v  = sim_df["v_mps"].to_numpy(dtype=float)
    yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    dr = sim_df["delta_road_rad"].to_numpy(dtype=float)

    yr_corr = yr / (1.0 + k * v * v) + g * dr + b

    return pd.DataFrame({"yaw_rate_pred_rads": yr_corr}, index=sim_df.index)
