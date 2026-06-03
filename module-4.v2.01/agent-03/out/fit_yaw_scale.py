"""Fit a per-platform multiplicative yaw-rate scale to V1 outputs on TRAIN.

Hypothesis: V1's yaw residual_mean is small, but CTE has signed drift
(F150 +29m, MachE -5m, Hyundai -9m). A small magnitude error in yaw
integrates over a segment into outward/inward drift. Fitting a single
scalar k per platform such that yr_corr = k * yr_v1 might cut CTE
without harming yaw RMSE much.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TPL = HERE.parent
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "final-model"))

from _shared.frozen_split import train_paths  # noqa
from predict import predict as v1_predict  # noqa


def fit_scale(paths):
    by_plat = {}
    for p in paths:
        plat = p.parts[-5]
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        v1 = v1_predict(df, plat)["yaw_rate_pred_rads"].to_numpy()
        truth = df["yaw_rate_meas_rads"].to_numpy()
        # Weighted scalar least squares: k = sum(v1*truth)/sum(v1*v1)
        by_plat.setdefault(plat, [0.0, 0.0])
        by_plat[plat][0] += float(np.sum(v1 * truth))
        by_plat[plat][1] += float(np.sum(v1 * v1))
    scales = {plat: (n / d) if d > 0 else 1.0 for plat, (n, d) in by_plat.items()}
    return scales


def main() -> int:
    train = train_paths()
    print(f"Fitting scale on {len(train)} train segments")
    scales = fit_scale(train)
    print(json.dumps(scales, indent=2))
    (HERE / "yaw_scales.json").write_text(json.dumps(scales, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
