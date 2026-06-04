"""route-bias — diagnose per-route systematic bias that the per-platform fit
cannot capture.

`scoring-model.per_route` already exposes per-route signed CTE drift, but it
buries the signal inside a wider table. The v2 cohort kept hitting the same
wall: Hyundai's residual CTE drift was dominated by a handful of routes with
consistent sign, and the per-platform fit had no way to reach it because the
coefficients were averaging the routes together.

This skill ranks routes by *contribution to the platform's pooled error* —
not just by their own RMSE — so the agent can see which routes are the
biggest opportunity. It also computes mean values of a chosen list of input
features per route, so the agent can correlate the bias against an
observable feature and add a feature-conditional term to their model.

**Diagnostic, not corrective.** Route id is NOT available at inference time
(the canonical grader hands `predict(sim_df, platform)` and nothing else),
so the per-route bias *cannot* be applied directly as a lookup. To exploit
this, find an INPUT FEATURE that correlates with the flagged routes
(typical candidates: mean speed, mean |delta_road|, mean a_long, segment
distance) and add a term to your model that depends on that feature.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Reuse the schema + allowlist + V0 baseline alias from scoring-model.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "score-model"))
from score import (  # noqa: E402
    ALLOWED_INPUT_COLUMNS,
    DEFAULT_SCHEMA,
    PLATFORM_SCHEMA,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa: E402


# Thresholds for the "look here" recommendation column.
ROUTE_YAW_BIAS_WARN_RAD_S = 0.0015
ROUTE_CTE_DRIFT_WARN_M    = 5.0


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _platform_from_path(p: Path) -> str:
    return p.resolve().parents[3].name


def _route_from_path(p: Path) -> str:
    return p.resolve().parents[1].name


def _default_segment_paths() -> list[Path]:
    root = Path.cwd() / "data" / "sim" / "segments"
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())


def _resolve_schema(platform: str) -> dict:
    return PLATFORM_SCHEMA.get(platform, DEFAULT_SCHEMA)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def route_bias(
    predict_fn,
    segment_paths: list | None = None,
    platform_filter: str | None = None,
    sample_filter_v_mps: float = 2.0,
    grid_step_m: float = 1.0,
    min_distance_m: float = 20.0,
    feature_means: list[str] | None = None,
    top_n: int = 15,
) -> dict:
    """Compute per-route signed yaw bias and signed CTE drift for `predict_fn`.

    Args:
        predict_fn: callable(sim_df, platform) -> DataFrame with `yaw_rate_pred_rads`.
        segment_paths: list[Path] or None (default — ALL platforms).
        platform_filter: keep only this platform if set.
        sample_filter_v_mps, grid_step_m, min_distance_m: match scoring-model.
        feature_means: list of input column names to also average per route, so
            you can look for an observable feature that correlates with the
            flagged routes. Default: ["v_mps", "delta_road_rad", "a_long_mps2"].
            Resolved from the agent-view sim_df.
        top_n: how many routes per platform to include in the ranked tables.

    Returns:
        dict — per_route (DataFrame: platform, route, n_segments, distance_m,
        yaw_residual_mean, cte_signed_mean, share_of_platform_yaw_sum_sq,
        share_of_platform_cte_sum_sq, plus one column per feature in
        `feature_means`), per_platform_summary, top_routes_by_cte,
        top_routes_by_yaw_bias, recommendations, failed_segments.
    """
    if feature_means is None:
        feature_means = ["v_mps", "delta_road_rad", "a_long_mps2"]

    if segment_paths is None:
        segment_paths = _default_segment_paths()
    paths = [Path(p) for p in segment_paths]
    if platform_filter is not None:
        paths = [p for p in paths if _platform_from_path(p) == platform_filter]

    rows: list[dict] = []
    failed = 0

    for p in paths:
        platform = _platform_from_path(p)
        schema = _resolve_schema(platform)
        truth_col = schema["truth_col"]
        base_col  = schema["baseline_col"]

        try:
            sim_df = pd.read_csv(p)
        except Exception:
            failed += 1; continue

        if any(c not in sim_df.columns for c in (truth_col, "v_mps", "t_s")):
            failed += 1; continue

        sim_df_agent = sim_df[[c for c in sim_df.columns if c in ALLOWED_INPUT_COLUMNS]].copy()
        if "yaw_rate_pred_rads" not in sim_df_agent.columns and base_col in sim_df.columns:
            sim_df_agent["yaw_rate_pred_rads"] = sim_df[base_col].astype(float).to_numpy()

        try:
            pred_df = predict_fn(sim_df_agent, platform)
        except Exception:
            failed += 1; continue
        if (
            not isinstance(pred_df, pd.DataFrame)
            or "yaw_rate_pred_rads" not in pred_df.columns
            or len(pred_df) != len(sim_df)
        ):
            failed += 1; continue

        t        = sim_df["t_s"].to_numpy(dtype=float)
        v        = sim_df["v_mps"].to_numpy(dtype=float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            failed += 1; continue
        yr_truth = sim_df[truth_col].to_numpy(dtype=float)
        yr_pred  = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float)

        mask_v   = v > sample_filter_v_mps
        resid    = yr_pred - yr_truth
        yaw_sum_signed = float(np.sum(resid[mask_v]))
        yaw_sum_sq     = float(np.sum(resid[mask_v] ** 2))
        yaw_n          = int(mask_v.sum())

        cte = cte_diagnostics_segment(
            t, v, yr_truth, yr_pred,
            grid_step_m=grid_step_m, min_distance_m=min_distance_m,
        )

        row = {
            "platform":        platform,
            "route":           _route_from_path(p),
            "segment_path":    str(p),
            "distance_m":      float(cte["total_distance_m"]),
            "yaw_n":           yaw_n,
            "yaw_sum_signed":  yaw_sum_signed,
            "yaw_sum_sq":      yaw_sum_sq,
            "cte_sum_signed":  float(cte["sum_signed_m"]),
            "cte_sum_sq":      float(cte["sum_sq_m2"]),
            "cte_n_bins":      int(cte["n_bins"]),
        }
        for feat in feature_means:
            if feat in sim_df_agent.columns:
                arr = sim_df_agent[feat].to_numpy(dtype=float)
                row[f"mean_{feat}"] = float(np.nanmean(arr)) if arr.size else float("nan")
            elif feat in sim_df.columns:
                arr = sim_df[feat].to_numpy(dtype=float)
                row[f"mean_{feat}"] = float(np.nanmean(arr)) if arr.size else float("nan")
            else:
                row[f"mean_{feat}"] = float("nan")
        rows.append(row)

    if not rows:
        return _empty(failed, feature_means)

    seg = pd.DataFrame(rows)

    # Per-route pool.
    feat_cols = [f"mean_{f}" for f in feature_means]
    grouped = seg.groupby(["platform", "route"], as_index=False).agg({
        "segment_path":   "count",
        "distance_m":     "sum",
        "yaw_n":          "sum",
        "yaw_sum_signed": "sum",
        "yaw_sum_sq":     "sum",
        "cte_sum_signed": "sum",
        "cte_sum_sq":     "sum",
        "cte_n_bins":     "sum",
        **{c: "mean" for c in feat_cols},
    }).rename(columns={"segment_path": "n_segments"})

    grouped["yaw_residual_mean"] = grouped["yaw_sum_signed"] / grouped["yaw_n"].replace(0, np.nan)
    grouped["cte_signed_mean"]   = grouped["cte_sum_signed"] / grouped["cte_n_bins"].replace(0, np.nan)
    grouped["yaw_rmse"]          = np.sqrt(grouped["yaw_sum_sq"] / grouped["yaw_n"].replace(0, np.nan))
    grouped["cte_rmse"]          = np.sqrt(grouped["cte_sum_sq"] / grouped["cte_n_bins"].replace(0, np.nan))

    # Share of the platform's pooled sum-of-squares — this is the *opportunity*
    # signal: a route may have moderate signed bias but contribute a huge
    # fraction of the platform's total error.
    plat_yaw_total = seg.groupby("platform")["yaw_sum_sq"].sum().rename("plat_yaw_total")
    plat_cte_total = seg.groupby("platform")["cte_sum_sq"].sum().rename("plat_cte_total")
    grouped = grouped.join(plat_yaw_total, on="platform").join(plat_cte_total, on="platform")
    grouped["share_of_platform_yaw_sum_sq"] = grouped["yaw_sum_sq"] / grouped["plat_yaw_total"].replace(0, np.nan)
    grouped["share_of_platform_cte_sum_sq"] = grouped["cte_sum_sq"] / grouped["plat_cte_total"].replace(0, np.nan)

    view_cols = [
        "platform", "route", "n_segments", "distance_m",
        "yaw_rmse", "yaw_residual_mean",
        "cte_rmse", "cte_signed_mean",
        "share_of_platform_yaw_sum_sq", "share_of_platform_cte_sum_sq",
    ] + feat_cols
    per_route = grouped[view_cols].copy()

    # Per-platform summary line.
    per_platform_summary = []
    for platform, sub in per_route.groupby("platform"):
        n_routes  = int(len(sub))
        # Routes whose absolute signed bias exceeds a threshold.
        flagged_y = int((sub["yaw_residual_mean"].abs() > ROUTE_YAW_BIAS_WARN_RAD_S).sum())
        flagged_c = int((sub["cte_signed_mean"].abs() > ROUTE_CTE_DRIFT_WARN_M).sum())
        per_platform_summary.append({
            "platform":         platform,
            "n_routes":         n_routes,
            "routes_yaw_flag":  flagged_y,
            "routes_cte_flag":  flagged_c,
            "max_abs_yaw_bias": float(sub["yaw_residual_mean"].abs().max()),
            "max_abs_cte_drift":float(sub["cte_signed_mean"].abs().max()),
        })
    per_platform_summary = pd.DataFrame(per_platform_summary)

    # Top-N by absolute CTE drift and by abs yaw bias, per platform.
    def _top_per_platform(df: pd.DataFrame, by: str, key: str) -> pd.DataFrame:
        out: list[pd.DataFrame] = []
        for _, sub in df.groupby("platform"):
            out.append(sub.assign(_abs=sub[by].abs()).nlargest(top_n, "_abs").drop(columns="_abs"))
        return pd.concat(out, ignore_index=True) if out else df.iloc[0:0]

    top_routes_by_cte      = _top_per_platform(per_route, "cte_signed_mean",   "cte")
    top_routes_by_yaw_bias = _top_per_platform(per_route, "yaw_residual_mean", "yaw")

    # Recommendation column — surface routes where signed bias is large AND
    # the share of platform error is non-trivial. These are the actionable ones.
    recommendations: list[dict] = []
    for _, r in per_route.iterrows():
        notes = []
        if abs(r["cte_signed_mean"]) > ROUTE_CTE_DRIFT_WARN_M and r["share_of_platform_cte_sum_sq"] > 0.05:
            notes.append("dominant_cte_drift")
        if abs(r["yaw_residual_mean"]) > ROUTE_YAW_BIAS_WARN_RAD_S and r["share_of_platform_yaw_sum_sq"] > 0.05:
            notes.append("dominant_yaw_bias")
        if notes:
            feat_summary = {f"mean_{f}": float(r[f"mean_{f}"]) for f in feature_means
                            if not math.isnan(r[f"mean_{f}"])}
            recommendations.append({
                "platform":         r["platform"],
                "route":            r["route"],
                "n_segments":       int(r["n_segments"]),
                "cte_signed_mean":  float(r["cte_signed_mean"]),
                "yaw_residual_mean":float(r["yaw_residual_mean"]),
                "share_yaw":        float(r["share_of_platform_yaw_sum_sq"]),
                "share_cte":        float(r["share_of_platform_cte_sum_sq"]),
                "feature_means":    feat_summary,
                "notes":            notes,
            })

    return {
        "per_route":              per_route,
        "per_platform_summary":   per_platform_summary,
        "top_routes_by_cte":      top_routes_by_cte,
        "top_routes_by_yaw_bias": top_routes_by_yaw_bias,
        "recommendations":        recommendations,
        "failed_segments":        failed,
        "feature_means":          feature_means,
    }


def format_route_bias_summary(result: dict, top_n: int = 10) -> str:
    """One-shot markdown dashboard. Lead with the recommendation block so the
    agent's eye goes to the actionable routes first."""
    if result["per_route"].empty:
        return f"route-bias: no routes scored ({result['failed_segments']} failed)."

    L = []
    L.append("## route-bias diagnostic")
    L.append("")
    L.append("**Reminder**: per-route bias is DIAGNOSTIC. Route ID is not an inference input — you can't")
    L.append("apply a route-keyed correction directly. Use the feature_means columns below to find an")
    L.append("OBSERVABLE input feature that correlates with the flagged routes, then add a term that")
    L.append("depends on that feature to your model.")
    L.append("")
    L.append("### per-platform summary")
    L.append("| platform | n_routes | routes_yaw_flag | routes_cte_flag | max_abs_yaw_bias | max_abs_cte_drift |")
    L.append("|---|---|---|---|---|---|")
    for _, r in result["per_platform_summary"].iterrows():
        L.append(
            f"| `{r['platform']}` | {r['n_routes']} | {r['routes_yaw_flag']} | {r['routes_cte_flag']} | "
            f"{r['max_abs_yaw_bias']:+.5f} | {r['max_abs_cte_drift']:+.2f} |"
        )

    if result["recommendations"]:
        L.append("")
        L.append("### 🎯 routes to act on")
        L.append("(non-trivial signed bias AND >5% share of the platform's pooled error)")
        L.append("")
        L.append("| platform | route | n | yaw_bias | cte_drift | share_yaw | share_cte | feature_means |")
        L.append("|---|---|---|---|---|---|---|---|")
        for r in result["recommendations"][:top_n]:
            feats = ", ".join(f"{k}={v:+.3g}" for k, v in r["feature_means"].items())
            L.append(
                f"| `{r['platform']}` | `{r['route']}` | {r['n_segments']} | "
                f"{r['yaw_residual_mean']:+.5f} | {r['cte_signed_mean']:+.2f} | "
                f"{r['share_yaw']:.1%} | {r['share_cte']:.1%} | `{feats}` |"
            )
    else:
        L.append("")
        L.append("### 🎯 routes to act on")
        L.append("None — no route exceeds both the bias threshold and the >5% share threshold.")

    L.append("")
    L.append(f"### top {top_n} routes by |cte_signed_mean| (per platform)")
    cols = ["platform", "route", "n_segments", "distance_m",
            "cte_rmse", "cte_signed_mean",
            "share_of_platform_cte_sum_sq"]
    head = result["top_routes_by_cte"].groupby("platform").head(top_n)[cols]
    L.append("| platform | route | n | dist_m | cte_rmse | cte_signed | share |")
    L.append("|---|---|---|---|---|---|---|")
    for _, r in head.iterrows():
        L.append(
            f"| `{r['platform']}` | `{r['route']}` | {r['n_segments']} | {r['distance_m']:.0f} | "
            f"{r['cte_rmse']:.2f} | {r['cte_signed_mean']:+.2f} | {r['share_of_platform_cte_sum_sq']:.1%} |"
        )
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _empty(failed: int, feature_means: list[str]) -> dict:
    return {
        "per_route":              pd.DataFrame(),
        "per_platform_summary":   pd.DataFrame(),
        "top_routes_by_cte":      pd.DataFrame(),
        "top_routes_by_yaw_bias": pd.DataFrame(),
        "recommendations":        [],
        "failed_segments":        failed,
        "feature_means":          feature_means,
    }


__all__ = [
    "route_bias",
    "format_route_bias_summary",
    "ROUTE_YAW_BIAS_WARN_RAD_S",
    "ROUTE_CTE_DRIFT_WARN_M",
]
