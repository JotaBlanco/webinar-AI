"""dst_nl — saturating Pacejka-lite tyre on dst_lin state-space. Rung 2.

Tyre: F_y = -μ · F_z · sin(C · atan(B · α))   (Pacejka simplified, no D explicit)
       where  B = C_α / (C · μ · F_z)   to recover the small-angle slope.

Fitted (per platform): {C_alpha_f, C_alpha_r, Iz, mu, C_pacejka}.

mu is the peak friction coefficient (anchors tyre saturation). C_pacejka is
the Pacejka shape factor (≈ 1.3 for tyres). At small α this collapses to
F_y ≈ -C_α · α — dst_lin is the small-angle limit of dst_nl.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_MODEL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_MODEL_DIR.parent))

from _common import (  # noqa: E402
    GRAVITY,
    PASSTHROUGH_PLATFORMS,
    get_platform_params,
    integrate_dst,
    load_coeffs,
    step_rk4_tyre,
)


def _pacejka_tyre(alpha: float, Fz: float, p: dict, which: str) -> float:
    """F_y = -μ · F_z · sin(C · atan(B · α)),  B = C_α / (C · μ · F_z).

    At small α: F_y ≈ -μ·F_z · C · (B·α) = -C_α · α. (Recovers the linear limit.)
    At large α: F_y → -μ · F_z · sin(C · π/2) ≈ -μ · F_z · 1.0  (saturation).
    """
    Cf = p["C_alpha_f"] if which == "front" else p["C_alpha_r"]
    mu = p.get("mu", 0.9)
    C  = p.get("C_pacejka", 1.30)
    Fz_safe = max(float(Fz), 100.0)
    B = Cf / (C * mu * Fz_safe)
    return -mu * Fz_safe * np.sin(C * np.arctan(B * alpha))


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform in PASSTHROUGH_PLATFORMS:
        return sim_df[["yaw_rate_pred_rads"]].copy()
    coeffs = load_coeffs(_MODEL_DIR)
    p = get_platform_params(platform, coeffs)
    # tyre_fn passed through to step_rk4_tyre via integrate_dst's **step_kwargs.
    return integrate_dst(
        sim_df, platform, p,
        step_fn=step_rk4_tyre,
        tyre_fn=_pacejka_tyre,
    )
