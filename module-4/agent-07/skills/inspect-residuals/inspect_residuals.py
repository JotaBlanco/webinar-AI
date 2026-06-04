"""inspect-residuals — see how a predict_fn's yaw residual varies with input features.

Two modes:
  - ``inspect_residuals(predict_fn, x_feature)`` — 1-D scatter + binned mean ± σ band.
  - ``inspect_residuals_2d(predict_fn, x_feature, y_feature)`` — 2-D heatmap of
    mean residual per (x, y) cell. Use this when the 1-D plot can't tell
    understeer-shape from hysteresis-shape because both effects depend jointly
    on speed AND steering.

Both modes return long DataFrames + a matplotlib Figure. The caller decides
what to do with the figure (savefig / show / discard). This skill does not
write to disk on its own.

Schema-aware: resolves each segment's truth column via `scoring-model`'s
`PLATFORM_SCHEMA`, so Tesla and any platform with a non-default schema
participate instead of being silently dropped.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
from traj_metrics import integrate_trajectory  # noqa: E402,F401  (re-export convenience)


# ---------------------------------------------------------------------------
# Path helpers — same convention as scoring-model
# ---------------------------------------------------------------------------

def _platform_from_path(p: Path) -> str:
    return p.resolve().parents[3].name


def _route_from_path(p: Path) -> str:
    return p.resolve().parents[1].name


def _default_segment_paths() -> list[Path]:
    """All platforms — not just FORD_*. The old default silently dropped
    Hyundai and Tesla; this default matches scoring-model."""
    root = Path.cwd() / "data" / "sim" / "segments"
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())


def _resolve_schema(platform: str) -> dict:
    return PLATFORM_SCHEMA.get(platform, DEFAULT_SCHEMA)


# ---------------------------------------------------------------------------
# Predict + residual helper, schema-aware. Returns aligned numpy arrays plus
# the sim_df *agent view* (allowlist-stripped, V0 aliased to
# yaw_rate_pred_rads), so callers can read any input feature uniformly,
# including ones whose native name differed (e.g. Tesla had no
# yaw_rate_pred_rads on disk — the alias is now there).
# ---------------------------------------------------------------------------

def _predict_and_residual(
    predict_fn,
    sim_df_full: pd.DataFrame,
    platform: str,
):
    schema    = _resolve_schema(platform)
    truth_col = schema["truth_col"]
    base_col  = schema["baseline_col"]

    if any(c not in sim_df_full.columns for c in (truth_col, "v_mps")):
        return None

    sim_df_agent = sim_df_full[[c for c in sim_df_full.columns if c in ALLOWED_INPUT_COLUMNS]].copy()
    if "yaw_rate_pred_rads" not in sim_df_agent.columns and base_col in sim_df_full.columns:
        sim_df_agent["yaw_rate_pred_rads"] = sim_df_full[base_col].astype(float).to_numpy()

    try:
        pred_df = predict_fn(sim_df_agent, platform)
    except Exception:
        return None
    if (
        not isinstance(pred_df, pd.DataFrame)
        or "yaw_rate_pred_rads" not in pred_df.columns
        or len(pred_df) != len(sim_df_full)
    ):
        return None

    v        = sim_df_full["v_mps"].to_numpy(dtype=float)
    yr_truth = sim_df_full[truth_col].to_numpy(dtype=float)
    yr_pred  = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    return yr_truth, yr_pred, v, sim_df_agent


def _feature_array(sim_df_agent: pd.DataFrame, sim_df_full: pd.DataFrame, name: str) -> np.ndarray | None:
    """Resolve a feature column.

    Prefers the allowlist-stripped agent view (matches what predict sees);
    falls back to the full sim.csv for diagnostic-only columns the agent
    isn't allowed to read at inference. Returns None if absent in both."""
    if name in sim_df_agent.columns:
        return sim_df_agent[name].to_numpy(dtype=float)
    if name in sim_df_full.columns:
        return sim_df_full[name].to_numpy(dtype=float)
    return None


# ---------------------------------------------------------------------------
# 1-D mode (existing API — same signature, now schema-aware)
# ---------------------------------------------------------------------------

