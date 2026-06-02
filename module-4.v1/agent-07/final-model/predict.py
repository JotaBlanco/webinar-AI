"""Final-model predict() — V1 baseline + per-platform bias + ridge residual head.

Following the operating contract: reads only the 8 input columns the grader
hands us in sim-only/. Returns a DataFrame aligned with sim_df.index with at
least `yaw_rate_pred_rads`.

Per references/m4-cohort-findings.md §0:
  - Per-platform additive bias correction on V1  (§2)
  - Low-rank ridge residual learner head on V1   (§4)

Tesla: bias and ridge weights are effectively zero (the training-truth equals
V1 by construction), so we passthrough.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).parent / "coeffs.json"
with open(_COEFFS_PATH) as _f:
    _COEFFS = json.load(_f)

_FEATS = _COEFFS["feature_names"]
_V_GATE = float(_COEFFS["v_gate_mps"])


def _build_features(df: pd.DataFrame) -> np.ndarray:
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    a = df["a_long_mps2"].to_numpy() if "a_long_mps2" in df.columns else np.zeros_like(delta)
    return np.column_stack([
        delta,
        np.abs(delta),
        v,
        delta * v,
        delta * np.abs(delta),
        a,
        delta * delta,
        np.sign(delta) * v,
    ])


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return DataFrame with at least `yaw_rate_pred_rads`, index-aligned."""
    v1 = sim_df["yaw_rate_pred_rads"].to_numpy().astype(float).copy()
    v = sim_df["v_mps"].to_numpy().astype(float)
    gate = v > _V_GATE

    # Per-platform additive bias.
    bias = float(_COEFFS["bias"].get(platform, 0.0))
    yr = v1 + bias * gate

    # Ridge residual head — only for platforms with fit weights.
    rc = _COEFFS["ridge"].get(platform)
    if rc is not None:
        X = _build_features(sim_df)
        w = np.array(rc["weights_raw"], dtype=float)
        b0 = float(rc["intercept_raw"])
        corr = X @ w + b0
        yr = yr + corr * gate

    out = pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    return out
