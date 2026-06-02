"""V2 model — calibrated correction on top of V0 (yaw_rate_pred_rads).

Structure (per platform):
    yr_ss = g * yr_v0 / (1 + K_us * v_mps**2)   - steady-state corrected
    yr_lag = first-order-lag(yr_ss, tau)
    Then yr = yr_lag with a per-segment delta0 bias removed in the V0 input.

For platforms where V0 already encodes wheelbase L correctly, the dominant
remaining error is:
- Steering ratio mismatch (gain g)
- Understeer (K_us)
- Lag (tau)
- Steering offset (delta0)

Fit with scipy.optimize.minimize, bounded.
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

TRUTH_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": "yaw_rate_meas_rads",
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5": "yaw_rate_meas_rads",
}


def load_segments(platform):
    truth_col = TRUTH_BY_PLATFORM[platform]
    plat_dir = SIM_ROOT / platform
    rows = []
    for p in sorted(plat_dir.rglob("sim.csv")):
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
    if mask.sum() < 50:
        return fallback
    return float(np.median(seg["delta_road"][mask]))


def v2_predict(seg, g, K_us, tau, delta0_use_per_seg, delta0_fallback, alpha_steer_rate=0.0):
    """V2 = scale V0 by g/(1+K_us v^2), optional steering-rate feedforward, lag."""
    yr_v0 = seg["yr_v0"]
    v = seg["v"]
    # Recompute V0 with a delta0 correction. yr_v0 ~ v * tan(delta_road)/L.
    # We can re-derive yr_v0_corrected = v * tan(delta_road - delta0)/L = yr_v0_with_offset
    # But the cleanest approach is to compute yr_ss from delta directly using V0 as ref:
    if delta0_use_per_seg:
        delta0 = per_seg_delta0(seg, delta0_fallback)
    else:
        delta0 = delta0_fallback
    # Apply delta0 by scaling: subtract the bias contribution from yr_v0
    # yr_v0 = v*tan(delta_road)/L ≈ v*delta_road/L (small angle).
    # yr_v0_corr ≈ yr_v0 - v*delta0/L_proxy. But L is hidden. Compute from yr_v0/delta_road:
    delta_road = seg["delta_road"]
    # Avoid division by tiny delta; use linear small-angle approximation
    # yr_v0_corr = yr_v0 * (delta_road - delta0) / max(delta_road, eps)? unstable.
    # Better: re-derive using delta_road and v with a hidden L_eff that we set = v / yr_v0 * delta_road for samples
    # Simpler: just subtract per-segment median of (yr_v0 in straight bins) — that IS the delta0 effect
    yr_v0_bias = 0.0
    mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
    if mask.sum() >= 50:
        yr_v0_bias = float(np.median(yr_v0[mask]))
    yr_v0_corr = yr_v0 - yr_v0_bias

    yr_ss = g * yr_v0_corr / (1.0 + K_us * v * v)

    # Steering-rate feedforward: optional small term proportional to d(delta)/dt
    if alpha_steer_rate != 0.0:
        dt_arr = np.diff(seg["t"], prepend=seg["t"][0])
        ddelta = np.gradient(delta_road, seg["t"])
        yr_ss = yr_ss + alpha_steer_rate * ddelta

    t = seg["t"]
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def loss_yr(params, segs, per_seg_delta0_flag, with_steer_rate):
    if with_steer_rate:
        g, K_us, tau, d0_fb, alpha_sr = params
    else:
        g, K_us, tau, d0_fb = params
        alpha_sr = 0.0
    if tau < 1e-3 or g <= 0.0 or g > 5.0 or K_us < -0.05 or K_us > 0.1:
        return 1e9
    s = 0.0; n = 0
    for seg in segs:
        yr = v2_predict(seg, g, K_us, tau, per_seg_delta0_flag, d0_fb, alpha_sr)
        d = yr - seg["yr_truth"]
        s += float((d*d).sum()); n += len(d)
    return s / max(n, 1)


def fit_platform(platform, per_seg_delta0_default, init_params, with_steer_rate=False, max_segs=None):
    segs = load_segments(platform)
    if max_segs:
        segs = segs[:max_segs]
    rng = np.random.default_rng(0)
    idx = np.arange(len(segs))
    rng.shuffle(idx)
    split = int(0.8 * len(segs))
    train = [segs[i] for i in idx[:split]]
    dev = [segs[i] for i in idx[split:]]

    def f(p): return loss_yr(p, train, per_seg_delta0_default, with_steer_rate)
    res = minimize(f, init_params, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-10, "maxiter": 800})
    p_opt = res.x

    yr_sq = 0.0; yr_n = 0
    cte_sq = 0.0; cte_n = 0
    if with_steer_rate:
        g_, K_, tau_, d0_, alpha_sr = p_opt
    else:
        g_, K_, tau_, d0_ = p_opt; alpha_sr = 0.0
    for seg in dev:
        yr = v2_predict(seg, g_, K_, tau_, per_seg_delta0_default, d0_, alpha_sr)
        d = yr - seg["yr_truth"]
        yr_sq += float((d*d).sum()); yr_n += len(d)
        s2, nb, _ = cte_rmse_segment(seg["t"], seg["v"], seg["yr_truth"], yr)
        cte_sq += s2; cte_n += nb
    yr_rmse = math.sqrt(yr_sq/yr_n) if yr_n else float("nan")
    cte_rmse = math.sqrt(cte_sq/cte_n) if cte_n else float("nan")
    return {
        "platform": platform,
        "g": float(g_), "K_us": float(K_), "tau": float(tau_),
        "delta0_fallback": float(d0_), "alpha_steer_rate": float(alpha_sr),
        "use_per_segment_delta0": per_seg_delta0_default,
        "with_steer_rate": with_steer_rate,
        "dev_yr_rmse": yr_rmse, "dev_cte_rmse": cte_rmse,
        "n_train": len(train), "n_dev": len(dev),
    }


if __name__ == "__main__":
    out = {}
    # init from V1 known coefficients (g, K_us, tau, delta0_fb [, alpha_steer_rate])
    configs = {
        "FORD_MUSTANG_MACH_E_MK1": dict(init=(0.95, 0.0015, 0.07, -0.0001), per_seg=True, with_sr=True, init_sr=0.0),
        "FORD_F_150_LIGHTNING_MK1": dict(init=(0.95, 0.0035, 0.06, 0.0013), per_seg=True, with_sr=True, init_sr=0.0),
        "HYUNDAI_IONIQ_5": dict(init=(0.95, 0.0029, 0.062, 0.0), per_seg=True, with_sr=True, init_sr=0.0),
    }
    for plat, cfg in configs.items():
        init = cfg["init"]
        if cfg["with_sr"]:
            init = init + (cfg["init_sr"],)
        print(f"Fitting {plat}, with_steer_rate={cfg['with_sr']}, per_seg_delta0={cfg['per_seg']}...")
        r = fit_platform(plat, cfg["per_seg"], init, with_steer_rate=cfg["with_sr"])
        print(json.dumps(r, indent=2, default=float))
        out[plat] = r
    (ROOT / "out" / "v2_coeffs.json").write_text(json.dumps(out, indent=2, default=float))
    print("Saved v2_coeffs.json")
