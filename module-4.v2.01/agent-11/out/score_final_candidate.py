"""Score the final candidate (V1 + per-platform load-transfer correction) on dev pooled."""
from __future__ import annotations
import sys, json, math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))

from _shared.frozen_split import dev_paths
from _shared.traj_metrics import cte_rmse_segment
from v1_fast import cache_segments, v1_predict_fast
from v1_baseline import PLATFORM_PARAMS_V1


# Per-platform correction coefficients fitted on train
COEFFS = {
    "FORD_F_150_LIGHTNING_MK1": {"k1": -0.00331, "k2": -0.00063},
    "FORD_MUSTANG_MACH_E_MK1": {"k1":  0.00179, "k2": -0.00271},
    "HYUNDAI_IONIQ_5":          {"k1":  0.0,     "k2":  0.0},   # V1 verbatim (no win)
}


def predict_final(s, platform):
    p = PLATFORM_PARAMS_V1[platform]
    yr_v1, _ = v1_predict_fast(s["t"], s["delta"], s["v"], s["yr_v0"],
                                g=p["g"], L_eff=p["L_eff"], K_us=p["K_us"],
                                tau=p["tau"],
                                delta0=p.get("delta0"),
                                use_per_seg=p.get("use_per_segment_delta0", False),
                                delta0_fallback=p.get("delta0_fallback", 0.0))
    c = COEFFS[platform]
    a_lat = yr_v1 * s["v"]
    return yr_v1 * (1.0 + c["k1"] * a_lat + c["k2"] * a_lat * a_lat)


def predict_v1(s, platform):
    p = PLATFORM_PARAMS_V1[platform]
    yr, _ = v1_predict_fast(s["t"], s["delta"], s["v"], s["yr_v0"],
                             g=p["g"], L_eff=p["L_eff"], K_us=p["K_us"],
                             tau=p["tau"],
                             delta0=p.get("delta0"),
                             use_per_seg=p.get("use_per_segment_delta0", False),
                             delta0_fallback=p.get("delta0_fallback", 0.0))
    return yr


def score_all():
    dev = dev_paths()
    by_plat = {}
    pool_y_sse = 0.0; pool_y_n = 0; pool_c_sse = 0.0; pool_c_n = 0
    pool_y_sse_v1 = 0.0; pool_c_sse_v1 = 0.0
    for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        segs = cache_segments(dev, plat)
        sy = 0.0; ny = 0; sc = 0.0; nc = 0
        sy_v1 = 0.0; sc_v1 = 0.0
        for s in segs:
            if s["yr_truth"] is None:
                continue
            yr_fin = predict_final(s, plat)
            yr_v1 = predict_v1(s, plat)
            mask = s["v"] > 2.0
            r = yr_fin[mask] - s["yr_truth"][mask]
            sy += float(np.sum(r*r))
            ny += int(mask.sum())
            sq, nb, _ = cte_rmse_segment(s["t"], s["v"], s["yr_truth"], yr_fin)
            sc += sq; nc += nb
            r_v1 = yr_v1[mask] - s["yr_truth"][mask]
            sy_v1 += float(np.sum(r_v1*r_v1))
            sq_v1, nb_v1, _ = cte_rmse_segment(s["t"], s["v"], s["yr_truth"], yr_v1)
            sc_v1 += sq_v1
        by_plat[plat] = {
            "final_yaw": math.sqrt(sy/ny) if ny else None,
            "final_cte": math.sqrt(sc/nc) if nc else None,
            "v1_yaw": math.sqrt(sy_v1/ny) if ny else None,
            "v1_cte": math.sqrt(sc_v1/nc) if nc else None,
        }
        pool_y_sse += sy; pool_y_n += ny; pool_c_sse += sc; pool_c_n += nc
        pool_y_sse_v1 += sy_v1; pool_c_sse_v1 += sc_v1
    final_y = math.sqrt(pool_y_sse / pool_y_n)
    final_c = math.sqrt(pool_c_sse / pool_c_n)
    v1_y = math.sqrt(pool_y_sse_v1 / pool_y_n)
    v1_c = math.sqrt(pool_c_sse_v1 / pool_c_n)
    print(f"\nPooled (3 platforms with truth):")
    print(f"  V1     yaw {v1_y:.6f}  CTE {v1_c:.4f}")
    print(f"  FINAL  yaw {final_y:.6f}  CTE {final_c:.4f}")
    print(f"  Δ      yaw {100*(final_y-v1_y)/v1_y:+.2f}%  CTE {100*(final_c-v1_c)/v1_c:+.2f}%")
    print(f"\nPer platform:")
    for plat, d in by_plat.items():
        print(f"  {plat}")
        print(f"    V1   : yaw {d['v1_yaw']:.6f}  CTE {d['v1_cte']:.3f}")
        print(f"    FINAL: yaw {d['final_yaw']:.6f}  CTE {d['final_cte']:.3f}")
    out = {"pooled": {"V1": {"yaw": v1_y, "cte": v1_c},
                       "FINAL": {"yaw": final_y, "cte": final_c}},
            "by_platform": by_plat, "coeffs": COEFFS}
    json.dump(out, (ROOT / "out" / "final_dev_scorecard.json").open("w"), indent=2, default=str)


if __name__ == "__main__":
    score_all()
