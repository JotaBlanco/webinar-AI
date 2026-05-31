import sys
sys.path.insert(0, 'skills/pre-flight-final-model')
from preflight import preflight
import json
r = preflight('final-model')
print(json.dumps(r, indent=2, default=str))
