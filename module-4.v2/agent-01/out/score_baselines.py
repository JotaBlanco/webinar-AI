"""Quick scoring harness — score V0 passthrough and V1 baseline."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

import pandas as pd

from score import score, format_summary  # type: ignore

from v1_baseline import predict_v1  # type: ignore


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
        index=sim_df.index,
    )


def main():
    # Use dev split — i.e. just glob all sim segments under data/sim/segments.
    root = ROOT / "data" / "sim" / "segments"
    # Skip Tesla (no truth)
    paths = []
    for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        paths.extend(sorted((root / plat).glob("**/sim.csv")))
    print(f"# segments: {len(paths)}")

    for name, fn in [("V0", predict_v0), ("V1", predict_v1)]:
        print(f"\n\n========== {name} ==========")
        r = score(fn, segment_paths=paths)
        print(format_summary(r))


if __name__ == "__main__":
    main()
