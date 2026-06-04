"""dst_lin — linear-tire dynamic single-track. Rung 1.

State: [β, ψ̇]   sideslip @ CG, yaw rate.
Tyre:  F_y = -C_α · α   (small-angle linear).
Fitted (per platform): {C_alpha_f, C_alpha_r, Iz}.

This is the model cohort §1 + §7 says "should work but was never demonstrated
because every prior cohort used carParams C_α/Iz instead of fitting them."
This implementation IS the demonstration — fit.py refits C_αf, C_αr, Iz
against pooled yaw RMSE on dev under route-grouped CV.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Path-relative imports so this file works whether called from the catalog or
# after being copied into models/<name>/.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import (  # noqa: E402
    PASSTHROUGH_PLATFORMS,
    get_platform_params,
    integrate_dst,
    load_coeffs,
    step_rk4_linear,
)


_MODEL_DIR = Path(__file__).resolve().parent


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """dst_lin predict() conforming to the m4 operating contract.

    Reads only the 8 allowlist columns. Returns a copy of sim_df with the
    `yaw_rate_pred_rads` column overwritten by the dst_lin integration.
    """
    if platform in PASSTHROUGH_PLATFORMS:
        return sim_df[["yaw_rate_pred_rads"]].copy()

    coeffs = load_coeffs(_MODEL_DIR)
    p = get_platform_params(platform, coeffs)
    return integrate_dst(sim_df, platform, p, step_fn=step_rk4_linear)