def inspect_residuals(
    predict_fn,
    x_feature: str,
    segment_paths: list | None = None,
    platform_filter: str | None = None,
    sample_filter_v_mps: float = 2.0,
    bins: int = 20,
    max_points_per_platform: int = 5000,
    title: str | None = None,
) -> dict:
    """Plot yaw residual against one input feature, with a per-platform binned
    mean ± σ overlay. See module docstring for 2-D companion.

    Args:
        predict_fn: callable(sim_df, platform) -> DataFrame with `yaw_rate_pred_rads`.
        x_feature: column name on the x-axis. Resolved from the agent-view sim_df
            first; falls back to the raw sim.csv. The same v-filter scoring-model
            uses is applied.
        segment_paths: list of sim.csv paths. If None, glob ALL platforms under
            ``data/sim/segments/*/**/sim.csv``.
        platform_filter, sample_filter_v_mps, bins, max_points_per_platform, title:
            as before.

    Returns:
        dict with: residuals (DataFrame), binned (DataFrame), figure, n_segments_used,
        n_segments_skipped, skipped_by_platform.
    """
    if segment_paths is None:
        segment_paths = _default_segment_paths()
    paths = [Path(p) for p in segment_paths]
    if platform_filter is not None:
        paths = [p for p in paths if _platform_from_path(p) == platform_filter]

    rows: list[dict] = []
    n_used = 0
    n_skipped = 0
    skipped_by_platform: dict[str, int] = {}

    for p in paths:
        platform = _platform_from_path(p)
        try:
            sim_df = pd.read_csv(p)
        except Exception as exc:
            warnings.warn(f"inspect-residuals: could not read {p}: {exc}")
            n_skipped += 1
            skipped_by_platform[platform] = skipped_by_platform.get(platform, 0) + 1
            continue

        bundle = _predict_and_residual(predict_fn, sim_df, platform)
        if bundle is None:
            n_skipped += 1
            skipped_by_platform[platform] = skipped_by_platform.get(platform, 0) + 1
            continue
        yr_truth, yr_pred, v, sim_df_agent = bundle

        x = _feature_array(sim_df_agent, sim_df, x_feature)
        if x is None:
            warnings.warn(f"inspect-residuals: {p} missing column {x_feature!r}; skipping")
            n_skipped += 1
            skipped_by_platform[platform] = skipped_by_platform.get(platform, 0) + 1
            continue

        mask  = v > sample_filter_v_mps
        resid = yr_pred[mask] - yr_truth[mask]
        x_vals = x[mask]

        for xv, rv in zip(x_vals, resid):
            rows.append({
                "segment_path": str(p),
                "platform":     platform,
                "route":        _route_from_path(p),
                "x_value":      float(xv),
                "residual":     float(rv),
            })
        n_used += 1

    if not rows:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, "no data", ha="center", va="center")
        return {
            "residuals":           pd.DataFrame(),
            "binned":              pd.DataFrame(),
            "figure":              fig,
            "n_segments_used":     n_used,
            "n_segments_skipped":  n_skipped,
            "skipped_by_platform": skipped_by_platform,
        }

    residuals = pd.DataFrame(rows)
    binned    = _bin_per_platform(residuals, bins=bins)
    figure    = _make_figure_1d(residuals, binned, x_feature, title, max_points_per_platform)

    return {
        "residuals":           residuals,
        "binned":              binned,
        "figure":              figure,
        "n_segments_used":     n_used,
        "n_segments_skipped":  n_skipped,
        "skipped_by_platform": skipped_by_platform,
    }


# ---------------------------------------------------------------------------
# 2-D mode — mean-residual heatmap per platform, per (x, y) cell.
# ---------------------------------------------------------------------------

