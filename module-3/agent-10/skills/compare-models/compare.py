"""compare-models — diff two predict callables segment-by-segment.

Exports `compare(predict_fn_a, predict_fn_b, ...)` returning a per-segment
DataFrame of yaw-rate RMSE, distance-resampled cross-track RMSE, deltas, and
regime fractions. See SKILL.md for the full contract.
"""

from __future__ import annotations

import math
import sys
import warnings
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd

# Import shared trajectory helpers from the template root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from traj_metrics import cte_rmse_segment, integrate_trajectory  # noqa: E402


PredictFn = Callable[[pd.DataFrame, str], pd.DataFrame]


# ---------- helpers ----------

def _infer_platform(segment_path: Path) -> str:
    """Pull the platform token out of a path like data/sim/segments/<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv."""
    parts = segment_path.resolve().parts
    try:
        i = parts.index("segments")
        return parts[i + 1]
    except (ValueError, IndexError):
        # Fallback — best-effort guess if path doesn't follow the convention.
        return segment_path.parents[3].name if len(segment_path.parents) >= 4 else "UNKNOWN"


def _default_segment_paths() -> list[Path]:
    """All FORD_* sim.csv files under the working dir's data/ tree."""
    root = Path.cwd() / "data" / "sim" / "segments"
    if not root.exists():
        return []
    return sorted(root.glob("FORD_*/**/sim.csv"))


def _regime_fractions(sim_df: pd.DataFrame) -> tuple[float, float, float]:
    """Classify each row and return (frac_straight, frac_steady, frac_transient).

    - straight:  |delta_road_rad| < 0.01
    - steady:    not straight AND |d(delta_road_rad)/dt| < 0.05 rad/s
    - transient: otherwise
    """
    n = len(sim_df)
    if n == 0:
        return float("nan"), float("nan"), float("nan")

    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    straight_mask = np.abs(delta) < 0.01

    # d(delta)/dt — forward difference, pad last sample.
    if n >= 2:
        dt = np.diff(t)
        # Avoid div-by-zero on degenerate timestamps; treat as zero rate.
        with np.errstate(divide="ignore", invalid="ignore"):
            ddelta_dt = np.where(dt > 0, np.diff(delta) / dt, 0.0)
        ddelta_dt = np.concatenate([ddelta_dt, [ddelta_dt[-1]]])
    else:
        ddelta_dt = np.zeros(n)

    steady_mask = (~straight_mask) & (np.abs(ddelta_dt) < 0.05)
    transient_mask = ~(straight_mask | steady_mask)

    return (
        float(straight_mask.mean()),
        float(steady_mask.mean()),
        float(transient_mask.mean()),
    )


def _yaw_rate_rmse(yr_truth: np.ndarray, yr_pred: np.ndarray, mask: np.ndarray) -> float:
    if mask.sum() == 0:
        return float("nan")
    e = yr_pred[mask] - yr_truth[mask]
    return float(np.sqrt(np.mean(e * e)))


def _segment_cte_rmse(
    sim_df: pd.DataFrame,
    pred_df: pd.DataFrame,
    grid_step_m: float,
    min_distance_m: float,
) -> float:
    """Per-segment CTE RMSE in meters. NaN if the segment is below min_distance_m."""
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    yr_truth = sim_df["yaw_rate_meas_rads"].to_numpy(dtype=float)
    yr_pred = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float)

    sum_sq, n_bins, _total = cte_rmse_segment(
        t, v, yr_truth, yr_pred,
        grid_step_m=grid_step_m,
        min_distance_m=min_distance_m,
    )
    if n_bins <= 0:
        return float("nan")
    return math.sqrt(sum_sq / n_bins)


def _run_predictor(
    fn: PredictFn,
    sim_df: pd.DataFrame,
    platform: str,
    label: str,
    segment_path: Path,
) -> pd.DataFrame | None:
    """Call the predictor and validate its output. Returns None on failure."""
    try:
        out = fn(sim_df.copy(), platform)
    except Exception as exc:
        warnings.warn(f"compare-models: predictor {label!r} raised on {segment_path}: {exc}")
        return None

    if not isinstance(out, pd.DataFrame):
        warnings.warn(f"compare-models: predictor {label!r} returned non-DataFrame on {segment_path}.")
        return None
    if "yaw_rate_pred_rads" not in out.columns:
        warnings.warn(f"compare-models: predictor {label!r} missing 'yaw_rate_pred_rads' on {segment_path}.")
        return None
    if len(out) != len(sim_df):
        warnings.warn(
            f"compare-models: predictor {label!r} length mismatch on {segment_path} "
            f"(got {len(out)}, expected {len(sim_df)})."
        )
        return None
    return out


