"""V3: V1's formula with bounded refit + optional steering-rate feedforward.

yr_ss = v * g * (delta_road - delta0) / (L_eff + K_us * v^2) + alpha_sr * d(delta_road)/dt
yr = first-order-lag(yr_ss, tau)

Fit per platform, train/dev split, scipy minimize with bounds.
"""
from __future__ import annotations
import sys, math, json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-08")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_rmse_segment  # type: ignore

SIM_ROOT = ROOT / "data" / "sim" / "segments"
SIMONLY_ROOT = ROOT / "data" / "sim-only" / "segments"

TRUTH = {
    "FORD_MUSTANG_MACH_E_MK1": "yaw_rate_meas_rads",
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5": "yaw_rate_meas_rads",
}


def load_segments(platform):
    truth_col = TRUTH[platform]
    rows = []
    for p in sorted((SIM_ROOT / platform).rglob("sim.csv")):
        try:
            df_full = pd.read_csv(p)
        except Exception:
            continue
        if truth_col not in df_full.columns:
            continue
        rel = p.relative_to(SIM_ROOT)
        so = SIMONLY_ROOT / rel
        if not so.exists():
            continue
        df_so = pd.read_csv(so)
        rows.append({
            "key": str(rel),
            "t": df_so["t_s"].to_numpy(),
            "delta_road": df_so["delta_road_rad"].to_numpy(),
            "v": df_so["v_mps"].to_numpy(),
            "yr_v0": df_so["yaw_rate_pred_rads"].to_numpy(),
            "yr_truth": df_full[truth_col].to_numpy(),
        })
    return rows


def per_seg_delta0(seg, fallback=0.0):
    v = seg["v"]; yr_v0 = seg["yr_v0"]
    mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
    if int(mask.sum()) < 50:
        return fallback
    return float(np.median(seg["delta_road"][mask]))


def predict_seg(seg, g, L_eff, K_us, tau, alpha_sr, use_per_seg_delta0, delta0_fb):
    delta0 = per_seg_delta0(seg, delta0_fb) if use_per_seg_delta0 else delta0_fb
    delta = (seg["delta_road"] - delta0) * g
    v = seg["v"]
    yr_ss = v * delta / (L_eff + K_us * v * v)
    if alpha_sr != 0.0:
        ddelta_dt = np.gradient(seg["delta_road"], seg["t"])
        yr_ss = yr_ss + alpha_sr * ddelta_dt
    t = seg["t"]
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def fit_platform(platform, init, bounds, use_per_seg_delta0, with_sr=True):
    segs = load_segments(platform)
    rng = np.random.default_rng(0)
    idx = np.arange(len(segs)); rng.shuffle(idx)
    split = int(0.8 * len(segs))
    train = [segs[i] for i in idx[:split]]
    dev = [segs[i] for i in idx[split:]]

    def loss(p):
        g, L_eff, K_us, tau, d0_fb, alpha_sr = p if with_sr else (*p, 0.0)
        if L_eff <= 0.3 or tau < 1e-3 or g <= 0:
            return 1e9
        s = 0.0; n = 0
        for seg in train:
            yr = predict_seg(seg, g, L_eff, K_us, tau, alpha_sr, use_per_seg_delta0, d0_fb)
            d = yr - seg["yr_truth"]
            s += float((d*d).sum()); n += len(d)
        return s / max(n, 1)

    p0 = init if with_sr else init[:5]
    bds = bounds if with_sr else bounds[:5]
    res = minimize(loss, p0, method="L-BFGS-B", bounds=bds,
                   options={"maxiter": 200, "ftol": 1e-10})
    p_opt = res.x
    g, L_eff, K_us, tau, d0_fb = p_opt[:5]
    alpha_sr = p_opt[5] if with_sr else 0.0
    # Dev score
    yr_sq = 0.0; yr_n = 0
    cte_sq = 0.0; cte_n = 0
    for seg in dev:
        yr = predict_seg(seg, g, L_eff, K_us, tau, alpha_sr, use_per_seg_delta0, d0_fb)
        d = yr - seg["yr_truth"]
        yr_sq += float((d*d).sum()); yr_n += len(d)
        s2, nb, _ = cte_rmse_segment(seg["t"], seg["v"], seg["yr_truth"], yr)
        cte_sq += s2; cte_n += nb
    return {
        "platform": platform,
        "g": float(g), "L_eff": float(L_eff), "K_us": float(K_us),
        "tau": float(tau), "delta0_fallback": float(d0_fb),
        "alpha_steer_rate": float(alpha_sr),
        "use_per_segment_delta0": use_per_seg_delta0,
        "with_steer_rate": with_sr,
        "dev_yr_rmse": math.sqrt(yr_sq/yr_n) if yr_n else float("nan"),
        "dev_cte_rmse": math.sqrt(cte_sq/cte_n) if cte_n else float("nan"),
        "n_train": len(train), "n_dev": len(dev),
        "loss": float(res.fun),
    }


if __name__ == "__main__":
    out = {}
    # init = (g, L_eff, K_us, tau, delta0_fb, alpha_sr)
    # bounds reflect physical priors
    cfg = {
        "FORD_MUSTANG_MACH_E_MK1": dict(
            init=(0.89, 2.22, 0.0015, 0.069, -0.0001, 0.0),
            bounds=[(0.5, 1.5), (1.0, 5.0), (0.0, 0.01), (0.005, 0.2), (-0.02, 0.02), (-0.5, 0.5)],
            per_seg=True,
        ),
        "FORD_F_150_LIGHTNING_MK1": dict(
            init=(0.86, 3.26, 0.0035, 0.060, 0.00133, 0.0),
            bounds=[(0.5, 1.5), (1.5, 6.0), (0.0, 0.01), (0.005, 0.2), (-0.02, 0.02), (-0.5, 0.5)],
            per_seg=True,
        ),
        "HYUNDAI_IONIQ_5": dict(
            init=(0.94, 2.89, 0.0029, 0.062, 0.0, 0.0),
            bounds=[(0.5, 1.5), (1.5, 5.0), (0.0, 0.01), (0.005, 0.2), (-0.02, 0.02), (-0.5, 0.5)],
            per_seg=True,
        ),
    }
    for plat, c in cfg.items():
        print(f"Fitting {plat}...")
        r = fit_platform(plat, c["init"], c["bounds"], c["per_seg"], with_sr=True)
        print(json.dumps(r, indent=2, default=float))
        out[plat] = r

    # Also try without steer-rate to see effect
    print("\n--- without steer rate ---")
    out_nosr = {}
    for plat, c in cfg.items():
        r = fit_platform(plat, c["init"], c["bounds"], c["per_seg"], with_sr=False)
        out_nosr[plat] = r
        print(f"  {plat}: dev_yr={r['dev_yr_rmse']:.6f}, dev_cte={r['dev_cte_rmse']:.4f}")

    (ROOT / "out" / "v3_coeffs.json").write_text(json.dumps({"with_sr": out, "no_sr": out_nosr}, indent=2, default=float))
    print("Saved v3_coeffs.json")
