"""Fit per-platform linear bicycle (understeer-gradient) coefficients.

Model:
    yaw_rate = k_delta * (v / L) * tan(delta_road) / (1 + Ku * v^2) + b

For each platform, fit (k_delta, Ku, b) by minimising pooled yaw-rate squared
error across all sim/segments. v_mps filter > 2.0 to match scorer.

Outputs `out/coeffs.json` keyed by platform.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from parameters import PARAM_BY_PLATFORM  # noqa: E402

PLATFORM_L = {
    "FORD_F_150_LIGHTNING_MK1": PARAM_BY_PLATFORM["FORD_F_150_LIGHTNING_MK1"].L,
    "FORD_MUSTANG_MACH_E_MK1":  PARAM_BY_PLATFORM["FORD_MUSTANG_MACH_E_MK1"].L,
    "TESLA_MODEL_3":            PARAM_BY_PLATFORM["TESLA_MODEL_3"].L,
    # Hyundai not in PARAM_BY_PLATFORM — use Tesla-like wheelbase as initial
    # guess; the fit absorbs it through k_delta. Source: Ioniq 5 spec ≈ 3.0 m.
    "HYUNDAI_IONIQ_5":          3.0,
}

TRUTH_COL = {
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1":  "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5":          "yaw_rate_meas_rads",
    "TESLA_MODEL_3":            "psi_dot_rads",
}


def load_platform(platform: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return concatenated (kin, v2, yaw_truth) arrays for one platform,
    v-filtered.

    kin = (v / L) * tan(delta_road_rad)  (V0 kinematic prediction)
    v2  = v^2
    """
    root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(root.glob("**/sim.csv"))
    L = PLATFORM_L[platform]
    tc = TRUTH_COL[platform]
    kin_all = []
    v2_all = []
    yt_all = []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=lambda c: c in {"v_mps", "delta_road_rad", tc, "t_s"})
        except Exception:
            continue
        if tc not in df.columns:
            continue
        v = df["v_mps"].to_numpy(dtype=float)
        d = df["delta_road_rad"].to_numpy(dtype=float)
        yt = df[tc].to_numpy(dtype=float)
        mask = v > 2.0
        if not mask.any():
            continue
        kin = (v / L) * np.tan(d)
        kin_all.append(kin[mask])
        v2_all.append((v * v)[mask])
        yt_all.append(yt[mask])
    if not kin_all:
        return np.empty(0), np.empty(0), np.empty(0)
    return (
        np.concatenate(kin_all),
        np.concatenate(v2_all),
        np.concatenate(yt_all),
    )


def fit_one(kin: np.ndarray, v2: np.ndarray, yt: np.ndarray) -> dict:
    """Fit (k_delta, Ku, b) minimising sum (y - (k*kin/(1+Ku*v2) + b))^2.

    Reduce: for fixed Ku, the model is linear in (k, b):
        y ~ k * f(Ku) + b,  where f = kin / (1 + Ku*v2)
    so closed-form LSQ for (k, b) given Ku. Then 1-D search over Ku.
    """
    def obj_for_Ku(Ku: float) -> float:
        f = kin / (1.0 + Ku * v2)
        # Solve least squares y = k*f + b
        A = np.column_stack([f, np.ones_like(f)])
        # Use normal equations directly for speed
        AT_A = A.T @ A
        AT_y = A.T @ yt
        try:
            k, b = np.linalg.solve(AT_A, AT_y)
        except np.linalg.LinAlgError:
            return 1e18
        r = yt - (k * f + b)
        return float(r @ r)

    res = minimize_scalar(obj_for_Ku, bounds=(-0.005, 0.02), method="bounded",
                          options={"xatol": 1e-6})
    Ku = float(res.x)
    f = kin / (1.0 + Ku * v2)
    A = np.column_stack([f, np.ones_like(f)])
    k, b = np.linalg.solve(A.T @ A, A.T @ yt)
    r = yt - (k * f + b)
    rmse = math.sqrt(float(r @ r) / len(yt))
    # V0 rmse for comparison
    r0 = yt - kin
    rmse0 = math.sqrt(float(r0 @ r0) / len(yt))
    return {
        "k_delta": float(k),
        "Ku": Ku,
        "b": float(b),
        "n": int(len(yt)),
        "rmse_fit": rmse,
        "rmse_v0": rmse0,
    }


def main():
    coeffs = {}
    for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1",
                 "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"):
        kin, v2, yt = load_platform(plat)
        if len(kin) == 0:
            print(f"[skip] {plat}: no data")
            continue
        info = fit_one(kin, v2, yt)
        info["L"] = PLATFORM_L[plat]
        coeffs[plat] = info
        print(f"{plat}: k={info['k_delta']:.4f}, Ku={info['Ku']:.5f}, b={info['b']:+.5f}, "
              f"rmse_v0={info['rmse_v0']:.5f} -> rmse_fit={info['rmse_fit']:.5f}, n={info['n']:,}")

    out_path = ROOT / "out" / "coeffs.json"
    with out_path.open("w") as fh:
        json.dump(coeffs, fh, indent=2)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
