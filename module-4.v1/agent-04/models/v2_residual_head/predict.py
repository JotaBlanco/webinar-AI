"""V2 = V1 + per-platform linear residual head.

Inputs follow the operating contract (8 allowlist columns). For each platform
we run V1 internally, then add a learned residual: r_hat = w0 + sum w_i f_i.
Features are deterministic functions of inputs only — no truth leakage.
Coefficients live in coeffs.json next to this file.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import importlib.util as _iu

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]

# Load V1 baseline by absolute path (avoids `code` stdlib clash).
_spec = _iu.spec_from_file_location("_v1b", _ROOT / "code" / "v1_baseline.py")
_v1m = _iu.module_from_spec(_spec); _spec.loader.exec_module(_v1m)
_predict_v1 = _v1m.predict_v1

_COEFFS = json.loads((_HERE / "coeffs.json").read_text())


def _features(df: pd.DataFrame, yr_v1: np.ndarray) -> dict:
    delta = df["delta_road_rad"].to_numpy(dtype=float)
    v = df["v_mps"].to_numpy(dtype=float)
    a_long = df["a_long_mps2"].to_numpy(dtype=float) if "a_long_mps2" in df.columns else np.zeros(len(df))
    return {
        "delta": delta,
        "v_delta": v * delta,
        "v2_delta": (v * v) * delta,
        "yr_v1": yr_v1,
        "v_yr_v1": v * yr_v1,
        "a_long": a_long,
    }


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    yr_v1 = _predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy()
    cfg = _COEFFS.get(platform)
    if cfg is None or not cfg.get("apply", True):
        return pd.DataFrame({"yaw_rate_pred_rads": yr_v1}, index=sim_df.index)
    feats = _features(sim_df, yr_v1)
    names = cfg["features"]
    coefs = np.asarray(cfg["coefs"], dtype=float)
    intercept = float(cfg["intercept"])
    X = np.column_stack([feats[n] for n in names])
    r_hat = intercept + X @ coefs
    yr = yr_v1 + r_hat
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
