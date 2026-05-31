"""Evaluation utilities for the agent-08 module.

Scores any predict(sim_df, platform) callable across segments using the canonical
operating contract: predict gets a sim_df with only ALLOWED_INPUT_COLUMNS.

Handles BOTH schemas:
- new schema (Ford/Hyundai): yaw_rate_meas_rads is the truth.
- legacy schema (Tesla): psi_dot_rads is the truth.

CTE and yaw-rate RMSE use the math in _shared/traj_metrics.py.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MOD_ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-08")
sys.path.insert(0, str(MOD_ROOT / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa: E402

ALLOWED_INPUT_COLUMNS = frozenset({
    "t_s",
    "delta_wheel_deg",
    "delta_road_rad",
    "v_mps",
    "a_long_mps2",
    "accel_pedal_pct",
    "brake_pressed",
    "yaw_rate_pred_rads",
})


def _truth_col(df: pd.DataFrame) -> str | None:
    if "yaw_rate_meas_rads" in df.columns:
        return "yaw_rate_meas_rads"
    if "psi_dot_rads" in df.columns:
        return "psi_dot_rads"
    return None


def _normalise_sim_df(sim_df: pd.DataFrame) -> pd.DataFrame:
    """Bring a sim/segments/ DataFrame into the sim-only schema for predict().

    - Map legacy Tesla schema (brake_pedal_state, no yaw_rate_pred_rads) onto
      the modern names.
    - Strip to the allowed input columns.
    """
    df = sim_df.copy()
    if "brake_pressed" not in df.columns and "brake_pedal_state" in df.columns:
        df["brake_pressed"] = (df["brake_pedal_state"] > 1).astype(int)
    # legacy V0 prediction column name is the same in both schemas (after
    # generate_simdata) but if absent, recompute from KS formula with default L.
    if "yaw_rate_pred_rads" not in df.columns:
        # Tesla legacy: V0 stored as psi_dot from state integration. Use
        # delta_state_rad if present, else delta_road_rad.
        # Best proxy: (v / L) * tan(delta_road_rad) with L from platform.
        df["yaw_rate_pred_rads"] = np.nan
    return df[[c for c in df.columns if c in ALLOWED_INPUT_COLUMNS]]


def _platform_from_path(p: Path) -> str:
    return p.resolve().parents[3].name


def list_segments(root: Path, platform: str | None = None) -> list[Path]:
    root = Path(root)
    if platform:
        return sorted((root / platform).rglob("sim.csv"))
    out = []
    for child in sorted(root.iterdir()):
        if child.is_dir():
            out.extend(child.rglob("sim.csv"))
    return sorted(out)


def score(
    predict_fn,
    segment_paths: list[Path],
    sample_filter_v_mps: float = 2.0,
    grid_step_m: float = 1.0,
    min_distance_m: float = 20.0,
) -> dict:
    rows = []
    failed = 0
    for p in segment_paths:
        platform = _platform_from_path(p)
        try:
            full_df = pd.read_csv(p)
        except Exception:
            failed += 1
            continue
        truth_col = _truth_col(full_df)
        if truth_col is None or "t_s" not in full_df.columns or "v_mps" not in full_df.columns:
            failed += 1
            continue
        sim_df_agent = _normalise_sim_df(full_df)
        try:
            pred_df = predict_fn(sim_df_agent, platform)
        except Exception as exc:
            failed += 1
            continue
        if not isinstance(pred_df, pd.DataFrame) or "yaw_rate_pred_rads" not in pred_df.columns or len(pred_df) != len(full_df):
            failed += 1
            continue

        t = full_df["t_s"].to_numpy(float)
        v = full_df["v_mps"].to_numpy(float)
        yr_truth = full_df[truth_col].to_numpy(float)
        yr_pred = pred_df["yaw_rate_pred_rads"].to_numpy(float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            failed += 1
            continue

        mask_v = v > sample_filter_v_mps
        resid = yr_pred - yr_truth
        n_v = int(mask_v.sum())
        yr_sum_sq = float(np.sum(resid[mask_v] ** 2))

        cte = cte_diagnostics_segment(t, v, yr_truth, yr_pred,
                                      grid_step_m=grid_step_m,
                                      min_distance_m=min_distance_m)
        rows.append({
            "platform": platform,
            "yaw_n": n_v,
            "yaw_sum_sq": yr_sum_sq,
            "cte_sum_sq": cte["sum_sq_m2"],
            "cte_n_bins": cte["n_bins"],
        })

    if not rows:
        return {"yaw_rate_rmse": float("nan"), "cte_rmse": float("nan"),
                "n_segments": 0, "failed": failed, "per_platform": {}}

    df = pd.DataFrame(rows)
    yr_rmse = math.sqrt(df["yaw_sum_sq"].sum() / df["yaw_n"].sum())
    cte_rmse = math.sqrt(df["cte_sum_sq"].sum() / df["cte_n_bins"].sum())

    per_platform = {}
    for plat, sub in df.groupby("platform"):
        n_yaw = sub["yaw_n"].sum()
        n_cte = sub["cte_n_bins"].sum()
        per_platform[plat] = {
            "yaw_rate_rmse": math.sqrt(sub["yaw_sum_sq"].sum() / n_yaw) if n_yaw > 0 else float("nan"),
            "cte_rmse": math.sqrt(sub["cte_sum_sq"].sum() / n_cte) if n_cte > 0 else float("nan"),
            "n_seg": len(sub),
        }

    return {
        "yaw_rate_rmse": yr_rmse,
        "cte_rmse": cte_rmse,
        "n_segments": len(rows),
        "failed": failed,
        "per_platform": per_platform,
    }
