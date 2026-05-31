"""Score any predict callable against a list of segment sim.csv files.

Returns the two pooled KPIs plus a rich per-segment table, per-platform
residual stats (signed bias, std, bias fraction), per-route pooling, worst-N
tables, and full distribution stats. All views read off the SAME pass over
the segments — there is no separate "deep" mode.

CTE math is imported from `_shared/traj_metrics.py`.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from traj_metrics import cte_diagnostics_segment, integrate_trajectory  # noqa: E402


# ---------------------------------------------------------------------------
# Operating contract — must match the canonical grader's allowlist.
#
# Your predict(sim_df, platform) function will be called by the canonical
# grader with a sim_df that has been stripped to ONLY these columns. The
# truth channel (yaw_rate_meas_rads), its kinematic shadow (a_lat_meas_mps2),
# residuals, and simulator state are NOT visible at scoring time.
#
# This local score-model enforces the same allowlist so your local RMSE
# reflects what the canonical grader will see. If you accidentally read a
# stripped column, your predict will fail here too — caught in dev, not in
# grading.
# ---------------------------------------------------------------------------
ALLOWED_INPUT_COLUMNS = frozenset({
    "t_s",
    "delta_wheel_deg",
    "delta_road_rad",
    "v_mps",
    "a_long_mps2",
    "accel_pedal_pct",
    "brake_pressed",
    "yaw_rate_pred_rads",   # V0 baseline reference — the column your predict REPLACES
})


# ---------------------------------------------------------------------------
# Path helpers — data/sim-full/<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv
# ---------------------------------------------------------------------------

def _platform_from_path(p: Path) -> str:
    return p.resolve().parents[3].name


def _route_from_path(p: Path) -> str:
    return p.resolve().parents[1].name


def _idx_from_path(p: Path) -> str:
    return p.resolve().parents[0].name


def _default_segment_paths() -> list[Path]:
    root = Path.cwd() / "data" / "sim-full"
    if not root.exists():
        return []
    return sorted(root.glob("FORD_*/**/sim.csv"))


# ---------------------------------------------------------------------------
# Regime classification (per row, yaw-rate diagnostic only)
# ---------------------------------------------------------------------------

def _regime_mask(delta_road: np.ndarray, t: np.ndarray) -> dict[str, np.ndarray]:
    straight = np.abs(delta_road) < 0.01
    if len(t) >= 2:
        ddelta_dt = np.gradient(delta_road, t)
    else:
        ddelta_dt = np.zeros_like(delta_road)
    steady = (~straight) & (np.abs(ddelta_dt) < 0.05)
    transient = (~straight) & (~steady)
    return {"straight": straight, "steady": steady, "transient": transient}


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
    top_n: int = 10,
) -> dict:
    """Score a predict callable across segments.

    Args:
        predict_fn: callable(sim_df, platform) -> DataFrame aligned with sim_df.index,
            must contain ``yaw_rate_pred_rads``.
        segment_paths: list of sim.csv paths. If None, glob all
            ``data/sim-full/FORD_*/**/sim.csv`` under cwd.
        platform_filter: if set, keep only that platform.
        grid_step_m, min_distance_m: CTE bin spacing and minimum segment length.
        sample_filter_v_mps: yaw-rate RMSE pools rows where ``v_mps`` exceeds this.
        top_n: how many worst-segments to include in the ranked outlier tables.

    Returns:
        See SKILL.md for the full key inventory. Headline keys are
        ``yaw_rate_rmse`` and ``cte_rmse``; everything else is diagnostic.
    """
    if segment_paths is None:
        segment_paths = _default_segment_paths()
    segment_paths = [Path(p) for p in segment_paths]
    if platform_filter is not None:
        segment_paths = [p for p in segment_paths if _platform_from_path(p) == platform_filter]

    # Per-segment records — one dict per segment that passed.
    rows: list[dict] = []
    # Pooled regime accumulators (yaw rate only).
    regime_acc = {
        k: {"sum_sq": 0.0, "sum_signed": 0.0, "n": 0}
        for k in ("straight", "steady", "transient")
    }
    failed = 0

    for p in segment_paths:
        platform = _platform_from_path(p)
        try:
            sim_df = pd.read_csv(p)
        except Exception:
            failed += 1
            continue

        for col in ("yaw_rate_meas_rads", "v_mps", "t_s"):
            if col not in sim_df.columns:
                failed += 1
                break
        else:
            # Strip to operating-contract allowlist before handing to the agent's predict.
            # Mirrors what the canonical grader does — local scores match canonical scores.
            sim_df_agent = sim_df[[c for c in sim_df.columns if c in ALLOWED_INPUT_COLUMNS]]
            try:
                pred_df = predict_fn(sim_df_agent, platform)
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

            t        = sim_df["t_s"].to_numpy(dtype=float)
            v        = sim_df["v_mps"].to_numpy(dtype=float)
            yr_truth = sim_df["yaw_rate_meas_rads"].to_numpy(dtype=float)
            yr_pred  = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float)

            if len(t) < 2 or np.any(np.diff(t) <= 0):
                failed += 1
                continue

            # ---- Yaw-rate residual (v-filtered) ----
            mask_v = v > sample_filter_v_mps
            resid = yr_pred - yr_truth
            r_v = resid[mask_v]
            yr_n = int(mask_v.sum())
            yr_sum_sq     = float(np.sum(r_v ** 2))
            yr_sum_signed = float(np.sum(r_v))
            yr_rmse       = math.sqrt(yr_sum_sq / yr_n) if yr_n > 0 else float("nan")
            yr_mean       = yr_sum_signed / yr_n if yr_n > 0 else float("nan")
            yr_std        = float(np.sqrt(max(yr_sum_sq / yr_n - yr_mean ** 2, 0.0))) if yr_n > 0 else float("nan")

            # ---- CTE diagnostics ----
            cte = cte_diagnostics_segment(
                t, v, yr_truth, yr_pred,
                grid_step_m=grid_step_m,
                min_distance_m=min_distance_m,
            )
            cte_rmse        = math.sqrt(cte["sum_sq_m2"] / cte["n_bins"]) if cte["n_bins"] > 0 else float("nan")
            cte_signed_mean = cte["sum_signed_m"] / cte["n_bins"] if cte["n_bins"] > 0 else float("nan")
            cte_abs_mean    = cte["sum_abs_m"]    / cte["n_bins"] if cte["n_bins"] > 0 else float("nan")

            rows.append({
                "segment_path":      str(p),
                "platform":          platform,
                "route":             _route_from_path(p),
                "idx":               _idx_from_path(p),
                "n_samples":         yr_n,
                "distance_m":        cte["total_distance_m"],
                "end_drift_m":       cte["end_drift_m"],
                "yaw_rate_rmse":     yr_rmse,
                "yaw_residual_mean": yr_mean,
                "yaw_residual_std":  yr_std,
                "yaw_sum_sq":        yr_sum_sq,
                "yaw_sum_signed":    yr_sum_signed,
                "cte_rmse":          cte_rmse,
                "cte_signed_mean":   cte_signed_mean,
                "cte_abs_mean":      cte_abs_mean,
                "cte_sum_sq":        cte["sum_sq_m2"],
                "cte_sum_signed":    cte["sum_signed_m"],
                "cte_n_bins":        cte["n_bins"],
            })

            # ---- Regime split (yaw rate only) ----
            if "delta_road_rad" in sim_df.columns:
                regime_masks = _regime_mask(sim_df["delta_road_rad"].to_numpy(dtype=float), t)
            else:
                regime_masks = {
                    "straight": np.zeros_like(v, dtype=bool),
                    "steady":   np.zeros_like(v, dtype=bool),
                    "transient": np.ones_like(v, dtype=bool),
                }
            for regime, rmask in regime_masks.items():
                combined = rmask & mask_v
                if combined.any():
                    rr = resid[combined]
                    regime_acc[regime]["sum_sq"]     += float(np.sum(rr ** 2))
                    regime_acc[regime]["sum_signed"] += float(np.sum(rr))
                    regime_acc[regime]["n"]          += int(combined.sum())

    # Empty case: nothing scored.
    if not rows:
        return _empty_result(failed)

    seg = pd.DataFrame(rows)

    # ---- Overall pooled ----
    overall_yaw_rmse = math.sqrt(seg["yaw_sum_sq"].sum() / seg["n_samples"].sum())
    overall_cte_rmse = math.sqrt(seg["cte_sum_sq"].sum() / seg["cte_n_bins"].sum()) if seg["cte_n_bins"].sum() > 0 else float("nan")

    # ---- Per-platform pooled (re-derive from per-segment sums) ----
    per_platform = {}
    for platform, sub in seg.groupby("platform"):
        n      = int(sub["n_samples"].sum())
        n_bins = int(sub["cte_n_bins"].sum())
        yaw_mean = float(sub["yaw_sum_signed"].sum() / n) if n > 0 else float("nan")
        yaw_var  = float(sub["yaw_sum_sq"].sum() / n - yaw_mean ** 2) if n > 0 else float("nan")
        yaw_var  = max(yaw_var, 0.0)
        yaw_rmse = math.sqrt(sub["yaw_sum_sq"].sum() / n) if n > 0 else float("nan")
        yaw_bias_fraction = (yaw_mean ** 2) / (yaw_mean ** 2 + yaw_var) if (yaw_mean ** 2 + yaw_var) > 0 else float("nan")
        per_platform[platform] = {
            "yaw_rate_rmse":     yaw_rmse,
            "yaw_residual_mean": yaw_mean,
            "yaw_residual_std":  math.sqrt(yaw_var),
            "yaw_bias_fraction": yaw_bias_fraction,
            "cte_rmse":          math.sqrt(sub["cte_sum_sq"].sum() / n_bins) if n_bins > 0 else float("nan"),
            "cte_signed_mean":   float(sub["cte_sum_signed"].sum() / n_bins) if n_bins > 0 else float("nan"),
            "n_segments":        int(len(sub)),
            "n_samples":         n,
        }

    # ---- Per-regime ----
    per_regime = {}
    for k, acc in regime_acc.items():
        n = acc["n"]
        if n > 0:
            mean = acc["sum_signed"] / n
            per_regime[k] = {
                "yaw_rate_rmse":     math.sqrt(acc["sum_sq"] / n),
                "yaw_residual_mean": mean,
                "n_samples":         n,
            }
        else:
            per_regime[k] = {"yaw_rate_rmse": float("nan"), "yaw_residual_mean": float("nan"), "n_samples": 0}

    # ---- Per-route pooled ----
    route_rows = []
    for (platform, route), sub in seg.groupby(["platform", "route"]):
        n      = int(sub["n_samples"].sum())
        n_bins = int(sub["cte_n_bins"].sum())
        route_rows.append({
            "platform":         platform,
            "route":            route,
            "n_segments":       int(len(sub)),
            "total_distance_m": float(sub["distance_m"].sum()),
            "yaw_rate_rmse":    math.sqrt(sub["yaw_sum_sq"].sum() / n) if n > 0 else float("nan"),
            "cte_rmse":         math.sqrt(sub["cte_sum_sq"].sum() / n_bins) if n_bins > 0 else float("nan"),
            "cte_signed_mean":  float(sub["cte_sum_signed"].sum() / n_bins) if n_bins > 0 else float("nan"),
        })
    per_route = pd.DataFrame(route_rows).sort_values("cte_rmse", ascending=False).reset_index(drop=True)

    # ---- Worst-N tables (drop the internal sum columns from the view) ----
    view_cols = [
        "segment_path", "platform", "route", "idx", "n_samples", "distance_m",
        "yaw_rate_rmse", "yaw_residual_mean", "yaw_residual_std",
        "cte_rmse", "cte_signed_mean", "cte_abs_mean", "end_drift_m",
    ]
    worst_cte = seg.nlargest(top_n, "cte_rmse")[view_cols].to_dict("records")
    worst_yaw = seg.nlargest(top_n, "yaw_rate_rmse")[view_cols].to_dict("records")

    # ---- Distribution stats ----
    yaw_dist = _describe(seg["yaw_rate_rmse"])
    cte_dist = _describe(seg["cte_rmse"])

    # Drop internal cumulative columns from the public per_segment view.
    per_segment_public = seg[view_cols].copy()

    return {
        "yaw_rate_rmse":           overall_yaw_rmse,
        "cte_rmse":                overall_cte_rmse,
        "n_segments":              int(len(seg)),
        "n_samples":               int(seg["n_samples"].sum()),
        "failed_segments":         failed,
        "per_platform":            per_platform,
        "per_regime":              per_regime,
        "per_segment":             per_segment_public,
        "per_route":               per_route,
        "worst_segments_by_cte":   worst_cte,
        "worst_segments_by_yaw":   worst_yaw,
        "yaw_rmse_distribution":   yaw_dist,
        "cte_rmse_distribution":   cte_dist,
    }


# ---------------------------------------------------------------------------
# Display helper — one-shot dashboard the agent can print
# ---------------------------------------------------------------------------

def format_summary(result: dict, top_n: int = 5) -> str:
    """Render a markdown dashboard of every view in `result`. Print this."""
    if result["n_segments"] == 0:
        return f"score-model: no segments scored ({result['failed_segments']} failed)."

    L = []
    L.append("## score-model summary")
    L.append(f"- n_segments: {result['n_segments']} (failed: {result['failed_segments']}), n_samples: {result['n_samples']:,}")
    L.append(f"- **yaw_rate_rmse**: {result['yaw_rate_rmse']:.6f} rad/s")
    L.append(f"- **cte_rmse**: {result['cte_rmse']:.4f} m")
    L.append("")
    L.append("### per platform")
    L.append("| platform | yaw_rmse | yaw_bias | yaw_std | bias_frac | cte_rmse | cte_signed_mean | n_seg |")
    L.append("|---|---|---|---|---|---|---|---|")
    for plat, m in result["per_platform"].items():
        L.append(f"| `{plat}` | {m['yaw_rate_rmse']:.5f} | {m['yaw_residual_mean']:+.5f} | {m['yaw_residual_std']:.5f} | {m['yaw_bias_fraction']:.2f} | {m['cte_rmse']:.3f} | {m['cte_signed_mean']:+.3f} | {m['n_segments']} |")
    L.append("")
    L.append("### per regime (yaw only)")
    for k, m in result["per_regime"].items():
        L.append(f"- `{k}`: rmse={m['yaw_rate_rmse']:.5f}, bias={m['yaw_residual_mean']:+.5f}, n={m['n_samples']:,}")
    L.append("")
    L.append("### per-segment distribution")
    for label, dist in (("yaw_rate_rmse", result["yaw_rmse_distribution"]),
                        ("cte_rmse",      result["cte_rmse_distribution"])):
        L.append(f"- **{label}**: min={dist['min']:.5g}, p25={dist['p25']:.5g}, median={dist['median']:.5g}, mean={dist['mean']:.5g}, p75={dist['p75']:.5g}, max={dist['max']:.5g}, std={dist['std']:.5g}")
    L.append("")
    L.append(f"### top {top_n} worst segments by CTE")
    L.append("| route/idx | platform | dist_m | cte_rmse | cte_signed | yaw_rmse |")
    L.append("|---|---|---|---|---|---|")
    for r in result["worst_segments_by_cte"][:top_n]:
        L.append(f"| `{r['route']}/{r['idx']}` | `{r['platform']}` | {r['distance_m']:.0f} | {r['cte_rmse']:.2f} | {r['cte_signed_mean']:+.2f} | {r['yaw_rate_rmse']:.5f} |")
    L.append("")
    L.append(f"### top {top_n} worst segments by yaw")
    L.append("| route/idx | platform | n_samp | yaw_rmse | yaw_bias |")
    L.append("|---|---|---|---|---|")
    for r in result["worst_segments_by_yaw"][:top_n]:
        L.append(f"| `{r['route']}/{r['idx']}` | `{r['platform']}` | {r['n_samples']} | {r['yaw_rate_rmse']:.5f} | {r['yaw_residual_mean']:+.5f} |")
    L.append("")
    L.append(f"### top {min(top_n, len(result['per_route']))} routes by CTE")
    L.append("| route | platform | n_seg | dist_m | yaw_rmse | cte_rmse | cte_signed |")
    L.append("|---|---|---|---|---|---|---|")
    for _, r in result["per_route"].head(top_n).iterrows():
        L.append(f"| `{r['route']}` | `{r['platform']}` | {r['n_segments']} | {r['total_distance_m']:.0f} | {r['yaw_rate_rmse']:.5f} | {r['cte_rmse']:.3f} | {r['cte_signed_mean']:+.3f} |")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _describe(s: pd.Series) -> dict:
    s = s.dropna()
    if len(s) == 0:
        return {"count": 0, "min": float("nan"), "p25": float("nan"), "median": float("nan"),
                "mean": float("nan"), "p75": float("nan"), "max": float("nan"), "std": float("nan")}
    return {
        "count":  int(len(s)),
        "min":    float(s.min()),
        "p25":    float(s.quantile(0.25)),
        "median": float(s.median()),
        "mean":   float(s.mean()),
        "p75":    float(s.quantile(0.75)),
        "max":    float(s.max()),
        "std":    float(s.std(ddof=0)),
    }


def _empty_result(failed: int) -> dict:
    return {
        "yaw_rate_rmse": float("nan"),
        "cte_rmse": float("nan"),
        "n_segments": 0,
        "n_samples": 0,
        "failed_segments": failed,
        "per_platform": {},
        "per_regime": {},
        "per_segment": pd.DataFrame(),
        "per_route": pd.DataFrame(),
        "worst_segments_by_cte": [],
        "worst_segments_by_yaw": [],
        "yaw_rmse_distribution": _describe(pd.Series(dtype=float)),
        "cte_rmse_distribution": _describe(pd.Series(dtype=float)),
    }


__all__ = ["score", "format_summary", "integrate_trajectory"]
