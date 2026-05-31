"""Score V0 baseline (the pre-computed yaw_rate_pred_rads column) on sim-only."""
from __future__ import annotations
import sys, glob, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-04")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa


def baseline_predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                        index=sim_df.index)


def score(predict_fn, segment_paths, sample_filter_v=2.0):
    rows = []
    failed = 0
    for p in segment_paths:
        try:
            sim_df = pd.read_csv(p)
        except Exception:
            failed += 1
            continue
        # Build sim-only style mirror — strip truth col before predict
        allowed = {"t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
                   "a_long_mps2", "accel_pedal_pct", "brake_pressed",
                   "yaw_rate_pred_rads"}
        # Map brake_pedal_state → brake_pressed
        sim_in = sim_df.copy()
        if "brake_pressed" not in sim_in.columns and "brake_pedal_state" in sim_in.columns:
            sim_in["brake_pressed"] = (sim_in["brake_pedal_state"] > 0).astype(int)
        sim_in = sim_in[[c for c in sim_in.columns if c in allowed]]
        platform = Path(p).resolve().parents[3].name

        try:
            pred = predict_fn(sim_in, platform)
        except Exception as e:
            failed += 1
            continue
        t = sim_df["t_s"].to_numpy(float)
        v = sim_df["v_mps"].to_numpy(float)
        yr_t = sim_df["yaw_rate_meas_rads"].to_numpy(float)
        yr_p = pred["yaw_rate_pred_rads"].to_numpy(float)
        mask = v > sample_filter_v
        r = yr_p[mask] - yr_t[mask]
        yr_n = int(mask.sum())
        if yr_n < 2:
            failed += 1
            continue
        cte = cte_diagnostics_segment(t, v, yr_t, yr_p)
        rows.append({
            "platform": platform,
            "yaw_sum_sq": float((r ** 2).sum()),
            "yaw_sum_signed": float(r.sum()),
            "n_samples": yr_n,
            "cte_sum_sq": cte["sum_sq_m2"],
            "cte_n_bins": cte["n_bins"],
            "cte_sum_signed": cte["sum_signed_m"],
        })
    seg = pd.DataFrame(rows)
    out = {}
    n = seg["n_samples"].sum()
    n_bins = seg["cte_n_bins"].sum()
    out["yaw_rmse"] = math.sqrt(seg["yaw_sum_sq"].sum() / n)
    out["cte_rmse"] = math.sqrt(seg["cte_sum_sq"].sum() / n_bins)
    out["n_segments"] = len(seg)
    out["failed"] = failed
    per_p = {}
    for plat, sub in seg.groupby("platform"):
        nn = sub["n_samples"].sum()
        nb = sub["cte_n_bins"].sum()
        per_p[plat] = {
            "yaw_rmse": math.sqrt(sub["yaw_sum_sq"].sum() / nn),
            "yaw_bias": sub["yaw_sum_signed"].sum() / nn,
            "cte_rmse": math.sqrt(sub["cte_sum_sq"].sum() / nb),
            "cte_signed": sub["cte_sum_signed"].sum() / nb,
            "n_seg": len(sub),
        }
    out["per_platform"] = per_p
    return out


def main():
    paths = sorted(glob.glob(str(ROOT / "data/sim/segments/*/*/*/*/sim.csv")))
    print(f"found {len(paths)} segments")
    result = score(baseline_predict, paths)
    print(f"V0 yaw_rmse={result['yaw_rmse']:.6f} rad/s")
    print(f"V0 cte_rmse={result['cte_rmse']:.4f} m")
    print(f"failed: {result['failed']} / {len(paths)}")
    for plat, m in result["per_platform"].items():
        print(f"  {plat}: yaw_rmse={m['yaw_rmse']:.5f} bias={m['yaw_bias']:+.5f} "
              f"cte_rmse={m['cte_rmse']:.3f} cte_signed={m['cte_signed']:+.3f} n={m['n_seg']}")


if __name__ == "__main__":
    main()
