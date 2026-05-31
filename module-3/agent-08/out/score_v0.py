"""V0 passthrough scoring baseline."""
import sys
import os
import importlib.util
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-08")
os.chdir(ROOT)

spec = importlib.util.spec_from_file_location("score_model", str(ROOT / "skills/score-model/score.py"))
score_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score_mod)


def predict_v0(sim_df, platform):
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    return out


if __name__ == "__main__":
    result = score_mod.score(predict_v0)
    print(score_mod.format_summary(result))
    print("\n=== HEADLINE ===")
    print(f"yaw_rate_rmse: {result['yaw_rate_rmse']:.6f}")
    print(f"cte_rmse:      {result['cte_rmse']:.4f}")
    print(f"n_segments:    {result['n_segments']}, failed: {result['failed_segments']}")
    print(f"failed_by_platform: {result['failed_by_platform']}")
