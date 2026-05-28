"""Run the yaw-divergence-triage variant ladder on FORD_MUSTANG_MACH_E_MK1.

Adapts the attribute-style parameters object to dict access expected by the
triage skill helpers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MOD = HERE.parent  # agent-05
sys.path.insert(0, str(MOD / "skills" / "yaw-divergence-triage"))
sys.path.insert(0, str(MOD / "skills" / "regime-comparison"))
sys.path.insert(0, str(MOD / "code"))

import triage  # type: ignore
import compare  # type: ignore
from parameters import PARAM_BY_PLATFORM  # type: ignore


class ParamAdapter(dict):
    def __init__(self, obj):
        super().__init__({k: getattr(obj, k) for k in
                          ("L", "l_f", "l_r", "m", "C_alpha_f", "C_alpha_r", "I_z")})


# Monkey-patch the triage loader to return a dict-like view.
def _load_params(platform, code_root="code"):
    return ParamAdapter(PARAM_BY_PLATFORM[platform])


triage._load_params = _load_params


PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
DATA_ROOT = MOD / "data" / "sim" / "segments"


def main():
    df = triage.load_ford_segments(PLATFORM, data_root=str(DATA_ROOT))
    df["regime"] = triage.regime_mask(df)
    print(f"Loaded {len(df):,} samples from {df['__source__'].nunique()} sim.csv files")
    print(f"Regime counts:\n{df['regime'].value_counts()}")

    v0_resid = df["yaw_rate_resid_rads"].to_numpy()
    _, v1_resid = triage.v1_ks_recalibrated(df, PLATFORM)
    _, v2_resid = triage.v2_linear_st_prior(df, PLATFORM)
    _, v3_resid, fit_info = triage.v3_linear_st_fit(df, PLATFORM)
    print(f"V3 fit: {fit_info}")

    variants = {"V0": v0_resid, "V1": v1_resid, "V2": v2_resid, "V3": v3_resid}

    rows = []
    for name, resid in variants.items():
        per = triage.per_regime_rmse(df, resid)
        rows.append({"variant": name, **per})
    ladder = pd.DataFrame(rows)
    print("\nVariant ladder (RMSE rad/s):")
    print(ladder.to_string(index=False))

    overall = ladder.set_index("variant")["overall"].to_dict()
    margs = {
        "V0->V1": overall["V0"] - overall["V1"],
        "V1->V2": overall["V1"] - overall["V2"],
        "V2->V3": overall["V2"] - overall["V3"],
    }
    total = overall["V0"] - overall["V3"]
    marg_sum = sum(margs.values())
    print(f"\nMarginals: {margs}")
    print(f"Total drop V0->V3: {total:.6f}")
    print(f"Marginal sum: {marg_sum:.6f}")
    if total != 0:
        print(f"Reconciliation: marg_sum/total = {marg_sum/total:.4f}")

    contrast_df = compare.contrast(df, variants, baseline_name="V0")
    print("\nPer-regime contrast (delta vs V0):")
    print(contrast_df.to_string(index=False))

    ladder.to_csv(HERE / "ladder.csv", index=False)
    contrast_df.to_csv(HERE / "contrast.csv", index=False)
    (HERE / "summary.json").write_text(json.dumps({
        "platform": PLATFORM,
        "n_samples": int(len(df)),
        "n_segments": int(df["__source__"].nunique()),
        "regime_counts": df["regime"].value_counts().to_dict(),
        "ladder": ladder.to_dict(orient="records"),
        "marginals": margs,
        "total_drop": total,
        "v3_fit": fit_info,
        "contrast": contrast_df.to_dict(orient="records"),
    }, indent=2, default=float))
    print("\nWrote ladder.csv, contrast.csv, summary.json")


if __name__ == "__main__":
    main()
