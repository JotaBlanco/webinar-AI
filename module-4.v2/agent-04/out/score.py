"""Local scoring harness.

Loads sim segments, runs a predict() function, computes pooled yaw RMSE and
distance-resampled CTE RMSE. Splits segments into train/dev by hash for
quick iteration. Uses only allowlist-compatible columns when calling predict.
"""
from __future__ import annotations
import sys, os, math, json, hashlib, glob, argparse
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-04")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))
from traj_metrics import cte_rmse_segment

ALLOW_COLS = [
    "t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
    "a_long_mps2", "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads",
]

PLATFORMS_WITH_TRUTH = [
    "FORD_F_150_LIGHTNING_MK1",
    "FORD_MUSTANG_MACH_E_MK1",
    "HYUNDAI_IONIQ_5",
]


def find_segments(platform: str, split: str = "all", seed: int = 42, dev_frac: float = 0.3):
    """Return list of sim.csv paths for a platform, optionally split train/dev."""
    base = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(glob.glob(str(base / "**" / "sim.csv"), recursive=True))
    if split == "all":
        return paths
    out = []
    for p in paths:
        h = int(hashlib.md5(p.encode()).hexdigest(), 16) % 100
        thr = int(dev_frac * 100)
        if split == "dev" and h < thr:
            out.append(p)
        elif split == "train" and h >= thr:
            out.append(p)
    return out


def load_sim(path):
    df = pd.read_csv(path)
    # Ensure all allowlist columns exist (some sims may lack a few)
    for c in ALLOW_COLS:
        if c not in df.columns:
            if c == "accel_pedal_pct":
                df[c] = 0.0
            elif c == "brake_pressed":
                df[c] = 0
            else:
                df[c] = 0.0
    return df


def score_predict(predict_fn, platform: str, paths: list, max_segs: int | None = None):
    """Pooled yaw RMSE + pooled CTE RMSE across given paths."""
    if max_segs:
        paths = paths[:max_segs]
    yaw_sq = 0.0
    yaw_n = 0
    cte_sq = 0.0
    cte_bins = 0
    for p in paths:
        df = load_sim(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        truth = df["yaw_rate_meas_rads"].to_numpy()
        # Hand predict only the allowlist subset
        sim_df = df[ALLOW_COLS].copy()
        out = predict_fn(sim_df, platform)
        pred = out["yaw_rate_pred_rads"].to_numpy()
        # yaw rmse contribution
        diff = pred - truth
        yaw_sq += float((diff * diff).sum())
        yaw_n += len(diff)
        # cte contribution
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        s, n_bins, total = cte_rmse_segment(t, v, truth, pred)
        cte_sq += s
        cte_bins += n_bins
    yaw_rmse = math.sqrt(yaw_sq / max(yaw_n, 1))
    cte_rmse = math.sqrt(cte_sq / max(cte_bins, 1)) if cte_bins > 0 else float("nan")
    return {"yaw_rmse": yaw_rmse, "cte_rmse": cte_rmse, "n_samples": yaw_n, "n_bins": cte_bins, "n_segs": len(paths)}


def score_pooled(predict_fn, split: str = "dev", max_segs_per: int | None = None):
    """Pooled across all platforms with truth."""
    yaw_sq = 0.0
    yaw_n = 0
    cte_sq = 0.0
    cte_bins = 0
    per_plat = {}
    for plat in PLATFORMS_WITH_TRUTH:
        paths = find_segments(plat, split=split)
        if max_segs_per:
            paths = paths[:max_segs_per]
        if not paths:
            continue
        res = score_predict(predict_fn, plat, paths)
        per_plat[plat] = res
        yaw_n_p = res["n_samples"]
        yaw_sq += res["yaw_rmse"] ** 2 * yaw_n_p
        yaw_n += yaw_n_p
        cte_n_p = res["n_bins"]
        cte_sq += res["cte_rmse"] ** 2 * cte_n_p
        cte_bins += cte_n_p
    return {
        "pooled_yaw_rmse": math.sqrt(yaw_sq / max(yaw_n, 1)),
        "pooled_cte_rmse": math.sqrt(cte_sq / max(cte_bins, 1)),
        "per_platform": per_plat,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="v1", help="v1, final, or path to module")
    parser.add_argument("--split", default="dev")
    parser.add_argument("--max-segs", type=int, default=None)
    args = parser.parse_args()

    if args.model == "v1":
        from v1_baseline import predict_v1 as predict
    elif args.model == "final":
        sys.path.insert(0, str(ROOT / "final-model"))
        from predict import predict
    else:
        raise SystemExit(f"unknown model {args.model}")

    res = score_pooled(predict, split=args.split, max_segs_per=args.max_segs)
    print(json.dumps(res, indent=2))
