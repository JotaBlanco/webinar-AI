"""V2 lateral-fidelity predictor.

Model (per non-Tesla platform):
    yaw_rate = v * (delta + tau * d(delta)/dt) / (L + Kus * v^2) + bias

The (delta + tau · d(delta)/dt) factor is a first-order lead/lag correction on
the steering input — empirically the per-platform tau came out NEGATIVE
(~-0.06 s), i.e. yaw measurement is delayed relative to steering measurement
(measurement-pipeline timing skew), so the model uses delta sampled slightly
in the past. The bias term absorbs the residual yaw offset.

For TESLA_MODEL_3 the sim truth IS the V0 KS output (no independent truth
channel), so the predictor passes V0 through unchanged. Tweaking Tesla can
only HURT its RMSE.

Coefficients fitted per platform via Nelder-Mead minimisation of pooled MSE on
v_mps > 2 samples from `data/sim/segments/<PLATFORM>/**/sim.csv` (see
`fit_coeffs.py` next to this file for the fit script).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
with (_HERE / "coeffs.json").open() as f:
    COEFFS: dict[str, dict] = json.load(f)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned to sim_df.index with `yaw_rate_pred_rads`."""
    out = pd.DataFrame(index=sim_df.index)

    # Tesla: pass V0 through.
    if platform == "TESLA_MODEL_3" or platform not in COEFFS:
        out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()
        return out

    c = COEFFS[platform]
    L = float(c["L"])
    Kus = float(c["Kus"])
    tau = float(c.get("tau", 0.0))
    bias = float(c.get("bias", 0.0))

    delta = sim_df["delta_road_rad"].astype(float).to_numpy()
    v = sim_df["v_mps"].astype(float).to_numpy()
    t = sim_df["t_s"].astype(float).to_numpy()

    if len(t) >= 2:
        ddelta = np.gradient(delta, t)
    else:
        ddelta = np.zeros_like(delta)

    eff_delta = delta + tau * ddelta
    denom = L + Kus * v * v
    # Guard against pathological denom (shouldn't happen for fitted L>0, Kus>=0, real v).
    denom = np.where(denom < 0.1, 0.1, denom)
    yr = v * eff_delta / denom + bias

    out["yaw_rate_pred_rads"] = yr
    return out
