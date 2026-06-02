"""bias-corrected-v1 — V1 with a per-platform additive yaw-rate output bias.

Attacks V1's residual CTE drift (Mach-E -22 m signed, IONIQ-5 -12 m signed).
Drift integrates from a small signed yaw bias surviving V1: -0.00142 rad/s on
Mach-E and -0.00075 on IONIQ-5. Adding a small positive offset to V1's yaw_rate
output (chosen to minimise pooled per-platform CTE — note: not equal to -bias,
because the residual is heteroscedastic and V1's lag couples in) drops CTE
without re-fitting V1 internally.

Structure tag: differs-from-v1. V1 cannot reach this output by re-fitting g, L_eff,
K_us, tau or delta0 because those interact non-linearly with v and the lag.
A constant additive output bias is a *new state* outside V1's state-space.
"""

from __future__ import annotations
from pathlib import Path
import sys

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
_AGENT_DIR = _THIS_DIR.parent.parent
sys.path.insert(0, str(_AGENT_DIR / "code"))
from v1_baseline import predict_v1  # type: ignore  # noqa: E402


# Fitted offline by sweeping each platform's per-pooled-CTE minimum on
# data/sim/segments/. See models/bias-corrected-v1/notes.md.
YAW_OFFSET_RAD_S = {
    "FORD_F_150_LIGHTNING_MK1": 0.0,
    "FORD_MUSTANG_MACH_E_MK1": 0.00210,
    "HYUNDAI_IONIQ_5": 0.00108,
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = predict_v1(sim_df, platform).copy()
    offset = YAW_OFFSET_RAD_S.get(platform, 0.0)
    if offset:
        out["yaw_rate_pred_rads"] = out["yaw_rate_pred_rads"] + offset
    return out
