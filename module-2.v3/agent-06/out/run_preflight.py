import os, sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-06")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
from preflight import preflight
r = preflight("final-model")
for c in r["checks"]:
    print(f"[{c['status']}] {c['name']}: {c['detail']}")
print()
print("PASSES:", r["passes"])
for e in r["errors"]:
    print("ERR:", e)
