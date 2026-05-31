"""Lateral-fidelity V1 — per-platform understeer correction on top of V0 (KS).

Model form (per platform):

    yr_pred(v) = a * yr_v0(v) / (1 + K * v^2) + b

where (a, K, b) are calibrated per-platform against the ground-truth yaw rate
on the training split. Rationale:

  - The kinematic single-track baseline (V0) systematically *over*-predicts
    yaw rate at speed because it ignores tyre slip; the empirically observed
    pred/truth ratio falls roughly as 1 / (1 + K v^2), the standard
    understeer / Ackermann correction.
  - The multiplicative gain `a` absorbs platform-specific steering-ratio /
    geometry calibration error.
  - The additive `b` removes the residual signed bias that dominates CTE
    (CTE is a double-integral of yaw error, so a small constant bias
    integrates into large drift).

Tesla has no independent truth channel (the sim's `psi_dot_rads` *is* the V0
output), so we leave Tesla as identity to avoid corrupting the only sanity
channel.

Coefficients live next to this file in `coeffs.json`. They were fit by
`fit_full.py` (kept under `module-2.v2/agent-06/out/`).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
with (_HERE / "coeffs.json").open() as fh:
    COEFFS: dict[str, dict[str, float]] = json.load(fh)

# Fallback for any unknown platform — identity (pass V0 through unchanged).
_IDENTITY = {"a": 1.0, "K": 0.0, "b": 0.0}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned with ``sim_df.index`` containing
    ``yaw_rate_pred_rads`` (required). Optional ``x_m, y_m`` are omitted —
    the grader integrates trajectory from yaw_rate + measured v.
    """
    coef = COEFFS.get(platform, _IDENTITY)
    a = float(coef["a"])
    K = float(coef["K"])
    b = float(coef["b"])

    v = sim_df["v_mps"].to_numpy(dtype=float)
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)

    denom = 1.0 + K * v * v
    yr_pred = a * yr_v0 / denom + b

    return pd.DataFrame({"yaw_rate_pred_rads": yr_pred}, index=sim_df.index)
