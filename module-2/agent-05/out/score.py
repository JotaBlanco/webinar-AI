"""Local scorer adapted to actual data layout (data/sim/segments/...).

Enforces the same input-allowlist as the canonical grader.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa: E402

ALLOWED_INPUT_COLUMNS = frozenset({
    "t_s", "delta_wheel_deg", "delta_road_rad", "v_mps", "a_long_mps2",
    "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads",
})

SAMPLE_FILTER_V_MPS = 2.0
GRID_STEP_M = 1.0
MIN_DIST_M = 20.0


def _platform_from_path(p: Path) -> str:
    # data/sim/segments/<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv
    return p.parts[-5]


def _route_from_path(p: Path) -> str:
    return p.parts[-3]


def find_segments(platform: str | None = None) -> list[Path]:
    root = ROOT / "data" / "sim" / "segments"
    if platform:
        return sorted((root / platform).rglob("sim.csv"))
    return sorted(root.rglob("sim.csv"))


def score(predict_fn, segment_paths, sample_filter_v_mps=SAMPLE_FILTER_V_MPS,
          grid_step_m=GRID_STEP_M, min_distance_m=MIN_DIST_M):
    rows = []
    failed = 0
    for p in segment_paths:
        platform = _platform_from_path(p)
        try:
            sim_df = pd.read_csv(p)
        except Exception:
            failed += 1
            continue
        # Need truth
        if "yaw_rate_meas_rads" not in sim_df.columns:
            continue
        # Strip to allowlist
        sim_df_agent = sim_df[[c for c in sim_df.columns if c in ALLOWED_INPUT_COLUMNS]].copy()
        try:
            pred_df = predict_fn(sim_df_agent, platform)
        except Exception as e:
            failed += 1
            print(f"FAIL {p.name}: {e}")
            continue
        if not isinstance(pred_df, pd.DataFrame) or "yaw_rate_pred_rads" not in pred_df.columns:
            failed += 1
            continue
        if len(pred_df) != len(sim_df):
            failed += 1
            continue

        t = sim_df["t_s"].to_numpy(float)
        v = sim_df["v_mps"].to_numpy(float)
        yr_truth = sim_df["yaw_rate_meas_rads"].to_numpy(float)
        yr_pred = pred_df["yaw_rate_pred_rads"].to_numpy(float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            failed += 1
            continue
        mask_v = v > sample_filter_v_mps
        resid = yr_pred - yr_truth
        r_v = resid[mask_v]
        yr_n = int(mask_v.sum())
        yr_sum_sq = float(np.sum(r_v ** 2))
        cte = cte_diagnostics_segment(t, v, yr_truth, yr_pred,
                                      grid_step_m=grid_step_m, min_distance_m=min_distance_m)
        rows.append({
            "segment_path": str(p),
            "platform": platform,
            "route": _route_from_path(p),
            "n_samples": yr_n,
            "yaw_sum_sq": yr_sum_sq,
            "yaw_sum_signed": float(np.sum(r_v)),
            "cte_sum_sq": cte["sum_sq_m2"],
            "cte_sum_signed": cte["sum_signed_m"],
            "cte_n_bins": cte["n_bins"],
            "distance_m": cte["total_distance_m"],
        })
    if not rows:
        return None
    seg = pd.DataFrame(rows)
    overall_yaw = math.sqrt(seg["yaw_sum_sq"].sum() / seg["n_samples"].sum())
    nbins = seg["cte_n_bins"].sum()
    overall_cte = math.sqrt(seg["cte_sum_sq"].sum() / nbins) if nbins > 0 else float("nan")
    per_platform = {}
    for plat, sub in seg.groupby("platform"):
        n = int(sub["n_samples"].sum())
        nb = int(sub["cte_n_bins"].sum())
        per_platform[plat] = {
            "yaw_rmse": math.sqrt(sub["yaw_sum_sq"].sum() / n) if n else float("nan"),
            "yaw_bias": float(sub["yaw_sum_signed"].sum() / n) if n else float("nan"),
            "cte_rmse": math.sqrt(sub["cte_sum_sq"].sum() / nb) if nb else float("nan"),
            "cte_signed_mean": float(sub["cte_sum_signed"].sum() / nb) if nb else float("nan"),
            "n_segments": int(len(sub)),
        }
    return {
        "yaw_rate_rmse": overall_yaw,
        "cte_rmse": overall_cte,
        "n_segments": len(seg),
        "failed_segments": failed,
        "per_platform": per_platform,
        "per_segment": seg,
    }


def print_summary(r):
    print(f"n_segments={r['n_segments']}, failed={r['failed_segments']}")
    print(f"yaw_rate_rmse = {r['yaw_rate_rmse']:.6f} rad/s")
    print(f"cte_rmse      = {r['cte_rmse']:.4f} m")
    print("per platform:")
    for k, v in r["per_platform"].items():
        print(f"  {k:30s} yaw={v['yaw_rmse']:.5f} bias={v['yaw_bias']:+.5f} cte={v['cte_rmse']:.3f} cte_signed={v['cte_signed_mean']:+.3f} n={v['n_segments']}")
