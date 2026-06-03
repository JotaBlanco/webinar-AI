"""Vectorized V1 baseline, plus train-data cache for fast fitting."""
from __future__ import annotations
import sys, pickle, hashlib
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _shared.frozen_split import train_paths, dev_paths

CACHE_DIR = ROOT / "out" / "cache"
CACHE_DIR.mkdir(exist_ok=True, parents=True)


def _per_segment_delta0(delta_road, v, yr_v0, fallback=0.0,
                         yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(delta_road[mask]))


def v1_predict_fast(t, delta_road, v, yr_v0, *, g, L_eff, K_us, tau,
                    delta0=None, use_per_seg=False, delta0_fallback=0.0):
    if use_per_seg:
        delta0 = _per_segment_delta0(delta_road, v, yr_v0, fallback=delta0_fallback)
    elif delta0 is None:
        delta0 = 0.0
    delta = (delta_road - delta0) * g
    yr_ss = v * delta / (L_eff + K_us * v * v)
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    # Scan (small Python loop, but small per segment)
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr, delta0


def load_segments(paths, platform):
    """Load only segments matching the platform, return list of dicts."""
    segs = []
    for p in paths:
        if p.parts[-5] != platform:
            continue
        df = pd.read_csv(p)
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
        yr_truth = df["yaw_rate_meas_rads"].to_numpy() if "yaw_rate_meas_rads" in df.columns else None
        segs.append({"t": t, "v": v, "delta": delta, "yr_v0": yr_v0,
                     "yr_truth": yr_truth, "path": str(p)})
    return segs


def cache_segments(paths, platform):
    key = hashlib.md5((platform + "|" + "|".join(str(p) for p in paths)).encode()).hexdigest()[:16]
    cache = CACHE_DIR / f"segs_{platform}_{key}.pkl"
    if cache.exists():
        with cache.open("rb") as fh:
            return pickle.load(fh)
    segs = load_segments(paths, platform)
    with cache.open("wb") as fh:
        pickle.dump(segs, fh)
    return segs
