import sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-02")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))
from score import score, format_summary  # noqa: E402
from predict_v2 import predict  # noqa: E402

if __name__ == "__main__":
    seg_paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    result = score(predict, segment_paths=seg_paths)
    print(format_summary(result, top_n=5))
