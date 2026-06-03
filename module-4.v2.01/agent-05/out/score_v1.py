"""Score V1 baseline on the frozen dev split."""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TPL = HERE.parent
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))
sys.path.insert(0, str(TPL / "code"))

from _shared.frozen_split import dev_paths  # noqa: E402
from score import score, format_summary  # noqa: E402
from v1_baseline import predict_v1  # noqa: E402


def main() -> int:
    dev = dev_paths()
    print(f"V1 dev score: {len(dev)} segments")
    res = score(predict_v1, segment_paths=dev)
    print(format_summary(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
