"""Execute the yaw-divergence-triage variant ladder, plus regime-comparison."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "skills" / "yaw-divergence-triage"))
sys.path.insert(0, str(HERE / "skills" / "regime-comparison"))

import triage  # noqa: E402
import compare  # noqa: E402

# Shim: skill expects dict-like params but parameters.py returns a dataclass.
_orig_load = triage._load_params

def _patched_load(platform, code_root="code"):
    p = _orig_load(platform, code_root=code_root)
    if isinstance(p, dict):
        return p
    return {k: getattr(p, k) for k in ("L", "l_f", "l_r", "m", "C_alpha_f", "C_alpha_r", "I_z")}

triage._load_params = _patched_load

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"

# Load
df = triage.load_ford_segments(PLATFORM, data_root=HERE / "data" / "sim" / "segments")
df["regime"] = triage.regime_mask(df)
print(f"loaded {len(df)} rows, {df['__source__'].nunique()} segments")

# V0 = as-shipped residual column
v0_resid = df["yaw_rate_resid_rads"].to_numpy()

# V1
_, v1_resid = triage.v1_ks_recalibrated(df, PLATFORM)

# V2
_, v2_resid = triage.v2_linear_st_prior(df, PLATFORM)

# V3
_, v3_resid, v3_info = triage.v3_linear_st_fit(df, PLATFORM)

# Per-regime RMSE
ladder = {}
for name, r in [("V0", v0_resid), ("V1", v1_resid), ("V2", v2_resid), ("V3", v3_resid)]:
    ladder[name] = triage.per_regime_rmse(df, r)

print("\nLadder (RMSE rad/s):")
for n, d in ladder.items():
    print(f"  {n}: overall={d['overall']:.4f}  straight={d['straight']:.4f}  steady={d['steady']:.4f}  transient={d['transient']:.4f}")

print(f"\nV3 fit: C_alpha_f={v3_info['C_alpha_f']:.3e}  C_alpha_r={v3_info['C_alpha_r']:.3e}  pegged={v3_info['pegged']}")

# Marginal attribution
print("\nMarginal drops (overall):")
names = ["V0", "V1", "V2", "V3"]
margins = {}
for i in range(1, 4):
    drop = ladder[names[i - 1]]["overall"] - ladder[names[i]]["overall"]
    margins[names[i]] = drop
    print(f"  {names[i]}: {drop:+.5f}")

total = ladder["V0"]["overall"] - ladder["V3"]["overall"]
sum_marg = sum(margins.values())
print(f"\nTotal drop V0->V3: {total:.5f}")
print(f"Sum of marginals : {sum_marg:.5f}")
print(f"Reconciliation gap: {abs(total - sum_marg) / abs(total) * 100:.2f}%")

# Sibling skill: regime-comparison
print("\nregime-comparison contrast:")
contrast_df = compare.contrast(df, {"V0": v0_resid, "V1": v1_resid, "V2": v2_resid, "V3": v3_resid}, baseline_name="V0")
print(contrast_df.to_string(index=False))
