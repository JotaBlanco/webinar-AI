"""Score V0 (precomputed yaw_rate_pred_rads) using score-model skill."""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path('/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-10')
sys.path.insert(0, str(ROOT / 'skills' / 'score-model'))
from score import score  # noqa: E402


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return pd.DataFrame({'yaw_rate_pred_rads': sim_df['yaw_rate_pred_rads'].values}, index=sim_df.index)


import os
os.chdir(ROOT)
res = score(predict_v0)
import json
print(json.dumps(res, indent=2, default=str))
