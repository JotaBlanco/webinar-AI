"""Score the shipped final-model/predict.py via score-model."""
from __future__ import annotations
import sys
import importlib.util
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-02")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary  # noqa: E402

spec = importlib.util.spec_from_file_location("finalpredict", str(ROOT / "final-model" / "predict.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

seg_root = ROOT / "data" / "sim" / "segments"
seg_paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
r = score(m.predict, segment_paths=seg_paths)
print(f"FINAL yaw_rate_rmse: {r['yaw_rate_rmse']:.6f} rad/s")
print(f"FINAL cte_rmse:      {r['cte_rmse']:.4f} m")
print(f"n_segments={r['n_segments']}, failed={r['failed_segments']}")
for plat, pm in r["per_platform"].items():
    print(f"  {plat}: yaw={pm['yaw_rate_rmse']:.5f}  cte={pm['cte_rmse']:.3f}  n={pm['n_segments']}")
