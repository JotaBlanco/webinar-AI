import sys, os
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
os.chdir(ROOT)
from preflight import preflight
r = preflight(ROOT / "final-model")
print("passes:", r["passes"])
for c in r["checks"]:
    print(f"  [{c['status']}] {c['name']}: {c['detail']}")
print("errors:", r["errors"])
