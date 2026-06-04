import sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))
from score import score, format_summary
from recipe_predict import predict

segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
result = score(predict, segment_paths=segs)
print(format_summary(result))
