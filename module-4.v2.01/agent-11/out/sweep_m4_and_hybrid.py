"""Sigma sweep for M4, then test a V1+M4 blend per platform on dev."""
from __future__ import annotations
import sys, json, math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))

from _shared.frozen_split import train_paths, dev_paths
from _shared.traj_metrics import cte_rmse_segment
from v1_fast import cache_segments, v1_predict_fast
from v1_baseline import PLATFORM_PARAMS_V1


def m4_predict(t, delta, v, yr_v0, *, g, L_eff, K_us, sigma, delta0=None,
               use_per_seg=False, delta0_fallback=0.0):
    if use_per_seg:
        from v1_fast import _per_segment_delta0
        delta0 = _per_segment_delta0(delta, v, yr_v0, fallback=delta0_fallback)
    elif delta0 is None:
        delta0 = 0.0
    delta_eff = (delta - delta0) * g
    yr_demand = v * delta_eff / (L_eff + K_us * v * v)
    dt = np.diff(t, prepend=t[0])
    V_MIN = 1.5
    n = len(t)
    out = np.empty(n)
    out[0] = yr_demand[0] if v[0] >= V_MIN else yr_v0[0]
    state = out[0]
    for i in range(1, n):
        if v[i] < V_MIN or sigma <= 0:
            state = yr_v0[i]
            out[i] = state
            continue
        a = 1.0 - math.exp(-v[i] * dt[i] / sigma)
        state = state + a * (yr_demand[i] - state)
        out[i] = state
    return out


def yaw_cte_for_segs(segs, predfn_kwargs_list):
    """predfn_kwargs_list: list of (label, fn_returning_yr) — score each one pooled."""
    results = {}
    for label, fn in predfn_kwargs_list:
        sse_y = 0.0
        n_y = 0
        sse_c = 0.0
        n_c = 0
        for s in segs:
            if s["yr_truth"] is None:
                continue
            yr = fn(s)
            mask = s["v"] > 2.0
            r = yr[mask] - s["yr_truth"][mask]
            sse_y += float(np.sum(r * r))
            n_y += int(mask.sum())
            sq, nb, _ = cte_rmse_segment(s["t"], s["v"], s["yr_truth"], yr)
            sse_c += sq
            n_c += nb
        results[label] = {"yaw_rmse": math.sqrt(sse_y/n_y) if n_y else None,
                          "cte_rmse": math.sqrt(sse_c/n_c) if n_c else None,
                          "n_y": n_y, "n_c": n_c}
    return results


