"""F150 load-transfer correction: yaw_pred = V1 × (1 + k1 * a_lat_proxy + k2 * a_lat_proxy^2).

Where a_lat_proxy is the V1 lateral accel ~= V1_yaw * v.
"""
from __future__ import annotations
import sys, json, math
from pathlib import Path
import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))

from _shared.frozen_split import train_paths, dev_paths
from _shared.traj_metrics import cte_rmse_segment
from v1_fast import cache_segments, v1_predict_fast
from v1_baseline import PLATFORM_PARAMS_V1


def v1_yr(s, p):
    yr, _ = v1_predict_fast(s["t"], s["delta"], s["v"], s["yr_v0"],
                             g=p["g"], L_eff=p["L_eff"], K_us=p["K_us"],
                             tau=p["tau"],
                             delta0=p.get("delta0"),
                             use_per_seg=p.get("use_per_segment_delta0", False),
                             delta0_fallback=p.get("delta0_fallback", 0.0))
    return yr


def correction_predict(yr_v1, v, k1, k2):
    a_lat = yr_v1 * v
    return yr_v1 * (1.0 + k1 * a_lat + k2 * a_lat * a_lat)


def score(segs, fn):
    sse_y = 0.0; n_y = 0; sse_c = 0.0; n_c = 0
    for s in segs:
        if s["yr_truth"] is None:
            continue
        yr = fn(s)
        mask = s["v"] > 2.0
        r = yr[mask] - s["yr_truth"][mask]
        sse_y += float(np.sum(r * r))
        n_y += int(mask.sum())
        sq, nb, _ = cte_rmse_segment(s["t"], s["v"], s["yr_truth"], yr)
        sse_c += sq; n_c += nb
    return (math.sqrt(sse_y/n_y) if n_y else None,
            math.sqrt(sse_c/n_c) if n_c else None)


def main():
    train = train_paths()
    dev = dev_paths()
    results = {}
    for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        p = PLATFORM_PARAMS_V1[plat]
        train_segs = cache_segments(train, plat)
        dev_segs = cache_segments(dev, plat)
        # Pre-compute V1 predictions
        for ss in train_segs + dev_segs:
            ss["yr_v1"] = v1_yr(ss, p)

        def fn(s, k1=0.0, k2=0.0):
            return correction_predict(s["yr_v1"], s["v"], k1, k2)

        # Baseline
        y_b, c_b = score(dev_segs, fn)
        print(f"\n== {plat} ==  V1 dev: yaw {y_b:.6f}  CTE {c_b:.3f}")

        # Search k1, k2 on train
        def obj(x):
            sse = 0.0; n = 0
            for s in train_segs:
                if s["yr_truth"] is None: continue
                yr = correction_predict(s["yr_v1"], s["v"], x[0], x[1])
                mask = s["v"] > 2.0
                r = yr[mask] - s["yr_truth"][mask]
                sse += float(np.sum(r * r))
                n += int(mask.sum())
            return sse / max(n, 1)

        res = minimize(obj, [0.0, 0.0], method="Nelder-Mead",
                       options={"xatol": 1e-7, "fatol": 1e-12, "maxiter": 200})
        k1, k2 = res.x
        def fn_fit(s, k1=k1, k2=k2):
            return correction_predict(s["yr_v1"], s["v"], k1, k2)
        y_t, c_t = score(train_segs, fn_fit)
        y_d, c_d = score(dev_segs, fn_fit)
        print(f"  fit (k1={k1:.5f}, k2={k2:.5f}):")
        print(f"    train yaw {y_t:.6f}")
        print(f"    dev   yaw {y_d:.6f}  CTE {c_d:.3f}  Δyaw={100*(y_d-y_b)/y_b:+.2f}%  ΔCTE={100*(c_d-c_b)/c_b:+.2f}%")
        results[plat] = {"k1": k1, "k2": k2, "v1_dev": (y_b, c_b), "fit_dev": (y_d, c_d)}

    out_path = ROOT / "out" / "loadtransfer_coeffs.json"
    json.dump(results, out_path.open("w"), indent=2, default=str)


if __name__ == "__main__":
    main()
