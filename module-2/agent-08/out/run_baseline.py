"""Score V0 baseline against the sim/segments dataset."""

import sys
from pathlib import Path

MOD_ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-08")
sys.path.insert(0, str(MOD_ROOT / "out"))
import eval as ev
from predict_v0 import predict


SEG_ROOT = MOD_ROOT / "data" / "sim" / "segments"


def main():
    paths = ev.list_segments(SEG_ROOT)
    print(f"N segments: {len(paths)}")
    result = ev.score(predict, paths)
    print(f"yaw_rate_rmse = {result['yaw_rate_rmse']:.6f} rad/s")
    print(f"cte_rmse      = {result['cte_rmse']:.4f} m")
    print(f"n_segments    = {result['n_segments']}, failed={result['failed']}")
    print()
    print("per platform:")
    for plat, m in result["per_platform"].items():
        print(f"  {plat:30s} yaw={m['yaw_rate_rmse']:.6f}  cte={m['cte_rmse']:.3f}  n={m['n_seg']}")


if __name__ == "__main__":
    main()
