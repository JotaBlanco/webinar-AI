"""Score the final-model bundle via its predict() under the sim-only contract."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "final-model"))
from predict import predict
from out.score import score_paths
from _shared.frozen_split import dev_paths

if __name__ == "__main__":
    import json
    res = score_paths(dev_paths(), predict, "dev")
    print(json.dumps(res, indent=2))
