"""Score V1 baseline against sim-only segments (the agent-facing allowlist view)
and against sim segments (full schema). Confirms V1 floor.
"""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v3/agent-04")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))

from v1_baseline import predict_v1
from score import score, format_summary


def main() -> None:
    # Score against sim (full schema; truth available)
    sim_segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    res = score(predict_v1, segment_paths=sim_segs)
    print(format_summary(res))


if __name__ == "__main__":
    main()
