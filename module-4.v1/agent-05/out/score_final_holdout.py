"""Score on held-out 20% segment-hashed dev fold only (matches fit's dev fold)."""
import sys, importlib.util, hashlib
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-05")
sys.path.insert(0, str(ROOT / "_shared"))

spec = importlib.util.spec_from_file_location("predict_mod", ROOT / "final-model" / "predict.py")
pm = importlib.util.module_from_spec(spec); spec.loader.exec_module(pm)

spec2 = importlib.util.spec_from_file_location("score_mod", ROOT / "skills" / "score-model" / "score.py")
score_mod = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(score_mod)

spec3 = importlib.util.spec_from_file_location("v1b", ROOT / "code" / "v1_baseline.py")
v1mod = importlib.util.module_from_spec(spec3); spec3.loader.exec_module(v1mod)

ALLOWED = list(score_mod.ALLOWED_INPUT_COLUMNS)

def fold_of(seg_id: str) -> int:
    return int(hashlib.md5(seg_id.encode()).hexdigest(), 16) % 5

all_segs = sorted((ROOT / "data" / "sim" / "segments").rglob("sim.csv"))
dev_segs = [p for p in all_segs if fold_of(str(p)) == 4]
print(f"dev segments: {len(dev_segs)} / total {len(all_segs)}")

def wrapped(sim_df, platform):
    keep = [c for c in sim_df.columns if c in ALLOWED]
    return pm.predict(sim_df[keep], platform)

print("\n--- V1 baseline on dev fold ---")
r1 = score_mod.score(v1mod.predict_v1, segment_paths=dev_segs)
print(f"V1 dev yaw RMSE: {r1['yaw_rate_rmse']:.6f}")
print(f"V1 dev CTE RMSE: {r1['cte_rmse']:.4f}")

print("\n--- Final model on dev fold ---")
r2 = score_mod.score(wrapped, segment_paths=dev_segs)
print(f"FINAL dev yaw RMSE: {r2['yaw_rate_rmse']:.6f}")
print(f"FINAL dev CTE RMSE: {r2['cte_rmse']:.4f}")
print("Per-platform:")
for plat, st in r2["per_platform"].items():
    print(f"  {plat}: yaw_rmse={st.get('yaw_rate_rmse'):.6f} cte_rmse={st.get('cte_rmse'):.4f}")

dyaw = (r1['yaw_rate_rmse'] - r2['yaw_rate_rmse']) / r1['yaw_rate_rmse'] * 100
dcte = (r1['cte_rmse'] - r2['cte_rmse']) / r1['cte_rmse'] * 100
print(f"\nDelta vs V1: yaw {dyaw:+.2f}%, CTE {dcte:+.2f}%")
