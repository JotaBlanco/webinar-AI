"""Fit k_ff per platform: yr_v1 + k_ff*v*d(delta)/dt ≈ yr_truth."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1  # noqa: E402


def main() -> None:
    seg_root = ROOT / "data" / "sim" / "segments"
    coeffs = {}
    for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        segs = sorted((seg_root / plat).glob("**/sim.csv"))
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
            v1 = predict_v1(df, plat)["yaw_rate_pred_rads"].to_numpy()
            delta = df["delta_road_rad"].to_numpy()
            d_delta = np.gradient(delta, t)
            feat = v * d_delta  # for k_ff
            resid = df["yaw_rate_meas_rads"].to_numpy() - v1
            X_list.append(feat[mask_v])
            y_list.append(resid[mask_v])
        feat = np.concatenate(X_list)
        y = np.concatenate(y_list)
        # subsample
        feat = feat[::4]
        y = y[::4]
        # Fit y = bias + k_ff * feat (2 params).
        A = np.column_stack([np.ones_like(feat), feat])
        beta, *_ = np.linalg.lstsq(A, y, rcond=None)
        bias = float(beta[0])
        k_ff = float(beta[1])
        coeffs[plat] = {"k_ff": k_ff, "bias": bias}
        rmse_pre = float(np.sqrt((y ** 2).mean()))
        rmse_post = float(np.sqrt(((y - A @ beta) ** 2).mean()))
        print(f"{plat}: k_ff={k_ff:.5f}, bias={bias:+.5f}, "
              f"yaw_resid rmse {rmse_pre:.5f} -> {rmse_post:.5f}")
    out = ROOT / "out" / "steer_rate_ff_coeffs.json"
    out.write_text(json.dumps(coeffs, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
