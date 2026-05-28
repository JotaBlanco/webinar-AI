"""agent-05 lateral-fidelity submission.

Model form (per platform):
    psi_dot_pred = gain * v * (delta - delta_offset) / (L + Kus * v^2)

This is the linear-bicycle understeer-gradient form: same shape as the
kinematic single-track (KS) baseline at low speed, with a tunable
speed-squared term that bends the steady-state cornering response away
from the geometric prediction at higher speed.

Coefficients (Kus, delta_offset, gain) are fit per platform from the
training pool by Nelder-Mead minimising yaw-rate RMSE against
`yaw_rate_meas_rads`. See coeffs.json and REPORT.md.

For TESLA_MODEL_3 (no measured yaw-rate channel in training data) the
model degenerates to V0: tan-based kinematic prediction.
"""

from __future__ import annotations

import json
import os
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "coeffs.json"), "r") as _f:
    _COEFFS = json.load(_f)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned with sim_df.index containing yaw_rate_pred_rads.

    Required input columns: v_mps, delta_road_rad.
    """
    if platform not in _COEFFS:
        # Unknown platform — fall back to vanilla KS with a 2.875 m wheelbase
        c = {"L": 2.875, "Kus": 0.0, "delta_offset": 0.0, "gain": 1.0}
    else:
        c = _COEFFS[platform]

    L = c["L"]
    Kus = c["Kus"]
    d0 = c["delta_offset"]
    g = c["gain"]

    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)

    if Kus == 0.0 and g == 1.0 and d0 == 0.0:
        # V0 fallback: matches KS exactly via tan
        psi_dot = (v / L) * np.tan(d)
    else:
        psi_dot = g * v * (d - d0) / (L + Kus * v * v)

    out = pd.DataFrame(index=sim_df.index)
    out["yaw_rate_pred_rads"] = psi_dot
    return out
