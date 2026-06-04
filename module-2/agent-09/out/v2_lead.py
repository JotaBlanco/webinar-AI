"""V2: V1 + steering-rate lead term: yaw = v * (delta + tau * d(delta)/dt) / (L + Kus * v^2).

Also adds a small bias term to handle systematic drift.
Fits per-platform (L, Kus, tau, bias).
"""
import sys, json, os
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from score import score, format_summary
from scipy.optimize import minimize


def predict_v2_factory(coeffs_dict):
    def predict(sim_df, platform):
        out = sim_df[["yaw_rate_pred_rads"]].copy()
        if platform == "TESLA_MODEL_3":
            return out
        c = coeffs_dict.get(platform)
        if c is None:
            return out
        L = c["L"]
        Kus = c["Kus"]
        tau = c.get("tau", 0.0)
        bias = c.get("bias", 0.0)
        delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
        v = sim_df["v_mps"].to_numpy(dtype=float)
        t = sim_df["t_s"].to_numpy(dtype=float)
        if len(t) >= 2:
            ddelta = np.gradient(delta, t)
        else:
            ddelta = np.zeros_like(delta)
        eff_delta = delta + tau * ddelta
        denom = L + Kus * v * v
        yr = v * eff_delta / denom + bias
        out["yaw_rate_pred_rads"] = yr
        return out
    return predict


def fit_platform_v2(platform, init):
    """Fit (L, Kus, tau, bias) per-segment-pooled."""
    seg_root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(seg_root.glob("*/**/sim.csv"))
    # Build pooled lists with per-segment derivatives.
    Vs, Ds, dDs, Ys = [], [], [], []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["t_s", "v_mps", "delta_road_rad", "yaw_rate_meas_rads"])
        except Exception:
            continue
        if len(df) < 5:
            continue
        t = df["t_s"].to_numpy(dtype=float)
        d = df["delta_road_rad"].to_numpy(dtype=float)
        v = df["v_mps"].to_numpy(dtype=float)
        y = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        ddelta = np.gradient(d, t)
        m = v > 2.0
        Vs.append(v[m]); Ds.append(d[m]); dDs.append(ddelta[m]); Ys.append(y[m])
    v = np.concatenate(Vs); d = np.concatenate(Ds); dd = np.concatenate(dDs); y = np.concatenate(Ys)

    def obj(params):
        L, Kus, tau, bias = params
        if L < 1.5 or L > 6.0:
            return 1e6
        denom = L + Kus * v * v
        if np.any(denom <= 0.1):
            return 1e6
        pred = v * (d + tau * dd) / denom + bias
        return float(np.mean((pred - y) ** 2))

    best = None
    starts = [
        (init["L"], init["Kus"], 0.0, 0.0),
        (init["L"], init["Kus"], 0.05, 0.0),
        (init["L"], init["Kus"], -0.05, 0.0),
        (init["L"], init["Kus"], 0.1, 0.0),
        (init["L"], init["Kus"], 0.0, -0.001),
    ]
    for x0 in starts:
        r = minimize(obj, x0=list(x0), method="Nelder-Mead",
                     options={"xatol": 1e-5, "fatol": 1e-10, "maxiter": 2000})
        if best is None or r.fun < best.fun:
            best = r
    L, Kus, tau, bias = best.x
    print(f"  {platform}: L={L:.4f}, Kus={Kus:.5f}, tau={tau:.4f}, bias={bias:.5f}, MSE={best.fun:.6e}")
    return {"L": float(L), "Kus": float(Kus), "tau": float(tau), "bias": float(bias)}


if __name__ == "__main__":
    v1 = json.loads((ROOT / "out" / "v1_coeffs.json").read_text())
    coeffs = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        coeffs[plat] = fit_platform_v2(plat, v1[plat])
    (ROOT / "out" / "v2_coeffs.json").write_text(json.dumps(coeffs, indent=2))

    print("\n--- V2 score ---")
    result = score(predict_v2_factory(coeffs))
    print(format_summary(result))
    print("\nV2: yaw=%f, cte=%f" % (result["yaw_rate_rmse"], result["cte_rmse"]))
