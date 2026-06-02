"""v-dependent-lag — V1 with the scalar lag time constant replaced by τ(v) = τ0 + τ1 / max(v, 1).

Attacks V1's transient-regime residual by letting the lag respond harder at low
speed (where transients dominate CTE in city driving). Differs from V1 because
τ is no longer a scalar — it varies sample-to-sample with v.

The empirical sweep on dev showed only IONIQ-5 picks up a non-zero τ1 (with a
tiny improvement). Mach-E and Lightning collapse back to V1's τ. So this
candidate is essentially "differs-from-v1 in formulation, equivalent in fit"
— useful negative result (rules out v-dependent lag as the right structure).
"""

from __future__ import annotations
from pathlib import Path
import sys

import numpy as np
import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
_AGENT_DIR = _THIS_DIR.parent.parent
sys.path.insert(0, str(_AGENT_DIR / "code"))
from v1_baseline import PLATFORM_PARAMS_V1, _per_segment_delta0  # type: ignore  # noqa: E402


# Fitted via grid search per platform, minimising pooled yaw RMSE on
# data/sim/segments/<platform>/.
TAU_PARAMS = {
    "FORD_F_150_LIGHTNING_MK1": {"tau0": 0.060, "tau1": 0.000},
    "FORD_MUSTANG_MACH_E_MK1":  {"tau0": 0.060, "tau1": 0.000},
    "HYUNDAI_IONIQ_5":           {"tau0": 0.040, "tau1": 0.050},
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in PLATFORM_PARAMS_V1 or platform not in TAU_PARAMS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = PLATFORM_PARAMS_V1[platform]
    tp = TAU_PARAMS[platform]
    delta0 = (
        _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
        if p["use_per_segment_delta0"]
        else p["delta0"]
    )
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    tau = tp["tau0"] + tp["tau1"] / np.maximum(v, 1.0)
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
