"""Local scoring harness for module-4.v1 agent-09.

Loads all segments under data/sim/segments/<platform>, calls a predict(sim_df, platform) callable,
computes pooled yaw-rate RMSE and pooled distance-resampled CTE RMSE.
"""
from __future__ import annotations
import math, sys, os, glob, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-09")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))

from traj_metrics import cte_rmse_segment  # type: ignore

ALLOWED_COLS = [
    "t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
    "a_long_mps2", "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads",
]

PLATFORMS_FIT = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
ALL_PLATFORMS = PLATFORMS_FIT + ["TESLA_MODEL_3"]


def list_segments(platform: str):
    """Return list of (sim_only_path, sim_full_path) pairs."""
    base_only = ROOT / "data" / "sim-only" / "segments" / platform
    base_full = ROOT / "data" / "sim" / "segments" / platform
    pairs = []
    for sp in sorted(base_only.glob("*/*/*/sim.csv")):
        rel = sp.relative_to(base_only)
        fp = base_full / rel
        if fp.exists():
            pairs.append((sp, fp))
    return pairs


def load_segment(p: Path) -> pd.DataFrame:
    return pd.read_csv(p)


def score_predict(predict_fn, platforms=PLATFORMS_FIT, max_per_platform=None, verbose=False):
    """Score predict_fn. Returns dict with yaw_rmse and cte_rmse pooled."""
    pooled = {"yaw_sse": 0.0, "yaw_n": 0, "cte_sse": 0.0, "cte_n": 0}
    per_platform = {}
    for plat in platforms:
        segs = list_segments(plat)
        if max_per_platform:
            segs = segs[:max_per_platform]
        p_yaw_sse = 0.0; p_yaw_n = 0; p_cte_sse = 0.0; p_cte_n = 0
        for sp_only, sp_full in segs:
            sim_df = load_segment(sp_only)
            # Defensive: keep only allowed cols
            missing = [c for c in ALLOWED_COLS if c not in sim_df.columns]
            if missing:
                continue
            sim_df = sim_df[ALLOWED_COLS].copy()
            df_full = load_segment(sp_full)
            if "yaw_rate_meas_rads" not in df_full.columns:
                continue
            yr_truth = df_full["yaw_rate_meas_rads"].to_numpy()
            try:
                out = predict_fn(sim_df, plat)
                yr_pred = out["yaw_rate_pred_rads"].to_numpy()
            except Exception as e:
                if verbose:
                    print(f"FAIL {sp}: {e}")
                continue
            res = yr_pred - yr_truth
            p_yaw_sse += float(np.sum(res * res))
            p_yaw_n += len(res)
            t = sim_df["t_s"].to_numpy()
            v = sim_df["v_mps"].to_numpy()
            if len(yr_truth) != len(yr_pred):
                continue
            sum_sq, n_bins, _ = cte_rmse_segment(t, v, yr_truth, yr_pred)
            p_cte_sse += sum_sq
            p_cte_n += n_bins
        per_platform[plat] = {
            "yaw_rmse": math.sqrt(p_yaw_sse / max(1, p_yaw_n)),
            "cte_rmse": math.sqrt(p_cte_sse / max(1, p_cte_n)),
            "n_samples": p_yaw_n, "n_bins": p_cte_n, "n_segments": len(segs),
        }
        pooled["yaw_sse"] += p_yaw_sse; pooled["yaw_n"] += p_yaw_n
        pooled["cte_sse"] += p_cte_sse; pooled["cte_n"] += p_cte_n
    return {
        "yaw_rmse": math.sqrt(pooled["yaw_sse"] / max(1, pooled["yaw_n"])),
        "cte_rmse": math.sqrt(pooled["cte_sse"] / max(1, pooled["cte_n"])),
        "per_platform": per_platform,
    }


if __name__ == "__main__":
    from v1_baseline import predict_v1
    print(json.dumps(score_predict(predict_v1, max_per_platform=20), indent=2))
