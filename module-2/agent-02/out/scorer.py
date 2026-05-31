"""Local scorer that works against our data layout (sim/segments).

Calls a `predict(sim_df, platform) -> DataFrame` and computes:
- pooled yaw-rate RMSE (rad/s), filter v > 2 m/s
- pooled distance-resampled CTE RMSE (m)
Strips inputs to the allowlist so the contract matches sim-only/grading.
"""
from __future__ import annotations
import sys, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa

ALLOWED = frozenset({
    "t_s", "delta_wheel_deg", "delta_road_rad", "v_mps", "a_long_mps2",
    "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads",
})

SIM_ROOT = ROOT / "data" / "sim" / "segments"


def segment_paths(platforms=None):
    paths = []
    plats = platforms or [d.name for d in SIM_ROOT.iterdir() if d.is_dir()]
    for plat in plats:
        for p in sorted((SIM_ROOT / plat).glob("**/sim.csv")):
            paths.append(p)
    return paths


def _platform_from_path(p: Path) -> str:
    # .../data/sim/segments/<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv
    return p.parents[3].name


def score(predict_fn, paths=None, platforms=None, v_min=2.0,
          grid_step_m=1.0, min_distance_m=20.0, max_segments=None):
    if paths is None:
        paths = segment_paths(platforms)
    if max_segments:
        paths = paths[:max_segments]

    rows = []
    failed = 0
    for p in paths:
        platform = _platform_from_path(p)
        try:
            sim_df = pd.read_csv(p)
        except Exception:
            failed += 1; continue
        if "yaw_rate_meas_rads" not in sim_df.columns:
            failed += 1; continue

        sim_agent = sim_df[[c for c in sim_df.columns if c in ALLOWED]].copy()
        # Ensure brake_pressed exists
        if "brake_pressed" not in sim_agent.columns and "brake_pedal_state" in sim_df.columns:
            sim_agent["brake_pressed"] = (sim_df["brake_pedal_state"] > 0).astype(int)
        try:
            pred = predict_fn(sim_agent, platform)
        except Exception as e:
            failed += 1; continue
        if not isinstance(pred, pd.DataFrame) or "yaw_rate_pred_rads" not in pred.columns:
            failed += 1; continue
        if len(pred) != len(sim_df):
            failed += 1; continue

        t = sim_df["t_s"].to_numpy(float)
        v = sim_df["v_mps"].to_numpy(float)
        yr_t = sim_df["yaw_rate_meas_rads"].to_numpy(float)
        yr_p = pred["yaw_rate_pred_rads"].to_numpy(float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            failed += 1; continue
        mask = v > v_min
        if not mask.any():
            continue
        resid = yr_p - yr_t
        rv = resid[mask]
        n = int(mask.sum())
        sum_sq = float(np.sum(rv**2))
        sum_signed = float(np.sum(rv))

        cte = cte_diagnostics_segment(t, v, yr_t, yr_p, grid_step_m, min_distance_m)
        rows.append({
            "path": str(p), "platform": platform, "n": n,
            "yaw_sum_sq": sum_sq, "yaw_sum_signed": sum_signed,
            "cte_sum_sq": cte["sum_sq_m2"], "cte_n_bins": cte["n_bins"],
            "distance_m": cte["total_distance_m"],
        })

    seg = pd.DataFrame(rows)
    if seg.empty:
        return {"yaw_rate_rmse": float("nan"), "cte_rmse": float("nan"),
                "n_segments": 0, "failed": failed}
    yaw = math.sqrt(seg["yaw_sum_sq"].sum() / seg["n"].sum())
    cte = math.sqrt(seg["cte_sum_sq"].sum() / seg["cte_n_bins"].sum()) if seg["cte_n_bins"].sum() else float("nan")
    per_plat = {}
    for plat, sub in seg.groupby("platform"):
        n = sub["n"].sum(); nb = sub["cte_n_bins"].sum()
        per_plat[plat] = {
            "yaw_rate_rmse": math.sqrt(sub["yaw_sum_sq"].sum() / n) if n else float("nan"),
            "yaw_bias": float(sub["yaw_sum_signed"].sum() / n) if n else float("nan"),
            "cte_rmse": math.sqrt(sub["cte_sum_sq"].sum() / nb) if nb else float("nan"),
            "n_seg": int(len(sub)),
        }
    return {"yaw_rate_rmse": yaw, "cte_rmse": cte,
            "n_segments": int(len(seg)), "failed": failed,
            "per_platform": per_plat, "seg": seg}


def v0_predict(sim_df, platform):
    """Identity baseline: predicts equal to the supplied yaw_rate_pred_rads."""
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                        index=sim_df.index)


if __name__ == "__main__":
    res = score(v0_predict)
    print(f"V0 yaw_rate_rmse: {res['yaw_rate_rmse']:.6f} rad/s")
    print(f"V0 cte_rmse: {res['cte_rmse']:.4f} m")
    print(f"n_segments: {res['n_segments']}, failed: {res['failed']}")
    for plat, m in res["per_platform"].items():
        print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f}  bias={m['yaw_bias']:+.5f}  cte={m['cte_rmse']:.3f}  n_seg={m['n_seg']}")
