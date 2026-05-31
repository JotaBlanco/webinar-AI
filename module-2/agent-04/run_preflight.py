import sys, json
sys.path.insert(0, 'skills/pre-flight-final-model')
from preflight import preflight
r = preflight('final-model')
print(json.dumps(r, indent=2))
print('PASSES?', r['passes'])
