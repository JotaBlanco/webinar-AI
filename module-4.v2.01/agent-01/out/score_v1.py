"""Score V1 baseline on dev to confirm starting point."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary  # noqa
from _shared.frozen_split import dev_paths  # noqa
from v1_baseline import predict_v1  # noqa

if __name__ == "__main__":
    dev = dev_paths()
    print(f"Scoring V1 on {len(dev)} dev segments")
    res = score(predict_v1, segment_paths=dev)
    print(f"yaw_rate_rmse = {res['yaw_rate_rmse']:.6f}")
    print(f"cte_rmse       = {res['cte_rmse']:.4f}")
    print(format_summary(res))
