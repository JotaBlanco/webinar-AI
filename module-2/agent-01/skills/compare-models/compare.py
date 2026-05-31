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
    """Pull the platform token out of a path like data/sim-full/<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv."""
    parts = segment_path.resolve().parts
    try:
        i = parts.index("segments")
        return parts[i + 1]
    except (ValueError, IndexError):
        # Fallback — best-effort guess if path doesn't follow the convention.
        return segment_path.parents[3].name if len(segment_path.parents) >= 4 else "UNKNOWN"


def _default_segment_paths() -> list[Path]:
    """All FORD_* sim.csv files under the working dir's data/ tree."""
    root = Path.cwd() / "data" / "sim-full"
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


# ---------- ranked views & summary helpers ----------

def top_regressions(df: pd.DataFrame, metric: str = "cte_delta", n: int = 10) -> pd.DataFrame:
    """Segments where B is *worse* than A on the given delta metric.

    `metric` should be a `*_delta` column (B - A; positive = B worse). Returns
    the top-`n` rows by largest positive delta. NaN deltas are dropped.
    """
    if metric not in df.columns:
        raise KeyError(f"{metric!r} not in DataFrame; have: {list(df.columns)}")
    return df.dropna(subset=[metric]).nlargest(n, metric).reset_index(drop=True)


def top_improvements(df: pd.DataFrame, metric: str = "cte_delta", n: int = 10) -> pd.DataFrame:
    """Segments where B is *better* than A. Top-`n` rows by most negative delta."""
    if metric not in df.columns:
        raise KeyError(f"{metric!r} not in DataFrame; have: {list(df.columns)}")
    return df.dropna(subset=[metric]).nsmallest(n, metric).reset_index(drop=True)


def per_platform_summary(df: pd.DataFrame, name_a: str = "A", name_b: str = "B") -> pd.DataFrame:
    """Per-platform pooled view: mean yaw and CTE for A and B + mean delta."""
    if df.empty:
        return pd.DataFrame()
    yaw_a = f"yaw_rate_rmse_{name_a}"
    yaw_b = f"yaw_rate_rmse_{name_b}"
    cte_a = f"cte_rmse_{name_a}"
    cte_b = f"cte_rmse_{name_b}"
    rows = []
    for plat, sub in df.groupby("platform"):
        rows.append({
            "platform":            plat,
            "n_segments":          int(len(sub)),
            f"yaw_mean_{name_a}":  float(sub[yaw_a].mean(skipna=True)),
            f"yaw_mean_{name_b}":  float(sub[yaw_b].mean(skipna=True)),
            "yaw_delta_mean":      float(sub["yaw_rate_delta"].mean(skipna=True)),
            "yaw_b_wins_frac":     float((sub["yaw_rate_delta"] < 0).mean()),
            f"cte_mean_{name_a}":  float(sub[cte_a].mean(skipna=True)),
            f"cte_mean_{name_b}":  float(sub[cte_b].mean(skipna=True)),
            "cte_delta_mean":      float(sub["cte_delta"].mean(skipna=True)),
            "cte_b_wins_frac":     float((sub["cte_delta"] < 0).mean(skipna=True)),
        })
    return pd.DataFrame(rows)


def format_summary(df: pd.DataFrame, name_a: str = "A", name_b: str = "B", top_n: int = 5) -> str:
    """Render a markdown dashboard — overall win/loss counts, per-platform
    summary, top regressions, top improvements. Print this to your console."""
    if df.empty:
        return "compare-models: no segments compared."

    n = len(df)
    yaw_b_wins = int((df["yaw_rate_delta"] < 0).sum())
    cte_b_wins = int((df["cte_delta"] < 0).sum())
    cte_valid  = int(df["cte_delta"].notna().sum())

    L = []
    L.append(f"## compare-models — `{name_a}` vs `{name_b}`")
    L.append(f"- segments compared: {n}")
    L.append(f"- **yaw**: `{name_b}` wins {yaw_b_wins}/{n} segments (mean delta = {df['yaw_rate_delta'].mean():+.5f} rad/s)")
    L.append(f"- **CTE**: `{name_b}` wins {cte_b_wins}/{cte_valid} segments (mean delta = {df['cte_delta'].mean(skipna=True):+.3f} m)")
    L.append("")
    L.append("### per platform")
    pp = per_platform_summary(df, name_a, name_b)
    if not pp.empty:
        yaw_a = f"yaw_mean_{name_a}"
        yaw_b = f"yaw_mean_{name_b}"
        cte_a = f"cte_mean_{name_a}"
        cte_b = f"cte_mean_{name_b}"
        L.append(f"| platform | n | yaw {name_a} | yaw {name_b} | yaw Δ | B wins yaw | cte {name_a} | cte {name_b} | cte Δ | B wins cte |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        for _, r in pp.iterrows():
            L.append(f"| `{r['platform']}` | {r['n_segments']} | {r[yaw_a]:.5f} | {r[yaw_b]:.5f} | {r['yaw_delta_mean']:+.5f} | {r['yaw_b_wins_frac']:.0%} | {r[cte_a]:.2f} | {r[cte_b]:.2f} | {r['cte_delta_mean']:+.2f} | {r['cte_b_wins_frac']:.0%} |")
    L.append("")
    L.append(f"### top {top_n} CTE regressions (B worse than A)")
    tr = top_regressions(df, "cte_delta", top_n)
    L.append("| segment | platform | cte_delta | yaw_delta |")
    L.append("|---|---|---|---|")
    for _, r in tr.iterrows():
        seg = Path(r["segment_path"]).parent.name
        route = Path(r["segment_path"]).parents[1].name
        L.append(f"| `{route}/{seg}` | `{r['platform']}` | {r['cte_delta']:+.2f} | {r['yaw_rate_delta']:+.5f} |")
    L.append("")
    L.append(f"### top {top_n} CTE improvements (B better than A)")
    ti = top_improvements(df, "cte_delta", top_n)
    L.append("| segment | platform | cte_delta | yaw_delta |")
    L.append("|---|---|---|---|")
    for _, r in ti.iterrows():
        seg = Path(r["segment_path"]).parent.name
        route = Path(r["segment_path"]).parents[1].name
        L.append(f"| `{route}/{seg}` | `{r['platform']}` | {r['cte_delta']:+.2f} | {r['yaw_rate_delta']:+.5f} |")
    return "\n".join(L)


__all__ = [
    "compare",
    "top_regressions",
    "top_improvements",
    "per_platform_summary",
    "format_summary",
    "integrate_trajectory",
]
