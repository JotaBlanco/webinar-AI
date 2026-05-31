"""Inspect what drives the V0 residual: gain, understeer, speed dependence."""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07")
sys.path.insert(0, str(ROOT / "code"))

WHEELBASE_M = {
    "TESLA_MODEL_3": 2.875, "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70, "HYUNDAI_IONIQ_5": 3.00,
}


def collect(platform):
    segs = sorted((ROOT / "data" / "sim" / "segments" / platform).rglob("sim.csv"))
    chunks = []
    for p in segs:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        df = df[["t_s","v_mps","delta_road_rad","yaw_rate_meas_rads","a_long_mps2"]].copy()
        df["platform"] = platform
        # Mask: v>2 and reasonable
        df = df[df["v_mps"] > 2].copy()
        if len(df):
            chunks.append(df)
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()


def fit_understeer(platform):
    """Fit yr_truth = v * delta / (L + K * v^2) by least squares for K and L_eff."""
    df = collect(platform)
    if len(df) == 0:
        return None
    L = WHEELBASE_M[platform]
    v = df["v_mps"].to_numpy(float)
    d = df["delta_road_rad"].to_numpy(float)
    y = df["yaw_rate_meas_rads"].to_numpy(float)
    # Filter out near-zero steering (avoid /0 issues, and zero info)
    mask = (np.abs(d) > 0.002) & (v > 3) & (np.abs(y) > 1e-4)
    v, d, y = v[mask], d[mask], y[mask]
    # Model: y = v * d / (L + K*v^2)  =>  v*d/y = L + K*v^2
    # Linear in (1, v^2) for vd/y as response.
    z = v * d / y
    # Clip to reasonable range to discard outliers
    ok = (z > 0.5) & (z < 20)
    z = z[ok]; vv = v[ok]
    A = np.column_stack([np.ones_like(vv), vv**2])
    coef, *_ = np.linalg.lstsq(A, z, rcond=None)
    L_eff, K = coef
    # Now check RMSE
    L_use, K_use = L_eff, K
    y_pred = v * d / (L_use + K_use * v**2)
    yr_v0  = v * d / L
    rmse_us = float(np.sqrt(np.mean((y_pred - y)**2)))
    rmse_v0 = float(np.sqrt(np.mean((yr_v0 - y)**2)))
    # Also try gain only (no understeer)
    g = float(np.sum(yr_v0 * y) / np.sum(yr_v0**2))
    yr_g = g * yr_v0
    rmse_g = float(np.sqrt(np.mean((yr_g - y)**2)))
    print(f"{platform}: n={len(z)}  L={L:.3f}  L_eff={L_eff:.3f}  K={K:.5f}")
    print(f"   yr=v*d/L:       rmse={rmse_v0:.5f}")
    print(f"   yr=v*d/L * g:   g={g:.4f}  rmse={rmse_g:.5f}")
    print(f"   understeer fit: rmse={rmse_us:.5f}")
    return {"L_eff": float(L_eff), "K_u": float(K), "gain": g}


if __name__ == "__main__":
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]:
        out[plat] = fit_understeer(plat)
    import json
    Path(ROOT / "out" / "fit_coeffs.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
