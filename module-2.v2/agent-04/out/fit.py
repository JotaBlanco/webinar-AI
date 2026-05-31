"""Reproducer for final-model/coeffs.json.

For each non-Tesla platform, pools all (delta_road, v, yaw_truth) rows under
data/sim/segments/<platform>/ (v_mps > 2 m/s) and minimises mean squared error
of the parametric form

    yaw_pred = kk * v * tan(delta_road - d0) / (L + KK * v^2)

over (d0, kk, KK) by Nelder-Mead. L is taken from the vehicle parameter set
(or inferred for HYUNDAI_IONIQ_5 as 2.97 m).

Tesla is identity (truth = V0 by construction in the sim dataset).
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

PLATFORM_L = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "HYUNDAI_IONIQ_5": 2.97,
}


def fit_platform(d, v, y, L):
    def err(p):
        d0, kk, KK = p
        pred = kk * v * np.tan(d - d0) / (L + KK * v * v)
        return float(np.mean((pred - y) ** 2))

    res = minimize(
        err, [0.0, 1.0, 0.0], method="Nelder-Mead",
        options={"xatol": 1e-7, "fatol": 1e-13, "maxiter": 5000},
    )
    return res.x


def main():
    root = Path("data/sim/segments")
    results = {}
    for plat, L in PLATFORM_L.items():
        rows_d, rows_v, rows_y = [], [], []
        for sim_csv in (root / plat).glob("**/sim.csv"):
            df = pd.read_csv(sim_csv)
            if "yaw_rate_meas_rads" not in df.columns:
                continue
            mask = df["v_mps"] > 2.0
            rows_d.append(df.loc[mask, "delta_road_rad"].values)
            rows_v.append(df.loc[mask, "v_mps"].values)
            rows_y.append(df.loc[mask, "yaw_rate_meas_rads"].values)
        d = np.concatenate(rows_d)
        v = np.concatenate(rows_v)
        y = np.concatenate(rows_y)
        d0, kk, KK = fit_platform(d, v, y, L)
        results[plat] = {"L": L, "d0": float(d0), "kk": float(kk), "KK": float(KK), "tau": 0.0}
        print(f"{plat}: d0={d0:.5e} kk={kk:.4f} KK={KK:.5f}")

    results["TESLA_MODEL_3"] = {"L": 2.875, "d0": 0.0, "kk": 1.0, "KK": 0.0, "tau": 0.0}
    Path("final-model/coeffs.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
