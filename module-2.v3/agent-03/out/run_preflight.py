import os, sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-03")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
from preflight import preflight
res = preflight("final-model")
print("passes:", res["passes"])
for c in res["checks"]:
    print(f"  {c['status']}  {c['name']}: {c.get('detail','')}")
for e in res.get("errors", []):
    print("ERR:", e)
