"""Build per-platform feature matrices and residuals from V1 predictions.

For each platform (Ford Lightning, Mach-E, IONIQ-5), iterate over the sim
segments, run predict_v1, capture (yaw_truth - yaw_v1) and a small set of
features computed from the allowlist columns only.

Saves a parquet/csv per platform under out/residuals/.

Tesla is skipped (no truth).
"""
from __future__ import annotations

import sys
from pathlib import Path
import json

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-02")
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))

from v1_baseline import predict_v1  # noqa: E402

OUT_DIR = ROOT / "out" / "residuals"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PLATFORMS = [
    "FORD_F_150_LIGHTNING_MK1",
    "FORD_MUSTANG_MACH_E_MK1",
    "HYUNDAI_IONIQ_5",
]


def per_segment_delta0(sim_df, fallback=0.0):
    """Replicates V1 per-segment delta0 estimation, used as a feature too."""
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
    if int(mask.sum()) < 50:
        return fallback
    return float(np.median(sim_df.loc[mask, "delta_road_rad"]))


def build_for_platform(platform):
    seg_paths = sorted((ROOT / "data" / "sim" / "segments" / platform).glob("**/sim.csv"))
    print(f"[{platform}] {len(seg_paths)} segments")
    rows = []
    for p in seg_paths:
        try:
            df = pd.read_csv(p)
        except Exception as e:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        # Strip to allowlist + truth, mirror canonical grader contract.
        keep = ["t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
                "a_long_mps2", "accel_pedal_pct", "brake_pressed",
                "yaw_rate_pred_rads"]
        keep = [c for c in keep if c in df.columns]
        sim_in = df[keep].copy()
        try:
            pred = predict_v1(sim_in, platform)
        except Exception as e:
            print(f"  predict failed: {p}: {e}")
            continue
        yr_v1 = pred["yaw_rate_pred_rads"].to_numpy()
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        resid = yr_truth - yr_v1  # we want to predict this

        v = sim_in["v_mps"].to_numpy()
        delta = sim_in["delta_road_rad"].to_numpy()
        t = sim_in["t_s"].to_numpy()
        ddelta_dt = np.gradient(delta, t)
        a_long = sim_in["a_long_mps2"].to_numpy() if "a_long_mps2" in sim_in.columns else np.zeros_like(v)
        brake = sim_in["brake_pressed"].to_numpy().astype(float) if "brake_pressed" in sim_in.columns else np.zeros_like(v)

        # ay proxy with V1's prediction (truth-free)
        ay_proxy = v * yr_v1

        # path id for route-grouped CV
        route = str(p.resolve().parents[1].name)

        seg_df = pd.DataFrame({
            "route": route,
            "seg": str(p.resolve().parents[0].name),
            "v": v,
            "delta": delta,
            "ddelta_dt": ddelta_dt,
            "a_long": a_long,
            "brake": brake,
            "yr_v1": yr_v1,
            "ay_proxy": ay_proxy,
            "resid": resid,
        })
        # Filter low-speed; that's where V1 noise is misleading
        seg_df = seg_df[v > 2.0].reset_index(drop=True)
        rows.append(seg_df)

    if not rows:
        return None
    big = pd.concat(rows, ignore_index=True)
    out = OUT_DIR / f"{platform}.parquet"
    big.to_parquet(out, index=False)
    print(f"  saved {len(big):,} rows to {out}")
    return big


def main():
    for plat in PLATFORMS:
        build_for_platform(plat)


if __name__ == "__main__":
    main()
