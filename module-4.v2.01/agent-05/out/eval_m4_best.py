"""Full-dev eval of M4 with sigma=0.3 across platforms."""
from __future__ import annotations
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TPL = HERE.parent
M4 = TPL / "phases" / "3-implement" / "models" / "m4-relaxation-length"

sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))
sys.path.insert(0, str(M4))

from _shared.frozen_split import dev_paths  # noqa: E402
from score import score, format_summary  # noqa: E402
from model import predict_factory  # noqa: E402

with (HERE / "m4_best_coeffs.json").open() as f:
    COEFFS = json.load(f)


def predict_fn(sim_df, platform):
    c = COEFFS.get(platform, {})
    yr = predict_factory(platform, c)(sim_df)
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = yr
    return out


dev = dev_paths()
print(f"M4 sigma=0.3 dev — {len(dev)} segments")
res = score(predict_fn, segment_paths=dev)
print(format_summary(res))

scorecard = {
    "model": "m4-relaxation-length-sigma03",
    "yaw_rate_rmse": res["yaw_rate_rmse"],
    "cte_rmse": res["cte_rmse"],
    "per_platform": {
        p: {"yaw_rate_rmse": m["yaw_rate_rmse"], "cte_rmse": m["cte_rmse"]}
        for p, m in res["per_platform"].items()
    },
}
with (HERE / "m4_best_scorecard.json").open("w") as f:
    json.dump(scorecard, f, indent=2)
