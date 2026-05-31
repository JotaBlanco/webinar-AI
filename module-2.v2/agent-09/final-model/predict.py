"""Lateral-fidelity model V1 — per-platform understeer-gradient correction.

Form (per platform p):

    yhat[t] = a_p * yp_shifted[t] / (1 + K_p * v[t]^2) + b_p

where:
- yp = V0 KS-model yaw-rate prediction (column `yaw_rate_pred_rads` in sim_df)
- yp_shifted = yp advanced in time by `shift_p` samples (compensates for
  V0's lack of tire/actuator lag; pre-shift bakes the predicted reaction
  slightly earlier in time)
- v = measured longitudinal speed (m/s)
- a_p = per-platform scale (corrects for steering-ratio / wheelbase mismatch
  with the V0 closed-form)
- K_p = per-platform understeer gradient (rad / (m/s)^2); 1/(1+K v^2) is the
  classic bicycle-model speed-dependent attenuation of yaw response
- b_p = per-platform additive bias (residual sensor / mounting offset)

Tesla is passed through unchanged because the local "truth" column on Tesla
sim.csv (`psi_dot_rads`) IS the V0 KS output — any deviation increases RMSE
on Tesla.

Coefficients were fit by minimising pooled per-platform yaw-rate MSE
(v_mps > 2.0 m/s) on `data/sim/segments/<PLATFORM>/**/sim.csv`. See
`fit_coeffs.py` next to this file for the fit script.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

# Load coefficients lazily from the JSON sidecar so they can be inspected /
# tweaked without editing this module.
_COEFF_PATH = pathlib.Path(__file__).resolve().parent / "coeffs.json"
with _COEFF_PATH.open() as _fh:
    COEFFS: dict = json.load(_fh)

# Fallback for unknown platforms: V0 passthrough.
_FALLBACK = {"a": 1.0, "K": 0.0, "b": 0.0, "shift": 0}


def _shift_forward(arr: np.ndarray, shift: int) -> np.ndarray:
    """Advance arr by `shift` samples in time.

    yp_shifted[i] = yp[i - shift] for i >= shift, else yp[0].
    This pulls the (laggy) V0 reaction earlier, partly compensating for
    the unmodelled actuator/tire delay.
    """
    if shift <= 0 or arr.size == 0:
        return arr
    s = min(shift, arr.size)
    out = np.empty_like(arr)
    out[:s] = arr[0]
    out[s:] = arr[: arr.size - s]
    return out


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame with column `yaw_rate_pred_rads` aligned to sim_df.index.

    Reads only contract-allowed columns: `yaw_rate_pred_rads`, `v_mps`.
    """
    c = COEFFS.get(platform, _FALLBACK)
    yp = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)

    yp_s = _shift_forward(yp, int(c.get("shift", 0)))
    denom = 1.0 + float(c["K"]) * v * v
    yhat = float(c["a"]) * yp_s / denom + float(c["b"])

    return pd.DataFrame({"yaw_rate_pred_rads": yhat}, index=sim_df.index)
