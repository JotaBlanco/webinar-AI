"""Fast per-platform fit.

Two-stage strategy:
  Stage A: yaw-only fit using stacked numpy arrays (very fast).
           - δ₀ per-segment (input-derived median) computed once up front.
           - Fit (g, L_eff, K_us, tau) by Nelder-Mead, single start (good init).
  Stage B: short CTE refinement on (g, tau) only (CTE is dominated by these).
           - Skipped if it makes things worse; legal weighted-objective phase.

We use per-segment δ₀ for all 3 platforms (legal: based on input columns only).
"""
from __future__ import annotations
import sys, math, json, time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "out"))
from _shared.traj_metrics import cte_rmse_segment
from harness import find_sim_csvs, load_segment, SIM_ROOT

WHEELBASE_PRIOR = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.708,
    "HYUNDAI_IONIQ_5": 3.000,
}


def _per_seg_delta0(delta, v, fallback=0.0, delta_thresh=0.01, v_thresh=5.0, min_rows=50):
    mask = (np.abs(delta) < delta_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(delta[mask]))


def collect(platform):
    csvs = find_sim_csvs(SIM_ROOT, platform)
    out = []
    for csv in csvs:
        df = load_segment(csv)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        d0 = _per_seg_delta0(delta, v)
        out.append({"t": t, "v": v, "delta": delta, "yr": yr_truth, "d0": d0})
    return out


def predict_yr(seg, g, L_eff, K_us, tau):
    delta = (seg["delta"] - seg["d0"]) * g
    v = seg["v"]
    yr_ss = v * delta / (L_eff + K_us * v * v)
    t = seg["t"]
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def yaw_only_loss(segs, g, L_eff, K_us, tau):
    ss = 0.0
    n = 0
    for seg in segs:
        yr = predict_yr(seg, g, L_eff, K_us, tau)
        err = yr - seg["yr"]
        ss += float((err * err).sum())
        n += len(err)
    return math.sqrt(ss / n)


def both_loss(segs, g, L_eff, K_us, tau):
    ss_y = 0.0
    ny = 0
    ss_c = 0.0
    nc = 0
    for seg in segs:
        yr = predict_yr(seg, g, L_eff, K_us, tau)
        err = yr - seg["yr"]
        ss_y += float((err * err).sum())
        ny += len(err)
        ssc, nb, _ = cte_rmse_segment(seg["t"], seg["v"], seg["yr"], yr)
        ss_c += ssc
        nc += nb
    return (math.sqrt(ss_y / ny) if ny else float("nan"),
            math.sqrt(ss_c / nc) if nc else float("nan"))


def fit_one(platform):
    print(f"\n[{platform}] loading...", flush=True)
    t0 = time.time()
    segs = collect(platform)
    print(f"  {len(segs)} segments in {time.time()-t0:.1f}s", flush=True)
    L_prior = WHEELBASE_PRIOR[platform]

    # Baseline (V0-mimic) for reporting
    y0, c0 = both_loss(segs, 1.0, L_prior, 0.0, 1e-3)
    print(f"  V0-mimic: yaw={y0:.5f} cte={c0:.3f}", flush=True)

    # Stage A: yaw-only NM, single start
    def yaw_obj(x):
        g, L_eff, K_us, tau = x
        if g < 0.7 or g > 1.2: return 1e3
        if L_eff < 2.0 or L_eff > 4.2: return 1e3
        if K_us < -0.003 or K_us > 0.015: return 1e3
        if tau < 0.005 or tau > 0.25: return 1e3
        return yaw_only_loss(segs, g, L_eff, K_us, tau)

    init = [0.88, L_prior, 0.003, 0.06]
    t1 = time.time()
    res = minimize(yaw_obj, init, method="Nelder-Mead",
                   options={"xatol": 1e-4, "fatol": 1e-6, "maxiter": 200})
    print(f"  Stage A (yaw-only) {time.time()-t1:.1f}s: yaw={res.fun:.5f}", flush=True)
    g, L_eff, K_us, tau = res.x
    y_a, c_a = both_loss(segs, g, L_eff, K_us, tau)
    print(f"    after A:  yaw={y_a:.5f} cte={c_a:.3f}  params g={g:.4f} L={L_eff:.3f} Kus={K_us:.5f} tau={tau:.4f}", flush=True)

    # Stage B: joint (g, tau) refine on (yaw + cte) normalised
    base_y, base_c = y_a, c_a
    def joint_obj(x):
        gg, tt = x
        if gg < 0.7 or gg > 1.2: return 1e3
        if tt < 0.005 or tt > 0.25: return 1e3
        y, c = both_loss(segs, gg, L_eff, K_us, tt)
        return y / base_y + c / base_c

    t2 = time.time()
    res2 = minimize(joint_obj, [g, tau], method="Nelder-Mead",
                    options={"xatol": 1e-4, "fatol": 1e-5, "maxiter": 80})
    g2, tau2 = res2.x
    y_b, c_b = both_loss(segs, g2, L_eff, K_us, tau2)
    print(f"  Stage B ({time.time()-t2:.1f}s): yaw={y_b:.5f} cte={c_b:.3f}", flush=True)

    # Pick whichever stage gives better combined score
    score_a = y_a / y0 + c_a / c0
    score_b = y_b / y0 + c_b / c0
    if score_b < score_a:
        chosen = {"g": float(g2), "L_eff": float(L_eff), "K_us": float(K_us),
                   "tau": float(tau2)}
        print(f"  CHOSE Stage B", flush=True)
    else:
        chosen = {"g": float(g), "L_eff": float(L_eff), "K_us": float(K_us),
                   "tau": float(tau)}
        print(f"  CHOSE Stage A", flush=True)
    chosen["use_per_segment_delta0"] = True
    chosen["delta0_fallback"] = 0.0
    return chosen


if __name__ == "__main__":
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        out[plat] = fit_one(plat)
    path = ROOT / "out" / "fitted_fast.json"
    with path.open("w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved {path}")
