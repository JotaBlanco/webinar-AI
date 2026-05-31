"""V3 predict — per-platform understeer-aware affine correction of V0 yaw rate.

Model
-----
    yaw_pred = (k * yaw_v0) / (1 + K_us * v^2) + b

Per platform, fit by nonlinear least squares against the truth yaw rate
(yaw_rate_meas_rads where it exists; psi_dot_rads for Tesla).

- `k`     : multiplicative correction for the V0 steering-ratio / effective-
            wheelbase mismatch.
- `K_us`  : classic understeer-gradient term — at higher v, the same steering
            input produces less yaw than the pure kinematic model predicts.
- `b`     : residual yaw-rate offset (gyro / mounting bias).

Tesla coefficients are pinned to (k=1, K_us=0, b=0): the Tesla "truth" column
in this sim IS the V0 KS output, so any deviation would *increase* RMSE.

Coefficients live in `coeffs.json` next to this file.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFFS_PATH.open() as _fh:
    COEFFS: dict = json.load(_fh)

_DEFAULT = {"k": 1.0, "K_us": 0.0, "b": 0.0}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned to sim_df.index with `yaw_rate_pred_rads`.

    Reads only allowlisted columns from sim_df:
      - `v_mps`
      - `yaw_rate_pred_rads` (V0 baseline; the grader exposes this via the
        operating contract regardless of platform)
    """
    c = COEFFS.get(platform, _DEFAULT)
    k = float(c.get("k", 1.0))
    K_us = float(c.get("K_us", 0.0))
    b = float(c.get("b", 0.0))

    v = sim_df["v_mps"].to_numpy(dtype=float)
    x = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    yp = (k * x) / (1.0 + K_us * v * v) + b

    out = pd.DataFrame(index=sim_df.index)
    out["yaw_rate_pred_rads"] = yp
    return out
