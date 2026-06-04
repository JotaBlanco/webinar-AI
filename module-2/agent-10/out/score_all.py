"""Score V0, V1, V2 against full sim dataset."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-10")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))

from score import score, format_summary  # noqa: E402
from v0_predict import predict as predict_v0  # noqa: E402
from predict_v import predict_v1, predict_v2, predict_v3  # noqa: E402

seg_root = ROOT / "data" / "sim" / "segments"
seg_paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
print(f"Found {len(seg_paths)} segments")

for name, fn in (("V0", predict_v0), ("V1", predict_v1), ("V2", predict_v2), ("V3", predict_v3)):
    r = score(fn, segment_paths=seg_paths)
    print(f"\n=== {name} ===")
    print(f"yaw_rate_rmse: {r['yaw_rate_rmse']:.6f}  cte_rmse: {r['cte_rmse']:.4f}")
    for plat, m in r["per_platform"].items():
        print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f} bias={m['yaw_residual_mean']:+.5f} cte={m['cte_rmse']:.3f} drift={m['cte_signed_mean']:+.3f}")
