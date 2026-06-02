"""Score V1 baseline on the agent-facing sim-only segments (matches grading)."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))

from score import score, format_summary  # type: ignore
from v1_baseline import predict_v1  # type: ignore


def get_segs():
    # use the sim/segments tree because score-model expects truth columns to live there;
    # internally it strips to the allowlist before calling predict, so this matches grading.
    root = ROOT / "data" / "sim" / "segments"
    return sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())


if __name__ == "__main__":
    res = score(predict_v1, segment_paths=get_segs())
    print(format_summary(res))
