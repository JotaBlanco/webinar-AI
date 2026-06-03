"""Score V1 baseline on dev split."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TPL = HERE.parent
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))
sys.path.insert(0, str(TPL / "code"))

from _shared.frozen_split import dev_paths  # noqa
from score import score, format_summary  # noqa
from v1_baseline import predict_v1  # noqa


def main() -> int:
    dev = dev_paths()
    print(f"V1 baseline eval — {len(dev)} dev segments")
    result = score(predict_v1, segment_paths=dev)
    print(format_summary(result))
    out = {
        "model": "v1_baseline",
        "yaw_rate_rmse": result["yaw_rate_rmse"],
        "cte_rmse": result["cte_rmse"],
        "n_segments": result["n_segments"],
        "per_platform": {
            plat: {
                "yaw_rate_rmse": stats["yaw_rate_rmse"],
                "cte_rmse": stats["cte_rmse"],
                "yaw_residual_mean": stats.get("yaw_residual_mean"),
                "cte_signed_drift_m": stats.get("cte_signed_drift_m"),
            }
            for plat, stats in result["per_platform"].items()
        },
    }
    (HERE / "v1_scorecard.json").write_text(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
