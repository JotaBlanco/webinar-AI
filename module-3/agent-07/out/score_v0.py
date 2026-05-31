"""Score V0 passthrough as baseline."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402

def v0(sim_df, platform):
    import pandas as pd
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()}, index=sim_df.index)

import os
os.chdir(ROOT)
res = score(v0)
print(format_summary(res))
