"""Score final-model/predict against full segment set."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01")
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "final-model"))
sys.path.insert(0, str(ROOT / "out"))

from predict import predict as final_predict
from score_v0 import score_predict, ALL_PATHS, v0_predict

if __name__ == "__main__":
    print("Scoring V0 baseline...")
    res_v0 = score_predict(v0_predict, ALL_PATHS)
    print(f"V0   yaw_rmse: {res_v0['yaw_rate_rmse']:.6f}  cte_rmse: {res_v0['cte_rmse']:.4f}")
    print()
    print("Scoring final model...")
    res = score_predict(final_predict, ALL_PATHS)
    print(f"FINAL yaw_rmse: {res['yaw_rate_rmse']:.6f}  cte_rmse: {res['cte_rmse']:.4f}")
    print()
    print("Per-platform (final):")
    for pl, d in res["per_platform"].items():
        v = res_v0["per_platform"].get(pl, {})
        print(f"  {pl:30s} yaw_rmse={d['yaw_rmse']:.5f} (V0 {v.get('yaw_rmse', float('nan')):.5f})  "
              f"bias={d['yaw_bias']:+.5f}  cte_rmse={d['cte_rmse']:.3f} (V0 {v.get('cte_rmse', float('nan')):.3f})")
