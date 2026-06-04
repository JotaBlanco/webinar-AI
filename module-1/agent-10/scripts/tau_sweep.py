"""Finer tau sweep + try a steering low-pass pre-filter."""
import glob, json, os, numpy as np, pandas as pd
ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-10/data/sim/segments"

with open("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-10/out/coeffs.json") as f:
    COEFFS = json.load(f)


def load_all(plat):
    files = sorted(glob.glob(os.path.join(ROOT, plat, "**", "sim.csv"), recursive=True))
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, usecols=lambda c: c in {
                "t_s","delta_road_rad","v_mps","yaw_rate_meas_rads"})
            if "yaw_rate_meas_rads" not in df.columns: continue
            dfs.append(df)
        except Exception: continue
    return dfs


def eval_with(dfs, L, K, d0, tau, tau_steer=0.0):
    sse, n = 0.0, 0
    for df in dfs:
        t = df["t_s"].values
        v = df["v_mps"].values
        d = df["delta_road_rad"].values - d0
        if tau_steer > 0:
            ds = np.zeros_like(d); ds[0] = d[0]
            for i in range(1, len(d)):
                dt = t[i]-t[i-1]
                if dt <= 0: ds[i] = d[i]; continue
                a = dt / (tau_steer + dt)
                ds[i] = ds[i-1] + a*(d[i]-ds[i-1])
            d = ds
        denom = L + K * v * v
        denom = np.where(np.abs(denom) < 1e-6, 1e-6, denom)
        yaw_ss = v * d / denom
        if tau > 0:
            yp = np.zeros_like(yaw_ss); yp[0] = yaw_ss[0]
            for i in range(1, len(yaw_ss)):
                dt = t[i]-t[i-1]
                if dt <= 0: yp[i] = yaw_ss[i]; continue
                a = dt / (tau + dt)
                yp[i] = yp[i-1] + a*(yaw_ss[i] - yp[i-1])
        else:
            yp = yaw_ss
        y = df["yaw_rate_meas_rads"].values
        m = np.isfinite(yp) & np.isfinite(y)
        e = yp[m] - y[m]
        sse += np.sum(e*e); n += int(m.sum())
    return float(np.sqrt(sse / max(n,1)))


for plat in ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5"]:
    p = COEFFS[plat]
    L, K, d0 = p["L_eff_3p"], p["K_us_3p"], p["d0_3p"]
    dfs = load_all(plat)
    print(f"\n{plat}")
    best = (1e9, 0, 0)
    for tau in [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20]:
        for ts in [0.0, 0.02, 0.05, 0.10]:
            r = eval_with(dfs, L, K, d0, tau, ts)
            if r < best[0]:
                best = (r, tau, ts)
            # print(f" tau={tau:.2f} ts={ts:.2f} -> {r:.5f}")
    print(f"  best: tau={best[1]:.3f} ts={best[2]:.3f} RMSE={best[0]:.5f}")
    COEFFS[plat]["tau_final"] = best[1]
    COEFFS[plat]["tau_steer"] = best[2]
    COEFFS[plat]["rmse_final"] = best[0]


with open("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-10/out/coeffs.json", "w") as f:
    json.dump(COEFFS, f, indent=2)
print("\nUpdated coeffs.json")
