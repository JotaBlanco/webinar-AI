"""Score recipe with cohort defaults."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))
from score import score, format_summary  # noqa
import predict as predict_mod  # noqa


if __name__ == "__main__":
    root = ROOT / "data" / "sim" / "segments"
    segs = sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())
    res = score(predict_mod.predict, segment_paths=segs)
    print(format_summary(res))
