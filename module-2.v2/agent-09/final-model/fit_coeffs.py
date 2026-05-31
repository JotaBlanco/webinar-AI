"""Fit per-platform (a, K, b) coefficients by minimising pooled yaw-rate MSE.

Form: yhat = a * shift(yp, +S) / (1 + K * v^2) + b, with S fixed at 2 samples.

Pools across all sim.csv under `data/sim/segments/<PLATFORM>/**/sim.csv`,
filtered to v_mps > 2.0. Tesla is skipped (its sim truth column is the V0
output itself; passthrough is optimal).

Writes `coeffs.json` next to this script.
"""
from __future__ import annotations

import json
import pathlib
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = pathlib.Path(__file__).resolve().parents[1] / "data" / "sim" / "segments"
SHIFT = 2  # samples; ~40 ms at 50 Hz, compensates V0 actuator lag
V_FILTER = 2.0  # m/s, matches score-model's sample_filter_v_mps


def _shift_forward(arr: np.ndarray, s: int) -> np.ndarray:
    if s <= 0:
        return arr
    out = np.empty_like(arr)
    out[:s] = arr[0]
    out[s:] = arr[:-s]
    return out


def main() -> dict:
    per_plat = defaultdict(list)
    for p in ROOT.glob("*/**/sim.csv"):
        platform = p.resolve().parents[3].name
        if platform == "TESLA_MODEL_3":
            continue
        try:
            df = pd.read_csv(
                p, usecols=["t_s", "v_mps", "yaw_rate_meas_rads", "yaw_rate_pred_rads"]
            )
        except Exception:
            continue
        if len(df) < 100:
            continue
        per_plat[platform].append(df)

    coeffs = {
        "TESLA_MODEL_3": {
            "a": 1.0, "K": 0.0, "b": 0.0, "shift": 0,
            "note": "V0 passthrough; truth column on Tesla sim IS the V0 output.",
        }
    }

    for platform, dfs in per_plat.items():
        yp_list, yt_list, v_list = [], [], []
        for df in dfs:
            v = df["v_mps"].to_numpy(float)
            m = v > V_FILTER
            if m.sum() < 50:
                continue
            yp = df["yaw_rate_pred_rads"].to_numpy(float)
            yt = df["yaw_rate_meas_rads"].to_numpy(float)
            yp_s = _shift_forward(yp, SHIFT)
            yp_list.append(yp_s[m]); yt_list.append(yt[m]); v_list.append(v[m])
        yp = np.concatenate(yp_list)
        yt = np.concatenate(yt_list)
        v = np.concatenate(v_list)

        def loss(p):
            a, K, b = p
            return float(np.mean((a * yp / (1.0 + K * v * v) + b - yt) ** 2))

        res = minimize(
            loss, x0=[1.0, 5e-4, 0.0], method="Nelder-Mead",
            options={"xatol": 1e-7, "fatol": 1e-12, "maxiter": 2000},
        )
        a, K, b = (float(x) for x in res.x)
        rmse = float(np.sqrt(loss(res.x)))
        coeffs[platform] = {"a": a, "K": K, "b": b, "shift": SHIFT, "fit_rmse": rmse}
        print(f"{platform}: a={a:.5f} K={K:.6g} b={b:+.6f} shift={SHIFT} -> rmse={rmse:.5f}")

    out_path = pathlib.Path(__file__).resolve().parent / "coeffs.json"
    out_path.write_text(json.dumps(coeffs, indent=2) + "\n")
    print(f"\nwrote {out_path}")
    return coeffs


if __name__ == "__main__":
    main()
