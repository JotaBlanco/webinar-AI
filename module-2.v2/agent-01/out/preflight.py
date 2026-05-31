import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
from preflight import preflight
import json
res = preflight(str(ROOT / "final-model"))
print(json.dumps({"passes": res["passes"], "errors": res["errors"]}, indent=2))
for c in res["checks"]:
    print(f"  - {c['name']}: {c['status']}  {c.get('detail','')}")
