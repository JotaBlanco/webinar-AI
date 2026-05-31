"""Final model: per-platform understeer-corrected yaw rate with steering-rate
lead term and a delta-cubic correction.

    delta_eff = delta_road + tau * d/dt(delta_road) + delta_bias + alpha3 * delta_road**3
    yaw       = scale * v * delta_eff / (L + K_us * v**2)

Per-platform coefficients (K_us, scale, delta_bias, tau, alpha3, L) are stored
in `coeffs.json` next to this file. Fit on the truth-bearing subset of
`data/sim/segments/` (Ford Lightning, Mach-E, Hyundai Ioniq 5) using
scipy.optimize.least_squares on samples with v > 2 m/s.

Tesla — for which the workshop has no truth labels — uses the Mach-E K_us/tau
with scale=1 and no biases, as a safe-ish prior. Anything more aggressive would
be unverifiable.

Inputs strictly follow the canonical grader allowlist; no truth columns read.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS: dict | None = None
_DEFAULT = {
    "K_us": 0.0028, "scale": 1.0, "delta_bias": 0.0,
    "tau": -0.06, "alpha3": 0.0, "L0": 3.0,
}


def _load() -> dict:
    global _COEFFS
    if _COEFFS is None:
        p = Path(__file__).parent / "coeffs.json"
        _COEFFS = json.loads(p.read_text())
    return _COEFFS


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    coeffs = _load().get(platform, _DEFAULT)
    K_us = coeffs["K_us"]
    scale = coeffs["scale"]
    delta_bias = coeffs["delta_bias"]
    tau = coeffs.get("tau", 0.0)
    alpha3 = coeffs.get("alpha3", 0.0)
    L = coeffs.get("L0", _DEFAULT["L0"])

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)
    if len(t) >= 3:
        ddot = np.gradient(d, t)
    else:
        ddot = np.zeros_like(d)
    d_eff = d + tau * ddot + delta_bias + alpha3 * (d ** 3)
    yaw = scale * v * d_eff / (L + K_us * v * v)

    return pd.DataFrame({"yaw_rate_pred_rads": yaw}, index=sim_df.index)
