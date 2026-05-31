"""Render a 3-panel PNG for one segment — truth vs N predictions.

Panels (top to bottom):
  1. Bird's-eye trajectory (x vs y, equal aspect).
  2. Yaw rate vs time (rad/s).
  3. Yaw rate residual vs time (pred - meas), with a zero line.

Predictions are supplied as a dict[name -> predict_fn], where
`predict_fn(sim_df, platform) -> DataFrame` with `yaw_rate_pred_rads`
(and optionally `x_m`, `y_m`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Import the shared integrator so trajectory math is identical everywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from traj_metrics import integrate_trajectory  # noqa: E402


def _infer_platform(segment_path: Path) -> str:
    """Platform is the 3rd-from-rightmost directory of the segment path.

    Layout: .../<PLATFORM>/<device>/<route>/<idx>/sim.csv
    """
    return segment_path.resolve().parents[2].name


def _default_title(segment_path: Path) -> str:
    parts = segment_path.resolve().parts
    tail = parts[-5:-1]  # PLATFORM / device / route / idx
    return "/".join(tail) if len(tail) == 4 else "/".join(parts[-4:-1])


def _truth_trajectory(sim_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    yr = sim_df["yaw_rate_meas_rads"].to_numpy(dtype=float)
    if len(t) < 2:
        z = np.zeros(len(t))
        return z, z
    dt = np.diff(t)
    _, x, y, _ = integrate_trajectory(dt, v, yr)
    return x, y


def _pred_trajectory(sim_df: pd.DataFrame, pred_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    # If the prediction supplies its own (x_m, y_m), trust them.
    if "x_m" in pred_df.columns and "y_m" in pred_df.columns:
        return pred_df["x_m"].to_numpy(dtype=float), pred_df["y_m"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    yr = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    if len(t) < 2:
        z = np.zeros(len(t))
        return z, z
    dt = np.diff(t)
    _, x, y, _ = integrate_trajectory(dt, v, yr)
    return x, y


def plot(
    segment_path,
    predict_fns,
    out_path,
    title=None,
    figsize=(10, 12),
) -> Path:
    """Render one segment's truth + predictions to a PNG.

    Args:
        segment_path: Path to a sim.csv file.
        predict_fns: dict[str, callable(sim_df, platform) -> DataFrame].
            Each predicted DataFrame must contain `yaw_rate_pred_rads`;
            optionally `x_m` and `y_m` to override integrated trajectory.
        out_path: Where the PNG will be written. Parent dirs are created.
        title: Optional figure title. Defaults to the last 4 path components
            (platform/device/route/idx).
        figsize: matplotlib figsize tuple.

    Returns:
        out_path, after writing the PNG.
    """
    segment_path = Path(segment_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sim_df = pd.read_csv(segment_path)
    platform = _infer_platform(segment_path)
    t = sim_df["t_s"].to_numpy(dtype=float)
    yr_meas = sim_df["yaw_rate_meas_rads"].to_numpy(dtype=float)

    truth_x, truth_y = _truth_trajectory(sim_df)

    # Run all predictors up-front so we fail loudly before plotting.
    preds: dict[str, pd.DataFrame] = {}
    for name, fn in predict_fns.items():
        pred_df = fn(sim_df, platform)
        if "yaw_rate_pred_rads" not in pred_df.columns:
            raise ValueError(
                f"predict_fn {name!r} returned a DataFrame missing 'yaw_rate_pred_rads'"
            )
        preds[name] = pred_df

    fig, axes = plt.subplots(3, 1, figsize=figsize)
    ax_xy, ax_yr, ax_res = axes

    # Truth styled to stand out: thicker, dark grey.
    truth_kw = dict(color="#222222", linewidth=2.4, label="truth")

    # --- Panel 1: bird's-eye ---
    ax_xy.plot(truth_x, truth_y, **truth_kw)
    ax_xy.plot([0], [0], marker="o", markersize=6,
               markerfacecolor="white", markeredgecolor="#222222", linestyle="None",
               label="start (0, 0)")
    for name, pred_df in preds.items():
        px, py = _pred_trajectory(sim_df, pred_df)
        ax_xy.plot(px, py, linewidth=1.4, label=name)
    ax_xy.set_xlabel("x [m]")
    ax_xy.set_ylabel("y [m]")
    ax_xy.set_title("Bird's-eye trajectory")
    ax_xy.set_aspect("equal", adjustable="datalim")
    ax_xy.grid(True, alpha=0.3)
    ax_xy.legend(loc="best", fontsize=9)

    # --- Panel 2: yaw rate time series ---
    ax_yr.plot(t, yr_meas, **truth_kw)
    for name, pred_df in preds.items():
        ax_yr.plot(t, pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float),
                   linewidth=1.2, label=name)
    ax_yr.set_xlabel("t [s]")
    ax_yr.set_ylabel("yaw rate [rad/s]")
    ax_yr.set_title("Yaw rate vs time")
    ax_yr.grid(True, alpha=0.3)
    ax_yr.legend(loc="best", fontsize=9)

    # --- Panel 3: yaw rate residual ---
    ax_res.axhline(0.0, color="#222222", linewidth=1.0, linestyle="--", alpha=0.7)
    for name, pred_df in preds.items():
        resid = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float) - yr_meas
        ax_res.plot(t, resid, linewidth=1.2, label=name)
    ax_res.set_xlabel("t [s]")
    ax_res.set_ylabel("pred - meas [rad/s]")
    ax_res.set_title("Yaw rate residual")
    ax_res.grid(True, alpha=0.3)
    ax_res.legend(loc="best", fontsize=9)

    fig.suptitle(title if title is not None else _default_title(segment_path), fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    return out_path
