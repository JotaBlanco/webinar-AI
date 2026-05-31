"""Score any predict callable against a list of segment sim.csv files.

Returns pooled yaw-rate RMSE (rad/s) and pooled distance-resampled CTE RMSE (m),
plus per-platform and per-regime breakdowns. CTE math is imported from
`_shared/traj_metrics.py` so the metric is identical everywhere.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from traj_metrics import cte_rmse_segment, integrate_trajectory  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _platform_from_path(p: Path) -> str:
    """Platform is the 3rd-from-rightmost dir in data/sim/segments/<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv."""
    # parts: ..., PLATFORM, DEVICE, ROUTE, IDX, sim.csv -> parents[3]
    return p.resolve().parents[3].name


def _default_segment_paths() -> list[Path]:
    """All sim.csv under data/sim/segments/FORD_*/**/sim.csv relative to cwd."""
    root = Path.cwd() / "data" / "sim" / "segments"
    if not root.exists():
        return []
    return sorted(root.glob("FORD_*/**/sim.csv"))


def _regime_mask(delta_road: np.ndarray, t: np.ndarray) -> dict[str, np.ndarray]:
    """Return boolean masks for straight / steady / transient regimes."""
    straight = np.abs(delta_road) < 0.01
    # d(delta)/dt via np.gradient (handles non-uniform dt)
    if len(t) >= 2:
        ddelta_dt = np.gradient(delta_road, t)
    else:
        ddelta_dt = np.zeros_like(delta_road)
    steady = (~straight) & (np.abs(ddelta_dt) < 0.05)
    transient = (~straight) & (~steady)
    return {"straight": straight, "steady": steady, "transient": transient}


def _empty_acc() -> dict:
    return {
        "yr_sum_sq": 0.0,
        "yr_n": 0,
        "cte_sum_sq": 0.0,
        "cte_n_bins": 0,
        "n_segments": 0,
    }


def _empty_regime_acc() -> dict:
    return {k: {"yr_sum_sq": 0.0, "yr_n": 0} for k in ("straight", "steady", "transient")}


def _finalize(acc: dict) -> dict:
    yr_rmse = math.sqrt(acc["yr_sum_sq"] / acc["yr_n"]) if acc["yr_n"] > 0 else float("nan")
    cte_rmse = math.sqrt(acc["cte_sum_sq"] / acc["cte_n_bins"]) if acc["cte_n_bins"] > 0 else float("nan")
    return {
        "yaw_rate_rmse": yr_rmse,
        "cte_rmse": cte_rmse,
        "n_segments": acc["n_segments"],
        "n_samples": acc["yr_n"],
    }


def _finalize_regime(racc: dict) -> dict:
    out = {}
    for k, v in racc.items():
        rmse = math.sqrt(v["yr_sum_sq"] / v["yr_n"]) if v["yr_n"] > 0 else float("nan")
        out[k] = {"yaw_rate_rmse": rmse, "n_samples": v["yr_n"]}
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score(
    predict_fn,
    segment_paths: list | None = None,
    platform_filter: str | None = None,
    grid_step_m: float = 1.0,
    min_distance_m: float = 20.0,
    sample_filter_v_mps: float = 2.0,
) -> dict:
    """Score a predict callable across segments.

    Args:
        predict_fn: callable(sim_df, platform) -> DataFrame aligned with sim_df.index.
            Required column: ``yaw_rate_pred_rads``. Optional: ``x_m``, ``y_m``.
        segment_paths: list of sim.csv paths. If None, glob all
            ``data/sim/segments/FORD_*/**/sim.csv`` under the current working dir.
        platform_filter: if set, only keep segments whose platform dir matches.
        grid_step_m: distance grid spacing for CTE (meters).
        min_distance_m: CTE drops segments whose travelled distance is below this.
        sample_filter_v_mps: yaw-rate RMSE pools samples where ``v_mps`` exceeds this.

    Returns:
        dict with overall and per-platform / per-regime breakdowns. See SKILL.md.
    """
    if segment_paths is None:
        segment_paths = _default_segment_paths()
    segment_paths = [Path(p) for p in segment_paths]

    if platform_filter is not None:
        segment_paths = [p for p in segment_paths if _platform_from_path(p) == platform_filter]

    overall = _empty_acc()
    per_platform: dict[str, dict] = {}
    per_regime = _empty_regime_acc()
    failed = 0

    for p in segment_paths:
        platform = _platform_from_path(p)
        try:
            sim_df = pd.read_csv(p)
        except Exception:
            failed += 1
            continue

        # Required truth column.
        if "yaw_rate_meas_rads" not in sim_df.columns or "v_mps" not in sim_df.columns or "t_s" not in sim_df.columns:
            failed += 1
            continue

        # Run the model.
        try:
            pred_df = predict_fn(sim_df, platform)
        except Exception:
            failed += 1
            continue

        if (
            not isinstance(pred_df, pd.DataFrame)
            or "yaw_rate_pred_rads" not in pred_df.columns
            or len(pred_df) != len(sim_df)
        ):
            failed += 1
            continue

        t = sim_df["t_s"].to_numpy(dtype=float)
        v = sim_df["v_mps"].to_numpy(dtype=float)
        yr_truth = sim_df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        yr_pred = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float)

        if len(t) < 2 or np.any(np.diff(t) <= 0):
            failed += 1
            continue

        # ---- Yaw-rate RMSE (sample-pooled, v-filtered) ----
        mask_v = v > sample_filter_v_mps
        resid = yr_pred - yr_truth
        sample_sq = resid[mask_v] ** 2
        yr_sum_sq = float(np.sum(sample_sq))
        yr_n = int(mask_v.sum())

        # ---- CTE RMSE (segment-then-bin pooled) ----
        sum_sq, n_bins, _total = cte_rmse_segment(
            t, v, yr_truth, yr_pred,
            grid_step_m=grid_step_m,
            min_distance_m=min_distance_m,
        )

        # ---- Regime split (only yaw-rate RMSE) ----
        if "delta_road_rad" in sim_df.columns:
            delta_road = sim_df["delta_road_rad"].to_numpy(dtype=float)
            regime_masks = _regime_mask(delta_road, t)
        else:
            # No regime info — count everything as transient by convention.
            regime_masks = {
                "straight": np.zeros_like(v, dtype=bool),
                "steady": np.zeros_like(v, dtype=bool),
                "transient": np.ones_like(v, dtype=bool),
            }

        # ---- Accumulate overall ----
        overall["yr_sum_sq"] += yr_sum_sq
        overall["yr_n"] += yr_n
        overall["cte_sum_sq"] += sum_sq
        overall["cte_n_bins"] += n_bins
        overall["n_segments"] += 1

        # ---- Accumulate per-platform ----
        if platform not in per_platform:
            per_platform[platform] = _empty_acc()
        pp = per_platform[platform]
        pp["yr_sum_sq"] += yr_sum_sq
        pp["yr_n"] += yr_n
        pp["cte_sum_sq"] += sum_sq
        pp["cte_n_bins"] += n_bins
        pp["n_segments"] += 1

        # ---- Accumulate per-regime (v-filtered, like the headline yaw-rate RMSE) ----
        for regime, rmask in regime_masks.items():
            combined = rmask & mask_v
            if combined.any():
                per_regime[regime]["yr_sum_sq"] += float(np.sum(resid[combined] ** 2))
                per_regime[regime]["yr_n"] += int(combined.sum())

    out = _finalize(overall)
    out["per_platform"] = {k: _finalize(v) for k, v in per_platform.items()}
    out["per_regime"] = _finalize_regime(per_regime)
    out["failed_segments"] = failed
    return out


# Re-export for convenience.
__all__ = ["score", "integrate_trajectory"]
