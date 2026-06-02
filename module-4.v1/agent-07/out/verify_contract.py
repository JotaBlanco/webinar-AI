"""Verify final-model/predict.py against the operating contract.

Loads sim-only/ files (8-col input-only), runs predict(), confirms shape + that
no truth columns are required. Then scores against the matching sim/ truth.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-07")
sys.path.insert(0, str(ROOT / "final-model"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))

from predict import predict  # noqa: E402
from traj_metrics import cte_rmse_segment  # noqa: E402

PLATFORMS = ["TESLA_MODEL_3", "FORD_F_150_LIGHTNING_MK1",
             "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def truth_for(platform: str, sim_only_path: Path) -> tuple[np.ndarray, np.ndarray] | None:
    """Find the matching sim/ file to get truth. Tesla -> psi_dot_rads,
    others -> yaw_rate_meas_rads."""
    rel = sim_only_path.relative_to(ROOT / "data" / "sim-only" / "segments")
    sim_path = ROOT / "data" / "sim" / "segments" / rel
    if not sim_path.exists():
        return None
    df = pd.read_csv(sim_path)
    if platform == "TESLA_MODEL_3":
        if "psi_dot_rads" not in df.columns:
            return None
        return df["t_s"].to_numpy(), df["psi_dot_rads"].to_numpy()
    if "yaw_rate_meas_rads" not in df.columns:
        return None
    return df["t_s"].to_numpy(), df["yaw_rate_meas_rads"].to_numpy()


def main():
    overall_sse_yaw = 0.0; overall_n_yaw = 0
    overall_sse_cte = 0.0; overall_n_cte = 0
    for plat in PLATFORMS:
        base = ROOT / "data" / "sim-only" / "segments" / plat
        paths = sorted(base.rglob("sim.csv"))
        # Sample 150 segments per platform deterministically
        step = max(1, len(paths) // 150)
        paths = paths[::step][:150]
        sse_yaw = 0.0; n_yaw = 0
        sse_cte = 0.0; n_cte = 0
        sse_v1 = 0.0
        sse_cte_v1 = 0.0; n_cte_v1 = 0
        for p in paths:
            df = pd.read_csv(p)
            # Hard contract check: only 8 standard columns must be present.
            assert "yaw_rate_meas_rads" not in df.columns
            assert "psi_dot_rads" not in df.columns
            pred = predict(df.copy(), plat)
            assert "yaw_rate_pred_rads" in pred.columns
            assert len(pred) == len(df)
            tr = truth_for(plat, p)
            if tr is None:
                continue
            _, truth = tr
            if len(truth) != len(df):
                continue
            yr_pred = pred["yaw_rate_pred_rads"].to_numpy()
            v1 = df["yaw_rate_pred_rads"].to_numpy()
            v = df["v_mps"].to_numpy()
            t = df["t_s"].to_numpy()
            e = yr_pred - truth
            sse_yaw += float(np.sum(e * e)); n_yaw += len(e)
            sse_v1 += float(np.sum((v1 - truth) ** 2))
            ss, nb, _ = cte_rmse_segment(t, v, truth, yr_pred)
            sse_cte += ss; n_cte += nb
            ss1, nb1, _ = cte_rmse_segment(t, v, truth, v1)
            sse_cte_v1 += ss1; n_cte_v1 += nb1
        yaw_pred = np.sqrt(sse_yaw / n_yaw) if n_yaw else float("nan")
        yaw_v1 = np.sqrt(sse_v1 / n_yaw) if n_yaw else float("nan")
        cte_pred = np.sqrt(sse_cte / n_cte) if n_cte else float("nan")
        cte_v1 = np.sqrt(sse_cte_v1 / n_cte_v1) if n_cte_v1 else float("nan")
        print(f"  {plat}: yaw V1={yaw_v1:.5f} -> pred={yaw_pred:.5f}  "
              f"({100*(yaw_v1-yaw_pred)/max(yaw_v1,1e-9):+.1f}%)  "
              f"cte V1={cte_v1:.2f} -> pred={cte_pred:.2f}  "
              f"({100*(cte_v1-cte_pred)/max(cte_v1,1e-9):+.1f}%)")
        overall_sse_yaw += sse_yaw; overall_n_yaw += n_yaw
        overall_sse_cte += sse_cte; overall_n_cte += n_cte
    print(f"\nPOOLED (sim-only): yaw={np.sqrt(overall_sse_yaw/overall_n_yaw):.5f}, "
          f"cte={np.sqrt(overall_sse_cte/overall_n_cte):.3f}")


if __name__ == "__main__":
    main()
