"""Score final-model/predict.py through the harness."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary
from predict import predict


segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
res = score(predict, segment_paths=segs)
print(f"FINAL  yaw={res['yaw_rate_rmse']:.6f}  cte={res['cte_rmse']:.4f}  n_seg={res['n_segments']}")
for plat, m in res["per_platform"].items():
    print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f} cte={m['cte_rmse']:.3f} bias={m['yaw_residual_mean']:+.5f}")
