"""Score shipped V1 predict.py on the frozen TEST split (preflight --final).
Run only once."""
from __future__ import annotations
import json, sys, os
from pathlib import Path

os.environ["FROZEN_SPLIT_ALLOW_TEST"] = "1"

HERE = Path(__file__).resolve().parent
TPL  = HERE.parent
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))
sys.path.insert(0, str(TPL / "final-model"))

from _shared.frozen_split import test_paths
from score import score, format_summary
from predict import predict

test = test_paths()
print(f"TEST split: {len(test)} segments")
result = score(predict, segment_paths=test)
print(format_summary(result))

out = {
    "split": "test",
    "yaw_rate_rmse": result["yaw_rate_rmse"],
    "cte_rmse": result["cte_rmse"],
    "per_platform": {p: {"yaw_rate_rmse": s["yaw_rate_rmse"], "cte_rmse": s["cte_rmse"]} for p, s in result["per_platform"].items()},
}
with (HERE / "score_v1_test.json").open("w") as f:
    json.dump(out, f, indent=2, default=str)
print(f"wrote {HERE/'score_v1_test.json'}")
