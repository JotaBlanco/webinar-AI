"""dst_regime — speed-regime switched: V1 kinematic below threshold, dst_lin above.

The blend at the threshold is smooth (logistic), so the predict is C^∞ across
the regime boundary — avoids the discontinuity-induced CTE blow-ups that
hard switches produce.

Fitted (per platform): {C_alpha_f, C_alpha_r, Iz, theta_v_psi, blend_width}.

theta_v_psi is the threshold on |v · yaw_rate_pred_rads| (units: m·rad/s²).
The dataset's typical range is 0–10; cohort §1 suggests rung-1 starts to
earn its place around theta ≈ 3–4.

Rationale: cohort §1 says rung-1 attempts hurt at low speed (numerical
issues + tiny α). Gating means we only pay rung-1's cost where it earns it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_MODEL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_MODEL_DIR.parent))

from _common import (  # noqa: E402
    PASSTHROUGH_PLATFORMS,
    PLATFORM_PRIORS,
    V_FLOOR_MPS,
    get_platform_params,
    integrate_dst,
    load_coeffs,
    step_rk4_linear,
)


def _v1_kinematic_yaw(sim_df: pd.DataFrame, platform: str) -> np.ndarray:
    """A small kinematic-single-track stand-in for V1 when V1 isn't importable.

    psi_dot = v * tan(delta) / L, no understeer, no lag. Matches V1's output
    to within a couple % for the small-angle regime where dst_regime hands
    off to it, which is sufficient for the blend.
    """
    L = PLATFORM_PRIORS.get(platform, {}).get("L", 3.0)
    delta = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    return v * np.tan(delta) / max(L, 0.5)


def _smooth_gate(x: np.ndarray, theta: float, width: float) -> np.ndarray:
    """Logistic blend: 0 below theta, 1 above. width controls steepness."""
    z = (x - theta) / max(width, 1e-3)
    return 1.0 / (1.0 + np.exp(-z))


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform in PASSTHROUGH_PLATFORMS:
        return sim_df[["yaw_rate_pred_rads"]].copy()
    coeffs = load_coeffs(_MODEL_DIR)
    p = get_platform_params(platform, coeffs)
    theta = float(p.get("theta_v_psi", 3.5))
    width = float(p.get("blend_width", 0.5))

    # Run dst_lin across the whole segment.
    dst_out = integrate_dst(sim_df, platform, p, step_fn=step_rk4_linear)
    dst_yaw = dst_out["yaw_rate_pred_rads"].to_numpy()

    # V1-stand-in (kinematic) yaw rate, plus the V0 column for the low-end fall-through.
    kin_yaw = _v1_kinematic_yaw(sim_df, platform)
    v = sim_df["v_mps"].to_numpy()

    # Gate variable: |v · yaw_pred_v0|. yaw_rate_pred_rads in the input IS V0.
    gate_var = np.abs(v * sim_df["yaw_rate_pred_rads"].to_numpy())
    gate = _smooth_gate(gate_var, theta, width)

    blended = gate * dst_yaw + (1.0 - gate) * kin_yaw
    # Always fall through to V0 below the integration floor.
    floor_mask = v < V_FLOOR_MPS
    blended = np.where(floor_mask, sim_df["yaw_rate_pred_rads"].to_numpy(), blended)

    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = blended
    return out
