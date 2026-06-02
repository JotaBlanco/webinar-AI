"""steering-derivative-residual — V1 + linear residual learner on (ddelta/dt, v*ddelta/dt, sign·sqrt).

Attacks V1's transient-regime yaw error (transient regime RMSE 0.01647 vs
straight 0.00442) and the residual CTE drift simultaneously, by letting a small
linear model with a constant bias term soak up both the steady offset and the
steering-rate-correlated transient.

Structure tag: differs-from-v1. V1's kinematic-single-track output cannot reach
a `r̂ = a·dδ/dt + b·v·dδ/dt + c·sign(δ̇)·sqrt|δ̇| + d` correction by re-fitting
its scalar (g, L_eff, K_us, τ, δ₀).
"""

from __future__ import annotations
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
_AGENT_DIR = _THIS_DIR.parent.parent
sys.path.insert(0, str(_AGENT_DIR / "code"))
from v1_baseline import predict_v1  # type: ignore  # noqa: E402


# Fitted offline via ridge least-squares on the V1 residual across each
# platform's full segment set (data/sim/segments/). Features:
#   f1 = dδ/dt        (rad/s, road-wheel steering rate from time-gradient)
#   f2 = v · dδ/dt   (m·rad/s²; couples speed to steering rate)
#   f3 = sign(δ̇)·sqrt|δ̇|
#   f4 = 1            (constant bias)
# Coefficient vector order: [w1, w2, w3, w4].
COEFFS = {
    "FORD_F_150_LIGHTNING_MK1": [
        4.7227e-04,
        -1.1812e-03,
        -1.8544e-04,
        4.9118e-05,
    ],
    "FORD_MUSTANG_MACH_E_MK1": [
        1.4706e-02,
        -5.6546e-03,
        5.2983e-03,
        1.3277e-03,
    ],
    "HYUNDAI_IONIQ_5": [
        -1.2221e-02,
        -2.7516e-03,
        1.2407e-02,
        7.5429e-04,
    ],
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = predict_v1(sim_df, platform).copy()
    if platform not in COEFFS:
        return out
    t = sim_df["t_s"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    # gradient handles unevenly-spaced t but here dt is ~uniform.
    ddelta = np.gradient(delta, t)
    f1 = ddelta
    f2 = v * ddelta
    f3 = np.sign(ddelta) * np.sqrt(np.abs(ddelta))
    w = COEFFS[platform]
    r_hat = w[0] * f1 + w[1] * f2 + w[2] * f3 + w[3]
    out["yaw_rate_pred_rads"] = out["yaw_rate_pred_rads"].to_numpy() + r_hat
    return out
