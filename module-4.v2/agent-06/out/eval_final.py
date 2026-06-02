"""Evaluate final-model/predict.py end-to-end against data/sim/segments/ truth.

Mimics the operating contract: passes the predict() function only the 8
allowlist columns from sim_df (no truth, no residual channels).

Reports pooled yaw RMSE and pooled distance-resampled CTE RMSE per platform
and overall, comparing V1 to the corrected model.
"""
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-06")

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

predict_mod = _load("final_predict", str(ROOT / "final-model" / "predict.py"))
v1_mod = _load("v1_baseline", str(ROOT / "code" / "v1_baseline.py"))
tm = _load("traj_metrics", str(ROOT / "_shared" / "traj_metrics.py"))

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]
ALLOWLIST = ["t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
             "a_long_mps2", "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads"]


def main():
    # Use the same 80/20 seg split as fit, but with the same seed.
    pooled = {
        "v1": {"yr_sse": 0.0, "yr_n": 0, "cte_ss": 0.0, "cte_bins": 0},
        "new": {"yr_sse": 0.0, "yr_n": 0, "cte_ss": 0.0, "cte_bins": 0},
    }
    by_platform = {}
    for platform in PLATFORMS:
        seg_files = sorted((ROOT / "data" / "sim" / "segments" / platform).rglob("sim.csv"))
        # split by file index, same RNG seed as fit
        rng = np.random.RandomState(42)
        idx = list(range(len(seg_files)))
        rng.shuffle(idx)
        n_train = int(0.8 * len(idx))
        dev_idx = set(idx[n_train:])
        dev_files = [seg_files[i] for i in sorted(dev_idx)]

        ppl = {"v1_yr_sse": 0.0, "v1_yr_n": 0, "new_yr_sse": 0.0, "new_yr_n": 0,
               "v1_cte_ss": 0.0, "v1_cte_bins": 0, "new_cte_ss": 0.0, "new_cte_bins": 0}

        for f in dev_files:
            try:
                df = pd.read_csv(f)
            except Exception:
                continue
            if "yaw_rate_meas_rads" not in df.columns and platform != "TESLA_MODEL_3":
                continue
            # Ensure allowlist cols present
            for c in ALLOWLIST:
                if c not in df.columns:
                    df[c] = 0.0
            sim_in = df[ALLOWLIST].copy().reset_index(drop=True)
            t = sim_in["t_s"].to_numpy()
            v = sim_in["v_mps"].to_numpy()
            if len(t) < 5:
                continue

            # V1
            v1_out = v1_mod.predict_v1(sim_in, platform)
            yr_v1 = v1_out["yaw_rate_pred_rads"].to_numpy()

            # New (final-model)
            new_out = predict_mod.predict(sim_in, platform)
            yr_new = new_out["yaw_rate_pred_rads"].to_numpy()

            if "yaw_rate_meas_rads" in df.columns:
                yr_truth = df["yaw_rate_meas_rads"].to_numpy()
                # yaw RMSE accumulators
                ppl["v1_yr_sse"] += float(np.sum((yr_truth - yr_v1) ** 2))
                ppl["v1_yr_n"] += len(yr_truth)
                ppl["new_yr_sse"] += float(np.sum((yr_truth - yr_new) ** 2))
                ppl["new_yr_n"] += len(yr_truth)
                # CTE
                ss1, nb1, _ = tm.cte_rmse_segment(t, v, yr_truth, yr_v1)
                ss2, nb2, _ = tm.cte_rmse_segment(t, v, yr_truth, yr_new)
                ppl["v1_cte_ss"] += ss1
                ppl["v1_cte_bins"] += nb1
                ppl["new_cte_ss"] += ss2
                ppl["new_cte_bins"] += nb2

        if ppl["v1_yr_n"]:
            v1_yr = math.sqrt(ppl["v1_yr_sse"] / ppl["v1_yr_n"])
            new_yr = math.sqrt(ppl["new_yr_sse"] / ppl["new_yr_n"])
            v1_cte = math.sqrt(ppl["v1_cte_ss"] / ppl["v1_cte_bins"]) if ppl["v1_cte_bins"] else None
            new_cte = math.sqrt(ppl["new_cte_ss"] / ppl["new_cte_bins"]) if ppl["new_cte_bins"] else None
            by_platform[platform] = {
                "v1_yaw_rmse": v1_yr, "new_yaw_rmse": new_yr,
                "v1_cte_rmse": v1_cte, "new_cte_rmse": new_cte,
                "yaw_improvement_pct": 100 * (v1_yr - new_yr) / v1_yr if v1_yr else 0,
                "cte_improvement_pct": 100 * (v1_cte - new_cte) / v1_cte if v1_cte else 0,
            }
            pooled["v1"]["yr_sse"] += ppl["v1_yr_sse"]; pooled["v1"]["yr_n"] += ppl["v1_yr_n"]
            pooled["new"]["yr_sse"] += ppl["new_yr_sse"]; pooled["new"]["yr_n"] += ppl["new_yr_n"]
            pooled["v1"]["cte_ss"] += ppl["v1_cte_ss"]; pooled["v1"]["cte_bins"] += ppl["v1_cte_bins"]
            pooled["new"]["cte_ss"] += ppl["new_cte_ss"]; pooled["new"]["cte_bins"] += ppl["new_cte_bins"]
        else:
            by_platform[platform] = {"note": "no truth available (Tesla) or skipped"}

    overall = {}
    if pooled["v1"]["yr_n"]:
        overall["v1_yaw_rmse"] = math.sqrt(pooled["v1"]["yr_sse"] / pooled["v1"]["yr_n"])
        overall["new_yaw_rmse"] = math.sqrt(pooled["new"]["yr_sse"] / pooled["new"]["yr_n"])
        overall["yaw_improvement_pct"] = 100 * (overall["v1_yaw_rmse"] - overall["new_yaw_rmse"]) / overall["v1_yaw_rmse"]
    if pooled["v1"]["cte_bins"]:
        overall["v1_cte_rmse"] = math.sqrt(pooled["v1"]["cte_ss"] / pooled["v1"]["cte_bins"])
        overall["new_cte_rmse"] = math.sqrt(pooled["new"]["cte_ss"] / pooled["new"]["cte_bins"])
        overall["cte_improvement_pct"] = 100 * (overall["v1_cte_rmse"] - overall["new_cte_rmse"]) / overall["v1_cte_rmse"]

    import json
    print("=== Per platform (dev split, 20% of segments) ===")
    print(json.dumps(by_platform, indent=2))
    print("\n=== Pooled overall (fittable platforms) ===")
    print(json.dumps(overall, indent=2))

    (ROOT / "out" / "eval_final.json").write_text(json.dumps({
        "per_platform": by_platform, "pooled": overall,
    }, indent=2))


if __name__ == "__main__":
    main()
