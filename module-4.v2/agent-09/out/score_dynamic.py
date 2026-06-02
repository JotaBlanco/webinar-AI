"""Try a first-order-lag dynamic single-track on top of the understeer model.

   yr_ss[k]  = v*delta*scale / (L + K_us*v^2)
   yr[k+1]   = yr[k] + dt * (yr_ss[k] - yr[k]) / tau

Fit (K_us, scale, tau) per platform.
"""
from __future__ import annotations
import sys, math, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-09")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_rmse_segment

SIM_ROOT = ROOT / "data" / "sim" / "segments"
L_BY_PLATFORM = {
    "TESLA_MODEL_3":              2.875,
    "FORD_MUSTANG_MACH_E_MK1":    2.984,
    "FORD_F_150_LIGHTNING_MK1":   3.70,
    "HYUNDAI_IONIQ_5":            3.00,
}


def load_segment(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "yaw_rate_meas_rads" not in df.columns and "psi_dot_rads" in df.columns:
        df["yaw_rate_meas_rads"] = df["psi_dot_rads"]
    if "yaw_rate_pred_rads" not in df.columns:
        v = df["v_mps"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        df["yaw_rate_pred_rads"] = v * d / 2.875
    return df


def collect(platform):
    chunks = []
    for p in sorted((SIM_ROOT / platform).rglob("sim.csv")):
        df = load_segment(p)
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        yr = df["yaw_rate_meas_rads"].to_numpy()
        mask = np.isfinite(t) & np.isfinite(v) & np.isfinite(d) & np.isfinite(yr)
        if mask.sum() < 50:
            continue
        chunks.append((t[mask], v[mask], d[mask], yr[mask]))
    return chunks


def predict_dyn(t, v, d, K_us, scale, tau, L):
    yr_ss = v * d * scale / (L + K_us * v * v)
    if tau <= 1e-3:
        return yr_ss
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    dt = np.diff(t)
    for i in range(len(t) - 1):
        yr[i+1] = yr[i] + dt[i] * (yr_ss[i] - yr[i]) / tau
    return yr


def fit_platform(platform):
    chunks = collect(platform)
    L = L_BY_PLATFORM[platform]

    def loss(x):
        K_us, scale, tau = x
        if tau < 0: tau = 0
        sse, n = 0.0, 0
        for t, v, d, yr in chunks:
            yp = predict_dyn(t, v, d, K_us, scale, tau, L)
            e = yr - yp
            sse += float(np.sum(e * e))
            n += len(e)
        return math.sqrt(sse / n)

    # Two-stage: static first, then add tau
    res0 = minimize(lambda x: loss([x[0], x[1], 0.0]), [0.001, 1.0],
                    method="Nelder-Mead", options={"xatol":1e-6,"fatol":1e-8,"maxiter":400})
    K0, s0 = res0.x
    res = minimize(loss, [K0, s0, 0.05],
                   method="Nelder-Mead", options={"xatol":1e-6,"fatol":1e-8,"maxiter":600})
    return res.x, res.fun


def score(platform, K_us, scale, tau):
    L = L_BY_PLATFORM[platform]
    yaw_sq = 0.0; yaw_n = 0
    cte_sq = 0.0; cte_n = 0
    for t, v, d, yr in collect(platform):
        yp = predict_dyn(t, v, d, K_us, scale, tau, L)
        e = yr - yp
        yaw_sq += float(np.sum(e * e)); yaw_n += len(e)
        ss, nb, _ = cte_rmse_segment(t, v, yr, yp, grid_step_m=1.0, min_distance_m=20.0)
        cte_sq += ss; cte_n += nb
    return math.sqrt(yaw_sq/yaw_n), math.sqrt(cte_sq/cte_n) if cte_n else float("nan")


def main():
    out = {}
    for plat in ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5"]:
        (K, s, tau), loss = fit_platform(plat)
        y_rmse, c_rmse = score(plat, K, s, tau)
        print(f"{plat}: K_us={K:.5f} scale={s:.4f} tau={tau:.4f}  yaw_rmse={y_rmse:.5f}  cte_rmse={c_rmse:.3f} m")
        out[plat] = {"K_us": K, "scale": s, "tau": tau, "L": L_BY_PLATFORM[plat],
                     "yaw_rmse_rads": y_rmse, "cte_rmse_m": c_rmse}
    (ROOT / "out" / "dynamic_scores.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
