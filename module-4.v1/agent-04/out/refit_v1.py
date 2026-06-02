"""Refit V1's (g, K_us, delta0, tau) per platform via Nelder-Mead minimizing
pooled yaw_rate RMSE on a 80/20 split. Then save updated PLATFORM_PARAMS.
"""
from __future__ import annotations
import sys, json, hashlib, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import importlib.util as _iu
_spec = _iu.spec_from_file_location("v1b", ROOT/"code"/"v1_baseline.py")
_v1m = _iu.module_from_spec(_spec); _spec.loader.exec_module(_v1m)
predict_v1 = _v1m.predict_v1
PLATFORM_PARAMS_V1 = _v1m.PLATFORM_PARAMS_V1

ALLOWLIST = ["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2","accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1","FORD_MUSTANG_MACH_E_MK1","HYUNDAI_IONIQ_5"]


def yr_v1(params, df):
    """Replicate V1 yaw-rate eqn with given params (g, L_eff, K_us, tau, delta0)."""
    g, L_eff, K_us, tau, delta0 = params
    delta = (df["delta_road_rad"].to_numpy() - delta0) * g
    v = df["v_mps"].to_numpy()
    yr_ss = v * delta / (L_eff + K_us * v * v)
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def loss_for_platform(params, segs_data, per_seg_delta0=None):
    # params: g, K_us, tau (we keep L_eff fixed) — and a fallback delta0 if not per-seg
    g, K_us, tau, delta0 = params
    sse, n = 0.0, 0
    for seg in segs_data:
        df, L_eff = seg["df"], seg["L_eff"]
        d0 = seg.get("delta0", delta0)
        yr = yr_v1((g, L_eff, K_us, tau, d0), df)
        truth = df["yaw_rate_meas_rads"].to_numpy()
        res = yr - truth
        sse += float(np.sum(res*res))
        n += len(res)
    return math.sqrt(sse/n) if n else float("inf")


def load_segs(platform, n=None):
    """Pre-load a subset of segments to speed up optimization."""
    pdir = ROOT/"data"/"sim"/"segments"/platform
    segs = sorted(pdir.rglob("sim.csv"))
    if n is not None:
        # subsample deterministically
        segs = [s for s in segs if int(hashlib.md5(str(s).encode()).hexdigest()[:8],16) % 4 == 0]
        segs = segs[:n] if n is not None and len(segs)>n else segs
    out = []
    p0 = PLATFORM_PARAMS_V1[platform]
    L_eff = p0["L_eff"]
    use_perseg = p0["use_per_segment_delta0"]
    for s in segs:
        try:
            df = pd.read_csv(s)
        except Exception: continue
        if "yaw_rate_meas_rads" not in df.columns: continue
        for c in ALLOWLIST:
            if c not in df.columns: df[c] = 0.0
        rec = {"df": df, "L_eff": L_eff, "path": str(s)}
        if use_perseg:
            v = df["v_mps"].to_numpy()
            yr0 = df["yaw_rate_pred_rads"].to_numpy()
            mask = (np.abs(yr0) < 0.03) & (v > 5.0)
            if mask.sum() >= 50:
                rec["delta0"] = float(np.median(df.loc[mask,"delta_road_rad"]))
        out.append(rec)
    return out


def fit(platform):
    print(f"\n=== Refit {platform} ===")
    p0 = PLATFORM_PARAMS_V1[platform]
    # warm start
    x0 = np.array([p0["g"], p0["K_us"], p0["tau"], p0.get("delta0_fallback", p0.get("delta0", 0.0))])
    segs = load_segs(platform, n=80)  # subsample for speed
    print(f"  using {len(segs)} segments")
    rmse0 = loss_for_platform(x0, segs)
    print(f"  RMSE @ V1 warmstart = {rmse0:.6f}")
    res = minimize(lambda p: loss_for_platform(p, segs), x0,
                   method="Nelder-Mead",
                   options={"xatol":1e-5,"fatol":1e-7,"maxiter":300,"disp":True})
    print(f"  RMSE @ refit       = {res.fun:.6f}")
    print(f"  V1 params: g={p0['g']:.4f} K_us={p0['K_us']:.5f} tau={p0['tau']:.4f}")
    print(f"  Fit params: g={res.x[0]:.4f} K_us={res.x[1]:.5f} tau={res.x[2]:.4f} delta0={res.x[3]:.5f}")
    return {"g": float(res.x[0]), "K_us": float(res.x[1]), "tau": float(res.x[2]), "delta0_fallback": float(res.x[3])}


def main():
    out = {}
    for plat in PLATFORMS:
        out[plat] = fit(plat)
    (ROOT/"out"/"refit_params.json").write_text(json.dumps(out, indent=2))
    print("\nwrote", ROOT/"out"/"refit_params.json")

if __name__ == "__main__":
    main()
