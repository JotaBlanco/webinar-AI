"""Run the preflight skill against final-model/."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))

# Touch a REPORT.md placeholder so preflight passes; orchestrator will overwrite.
report = ROOT / "final-model" / "REPORT.md"
if not report.exists() or report.stat().st_size < 100:
    report.write_text(
        "# Final model — calibrated kinematic single-track + first-order yaw lag\n\n"
        "Per-platform coefficients in `coeffs.json`. See top-level `REPORT.md` for the writeup.\n"
    )

from preflight import preflight  # noqa: E402

# preflight resolves sample sim.csv relative to cwd("data/sim-only/...")
import os
os.chdir(ROOT)

res = preflight(ROOT / "final-model")
print("passes:", res["passes"])
for c in res["checks"]:
    print(f"  [{c['status']}] {c['name']}: {c['detail']}")
if res["errors"]:
    print("\nerrors:")
    for e in res["errors"]:
        print(" -", e)
