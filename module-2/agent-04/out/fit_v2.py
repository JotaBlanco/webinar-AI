"""V2 fit: V1 + steering-rate lead term.

Model:  yr_pred = v * (d + tau * ddot) / (L_eff + Kus * v^2) + bias

where ddot = d/dt of delta_road. The tau term advances the steering angle
in time, modelling the pipeline-delay between steering and yaw measurement.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-04")
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))

from fit import fit, format_fit_summary  # noqa: E402

L_PRIOR = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "HYUNDAI_IONIQ_5":          3.00,
}


def _ddot(t, d):
    # Centered gradient (numpy.gradient handles uneven dt)
    return np.gradient(d, t)


def predict_factory(platform, coeffs):
    if platform == "TESLA_MODEL_3":
        def predict(sim_df):
            return sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        return predict

    L_eff = coeffs["L_eff"]
    Kus = coeffs["Kus"]
    bias = coeffs["bias"]
    tau = coeffs["tau"]

    def predict(sim_df):
        t = sim_df["t_s"].to_numpy(dtype=float)
        v = sim_df["v_mps"].to_numpy(dtype=float)
        d = sim_df["delta_road_rad"].to_numpy(dtype=float)
        ddot = _ddot(t, d)
        d_lead = d + tau * ddot
        denom = L_eff + Kus * v * v
        return v * d_lead / denom + bias

    return predict


def main():
    seg_root = ROOT / "data" / "sim" / "segments"
    all_paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    train, dev = [], []
    for p in all_paths:
        route = p.resolve().parents[1].name
        h = hash(route) & 0xff
        if h < 200:
            train.append(p)
        else:
            dev.append(p)
    print(f"train={len(train)} dev={len(dev)}")

    # Seed from V1
    v1 = json.loads((ROOT / "out" / "coeffs_v1.json").read_text())

    init = {}
    bounds = {}
    for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        c = v1[plat]
        init[plat] = {"L_eff": c["L_eff"], "Kus": c["Kus"], "bias": c["bias"], "tau": 0.05}
        bounds[plat] = {
            "L_eff": (1.5, 5.0),
            "Kus": (-0.005, 0.02),
            "bias": (-0.02, 0.02),
            "tau": (-0.5, 0.5),
        }
    init["TESLA_MODEL_3"] = {"dummy": 0.0}
    bounds["TESLA_MODEL_3"] = {"dummy": (-1.0, 1.0)}

    result = fit(
        predict_factory, init, train_segments=train,
        objective="yaw_plus_cte", dev_segments=dev,
        bounds=bounds, cte_weight=1.0, max_iter=120,
    )
    print(format_fit_summary(result))

    out = ROOT / "out" / "coeffs_v2.json"
    with out.open("w") as f:
        json.dump(result["coeffs"], f, indent=2)
    print(f"saved → {out}")


if __name__ == "__main__":
    main()
