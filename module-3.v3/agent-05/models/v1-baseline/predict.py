"""V1 baseline (re-export). Reference model — the floor every candidate competes against."""
from __future__ import annotations

import sys
from pathlib import Path

_CODE = Path(__file__).resolve().parents[2] / "code"
if str(_CODE) not in sys.path:
    sys.path.insert(0, str(_CODE))

from v1_baseline import predict_v1  # noqa: E402

predict = predict_v1
