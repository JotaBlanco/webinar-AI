"""Evaluate V0 and V1 on train/dev/all using the canonical score skill."""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/score-model"))
sys.path.insert(0, str(ROOT / "skills/make-train-dev-split"))
sys.path.insert(0, str(ROOT / "final-model"))
sys.path.insert(0, str(ROOT / "_shared"))

from score import score
from split import split as make_split
import predict as final_predict

def predict_v0(sim_df, platform):
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].values},
                        index=sim_df.index)

train_paths, dev_paths = make_split(dev_fraction=0.25, seed=42)
print(f"train={len(train_paths)} dev={len(dev_paths)}")

for name, paths in [("ALL", None), ("DEV", dev_paths), ("TRAIN", train_paths)]:
    print(f"\n========== {name} ==========")
    r0 = score(predict_v0, segment_paths=paths)
    r1 = score(final_predict.predict, segment_paths=paths)
    print(f"V0 overall yaw RMSE = {r0['yaw_rate_rmse']:.6f}  CTE RMSE = {r0['cte_rmse']:.4f}")
    print(f"V1 overall yaw RMSE = {r1['yaw_rate_rmse']:.6f}  CTE RMSE = {r1['cte_rmse']:.4f}")
    for plat in r0['per_platform']:
        a = r0['per_platform'][plat]
        b = r1['per_platform'][plat]
        print(f"  {plat}:")
        print(f"    V0: yaw RMSE={a['yaw_rate_rmse']:.6f}  CTE={a['cte_rmse']:.4f}")
        print(f"    V1: yaw RMSE={b['yaw_rate_rmse']:.6f}  CTE={b['cte_rmse']:.4f}")
    print("  per-regime V0:", {k: round(v['yaw_rate_rmse'],5) for k,v in r0['per_regime'].items()})
    print("  per-regime V1:", {k: round(v['yaw_rate_rmse'],5) for k,v in r1['per_regime'].items()})
    print(f"  n_segments={r1['n_segments']} failed={r1.get('failed_segments',0)}")
