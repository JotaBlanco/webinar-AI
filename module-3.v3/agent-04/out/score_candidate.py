"""Score a named candidate model from models/<name>/predict.py."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v3/agent-04")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary


def load_predict(name: str):
    p = ROOT / "models" / name / "predict.py"
    spec = importlib.util.spec_from_file_location(f"models_{name}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.predict


def main(name: str) -> None:
    pred = load_predict(name)
    sim_segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    res = score(pred, segment_paths=sim_segs)
    print(format_summary(res))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "v1_plus_nonlin")
