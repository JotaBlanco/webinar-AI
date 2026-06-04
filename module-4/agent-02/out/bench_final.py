"""Bench: V0 / V1 / final-model.predict on full pooled dev.

Also dry-runs the final-model predict against sim-only/ to verify contract.
"""
from __future__ import annotations
import sys, math, time
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "final-model"))

from _shared.traj_metrics import cte_rmse_segment
from v1_baseline import predict_v1
import predict as final_predict_mod

SEG_ROOT = ROOT / "data" / "sim" / "segments"
SIMONLY_ROOT = ROOT / "data" / "sim-only" / "segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]


def predict_v0(df, plat): return df["yaw_rate_pred_rads"].to_numpy()
def predict_v1_fn(df, plat): return predict_v1(df, plat)["yaw_rate_pred_rads"].to_numpy()
def predict_final(df, plat): return final_predict_mod.predict(df, plat)["yaw_rate_pred_rads"].to_numpy()


def score(predict_fn, label, root=SEG_ROOT, with_truth=True):
    yaw_ss = yaw_n = 0
    cte_ss = cte_n = 0
    per = defaultdict(lambda: [0.0, 0, 0.0, 0])
    t0 = time.time()
    for plat in PLATFORMS:
        for p in sorted((root / plat).glob("**/sim.csv")):
            df = pd.read_csv(p)
            if with_truth and "yaw_rate_meas_rads" not in df.columns: continue
            yr = predict_fn(df, plat)
            if with_truth:
                truth = df["yaw_rate_meas_rads"].to_numpy()
                v = df["v_mps"].to_numpy()
                t = df["t_s"].to_numpy()
                mask = v > 2.0
                r = yr[mask] - truth[mask]
                yaw_ss += float(np.dot(r, r)); yaw_n += int(mask.sum())
                per[plat][0] += float(np.dot(r, r)); per[plat][1] += int(mask.sum())
                ss, nb, _ = cte_rmse_segment(t, v, truth, yr)
                cte_ss += ss; cte_n += nb
                per[plat][2] += ss; per[plat][3] += nb
    yaw_rmse = math.sqrt(yaw_ss/max(yaw_n,1)) if yaw_n else float('nan')
    cte_rmse = math.sqrt(cte_ss/max(cte_n,1)) if cte_n else float('nan')
    dt = time.time()-t0
    print(f"\n=== {label} === ({dt:.1f}s)")
    print(f"  POOLED yaw={yaw_rmse:.6f}  CTE={cte_rmse:.4f}")
    for plat, (ys, yn, cs, cn) in per.items():
        y = math.sqrt(ys/max(yn,1)) if yn else float('nan')
        c = math.sqrt(cs/max(cn,1)) if cn else float('nan')
        print(f"  {plat:30s} yaw={y:.6f}  CTE={c:.4f}")
    return yaw_rmse, cte_rmse


def contract_check():
    """Run final-predict on sim-only/ (no truth column) to verify it doesn't KeyError."""
    print("\n=== contract check (sim-only/) ===")
    n_ok = n_fail = 0
    for plat in PLATFORMS:
        paths = list((SIMONLY_ROOT / plat).glob("**/sim.csv"))[:3]
        for p in paths:
            df = pd.read_csv(p)
            try:
                out = final_predict_mod.predict(df, plat)
                assert len(out) == len(df), "length mismatch"
                assert "yaw_rate_pred_rads" in out.columns
                n_ok += 1
            except Exception as e:
                print(f"  FAIL {plat}/{p.parent.name}: {e}")
                n_fail += 1
    print(f"  {n_ok} OK, {n_fail} FAIL on sim-only/")


if __name__ == "__main__":
    contract_check()
    score(predict_v0, "V0 baseline")
    v1_y, v1_c = score(predict_v1_fn, "V1 baseline")
    fin_y, fin_c = score(predict_final, "FINAL (refit)")
    print(f"\nDelta vs V1: yaw {fin_y-v1_y:+.6f} ({(fin_y-v1_y)/v1_y*100:+.2f}%)  "
          f"CTE {fin_c-v1_c:+.4f} ({(fin_c-v1_c)/v1_c*100:+.2f}%)")
