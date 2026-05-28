"""Run yaw-divergence-triage variant ladder for Mach-E."""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD_ROOT = HERE.parent  # agent-02/
sys.path.insert(0, str(MOD_ROOT / "skills" / "yaw-divergence-triage"))
sys.path.insert(0, str(MOD_ROOT / "skills" / "regime-comparison"))

import numpy as np
import pandas as pd

import triage
import compare

# Adapter — skill helpers expect subscriptable params dict; parameters.py exposes dataclasses.
_orig_load = triage._load_params
def _load_params_adapted(platform, code_root=str(MOD_ROOT / "code")):
    P = _orig_load(platform, code_root=code_root)
    if isinstance(P, dict):
        return P
    return {k: getattr(P, k) for k in ("L", "l_f", "l_r", "m", "C_alpha_f", "C_alpha_r", "I_z")}
triage._load_params = _load_params_adapted

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
DATA_ROOT = MOD_ROOT / "data" / "sim" / "segments"

df = triage.load_ford_segments(PLATFORM, data_root=DATA_ROOT)
print(f"loaded rows={len(df)} segments={df['__source__'].nunique()}")

# Establish regime once; reuse across variants
df["regime"] = triage.regime_mask(df)

# V0: as-is residual already in CSV
v0_resid = df["yaw_rate_resid_rads"].to_numpy()

# V1
_, v1_resid = triage.v1_ks_recalibrated(df, PLATFORM)

# V2
_, v2_resid = triage.v2_linear_st_prior(df, PLATFORM)

# V3
_, v3_resid, v3_info = triage.v3_linear_st_fit(df, PLATFORM)

variants = {"V0": v0_resid, "V1": v1_resid, "V2": v2_resid, "V3": v3_resid}

# Per-regime RMSEs
rows = []
for name, r in variants.items():
    pr = triage.per_regime_rmse(df, r)
    rows.append({"variant": name, **pr})
ladder = pd.DataFrame(rows)
print("\n=== ladder ===")
print(ladder.to_string(index=False))

# Marginal attribution on overall
marginals = []
prev = ladder.loc[ladder["variant"] == "V0", "overall"].iloc[0]
for v in ("V1", "V2", "V3"):
    cur = ladder.loc[ladder["variant"] == v, "overall"].iloc[0]
    marginals.append((v, prev - cur))
    prev = cur
total_drop = ladder.loc[ladder["variant"] == "V0", "overall"].iloc[0] - ladder.loc[ladder["variant"] == "V3", "overall"].iloc[0]
sum_marg = sum(d for _, d in marginals)
acc_err = abs(sum_marg - total_drop) / abs(total_drop) if total_drop else 0
print("\n=== attribution ===")
for v, d in marginals:
    print(f"  {v}: marginal_drop={d:+.6f}")
print(f"  sum={sum_marg:+.6f}  total={total_drop:+.6f}  rel_err={acc_err:.4f}")
print(f"\nV3 fit info: {v3_info}")

# Sibling skill — regime contrast
print("\n=== regime-comparison contrast ===")
contrast_tbl = compare.contrast(df, variants, baseline_name="V0")
print(contrast_tbl.to_string(index=False))

# Save artifacts
ladder.to_csv(HERE / "ladder.csv", index=False)
contrast_tbl.to_csv(HERE / "contrast.csv", index=False)
print(f"\nartifacts in {HERE}")
