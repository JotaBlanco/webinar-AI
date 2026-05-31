import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'skills' / 'pre-flight-final-model'))
from preflight import preflight
import json
r = preflight(str(ROOT / 'final-model'))
print(json.dumps(r, indent=2, default=str))
