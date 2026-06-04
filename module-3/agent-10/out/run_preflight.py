import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
import os
os.chdir(ROOT)
from preflight import preflight
res = preflight(ROOT / "final-model")
print("PASSES:", res["passes"])
for c in res["checks"]:
    print(f"  [{c['status']}] {c['name']}: {c['detail'][:120]}")
if res["errors"]:
    print("ERRORS:")
    for e in res["errors"]:
        print(" -", e)
