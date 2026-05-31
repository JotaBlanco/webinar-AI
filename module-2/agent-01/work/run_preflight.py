import sys, os, json
ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01'
sys.path.insert(0, os.path.join(ROOT, 'skills/pre-flight-final-model'))
os.chdir(ROOT)
from preflight import preflight
res = preflight(os.path.join(ROOT, 'final-model'))
print(json.dumps(res, indent=2))
