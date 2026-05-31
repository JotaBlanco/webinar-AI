"""Fit understeer-gradient bicycle model per platform.

Model: yaw_ss = v * delta / (L_eff + K_us * v^2)

Linear regression form:  v * delta = L_eff * yaw + K_us * (yaw * v^2)
features = [yaw, yaw*v^2], target = v*delta.

Also try with steering offset:
   v * (delta - d0) = L_eff * yaw + K_us * yaw * v^2
features = [yaw, yaw*v^2, -v], target = v*delta.

Optional: low-pass time constant tau on yaw (first-order lag).
"""
import glob
import json
import os
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-10/data/sim/segments"
OUT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-10/out"

PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]


def load_all(plat, max_segs=None):
    files = sorted(glob.glob(os.path.join(ROOT, plat, "**", "sim.csv"), recursive=True))
    if max_segs:
        files = files[:max_segs]
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, usecols=lambda c: c in {
                "t_s","delta_road_rad","v_mps","a_long_mps2",
                "yaw_rate_meas_rads","yaw_rate_pred_rads"
            })
            if "yaw_rate_meas_rads" not in df.columns:
                continue
            dfs.append(df)
        except Exception:
            continue
    return dfs


def fit_understeer(dfs, v_min=3.0):
    yaw_list, vdelta_list, v_list = [], [], []
    for df in dfs:
        v = df["v_mps"].values
        d = df["delta_road_rad"].values
        y = df["yaw_rate_meas_rads"].values
        m = (v >= v_min) & np.isfinite(v) & np.isfinite(d) & np.isfinite(y)
        yaw_list.append(y[m])
        vdelta_list.append((v * d)[m])
        v_list.append(v[m])
    yaw = np.concatenate(yaw_list)
    vd = np.concatenate(vdelta_list)
    v = np.concatenate(v_list)

    # Two-param fit: target = L*yaw + K*yaw*v^2
    A = np.column_stack([yaw, yaw * v * v])
    b = vd
    coef, *_ = np.linalg.lstsq(A, b, rcond=None)
    L_eff, K_us = coef
    pred = A @ coef
    resid = b - pred
    print(f"   2-param: L_eff={L_eff:.4f}  K_us={K_us:.6f}  rss={np.sum(resid**2):.1f}")

    # Three-param fit: include steering offset d0 (v*delta - v*d0 = L*yaw + K*yaw*v^2)
    # => v*delta = L*yaw + K*yaw*v^2 + v*d0
    A3 = np.column_stack([yaw, yaw * v * v, v])
    coef3, *_ = np.linalg.lstsq(A3, b, rcond=None)
    L3, K3, d0 = coef3
    pred3 = A3 @ coef3
    resid3 = b - pred3
    print(f"   3-param: L_eff={L3:.4f}  K_us={K3:.6f}  d0={d0:.6f}  rss={np.sum(resid3**2):.1f}")

    return {"L_eff": float(L_eff), "K_us": float(K_us),
            "L_eff_3p": float(L3), "K_us_3p": float(K3), "d0_3p": float(d0)}


def eval_model(dfs, params, model="ss", tau=0.0, use_3p=False):
    """Evaluate yaw-rate RMSE on dfs."""
    sse, n = 0.0, 0
    L = params["L_eff_3p"] if use_3p else params["L_eff"]
    K = params["K_us_3p"] if use_3p else params["K_us"]
    d0 = params.get("d0_3p", 0.0) if use_3p else 0.0
    for df in dfs:
        v = df["v_mps"].values
        d = df["delta_road_rad"].values - d0
        y = df["yaw_rate_meas_rads"].values
        # Compute steady-state yaw
        denom = L + K * v * v
        denom = np.where(np.abs(denom) < 1e-6, 1e-6, denom)
        yaw_ss = v * d / denom
        if tau > 0:
            # First-order lag with sample spacing dt
            t = df["t_s"].values
            yaw_pred = np.zeros_like(yaw_ss)
            yaw_pred[0] = yaw_ss[0]
            for i in range(1, len(yaw_ss)):
                dt = t[i] - t[i-1]
                if dt <= 0 or not np.isfinite(dt):
                    yaw_pred[i] = yaw_ss[i]
                    continue
                a = dt / (tau + dt)
                yaw_pred[i] = yaw_pred[i-1] + a * (yaw_ss[i] - yaw_pred[i-1])
        else:
            yaw_pred = yaw_ss
        m = np.isfinite(yaw_pred) & np.isfinite(y)
        e = (yaw_pred[m] - y[m])
        sse += np.sum(e * e)
        n += int(m.sum())
    return float(np.sqrt(sse / max(n, 1)))


def baseline_rmse(dfs):
    sse, n = 0.0, 0
    for df in dfs:
        y = df["yaw_rate_meas_rads"].values
        p = df["yaw_rate_pred_rads"].values
        m = np.isfinite(y) & np.isfinite(p)
        e = p[m] - y[m]
        sse += np.sum(e * e); n += int(m.sum())
    return float(np.sqrt(sse / max(n, 1)))


def main():
    coeffs = {}
    for plat in PLATFORMS:
        print(f"\n==> {plat}")
        dfs = load_all(plat)
        if not dfs:
            print("   no truth segments — skip")
            continue
        v0 = baseline_rmse(dfs)
        print(f"   V0 RMSE = {v0:.5f} rad/s")
        p = fit_understeer(dfs)

        # eval 2-param
        r2 = eval_model(dfs, p, use_3p=False, tau=0.0)
        print(f"   SS (2p)        RMSE = {r2:.5f}")
        r3 = eval_model(dfs, p, use_3p=True, tau=0.0)
        print(f"   SS (3p +d0)    RMSE = {r3:.5f}")

        # Sweep tau
        best = (r3, 0.0, True)
        for tau in [0.05, 0.1, 0.15, 0.2, 0.3, 0.5]:
            rt = eval_model(dfs, p, use_3p=True, tau=tau)
            if rt < best[0]:
                best = (rt, tau, True)
        print(f"   best tau={best[1]:.3f} RMSE={best[0]:.5f}")

        coeffs[plat] = {**p, "tau_best": best[1], "rmse_best": best[0],
                        "v0_rmse": v0}

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "coeffs.json"), "w") as f:
        json.dump(coeffs, f, indent=2)
    print("\nWrote", os.path.join(OUT, "coeffs.json"))


if __name__ == "__main__":
    main()
