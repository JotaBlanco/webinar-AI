"""Lateral-fidelity ablation for the KS model on Ford rlog segments.

Reads the pre-generated sim CSVs (already include `yaw_rate_pred_rads`,
`a_y_pred_mps2`, `yaw_rate_meas_rads`, `a_lat_meas_mps2`) and re-computes
the predictions under successive model variants:

  V0  baseline KS                    : ψ̇ = (v/L)·tan(δ)
  V1  KS + yaw-rate sensor de-bias    : subtract the mean(ψ̇_meas - ψ̇_pred) on
                                         straight-line samples (|δ|<0.3° and
                                         |ψ̇_meas|<0.5°/s).
  V2  ST steady-state (understeer)    : ψ̇ = (v/L)·δ / (1 + K_us·v²),
                                         K_us = m·(l_r·C_alpha_r - l_f·C_alpha_f) /
                                                (L²·C_alpha_f·C_alpha_r). Linear
                                         bicycle steady-state. Drops the
                                         KS small-angle approximation; captures
                                         tyre compliance.
  V3  V2 + yaw-rate sensor de-bias    : V2 followed by the same offset removal.

For each platform, prints RMSE (yaw rate °/s, a_y m/s²) and writes the
ablation table to a CSV. Also produces a regime breakdown (binned by |v| and
|a_y|) for the baseline.

Run from the module root:

    python3 ablation.py
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

MODULE_DIR = Path(__file__).resolve().parent
CODE_DIR = (MODULE_DIR / "code").resolve()
DATA_DIR = (MODULE_DIR / "data").resolve()
sys.path.insert(0, str(CODE_DIR))

from parameters import PARAM_BY_PLATFORM  # noqa: E402

FORD_PLATFORMS = ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1")

# ---------- residual helpers --------------------------------------------------


def rmse(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2)))


def corrcoef(a: np.ndarray, b: np.ndarray) -> float:
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


# ---------- model variants ----------------------------------------------------


def predict_v0_ks(df: pd.DataFrame, p) -> tuple[np.ndarray, np.ndarray]:
    """Baseline KS — exactly what the CSV already has, but recomputed here so
    the same code path is reused across all variants."""
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    psi_dot = (v / p.L) * np.tan(delta)
    a_y = v * psi_dot
    return psi_dot, a_y


def predict_v2_st_steady(df: pd.DataFrame, p) -> tuple[np.ndarray, np.ndarray]:
    """Linear single-track steady-state (understeer gradient form).

    From the linear bicycle:
        ψ̇_ss = (v/L) · δ / (1 + K_us · v²)
    where the understeer gradient K_us has units s²/m²:
        K_us = m · (l_r · C_alpha_r - l_f · C_alpha_f) / (L² · C_alpha_f · C_alpha_r)

    Note sign: if the car is rear-biased (l_r·C_alpha_r > l_f·C_alpha_f),
    K_us > 0 → understeer → ψ̇_ss < ψ̇_KS, which is exactly the residual
    direction we see in the Ford data.
    """
    m = p.m
    L = p.L
    l_f = p.l_f
    l_r = p.l_r
    C_f = p.C_alpha_f
    C_r = p.C_alpha_r
    K_us = m * (l_r * C_r - l_f * C_f) / (L ** 2 * C_f * C_r)
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    psi_dot = (v / L) * delta / (1.0 + K_us * v ** 2)
    a_y = v * psi_dot
    return psi_dot, a_y


def yaw_bias_offset(psi_dot_pred: np.ndarray, psi_dot_meas: np.ndarray,
                    delta: np.ndarray) -> float:
    """Mean residual on straight-line samples (used as sensor de-bias)."""
    mask = (np.abs(delta) < np.radians(0.3 / 17.0)) & (np.abs(psi_dot_meas) < np.radians(0.5))
    if mask.sum() < 50:
        # fall back to slightly relaxed mask
        mask = (np.abs(delta) < np.radians(2.0 / 17.0)) & (np.abs(psi_dot_meas) < np.radians(1.5))
    if mask.sum() < 20:
        return 0.0
    return float(np.mean(psi_dot_meas[mask] - psi_dot_pred[mask]))


# ---------- regime breakdown --------------------------------------------------


def regime_breakdown(df: pd.DataFrame, resid_yaw_rads: np.ndarray) -> str:
    v = df["v_mps"].to_numpy()
    a_y = df["a_lat_meas_mps2"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    lines = []

    def _bin(mask, label):
        if mask.sum() < 10:
            return None
        return f"  {label:25s} N={mask.sum():5d}  RMSE_ψ̇={np.degrees(rmse(resid_yaw_rads[mask])):.3f} °/s"

    # by speed
    for lo, hi in [(0, 10), (10, 20), (20, 30), (30, 50)]:
        mask = (v >= lo) & (v < hi)
        line = _bin(mask, f"v∈[{lo:2d},{hi:2d}) m/s")
        if line:
            lines.append(line)
    # by |a_y|
    for lo, hi in [(0, 1), (1, 2), (2, 4), (4, 10)]:
        mask = (np.abs(a_y) >= lo) & (np.abs(a_y) < hi)
        line = _bin(mask, f"|a_y|∈[{lo:.0f},{hi:.0f}) m/s²")
        if line:
            lines.append(line)
    # by |δ| (road-wheel)
    for lo_deg, hi_deg in [(0, 1), (1, 3), (3, 6), (6, 30)]:
        lo = np.radians(lo_deg)
        hi = np.radians(hi_deg)
        mask = (np.abs(delta) >= lo) & (np.abs(delta) < hi)
        line = _bin(mask, f"|δ_road|∈[{lo_deg},{hi_deg})°")
        if line:
            lines.append(line)
    return "\n".join(lines)


# ---------- per-segment runner ------------------------------------------------


def collect_csvs(platform: str) -> list[Path]:
    root = DATA_DIR / "sim" / "segments" / platform
    return sorted(root.glob("**/sim.csv"))


def run_variants_on_csv(csv_path: Path, p) -> dict:
    df = pd.read_csv(csv_path)
    psi_meas = df["yaw_rate_meas_rads"].to_numpy()
    ay_meas = df["a_lat_meas_mps2"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()

    out: dict = {"csv": csv_path, "N": len(df)}

    # V0 baseline KS
    psi_v0, ay_v0 = predict_v0_ks(df, p)
    out["V0"] = dict(
        psi_resid_rads=psi_meas - psi_v0,
        ay_resid_mps2=ay_meas - ay_v0,
        psi_pred=psi_v0,
        ay_pred=ay_v0,
    )

    # V1 KS + yaw bias
    b1 = yaw_bias_offset(psi_v0, psi_meas, delta)
    psi_v1 = psi_v0 + b1
    ay_v1 = ay_v0 + df["v_mps"].to_numpy() * b1
    out["V1"] = dict(
        bias_rads=b1,
        psi_resid_rads=psi_meas - psi_v1,
        ay_resid_mps2=ay_meas - ay_v1,
        psi_pred=psi_v1,
        ay_pred=ay_v1,
    )

    # V2 ST steady-state
    psi_v2, ay_v2 = predict_v2_st_steady(df, p)
    out["V2"] = dict(
        psi_resid_rads=psi_meas - psi_v2,
        ay_resid_mps2=ay_meas - ay_v2,
        psi_pred=psi_v2,
        ay_pred=ay_v2,
    )

    # V3 ST steady-state + yaw bias
    b3 = yaw_bias_offset(psi_v2, psi_meas, delta)
    psi_v3 = psi_v2 + b3
    ay_v3 = ay_v2 + df["v_mps"].to_numpy() * b3
    out["V3"] = dict(
        bias_rads=b3,
        psi_resid_rads=psi_meas - psi_v3,
        ay_resid_mps2=ay_meas - ay_v3,
        psi_pred=psi_v3,
        ay_pred=ay_v3,
    )

    return out


def aggregate_platform(platform: str) -> dict:
    p = PARAM_BY_PLATFORM[platform]
    csvs = collect_csvs(platform)
    if not csvs:
        return {}

    # concatenate residuals across all segments
    cat = {v: {"psi_resid": [], "ay_resid": [], "psi_meas": [], "ay_meas": [],
               "psi_pred": [], "ay_pred": []}
           for v in ("V0", "V1", "V2", "V3")}
    biases_v1 = []
    biases_v3 = []
    df_all = []
    resid_yaw_v0_all = []

    for csvp in csvs:
        df = pd.read_csv(csvp)
        df_all.append(df)
        r = run_variants_on_csv(csvp, p)
        biases_v1.append(r["V1"]["bias_rads"])
        biases_v3.append(r["V3"]["bias_rads"])
        for v in ("V0", "V1", "V2", "V3"):
            cat[v]["psi_resid"].append(r[v]["psi_resid_rads"])
            cat[v]["ay_resid"].append(r[v]["ay_resid_mps2"])
            cat[v]["psi_meas"].append(df["yaw_rate_meas_rads"].to_numpy())
            cat[v]["ay_meas"].append(df["a_lat_meas_mps2"].to_numpy())
            cat[v]["psi_pred"].append(r[v]["psi_pred"])
            cat[v]["ay_pred"].append(r[v]["ay_pred"])
        resid_yaw_v0_all.append(r["V0"]["psi_resid_rads"])

    df_full = pd.concat(df_all, ignore_index=True)
    resid_yaw_v0_full = np.concatenate(resid_yaw_v0_all)

    rows = []
    for v in ("V0", "V1", "V2", "V3"):
        psi_resid = np.concatenate(cat[v]["psi_resid"])
        ay_resid = np.concatenate(cat[v]["ay_resid"])
        psi_meas = np.concatenate(cat[v]["psi_meas"])
        ay_meas = np.concatenate(cat[v]["ay_meas"])
        psi_pred = np.concatenate(cat[v]["psi_pred"])
        ay_pred = np.concatenate(cat[v]["ay_pred"])
        rows.append({
            "variant": v,
            "N": len(psi_resid),
            "rmse_yaw_degs": np.degrees(rmse(psi_resid)),
            "rmse_ay_mps2": rmse(ay_resid),
            "mean_yaw_resid_degs": np.degrees(np.mean(psi_resid)),
            "mean_ay_resid_mps2": float(np.mean(ay_resid)),
            "corr_yaw": corrcoef(psi_pred, psi_meas),
            "corr_ay": corrcoef(ay_pred, ay_meas),
        })

    table = pd.DataFrame(rows)
    regime = regime_breakdown(df_full, resid_yaw_v0_full)
    return {
        "table": table,
        "regime": regime,
        "biases_v1_degs": [float(np.degrees(b)) for b in biases_v1],
        "biases_v3_degs": [float(np.degrees(b)) for b in biases_v3],
        "platform_params": p,
        "n_segments": len(csvs),
    }


def main():
    all_results = {}
    for plat in FORD_PLATFORMS:
        print(f"\n========== {plat} ==========")
        r = aggregate_platform(plat)
        if not r:
            print("  (no sim CSVs found)")
            continue
        print(r["table"].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
        print("\nRegime breakdown (V0 baseline):")
        print(r["regime"])
        print(f"\nPer-segment V1 yaw bias (°/s) used: {r['biases_v1_degs']}")
        print(f"Per-segment V3 yaw bias (°/s) used: {r['biases_v3_degs']}")
        all_results[plat] = r

    # write a combined ablation CSV
    out = MODULE_DIR / "ablation_results.csv"
    rows = []
    for plat, r in all_results.items():
        for _, row in r["table"].iterrows():
            rows.append({"platform": plat, **row.to_dict()})
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
