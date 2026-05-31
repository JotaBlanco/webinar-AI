"""Score the V1 final-model predict."""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-08")
os.chdir(ROOT)

# load score-model
spec_s = importlib.util.spec_from_file_location("score_model", str(ROOT / "skills/score-model/score.py"))
score_mod = importlib.util.module_from_spec(spec_s)
spec_s.loader.exec_module(score_mod)

# load predict
spec_p = importlib.util.spec_from_file_location("final_predict", str(ROOT / "final-model/predict.py"))
predict_mod = importlib.util.module_from_spec(spec_p)
spec_p.loader.exec_module(predict_mod)


if __name__ == "__main__":
    result = score_mod.score(predict_mod.predict)
    print(score_mod.format_summary(result))
    print("\n=== V1 HEADLINE ===")
    print(f"yaw_rate_rmse: {result['yaw_rate_rmse']:.6f}")
    print(f"cte_rmse:      {result['cte_rmse']:.4f}")
    print(f"n_segments:    {result['n_segments']}, failed: {result['failed_segments']}")
    print(f"failed_by_platform: {result['failed_by_platform']}")