def inspect_residuals_2d(
    predict_fn,
    x_feature: str,
    y_feature: str,
    segment_paths: list | None = None,
    platform_filter: str | None = None,
    sample_filter_v_mps: float = 2.0,
    bins: tuple[int, int] = (20, 20),
    min_cell_n: int = 5,
    title: str | None = None,
    cmap: str = "RdBu_r",
    symmetric_color_scale: bool = True,
) -> dict:
    """Heatmap of mean residual per (x_feature, y_feature) cell, one panel per platform.

    Use when 1-D inspect-residuals shows structure on two axes simultaneously
    (e.g. residual depends on both speed AND steering) and you can't tell what
    shape the bias has.

    Args:
        predict_fn: callable(sim_df, platform) -> DataFrame with `yaw_rate_pred_rads`.
        x_feature, y_feature: column names. Resolved like the 1-D mode.
        segment_paths, platform_filter, sample_filter_v_mps: as 1-D mode.
        bins: (n_x_bins, n_y_bins). Equal-quantile in each axis, per platform.
        min_cell_n: cells with fewer samples than this are NaN-masked in the plot.
        title: figure title.
        cmap: matplotlib colormap. Diverging cmap (default `RdBu_r`) is the right
            choice for *signed* residual.
        symmetric_color_scale: if True, the colour limits are ±max(|residual|) so
            zero is always white.

    Returns:
        dict with: residuals (long DataFrame), heatmaps (per-platform dict of
        {x_edges, y_edges, mean, count}), figure, n_segments_used,
        n_segments_skipped, skipped_by_platform.
    """
    if segment_paths is None:
        segment_paths = _default_segment_paths()
    paths = [Path(p) for p in segment_paths]
    if platform_filter is not None:
        paths = [p for p in paths if _platform_from_path(p) == platform_filter]

    rows: list[dict] = []
    n_used = 0
    n_skipped = 0
    skipped_by_platform: dict[str, int] = {}

    for p in paths:
        platform = _platform_from_path(p)
        try:
            sim_df = pd.read_csv(p)
        except Exception as exc:
            warnings.warn(f"inspect-residuals-2d: could not read {p}: {exc}")
            n_skipped += 1
            skipped_by_platform[platform] = skipped_by_platform.get(platform, 0) + 1
            continue

        bundle = _predict_and_residual(predict_fn, sim_df, platform)
        if bundle is None:
            n_skipped += 1
            skipped_by_platform[platform] = skipped_by_platform.get(platform, 0) + 1
            continue
        yr_truth, yr_pred, v, sim_df_agent = bundle

        x = _feature_array(sim_df_agent, sim_df, x_feature)
        y = _feature_array(sim_df_agent, sim_df, y_feature)
        if x is None or y is None:
            missing = x_feature if x is None else y_feature
            warnings.warn(f"inspect-residuals-2d: {p} missing column {missing!r}; skipping")
            n_skipped += 1
            skipped_by_platform[platform] = skipped_by_platform.get(platform, 0) + 1
            continue

        mask  = v > sample_filter_v_mps
        resid = yr_pred[mask] - yr_truth[mask]
        xv = x[mask]
        yv = y[mask]

        for xx, yy, rv in zip(xv, yv, resid):
            rows.append({
                "segment_path": str(p),
                "platform":     platform,
                "route":        _route_from_path(p),
                "x_value":      float(xx),
                "y_value":      float(yy),
                "residual":     float(rv),
            })
        n_used += 1

    if not rows:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, "no data", ha="center", va="center")
        return {
            "residuals":           pd.DataFrame(),
            "heatmaps":            {},
            "figure":              fig,
            "n_segments_used":     n_used,
            "n_segments_skipped":  n_skipped,
            "skipped_by_platform": skipped_by_platform,
        }

    residuals = pd.DataFrame(rows)
    heatmaps  = _bin_2d_per_platform(residuals, bins=bins, min_cell_n=min_cell_n)
    figure    = _make_figure_2d(
        heatmaps, x_feature, y_feature, title,
        cmap=cmap, symmetric_color_scale=symmetric_color_scale,
    )

    return {
        "residuals":           residuals,
        "heatmaps":            heatmaps,
        "figure":              figure,
        "n_segments_used":     n_used,
        "n_segments_skipped":  n_skipped,
        "skipped_by_platform": skipped_by_platform,
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _bin_per_platform(residuals: pd.DataFrame, bins: int) -> pd.DataFrame:
    """Equal-quantile bins per platform → mean/std/count per bin."""
    out_rows: list[dict] = []
    for platform, sub in residuals.groupby("platform"):
        x = sub["x_value"].to_numpy()
        if len(x) < bins:
            edges = np.linspace(np.nanmin(x), np.nanmax(x), max(len(x), 2))
        else:
            qs = np.linspace(0.0, 1.0, bins + 1)
            edges = np.unique(np.quantile(x, qs))
        if len(edges) < 2:
            continue
        bin_idx = np.digitize(x, edges[1:-1], right=False)
        r = sub["residual"].to_numpy()
        for i in range(len(edges) - 1):
            mask = bin_idx == i
            if mask.sum() == 0:
                continue
            out_rows.append({
                "platform":     platform,
                "x_bin_left":   float(edges[i]),
                "x_bin_right":  float(edges[i + 1]),
                "x_bin_centre": float(0.5 * (edges[i] + edges[i + 1])),
                "n":            int(mask.sum()),
                "mean":         float(r[mask].mean()),
                "std":          float(r[mask].std(ddof=0)),
            })
    return pd.DataFrame(out_rows)


def _bin_2d_per_platform(
    residuals: pd.DataFrame,
    bins: tuple[int, int],
    min_cell_n: int,
) -> dict[str, dict]:
    nx, ny = bins
    heatmaps: dict[str, dict] = {}
    for platform, sub in residuals.groupby("platform"):
        x = sub["x_value"].to_numpy()
        y = sub["y_value"].to_numpy()
        r = sub["residual"].to_numpy()

        if len(x) < max(nx, ny):
            continue

        # Equal-quantile edges per axis.
        x_edges = np.unique(np.quantile(x, np.linspace(0.0, 1.0, nx + 1)))
        y_edges = np.unique(np.quantile(y, np.linspace(0.0, 1.0, ny + 1)))
        if len(x_edges) < 2 or len(y_edges) < 2:
            continue

        # `statistic_2d` would be nice but we don't import scipy.stats here;
        # numpy histogram primitives are enough.
        sum_, _, _ = np.histogram2d(x, y, bins=[x_edges, y_edges], weights=r)
        count, _, _ = np.histogram2d(x, y, bins=[x_edges, y_edges])
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = sum_ / count
        mean = np.where(count >= min_cell_n, mean, np.nan)

        heatmaps[platform] = {
            "x_edges": x_edges,
            "y_edges": y_edges,
            "mean":    mean,    # shape (len(x_edges)-1, len(y_edges)-1)
            "count":   count,
        }
    return heatmaps


def _make_figure_1d(
    residuals: pd.DataFrame,
    binned:    pd.DataFrame,
    x_feature: str,
    title:     str | None,
    max_pts:   int,
) -> "plt.Figure":
    fig, ax = plt.subplots(figsize=(9, 5.5))

    platforms = sorted(residuals["platform"].unique())
    cmap = plt.cm.get_cmap("tab10", max(len(platforms), 3))
    colors = {plat: cmap(i) for i, plat in enumerate(platforms)}

    rng = np.random.default_rng(0)
    for plat in platforms:
        sub = residuals[residuals["platform"] == plat]
        n = len(sub)
        if n > max_pts:
            idx = rng.choice(n, size=max_pts, replace=False)
            sub_plot = sub.iloc[idx]
        else:
            sub_plot = sub
        ax.scatter(
            sub_plot["x_value"], sub_plot["residual"],
            s=5, alpha=0.25, color=colors[plat], label=f"{plat} (n={n})",
        )
        sub_bin = binned[binned["platform"] == plat].sort_values("x_bin_centre")
        if not sub_bin.empty:
            ax.plot(sub_bin["x_bin_centre"], sub_bin["mean"],
                    color=colors[plat], linewidth=2.0)
            ax.fill_between(
                sub_bin["x_bin_centre"],
                sub_bin["mean"] - sub_bin["std"],
                sub_bin["mean"] + sub_bin["std"],
                color=colors[plat], alpha=0.15,
            )

    ax.axhline(0.0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.set_xlabel(x_feature)
    ax.set_ylabel("yaw residual (pred - truth) [rad/s]")
    ax.set_title(title or f"yaw residual vs {x_feature}")
    ax.legend(loc="best", framealpha=0.85)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def _make_figure_2d(
    heatmaps: dict[str, dict],
    x_feature: str,
    y_feature: str,
    title:     str | None,
    cmap:      str,
    symmetric_color_scale: bool,
) -> "plt.Figure":
    platforms = list(heatmaps.keys())
    n = max(len(platforms), 1)
    cols = min(n, 2)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(6.5 * cols, 4.8 * rows), squeeze=False)

    # Shared symmetric colour range so platforms are comparable.
    if symmetric_color_scale and heatmaps:
        all_vals = np.concatenate([h["mean"][np.isfinite(h["mean"])] for h in heatmaps.values()]) \
            if any(np.isfinite(h["mean"]).any() for h in heatmaps.values()) else np.array([0.0])
        vmax = float(np.nanmax(np.abs(all_vals))) if all_vals.size else 1.0
        vmin = -vmax
    else:
        vmin = vmax = None

    for i, plat in enumerate(platforms):
        ax = axes[i // cols][i % cols]
        h = heatmaps[plat]
        # imshow wants (rows=y, cols=x) — our mean array is (x, y), transpose.
        mesh = ax.pcolormesh(
            h["x_edges"], h["y_edges"], h["mean"].T,
            cmap=cmap, vmin=vmin, vmax=vmax, shading="auto",
        )
        ax.set_xlabel(x_feature)
        ax.set_ylabel(y_feature)
        ax.set_title(f"{plat} — mean residual (rad/s)")
        fig.colorbar(mesh, ax=ax, label="mean residual")

    # Hide unused subplots.
    for j in range(len(platforms), rows * cols):
        axes[j // cols][j % cols].axis("off")

    fig.suptitle(title or f"mean yaw residual heatmap — {x_feature} × {y_feature}")
    fig.tight_layout()
    return fig


__all__ = ["inspect_residuals", "inspect_residuals_2d"]
