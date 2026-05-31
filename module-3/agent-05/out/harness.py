"""Local harness: load segments, score a predict() against truth.

KPIs:
- pooled yaw-rate RMSE (rad/s)
- pooled distance-resampled CTE RMSE (m)
"""
from __future__ import annotations

import sys
from pathlib import Path
import math
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _shared.traj_metrics import cte_rmse_segment  # noqa


SIM_ROOT = ROOT / "data" / "sim" / "segments"
SIM_ONLY_ROOT = ROOT / "data" / "sim-only" / "segments"
PLATFORMS_WITH_TRUTH = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def find_sim_csvs(root: Path, platform: str) -> list[Path]:
    return sorted(root.glob(f"{platform}/*/*/*/sim.csv"))


def load_segment(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p)
    return df


def score_predict(predict_fn, platforms=PLATFORMS_WITH_TRUTH, root: Path = SIM_ROOT,
                  use_input_only=False, max_segments=None, verbose=False):
    """Score a predict(sim_df, platform) -> DataFrame with 'yaw_rate_pred_rads'.

    use_input_only: if True, strip truth columns before passing to predict (mimics grading contract).
    """
    sum_sq_yaw = 0.0
    n_yaw = 0
    sum_sq_cte = 0.0
    n_bins = 0
    per_platform = {}
    per_segment = []

    for plat in platforms:
        csvs = find_sim_csvs(root, plat)
        if max_segments:
            csvs = csvs[:max_segments]
        p_sum_sq_yaw = 0.0
        p_n_yaw = 0
        p_sum_sq_cte = 0.0
        p_n_bins = 0
        for csv in csvs:
            df = load_segment(csv)
            if "yaw_rate_meas_rads" not in df.columns:
                continue
            truth = df["yaw_rate_meas_rads"].to_numpy()
            t = df["t_s"].to_numpy()
            v = df["v_mps"].to_numpy()

            input_df = df
            if use_input_only:
                cols_to_drop = [c for c in df.columns if c in
                                ("yaw_rate_meas_rads", "x_m", "y_m", "psi_rad",
                                 "v_state_mps", "delta_state_rad", "a_y_pred_mps2",
                                 "yaw_rate_resid_rads", "a_y_resid_mps2",
                                 "a_lat_meas_mps2")]
                input_df = df.drop(columns=cols_to_drop)

            pred_df = predict_fn(input_df, plat)
            pred = pred_df["yaw_rate_pred_rads"].to_numpy()
            # yaw RMSE
            err = pred - truth
            p_sum_sq_yaw += float((err * err).sum())
            p_n_yaw += int(len(err))
            # CTE RMSE
            ss, nb, _ = cte_rmse_segment(t, v, truth, pred)
            p_sum_sq_cte += ss
            p_n_bins += nb
            per_segment.append({
                "platform": plat, "segment": str(csv.relative_to(root)),
                "yaw_rmse": math.sqrt(float((err * err).mean())),
                "cte_rmse": math.sqrt(ss / nb) if nb > 0 else float("nan"),
                "n": len(err),
            })

        if p_n_yaw > 0:
            per_platform[plat] = {
                "yaw_rmse": math.sqrt(p_sum_sq_yaw / p_n_yaw),
                "cte_rmse": math.sqrt(p_sum_sq_cte / p_n_bins) if p_n_bins > 0 else float("nan"),
                "n_samples": p_n_yaw,
                "n_segments": len([s for s in per_segment if s["platform"] == plat]),
            }
        sum_sq_yaw += p_sum_sq_yaw
        n_yaw += p_n_yaw
        sum_sq_cte += p_sum_sq_cte
        n_bins += p_n_bins

    pooled = {
        "yaw_rmse": math.sqrt(sum_sq_yaw / n_yaw) if n_yaw > 0 else float("nan"),
        "cte_rmse": math.sqrt(sum_sq_cte / n_bins) if n_bins > 0 else float("nan"),
        "n_samples": n_yaw,
        "n_bins": n_bins,
    }
    if verbose:
        print(f"Pooled: yaw_rmse={pooled['yaw_rmse']:.5f}  cte_rmse={pooled['cte_rmse']:.3f}")
        for plat, m in per_platform.items():
            print(f"  {plat}: yaw={m['yaw_rmse']:.5f}  cte={m['cte_rmse']:.3f}  n_seg={m['n_segments']}")
    return pooled, per_platform, per_segment


def v0_predict(sim_df, platform):
    """V0 passthrough — just use the pre-computed yaw_rate_pred_rads."""
    return sim_df[["yaw_rate_pred_rads"]].copy()


if __name__ == "__main__":
    pooled, per_plat, _ = score_predict(v0_predict, verbose=True)
