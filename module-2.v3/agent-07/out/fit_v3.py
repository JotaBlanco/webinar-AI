"""V3: add cubic-δ understeer and v²·dδ steering-rate lead.

    delta_eff = (delta - d_off) + (tau + tau2 * v^2 / 100) * d_delta_dt - cub * delta^3
    yaw_pred  = gain * v * delta_eff / (1 + K_us * v^2)
"""
from __future__ import annotations
import sys, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-07")

L_NOMINAL = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "HYUNDAI_IONIQ_5":          3.0,
    "TESLA_MODEL_3":            2.875,
}


def load_platform(platform: str):
    seg_root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    truth_col = "psi_dot_rads" if platform == "TESLA_MODEL_3" else "yaw_rate_meas_rads"
    rows_d, rows_v, rows_dd, rows_y = [], [], [], []
    for p in paths:
        df = pd.read_csv(p)
        if truth_col not in df.columns or len(df) < 10:
            continue
        t = df["t_s"].to_numpy(float)
        if np.any(np.diff(t) <= 0):
            continue
        d = df["delta_road_rad"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        y = df[truth_col].to_numpy(float)
        dd = np.gradient(d, t)
        mask = v > 2.0
        rows_d.append(d[mask]); rows_v.append(v[mask])
        rows_dd.append(dd[mask]); rows_y.append(y[mask])
    if not rows_d: return None
    return {"d": np.concatenate(rows_d), "v": np.concatenate(rows_v),
            "dd": np.concatenate(rows_dd), "y": np.concatenate(rows_y)}


def predict_model(d, v, dd, gain, K_us, tau, tau2, d_off, cub):
    tau_eff = tau + tau2 * (v * v) / 100.0
    delta_eff = (d - d_off) + tau_eff * dd - cub * (d ** 3)
    return gain * v * delta_eff / (1.0 + K_us * v * v)


def fit_platform(platform, data, L_nom):
    d, v, dd, y = data["d"], data["v"], data["dd"], data["y"]
    n = len(d)
    if n > 250_000:
        rng = np.random.default_rng(42)
        idx = rng.choice(n, 250_000, replace=False)
        d, v, dd, y = d[idx], v[idx], dd[idx], y[idx]

    x0 = np.array([1.0 / L_nom, 0.0, 0.0, 0.0, 0.0, 0.0])

    def loss(x):
        gain, K_us, tau, tau2, d_off, cub = x
        yp = predict_model(d, v, dd, gain, K_us, tau, tau2, d_off, cub)
        return float(np.mean((yp - y) ** 2))

    bounds = [
        (0.5 / L_nom, 2.0 / L_nom),  # gain
        (-0.01, 0.05),                # K_us
        (-0.3, 0.5),                  # tau
        (-0.3, 0.3),                  # tau2 (v² scaling for steering lead)
        (-0.01, 0.01),                # delta_off
        (-2.0, 2.0),                  # cubic δ coefficient
    ]
    r = minimize(loss, x0, method="L-BFGS-B", bounds=bounds,
                 options={"maxiter": 500, "ftol": 1e-12})
    gain, K_us, tau, tau2, d_off, cub = r.x
    return {
        "gain": float(gain), "K_us": float(K_us),
        "tau": float(tau), "tau2": float(tau2),
        "delta_off": float(d_off), "cub": float(cub),
        "L_nominal": float(L_nom),
        "rmse_train": math.sqrt(r.fun),
        "n_train": int(len(d)), "converged": bool(r.success),
    }


def main():
    coeffs = {}
    for plat, L_nom in L_NOMINAL.items():
        if plat == "TESLA_MODEL_3":
            coeffs[plat] = {"gain": 1.0/L_nom, "K_us":0,"tau":0,"tau2":0,
                            "delta_off":0,"cub":0,"L_nominal":L_nom,"passthrough":True}
            continue
        print(f"\n== {plat} ==", flush=True)
        data = load_platform(plat)
        print(f"  loaded {len(data['d']):,} samples")
        c = fit_platform(plat, data, L_nom)
        print(f"  coeffs: gain={c['gain']:.4f} K_us={c['K_us']:.5f} tau={c['tau']:.4f} "
              f"tau2={c['tau2']:.4f} d_off={c['delta_off']:+.5f} cub={c['cub']:.4f} "
              f"rmse_train={c['rmse_train']:.5f}")
        coeffs[plat] = c
    out = ROOT / "out" / "coeffs_v3.json"
    out.write_text(json.dumps(coeffs, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
