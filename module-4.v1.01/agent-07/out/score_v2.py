import sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-07")
sys.path.insert(0, str(ROOT / "final-model"))
sys.path.insert(0, str(ROOT))

import importlib.util
spec = importlib.util.spec_from_file_location("score_mod", ROOT / "skills/score-model/score.py")
score_mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(score_mod)
spec2 = importlib.util.spec_from_file_location("final_predict", ROOT / "final-model/predict.py")
fp = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(fp)

import os; os.chdir(ROOT)
result = score_mod.score(fp.predict)
print(score_mod.format_summary(result))
