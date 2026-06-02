"""V1 + asymmetric gain + signed-bias debias.

Structural diff vs V1:
- v1-asym-gain plus an additional small per-platform additive bias correction.
- This is the *combined* candidate: g_left, g_right tunes the gain asymmetry;
  an additional `b_offset` term that's an additive output bias, fitted to drive
  signed yaw bias to ~zero, knocks the residual CTE drift down further.

Per-platform fit: g_left, g_right (from v1-asym-gain), plus b_offset.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "code"))
from v1_baseline import PLATFORM_PARAMS_V1, _per_segment_delta0  # noqa: E402

_COEFFS_PATH = Path(__file__).parent / "coeffs.json"


def _load_coeffs() -> dict:
    if _COEFFS_PATH.exists():
        return json.loads(_COEFFS_PATH.read_text())
    return {}


COEFFS = _load_coeffs()


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in PLATFORM_PARAMS_V1:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = PLATFORM_PARAMS_V1[platform]
    c = COEFFS.get(platform, {})

    if p["use_per_segment_delta0"]:
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0"]

    delta_raw = sim_df["delta_road_rad"].to_numpy(dtype=float) - delta0
    g_left = c.get("g_left", p["g"])
    g_right = c.get("g_right", p["g"])
    eps = max(c.get("blend_eps", 0.005), 1e-6)
    w_left = 0.5 * (1.0 + np.tanh(delta_raw / eps))
    g_eff = g_left * w_left + g_right * (1.0 - w_left)
    delta = delta_raw * g_eff

    v = sim_df["v_mps"].to_numpy(dtype=float)
    L_eff = c.get("L_eff", p["L_eff"])
    K_us = c.get("K_us", p["K_us"])
    tau = c.get("tau", p["tau"])
    yr_ss = v * delta / (L_eff + K_us * v * v)

    t = sim_df["t_s"].to_numpy(dtype=float)
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])

    # Conditional additive debias: only apply when vehicle is moving and steering
    # (don't bias the straight-line predictions).
    b_offset = c.get("b_offset", 0.0)
    # Gate so we don't pollute v<1 straight passages
    gate = (v > 2.0).astype(float)
    yr = yr + b_offset * gate
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
