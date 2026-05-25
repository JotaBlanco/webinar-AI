"""Regenerate Ford sim CSVs under correction variants for the ablation.

Variants (one CLI arg required):
    baseline  - rewrite the columns from sim.csv as-is (sanity check)
    h1        - apply per-segment yaw-bias subtraction to MEASURED channel
    h3        - apply understeer-gradient correction to PREDICTED channel
    h1_h3     - apply both

Reads the existing baseline `sim.csv` per segment (does NOT re-decode rlogs;
the CAN-decode deps are not installed in this environment). Writes alongside
as `sim_<variant>.csv`. Only the four columns
{ yaw_rate_pred_rads, a_y_pred_mps2, yaw_rate_resid_rads, a_y_resid_mps2 }
are changed per variant.

Run order (and the canonical reproducer):

    python3 tools/regenerate_with_corrections.py baseline
    python3 tools/regenerate_with_corrections.py h1
    python3 tools/regenerate_with_corrections.py h3
    python3 tools/regenerate_with_corrections.py h1_h3
    python3 tools/eval_ablation.py
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "tools"))

from parameters import PARAM_BY_PLATFORM  # noqa: E402
from lateral_corrections import (  # noqa: E402
    estimate_yaw_bias,
    understeer_gradient,
    apply_understeer_correction,
)

PLATFORMS = ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1")
VARIANTS = {"baseline", "h1", "h3", "h1_h3"}


def process_segment(csv_in: Path, variant: str, p_st) -> Path:
    df = pd.read_csv(csv_in)
    v = df["v_mps"].to_numpy()
    delta_road = df["delta_road_rad"].to_numpy()
    yaw_meas = df["yaw_rate_meas_rads"].to_numpy()
    ay_meas = df["a_lat_meas_mps2"].to_numpy()

    # baseline pred from CSV
    yaw_pred = df["yaw_rate_pred_rads"].to_numpy().copy()
    ay_pred = df["a_y_pred_mps2"].to_numpy().copy()

    # Apply H3 to predicted channel (changes both yaw_pred and a_y_pred)
    if variant in ("h3", "h1_h3"):
        K_u = understeer_gradient(p_st)
        yaw_pred = apply_understeer_correction(yaw_pred, v, K_u)
        ay_pred = v * yaw_pred  # a_y = v * psi_dot in KS framework

    # Apply H1 to measured channel (subtract per-segment bias)
    yaw_meas_corr = yaw_meas.copy()
    ay_meas_corr = ay_meas.copy()
    if variant in ("h1", "h1_h3"):
        b_hat = estimate_yaw_bias(yaw_meas, delta_road, v)
        yaw_meas_corr = yaw_meas - b_hat
        # The lateral-G measurement BrakeSnData_3 is an independent sensor;
        # a yaw-rate sensor bias does NOT propagate into a_y_meas. So we
        # debias only the yaw channel for the residual against pred. But
        # a_y bias COULD be a separate physical phenomenon — out of scope here,
        # we only treat the yaw bias (H1 as planned).

    df_out = df.copy()
    df_out["yaw_rate_pred_rads"] = yaw_pred
    df_out["a_y_pred_mps2"] = ay_pred
    df_out["yaw_rate_resid_rads"] = yaw_meas_corr - yaw_pred
    df_out["a_y_resid_mps2"] = ay_meas_corr - ay_pred

    out = csv_in.parent / f"sim_{variant}.csv"
    df_out.to_csv(out, index=False, float_format="%.6g")
    return out


def main(variant: str) -> None:
    if variant not in VARIANTS:
        print(f"unknown variant {variant!r}; choose from {sorted(VARIANTS)}", file=sys.stderr)
        sys.exit(2)
    sim_root = ROOT / "data" / "sim" / "segments"
    n = 0
    for plat in PLATFORMS:
        p_st = PARAM_BY_PLATFORM[plat]
        files = sorted(glob.glob(str(sim_root / plat / "**" / "sim.csv"), recursive=True))
        for f in files:
            out = process_segment(Path(f), variant, p_st)
            n += 1
            try:
                print(f"  wrote {out.relative_to(ROOT)}")
            except ValueError:
                print(f"  wrote {out}")
    print(f"variant={variant}: {n} files written")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: regenerate_with_corrections.py <baseline|h1|h3|h1_h3>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1])
