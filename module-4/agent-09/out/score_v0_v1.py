"""Score V0 (passthrough) and V1 baseline. Anchor numbers."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

import pandas as pd
from score import score, format_summary
from v1_baseline import predict_v1


def predict_v0(sim_df, platform):
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()}, index=sim_df.index)


# Collect all sim segments
segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
print(f"Found {len(segs)} segments")

print("\n=== V0 passthrough ===")
res_v0 = score(predict_v0, segment_paths=segs)
print(f"V0  yaw={res_v0['yaw_rate_rmse']:.6f}  cte={res_v0['cte_rmse']:.4f}  n_seg={res_v0['n_segments']}")
for plat, m in res_v0["per_platform"].items():
    print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f} cte={m['cte_rmse']:.3f} bias={m['yaw_residual_mean']:+.5f}")

print("\n=== V1 baseline ===")
res_v1 = score(predict_v1, segment_paths=segs)
print(f"V1  yaw={res_v1['yaw_rate_rmse']:.6f}  cte={res_v1['cte_rmse']:.4f}  n_seg={res_v1['n_segments']}")
for plat, m in res_v1["per_platform"].items():
    print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f} cte={m['cte_rmse']:.3f} bias={m['yaw_residual_mean']:+.5f}")
