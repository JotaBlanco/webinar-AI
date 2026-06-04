"""Score the final-model predict against sim-only/."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-04")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "final-model"))

import os
os.chdir(ROOT)

from score import score, format_summary
import predict as predict_mod


if __name__ == "__main__":
    # Score against the canonical default paths (data/sim/segments) and also try sim-only.
    result = score(predict_mod.predict)
    print(format_summary(result))
    print("\nHEADLINE FINAL:")
    print(f"  yaw_rate_rmse = {result['yaw_rate_rmse']:.6f}")
    print(f"  cte_rmse      = {result['cte_rmse']:.4f}")
