"""Score the actual shipped predict() from final-model/."""
import sys, os, json, importlib.util
from pathlib import Path
import pandas as pd

ROOT = Path('/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-10')
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / 'final-model'))
sys.path.insert(0, str(ROOT / 'skills' / 'score-model'))

from score import score
spec = importlib.util.spec_from_file_location('predict_mod', str(ROOT / 'final-model/predict.py'))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def v0(sim_df, p):
    return pd.DataFrame({'yaw_rate_pred_rads': sim_df['yaw_rate_pred_rads'].values}, index=sim_df.index)

print('V0 ALL:'); print(json.dumps(score(v0), indent=2, default=str))
print('SHIPPED ALL:'); print(json.dumps(score(mod.predict), indent=2, default=str))
