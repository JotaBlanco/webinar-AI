"""Score V1 baseline (and V0 passthrough) over data/sim/segments/."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary  # noqa: E402
import pandas as pd  # noqa: E402

from v1_baseline import predict_v1  # noqa: E402


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
        index=sim_df.index,
    )


def main() -> None:
    seg_root = ROOT / "data" / "sim" / "segments"
    segs = sorted(seg_root.glob("*/**/sim.csv"))
    print(f"# segments: {len(segs)}")
    for name, fn in (("V0", predict_v0), ("V1", predict_v1)):
        print(f"\n=== {name} ===")
        result = score(fn, segment_paths=segs)
        print(format_summary(result, top_n=3))


if __name__ == "__main__":
    main()
