"""Run pre-flight checks on the final-model bundle."""
import json
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
from preflight import preflight  # noqa: E402

import os
os.chdir(str(ROOT))
result = preflight(ROOT / "final-model")
print(json.dumps(result, indent=2, default=str))
