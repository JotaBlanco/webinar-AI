"""V2: understeer + first-order steering lag.

Model:
  delta_eff = first-order-lag(delta_road, tau)            # tyre/actuator lag
  yaw_geom = v/L * tan(delta_eff)                          # but we use yaw_v0 as a proxy
  yaw_pred = G * yaw_v0_lagged / (1 + Kus * v^2) + bias

We approximate by low-pass filtering yaw_v0 itself with time constant tau —
this captures the first-order lag between commanded steering and actual yaw
response. We also add a small steer-rate damping term `kdot * dyaw_v0/dt`.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-08")
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))

from fit import fit, format_fit_summary
from score import score, format_summary


def lowpass(y: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    """First-order discrete low-pass filter with time-varying dt."""
    if tau <= 1e-6:
        return y.copy()
    out = np.empty_like(y)
    out[0] = y[0]
    dt = np.diff(t)
    # alpha[i] = dt[i] / (tau + dt[i]) — discrete first-order
    for i in range(1, len(y)):
        a = dt[i - 1] / (tau + dt[i - 1])
        out[i] = out[i - 1] + a * (y[i] - out[i - 1])
    return out


def predict_factory(platform: str, coeffs: dict):
    G    = float(coeffs.get("G", 1.0))
    Kus  = float(coeffs.get("Kus", 0.0))
    bias = float(coeffs.get("bias", 0.0))
    tau  = float(coeffs.get("tau", 0.0))
    kdot = float(coeffs.get("kdot", 0.0))

    def predict(sim_df: pd.DataFrame) -> np.ndarray:
        v   = sim_df["v_mps"].to_numpy(dtype=float)
        yv0 = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        t   = sim_df["t_s"].to_numpy(dtype=float)
        # Lagged baseline
        yv0_lag = lowpass(yv0, t, tau) if tau > 1e-6 else yv0
        # rate term (using lagged yaw rate of change as a damping proxy)
        dyv0 = np.zeros_like(yv0)
        if len(yv0) >= 2:
            dyv0[1:] = (yv0[1:] - yv0[:-1]) / np.maximum(np.diff(t), 1e-6)
        yaw = (G * yv0_lag) / (1.0 + Kus * v * v) + kdot * dyv0 + bias
        return yaw

    return predict


def all_segments():
    root = ROOT / "data" / "sim" / "segments"
    return sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())


def main():
    segs = all_segments()
    init = {
        "FORD_F_150_LIGHTNING_MK1": {"G": 0.90, "Kus": 0.0008, "bias": -0.005, "tau": 0.05, "kdot": 0.0},
        "FORD_MUSTANG_MACH_E_MK1":  {"G": 1.16, "Kus": 0.0010, "bias": 0.001,  "tau": 0.05, "kdot": 0.0},
        "HYUNDAI_IONIQ_5":          {"G": 0.97, "Kus": 0.0016, "bias": 0.002,  "tau": 0.05, "kdot": 0.0},
    }
    bounds = {
        p: {"G": (0.5, 1.5), "Kus": (-0.005, 0.02), "bias": (-0.02, 0.02),
            "tau": (0.0, 0.5), "kdot": (-0.2, 0.2)}
        for p in init
    }
    result = fit(
        predict_factory,
        init,
        train_segments=segs,
        objective="yaw_plus_cte",
        bounds=bounds,
        method="L-BFGS-B",
        max_iter=120,
        cte_weight=2.0,
        verbose=False,
    )
    print(format_fit_summary(result))

    coeffs = result["coeffs"]
    coeffs["TESLA_MODEL_3"] = {"G": 1.0, "Kus": 0.0, "bias": 0.0, "tau": 0.0, "kdot": 0.0}
    (ROOT / "out" / "coeffs_v2.json").write_text(json.dumps(coeffs, indent=2))

    def predict_v2(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        c = coeffs.get(platform, {"G": 1.0, "Kus": 0.0, "bias": 0.0, "tau": 0.0, "kdot": 0.0})
        cb = predict_factory(platform, c)
        return pd.DataFrame({"yaw_rate_pred_rads": cb(sim_df)}, index=sim_df.index)

    res = score(predict_v2)
    print()
    print(format_summary(res, top_n=5))


if __name__ == "__main__":
    main()
