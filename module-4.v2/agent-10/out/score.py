"""Local scorer: pooled yaw RMSE and pooled distance-resampled CTE RMSE.

Walks data/sim/segments/<PLATFORM>/<route>/<seg>/sim.csv. Uses the truth
column yaw_rate_meas_rads and a user-supplied predict() callable run on a
column-restricted view that mirrors the grading-time contract.
"""
from __future__ import annotations
import sys
import math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-10")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))

from traj_metrics import cte_rmse_segment  # noqa: E402

ALLOWED_COLS = [
    "t_s", "delta_wheel_deg", "delta_road_rad", "v_mps", "a_long_mps2",
    "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads",
]

DATA_SIM = ROOT / "data" / "sim" / "segments"


def iter_segments(platforms=None):
    for plat_dir in sorted(DATA_SIM.iterdir()):
        if not plat_dir.is_dir():
            continue
        if platforms and plat_dir.name not in platforms:
            continue
        for route_dir in sorted(plat_dir.iterdir()):
            if not route_dir.is_dir():
                continue
            for sub in sorted(route_dir.iterdir()):
                if not sub.is_dir():
                    continue
                for seg in sorted(sub.iterdir()):
                    f = seg / "sim.csv"
                    if f.is_file():
                        yield plat_dir.name, route_dir.name, seg.name, f


def score(predict_fn, platforms=None, limit_per_platform=None, verbose=False):
    yaw_sse = 0.0
    yaw_n = 0
    cte_sse = 0.0
    cte_bins = 0
    per_plat = {}
    counts = {}
    for plat, route, seg, f in iter_segments(platforms=platforms):
        c = counts.get(plat, 0)
        if limit_per_platform and c >= limit_per_platform:
            continue
        counts[plat] = c + 1
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        truth = df["yaw_rate_meas_rads"].to_numpy()
        # Build the allow-list view, filling missing optional cols with zeros.
        sim_in = pd.DataFrame(index=df.index)
        for c in ALLOWED_COLS:
            if c in df.columns:
                sim_in[c] = df[c].to_numpy()
            else:
                sim_in[c] = 0.0
        try:
            pred_out = predict_fn(sim_in, plat)
        except Exception as e:
            if verbose:
                print(f"predict failed on {plat}/{route}/{seg}: {e}")
            continue
        pred = pred_out["yaw_rate_pred_rads"].to_numpy()
        if pred.shape != truth.shape:
            continue
        # yaw rmse pooled
        d = pred - truth
        yaw_sse += float(np.sum(d * d))
        yaw_n += len(d)
        # cte
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        sum_sq, n_bins, total = cte_rmse_segment(t, v, truth, pred)
        cte_sse += sum_sq
        cte_bins += n_bins
        pp = per_plat.setdefault(plat, {"yaw_sse": 0.0, "yaw_n": 0, "cte_sse": 0.0, "cte_bins": 0, "n_seg": 0})
        pp["yaw_sse"] += float(np.sum(d * d))
        pp["yaw_n"] += len(d)
        pp["cte_sse"] += sum_sq
        pp["cte_bins"] += n_bins
        pp["n_seg"] += 1
    yaw_rmse = math.sqrt(yaw_sse / yaw_n) if yaw_n else float("nan")
    cte_rmse = math.sqrt(cte_sse / cte_bins) if cte_bins else float("nan")
    out = {"yaw_rmse": yaw_rmse, "cte_rmse": cte_rmse, "yaw_n": yaw_n, "cte_bins": cte_bins, "per_plat": {}}
    for k, v in per_plat.items():
        out["per_plat"][k] = {
            "yaw_rmse": math.sqrt(v["yaw_sse"] / v["yaw_n"]) if v["yaw_n"] else float("nan"),
            "cte_rmse": math.sqrt(v["cte_sse"] / v["cte_bins"]) if v["cte_bins"] else float("nan"),
            "n_seg": v["n_seg"],
        }
    return out


if __name__ == "__main__":
    from v1_baseline import predict_v1

    def v0(sim_df, platform):
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()}, index=sim_df.index)

    print("V0 (passthrough):")
    print(score(v0))
    print("V1:")
    print(score(predict_v1))
