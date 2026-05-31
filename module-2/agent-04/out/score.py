"""Score a predict() against sim-only inputs using sim truth.

Truth col:
  - Tesla: 'psi_dot_rads'
  - others: 'yaw_rate_meas_rads'
"""
from __future__ import annotations
import sys, glob, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-04")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa


TRUTH_COL = {
    "TESLA_MODEL_3": "psi_dot_rads",
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1": "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5": "yaw_rate_meas_rads",
}


def _list_sim_only_paths():
    return sorted(glob.glob(str(ROOT / "data/sim-only/segments/*/*/*/*/sim.csv")))


def _platform(p):
    return Path(p).resolve().parents[3].name


def _truth_path(sim_only_path):
    return str(sim_only_path).replace("/sim-only/", "/sim/")


def score(predict_fn, paths=None, sample_filter_v=2.0):
    paths = paths or _list_sim_only_paths()
    rows = []
    failed = 0
    for p in paths:
        plat = _platform(p)
        try:
            sim_in = pd.read_csv(p)
            sim_full = pd.read_csv(_truth_path(p))
        except Exception:
            failed += 1
            continue
        truth_col = TRUTH_COL[plat]
        if truth_col not in sim_full.columns:
            failed += 1
            continue
        t = sim_in["t_s"].to_numpy(float)
        v = sim_in["v_mps"].to_numpy(float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            failed += 1
            continue
        yr_truth = sim_full[truth_col].to_numpy(float)
        try:
            pred = predict_fn(sim_in, plat)
            yr_p = pred["yaw_rate_pred_rads"].to_numpy(float)
        except Exception:
            failed += 1
            continue
        mask = v > sample_filter_v
        if mask.sum() < 2:
            failed += 1
            continue
        r = yr_p[mask] - yr_truth[mask]
        cte = cte_diagnostics_segment(t, v, yr_truth, yr_p)
        rows.append({
            "platform": plat, "path": p,
            "yaw_sum_sq": float((r ** 2).sum()),
            "yaw_sum_signed": float(r.sum()),
            "n_samples": int(mask.sum()),
            "cte_sum_sq": cte["sum_sq_m2"],
            "cte_n_bins": cte["n_bins"],
            "cte_sum_signed": cte["sum_signed_m"],
        })
    seg = pd.DataFrame(rows)
    out = {"failed": failed, "n_segments": len(seg)}
    n = int(seg["n_samples"].sum())
    nb = int(seg["cte_n_bins"].sum())
    out["yaw_rmse"] = math.sqrt(seg["yaw_sum_sq"].sum() / n) if n else float("nan")
    out["cte_rmse"] = math.sqrt(seg["cte_sum_sq"].sum() / nb) if nb else float("nan")
    per_p = {}
    for plat, sub in seg.groupby("platform"):
        nn = int(sub["n_samples"].sum())
        nbn = int(sub["cte_n_bins"].sum())
        per_p[plat] = {
            "yaw_rmse": math.sqrt(sub["yaw_sum_sq"].sum() / nn) if nn else float("nan"),
            "yaw_bias": sub["yaw_sum_signed"].sum() / nn if nn else float("nan"),
            "cte_rmse": math.sqrt(sub["cte_sum_sq"].sum() / nbn) if nbn else float("nan"),
            "cte_signed": sub["cte_sum_signed"].sum() / nbn if nbn else float("nan"),
            "n_seg": int(len(sub)),
        }
    out["per_platform"] = per_p
    out["seg"] = seg
    return out


def baseline_predict(sim_df, platform):
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                        index=sim_df.index)


def main():
    paths = _list_sim_only_paths()
    print(f"found {len(paths)} sim-only segments")
    result = score(baseline_predict, paths)
    print(f"V0 yaw_rmse={result['yaw_rmse']:.6f} rad/s")
    print(f"V0 cte_rmse={result['cte_rmse']:.4f} m")
    print(f"failed: {result['failed']}, n_seg: {result['n_segments']}")
    for plat, m in result["per_platform"].items():
        print(f"  {plat}: yaw_rmse={m['yaw_rmse']:.5f} bias={m['yaw_bias']:+.5f} "
              f"cte_rmse={m['cte_rmse']:.3f} cte_signed={m['cte_signed']:+.3f} n={m['n_seg']}")


if __name__ == "__main__":
    main()
