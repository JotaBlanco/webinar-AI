"""Fit a per-platform linear residual learner on top of V1.

Features (allowlist-safe):
  - v_mps
  - delta_road_rad
  - d_delta_dt
  - a_long_mps2
  - yaw_rate_v1 (output of V1)
  - sign(yr_v1) * (yr_v1^2)
  - |delta_road_rad|

Target: yaw_rate_meas_rads - yaw_rate_v1.

Fit ridge regression per platform on a stratified subset of segments.
Save coeffs JSON for predict.py to load.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1  # noqa: E402


FEATURES = [
    "v_mps",
    "delta_road_rad",
    "d_delta_dt",
    "a_long_mps2",
    "yr_v1",
    "abs_delta",
    "yr_v1_sq_signed",
]


def features_for_segment(sim_df: pd.DataFrame, platform: str) -> tuple[pd.DataFrame, np.ndarray | None]:
    """Returns (feature DataFrame, V1 yaw prediction array)."""
    v1_out = predict_v1(sim_df, platform)
    yr_v1 = v1_out["yaw_rate_pred_rads"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    d_delta_dt = np.gradient(delta, t) if len(t) > 1 else np.zeros_like(delta)
    feats = pd.DataFrame({
        "v_mps": sim_df["v_mps"].to_numpy(),
        "delta_road_rad": delta,
        "d_delta_dt": d_delta_dt,
        "a_long_mps2": sim_df["a_long_mps2"].to_numpy(),
        "yr_v1": yr_v1,
        "abs_delta": np.abs(delta),
        "yr_v1_sq_signed": np.sign(yr_v1) * (yr_v1 ** 2),
    }, index=sim_df.index)
    return feats, yr_v1


def main() -> None:
    seg_root = ROOT / "data" / "sim" / "segments"
    coeffs = {}
    for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        segs = sorted((seg_root / plat).glob("**/sim.csv"))
        print(f"\n=== {plat}: {len(segs)} segments ===")
        X_list = []
        y_list = []
        for p in segs:
            try:
                df = pd.read_csv(p)
            except Exception:
                continue
            if "yaw_rate_meas_rads" not in df.columns or len(df) < 50:
                continue
            t = df["t_s"].to_numpy()
            if len(t) < 2 or np.any(np.diff(t) <= 0):
                continue
            v = df["v_mps"].to_numpy()
            mask_v = v > 2.0
            if mask_v.sum() < 50:
                continue
            feats, yr_v1 = features_for_segment(df, plat)
            resid = df["yaw_rate_meas_rads"].to_numpy() - yr_v1
            X = feats.to_numpy()
            X_list.append(X[mask_v])
            y_list.append(resid[mask_v])

        X = np.concatenate(X_list, axis=0)
        y = np.concatenate(y_list, axis=0)
        # Subsample for speed (every 4th).
        X = X[::4]
        y = y[::4]
        # Build design with intercept.
        X_design = np.column_stack([np.ones(len(X)), X])
        # Ridge.
        lam = 1e-3 * X_design.shape[0]
        XtX = X_design.T @ X_design
        # Don't regularize intercept.
        I = np.eye(XtX.shape[0]); I[0, 0] = 0
        beta = np.linalg.solve(XtX + lam * I, X_design.T @ y)
        intercept = float(beta[0])
        coeffs[plat] = {
            "intercept": intercept,
            "weights": {name: float(w) for name, w in zip(FEATURES, beta[1:])},
        }
        # Diagnostics.
        y_pred = X_design @ beta
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        # Compare RMSE: pre / post correction.
        rmse_v1 = float(np.sqrt((y ** 2).mean()))
        rmse_corr = float(np.sqrt(((y - y_pred) ** 2).mean()))
        print(f"  intercept={intercept:+.5f}, R²={r2:.4f}, "
              f"V1 yaw_resid rmse={rmse_v1:.5f} -> corrected={rmse_corr:.5f}")
        print(f"  weights={coeffs[plat]['weights']}")

    out_path = ROOT / "out" / "residual_coeffs.json"
    out_path.write_text(json.dumps(coeffs, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
