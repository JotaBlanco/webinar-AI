import json, sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
from preflight import preflight
os.chdir(ROOT)
report = preflight(ROOT / "final-model")
print(json.dumps(report, indent=2))
