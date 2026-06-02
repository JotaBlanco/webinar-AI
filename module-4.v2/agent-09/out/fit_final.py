"""Joint fit (K_us, scale, delta_offset) per platform, plus first-order lag.

Final model used at predict time:
    delta_eff[k] = (delta_road_rad[k] + delta_offset) * scale
    yr_ss[k]     = v[k] * delta_eff[k] / (L + K_us * v[k]^2)
    yr[k+1]      = yr[k] + dt * (yr_ss[k] - yr[k]) / tau   (tau optional)
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
    return df


def collect(platform):
    chunks = []
    for p in sorted((SIM_ROOT / platform).rglob("sim.csv")):
        df = load_segment(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        yr = df["yaw_rate_meas_rads"].to_numpy()
        m = np.isfinite(t) & np.isfinite(v) & np.isfinite(d) & np.isfinite(yr)
        if m.sum() < 50: continue
        chunks.append((t[m], v[m], d[m], yr[m]))
    return chunks


def predict(t, v, d, K_us, scale, do, tau, L):
    d_eff = (d + do) * scale
    yr_ss = v * d_eff / (L + K_us * v * v)
    if tau <= 1e-4:
        return yr_ss
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    dt = np.diff(t)
    for i in range(len(t) - 1):
        yr[i+1] = yr[i] + dt[i] * (yr_ss[i] - yr[i]) / tau
    return yr


def fit(platform):
    chunks = collect(platform)
    L = L_BY_PLATFORM[platform]

    def loss_static(x):
        K_us, scale, do = x
        sse, n = 0.0, 0
        for t, v, d, yr in chunks:
            yp = predict(t, v, d, K_us, scale, do, 0.0, L)
            e = yr - yp
            sse += float(np.sum(e * e))
            n += len(e)
        return math.sqrt(sse / n)

    def loss_dyn(x):
        K_us, scale, do, tau = x
        if tau < 0: tau = 0
        sse, n = 0.0, 0
        for t, v, d, yr in chunks:
            yp = predict(t, v, d, K_us, scale, do, tau, L)
            e = yr - yp
            sse += float(np.sum(e * e))
            n += len(e)
        return math.sqrt(sse / n)

    res0 = minimize(loss_static, [0.001, 1.0, 0.0], method="Nelder-Mead",
                    options={"xatol":1e-6,"fatol":1e-8,"maxiter":1200})
    K, s, do = res0.x
    res = minimize(loss_dyn, [K, s, do, 0.05], method="Nelder-Mead",
                   options={"xatol":1e-6,"fatol":1e-8,"maxiter":1500})
    return res.x, res.fun


def score(platform, K_us, scale, do, tau):
    L = L_BY_PLATFORM[platform]
    yaw_sq = 0.0; yaw_n = 0
    cte_sq = 0.0; cte_n = 0
    for t, v, d, yr in collect(platform):
        yp = predict(t, v, d, K_us, scale, do, tau, L)
        e = yr - yp
        yaw_sq += float(np.sum(e * e)); yaw_n += len(e)
        ss, nb, _ = cte_rmse_segment(t, v, yr, yp, grid_step_m=1.0, min_distance_m=20.0)
        cte_sq += ss; cte_n += nb
    return math.sqrt(yaw_sq/yaw_n), (math.sqrt(cte_sq/cte_n) if cte_n else float("nan"))


def main():
    out = {}
    for plat in L_BY_PLATFORM:
        if plat == "TESLA_MODEL_3":
            # Tesla truth is the KS simulator state — V0 is optimal.
            # We still need a model. Use K=0,scale=1,do=0,tau=0, L=2.875.
            (K, s, do, tau) = (0.0, 1.0, 0.0, 0.0)
            y, c = score(plat, K, s, do, tau)
            print(f"{plat} (V0 passthrough): yaw={y:.5f} cte={c:.3f}")
        else:
            (K, s, do, tau), loss = fit(plat)
            y, c = score(plat, K, s, do, tau)
            print(f"{plat}: K_us={K:.5f} scale={s:.4f} do={do*1000:.3f}mrad tau={tau:.4f}  yaw={y:.5f} cte={c:.3f}")
        out[plat] = {"K_us": float(K), "scale": float(s),
                     "delta_offset_rad": float(do), "tau_s": float(tau),
                     "L": L_BY_PLATFORM[plat],
                     "yaw_rmse_rads": y, "cte_rmse_m": c}
    (ROOT / "out" / "final_coeffs.json").write_text(json.dumps(out, indent=2))
    print("\nWrote out/final_coeffs.json")


if __name__ == "__main__":
    main()
