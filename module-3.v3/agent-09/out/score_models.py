"""Score a candidate model by module path."""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))

from score import score, format_summary  # type: ignore


def load_predict(path: Path):
    spec = importlib.util.spec_from_file_location("cand", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.predict


def get_segs():
    root = ROOT / "data" / "sim" / "segments"
    return sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())


if __name__ == "__main__":
    path = Path(sys.argv[1])
    res = score(load_predict(path), segment_paths=get_segs())
    print(format_summary(res))
