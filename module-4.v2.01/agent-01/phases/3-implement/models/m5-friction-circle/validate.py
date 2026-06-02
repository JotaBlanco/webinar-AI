"""Train→dev→test progression for M5.

Reports the dev→test delta so over-fit to dev is visible. The test split
is gated; pass `--final` to allow reading it.

Usage:
    python validate.py            # dev only
    python validate.py --final    # dev + test, sets FROZEN_SPLIT_ALLOW_TEST
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TPL  = HERE.parents[3]
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))

from _shared.frozen_split import train_paths, dev_paths  # noqa: E402
from score import score  # noqa: E402

from model import predict_factory  # noqa: E402


def _predict(coeffs, sim_df, platform):
    import pandas as pd
    c = coeffs.get(platform, {})
    yr = predict_factory(platform, c)(sim_df)
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = yr
    return out


def _headline(result):
    return {
        "yaw_rate_rmse": result["yaw_rate_rmse"],
        "cte_rmse":      result["cte_rmse"],
        "n_segments":    result["n_segments"],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--final", action="store_true",
                   help="Also score on the held-out test split.")
    args = p.parse_args()

    with (HERE / "coeffs.json").open() as f:
        coeffs = json.load(f)

    def fn(sim_df, platform):
        return _predict(coeffs, sim_df, platform)

    out = {"model": "m5-friction-circle"}

    train = train_paths()
    dev   = dev_paths()
    print(f"M5 validate — scoring train ({len(train)}) and dev ({len(dev)})")
    out["train"] = _headline(score(fn, segment_paths=train))
    out["dev"]   = _headline(score(fn, segment_paths=dev))

    if args.final:
        os.environ["FROZEN_SPLIT_ALLOW_TEST"] = "1"
        from _shared.frozen_split import test_paths
        test = test_paths()
        print(f"  + test ({len(test)})")
        out["test"] = _headline(score(fn, segment_paths=test))

    gap_yaw = out["dev"]["yaw_rate_rmse"] - out["train"]["yaw_rate_rmse"]
    gap_cte = out["dev"]["cte_rmse"]      - out["train"]["cte_rmse"]
    out["dev_train_gap_yaw"] = gap_yaw
    out["dev_train_gap_cte"] = gap_cte
    print(f"train→dev gap: yaw {gap_yaw:+.5f} rad/s, CTE {gap_cte:+.2f} m")
    if args.final:
        out["dev_test_gap_yaw"] = out["test"]["yaw_rate_rmse"] - out["dev"]["yaw_rate_rmse"]
        out["dev_test_gap_cte"] = out["test"]["cte_rmse"]      - out["dev"]["cte_rmse"]
        print(f"dev→test  gap: yaw {out['dev_test_gap_yaw']:+.5f} rad/s, "
              f"CTE {out['dev_test_gap_cte']:+.2f} m")

    with (HERE / "validation.json").open("w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote validation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
