"""Check whether residuals have per-route mean structure (sensor bias drift)."""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "final-model"))
from predict import predict


def per_route_stats(platform):
    paths = sorted(glob.glob(
        str(ROOT / "data" / "sim" / "segments" / platform / "*" / "**" / "sim.csv"),
        recursive=True,
    ))
    rows = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        m = df["v_mps"] > 2.0
        if m.sum() == 0:
            continue
        pred = predict(df.loc[:, [c for c in df.columns if c in {
            "t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
            "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"}]], platform)
        resid = (pred["yaw_rate_pred_rads"] - df["yaw_rate_meas_rads"]).to_numpy()
        resid_v = resid[m.to_numpy()]
        route = Path(p).resolve().parents[1].name
        device = Path(p).resolve().parents[2].name
        rows.append({
            "device": device,
            "route": route,
            "n": int(m.sum()),
            "resid_mean": float(np.mean(resid_v)),
            "resid_std": float(np.std(resid_v)),
        })
    df_r = pd.DataFrame(rows)
    print(f"\n{platform}: {len(df_r)} segments")
    print(f"  overall_resid_mean = {(df_r['resid_mean']*df_r['n']).sum()/df_r['n'].sum():+.6f}")
    print(f"  std of per-route resid_mean across segments: {df_r['resid_mean'].std():.6f}")
    # group by route — mean of segment means weighted by n
    by_route = df_r.groupby("route").apply(lambda g: pd.Series({
        "n": g["n"].sum(),
        "mean": (g["resid_mean"] * g["n"]).sum() / g["n"].sum(),
    })).reset_index()
    print(f"  routes with |mean| > 0.005: "
          f"{(by_route['mean'].abs() > 0.005).sum()} / {len(by_route)}")
    print(by_route.nlargest(5, "mean").to_string(index=False))
    print(by_route.nsmallest(5, "mean").to_string(index=False))


for plat in ["HYUNDAI_IONIQ_5", "FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]:
    per_route_stats(plat)
