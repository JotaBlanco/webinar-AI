"""V1 with per-platform yaw_bias calibration learned from train.

V1 baseline shows F150 yaw_bias=+0.00155 -> +29.8m CTE drift; a constant
subtraction shouldn't help yaw RMSE much but can cut CTE substantially
(CTE is a double integral, dominated by signed yaw bias).

Approach: fit a single scalar `yaw_bias[plat]` on train by minimising
yaw RMSE; subtract from V1 yaw prediction.

Optionally also fit a scalar `yaw_gain[plat]` (multiplicative).
"""
from __future__ import annotations
import json, sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar, minimize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary
from _shared.frozen_split import dev_paths, train_paths
from v1_baseline import predict_v1

TRUTH_COL = "yaw_rate_meas_rads"
V_FLOOR = 2.0

PLATFORMS = [
    "FORD_F_150_LIGHTNING_MK1",
    "FORD_MUSTANG_MACH_E_MK1",
    "HYUNDAI_IONIQ_5",
]


def platform_of(p):
    return Path(p).resolve().parents[3].name


def collect_yhat_truth(paths):
    """Return list of (yhat_v1, truth, v) arrays per segment."""
    out = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if TRUTH_COL not in df.columns:
            continue
        plat = platform_of(p)
        yhat = predict_v1(df, plat)["yaw_rate_pred_rads"].to_numpy()
        out.append({
            "yhat": yhat,
            "truth": df[TRUTH_COL].to_numpy(float),
            "v": df["v_mps"].to_numpy(float),
        })
    return out


def fit_gain_bias(segs):
    """Fit yhat_corrected = gain * yhat + bias to minimise RMSE."""
    Y = []
    T = []
    for s in segs:
        m = s["v"] > V_FLOOR
        Y.append(s["yhat"][m])
        T.append(s["truth"][m])
    Y = np.concatenate(Y)
    T = np.concatenate(T)
    # Linear regression: T = gain * Y + bias  -> [Y, 1] x [gain; bias] = T
    A = np.column_stack([Y, np.ones_like(Y)])
    coef, *_ = np.linalg.lstsq(A, T, rcond=None)
    gain, bias = float(coef[0]), float(coef[1])
    return gain, bias


def fit_bias_only(segs):
    """Fit yhat_corrected = yhat + bias (no scaling)."""
    diffs = []
    for s in segs:
        m = s["v"] > V_FLOOR
        diffs.append(s["truth"][m] - s["yhat"][m])
    diffs = np.concatenate(diffs)
    return float(np.mean(diffs))


def main():
    train = train_paths()
    by_plat = defaultdict(list)
    for p in train:
        by_plat[platform_of(p)].append(p)

    params = {}
    for plat in PLATFORMS:
        paths = by_plat[plat]
        segs = collect_yhat_truth(paths)
        gain, bias = fit_gain_bias(segs)
        bias_only = fit_bias_only(segs)
        # train residual RMSE before/after
        Y = np.concatenate([s["yhat"][s["v"] > V_FLOOR] for s in segs])
        T = np.concatenate([s["truth"][s["v"] > V_FLOOR] for s in segs])
        rmse_raw = float(np.sqrt(np.mean((Y - T) ** 2)))
        rmse_bias = float(np.sqrt(np.mean((Y + bias_only - T) ** 2)))
        rmse_gain_bias = float(np.sqrt(np.mean((gain * Y + bias - T) ** 2)))
        print(f"\n=== {plat} ===")
        print(f"  raw_train_rmse = {rmse_raw:.6f}")
        print(f"  + bias({bias_only:+.5f})       -> {rmse_bias:.6f}")
        print(f"  * gain({gain:.4f}) + bias({bias:+.5f}) -> {rmse_gain_bias:.6f}")
        params[plat] = {"gain": gain, "bias": bias, "bias_only": bias_only}

    out_path = HERE / "v1_calibration.json"
    with out_path.open("w") as f:
        json.dump(params, f, indent=2)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
