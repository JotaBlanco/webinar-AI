"""Final check: import final-model/predict.py via the grader-style import path
and score against sim/segments/."""
from __future__ import annotations
import sys, importlib.util
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-04")
sys.path.insert(0, str(ROOT / "out"))
from quick_score import score

spec = importlib.util.spec_from_file_location("final_predict", str(ROOT / "final-model" / "predict.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

r = score(m.predict)
print("FINAL MODEL pooled (dev / sim segments):")
print(f"  yaw_rate_rmse = {r['yaw_rate_rmse']:.6f}")
print(f"  cte_rmse      = {r['cte_rmse']:.4f}")
for plat, pp in r["per_platform"].items():
    print(f"  {plat}: yaw={pp['yaw_rmse']:.6f} bias={pp['yaw_bias']:+.6f} cte={pp['cte_rmse']:.3f}")

# also test on sim-only/segments (no truth) just to confirm no crash
sim_only_segments = sorted((ROOT / "data" / "sim-only" / "segments").glob("*/**/sim.csv"))
print(f"\nsim-only segments available: {len(sim_only_segments)}")
import pandas as pd
ok = 0; fail = 0
for p in sim_only_segments[:50]:
    plat = p.resolve().parents[3].name
    df = pd.read_csv(p)
    try:
        out = m.predict(df, plat)
        assert "yaw_rate_pred_rads" in out.columns
        assert len(out) == len(df)
        ok += 1
    except Exception as e:
        fail += 1
        print(f"FAIL on {p}: {e}")
print(f"sim-only smoke: {ok} ok, {fail} fail (of {min(50, len(sim_only_segments))})")
