"""Score V1 baseline and M1 (LDST) on the frozen dev split."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

from _shared.frozen_split import dev_paths  # noqa: E402
from score import score  # noqa: E402


def summarize(label, result):
    out = {
        "label": label,
        "yaw_rate_rmse": result["yaw_rate_rmse"],
        "cte_rmse": result["cte_rmse"],
        "n_segments": result["n_segments"],
        "failed_segments": result["failed_segments"],
        "per_platform": {
            k: {
                "yaw_rate_rmse": v.get("yaw_rate_rmse"),
                "cte_rmse": v.get("cte_rmse"),
                "yaw_signed_bias": v.get("yaw_signed_bias"),
                "cte_signed_drift": v.get("cte_signed_drift"),
                "bias_fraction": v.get("yaw_bias_fraction"),
                "n_segments": v.get("n_segments"),
            }
            for k, v in result.get("per_platform", {}).items()
        },
        "per_regime": result.get("per_regime"),
    }
    return out


def main():
    dev = dev_paths()
    print(f"dev segments: {len(dev)}")

    # V1 baseline (rung 0)
    from v1_baseline import predict_v1
    print("scoring V1 baseline...")
    r_v1 = score(predict_v1, segment_paths=dev)
    print(f"  V1  yaw {r_v1['yaw_rate_rmse']:.6f}  cte {r_v1['cte_rmse']:.4f}")

    # M1 (LDST rung 1) with prefilled (prior) coeffs
    sys.path.insert(0, str(ROOT / "phases/3-implement/models/m1-linear-dynamic-st"))
    import model as m1
    print("scoring M1 (priors)...")
    r_m1 = score(m1.predict, segment_paths=dev)
    print(f"  M1  yaw {r_m1['yaw_rate_rmse']:.6f}  cte {r_m1['cte_rmse']:.4f}")

    payload = {
        "v1": summarize("v1_baseline", r_v1),
        "m1_priors": summarize("m1_linear_dynamic_priors", r_m1),
    }
    out_path = HERE / "baseline_scores.json"
    with out_path.open("w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
