"""Run preflight on the final-model bundle and score it against sim-only mirror."""
from __future__ import annotations
import os, sys, importlib.util
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-05")
os.chdir(ROOT)

# preflight
sys.path.insert(0, str(ROOT / "skills" / "pre-flight-final-model"))
try:
    from preflight import preflight
    pre = preflight(str(ROOT / "final-model"))
    print("=== PREFLIGHT ===")
    print(f"passes: {pre['passes']}")
    for c in pre["checks"]:
        print(f"  [{c['status']}] {c['name']}: {c.get('detail','')}")
    if pre["errors"]:
        for e in pre["errors"]:
            print("  ERR:", e)
except Exception as e:
    print(f"preflight import/run failed: {e}")

# Score predict against the sim-only mirror (grader-shaped inputs).
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402

# Load predict.py from final-model
spec = importlib.util.spec_from_file_location("final_predict", ROOT / "final-model" / "predict.py")
mod = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(ROOT / "final-model"))
spec.loader.exec_module(mod)

# Score against sim-only mirror
sim_only = sorted((ROOT / "data" / "sim-only" / "segments").glob("*/**/sim.csv"))
print(f"\n=== SCORE on sim-only ({len(sim_only)} segs) ===")
# Score uses sim/segments by default — pass paths explicitly.
# But: sim-only sim.csv may not have truth columns! Score expects truth.
# Check schema first.
import pandas as pd
sample = pd.read_csv(sim_only[0])
print("sim-only columns:", list(sample.columns))
