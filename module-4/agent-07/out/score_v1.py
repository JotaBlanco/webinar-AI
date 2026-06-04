"""Score V1 baseline on the sim-only dev split, then print residual diagnostics
to guide our improvement direction."""
import sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-07")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "skills"))

import importlib.util
spec = importlib.util.spec_from_file_location("v1_baseline", ROOT / "code/v1_baseline.py")
v1_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v1_mod)
predict_v1 = v1_mod.predict_v1
spec = importlib.util.spec_from_file_location("score_mod", ROOT / "skills/score-model/score.py")
score_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score_mod)

import os
os.chdir(ROOT)

result = score_mod.score(predict_v1)
print(score_mod.format_summary(result))
