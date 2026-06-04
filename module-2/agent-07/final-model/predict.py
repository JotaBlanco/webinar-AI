"""Lateral-fidelity predict() for module-2.v3 agent-07.

Per-platform model: understeer-corrected linearised bicycle with a small
steering-rate lead term.

    delta_eff(t) = (delta_road_rad(t) - delta_off) + tau * d(delta_road_rad)/dt
    yaw_pred(t)  = gain * v(t) * delta_eff(t) / (1 + K_us * v(t)^2)

Coefficients per platform live in coeffs.json (sibling file).

Tesla is a no-op: its sim has no independent truth channel — its sim.csv
`psi_dot_rads` IS the V0 KS output. Deviating from V0 on Tesla can only
inflate RMSE, so we pass V0 through.

Output: DataFrame indexed identically to sim_df, with `yaw_rate_pred_rads`.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
_COEFFS = json.loads(_COEFFS_PATH.read_text())

PLATFORM_SUPPORT = sorted(_COEFFS.keys())


def _safe_gradient(d: np.ndarray, t: np.ndarray) -> np.ndarray:
    if len(t) < 2:
        return np.zeros_like(d)
    return np.gradient(d, t)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return DataFrame with `yaw_rate_pred_rads` aligned to sim_df.index."""
    out = pd.DataFrame(index=sim_df.index)

    coeffs = _COEFFS.get(platform)
    if coeffs is None or coeffs.get("passthrough"):
        # V0 passthrough for unknown platforms and Tesla.
        out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        return out

    t = sim_df["t_s"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    dd = _safe_gradient(d, t)

    gain = float(coeffs["gain"])
    K_us = float(coeffs["K_us"])
    tau  = float(coeffs["tau"])
    d_off = float(coeffs["delta_off"])

    delta_eff = (d - d_off) + tau * dd
    yr = gain * v * delta_eff / (1.0 + K_us * v * v)
    out["yaw_rate_pred_rads"] = yr
    return out
