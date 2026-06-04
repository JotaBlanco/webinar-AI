"""Run pre-flight on final-model bundle."""
import os
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
os.chdir(ROOT)
from preflight import preflight  # type: ignore

result = preflight(ROOT / "final-model")
print(f"passes={result['passes']}")
for c in result["checks"]:
    print(f"  {c['status']:5s} {c['name']:40s} {c['detail']}")
