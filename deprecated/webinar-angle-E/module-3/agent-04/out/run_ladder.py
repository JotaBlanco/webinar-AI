"""Run yaw-divergence-triage variant ladder on Ford Mach-E."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MOD = HERE.parent
sys.path.insert(0, str(MOD / "skills" / "yaw-divergence-triage"))
sys.path.insert(0, str(MOD / "skills" / "regime-comparison"))

import triage  # noqa: E402
import compare  # noqa: E402

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"

df = triage.load_ford_segments(PLATFORM, data_root=MOD / "data" / "sim" / "segments")
df["regime"] = triage.regime_mask(df)

# V0 baseline: as-shipped residual column
v0_resid = df["yaw_rate_resid_rads"].to_numpy()

# V1 KS recalibrated
_, v1_resid = triage.v1_ks_recalibrated(df, PLATFORM)

# V2 Linear ST prior
_, v2_resid = triage.v2_linear_st_prior(df, PLATFORM)

# V3 Linear ST fitted
_, v3_resid, fit_info = triage.v3_linear_st_fit(df, PLATFORM)

variants = {"V0": v0_resid, "V1": v1_resid, "V2": v2_resid, "V3": v3_resid}

results = {}
for name, resid in variants.items():
    results[name] = triage.per_regime_rmse(df, resid)

# Marginal attribution V0 -> V1 -> V2 -> V3
order = ["V0", "V1", "V2", "V3"]
marg = {}
for i in range(1, len(order)):
    prev = results[order[i - 1]]["overall"]
    cur = results[order[i]]["overall"]
    marg[order[i]] = prev - cur

total_drop = results["V0"]["overall"] - results["V3"]["overall"]
marg_sum = sum(marg.values())
accounting_err = abs(total_drop - marg_sum) / abs(total_drop) if total_drop != 0 else 0.0

# Regime-comparison sibling
contrast_df = compare.contrast(df, variants, baseline_name="V0")

# Pegged check
pegged_note = (
    f"V3 fit: C_alpha_f={fit_info['C_alpha_f']:.3e} N/rad, "
    f"C_alpha_r={fit_info['C_alpha_r']:.3e} N/rad, pegged={fit_info['pegged']}"
)

# Print as JSON for downstream report
payload = {
    "platform": PLATFORM,
    "n_rows": int(len(df)),
    "n_segments": int(df["__source__"].nunique()),
    "results": results,
    "marginal_drops": marg,
    "total_drop": total_drop,
    "marginal_sum": marg_sum,
    "accounting_err_frac": accounting_err,
    "fit_info": fit_info,
    "pegged_note": pegged_note,
    "contrast": contrast_df.to_dict(orient="records"),
}
print(json.dumps(payload, indent=2, default=float))
