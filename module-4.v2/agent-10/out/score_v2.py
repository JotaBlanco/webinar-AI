import sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-10")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "final-model"))
sys.path.insert(0, str(ROOT / "code"))
from out.score import score
from v1_baseline import predict_v1
from predict import predict as predict_v2
import pandas as pd

def v0(sim_df, platform):
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()}, index=sim_df.index)

print("V1:")
print(score(predict_v1))
print()
print("V2:")
print(score(predict_v2))
