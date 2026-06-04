"""Rung-1 attempt: linear dynamic single-track with slip angles.

Minimum-viable version per dynamics-formulations.md § Rung 1:
- Fix m, Iz, a, b, C_ar from carParams.
- Use C_af from carParams (no fit; baseline rung-1 vs rung-0).
- Two states (vy, yr), Euler integration.
- Tesla and Lightning: passthrough to V0 to isolate the climb on Mach-E + IONIQ-5.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-08")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary  # type: ignore

# Hand-loaded constants from code/parameters.py (avoid full import chain)
RUNG1_PARAMS = {
    "FORD_MUSTANG_MACH_E_MK1": {
        "C_af": 286551.0, "C_ar": 355912.0,
        "m": 2336.0, "Iz": 4879.05,
        "a": 1.3130, "b": 1.671,
        "i_s": 17.0,  # steering ratio if needed
    },
    "HYUNDAI_IONIQ_5": {
        # carParams approximate (similar EV CUV); not loaded from file
        "C_af": 280000.0, "C_ar": 350000.0,
        "m": 2100.0, "Iz": 4500.0,
        "a": 1.45, "b": 1.45,
        "i_s": 15.0,
    },
}


def rung1_predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in RUNG1_PARAMS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = RUNG1_PARAMS[platform]
    delta = sim_df["delta_road_rad"].to_numpy()
    vx = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()

    vx_safe = np.maximum(vx, 5.0)
    dt = np.diff(t, prepend=t[0])
    dt[0] = 0.0
    # cap dt to avoid stiff explosions
    dt = np.clip(dt, 0.0, 0.02)

    C_af, C_ar = p["C_af"], p["C_ar"]
    m, Iz = p["m"], p["Iz"]
    a, b = p["a"], p["b"]

    vy = 0.0
    yr = 0.0
    out = np.empty_like(vx)
    out[0] = 0.0
    for i in range(1, len(vx)):
        # substep to keep Euler stable: stiff dynamics need fine dt
        n_sub = 5
        h = dt[i] / n_sub
        for _ in range(n_sub):
            alpha_f = delta[i] - (vy + a * yr) / vx_safe[i]
            alpha_r = -(vy - b * yr) / vx_safe[i]
            F_yf = C_af * alpha_f
            F_yr = C_ar * alpha_r
            vy_dot = (F_yf + F_yr) / m - vx[i] * yr
            yr_dot = (a * F_yf - b * F_yr) / Iz
            vy += vy_dot * h
            yr += yr_dot * h
        # clamp to physical range
        if not np.isfinite(yr) or abs(yr) > 5.0:
            yr = 0.0
            vy = 0.0
        out[i] = yr
    return pd.DataFrame({"yaw_rate_pred_rads": out}, index=sim_df.index)


def main():
    paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    print(f"Found {len(paths)} segments")
    r = score(rung1_predict, segment_paths=paths)
    print(format_summary(r))


if __name__ == "__main__":
    main()
