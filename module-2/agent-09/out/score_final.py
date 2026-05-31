"""Score final-model/predict.py with the score-model skill on truth-bearing segments.

Tesla has psi_dot_rads not yaw_rate_meas_rads -> handled with a small monkey patch
or skipped. Here we score Ford F-150, Ford Mustang Mach-E, Hyundai Ioniq 5 via the
official scorer (which requires yaw_rate_meas_rads). Tesla we score separately by
loading psi_dot_rads as truth.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-09")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "final-model"))
sys.path.insert(0, str(ROOT / "skills"))
sys.path.insert(0, str(ROOT / "_shared"))

from predict import predict  # noqa: E402

# score-model lives under skills/score-model/ (dash, not import-safe). Load by path.
import importlib.util
_spec = importlib.util.spec_from_file_location("score_module", ROOT / "skills" / "score-model" / "score.py")
_score_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_score_module)
score = _score_module.score
format_summary = _score_module.format_summary

from traj_metrics import cte_diagnostics_segment  # noqa: E402

import math

SIM_ROOT = ROOT / "data" / "sim" / "segments"


def collect_segments(platform: str) -> list[Path]:
    return sorted((SIM_ROOT / platform).glob("**/sim.csv"))


def main():
    # Ford + Hyundai through the standard scorer.
    fh_platforms = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
    fh_paths: list[Path] = []
    for p in fh_platforms:
        fh_paths += collect_segments(p)
    print(f"Scoring {len(fh_paths)} Ford+Hyundai segments via score-model skill...")
    result = score(predict, segment_paths=fh_paths)
    print(format_summary(result))

    summary = {
        "ford_hyundai": {
            "yaw_rate_rmse": result["yaw_rate_rmse"],
            "cte_rmse": result["cte_rmse"],
            "n_segments": result["n_segments"],
            "n_samples": result["n_samples"],
            "per_platform": {
                k: {kk: (float(vv) if isinstance(vv, (int, float, np.floating)) else vv)
                    for kk, vv in v.items()}
                for k, v in result["per_platform"].items()
            },
        }
    }

    # Tesla — score manually with psi_dot_rads as truth.
    tesla_paths = collect_segments("TESLA_MODEL_3")
    print(f"\nScoring {len(tesla_paths)} Tesla segments manually (psi_dot_rads truth)...")
    yaw_sum_sq, yaw_n = 0.0, 0
    cte_sum_sq, cte_n_bins = 0.0, 0
    per_seg_yaw_rmses = []
    per_seg_cte_rmses = []
    failed = 0

    ALLOWED = {
        "t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
        "a_long_mps2", "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads",
    }

    for p in tesla_paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            failed += 1
            continue
        if "psi_dot_rads" not in df.columns or "v_mps" not in df.columns or "t_s" not in df.columns:
            failed += 1
            continue

        # Build a yaw_rate_pred_rads column from V0 if missing, to mirror grader's input.
        if "yaw_rate_pred_rads" not in df.columns:
            v = df["v_mps"].to_numpy(dtype=float)
            delta = df["delta_road_rad"].to_numpy(dtype=float)
            df["yaw_rate_pred_rads"] = (v / 2.875) * np.tan(delta)
        if "brake_pressed" not in df.columns and "brake_pedal_state" in df.columns:
            df["brake_pressed"] = df["brake_pedal_state"]

        sim_df_agent = df[[c for c in df.columns if c in ALLOWED]]
        pred_df = predict(sim_df_agent, "TESLA_MODEL_3")

        t = df["t_s"].to_numpy(dtype=float)
        v = df["v_mps"].to_numpy(dtype=float)
        truth = df["psi_dot_rads"].to_numpy(dtype=float)
        yr_pred = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float)

        if len(t) < 2 or np.any(np.diff(t) <= 0):
            failed += 1
            continue
        mask_v = v > 2.0
        resid = (yr_pred - truth)[mask_v]
        yaw_sum_sq += float(np.sum(resid ** 2))
        yaw_n += int(mask_v.sum())

        if mask_v.sum() > 0:
            seg_rmse = math.sqrt(float(np.mean(resid ** 2)))
            per_seg_yaw_rmses.append(seg_rmse)

        cte = cte_diagnostics_segment(t, v, truth, yr_pred, grid_step_m=1.0, min_distance_m=20.0)
        cte_sum_sq += cte["sum_sq_m2"]
        cte_n_bins += cte["n_bins"]
        if cte["n_bins"] > 0:
            per_seg_cte_rmses.append(math.sqrt(cte["sum_sq_m2"] / cte["n_bins"]))

    tesla_yaw_rmse = math.sqrt(yaw_sum_sq / yaw_n) if yaw_n > 0 else float("nan")
    tesla_cte_rmse = math.sqrt(cte_sum_sq / cte_n_bins) if cte_n_bins > 0 else float("nan")

    print(f"  Tesla yaw RMSE: {tesla_yaw_rmse:.6f}  CTE RMSE: {tesla_cte_rmse:.6f}  "
          f"n_seg={len(per_seg_yaw_rmses)}  failed={failed}")

    summary["tesla"] = {
        "yaw_rate_rmse": tesla_yaw_rmse,
        "cte_rmse": tesla_cte_rmse,
        "n_segments": len(per_seg_yaw_rmses),
        "n_samples": yaw_n,
        "failed": failed,
    }

    # Combined pooled (sum-of-squares pooling)
    fh_n_samples = result["n_samples"]
    fh_n_bins = sum(int(r["cte_n_bins"]) for _, r in result["per_segment"].iterrows())
    fh_yaw_sum_sq = sum(float(r["yaw_sum_sq"]) for _, r in result["per_segment"].iterrows())
    fh_cte_sum_sq = sum(float(r["cte_sum_sq"]) for _, r in result["per_segment"].iterrows())

    pooled_yaw = math.sqrt((fh_yaw_sum_sq + yaw_sum_sq) / (fh_n_samples + yaw_n))
    pooled_cte = math.sqrt((fh_cte_sum_sq + cte_sum_sq) / (fh_n_bins + cte_n_bins))

    summary["pooled_all_platforms"] = {
        "yaw_rate_rmse": pooled_yaw,
        "cte_rmse": pooled_cte,
        "n_samples": fh_n_samples + yaw_n,
        "n_bins": fh_n_bins + cte_n_bins,
    }
    print(f"\nPOOLED ALL PLATFORMS  yaw RMSE: {pooled_yaw:.6f}  CTE RMSE: {pooled_cte:.6f}")

    with (ROOT / "out" / "score_final.json").open("w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    print(f"Wrote {ROOT / 'out' / 'score_final.json'}")


if __name__ == "__main__":
    main()
