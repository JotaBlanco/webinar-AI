"""Post-process baseline KS sim CSVs to apply yaw-rate corrections.

Two variants:
  A: linear-bicycle understeer correction
        ψ̇_corr = ψ̇_KS / (1 + K_us · v²)
     with K_us computed from openpilot-canonical ST parameters.
  B (layered on A): per-segment yaw-rate bias removed at low-|δ| samples.

Inputs:  data/sim/segments/FORD_*/<device>/<route>/<idx>/sim.csv
Outputs: out/sim_<variant>/segments/FORD_*/<device>/<route>/<idx>/sim.csv

Run:
    python3 out/postprocess.py A
    python3 out/postprocess.py AB
    python3 out/postprocess.py both       # writes both variant trees
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Make code/parameters.py importable for canonical K_us computation.
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "code"))
from parameters import PARAM_BY_PLATFORM  # noqa: E402


def understeer_gradient(p) -> float:
    """K_us [s²/m²] for the linear bicycle model.

    K_us = m * (l_r * C_alpha_f - l_f * C_alpha_r) / (L² * C_alpha_f * C_alpha_r)

    > 0  → understeer (steady-state yaw < kinematic prediction)
    < 0  → oversteer
    """
    return (p.m * (p.l_r * p.C_alpha_f - p.l_f * p.C_alpha_r)
            / (p.L ** 2 * p.C_alpha_f * p.C_alpha_r))


def apply_variant_A(df: pd.DataFrame, p) -> pd.DataFrame:
    """Understeer-gradient correction."""
    K_us = understeer_gradient(p)
    v = df["v_state_mps"].values
    # Baseline KS prediction reconstructed analytically (verified to match
    # the CSV's yaw_rate_pred_rads to <1e-6 rad/s in spot checks).
    psi_dot_ks = (v / p.L) * np.tan(df["delta_state_rad"].values)
    psi_dot_corr = psi_dot_ks / (1.0 + K_us * v ** 2)
    a_y_corr = v * psi_dot_corr
    out = df.copy()
    out["yaw_rate_pred_rads"] = psi_dot_corr
    out["a_y_pred_mps2"] = a_y_corr
    out["yaw_rate_resid_rads"] = out["yaw_rate_meas_rads"] - psi_dot_corr
    out["a_y_resid_mps2"] = out["a_lat_meas_mps2"] - a_y_corr
    return out


def apply_variant_B(df: pd.DataFrame) -> pd.DataFrame:
    """Per-segment yaw-rate bias removal at low |δ_road|.

    Estimates bias as mean(resid) on samples where |δ_road| < 0.005 rad.
    Caps |bias| at 0.03 rad/s. If too few low-δ samples, falls back to overall
    mean residual.
    """
    delta = df["delta_road_rad"].values
    resid = df["yaw_rate_resid_rads"].values
    mask = np.abs(delta) < 0.005
    if mask.sum() >= 50:
        bias = float(np.mean(resid[mask]))
    else:
        bias = float(np.mean(resid))
    bias = float(np.clip(bias, -0.03, 0.03))
    psi_dot_corr = df["yaw_rate_pred_rads"].values + bias
    v = df["v_state_mps"].values
    a_y_corr = v * psi_dot_corr
    out = df.copy()
    out["yaw_rate_pred_rads"] = psi_dot_corr
    out["a_y_pred_mps2"] = a_y_corr
    out["yaw_rate_resid_rads"] = out["yaw_rate_meas_rads"] - psi_dot_corr
    out["a_y_resid_mps2"] = out["a_lat_meas_mps2"] - a_y_corr
    out.attrs["bias_applied_rads"] = bias
    return out


def process(variant: str):
    src_root = HERE / "data" / "sim" / "segments"
    dst_root = HERE / "out" / f"sim_{variant}" / "segments"
    biases = []
    for plat in ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]:
        p = PARAM_BY_PLATFORM[plat]
        K_us = understeer_gradient(p)
        print(f"[{variant}] {plat}: K_us = {K_us:.6e} s²/m²  "
              f"(softening factor at v=30 m/s: {1+K_us*900:.3f})")
        for csv in sorted((src_root / plat).rglob("*.csv")):
            df = pd.read_csv(csv)
            if variant == "A":
                df_out = apply_variant_A(df, p)
            elif variant == "AB":
                df_a = apply_variant_A(df, p)
                df_out = apply_variant_B(df_a)
                biases.append((plat, csv.parts[-3], csv.parts[-2],
                               df_out.attrs.get("bias_applied_rads", 0.0)))
            else:
                raise ValueError(variant)
            rel = csv.relative_to(src_root)
            dst = dst_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            df_out.to_csv(dst, index=False)
    if biases:
        print(f"\n[{variant}] per-segment biases applied (rad/s):")
        for plat, dev, route, b in biases:
            print(f"  {plat[5:14]} {dev[:6]}/{route}: {b:+.5f}  ({b*180/math.pi:+.3f} °/s)")


if __name__ == "__main__":
    args = sys.argv[1:] or ["both"]
    if args == ["both"]:
        process("A")
        process("AB")
    else:
        for v in args:
            process(v)
