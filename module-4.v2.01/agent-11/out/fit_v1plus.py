"""Per-platform joint fit of (g, K_us, tau, delta0_fallback) starting from V1 priors.

Trains on the frozen train split, scores on dev. v-filtered (v>2) sample yaw RMSE.
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))

from _shared.frozen_split import train_paths, dev_paths
from v1_baseline import PLATFORM_PARAMS_V1
from v1_fast import v1_predict_fast, cache_segments


def yaw_obj_for_platform(segs, params):
    """Pooled yaw SSE (v>2) under the given params."""
    sse = 0.0
    n = 0
    for s in segs:
        if s["yr_truth"] is None:
            continue
        yr, _ = v1_predict_fast(
            s["t"], s["delta"], s["v"], s["yr_v0"],
            g=params["g"], L_eff=params["L_eff"],
            K_us=params["K_us"], tau=params["tau"],
            delta0=params.get("delta0"),
            use_per_seg=params.get("use_per_seg", False),
            delta0_fallback=params.get("delta0_fallback", 0.0),
        )
        mask = s["v"] > 2.0
        r = yr[mask] - s["yr_truth"][mask]
        sse += float(np.sum(r * r))
        n += int(mask.sum())
    return sse, n


def main():
    plat_configs = {
        "FORD_F_150_LIGHTNING_MK1": {"use_per_seg": False, "fit_delta0": True},
        "FORD_MUSTANG_MACH_E_MK1": {"use_per_seg": True, "fit_delta0": False},
        "HYUNDAI_IONIQ_5": {"use_per_seg": True, "fit_delta0": False},
    }
    train = train_paths()
    dev = dev_paths()
    out = {}
    for plat, cfg in plat_configs.items():
        v1 = PLATFORM_PARAMS_V1[plat]
        print(f"\n== {plat} ==")
        t0 = time.time()
        train_segs = cache_segments(train, plat)
        dev_segs = cache_segments(dev, plat)
        print(f"  loaded train={len(train_segs)} dev={len(dev_segs)} in {time.time()-t0:.1f}s")

        # Initial params
        if cfg["fit_delta0"]:
            x0 = np.array([v1["g"], v1["K_us"], v1["tau"], v1["delta0"]])
            scale = np.array([1.0, 0.001, 0.01, 0.001])
        else:
            x0 = np.array([v1["g"], v1["K_us"], v1["tau"]])
            scale = np.array([1.0, 0.001, 0.01])

        def unpack(x):
            p = {"L_eff": v1["L_eff"], "use_per_seg": cfg["use_per_seg"]}
            p["g"] = x[0]
            p["K_us"] = x[1]
            p["tau"] = max(x[2], 1e-4)
            if cfg["fit_delta0"]:
                p["delta0"] = x[3]
            else:
                p["delta0_fallback"] = v1.get("delta0_fallback", 0.0)
            return p

        def obj(x):
            p = unpack(x)
            sse, n = yaw_obj_for_platform(train_segs, p)
            return sse / max(n, 1)

        # Baseline (V1 priors)
        sse0, n0 = yaw_obj_for_platform(train_segs, unpack(x0))
        train_v1 = (sse0 / n0) ** 0.5
        sse0d, n0d = yaw_obj_for_platform(dev_segs, unpack(x0))
        dev_v1 = (sse0d / n0d) ** 0.5
        print(f"  V1 priors: train rmse {train_v1:.6f}  dev rmse {dev_v1:.6f}")

        res = minimize(obj, x0, method="Nelder-Mead",
                       options={"xatol": 1e-5, "fatol": 1e-10, "maxiter": 200,
                                "initial_simplex": np.vstack([x0] + [x0 + scale * np.eye(len(x0))[i] for i in range(len(x0))])})
        print(f"  optimised in {time.time()-t0:.1f}s, nit={res.nit}")

        x_fit = res.x
        p_fit = unpack(x_fit)
        sse_t, n_t = yaw_obj_for_platform(train_segs, p_fit)
        train_fit = (sse_t / n_t) ** 0.5
        sse_d, n_d = yaw_obj_for_platform(dev_segs, p_fit)
        dev_fit = (sse_d / n_d) ** 0.5
        print(f"  fit: train rmse {train_fit:.6f}  dev rmse {dev_fit:.6f}")
        print(f"  x_fit: {x_fit}")

        out[plat] = {
            "v1_train_rmse": train_v1, "v1_dev_rmse": dev_v1,
            "fit_train_rmse": train_fit, "fit_dev_rmse": dev_fit,
            "params": p_fit, "delta_dev_pct": 100.0 * (dev_fit - dev_v1) / dev_v1,
        }
    out_path = ROOT / "out" / "v1plus_coeffs.json"
    with out_path.open("w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
