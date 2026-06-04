import sys, os
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-08")
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
os.chdir(ROOT)
from preflight import preflight
import json
res = preflight(Path("final-model"))
print(json.dumps(res, indent=2, default=str))
