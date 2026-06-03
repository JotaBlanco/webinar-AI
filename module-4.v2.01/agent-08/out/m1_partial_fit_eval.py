"""Score M1 with the (partial) fitted coeffs from the prior fit run on dev.

The fit was killed mid-Mach-E by OOM; we use the values it converged to for
F150 and inherit priors for the rest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
M1_DIR = ROOT / "phases/3-implement/models/m1-linear-dynamic-st"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(M1_DIR))

from _shared.frozen_split import dev_paths  # noqa: E402
from score import score  # noqa: E402
import model as m1  # noqa: E402

# Update M1's coeffs.json with what we saw converging.
coeffs = {
    "FORD_F_150_LIGHTNING_MK1": {
        "C_alpha_f": 246250.0,
        "C_alpha_r": 470400.0,
        "I_z":       15000.0,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        # last seen converging toward higher C_alpha_f; keep prior for now
        "C_alpha_f": 300880.0,
        "C_alpha_r": 355912.0,
        "I_z":       4879.05,
    },
    "HYUNDAI_IONIQ_5": {
        "C_alpha_f": 240000.0,
        "C_alpha_r": 360000.0,
        "I_z":       4000.0,
    },
}
coeffs_path = M1_DIR / "coeffs.json"
with coeffs_path.open("w") as f:
    json.dump(coeffs, f, indent=2)

dev = dev_paths()
print(f"dev={len(dev)} scoring M1 with partial-fit coeffs")
r = score(m1.predict, segment_paths=dev)
print(f"M1 dev  yaw {r['yaw_rate_rmse']:.6f}  cte {r['cte_rmse']:.4f}")
for plat, s in r["per_platform"].items():
    print(f"  {plat:30s}  yaw {s.get('yaw_rate_rmse')}  cte {s.get('cte_rmse')}  n={s.get('n_segments')}")

with (HERE / "m1_partial_dev.json").open("w") as f:
    json.dump({
        "yaw_rate_rmse": r["yaw_rate_rmse"],
        "cte_rmse": r["cte_rmse"],
        "per_platform": {k: {kk: v.get(kk) for kk in ("yaw_rate_rmse", "cte_rmse", "n_segments")} for k, v in r["per_platform"].items()},
        "per_regime": r.get("per_regime"),
        "coeffs_used": coeffs,
    }, f, indent=2, default=str)
