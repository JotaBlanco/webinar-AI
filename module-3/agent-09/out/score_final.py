"""Score the final-model predict against the full sim/ dataset."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary  # noqa: E402

spec = importlib.util.spec_from_file_location("final_predict", ROOT / "final-model" / "predict.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


if __name__ == "__main__":
    seg_root = ROOT / "data" / "sim" / "segments"
    seg_paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    print(f"scoring {len(seg_paths)} segments")
    result = score(mod.predict, segment_paths=seg_paths)
    print(format_summary(result, top_n=5))
