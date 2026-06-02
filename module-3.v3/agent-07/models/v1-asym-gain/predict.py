"""V1 + direction-asymmetric steering gain (left vs right).

Structural diff vs V1:
- V1 applies a single steering scale `g` and a (per-segment) δ₀ offset that
  treats left and right turns symmetrically.
- Diagnostic shows V1 systematically under-predicts right turns on Mach-E and
  IONIQ-5 (residual mean -0.00719 / -0.00547 on right turns vs near-zero on
  left). A single δ₀ cannot fix that — it's a left/right gain asymmetry,
  possibly from sensor mounting, suspension geometry, or alignment.
- This adds a sign-aware gain: scale the *effective* steering by g_left when
  delta_eff > 0 and g_right when delta_eff < 0, blended smoothly.

Per-platform fitted coefficients in `coeffs.json` next to this file.
"""

from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
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
    c = COEFFS.get(platform, {"g_left": p["g"], "g_right": p["g"], "blend_eps": 0.005,
                              "tau": p["tau"], "K_us": p["K_us"], "L_eff": p["L_eff"]})

    if p["use_per_segment_delta0"]:
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0"]

    delta_raw = sim_df["delta_road_rad"].to_numpy(dtype=float) - delta0
    # Smooth sign blend so the gain transition isn't a step discontinuity:
    # w_left ∈ [0,1] using a tanh sigmoid around 0 with width eps.
    eps = max(c.get("blend_eps", 0.005), 1e-6)
    w_left = 0.5 * (1.0 + np.tanh(delta_raw / eps))
    g_eff = c["g_left"] * w_left + c["g_right"] * (1.0 - w_left)
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
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
