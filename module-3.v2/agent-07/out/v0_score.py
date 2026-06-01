"""Quick: score V0 passthrough across all platforms."""
import sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary
import pandas as pd

def predict_v0(sim_df, platform):
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                        index=sim_df.index)

segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
result = score(predict_v0, segment_paths=segs)
print(format_summary(result))
