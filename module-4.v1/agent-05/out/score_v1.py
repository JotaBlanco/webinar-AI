"""Score V1 baseline on dev (sim/segments)."""
import sys, importlib.util
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-05")
sys.path.insert(0, str(ROOT / "_shared"))

# load v1
spec = importlib.util.spec_from_file_location("v1_baseline", ROOT / "code" / "v1_baseline.py")
v1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v1)

# load score
spec2 = importlib.util.spec_from_file_location("score_mod", ROOT / "skills" / "score-model" / "score.py")
score_mod = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(score_mod)

# find all dev sim.csvs (non-test)
seg_paths = sorted((ROOT / "data" / "sim" / "segments").rglob("sim.csv"))
print(f"found {len(seg_paths)} segments")

result = score_mod.score(v1.predict_v1, segment_paths=seg_paths)
print(f"V1 yaw RMSE: {result['yaw_rate_rmse']:.6f}")
print(f"V1 CTE RMSE: {result['cte_rmse']:.4f}")
print(f"n_segments scored: {result['n_segments']}")
print("Per-platform:")
for plat, st in result["per_platform"].items():
    print(f"  {plat}: yaw_bias={st.get('yaw_residual_mean'):.6f} yaw_rmse={st.get('yaw_rate_rmse'):.6f} cte_drift={st.get('cte_signed_mean'):.4f} cte_rmse={st.get('cte_rmse'):.4f}")
