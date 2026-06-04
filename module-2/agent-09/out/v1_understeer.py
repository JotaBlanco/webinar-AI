"""V1: bicycle understeer model. yaw = v * delta / (L + Kus * v^2).

Tesla baseline = V0 (we leave it alone, as schema_note advises).
For Ford/Hyundai we fit (L, Kus) per platform.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT))

import os
os.chdir(ROOT)

from score import score, format_summary
from scipy.optimize import minimize

# Initial wheelbases (rough): Ford F150 lightning ~3.71, Mach-E ~2.98, Ioniq5 ~3.0
DEFAULT_COEFFS = {
    "FORD_F_150_LIGHTNING_MK1": {"L": 3.71, "Kus": 0.0},
    "FORD_MUSTANG_MACH_E_MK1":  {"L": 2.98, "Kus": 0.0},
    "HYUNDAI_IONIQ_5":          {"L": 3.0,  "Kus": 0.0},
}


def make_predict(coeffs_dict):
    def predict(sim_df, platform):
        out = sim_df[["yaw_rate_pred_rads"]].copy()
        if platform == "TESLA_MODEL_3":
            return out
        c = coeffs_dict.get(platform)
        if c is None:
            return out
        L = c["L"]
        Kus = c["Kus"]
        delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
        v = sim_df["v_mps"].to_numpy(dtype=float)
        yr = v * delta / (L + Kus * v * v)
        out["yaw_rate_pred_rads"] = yr
        return out
    return predict


def fit_platform(platform):
    """Fit (L, Kus) for one platform by minimising yaw RMSE on the truth column."""
    # Gather all (v, delta, yr_truth) samples for the platform.
    seg_root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(seg_root.glob("*/**/sim.csv"))
    Vs, Ds, Ys = [], [], []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["v_mps", "delta_road_rad", "yaw_rate_meas_rads"])
        except Exception:
            continue
        m = df["v_mps"] > 2.0
        Vs.append(df.loc[m, "v_mps"].to_numpy())
        Ds.append(df.loc[m, "delta_road_rad"].to_numpy())
        Ys.append(df.loc[m, "yaw_rate_meas_rads"].to_numpy())
    v = np.concatenate(Vs)
    d = np.concatenate(Ds)
    y = np.concatenate(Ys)

    def obj(params):
        L, Kus = params
        if L < 1.5 or L > 6.0:
            return 1e6
        denom = L + Kus * v * v
        if np.any(denom <= 0.1):
            return 1e6
        pred = v * d / denom
        return float(np.mean((pred - y) ** 2))

    from scipy.optimize import minimize
    best = None
    for L0 in (2.5, 3.0, 3.5):
        for K0 in (-0.5, 0.0, 0.5, 1.5):
            r = minimize(obj, x0=[L0, K0], method="Nelder-Mead",
                         options={"xatol": 1e-4, "fatol": 1e-8, "maxiter": 500})
            if best is None or r.fun < best.fun:
                best = r
    L, Kus = best.x
    print(f"  {platform}: L={L:.4f}, Kus={Kus:.5f}, train MSE={best.fun:.6e}")
    return {"L": float(L), "Kus": float(Kus)}


if __name__ == "__main__":
    coeffs = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        coeffs[plat] = fit_platform(plat)
    import json
    (ROOT / "out" / "v1_coeffs.json").write_text(json.dumps(coeffs, indent=2))

    print("\n--- V1 score ---")
    result = score(make_predict(coeffs))
    print(format_summary(result))
    print("\nV1: yaw=%f, cte=%f" % (result["yaw_rate_rmse"], result["cte_rmse"]))
