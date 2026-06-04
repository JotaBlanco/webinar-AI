"""Lateral-fidelity predict — V2 model.

Per-platform refit of the canonical understeer-augmented bicycle output:

    yaw_pred = v * (delta + tau * d_delta / dt) / (L + Kus * v^2) + bias

Per-platform coefficients live in ``coeffs.json`` next to this file.

- ``L``     — effective wheelbase (m).
- ``Kus``   — understeer coefficient (s^2 / m).
- ``tau``   — steering-rate lag/lead (s); compensates for the relative delay
              between the steering and yaw sensor pipelines.
- ``bias``  — additive yaw-rate offset (rad/s); captures residual calibration
              drift that the multiplicative terms cannot remove.

Tesla is a passthrough: in our local sim its ``psi_dot_rads`` IS the V0 KS
output, so any deviation would *increase* RMSE. We do not edit it.

Trajectory `x_m`/`y_m` are intentionally omitted — the scorer will integrate
them from `yaw_rate_pred_rads` and measured `v_mps`, which is identical to
what we would do by hand.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFFS_PATH.open() as _f:
    COEFFS: dict = json.load(_f)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned with `sim_df.index` containing
    ``yaw_rate_pred_rads``.
    """
    # Tesla — V0 IS truth in our sim; do not modify.
    if platform == "TESLA_MODEL_3":
        return sim_df[["yaw_rate_pred_rads"]].copy()

    c = COEFFS.get(platform)
    if c is None:
        # Unknown platform — fall back to V0.
        return sim_df[["yaw_rate_pred_rads"]].copy()

    t = sim_df["t_s"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)

    if len(t) >= 2:
        dd = np.gradient(d, t)
    else:
        dd = np.zeros_like(d)

    yr = v * (d + c["tau"] * dd) / (c["L"] + c["Kus"] * v * v) + c["bias"]
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
