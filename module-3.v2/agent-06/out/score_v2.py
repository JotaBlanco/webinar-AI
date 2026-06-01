"""Score V2 — V1 form with fitted coefficients."""
import sys, json, shutil
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-06")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))

import pandas as pd
from score import score, format_summary
from predict_v1 import predict as v_predict, _load_coeffs

# Copy v2 coeffs into out/coeffs.json so predict_v1 picks it up
src = ROOT / "out" / "coeffs_fitted_v2.json"
dst = ROOT / "out" / "coeffs.json"
shutil.copy(src, dst)

paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
print(f"# segments: {len(paths)}")

res = score(v_predict, segment_paths=paths)
print(format_summary(res, top_n=5))
