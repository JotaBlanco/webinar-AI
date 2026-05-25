"""Ablation study for KS lateral fidelity on the Ford platforms.

Reads each Ford sim CSV (inputs + measured truth), recomputes lateral
predictions under several model variants, and reports RMSE deltas.

All variants stay in *speed-known, lateral-only* mode (clamp v and delta to
the measured values; predict only psi_dot and a_y from those).

Variants:
    0. baseline                 : KS, official params
    1. yaw_bias                 : subtract per-segment mean yaw_rate_resid (bias-only)
    2. linear_st                : single-track linear-tyre understeer correction
                                  applied analytically (closed-form steady-state)
    3. linear_st + yaw_bias     : both
    4. wheelbase_fit            : recompute an "effective L" that minimises
                                  yaw RMSE per platform (regression on segment 1
                                  only — segment 2 used as held-out check)

For each variant we report RMSE_psi_dot [deg/s] and RMSE_a_y [m/s^2] per
segment and per platform (mean across segments).

Usage:
    python3 run_ablation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CODE = HERE / "code"
sys.path.insert(0, str(CODE))

from parameters import (  # noqa: E402
    MACH_E,
    F150_LIGHTNING,
)

DATA_SIM = HERE / "data" / "sim" / "segments"

SEGMENTS = {
    "FORD_MUSTANG_MACH_E_MK1": [
        DATA_SIM / "FORD_MUSTANG_MACH_E_MK1/08ec7b9afc6b766e/00000000--33439c2a9c/1/sim.csv",
        DATA_SIM / "FORD_MUSTANG_MACH_E_MK1/112bd787ceca718d/00000003--55220ffbee/12/sim.csv",
    ],
    "FORD_F_150_LIGHTNING_MK1": [
        DATA_SIM / "FORD_F_150_LIGHTNING_MK1/0b2c0bec9a28eb0f/00000001--82c7a5f419/34/sim.csv",
        DATA_SIM / "FORD_F_150_LIGHTNING_MK1/112e4d6e0cad05e1/00000001--3975f8fbf5/9/sim.csv",
    ],
}

PARAMS = {
    "FORD_MUSTANG_MACH_E_MK1": MACH_E,
    "FORD_F_150_LIGHTNING_MK1": F150_LIGHTNING,
}


# ---------------------------------------------------------------------------
# Model variants — all return (psi_dot_pred, a_y_pred) arrays of len N.
# Inputs are arrays in SI units. All use the speed-known, clamped scheme.
# ---------------------------------------------------------------------------

def predict_ks(delta_rad: np.ndarray, v_mps: np.ndarray, L: float):
    """Baseline KS prediction in speed-known mode (matches official sim)."""
    psi_dot = (v_mps / L) * np.tan(delta_rad)
    a_y = v_mps * psi_dot
    return psi_dot, a_y


def predict_ks_with_bias(delta_rad, v_mps, L, yaw_bias_rads, ay_bias_mps2):
    """KS + constant bias correction (one scalar per channel, per platform)."""
    psi_dot, a_y = predict_ks(delta_rad, v_mps, L)
    return psi_dot + yaw_bias_rads, a_y + ay_bias_mps2


def predict_linear_st_steady(delta_rad, v_mps, p):
    """Linear single-track (Ackermann + understeer gradient), steady-state form.

    Classical bicycle understeer formula:
        psi_dot = v * delta / (L + K_us * v^2)
    where  K_us = (m / L) * ( l_r / C_alpha_f  -  l_f / C_alpha_r ) .

    For modest sideslip this is the closed-form steady-state yaw response of
    the linear ST model. It is a strict improvement over KS in the high-speed
    cornering regime because it captures the speed-dependent yaw-gain droop
    (understeer). For Mach-E and F-150, K_us > 0 (rear-biased EVs with stiff
    rear tyres are still mildly understeering once you factor the mass).
    """
    L = p.L
    m, l_f, l_r = p.m, p.l_f, p.l_r
    Cf, Cr = p.C_alpha_f, p.C_alpha_r
    K_us = (m / L) * (l_r / Cf - l_f / Cr)
    psi_dot = v_mps * delta_rad / (L + K_us * v_mps ** 2)
    a_y = v_mps * psi_dot
    return psi_dot, a_y


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def evaluate_segment(df, p, variant: str, calib: dict | None = None):
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    yaw_meas = df["yaw_rate_meas_rads"].to_numpy()
    ay_meas = df["a_lat_meas_mps2"].to_numpy()

    if variant == "baseline":
        psi_dot, a_y = predict_ks(delta, v, p.L)
    elif variant == "yaw_bias":
        # Use the official baseline residual mean as the bias estimate.
        yaw_b = calib["yaw_bias"]
        ay_b = calib["ay_bias"]
        psi_dot, a_y = predict_ks_with_bias(delta, v, p.L, yaw_b, ay_b)
    elif variant == "linear_st":
        psi_dot, a_y = predict_linear_st_steady(delta, v, p)
    elif variant == "linear_st+bias":
        psi_dot_b, a_y_b = predict_linear_st_steady(delta, v, p)
        psi_dot = psi_dot_b + calib["yaw_bias"]
        a_y = a_y_b + calib["ay_bias"]
    elif variant == "wheelbase_fit":
        L_eff = calib["L_eff"]
        psi_dot, a_y = predict_ks(delta, v, L_eff)
    else:
        raise ValueError(variant)

    return {
        "rmse_yaw_degs": np.degrees(rmse(yaw_meas, psi_dot)),
        "rmse_ay_mps2": rmse(ay_meas, a_y),
        "corr_yaw": float(np.corrcoef(yaw_meas, psi_dot)[0, 1]),
        "corr_ay": float(np.corrcoef(ay_meas, a_y)[0, 1]),
        "n": len(df),
    }


def fit_effective_L(df, p):
    """Pick L that minimises yaw_rate RMSE in the KS form, holding delta and v.

    psi_dot_pred = (v / L) tan(delta). Closed-form LS for 1/L:
        let A = v tan(delta), then meas ≈ A / L =>  1/L = sum(A*meas) / sum(A*A).
    Clip to a sane range.
    """
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    yaw_meas = df["yaw_rate_meas_rads"].to_numpy()
    A = v * np.tan(delta)
    inv_L = np.sum(A * yaw_meas) / np.sum(A * A)
    L_eff = 1.0 / inv_L
    return L_eff


def bias_from_segment(df, p):
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    yaw_meas = df["yaw_rate_meas_rads"].to_numpy()
    ay_meas = df["a_lat_meas_mps2"].to_numpy()
    psi_dot, a_y = predict_ks(delta, v, p.L)
    return {
        "yaw_bias": float(np.mean(yaw_meas - psi_dot)),
        "ay_bias": float(np.mean(ay_meas - a_y)),
    }


# ---------------------------------------------------------------------------
# Regime analysis
# ---------------------------------------------------------------------------

def regime_breakdown(df, p):
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    yaw_meas = df["yaw_rate_meas_rads"].to_numpy()
    ay_meas = df["a_lat_meas_mps2"].to_numpy()
    psi_dot, a_y = predict_ks(delta, v, p.L)
    res_yaw = yaw_meas - psi_dot
    res_ay = ay_meas - a_y

    out = {}
    for label, mask in [
        ("v<5",      v < 5),
        ("5<=v<15",  (v >= 5) & (v < 15)),
        ("v>=15",    v >= 15),
        ("|ay|<1",   np.abs(ay_meas) < 1.0),
        ("|ay|>=1",  np.abs(ay_meas) >= 1.0),
    ]:
        n = int(mask.sum())
        if n == 0:
            continue
        out[label] = {
            "n": n,
            "rmse_yaw_degs": np.degrees(rmse(yaw_meas[mask], psi_dot[mask])),
            "rmse_ay_mps2": rmse(ay_meas[mask], a_y[mask]),
            "mean_yaw_resid_degs": np.degrees(np.mean(res_yaw[mask])),
            "mean_ay_resid_mps2": float(np.mean(res_ay[mask])),
        }
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 80)
    print("KS lateral-fidelity ablation — Ford Mach-E and F-150 Lightning")
    print("=" * 80)

    summary_rows = []
    regime_rows = []

    for platform, paths in SEGMENTS.items():
        p = PARAMS[platform]
        L_orig = p.L
        print(f"\n## Platform: {platform}   (L={L_orig:.3f} m, m={p.m:.0f} kg)")

        # Calibration: bias and L_eff from segment 1 (the "calibration" segment).
        df_cal = pd.read_csv(paths[0])
        calib = bias_from_segment(df_cal, p)
        calib["L_eff"] = fit_effective_L(df_cal, p)
        print(f"  Calibration on seg-1:")
        print(f"    yaw bias  = {np.degrees(calib['yaw_bias']):+.3f} deg/s")
        print(f"    ay  bias  = {calib['ay_bias']:+.4f} m/s²")
        print(f"    L_eff     = {calib['L_eff']:.3f} m   (vs nominal {L_orig:.3f})")

        # Regime breakdown (baseline only) using seg-1.
        regimes = regime_breakdown(df_cal, p)
        print(f"  Regime breakdown (seg-1, baseline):")
        for k, v in regimes.items():
            print(f"    {k:>10s}: n={v['n']:5d}  "
                  f"RMSE_ψ̇={v['rmse_yaw_degs']:5.3f}°/s  "
                  f"RMSE_ay={v['rmse_ay_mps2']:5.3f}m/s²  "
                  f"mean_resid_ψ̇={v['mean_yaw_resid_degs']:+5.3f}°/s")
            regime_rows.append({"platform": platform, "regime": k, **v})

        for seg_idx, path in enumerate(paths, start=1):
            df = pd.read_csv(path)
            for variant in [
                "baseline",
                "yaw_bias",
                "linear_st",
                "linear_st+bias",
                "wheelbase_fit",
            ]:
                m = evaluate_segment(df, p, variant, calib)
                row = {
                    "platform": platform,
                    "segment": seg_idx,
                    "variant": variant,
                    **m,
                }
                summary_rows.append(row)

    df = pd.DataFrame(summary_rows)

    # Aggregate per platform (mean over segments).
    agg = (df.groupby(["platform", "variant"], sort=False)
             .agg(rmse_yaw_degs=("rmse_yaw_degs", "mean"),
                  rmse_ay_mps2=("rmse_ay_mps2", "mean"),
                  corr_yaw=("corr_yaw", "mean"),
                  corr_ay=("corr_ay", "mean"))
             .reset_index())

    print("\n" + "=" * 80)
    print("PER-SEGMENT RESULTS")
    print("=" * 80)
    print(df.to_string(index=False, float_format=lambda x: f"{x:7.4f}"))

    print("\n" + "=" * 80)
    print("AGGREGATE (mean across 2 segments per platform)")
    print("=" * 80)
    print(agg.to_string(index=False, float_format=lambda x: f"{x:7.4f}"))

    # Save artefacts.
    df.to_csv(HERE / "ablation_results.csv", index=False)
    agg.to_csv(HERE / "ablation_aggregate.csv", index=False)
    pd.DataFrame(regime_rows).to_csv(HERE / "regime_breakdown.csv", index=False)
    print(f"\nWrote: ablation_results.csv, ablation_aggregate.csv, regime_breakdown.csv")


if __name__ == "__main__":
    main()
