import sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
from preflight import preflight  # noqa: E402
r = preflight(str(ROOT / "final-model"))
print("passes:", r["passes"])
for c in r["checks"]:
    print(f"  [{c['status']}] {c['name']}: {c.get('detail', '')[:200]}")
for e in r.get("errors", []):
    print("ERROR:", e)
