import sys, json
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
import os
os.chdir(ROOT)
from preflight import preflight
res = preflight(ROOT / "final-model")
print(json.dumps(res, indent=2, default=str))
