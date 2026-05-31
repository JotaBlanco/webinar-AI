"""inspect-residuals — see how a predict_fn's yaw residual varies with any input feature.

Run the predictor over a set of segments, compute per-row residual = pred - truth,
and return both:
  - a long DataFrame of (segment, platform, x_value, residual) rows
  - a matplotlib Figure (scatter coloured by platform + binned mean/std overlay)

The caller decides what to do with the figure (savefig / show / discard). This
skill does not write to disk on its own.
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
    root = Path.cwd() / "data" / "sim-full"
    if not root.exists():
        return []
    return sorted(root.glob("FORD_*/**/sim.csv"))


# ---------------------------------------------------------------------------
# Public API
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
    """Plot yaw residual against an arbitrary input feature.

    Args:
        predict_fn: callable(sim_df, platform) -> DataFrame with `yaw_rate_pred_rads`.
        x_feature: name of a column present in sim_df to put on the x-axis
            (e.g. `delta_road_rad`, `v_mps`, `t_s`, or any column you compute
            yourself before passing the segment in). The same v-filter the
            scoring-model uses is applied before pairing x with residual.
        segment_paths: list of sim.csv paths. If None, glob FORD_* under cwd.
        platform_filter: keep only this platform if set.
        sample_filter_v_mps: rows below this speed are dropped (matches scoring-model).
        bins: number of equal-quantile bins for the overlaid mean/std curves.
        max_points_per_platform: cap on scatter points drawn per platform
            (uniformly downsampled) — keeps the figure readable. The returned
            DataFrame is NOT downsampled.
        title: figure title. Defaults to "yaw residual vs {x_feature}".

    Returns:
        dict with keys:
          - residuals: pandas.DataFrame of (segment_path, platform, x_value, residual)
            after the v-filter, one row per sample.
          - binned: pandas.DataFrame of (platform, x_bin_left, x_bin_right,
            x_bin_centre, n, mean, std) per platform per quantile bin.
          - figure: matplotlib.figure.Figure (you save / show / close it).
          - n_segments_used: int
          - n_segments_skipped: int
    """
    if segment_paths is None:
        segment_paths = _default_segment_paths()
    paths = [Path(p) for p in segment_paths]
    if platform_filter is not None:
        paths = [p for p in paths if _platform_from_path(p) == platform_filter]

    rows: list[dict] = []
    n_used = 0
    n_skipped = 0

    for p in paths:
        platform = _platform_from_path(p)
        try:
            sim_df = pd.read_csv(p)
        except Exception as exc:
            warnings.warn(f"inspect-residuals: could not read {p}: {exc}")
            n_skipped += 1
            continue

        for col in ("yaw_rate_meas_rads", "v_mps", x_feature):
            if col not in sim_df.columns:
                warnings.warn(f"inspect-residuals: {p} missing column {col!r}; skipping")
                n_skipped += 1
                break
        else:
            try:
                pred_df = predict_fn(sim_df, platform)
            except Exception as exc:
                warnings.warn(f"inspect-residuals: predict_fn raised on {p}: {exc}")
                n_skipped += 1
                continue

            if (
                not isinstance(pred_df, pd.DataFrame)
                or "yaw_rate_pred_rads" not in pred_df.columns
                or len(pred_df) != len(sim_df)
            ):
                warnings.warn(f"inspect-residuals: predict_fn returned wrong shape on {p}")
                n_skipped += 1
                continue

            v        = sim_df["v_mps"].to_numpy(dtype=float)
            yr_truth = sim_df["yaw_rate_meas_rads"].to_numpy(dtype=float)
            yr_pred  = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
            x        = sim_df[x_feature].to_numpy(dtype=float)
            mask     = v > sample_filter_v_mps

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
            "residuals":          pd.DataFrame(),
            "binned":             pd.DataFrame(),
            "figure":             fig,
            "n_segments_used":    n_used,
            "n_segments_skipped": n_skipped,
        }

    residuals = pd.DataFrame(rows)
    binned    = _bin_per_platform(residuals, bins=bins)
    figure    = _make_figure(residuals, binned, x_feature, title, max_points_per_platform)

    return {
        "residuals":          residuals,
        "binned":             binned,
        "figure":             figure,
        "n_segments_used":    n_used,
        "n_segments_skipped": n_skipped,
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


def _make_figure(
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


__all__ = ["inspect_residuals"]
