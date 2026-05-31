import sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "skills" / "pre-flight-final-model"))
from preflight import preflight
print(json.dumps(preflight(HERE / "final-model"), indent=2))
