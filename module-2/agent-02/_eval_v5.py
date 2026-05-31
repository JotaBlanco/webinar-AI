"""Score the V5 final model against V0 baseline using the score-model skill."""
import sys
import json
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "skills" / "score-model"))
sys.path.insert(0, str(HERE / "final-model"))
from score import score
from predict import predict as predict_v5


def predict_v0(sim_df, platform):
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"]}, index=sim_df.index)


if __name__ == "__main__":
    print("=== V0 (baseline KS) ===")
    r0 = score(predict_v0)
    print(json.dumps(r0, indent=2, default=str))

    print("\n=== V5 (understeer + scale/bias + lag) ===")
    r5 = score(predict_v5)
    print(json.dumps(r5, indent=2, default=str))

    print("\n=== Delta (V5 - V0; negative is better) ===")
    print(f"  Overall yaw RMSE: {r5['yaw_rate_rmse']:.6f} vs {r0['yaw_rate_rmse']:.6f} (delta {r5['yaw_rate_rmse']-r0['yaw_rate_rmse']:+.6f})")
    print(f"  Overall CTE RMSE: {r5['cte_rmse']:.3f}    vs {r0['cte_rmse']:.3f}    (delta {r5['cte_rmse']-r0['cte_rmse']:+.3f})")
