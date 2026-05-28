"""Trajectory metrics used by the canonical-eval pipeline.

Two primary KPIs:
- yaw-rate RMSE: computed inline in prepare_canonical.py and the judge prompt.
- distance-resampled cross-track-error RMSE: provided by `cte_rmse_segment` here.

Both pipelines (V0 baseline in prepare_canonical.py + per-agent judges) import this
module so the metric is computed identically everywhere. If you tweak the integration
scheme or the resampling, do it here, once.

Conventions:
- All angles in radians, all distances in meters, all times in seconds.
- Trajectories integrate Euler-style with zero-order hold on each step:
    psi[i+1] = psi[i] + yr[i] * dt[i]
    x[i+1]   = x[i] + v[i] * cos(psi[i]) * dt[i]
    y[i+1]   = y[i] + v[i] * sin(psi[i]) * dt[i]
  All start from (s, x, y, psi) = (0, 0, 0, 0).
- Under the project's operating contract (clamp_v_to_measured=True) the predicted
  and truth trajectories use the same v_meas, so their cumulative distance s is
  identical at every sample. This is exploited below — pred quantities are
  interpolated against the truth's s array.
"""

from __future__ import annotations

import math

import numpy as np


def integrate_trajectory(dt: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Integrate (yr, v) from (0,0,0,0).

    Args:
        dt: per-step duration, length n-1 (dt[i] = t[i+1] - t[i]).
        v:  speed per sample, length n.
        yr: yaw rate per sample, length n.

    Returns:
        s, x, y, psi — each length n, all starting at 0.
    """
    n = len(v)
    if n < 2:
        z = np.zeros(n)
        return z, z, z, z

    psi = np.empty(n)
    psi[0] = 0.0
    psi[1:] = np.cumsum(yr[:-1] * dt)

    x = np.empty(n)
    x[0] = 0.0
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)

    y = np.empty(n)
    y[0] = 0.0
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)

    s = np.empty(n)
    s[0] = 0.0
    s[1:] = np.cumsum(v[:-1] * dt)

    return s, x, y, psi


def cte_rmse_segment(
    t: np.ndarray,
    v: np.ndarray,
    yr_truth: np.ndarray,
    yr_pred: np.ndarray,
    grid_step_m: float = 1.0,
    min_distance_m: float = 20.0,
) -> tuple[float, int, float]:
    """Compute the segment's contribution to the pooled distance-resampled CTE RMSE.

    The "CTE" here is the Euclidean displacement between predicted and truth
    trajectories at matched cumulative-distance points along the truth path.
    Under the v-clamped contract this is equivalent to |signed cross-track error|
    because along-track error is zero by construction.

    Args:
        t:        time per sample (seconds), length n.
        v:        measured speed per sample (m/s), length n.
        yr_truth: measured yaw rate (rad/s), length n.
        yr_pred:  predicted yaw rate (rad/s), length n.
        grid_step_m: distance grid spacing in meters (default 1.0).
        min_distance_m: minimum truth-path distance to include the segment (default 20.0).

    Returns:
        (sum_sq_m2, n_bins, total_distance_m).
        Aggregate across segments by accumulating sum_sq and n_bins, then
        pooled_rmse = sqrt(sum_sq / n_bins).
        If the segment travelled less than min_distance, returns (0.0, 0, total_distance).
    """
    if len(v) < 2:
        return 0.0, 0, 0.0
    dt = np.diff(t)
    # Safety: dt must be positive.
    if np.any(dt <= 0):
        return 0.0, 0, 0.0

    s_t, x_t, y_t, _ = integrate_trajectory(dt, v, yr_truth)
    _,   x_p, y_p, _ = integrate_trajectory(dt, v, yr_pred)

    total = float(s_t[-1])
    if total < min_distance_m:
        return 0.0, 0, total

    # Build the uniform distance grid [grid_step, 2*grid_step, ..., <= total].
    n_bins = int(math.floor(total / grid_step_m))
    if n_bins <= 0:
        return 0.0, 0, total
    grid = np.arange(1, n_bins + 1, dtype=float) * grid_step_m

    # s_t is monotonic non-decreasing in time (cumulative distance with v >= 0).
    # If v can ever be zero, s_t has flat sections — np.interp handles them fine
    # by returning the value at the start of the flat section.
    x_t_g = np.interp(grid, s_t, x_t)
    y_t_g = np.interp(grid, s_t, y_t)
    x_p_g = np.interp(grid, s_t, x_p)
    y_p_g = np.interp(grid, s_t, y_p)

    err_sq = (x_t_g - x_p_g) ** 2 + (y_t_g - y_p_g) ** 2
    return float(err_sq.sum()), int(n_bins), total


def cte_baseline_from_segments(
    segment_paths: list,
    truth_channel: str = "yaw_rate_meas_rads",
    pred_channel: str = "yaw_rate_pred_rads",
    grid_step_m: float = 1.0,
    min_distance_m: float = 20.0,
    sample_filter_expr: str = "True",
) -> dict:
    """Compute pooled CTE RMSE for V0 across the canonical eval set.

    Loads sim.csv files directly (no pandas dependency to keep prep light).
    `sample_filter_expr` is ignored for trajectory integration — integration
    needs the full continuous time series. The filter is for the *yaw-rate*
    RMSE pipeline, which is sample-pooled; CTE is segment-then-bin-pooled.

    Returns a dict ready to merge into baseline.json.
    """
    import csv
    from pathlib import Path

    total_sum_sq = 0.0
    total_bins = 0
    n_used = 0
    n_skipped_short = 0
    n_skipped_bad = 0
    total_dist_all = 0.0

    for p in segment_paths:
        p = Path(p)
        with p.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        try:
            t = np.array([float(r["t_s"]) for r in rows], dtype=float)
            v = np.array([float(r["v_mps"]) for r in rows], dtype=float)
            yr_truth = np.array([float(r[truth_channel]) for r in rows], dtype=float)
            yr_pred = np.array([float(r[pred_channel]) for r in rows], dtype=float)
        except (KeyError, ValueError):
            n_skipped_bad += 1
            continue
        sum_sq, n_bins, total = cte_rmse_segment(
            t, v, yr_truth, yr_pred,
            grid_step_m=grid_step_m, min_distance_m=min_distance_m,
        )
        total_dist_all += total
        if n_bins == 0:
            n_skipped_short += 1
        else:
            total_sum_sq += sum_sq
            total_bins += n_bins
            n_used += 1

    if total_bins == 0:
        raise RuntimeError(
            f"cte_baseline_from_segments: zero qualifying distance-bins. "
            f"n_segments={len(segment_paths)}, n_skipped_short={n_skipped_short}, "
            f"n_skipped_bad={n_skipped_bad}"
        )

    rmse = math.sqrt(total_sum_sq / total_bins)
    return {
        "rmse_meters": rmse,
        "n_segments_used": n_used,
        "n_segments_skipped_short": n_skipped_short,
        "n_segments_skipped_bad": n_skipped_bad,
        "n_distance_bins": total_bins,
        "total_distance_m": total_dist_all,
        "grid_step_m": grid_step_m,
        "min_segment_distance_m": min_distance_m,
        "truth_channel": truth_channel,
        "pred_channel": pred_channel,
    }
