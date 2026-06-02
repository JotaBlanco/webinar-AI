"""Score V1 + candidates against the sim-only mirror (grading view, no truth in inputs).

NOTE: sim-only has only the 8 allowlist columns and lacks truth, so we can only
do this if we cross-reference truth from the matching sim/ path. We use sim/
for scoring (which already strips inputs to allowlist before calling predict).
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v3/agent-04")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary
from v1_baseline import predict_v1


def load_predict(name: str):
    p = ROOT / "models" / name / "predict.py"
    spec = importlib.util.spec_from_file_location(f"models_{name}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.predict


def comp(name, predict_fn):
    sim_segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    res = score(predict_fn, segment_paths=sim_segs)
    print(f"\n## {name}")
    print(f"  yaw_rmse: {res['yaw_rate_rmse']:.6f}  cte_rmse: {res['cte_rmse']:.4f}")
    for plat, m in res["per_platform"].items():
        print(f"    {plat:>30s}: yaw={m['yaw_rate_rmse']:.5f} cte={m['cte_rmse']:.3f}")
    return res


if __name__ == "__main__":
    comp("V1", predict_v1)
    comp("v1_plus_nonlin", load_predict("v1_plus_nonlin"))
    comp("v1_plus_rich", load_predict("v1_plus_rich"))
