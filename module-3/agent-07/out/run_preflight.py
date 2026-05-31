import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
import os
os.chdir(ROOT)
from preflight import preflight  # noqa: E402
r = preflight(ROOT / "final-model")
import json
print(json.dumps(r, indent=2, default=str))