def main():
    train = train_paths()
    dev = dev_paths()
    final_sigmas = {}
    out_summary = {}
    for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        v1p = PLATFORM_PARAMS_V1[plat]
        train_segs = cache_segments(train, plat)
        dev_segs = cache_segments(dev, plat)
        # V1 fn
        def v1_fn(s, p=v1p):
            yr, _ = v1_predict_fast(s["t"], s["delta"], s["v"], s["yr_v0"],
                                    g=p["g"], L_eff=p["L_eff"], K_us=p["K_us"],
                                    tau=p["tau"],
                                    delta0=p.get("delta0"),
                                    use_per_seg=p.get("use_per_segment_delta0", False),
                                    delta0_fallback=p.get("delta0_fallback", 0.0))
            return yr

        v1_res = yaw_cte_for_segs(dev_segs, [("V1", v1_fn)])["V1"]
        print(f"\n== {plat} ==")
        print(f"  V1 dev: yaw {v1_res['yaw_rmse']:.6f}  CTE {v1_res['cte_rmse']:.3f}")

        # Sigma sweep on train, optimize for yaw
        sigmas = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.80, 1.0, 1.5, 2.0]
        best_sigma = None
        best_train_yaw = 1e9
        for sg in sigmas:
            def m4_fn(s, p=v1p, sigma=sg):
                return m4_predict(s["t"], s["delta"], s["v"], s["yr_v0"],
                                  g=p["g"], L_eff=p["L_eff"], K_us=p["K_us"],
                                  sigma=sigma,
                                  delta0=p.get("delta0"),
                                  use_per_seg=p.get("use_per_segment_delta0", False),
                                  delta0_fallback=p.get("delta0_fallback", 0.0))
            tr = yaw_cte_for_segs(train_segs, [("M4", m4_fn)])["M4"]
            if tr["yaw_rmse"] < best_train_yaw:
                best_train_yaw = tr["yaw_rmse"]
                best_sigma = sg
        final_sigmas[plat] = best_sigma
        # Score dev for best sigma
        def m4_best_fn(s, p=v1p, sigma=best_sigma):
            return m4_predict(s["t"], s["delta"], s["v"], s["yr_v0"],
                              g=p["g"], L_eff=p["L_eff"], K_us=p["K_us"],
                              sigma=sigma,
                              delta0=p.get("delta0"),
                              use_per_seg=p.get("use_per_segment_delta0", False),
                              delta0_fallback=p.get("delta0_fallback", 0.0))
        m4_dev = yaw_cte_for_segs(dev_segs, [("M4", m4_best_fn)])["M4"]
        print(f"  M4 σ={best_sigma}: dev yaw {m4_dev['yaw_rmse']:.6f}  CTE {m4_dev['cte_rmse']:.3f}")

        # Hybrid: weighted blend in [0,1] of V1 and M4. Search on train.
        best_w = 0.0
        best_blend_yaw = v1_res["yaw_rmse"]
        for w in [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]:
            def blend_fn(s, p=v1p, sigma=best_sigma, ww=w):
                yr1, _ = v1_predict_fast(s["t"], s["delta"], s["v"], s["yr_v0"],
                                          g=p["g"], L_eff=p["L_eff"], K_us=p["K_us"],
                                          tau=p["tau"],
                                          delta0=p.get("delta0"),
                                          use_per_seg=p.get("use_per_segment_delta0", False),
                                          delta0_fallback=p.get("delta0_fallback", 0.0))
                yr2 = m4_predict(s["t"], s["delta"], s["v"], s["yr_v0"],
                                  g=p["g"], L_eff=p["L_eff"], K_us=p["K_us"],
                                  sigma=sigma,
                                  delta0=p.get("delta0"),
                                  use_per_seg=p.get("use_per_segment_delta0", False),
                                  delta0_fallback=p.get("delta0_fallback", 0.0))
                return (1-ww)*yr1 + ww*yr2
            tr = yaw_cte_for_segs(train_segs, [("B", blend_fn)])["B"]
            if tr["yaw_rmse"] < best_blend_yaw:
                best_blend_yaw = tr["yaw_rmse"]
                best_w = w
        # Score dev for best blend
        def best_blend_dev(s, p=v1p, sigma=best_sigma, ww=best_w):
            yr1, _ = v1_predict_fast(s["t"], s["delta"], s["v"], s["yr_v0"],
                                      g=p["g"], L_eff=p["L_eff"], K_us=p["K_us"],
                                      tau=p["tau"],
                                      delta0=p.get("delta0"),
                                      use_per_seg=p.get("use_per_segment_delta0", False),
                                      delta0_fallback=p.get("delta0_fallback", 0.0))
            yr2 = m4_predict(s["t"], s["delta"], s["v"], s["yr_v0"],
                              g=p["g"], L_eff=p["L_eff"], K_us=p["K_us"],
                              sigma=sigma,
                              delta0=p.get("delta0"),
                              use_per_seg=p.get("use_per_segment_delta0", False),
                              delta0_fallback=p.get("delta0_fallback", 0.0))
            return (1-ww)*yr1 + ww*yr2
        blend_dev = yaw_cte_for_segs(dev_segs, [("B", best_blend_dev)])["B"]
        print(f"  Blend w={best_w}: dev yaw {blend_dev['yaw_rmse']:.6f}  CTE {blend_dev['cte_rmse']:.3f}")
        out_summary[plat] = {"V1": v1_res, "M4": m4_dev, "best_sigma": best_sigma,
                              "blend_w": best_w, "blend": blend_dev}

    json.dump(out_summary, (ROOT / "out" / "sweep_summary.json").open("w"), indent=2, default=str)
    print("\nFinal sigmas:", final_sigmas)


if __name__ == "__main__":
    main()
