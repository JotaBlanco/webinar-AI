"""Final model — V1 + per-platform residual-feature OLS correction.

Calls V1 baseline, then applies an affine + saturation (yr_v1*(v*yr_v1)^2)
+ steering-rate (d delta_road / dt) per-platform correction. Coeffs in
coeffs.json. Tesla and unknown platforms fall through to V0 (no correction).

Honours the operating-contract allowlist: only reads t_s, delta_road_rad,
v_mps, yaw_rate_pred_rads from sim_df.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).parent
# Try a few code import paths so this works in dev and in the grader's harness.
_candidates = [
    _HERE.parent / "code",                  # agent-02/code/ via symlink
    Path("/Users/javiquix/Desktop/quixdev/code"),
    _HERE.parent.parent / "code",
]
for _c in _candidates:
    if (_c / "v1_baseline.py").exists():
        sys.path.insert(0, str(_c))
        break

import v1_baseline  # noqa: E402

_COEFFS = json.loads((_HERE / "coeffs.json").read_text())


def _ddelta(t: np.ndarray, delta: np.ndarray) -> np.ndarray:
    if len(t) < 2:
        return np.zeros_like(delta)
    dd = np.gradient(delta, t)
    return np.clip(dd, -2.0, 2.0)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v1_out = v1_baseline.predict_v1(sim_df, platform)
    yr_v1 = v1_out["yaw_rate_pred_rads"].to_numpy()
    if platform not in _COEFFS:
        return pd.DataFrame({"yaw_rate_pred_rads": yr_v1}, index=sim_df.index)
    c = _COEFFS[platform]
    v = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    a_lat = v * yr_v1
    dd = _ddelta(t, delta)
    yr = c["a"] * yr_v1 + c["b"] + c["c"] * yr_v1 * a_lat * a_lat + c["d"] * dd
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
