"""Score V1 baseline on dev split."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
TPL = HERE.parents[0]
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))
sys.path.insert(0, str(TPL / "code"))

from _shared.frozen_split import dev_paths
from score import score, format_summary
from v1_baseline import predict_v1

def predict_fn(sim_df, platform):
    return predict_v1(sim_df, platform)

dev = dev_paths()
print(f"V1 eval — {len(dev)} dev segments")
result = score(predict_fn, segment_paths=dev)
print(format_summary(result))

import json
with open(HERE / "v1_scorecard.json", "w") as f:
    json.dump({
        "yaw_rate_rmse": result["yaw_rate_rmse"],
        "cte_rmse": result["cte_rmse"],
        "per_platform": {k: {kk: vv for kk, vv in v.items() if isinstance(vv,(int,float,str)) or vv is None}
                         for k, v in result["per_platform"].items()},
    }, f, indent=2, default=str)
