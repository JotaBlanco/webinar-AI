"""M4 — Relaxation-length tire on kinematic core.

Keeps V1's kinematic single-track + understeer + per-segment δ₀ + speed
clamp, but REPLACES V1's time-domain first-order yaw lag (`τ`) with a
*distance-domain* first-order relaxation on the steady-state yaw signal.

Equations (see references/dynamics-formulations.md § Orthogonal — relaxation-length):

    δ_eff      = (δ − δ₀) · g
    yr_demand  = v · δ_eff / (L_eff + K_us · v²)
    yr[k]      = yr[k-1] + (1 − exp(−v[k] · dt[k] / σ)) · (yr_demand[k] − yr[k-1])

At constant v the relaxation collapses to V1's first-order time lag with
`τ = σ / v` — i.e. the lag shortens at high speed, which is the physically
correct behaviour V1's fixed `τ` gets wrong.

Numerics: scalar Euler-style first-order update per row. M4's relaxation
filter has no 1/v singularity (the math is well-behaved for any v ≥ 0),
so we use a *local* low-speed floor `V_MIN_M4 = 1.5 m/s` rather than
physics_core's `V_MIN_DYNAMIC = 4.0`. Below 1.5 m/s we fall back to V0
passthrough as a safety.

Held from V1 (constants of record — see `code/v1_baseline.py`): per-platform
`g`, `L_eff`, `K_us`, δ₀ policy. The single fitted parameter per platform
is `sigma` (meters). Tesla returns V0 passthrough (no truth).
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

# Make _shared importable when invoked from anywhere
TPL = Path(__file__).resolve().parents[4]
if str(TPL) not in sys.path:
    sys.path.insert(0, str(TPL))

from _shared.physics_core import safe_dt, v0_passthrough  # noqa: E402


# ---------------------------------------------------------------------------
# V1 constants of record — inlined verbatim from code/v1_baseline.py.
# M4 holds these fixed and only fits `sigma`.
# ---------------------------------------------------------------------------
V1_PARAMS: dict[str, dict] = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False,
        "delta0": 0.00133,
        "g": 0.863,
        "L_eff": 3.26,
        "K_us": 0.00350,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True,
        "delta0_fallback": -0.0001,
        "g": 0.891,
        "L_eff": 2.22,
        "K_us": 0.00150,
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True,
        "delta0_fallback": 0.0,
        "g": 0.938,
        "L_eff": 2.887,
        "K_us": 0.00289,
    },
}

# Local low-speed floor — M4's filter has no 1/v singularity, so we go
# lower than physics_core's V_MIN_DYNAMIC = 4.0.
V_MIN_M4 = 1.5


def _per_segment_delta0(
    sim_df: pd.DataFrame,
    fallback: float = 0.0,
    yr_thresh: float = 0.03,
    v_thresh: float = 5.0,
    min_rows: int = 50,
) -> float:
    """Median straight-driving steering offset for this segment.

    Copied verbatim from code/v1_baseline.py to keep M4's δ₀ policy
    identical to V1.
    """
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _run_relax(sim_df: pd.DataFrame, p: dict, sigma: float) -> np.ndarray:
    """V1 steady-state yaw + distance-domain relaxation in place of τ.

    Falls back to V0 passthrough below V_MIN_M4 (1.5 m/s).
    """
    delta_row = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    dt = safe_dt(t)

    # δ₀ policy (per-segment or global) — V1's exact rule.
    if p["use_per_segment_delta0"]:
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0"]

    delta_eff = (delta_row - delta0) * p["g"]
    yr_demand = v * delta_eff / (p["L_eff"] + p["K_us"] * v * v)

    n = len(t)
    out = np.empty(n, dtype=float)
    # Seed at the V0 yaw rate so cold-start at low v matches passthrough.
    yr_state = yr_v0[0]
    out[0] = yr_demand[0] if v[0] >= V_MIN_M4 else yr_v0[0]
    yr_state = out[0]

    for i in range(1, n):
        if v[i] < V_MIN_M4 or sigma <= 0.0:
            # Safety fallback / null relaxation → V0 passthrough.
            yr_state = yr_v0[i]
            out[i] = yr_v0[i]
            continue
        alpha = 1.0 - np.exp(-v[i] * dt[i] / sigma)
        yr_state = yr_state + alpha * (yr_demand[i] - yr_state)
        out[i] = yr_state
    return out


def predict_factory(platform: str, coeffs: dict[str, float]):
    """Build a predict callable for `fit-model` / `score-model`.

    `coeffs` is `{"sigma": float}` — the only fitted parameter per platform.
    Tesla returns V0 passthrough (no truth channel).
    """
    if platform == "TESLA_MODEL_3":
        def _passthrough(sim_df: pd.DataFrame) -> np.ndarray:
            return v0_passthrough(sim_df["yaw_rate_pred_rads"].to_numpy())
        return _passthrough

    if platform not in V1_PARAMS:
        def _passthrough(sim_df: pd.DataFrame) -> np.ndarray:
            return v0_passthrough(sim_df["yaw_rate_pred_rads"].to_numpy())
        return _passthrough

    p = V1_PARAMS[platform]
    sigma = float(coeffs.get("sigma", 0.5))

    def _predict(sim_df: pd.DataFrame) -> np.ndarray:
        return _run_relax(sim_df, p, sigma)

    return _predict


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Operating-contract entry point used by the canonical grader."""
    import json

    coeffs_path = Path(__file__).parent / "coeffs.json"
    if coeffs_path.is_file():
        with coeffs_path.open() as f:
            all_coeffs = json.load(f)
        c = all_coeffs.get(platform, {})
    else:
        c = {}

    fn = predict_factory(platform, c)
    yr = fn(sim_df)
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = yr
    return out
