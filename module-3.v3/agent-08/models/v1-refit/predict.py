"""V1-shape refit — a sanity-check candidate.

Same kinematic-single-track + understeer + first-order-lag formula as V1,
but with all coefficients refit by least-squares on `data/sim/segments/`.
"refines-v1" tag in MODELS.md — exists to confirm that recoeff-ing the V1
shape buys at most a basis point (the cohort's m3.v2 failure mode).

Falls through to V1 if its own coeffs.json is missing.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "code"))
from v1_baseline import predict_v1, _per_segment_delta0  # noqa: E402

_COEFFS_PATH = _HERE / "coeffs.json"
if _COEFFS_PATH.exists():
    _COEFFS = json.loads(_COEFFS_PATH.read_text())
else:
    _COEFFS = {}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in _COEFFS:
        return predict_v1(sim_df, platform)
    p = _COEFFS[platform]
    # Same shape as V1, different coeffs.
    fallback = p.get("delta0_fallback", 0.0)
    if p.get("use_per_segment_delta0", False):
        d0 = _per_segment_delta0(sim_df, fallback=fallback)
    else:
        d0 = p.get("delta0", 0.0)
    delta = (sim_df["delta_road_rad"].to_numpy() - d0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
