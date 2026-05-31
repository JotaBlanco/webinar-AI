"""Fit model C (a, K, b) per platform on full sim data with a route-grouped train/dev split.

After fitting, score predictions on full set with score-model.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-06")
SEG_ROOT = ROOT / "data" / "sim" / "segments"
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from traj_metrics import cte_diagnostics_segment  # noqa: E402

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def route_split(platform, seed=0, train_frac=0.8):
    paths = sorted((SEG_ROOT / platform).glob("**/sim.csv"))
    routes = {}
    for p in paths:
        r = p.resolve().parents[1].name
        routes.setdefault(r, []).append(p)
    keys = sorted(routes.keys())
    rng = np.random.default_rng(seed)
    rng.shuffle(keys)
    cut = max(1, int(train_frac * len(keys)))
    return ([p for k in keys[:cut] for p in routes[k]],
            [p for k in keys[cut:] for p in routes[k]])


def load_all(paths):
    chunks = []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["t_s", "v_mps", "yaw_rate_meas_rads", "yaw_rate_pred_rads"])
        except Exception:
            continue
        df = df[df["v_mps"] > 2.0]
        if len(df) < 10:
            continue
        chunks.append(df)
    if not chunks:
        return None
    return pd.concat(chunks, ignore_index=True)


def fit_C(df):
    v = df["v_mps"].to_numpy()
    p = df["yaw_rate_pred_rads"].to_numpy()
    t = df["yaw_rate_meas_rads"].to_numpy()

    def loss(x):
        a, K, b = x
        if K < -0.001 or K > 0.01:
            return 1e6
        denom = 1.0 + K * v * v
        yr = a * p / denom + b
        return float(np.mean((yr - t) ** 2))

    res = minimize(loss, [1.0, 0.001, 0.0], method="Nelder-Mead",
                   options={"xatol": 1e-7, "fatol": 1e-10, "maxiter": 2000})
    return {"a": float(res.x[0]), "K": float(res.x[1]), "b": float(res.x[2])}


def main():
    coeffs = {}
    for plat in PLATFORMS:
        train_paths, dev_paths = route_split(plat)
        print(f"\n=== {plat}: train_paths={len(train_paths)}, dev_paths={len(dev_paths)} ===")
        train_df = load_all(train_paths)
        dev_df   = load_all(dev_paths)
        print(f" train samples={len(train_df):,}, dev samples={len(dev_df):,}")
        coef = fit_C(train_df)
        print(f" coef: {coef}")
        # Yaw RMSE on train/dev
        for label, df in (("train", train_df), ("dev", dev_df)):
            v = df["v_mps"].to_numpy()
            p = df["yaw_rate_pred_rads"].to_numpy()
            t = df["yaw_rate_meas_rads"].to_numpy()
            yr = coef["a"] * p / (1.0 + coef["K"] * v * v) + coef["b"]
            rmse = float(np.sqrt(np.mean((yr - t) ** 2)))
            rmse_v0 = float(np.sqrt(np.mean((p - t) ** 2)))
            print(f"  {label}: V0={rmse_v0:.6f}, ours={rmse:.6f}")
        coeffs[plat] = coef
    # Tesla: identity
    coeffs["TESLA_MODEL_3"] = {"a": 1.0, "K": 0.0, "b": 0.0}

    out_path = ROOT / "out" / "coeffs_v1.json"
    out_path.write_text(json.dumps(coeffs, indent=2))
    print(f"\nSaved {out_path}")
    return coeffs


if __name__ == "__main__":
    main()
