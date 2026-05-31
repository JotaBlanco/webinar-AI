"""Score the final-model predict against full data/sim/segments.

Mimics grader contract: hands predict() only the sim-only allowed columns.
Truth is read from sim/ — psi_dot_rads for Tesla, yaw_rate_meas_rads otherwise.
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa: E402

ALLOWED = ("t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
           "a_long_mps2", "accel_pedal_pct", "brake_pressed",
           "yaw_rate_pred_rads")

TRUTH_COL = {
    "TESLA_MODEL_3": "psi_dot_rads",
    "HYUNDAI_IONIQ_5": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1": "yaw_rate_meas_rads",
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
}


def load_predict(path):
    spec = importlib.util.spec_from_file_location("predict_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.predict


def score(predict_fn, paths, v_thresh=2.0):
    yaw_ss, yaw_n = 0.0, 0
    cte_ss, cte_n = 0.0, 0
    per = {}
    failed = 0
    for p in paths:
        plat = p.parts[-5]
        truth_col = TRUTH_COL.get(plat)
        if not truth_col:
            failed += 1
            continue
        try:
            df = pd.read_csv(p)
        except Exception:
            failed += 1
            continue
        if truth_col not in df.columns:
            failed += 1
            continue
        # Build sim-only-style input
        sim_in_cols = [c for c in ALLOWED if c in df.columns]
        # Many sim/ Tesla CSVs don't have accel_pedal_pct/brake_pressed/yaw_rate_pred_rads.
        # The predict reads only delta_road_rad and v_mps so this is OK.
        # But for full contract parity, fabricate missing cols as NaN.
        agent_df = pd.DataFrame(index=df.index)
        for c in ALLOWED:
            agent_df[c] = df[c] if c in df.columns else np.nan
        try:
            pred = predict_fn(agent_df, plat)
        except Exception as e:
            failed += 1
            print("predict failed", plat, p.name, repr(e))
            continue
        if "yaw_rate_pred_rads" not in pred.columns or len(pred) != len(df):
            failed += 1
            continue
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        yr_t = df[truth_col].to_numpy(float)
        yr_p = pred["yaw_rate_pred_rads"].to_numpy(float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            failed += 1
            continue
        m = v > v_thresh
        if m.any():
            r = yr_p[m] - yr_t[m]
            yaw_ss += float((r * r).sum())
            yaw_n += int(m.sum())
            pd_ = per.setdefault(plat, {"ys": 0.0, "yn": 0, "cs": 0.0, "cn": 0})
            pd_["ys"] += float((r * r).sum())
            pd_["yn"] += int(m.sum())
        cte = cte_diagnostics_segment(t, v, yr_t, yr_p)
        cte_ss += cte["sum_sq_m2"]
        cte_n += cte["n_bins"]
        pd_ = per.setdefault(plat, {"ys": 0.0, "yn": 0, "cs": 0.0, "cn": 0})
        pd_["cs"] += cte["sum_sq_m2"]
        pd_["cn"] += cte["n_bins"]
    return {
        "yaw_rmse": math.sqrt(yaw_ss / yaw_n) if yaw_n else float("nan"),
        "cte_rmse": math.sqrt(cte_ss / cte_n) if cte_n else float("nan"),
        "n_segments": len(paths) - failed,
        "failed": failed,
        "per_platform": {pf: {
            "yaw_rmse": math.sqrt(d["ys"] / d["yn"]) if d["yn"] else float("nan"),
            "cte_rmse": math.sqrt(d["cs"] / d["cn"]) if d["cn"] else float("nan"),
        } for pf, d in per.items()},
    }


def main():
    import time
    paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/*/*/*/sim.csv"))

    # V0 baseline using pre-computed yaw_rate_pred_rads (only available on non-Tesla)
    def v0(sim_df, platform):
        # Tesla psi_dot truth == V0 KS-from-(v,delta), so emulate that everywhere.
        v = sim_df["v_mps"].to_numpy(float)
        d = sim_df["delta_road_rad"].to_numpy(float)
        L = {"TESLA_MODEL_3": 2.875,
             "HYUNDAI_IONIQ_5": 2.875,
             "FORD_MUSTANG_MACH_E_MK1": 2.984,
             "FORD_F_150_LIGHTNING_MK1": 3.70}.get(platform, 2.875)
        return pd.DataFrame({"yaw_rate_pred_rads": (v / L) * np.tan(d)},
                            index=sim_df.index)

    t0 = time.time()
    print("V0 (kinematic single-track, workshop wheelbases):")
    r0 = score(v0, paths)
    print(f"  yaw={r0['yaw_rmse']:.6f}  cte={r0['cte_rmse']:.4f}  n={r0['n_segments']} fail={r0['failed']}")
    for pf, m in r0["per_platform"].items():
        print(f"   {pf}: yaw={m['yaw_rmse']:.5f}  cte={m['cte_rmse']:.3f}")
    print(f"  ({time.time()-t0:.1f}s)")

    predict_fn = load_predict(ROOT / "final-model" / "predict.py")
    t0 = time.time()
    print("\nFinal (steady-state single-track per platform):")
    r = score(predict_fn, paths)
    print(f"  yaw={r['yaw_rmse']:.6f}  cte={r['cte_rmse']:.4f}  n={r['n_segments']} fail={r['failed']}")
    for pf, m in r["per_platform"].items():
        print(f"   {pf}: yaw={m['yaw_rmse']:.5f}  cte={m['cte_rmse']:.3f}")
    print(f"  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
