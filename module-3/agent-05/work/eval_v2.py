"""Compare V0 vs V1 vs V2 on dev and full."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "final-model"))
sys.path.insert(0, str(ROOT / "work"))

os.chdir(ROOT)

import pandas as pd
from score import score
from split import split
from predict import predict as v1_predict
from predict_v2 import predict as v2_predict


def v0_predict(sim_df, platform):
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].values},
        index=sim_df.index,
    )


def line(name, r):
    pp = r["per_platform"]
    fl = pp.get("FORD_F_150_LIGHTNING_MK1", {})
    me = pp.get("FORD_MUSTANG_MACH_E_MK1", {})
    print(f"{name:6s}  yr={r['yaw_rate_rmse']:.6f}  cte={r['cte_rmse']:7.3f}  | "
          f"F150 yr={fl.get('yaw_rate_rmse', 0):.6f} cte={fl.get('cte_rmse', 0):7.3f}  "
          f"MachE yr={me.get('yaw_rate_rmse', 0):.6f} cte={me.get('cte_rmse', 0):7.3f}")


def main():
    train, dev = split(dev_fraction=0.25, seed=42)

    print("=" * 90)
    print("DEV SET")
    print("=" * 90)
    line("V0", score(v0_predict, segment_paths=dev))
    line("V1", score(v1_predict, segment_paths=dev))
    line("V2", score(v2_predict, segment_paths=dev))

    print("\n" + "=" * 90)
    print("FULL SET")
    print("=" * 90)
    line("V0", score(v0_predict))
    line("V1", score(v1_predict))
    line("V2", score(v2_predict))


if __name__ == "__main__":
    main()
