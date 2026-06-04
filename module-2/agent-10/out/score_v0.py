"""Score V0 baseline."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-10")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))

from score import score, format_summary  # noqa: E402
from v0_predict import predict  # noqa: E402

# Build the segment paths from sim-only/segments (the grader's contract).
def gather(root_dir: Path):
    return sorted(p for p in root_dir.glob("*/**/sim.csv") if p.is_file())

# Note: score-model reads truth column from sim.csv. sim-only doesn't have truth.
# Use sim/ for scoring (truth present), but the predict path will be allowlisted.
seg_root = ROOT / "data" / "sim" / "segments"
seg_paths = gather(seg_root)
print(f"Found {len(seg_paths)} segments")

result = score(predict, segment_paths=seg_paths)
print(format_summary(result))
