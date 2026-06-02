"""Score V3."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(HERE))

from score import score, format_summary  # type: ignore
from predict_v3 import predict  # type: ignore


def main():
    root = ROOT / "data" / "sim" / "segments"
    paths = []
    for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        paths.extend(sorted((root / plat).glob("**/sim.csv")))
    r = score(predict, segment_paths=paths)
    print(format_summary(r))


if __name__ == "__main__":
    main()
