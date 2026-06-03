"""Score M4 against the frozen dev split via skills/score-model.

Writes scorecard.json (machine-readable) and prints the human summary.
Reads coeffs.json next to this file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TPL  = HERE.parents[3]
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))

from _shared.frozen_split import dev_paths  # noqa: E402
from score import score, format_summary  # noqa: E402

from model import predict_factory  # noqa: E402


def main() -> int:
    coeffs_path = HERE / "coeffs.json"
    with coeffs_path.open() as f:
        coeffs = json.load(f)

    def predict_fn(sim_df, platform):
        c = coeffs.get(platform, {})
        yr = predict_factory(platform, c)(sim_df)
        import pandas as pd
        out = sim_df[["yaw_rate_pred_rads"]].copy()
        out["yaw_rate_pred_rads"] = yr
        return out

    dev = dev_paths()
    print(f"M4 eval — {len(dev)} dev segments")

    result = score(predict_fn, segment_paths=dev)
    print(format_summary(result))

    scorecard = {
        "model": "m4-relaxation-length",
        "split": "dev",
        "n_segments": result["n_segments"],
        "yaw_rate_rmse": result["yaw_rate_rmse"],
        "cte_rmse": result["cte_rmse"],
        "per_platform": {
            plat: {
                "yaw_rate_rmse":      stats["yaw_rate_rmse"],
                "yaw_residual_mean":  stats["yaw_residual_mean"],
                "yaw_bias_fraction":  stats.get("bias_fraction"),
                "cte_rmse":           stats["cte_rmse"],
                "cte_signed_drift":   stats.get("cte_signed_drift_m"),
            }
            for plat, stats in result["per_platform"].items()
        },
        "bias_warnings": result.get("bias_warnings", []),
        "n_failed_segments": result.get("failed_segments", 0)
                              if isinstance(result.get("failed_segments"), int)
                              else len(result.get("failed_segments") or []),
    }
    out_path = HERE / "scorecard.json"
    with out_path.open("w") as f:
        json.dump(scorecard, f, indent=2, default=str)
    print(f"\nwrote {out_path.relative_to(TPL.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
