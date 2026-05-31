"""Per-platform calibration fits for lateral fidelity model.

Models tested:
  V0  : pred = (v/L)*tan(delta_road)         (baseline as in V0 column)
  V1  : pred = g * (v/L)*tan(delta_road) + b (per-platform linear scale + offset)
  V2  : pred = v * delta_road / (L + K*v^2)  (understeer bicycle, fit K per-platform)
  V3  : pred = g * v * delta_road / (L + K*v^2)  + b (full free fit)

All fits done on samples with v > 2 m/s (matching scorer's v-filter).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-09")
sys.path.insert(0, str(ROOT / "code"))
from parameters import PARAM_BY_PLATFORM  # noqa: E402

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]
SIM_ROOT = ROOT / "data" / "sim" / "segments"

# Default wheelbase for HYUNDAI_IONIQ_5 (not in parameters.py). Source: spec sheet 3.0 m.
HYUNDAI_L = 3.0


def L_for(platform: str) -> float:
    if platform == "HYUNDAI_IONIQ_5":
        return HYUNDAI_L
    return PARAM_BY_PLATFORM[platform].L


def load_platform_samples(platform: str, max_segs: int | None = None, v_min: float = 2.0) -> pd.DataFrame:
    """Concatenate samples (v>v_min) across all segments for one platform.

    Tesla has no truth column → returns empty.
    """
    segs = sorted((SIM_ROOT / platform).glob("**/sim.csv"))
    if max_segs:
        segs = segs[:max_segs]
    parts = []
    for p in segs:
        try:
            df = pd.read_csv(p, usecols=lambda c: c in {
                "t_s", "delta_road_rad", "v_mps", "yaw_rate_meas_rads", "yaw_rate_pred_rads", "psi_dot_rads"
            })
        except Exception:
            continue
        # Some platforms (Tesla) use psi_dot_rads instead of yaw_rate_meas_rads
        truth_col = "yaw_rate_meas_rads" if "yaw_rate_meas_rads" in df.columns else (
            "psi_dot_rads" if "psi_dot_rads" in df.columns else None
        )
        if truth_col is None or "delta_road_rad" not in df.columns or "v_mps" not in df.columns:
            continue
        df = df.rename(columns={truth_col: "yaw_truth"})
        df = df[df["v_mps"] > v_min].copy()
        if len(df) == 0:
            continue
        parts.append(df[["delta_road_rad", "v_mps", "yaw_truth"] +
                        (["yaw_rate_pred_rads"] if "yaw_rate_pred_rads" in df.columns else [])])
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def fit_platform(platform: str) -> dict:
    df = load_platform_samples(platform)
    print(f"\n== {platform}: {len(df):,} samples ==")
    if len(df) == 0:
        return {"platform": platform, "fit": "no_truth"}

    L = L_for(platform)
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    truth = df["yaw_truth"].to_numpy()

    # V0 — pure kinematic
    v0 = (v / L) * np.tan(delta)
    print(f"  V0 RMSE (recomputed): {rmse(v0, truth):.6f}")
    if "yaw_rate_pred_rads" in df.columns:
        baseline = df["yaw_rate_pred_rads"].to_numpy()
        print(f"  V0 RMSE (from CSV)   : {rmse(baseline, truth):.6f}")

    # V1 — g, b linear
    # min sum (g*v0 + b - truth)^2 — closed-form
    X = np.column_stack([v0, np.ones_like(v0)])
    coef, *_ = np.linalg.lstsq(X, truth, rcond=None)
    g1, b1 = float(coef[0]), float(coef[1])
    v1 = g1 * v0 + b1
    print(f"  V1 g={g1:.4f}, b={b1:+.6f}, RMSE={rmse(v1, truth):.6f}")

    # V2 — understeer bicycle: yr = v * delta / (L + K*v^2)
    def loss_v2(params):
        K = params[0]
        denom = L + K * v * v
        pred = v * delta / denom
        return float(np.mean((pred - truth) ** 2))

    res2 = minimize(loss_v2, x0=[0.001], method="Nelder-Mead")
    K2 = float(res2.x[0])
    v2 = v * delta / (L + K2 * v * v)
    print(f"  V2 K={K2:.6f}, RMSE={rmse(v2, truth):.6f}")

    # V3 — g, b, K free
    def loss_v3(params):
        g, b, K = params
        denom = L + K * v * v
        pred = g * v * delta / denom + b
        return float(np.mean((pred - truth) ** 2))

    res3 = minimize(loss_v3, x0=[1.0, 0.0, K2], method="Nelder-Mead",
                    options={"xatol": 1e-6, "fatol": 1e-10, "maxiter": 2000})
    g3, b3, K3 = map(float, res3.x)
    v3pred = g3 * v * delta / (L + K3 * v * v) + b3
    print(f"  V3 g={g3:.4f}, b={b3:+.6f}, K={K3:.6f}, RMSE={rmse(v3pred, truth):.6f}")

    return {
        "platform": platform,
        "L": L,
        "n_samples": int(len(df)),
        "rmse_v0_recomp": rmse(v0, truth),
        "v1": {"g": g1, "b": b1, "rmse": rmse(v1, truth)},
        "v2": {"K": K2, "rmse": rmse(v2, truth)},
        "v3": {"g": g3, "b": b3, "K": K3, "rmse": rmse(v3pred, truth)},
    }


def main():
    results = {}
    for plat in PLATFORMS:
        results[plat] = fit_platform(plat)
    out = ROOT / "out" / "fit_results.json"
    with out.open("w") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
