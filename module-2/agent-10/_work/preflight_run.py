import sys, os, json
from pathlib import Path
ROOT = Path('/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-10')
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / 'skills' / 'pre-flight-final-model'))
from preflight import preflight
r = preflight(ROOT / 'final-model')
print(json.dumps(r, indent=2, default=str))
