import sys
sys.path.insert(0, 'skills/pre-flight-final-model')
from preflight import preflight
r = preflight('final-model')
import json
print(json.dumps(r, indent=2))
