"""Verify final-model/predict.py scores cleanly on dev."""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TPL = HERE.parent
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))
sys.path.insert(0, str(TPL / "final-model"))

from _shared.frozen_split import dev_paths  # noqa: E402
from score import score, format_summary  # noqa: E402
from predict import predict  # noqa: E402

dev = dev_paths()
print(f"Final model dev — {len(dev)} segments")
res = score(predict, segment_paths=dev)
print(format_summary(res))
