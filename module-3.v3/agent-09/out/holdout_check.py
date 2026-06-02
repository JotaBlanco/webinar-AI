"""Quick route-grouped holdout: fit affine s,b per-platform on a 70% route
subset, score on the held-out 30%. If pooled KPIs still beat V1 out-of-sample,
the in-sample fit is real."""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from v1_baseline import predict_v1  # type: ignore
from score import score, format_summary  # type: ignore


def route_in_train(platform: str, route: str, frac: float = 0.7) -> bool:
    h = hashlib.md5(f"{platform}/{route}".encode()).digest()
    r = int.from_bytes(h[:4], "big") / 2**32
    return r < frac


def fit_affine(platform: str):
    SX = SY = SXX = SXY = 0.0
    n = 0
    seg_root = ROOT / "data" / "sim" / "segments" / platform
    for p in seg_root.glob("**/sim.csv"):
        route = p.parents[1].name
        if not route_in_train(platform, route):
            continue
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        sub = df[[c for c in df.columns if c in
                  {"t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
                   "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"}]].copy()
        if "yaw_rate_pred_rads" not in sub.columns:
            continue
        try:
            yv = predict_v1(sub, platform)["yaw_rate_pred_rads"].to_numpy()
        except Exception:
            continue
        yt = df["yaw_rate_meas_rads"].to_numpy()
        v = sub["v_mps"].to_numpy()
        m = v > 2.0
        x = yv[m]; y = yt[m]
        SX += x.sum(); SY += y.sum(); SXX += (x*x).sum(); SXY += (x*y).sum(); n += int(m.sum())
    if n == 0: return 1.0, 0.0
    denom = n*SXX - SX*SX
    s = (n*SXY - SX*SY) / denom
    b = (SY - s*SX) / n
    return float(s), float(b)


COEFFS = {plat: fit_affine(plat) for plat in
          ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]}
print("Train-fit coeffs:")
for k, v in COEFFS.items():
    print(f"  {k}: s={v[0]:.5f} b={v[1]:+.6f}")


def predict_holdout(sim_df, platform):
    base = predict_v1(sim_df, platform)
    if platform == "TESLA_MODEL_3" or platform not in COEFFS:
        return base
    s, b = COEFFS[platform]
    yr = base["yaw_rate_pred_rads"].to_numpy() * s + b
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)


# Score only on holdout segments
seg_paths = []
for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]:
    seg_root = ROOT / "data" / "sim" / "segments" / plat
    for p in seg_root.glob("**/sim.csv"):
        route = p.parents[1].name
        if not route_in_train(plat, route):
            seg_paths.append(p)

print(f"Holdout segments: {len(seg_paths)}")

# Score V1 on same holdout
res_v1 = score(predict_v1, segment_paths=seg_paths)
res_hd = score(predict_holdout, segment_paths=seg_paths)
print(f"V1   holdout: yaw={res_v1['yaw_rate_rmse']:.6f} cte={res_v1['cte_rmse']:.4f}")
print(f"D    holdout: yaw={res_hd['yaw_rate_rmse']:.6f} cte={res_hd['cte_rmse']:.4f}")
for plat in res_v1['per_platform']:
    a = res_v1['per_platform'][plat]
    b = res_hd['per_platform'][plat]
    print(f"  {plat}: V1 yaw={a['yaw_rate_rmse']:.5f}/cte={a['cte_rmse']:.2f}  -> D yaw={b['yaw_rate_rmse']:.5f}/cte={b['cte_rmse']:.2f}")
