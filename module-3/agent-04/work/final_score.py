"""Score the final-model/predict.py using score-model on dev and full data."""
import os, sys, importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
sys.path.insert(0, str(ROOT / "final-model"))

os.chdir(ROOT)

from score import score
from split import split

spec = importlib.util.spec_from_file_location("final_predict", ROOT / "final-model" / "predict.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

train, dev = split(dev_fraction=0.25, seed=42)
print(f"Train: {len(train)}   Dev: {len(dev)}")

print("\n=== FINAL — train set ===")
res = score(mod.predict, segment_paths=train)
print(f"Overall: yaw_RMSE={res['yaw_rate_rmse']:.6f}  CTE_RMSE={res['cte_rmse']:.3f}")
for plat, sub in res["per_platform"].items():
    print(f"  {plat}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  CTE_RMSE={sub['cte_rmse']:.3f}")

print("\n=== FINAL — dev set ===")
res = score(mod.predict, segment_paths=dev)
print(f"Overall: yaw_RMSE={res['yaw_rate_rmse']:.6f}  CTE_RMSE={res['cte_rmse']:.3f}")
for plat, sub in res["per_platform"].items():
    print(f"  {plat}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  CTE_RMSE={sub['cte_rmse']:.3f}")
for reg, sub in res["per_regime"].items():
    print(f"  regime {reg}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  n={sub['n_samples']}")

print("\n=== FINAL — full data ===")
res = score(mod.predict)
print(f"Overall: yaw_RMSE={res['yaw_rate_rmse']:.6f}  CTE_RMSE={res['cte_rmse']:.3f}")
for plat, sub in res["per_platform"].items():
    print(f"  {plat}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  CTE_RMSE={sub['cte_rmse']:.3f}")