# ---------- main entry point ----------

def compare(
    predict_fn_a: PredictFn,
    predict_fn_b: PredictFn,
    segment_paths: Iterable[Path] | None = None,
    name_a: str = "A",
    name_b: str = "B",
    grid_step_m: float = 1.0,
    min_distance_m: float = 20.0,
    sample_filter_v_mps: float = 2.0,
) -> pd.DataFrame:
    """Diff two predictors segment-by-segment.

    See SKILL.md for the contract. Returns a DataFrame with one row per
    segment, sorted by `segment_path`. Segments on which either predictor
    fails are excluded (with a printed warning). The CTE columns are NaN for
    segments shorter than `min_distance_m`; the delta is NaN in that case too.
    """
    if name_a == name_b:
        raise ValueError(f"name_a and name_b must differ (both were {name_a!r}).")

    if segment_paths is None:
        paths = _default_segment_paths()
    else:
        paths = [Path(p) for p in segment_paths]

    if not paths:
        return pd.DataFrame(
            columns=[
                "segment_path", "platform", "n_samples",
                f"yaw_rate_rmse_{name_a}", f"yaw_rate_rmse_{name_b}", "yaw_rate_delta",
                f"cte_rmse_{name_a}", f"cte_rmse_{name_b}", "cte_delta",
                "frac_straight", "frac_steady", "frac_transient",
            ]
        )

    rows = []
    for p in sorted(paths, key=lambda q: str(q)):
        try:
            sim_df = pd.read_csv(p)
        except Exception as exc:
            warnings.warn(f"compare-models: could not read {p}: {exc}")
            continue

        required = {"t_s", "v_mps", "delta_road_rad", "yaw_rate_meas_rads"}
        missing = required - set(sim_df.columns)
        if missing:
            warnings.warn(f"compare-models: {p} missing columns {sorted(missing)}; skipping.")
            continue

        platform = _infer_platform(p)

        pred_a = _run_predictor(predict_fn_a, sim_df, platform, name_a, p)
        pred_b = _run_predictor(predict_fn_b, sim_df, platform, name_b, p)
        if pred_a is None or pred_b is None:
            # Either side broke — surface the segment-drop and move on.
            continue

        v = sim_df["v_mps"].to_numpy(dtype=float)
        yr_truth = sim_df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        sample_mask = v >= sample_filter_v_mps
        n_samples = int(sample_mask.sum())

        yr_rmse_a = _yaw_rate_rmse(yr_truth, pred_a["yaw_rate_pred_rads"].to_numpy(dtype=float), sample_mask)
        yr_rmse_b = _yaw_rate_rmse(yr_truth, pred_b["yaw_rate_pred_rads"].to_numpy(dtype=float), sample_mask)

        cte_a = _segment_cte_rmse(sim_df, pred_a, grid_step_m, min_distance_m)
        cte_b = _segment_cte_rmse(sim_df, pred_b, grid_step_m, min_distance_m)

        cte_delta = (cte_b - cte_a) if (not math.isnan(cte_a) and not math.isnan(cte_b)) else float("nan")

        frac_straight, frac_steady, frac_transient = _regime_fractions(sim_df)

        rows.append({
            "segment_path": str(p),
            "platform": platform,
            "n_samples": n_samples,
            f"yaw_rate_rmse_{name_a}": yr_rmse_a,
            f"yaw_rate_rmse_{name_b}": yr_rmse_b,
            "yaw_rate_delta": yr_rmse_b - yr_rmse_a,
            f"cte_rmse_{name_a}": cte_a,
            f"cte_rmse_{name_b}": cte_b,
            "cte_delta": cte_delta,
            "frac_straight": frac_straight,
            "frac_steady": frac_steady,
            "frac_transient": frac_transient,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("segment_path").reset_index(drop=True)
    return df


# Silence the noqa on the helpers we import only for re-use by callers.
__all__ = ["compare", "integrate_trajectory"]
