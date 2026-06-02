"""Score the final model against full dev set, sample-allowed columns only."""
import sys, importlib.util
from pathlib import Path
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-05")
sys.path.insert(0, str(ROOT / "_shared"))

spec = importlib.util.spec_from_file_location("predict_mod", ROOT / "final-model" / "predict.py")
pm = importlib.util.module_from_spec(spec); spec.loader.exec_module(pm)

spec2 = importlib.util.spec_from_file_location("score_mod", ROOT / "skills" / "score-model" / "score.py")
score_mod = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(score_mod)

# enforce sim-only allowlist on inputs by wrapping predict
ALLOWED = list(score_mod.ALLOWED_INPUT_COLUMNS)

def wrapped(sim_df, platform):
    keep = [c for c in sim_df.columns if c in ALLOWED]
    return pm.predict(sim_df[keep], platform)

seg_paths = sorted((ROOT / "data" / "sim" / "segments").rglob("sim.csv"))

result = score_mod.score(wrapped, segment_paths=seg_paths)
print(f"FINAL yaw RMSE: {result['yaw_rate_rmse']:.6f}")
print(f"FINAL CTE RMSE: {result['cte_rmse']:.4f}")
print(f"failed segments: {result.get('failed_segments', 0)}")
print("Per-platform:")
for plat, st in result["per_platform"].items():
    print(f"  {plat}: yaw_bias={st.get('yaw_residual_mean'):+.6f} yaw_rmse={st.get('yaw_rate_rmse'):.6f} cte_drift={st.get('cte_signed_mean'):+.4f} cte_rmse={st.get('cte_rmse'):.4f}")
