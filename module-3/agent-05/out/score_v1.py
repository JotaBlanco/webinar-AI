import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import score_predict
from recipe_v1 import predict

pooled, per_plat, _ = score_predict(predict, verbose=True, use_input_only=True)
