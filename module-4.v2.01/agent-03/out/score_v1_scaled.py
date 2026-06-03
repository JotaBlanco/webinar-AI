"""Score V1 with per-platform multiplicative yaw scale, on DEV."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
TPL = HERE.parent
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))
sys.path.insert(0, str(TPL / "final-model"))

from _shared.frozen_split import dev_paths  # noqa
from score import score, format_summary  # noqa
from predict import predict as v1_predict  # noqa

SCALES = json.loads((HERE / "yaw_scales.json").read_text())


def scaled_predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = v1_predict(sim_df, platform)
    k = SCALES.get(platform, 1.0)
    out = out.copy()
    out["yaw_rate_pred_rads"] = out["yaw_rate_pred_rads"] * k
    return out


def main() -> int:
    dev = dev_paths()
    print(f"V1-scaled eval — {len(dev)} dev segments")
    result = score(scaled_predict, segment_paths=dev)
    print(format_summary(result))
    out = {
        "model": "v1_scaled",
        "scales": SCALES,
        "yaw_rate_rmse": result["yaw_rate_rmse"],
        "cte_rmse": result["cte_rmse"],
        "n_segments": result["n_segments"],
        "per_platform": {
            plat: {
                "yaw_rate_rmse": stats["yaw_rate_rmse"],
                "cte_rmse": stats["cte_rmse"],
            }
            for plat, stats in result["per_platform"].items()
        },
    }
    (HERE / "v1_scaled_scorecard.json").write_text(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
