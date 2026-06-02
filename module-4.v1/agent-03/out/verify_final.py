"""End-to-end verification: run final-model/predict.py against sim-only/segments contract,
then compute pooled yaw RMSE and CTE RMSE against truth from data/sim/segments."""
from __future__ import annotations
import importlib.util, math, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-03")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_rmse_segment  # type: ignore

spec = importlib.util.spec_from_file_location("final_predict", ROOT / "final-model" / "predict.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
predict = mod.predict

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]
INPUT_COLS = ["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
              "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]

def main():
    total_yaw_sq = total_yaw_n = 0
    total_cte_sq = total_cte_n = 0
    per_plat = {}
    for plat in PLATFORMS:
        base_truth = ROOT / "data" / "sim" / "segments" / plat
        base_only = ROOT / "data" / "sim-only" / "segments" / plat
        truth_paths = sorted(base_truth.rglob("sim.csv"))
        p_sq = p_n = 0; p_csq = p_cn = 0; n_segs = 0
        for tp in truth_paths:
            rel = tp.relative_to(base_truth)
            op = base_only / rel
            if not op.exists(): continue
            df_only = pd.read_csv(op)
            df_truth = pd.read_csv(tp)
            if "yaw_rate_meas_rads" not in df_truth.columns:
                # tesla — skip from scoring but predict
                continue
            # ensure required cols
            for c in INPUT_COLS:
                if c not in df_only.columns: df_only[c] = 0.0
            sim_df = df_only[INPUT_COLS].copy()
            out = predict(sim_df, plat)
            yr_pred = out["yaw_rate_pred_rads"].to_numpy()
            yr_truth = df_truth["yaw_rate_meas_rads"].to_numpy()
            if len(yr_pred) != len(yr_truth): continue
            p_sq += float(np.sum((yr_pred - yr_truth)**2))
            p_n += len(yr_pred)
            sq, nb, _ = cte_rmse_segment(df_truth["t_s"].to_numpy(),
                                          df_truth["v_mps"].to_numpy(),
                                          yr_truth, yr_pred)
            p_csq += sq; p_cn += nb; n_segs += 1
        if p_n:
            per_plat[plat] = {
                "yaw_rmse": math.sqrt(p_sq/p_n),
                "cte_rmse": math.sqrt(p_csq/p_cn) if p_cn else None,
                "n_segments": n_segs,
            }
            total_yaw_sq += p_sq; total_yaw_n += p_n
            total_cte_sq += p_csq; total_cte_n += p_cn
            print(f"{plat}: yaw={per_plat[plat]['yaw_rmse']:.6f}  cte={per_plat[plat]['cte_rmse']:.2f}  segs={n_segs}")
        else:
            print(f"{plat}: skipped (no truth)")
    print(f"\nPOOLED  yaw={math.sqrt(total_yaw_sq/total_yaw_n):.6f}  "
          f"cte={math.sqrt(total_cte_sq/total_cte_n):.2f}")

if __name__ == "__main__":
    main()
