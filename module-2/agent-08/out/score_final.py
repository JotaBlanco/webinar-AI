"""Score final-model/predict.py against data/sim/segments using out/eval.py.

Also compare to V0 baseline.
"""
import sys
from pathlib import Path
MOD = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-08")
sys.path.insert(0, str(MOD / "out"))
sys.path.insert(0, str(MOD / "final-model"))

import eval as ev  # noqa: E402
from predict import predict as predict_v1  # noqa: E402
from predict_v0 import predict as predict_v0  # noqa: E402

SEG_ROOT = MOD / "data" / "sim" / "segments"


def show(name, predict_fn):
    paths = ev.list_segments(SEG_ROOT)
    r = ev.score(predict_fn, paths)
    print(f"\n=== {name} ===")
    print(f"yaw_rate_rmse = {r['yaw_rate_rmse']:.6f} rad/s")
    print(f"cte_rmse      = {r['cte_rmse']:.4f} m")
    print(f"n_segments    = {r['n_segments']} (failed={r['failed']})")
    for plat, m in r["per_platform"].items():
        print(f"  {plat:30s} yaw={m['yaw_rate_rmse']:.6f}  cte={m['cte_rmse']:.3f}  n={m['n_seg']}")


if __name__ == "__main__":
    show("V0 baseline", predict_v0)
    show("V1 (linear-bicycle + lag)", predict_v1)
