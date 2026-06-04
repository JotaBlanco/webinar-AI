import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))

import os
os.chdir(ROOT)

from preflight import preflight

res = preflight("final-model")
import json
print(json.dumps(res, indent=2, default=str))
