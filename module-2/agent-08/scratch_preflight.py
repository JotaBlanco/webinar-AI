import sys
sys.path.insert(0, 'skills/pre-flight-final-model')
from preflight import preflight
r = preflight('final-model')
print('passes:', r['passes'])
for c in r['checks']:
    print(f"  [{c['status']}] {c['name']}: {c['detail']}")
print('errors:', r['errors'])
