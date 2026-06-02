"""Score all candidate models against V1 and V0."""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary  # noqa: E402
from v1_baseline import predict_v1  # noqa: E402


def _load_predict(path: Path):
    spec = importlib.util.spec_from_file_location(f"_mod_{path.parent.name}", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(path.parent))
    return mod.predict


def predict_v0(sim_df, platform):
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()}, index=sim_df.index)


def main() -> None:
    seg_root = ROOT / "data" / "sim" / "segments"
    segs = sorted(seg_root.glob("*/**/sim.csv"))
    print(f"# segments: {len(segs)}")

    models = [
        ("V0", predict_v0),
        ("V1", predict_v1),
    ]
    for d in sorted((ROOT / "models").iterdir()):
        if not d.is_dir():
            continue
        pp = d / "predict.py"
        if pp.exists():
            models.append((d.name, _load_predict(pp)))

    for name, fn in models:
        print(f"\n=== {name} ===")
        res = score(fn, segment_paths=segs)
        print(f"yaw_rate_rmse = {res['yaw_rate_rmse']:.6f}")
        print(f"cte_rmse      = {res['cte_rmse']:.4f}")
        for plat, m in res["per_platform"].items():
            print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f} cte={m['cte_rmse']:.3f} "
                  f"yaw_bias={m['yaw_residual_mean']:+.5f} cte_drift={m['cte_signed_mean']:+.3f}")


if __name__ == "__main__":
    main()
