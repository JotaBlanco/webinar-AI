import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
sys.path.insert(0, str(ROOT / "code"))
from preflight import preflight  # type: ignore

res = preflight(str(ROOT / "final-model"))
print("PASSES:", res["passes"])
for c in res["checks"]:
    print(f"  [{c['status']}] {c['name']}: {c.get('detail','')}")
for e in res.get("errors", []):
    print("ERROR:", e)
