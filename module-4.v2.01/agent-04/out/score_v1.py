"""Score V1 baseline on dev split — sanity check on the cohort floor."""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TPL  = HERE.parent
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))

from _shared.frozen_split import dev_paths
from score import score, format_summary

sys.path.insert(0, str(TPL / "code"))
from v1_baseline import predict_v1

dev = dev_paths()
print(f"V1 eval — {len(dev)} dev segments")
result = score(predict_v1, segment_paths=dev)
print(format_summary(result))

with (HERE / "score_v1.json").open("w") as f:
    json.dump({
        "yaw_rate_rmse": result["yaw_rate_rmse"],
        "cte_rmse": result["cte_rmse"],
        "per_platform": {p: {k: stats[k] for k in ("yaw_rate_rmse","cte_rmse","yaw_residual_mean") if k in stats}
                          for p, stats in result["per_platform"].items()},
    }, f, indent=2, default=str)
